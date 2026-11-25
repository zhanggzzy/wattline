"""Windows probe wire format and normalization into Wattline measurements."""
import base64
import ntpath
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .host_probe import gpu_measurements, gpu_number


# EncodedCommand uses UTF-16LE. Only this small bootstrap passes through the
# OpenSSH default shell. The packaged script and JSON options arrive on stdin.
_BOOTSTRAP = (
    '$ErrorActionPreference="Stop";'
    '[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);'
    '$source=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([Console]::ReadLine()));'
    '& ([ScriptBlock]::Create($source))'
)
COMMAND = (
    'powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand',
    base64.b64encode(_BOOTSTRAP.encode('utf-16-le')).decode('ascii'),
)
SCRIPT = base64.b64encode(Path(__file__).with_name('windows_probe.ps1').read_bytes())


def processor_percent(count, samples):
    if not isinstance(samples, list) or count is None or len(samples) != count:
        return None
    values = {}
    for row in samples:
        if not isinstance(row, dict):
            return None
        name, percent = row.get('name'), row.get('percent')
        if not isinstance(name, str) or not re.fullmatch(r'[0-9]+,[0-9]+', name):
            return None
        position = tuple(map(int, name.split(',')))
        if position in values or type(percent) not in (int, float) or not 0 <= percent <= 100:
            return None
        values[position] = percent
    return round(sum(values.values()) / count, 2)


def capacity(value):
    if isinstance(value, dict):
        total, available = value.get('total_bytes'), value.get('available_bytes')
        if type(total) is int and type(available) is int and total > 0 and 0 <= available <= total:
            return {'total_bytes':total, 'available_bytes':available}
    return None


def gpu_processes(device, evidence, observed_at):
    rows = []
    for item in device.findall('processes/process_info'):
        pid = (item.findtext('pid') or '').strip()
        if not re.fullmatch(r'[0-9]{1,10}', pid) or not 0 < int(pid) <= 2**32-1:
            continue
        row = {'pid':int(pid), 'type':item.findtext('type'), 'used_memory_mib':gpu_number(item, 'used_memory')}
        name = (item.findtext('process_name') or '').strip()
        if name and name.upper() != 'N/A' and not name.startswith('['):
            basename = ntpath.basename(name)
            if basename:
                row['name'] = basename[:128]
        match = evidence.get(str(row['pid']))
        if isinstance(match, dict):
            start = match.get('started_at')
            if type(start) is int and type(observed_at) is int and 0 < start < observed_at <= 8_640_000_000_000_000:
                row.update(started_at=start, elapsed_seconds=(observed_at-start)//1000)
                row.update({key:match[key][:128] for key in ('name', 'user') if isinstance(match.get(key), str)})
        rows.append(row)
    return rows


def nvidia_metrics(data, options, warnings):
    result = {'gpus':[], 'gpu_inventory_complete':False, 'driver_version':None}
    query = data.get('nvidia')
    expected = options.get('expected_gpu_count')
    if isinstance(query, dict) and query.get('empty') is True:
        result['gpu_inventory_complete'] = expected is None
        if expected is not None:
            warnings.append('GPU 清单与配置不符或不可见，无法核实空闲状态')
        return result
    try:
        root = ET.fromstring(base64.b64decode(query['xml'], validate=True))
        if root.tag != 'nvidia_smi_log':
            raise ValueError()
    except (KeyError, TypeError, ValueError, ET.ParseError):
        warnings.append('nvidia-smi 未返回有效 GPU 数据，请检查驱动、可见范围或采集权限')
        return result

    inspect = 'processes' in options['checks']
    evidence = data.get('process_evidence')
    if not isinstance(evidence, dict):
        evidence = {}
    observed_at = data.get('gpu_observed_at')
    devices, uuids = root.findall('gpu'), set()
    for device in devices:
        uuid = device.findtext('uuid', '').strip()
        if not uuid.startswith('GPU-') or uuid in uuids:
            continue
        uuids.add(uuid)
        gpu = gpu_measurements(device, uuid, warnings)
        rows = gpu_processes(device, evidence, observed_at) if inspect else []
        gpu.update(processes=rows, process_visibility='partial' if inspect else None,
                   state='occupied' if rows else 'unknown')
        result['gpus'].append(gpu)

    reported = root.findtext('attached_gpus')
    count_matches = reported is None or reported.strip() == str(len(devices))
    complete = (len(uuids) == len(devices) and count_matches
                and (bool(devices) or reported is not None)
                and (expected is None or len(devices) == expected))
    if not complete:
        warnings.append('GPU 清单与配置不符或不可见，无法核实空闲状态')
    if inspect and any(gpu['state'] == 'unknown' for gpu in result['gpus']):
        warnings.append('部分 GPU 占用状态无法核实')
    if any(gpu['utilization_percent'] is None or gpu['power_w'] is None for gpu in result['gpus']):
        warnings.append('部分 GPU 的利用率或实时功耗缺失')
    result.update(gpu_inventory_complete=complete, driver_version=root.findtext('driver_version'))
    return result


def metrics(data, options):
    warnings = []
    checks = options['checks']
    result = {key:data[key] for key in ('host_id', 'boot_id', 'source_observed_at') if key in data}
    result.update(scope='host', load_average=[], warnings=warnings)
    if 'cpu' in checks:
        count = data.get('cpu_count')
        count = count if type(count) is int and count > 0 else None
        cpu = processor_percent(count, data.get('cpu_samples'))
        if cpu is None:
            warnings.append('无法读取覆盖所有逻辑处理器的 Windows CPU 数据')
        result.update(cpu_count=count, cpu_percent=cpu)
    if 'memory' in checks:
        result['memory'] = capacity(data.get('memory'))
        if result['memory'] is None:
            warnings.append('无法读取宿主内存容量')
    if 'system' in checks:
        result['uptime_seconds'] = data.get('uptime_seconds')
        disk = data.get('root_disk')
        size = capacity(disk)
        volume = disk.get('volume') if size else None
        if isinstance(volume, str) and re.fullmatch(r'[A-Za-z]:', volume):
            result['root_disk'] = dict(size, volume=volume)
            if size['available_bytes'] / size['total_bytes'] < 0.05:
                warnings.append('系统盘可用空间低于 5%')
        else:
            warnings.append('无法读取 Windows 系统卷容量')
    if 'gpu' in checks:
        result.update(nvidia_metrics(data, options, warnings))
        if result['gpu_inventory_complete'] and not result['gpus']:
            result['gpu_inventory_empty'] = True
    return result
