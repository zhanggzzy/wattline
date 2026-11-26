"""Read-only Linux resource probe, also sent verbatim over SSH."""
from decimal import Decimal, DecimalException
import json
import math
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def host_identity(config, *, enrollment=False):
    proc = Path(config.get('host_proc', '/proc'))
    machine_id = Path(config.get('host_machine_id', '/etc/machine-id'))
    if config['mode'] == 'local' and Path('/.dockerenv').exists() and (str(proc) == '/proc' or str(machine_id) == '/etc/machine-id'):
        raise ValueError('容器内本机检查需要显式宿主 proc 和 machine-id 只读挂载')
    host_id = machine_id.read_text().strip()
    if (enrollment and not re.fullmatch(r'[a-f0-9]{32}', host_id)) or (
        not enrollment and (not host_id or host_id != config['expected_host_id'])
    ):
        raise ValueError('宿主身份与固定配置不符')
    boot_id = (proc/'sys/kernel/random/boot_id').read_text().strip()
    if not boot_id:
        raise ValueError('无法核实宿主启动身份')
    return proc, host_id, boot_id


def monitor_identity(config):
    _, host_id, boot_id = host_identity(config, enrollment=True)
    return {'host_id':host_id, 'boot_id':boot_id}



def gpu_number(gpu, *fields):
    for field in fields:
        try:
            value = float((gpu.findtext(field) or '').split()[0])
            if math.isfinite(value) and value >= 0:
                return value
        except (ValueError, IndexError):
            pass
    return None


def gpu_power(gpu, field):
    return gpu_number(gpu, 'gpu_power_readings/'+field, 'power_readings/'+field)


def measured_gpu_power(gpu):
    for field, kind in (('average_power_draw','average'), ('instant_power_draw','instantaneous'),
                        ('instantaneous_power_draw','instantaneous'), ('power_draw','reported')):
        watts = gpu_power(gpu, field)
        if watts is not None:
            return watts, kind
    return None, None


def gpu_measurements(gpu, uuid, warnings):
    temperature = gpu_number(gpu, 'temperature/gpu_temp')
    slowdown = gpu_number(gpu, 'temperature/gpu_temp_slow_threshold')
    if temperature is not None and slowdown and temperature >= slowdown:
        warnings.append(f'{uuid} 的温度已达到 GPU 降频阈值')
    watts, power_kind = measured_gpu_power(gpu)
    power_limit = gpu_power(gpu, 'current_power_limit')
    if power_limit is None:
        power_limit = gpu_power(gpu, 'enforced_power_limit')
    default_power_limit = gpu_power(gpu, 'default_power_limit')
    return {
        'uuid':uuid, 'name':gpu.findtext('product_name'), 'bus_id':gpu.findtext('pci/pci_bus_id'),
        'memory_used_mib':gpu_number(gpu, 'fb_memory_usage/used'),
        'memory_total_mib':gpu_number(gpu, 'fb_memory_usage/total'),
        'utilization_percent':gpu_number(gpu, 'utilization/gpu_util'),
        'temperature_c':temperature, 'power_w':watts, 'power_kind':power_kind, 'power_limit_w':power_limit,
        'default_power_limit_w':default_power_limit or None,
    }


def pid_start_ticks(process):
    return int((process/'stat').read_text().rsplit(')', 1)[1].split()[19])


def source_wall_time():
    try:
        observed_at = time.time()
    except OSError:
        return None
    return observed_at if 0 < observed_at <= 8.64e12 else None


def process_timing(start, start_limit, ticks_per_second, sampled_at):
    # A start in the sampling tick can belong to a PID reused after the cutoff.
    if sampled_at is None or start + 1 > start_limit:
        return {}
    elapsed = (start_limit - start) / ticks_per_second
    if elapsed >= sampled_at:
        return {}
    started_at_ms = round((sampled_at - float(elapsed)) * 1000)
    if started_at_ms <= 0:
        return {}
    return {'started_at':started_at_ms, 'elapsed_seconds':int(elapsed)}


def process_workload(cgroup):
    paths = [line.split(':', 2)[2] for line in cgroup.splitlines() if line.count(':') >= 2]
    for path in paths:
        pod = re.search(r'(?:^|[/-])pod([0-9a-f]{8}(?:[-_][0-9a-f]{4}){3}[-_][0-9a-f]{12})(?:\.slice)?(?:/|$)', path)
        container = re.search(r'(?:/docker/|/(docker|cri-containerd|crio)-)([0-9a-f]{64})(?:\.scope)?(?:/|$)', path)
        if pod:
            cgroupfs = re.match(r'([0-9a-f]{64})(?:/|$)', path[pod.end():])
            return {'kind':'kubernetes', 'pod_uid':pod[1].replace('_', '-'),
                    'container_id':container[2] if container else cgroupfs[1] if cgroupfs else None}
        if container:
            return {'kind':{None:'docker', 'docker':'docker', 'cri-containerd':'containerd', 'crio':'cri-o'}[container[1]],
                    'container_id':container[2]}
    if paths and all(path == '/' or path.startswith(('/system.slice/', '/user.slice/', '/init.scope')) for path in paths):
        return {'kind':'host'}
    return None


def process_identity(proc, pid, start_limit, users):
    target = proc/str(pid)
    try:
        start = pid_start_ticks(target)
        if not 0 <= start <= start_limit:
            return {}
        uid_line = next(line for line in (target/'status').read_text().splitlines() if line.startswith('Uid:'))
        uid = int(uid_line.split()[2])
        name = (target/'comm').read_text(errors='replace').strip()[:64]
        if pid_start_ticks(target) != start:
            return {}
        try:
            workload = process_workload((target/'cgroup').read_text())
        except OSError:
            workload = None
        if pid_start_ticks(target) != start:
            return {}
    except (OSError, ValueError, IndexError, StopIteration):
        return {}
    if uid not in users:
        try:
            users[uid] = pwd.getpwuid(uid).pw_name[:128] if proc == Path('/proc') else None
        except (KeyError, OSError):
            users[uid] = None
    user = users[uid]
    return {'uid':uid, 'user':user, 'name':name, 'start_ticks':start, 'workload':workload}


def host_users(proc):
    if proc == Path('/proc'):
        return {}
    # A container's own passwd database can assign different names to host UIDs.
    try:
        records = (proc/'1/root/etc/passwd').read_text(errors='replace').splitlines()
    except OSError:
        return {}
    users = {}
    for row in records:
        fields = row.split(':')
        if len(fields) == 7 and fields[2].isascii() and fields[2].isdigit():
            users.setdefault(int(fields[2]), fields[0][:128])
    return users


def monitor_gpus(config, proc, warnings, *, host_processes=True, warn_on_unknown=True):
    inventory = {'gpus': [], 'driver_version': None, 'gpu_inventory_complete': False}
    if not config.get('require_gpu', True):
        return inventory
    processes_enabled = config.get('monitor_processes', True)
    host_processes = host_processes and processes_enabled
    if host_processes:
        try:
            ticks_per_second = os.sysconf('SC_CLK_TCK')
            start_limit = Decimal((proc/'uptime').read_text().split()[0]) * ticks_per_second
            if ticks_per_second <= 0 or not start_limit.is_finite() or start_limit < 0:
                raise ValueError()
        except (OSError, IndexError, ValueError, DecimalException):
            host_processes = False
            warnings.append('无法核实宿主进程启动时间')
    sampled_at = source_wall_time() if host_processes else None
    try:
        nvidia = subprocess.run(['nvidia-smi', '-q', '-x'], capture_output=True, timeout=config.get('gpu_timeout', 6))
        if nvidia.returncode:
            raise ValueError()
        root = ET.fromstring(nvidia.stdout)
        if root.tag != 'nvidia_smi_log':
            raise ValueError()
    except (OSError, IndexError, ValueError, ET.ParseError, subprocess.TimeoutExpired):
        warnings.append('nvidia-smi 未返回有效 GPU 数据，请检查驱动、可见范围或采集权限')
        return inventory

    devices = root.findall('gpu')
    uuids = {gpu.findtext('uuid', '').strip() for gpu in devices}
    expected = config.get('expected_gpu_count')
    inventory_ok = (bool(devices) and (expected is None or expected == len(devices))
                    and len(uuids) == len(devices) and all(uuid.startswith('GPU-') for uuid in uuids)
                    and set(config.get('allowed_gpu_uuids', ())) <= uuids)
    if not inventory_ok:
        warnings.append('GPU 清单与配置不符或不可见，无法核实空闲状态')

    identities, gpus = {}, {}
    users = host_users(proc) if host_processes else {}
    for gpu in devices:
        uuid = gpu.findtext('uuid', '').strip()
        if not uuid.startswith('GPU-') or uuid in gpus:
            continue
        table = gpu.find('processes')
        visible = (host_processes and table is not None and (table.text or '').strip() in ('', 'None')
                   and gpu.findtext('mig_mode/current_mig') in (None, 'Disabled', 'N/A', '[N/A]'))
        processes = []
        for item in gpu.findall('processes/process_info') if processes_enabled else ():
            try:
                pid = int(item.findtext('pid') or '')
                if pid <= 0:
                    raise ValueError()
            except ValueError:
                visible = False
                continue
            if pid not in identities:
                identity = process_identity(proc, pid, start_limit, users) if host_processes else {}
                if identity:
                    identity.update(process_timing(identity['start_ticks'], start_limit, ticks_per_second, sampled_at))
                identities[pid] = identity
            processes.append({'pid':pid, 'type':item.findtext('type'), **identities[pid],
                              'used_memory_mib':gpu_number(item, 'used_memory')})
        used = gpu_number(gpu, 'fb_memory_usage/used')
        state = 'unknown'
        if processes:
            state = 'occupied'
        elif inventory_ok and visible and used is not None and used <= config.get('idle_memory_tolerance_mib', 0):
            state = 'free'
        gpus[uuid] = {
            **gpu_measurements(gpu, uuid, warnings),
            'processes':processes, 'process_visibility':('complete' if visible else 'partial') if processes_enabled else None,
            'state':state,
        }
    if host_processes and any(gpu['process_visibility'] == 'partial' for gpu in gpus.values()):
        warnings.append('部分 GPU 进程不可完整枚举，可能处于 MIG 模式')
    if host_processes and any(not process.get('workload') or 'uid' not in process for gpu in gpus.values() for process in gpu['processes']):
        warnings.append('部分进程归属未核实，可能缺少宿主读取权限或进程已退出')
    if processes_enabled and warn_on_unknown and any(gpu['state'] == 'unknown' for gpu in gpus.values()):
        warnings.append('部分 GPU 占用状态无法核实')
    if any(gpu['utilization_percent'] is None or gpu['power_w'] is None for gpu in gpus.values()):
        warnings.append('部分 GPU 的利用率或实时功耗缺失')
    return {'gpus':list(gpus.values()), 'driver_version':root.findtext('driver_version'),
            'gpu_inventory_complete':inventory_ok}


def monitor_cpu(proc, warnings):
    metrics = {'cpu_count':None, 'cpu_ticks':None}
    try:
        lines = (proc/'stat').read_text().splitlines()
        metrics['cpu_count'] = sum(line.startswith('cpu') and line[3:4].isdigit() for line in lines) or None
        fields = next(line.split()[1:9] for line in lines if line.startswith('cpu '))
        ticks = [int(field) for field in fields]
        if len(ticks) == 8 and all(tick >= 0 for tick in ticks):
            metrics['cpu_ticks'] = ticks
    except (OSError, ValueError, StopIteration):
        pass
    if metrics['cpu_ticks'] is None:
        warnings.append('无法读取宿主 CPU 累计计数')
    return metrics


def monitor_memory(proc, warnings):
    try:
        mem = {line.split(':')[0]:int(line.split()[1])*1024
               for line in (proc/'meminfo').read_text().splitlines()
               if line.startswith(('MemTotal:', 'MemAvailable:'))}
        total, available = mem['MemTotal'], mem['MemAvailable']
        if 0 <= available <= total and total > 0:
            return {'total_bytes':total, 'available_bytes':available}
    except (OSError, ValueError, IndexError, KeyError):
        pass
    warnings.append('无法读取宿主内存容量')
    return None


def monitor_numbers(proc, file, count, warnings, message):
    try:
        values = [float(v) for v in (proc/file).read_text().split()[:count]]
        if len(values) == count and all(math.isfinite(v) and v >= 0 for v in values):
            return values
    except (OSError, ValueError):
        pass
    warnings.append(message)
    return []


def monitor_metrics(proc, warnings, checks):
    metrics = {'memory':None}
    if 'cpu' in checks:
        metrics.update(monitor_cpu(proc, warnings))
        metrics['load_average'] = monitor_numbers(proc, 'loadavg', 3, warnings, '无法读取宿主负载')
    if 'memory' in checks:
        metrics['memory'] = monitor_memory(proc, warnings)
    if 'system' in checks:
        uptime = monitor_numbers(proc, 'uptime', 1, warnings, '无法读取宿主运行时长')
        metrics['uptime_seconds'] = uptime[0] if uptime else None
    return metrics


def container_cgroup(proc, root=Path('/sys/fs/cgroup')):
    # A private cgroup v2 mount can present the container as "/" with PID 1 in init.scope.
    if (root/'cgroup.type').is_file():
        return root
    try:
        memberships = (proc/'1/cgroup').read_text().splitlines()
    except OSError:
        return None
    for line in memberships:
        if not line.startswith('0::/'):
            continue
        parts = Path(line[3:]).parts[1:]
        if '..' in parts:
            continue
        for index, part in enumerate(parts):
            if re.fullmatch(r'(?:(?:docker|libpod|cri-containerd|crio)-)?[a-f0-9]{64}(?:\.scope)?', part):
                scope = root.joinpath(*parts[:index+1])
                if (scope/'cgroup.type').is_file():
                    return scope
    return None


def cgroup_limits(group, file):
    root = Path('/sys/fs/cgroup')
    for directory in (group, *group.parents):
        if directory != group and directory != root and root not in directory.parents:
            break
        try:
            fields = (directory/file).read_text().split()
        except FileNotFoundError:
            continue
        if fields and fields[0] != 'max':
            yield fields


def cgroup_cpu(group):
    counters = dict(line.split() for line in (group/'cpu.stat').read_text().splitlines())
    observed_ns = time.monotonic_ns()
    usage_ns = int(counters['usage_usec'])*1000
    if usage_ns < 0:
        raise ValueError('无效的容器 CPU 计数')
    try:
        allowed = (group/'cpuset.cpus.effective').read_text().strip().split(',')
        capacity = 0
        for interval in allowed:
            first, _, last = interval.partition('-')
            capacity += int(last or first)-int(first)+1
    except (OSError, ValueError):
        capacity = len(os.sched_getaffinity(0))
    limits = (int(quota)/int(period) for quota, period in cgroup_limits(group, 'cpu.max'))
    capacity = min(capacity, min(limits, default=capacity))
    if capacity <= 0:
        raise ValueError('无效的容器 CPU 容量')
    return {'usage_ns':usage_ns, 'observed_ns':observed_ns, 'capacity':capacity, 'group':group.stat().st_ino}


def cgroup_memory(group):
    used = int((group/'memory.current').read_text())
    limits = [int(fields[0]) for fields in cgroup_limits(group, 'memory.max')]
    limit = min(limits, default=None)
    if used < 0 or (limit is not None and limit <= 0):
        raise ValueError('无效的容器内存用量或限制')
    return {'used_bytes':used, 'total_bytes':limit, 'available_bytes':max(0,limit-used) if limit is not None else None}


def container_metrics(proc, warnings, checks):
    metrics = {'memory':None}
    if 'cpu' not in checks and 'memory' not in checks:
        return metrics
    group = container_cgroup(proc)
    if group is None:
        warnings.append('无法核实容器的 cgroup v2 指标范围')
        return metrics
    if 'cpu' in checks:
        try:
            cpu = cgroup_cpu(group)
            metrics.update(container_cpu=cpu, cpu_count=cpu['capacity'])
        except (OSError, ValueError, KeyError, ZeroDivisionError):
            warnings.append('无法读取容器 CPU 用量')
    if 'memory' in checks:
        try:
            metrics['memory'] = cgroup_memory(group)
        except (OSError, ValueError):
            warnings.append('无法读取容器内存用量')
    return metrics


def monitor(config):
    proc, host_id, boot_id = host_identity(config)
    source_observed_at = source_wall_time()
    warnings = []
    container_endpoint = config['mode'] == 'ssh' and (
        Path('/.dockerenv').exists() or Path('/run/.containerenv').exists()
    ) and (proc == Path('/proc') or config.get('host_machine_id', '/etc/machine-id') == '/etc/machine-id')
    checks = config.get('checks', ('cpu', 'memory', 'system', 'gpu', 'processes'))
    container_resources = container_endpoint and config.get('monitor_container_resources', False)
    if container_resources:
        metrics = container_metrics(proc, warnings, checks)
    elif container_endpoint:
        metrics = {'memory':None}
        warnings.append('SSH 端点位于容器中，仅展示可见 GPU。宿主 CPU、内存、系统盘及进程归属未核实')
    else:
        metrics = monitor_metrics(proc, warnings, checks)
    root_disk = None
    if not container_endpoint and 'system' in checks:
        try:
            stat = os.statvfs(proc/'1/root' if proc != Path('/proc') else '/')
            root_disk = {'total_bytes':stat.f_blocks*stat.f_frsize, 'available_bytes':stat.f_bavail*stat.f_frsize}
        except OSError:
            warnings.append('无法读取宿主系统盘')
    if not container_endpoint:
        for capacity, label in ((metrics['memory'], '可用内存'), (root_disk, '系统盘可用空间')):
            if capacity and capacity['total_bytes'] and capacity['available_bytes'] / capacity['total_bytes'] < .05:
                warnings.append(label+'低于 5%')
    gpu_config = dict(config, require_gpu='gpu' in checks and config.get('require_gpu', True),
                      monitor_processes='processes' in checks)
    inventory = monitor_gpus(gpu_config, proc, warnings, host_processes=not container_endpoint,
                             warn_on_unknown=not container_resources)
    return {'host_id':host_id, 'boot_id':boot_id, 'source_observed_at':source_observed_at,
            **metrics, **inventory, 'root_disk':root_disk, 'warnings':warnings,
            'scope':'container' if container_endpoint else 'host'}


if __name__ == '__main__':
    try:
        collect = {'--monitor':monitor, '--monitor-identity':monitor_identity}.get(
            sys.argv[1] if len(sys.argv) == 2 else '', monitor)
        print(json.dumps({'data':collect(json.load(sys.stdin))}, allow_nan=False))
    except Exception as exc:
        # No SSH, Docker stderr or external command text in public evidence.
        print(json.dumps({'error':str(exc) if isinstance(exc, ValueError) else '宿主检查失败：权限、路径或进程在采样期间变化'}))
        sys.exit(1)
