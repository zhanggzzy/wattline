import asyncio
from datetime import datetime
import gzip
import json
import sqlite3
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import pytest

from wattline.app import create_app
from wattline.collector import CollectionError, Collector, HostIdentity, cpu_percent
from wattline.config import Config, Machine, MachineRegistration, MachineSettings
from wattline.history import DAY_MS, WARM_HOURS, WARM_MS, History, HistoryInUse
from wattline.history_schema import HOT_SCHEMA, SCHEMA_VERSION
from wattline.service import ARCHIVE_ZONE, Monitor, archive_slots, metrics_from
from wattline import host_probe


ID = 'a'*32
GPU = 'GPU-11111111-2222-3333-4444-555555555555'
OTHER_GPU = 'GPU-22222222-3333-4444-5555-666666666666'


def machine(id='lab-01', expected_host_id=ID, **kwargs):
    return Machine(id=id, expected_host_id=expected_host_id, mode='ssh', ssh_alias=id, **kwargs)


def data(host=ID, gpu=GPU, boot='boot-1', ticks=None, util=0):
    return {'host_id':host,'boot_id':boot,'source_observed_at':100,
        'cpu_ticks':ticks or [100,0,20,300,0,0,0,0], 'cpu_count':8, 'load_average':[1.2,1,1],
        'memory':{'total_bytes':128*1024**3,'available_bytes':96*1024**3},
        'root_disk':{'available_bytes':512*1024**3,'total_bytes':1024**4},
        'uptime_seconds':600, 'driver_version':'580-fixture', 'gpu_inventory_complete':True, 'warnings':[],
        'gpus':[{'uuid':gpu,'name':'Fixture GPU','state':'occupied','bus_id':'00000000:04:00.0',
                 'utilization_percent':util,'memory_used_mib':2048,'memory_total_mib':4096,
                 'temperature_c':43,'power_w':125,'power_limit_w':300,'power_kind':'average',
                 'process_visibility':'complete',
                 'processes':[{'pid':93,'uid':1050,'user':'fixture-owner','start_ticks':70,'name':'fixture-worker',
                               'cmdline':'private-parameter','workload':{'kind':'docker','container_id':'abc'},
                               'used_memory_mib':2048}]}]}


def test_monitor_probe_nvidia_power_and_host_fields(tmp_path, monkeypatch):
    proc = tmp_path/'proc'
    values = {
        'sys/kernel/random/boot_id':'boot', '1/root/etc/passwd':'', 'uptime':'1000.00 400',
        'stat':'cpu 100 20 20 400 0 1 3 2 1000 2000\ncpu0 100 20 20 400 0 1 3 2',
        'meminfo':'MemTotal:  102400 kB\nMemAvailable: 76800 kB', 'loadavg':'0.4 0.6 0.5 1/9 5',
        '93/stat':'93 (worker) '+' '.join(['0']*19+['100']),
        '93/status':'Uid:\t1050\t1050\t1050\t1050', '93/comm':'worker',
        '93/cgroup':'0::/system.slice/docker-'+'a'*64+'.scope',
    }
    for key, content in values.items():
        path = proc/key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    machine_file = tmp_path/'machine-id'
    machine_file.write_text(ID)
    config = dict(mode='ssh', host_proc=str(proc), host_machine_id=str(machine_file), expected_host_id=ID)
    xml = f"""<nvidia_smi_log><driver_version>580.173.02</driver_version>
        <gpu><uuid>{GPU}</uuid><utilization><gpu_util>0 %</gpu_util></utilization>
          <gpu_power_readings><average_power_draw>42.3 W</average_power_draw><instant_power_draw>43 W</instant_power_draw>
            <current_power_limit>450 W</current_power_limit><default_power_limit>500 W</default_power_limit>
            <max_power_limit>600 W</max_power_limit></gpu_power_readings>
          <module_power_readings><default_power_limit>1000 W</default_power_limit></module_power_readings>
          <fb_memory_usage><used>2048 MiB</used><total>98304 MiB</total></fb_memory_usage>
          <processes><process_info><pid>93</pid><used_memory>2048 MiB</used_memory></process_info></processes>
        </gpu><gpu><uuid>{OTHER_GPU}</uuid><power_readings><power_draw>35 W</power_draw>
          <enforced_power_limit>300 W</enforced_power_limit></power_readings>
          <mig_mode><current_mig>Enabled</current_mig></mig_mode><processes>None</processes></gpu>
        </nvidia_smi_log>""".encode()
    monkeypatch.setattr(host_probe.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0, stdout=xml))
    sample = host_probe.monitor(config)
    assert sample['cpu_ticks'] == [100,20,20,400,0,1,3,2]
    assert sample['memory']['available_bytes'] == 76800*1024
    assert sample['driver_version'] == '580.173.02'
    assert sample['scope'] == 'host'
    primary, legacy = sample['gpus']
    assert (primary['power_w'],primary['power_kind'],primary['power_limit_w']) == (42.3,'average',450)
    assert primary['default_power_limit_w'] == 500
    assert primary['state'] == 'occupied' and primary['utilization_percent'] == 0
    gpu_only = host_probe.monitor(dict(config, checks=['gpu']))
    assert gpu_only['gpus'][0]['power_w'] == 42.3
    assert gpu_only['gpus'][0]['processes'] == [] and gpu_only['gpus'][0]['state'] == 'unknown'
    assert gpu_only['memory'] is None and gpu_only['root_disk'] is None and 'cpu_ticks' not in gpu_only
    proc_info = primary['processes'][0]
    assert proc_info['user'] is None and proc_info['uid'] == 1050
    assert proc_info['workload'] == {'kind':'docker','container_id':'a'*64}
    assert (legacy['power_w'],legacy['power_limit_w'],legacy['state']) == (35,300,'unknown')
    assert legacy['default_power_limit_w'] is None
    # The container can report a device PID through NVML with no trustworthy host ownership.
    cgroup = tmp_path/'cgroup'
    cgroup.mkdir()
    for file, contents in {
        'cgroup.type':'domain', 'cpu.stat':'usage_usec 12000000\nuser_usec 9000000',
        'cpu.max':'150000 100000', 'cpuset.cpus.effective':'0-3,7',
        'memory.current':'970', 'memory.max':'1000',
    }.items():
        (cgroup/file).write_text(contents)
    (proc/'1/cgroup').write_text('0::/init.scope\n')
    with monkeypatch.context() as container:
        exists = host_probe.Path.exists
        find_cgroup = host_probe.container_cgroup
        container.setattr(host_probe.Path,'exists',lambda path:path == host_probe.Path('/.dockerenv') or exists(path))
        container.setattr(host_probe,'host_identity',lambda _: (proc,ID,'boot'))
        container.setattr(host_probe,'container_cgroup',lambda proc: find_cgroup(proc, cgroup))
        limited = host_probe.monitor({'mode':'ssh','monitor_container_resources':True})
        (cgroup/'memory.max').write_text('max')
        unlimited = host_probe.monitor({'mode':'ssh','checks':['memory'],'monitor_container_resources':True})
    assert limited['scope'] == 'container'
    assert limited['cpu_count'] == 1.5 and limited['container_cpu']['usage_ns'] == 12_000_000_000
    assert limited['memory'] == {'used_bytes':970,'total_bytes':1000,'available_bytes':30}
    assert limited['root_disk'] is None and 'cpu_ticks' not in limited and 'load_average' not in limited
    assert limited['warnings'] == ['部分 GPU 的利用率或实时功耗缺失']
    assert unlimited['warnings'] == []
    assert unlimited['memory'] == {'used_bytes':970,'total_bytes':None,'available_bytes':None}
    assert limited['gpus'][0]['power_w'] == 42.3 and limited['gpus'][0]['process_visibility'] == 'partial'
    assert limited['gpus'][0]['processes'][0] == {'pid':93, 'type':None, 'used_memory_mib':2048}
    (proc/'93/status').unlink()
    assert host_probe.monitor(config)['gpus'][0]['processes'][0].get('uid') is None
    assert host_probe.monitor(dict(config, require_gpu=False))['gpus'] == []

    def timeout(*args, **kwargs):
        raise host_probe.subprocess.TimeoutExpired('nvidia-smi', 1)

    monkeypatch.setattr(host_probe.subprocess, 'run', timeout)
    assert host_probe.monitor(dict(config, checks=['memory']))['warnings'] == []
    waiting = host_probe.monitor(config)
    assert waiting['gpus'] == [] and waiting['memory'] == sample['memory']
    assert any('nvidia-smi' in warning for warning in waiting['warnings'])


def test_idle_memory_tolerance_configuration_defaults():
    def load(**settings):
        payload = {'data_dir':'data', 'machines':[{
            'id':'lab-01', 'mode':'ssh', 'ssh_alias':'lab-01', 'expected_host_id':ID, **settings}]}
        return Config.model_validate_json(json.dumps(payload)).machines[0]

    assert load().idle_memory_tolerance_mib == 256
    assert load(idle_memory_tolerance_mib=0).idle_memory_tolerance_mib == 0
    assert load(idle_memory_tolerance_mib=512).idle_memory_tolerance_mib == 512


def idle_gpu_xml(used='0 MiB', *, processes='None', mig=None, inventory=''):
    memory = (f'<fb_memory_usage><used>{used}</used><total>98304 MiB</total></fb_memory_usage>'
              if used else '')
    mig_xml = f'<mig_mode><current_mig>{mig}</current_mig></mig_mode>' if mig else ''
    return (f'<nvidia_smi_log>{inventory}<gpu><uuid>{GPU}</uuid>{mig_xml}{memory}'
            f'<processes>{processes}</processes></gpu></nvidia_smi_log>').encode()


@pytest.mark.parametrize(('options', 'xml', 'state'), [
    ({}, idle_gpu_xml('0 MiB'), 'free'),
    ({}, idle_gpu_xml('256 MiB'), 'free'),
    ({}, idle_gpu_xml('256.5 MiB'), 'unknown'),
    ({'idle_memory_tolerance_mib':0}, idle_gpu_xml('128 MiB'), 'unknown'),
    ({'idle_memory_tolerance_mib':2048}, idle_gpu_xml('1024 MiB'), 'free'),
    ({}, idle_gpu_xml('0 MiB', processes='<process_info><pid>93</pid></process_info>'), 'occupied'),
    ({}, idle_gpu_xml(''), 'unknown'),
    ({}, idle_gpu_xml('0 MiB', processes='N/A'), 'unknown'),
    ({}, idle_gpu_xml('0 MiB', mig='Enabled'), 'unknown'),
    ({'expected_gpu_count':2}, idle_gpu_xml('0 MiB'), 'unknown'),
], ids=['default-zero', 'default-boundary', 'above-boundary', 'explicit-zero',
        'explicit-high', 'occupied-process', 'missing-used', 'partial-enumeration',
        'mig-partial', 'incomplete-inventory'])
def test_linux_gpu_occupancy_tolerance(tmp_path, monkeypatch, options, xml, state):
    proc = tmp_path/'proc'
    proc.mkdir()
    (proc/'uptime').write_text('1000.00 0')
    monkeypatch.setattr(host_probe.subprocess, 'run',
                        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=xml))
    warnings = []
    gpu = host_probe.monitor_gpus(dict(options), proc, warnings)['gpus'][0]
    assert gpu['state'] == state
    assert '部分 GPU 占用状态无法核实' not in warnings


@pytest.mark.parametrize(('inventory', 'complete', 'state'), [
    pytest.param('', True, 'free', id='absent'),
    pytest.param('<attached_gpus> 1 </attached_gpus>', True, 'free', id='matching'),
    pytest.param('<attached_gpus>01</attached_gpus>', True, 'free', id='leading-zero'),
    pytest.param('<attached_gpus>2</attached_gpus>', False, 'unknown', id='mismatch'),
    pytest.param('<attached_gpus>0</attached_gpus>', False, 'unknown', id='reports-zero'),
    pytest.param('<attached_gpus>-1</attached_gpus>', False, 'unknown', id='negative'),
    pytest.param('<attached_gpus>1.0</attached_gpus>', False, 'unknown', id='fractional'),
    pytest.param('<attached_gpus> </attached_gpus>', False, 'unknown', id='blank'),
    pytest.param('<attached_gpus>N/A</attached_gpus>', False, 'unknown', id='unavailable'),
    pytest.param('<attached_gpus>1</attached_gpus>' * 2, False, 'unknown', id='duplicate'),
    pytest.param('<attached_gpus>1<count/></attached_gpus>', False, 'unknown', id='nested'),
    pytest.param('<attached_gpus>2</attached_gpus>', False, 'occupied', id='pid-priority'),
])
async def test_linux_gpu_inventory_count_and_collection_validity(tmp_path, monkeypatch, inventory, complete, state):
    host = machine(checks=('gpu', 'processes'))
    (tmp_path/'uptime').write_text('1000.00 0')
    used, processes = '128 MiB', 'None'
    if state == 'occupied':
        used, processes = 'N/A', 'N/A<process_info><pid>93</pid></process_info>'
    xml = idle_gpu_xml(used, processes=processes, inventory=inventory)
    monkeypatch.setattr(host_probe.subprocess, 'run',
                        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=xml))

    async def collect(node):
        warnings = []
        measured = host_probe.monitor_gpus(
            {'idle_memory_tolerance_mib':node.idle_memory_tolerance_mib}, tmp_path, warnings)
        return dict(data(), **measured, warnings=warnings)

    monitor = Monitor(Config(data_dir=tmp_path, machines=(host,)), collect)
    try:
        snapshot = await monitor.observe(host)
        metrics = snapshot['metrics']
        gpu, = metrics['gpus']
        assert metrics['gpu_inventory_complete'] is monitor.inventory_complete[host.id] is complete
        assert (gpu['state'], gpu['process_visibility']) == (
            state, 'partial' if state == 'occupied' else 'complete')
        assert ('GPU 清单与配置不符或不可见，无法核实空闲状态' in snapshot['warnings']) is not complete
        assert '部分 GPU 占用状态无法核实' not in snapshot['warnings']
        assert monitor.compute_alert(host, snapshot)[4] == {}
    finally:
        await monitor.close()


@pytest.mark.parametrize(('processes', 'state'), [
    ('None', 'unknown'),
    ('<process_info><pid>93</pid></process_info>', 'occupied'),
])
def test_container_view_keeps_partial_process_visibility(tmp_path, monkeypatch, processes, state):
    proc = tmp_path/'proc'
    proc.mkdir()
    (proc/'uptime').write_text('1000.00 0')
    xml = idle_gpu_xml(processes=processes)
    monkeypatch.setattr(host_probe.subprocess, 'run',
                        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=xml))
    warnings = []
    gpu = host_probe.monitor_gpus({'idle_memory_tolerance_mib':256}, proc, warnings, host_processes=False)['gpus'][0]
    assert (gpu['state'], gpu['process_visibility']) == (state, 'partial')
    assert '部分 GPU 占用状态无法核实' not in warnings


@pytest.mark.parametrize(('case', 'verified'), [
    ('valid', True),
    ('subsecond', True),
    ('boundary_tick', True),
    ('after_boundary', False),
    ('reused_during_reads', False),
    ('exited_during_reads', False),
    ('unreadable_cgroup', True),
    ('unavailable_uptime', False),
    ('invalid_uptime', False),
    ('unavailable_tick_rate', False),
    ('unavailable_wall_clock', True),
    ('invalid_wall_clock', True),
])
def test_gpu_process_timing_from_verified_source_sample(tmp_path, monkeypatch, case, verified):
    proc = tmp_path/'proc'
    target = proc/'93'
    target.mkdir(parents=True)
    uptime = proc/'uptime'
    if case != 'unavailable_uptime':
        uptime.write_text('NaN 0' if case == 'invalid_uptime' else '4500.00 0')
    start = {'subsecond':449999, 'boundary_tick':450000, 'after_boundary':450001}.get(case, 350)
    (target/'stat').write_text('93 (worker) name) '+' '.join(['0']*19+[str(start)]))
    (target/'status').write_text('Uid: 1050 1050 1050 1050')
    (target/'comm').write_text('worker')
    # No cgroup record also exercises the final identity check after an OSError.
    if case not in ('unreadable_cgroup', 'exited_during_reads'):
        (target/'cgroup').write_text('0::/system.slice/test.scope')
    sampled_at = 1_790_000_000.25
    wall = sampled_at - 4

    def wall_clock():
        nonlocal wall
        if case == 'unavailable_wall_clock':
            raise OSError()
        if case == 'invalid_wall_clock':
            return float('nan')
        observed_at = wall
        wall += 4
        return observed_at

    def nvidia(*args, **kwargs):
        nonlocal wall
        wall += 6
        uptime.write_text('4506.00 0')
        return SimpleNamespace(returncode=0, stdout=f'''<nvidia_smi_log><gpu><uuid>{GPU}</uuid>
            <processes><process_info><pid>93</pid><used_memory>2048 MiB</used_memory></process_info></processes>
            </gpu></nvidia_smi_log>'''.encode())

    monkeypatch.setattr(host_probe, 'time', SimpleNamespace(time=wall_clock))
    monkeypatch.setattr(host_probe, 'host_identity', lambda _: (proc, ID, 'boot-fixture'))
    monkeypatch.setattr(host_probe.os, 'sysconf', lambda name: -1 if case == 'unavailable_tick_rate' else 100)
    monkeypatch.setattr(host_probe.subprocess, 'run', nvidia)
    if case == 'exited_during_reads':
        read_text = host_probe.Path.read_text

        def exit_before_cgroup_read(path, *args, **kwargs):
            if path == target/'cgroup':
                (target/'stat').unlink()
            return read_text(path, *args, **kwargs)

        monkeypatch.setattr(host_probe.Path, 'read_text', exit_before_cgroup_read)
    if case == 'reused_during_reads':
        readings = iter([start, start, 450001])
        monkeypatch.setattr(host_probe, 'pid_start_ticks', lambda _: next(readings))

    result = host_probe.monitor({'mode':'ssh', 'checks':['gpu','processes'], 'host_machine_id':'fixture-machine-id'})
    assert result['source_observed_at'] == (
        None if case in ('unavailable_wall_clock', 'invalid_wall_clock') else sampled_at - 4)
    json.dumps(result, allow_nan=False)
    process = result['gpus'][0]['processes'][0]
    assert (process['pid'], process['used_memory_mib']) == (93, 2048)
    assert ('uid' in process) == verified
    if case in ('valid', 'subsecond', 'unreadable_cgroup'):
        assert (process['started_at'], process['elapsed_seconds']) == (
            (1_790_000_000_240, 0) if case == 'subsecond' else (1_789_995_503_750, 4496))
    else:
        assert 'started_at' not in process and 'elapsed_seconds' not in process
    if case == 'unreadable_cgroup':
        assert process['workload'] is None


def test_legacy_gpu_process_snapshot_keeps_visible_fields():
    process = metrics_from(data(), None)['gpus'][0]['processes'][0]
    assert process == {'pid':93, 'uid':1050, 'user':'fixture-owner', 'name':'fixture-worker',
                       'workload':{'kind':'docker','container_id':'abc'}, 'used_memory_mib':2048}


def test_cpu_delta_rejects_first_reset_and_empty_interval():
    first = [100,0,20,300,0,0,0,0]
    second = [130,0,30,350,10,0,0,0]
    assert cpu_percent(None, first) is None
    assert cpu_percent(first, first) is None
    assert cpu_percent(second, first) is None
    assert cpu_percent(first, second) == 40


@pytest.mark.parametrize('destination,user', [('lab-01',None), ('192.0.2.114','observer')])
async def test_ssh_destination_and_mismatched_identity_are_bounded(tmp_path, destination, user):
    host = Machine(id='lab-01', expected_host_id=ID, mode='ssh', ssh_alias=destination, ssh_user=user)
    config = Config(data_dir=tmp_path, machines=(host,))

    async def run(argv, payload, timeout):
        assert argv[-2] == destination
        if user is not None:
            assert argv[1:3] == ['-l', user]
        else:
            assert '-l' not in argv
        assert '-oStrictHostKeyChecking=yes' in argv and '-oUpdateHostKeys=no' in argv
        assert json.loads(payload)['expected_host_id'] == ID
        assert timeout == config.timeout_seconds
        return 0, json.dumps({'data':data(host='b'*32)}).encode(), b''

    with pytest.raises(CollectionError, match='身份'):
        await Collector(config,run)(host)


class ManualTime:
    def __init__(self):
        self.seconds = 0
        self.changed = asyncio.Event()

    def clock(self):
        return 1700000000000+round(self.seconds*1000)

    async def sleep(self, delay):
        end = self.seconds+delay
        while self.seconds < end:
            await self.changed.wait()
        await asyncio.sleep(0)

    def advance(self, delta):
        self.seconds += delta
        previous = self.changed
        self.changed = asyncio.Event()
        previous.set()


async def eventual(condition):
    async with asyncio.timeout(3):
        while not condition():
            await asyncio.sleep(.005)


async def run_monitor_iteration(monitor, loop, *args):
    original_sleep = monitor.sleep
    slept = False

    async def stop_after_iteration(_delay):
        nonlocal slept
        if slept:
            raise asyncio.CancelledError
        slept = True

    monitor.sleep = stop_after_iteration
    try:
        with pytest.raises(asyncio.CancelledError):
            await loop(*args)
    finally:
        monitor.sleep = original_sleep


@pytest.mark.parametrize(('fault', 'status', 'evidence'), [
    ('failure', 'unknown', '宿主身份或启动身份无法核实'),
    ('timeout', 'offline', '采集超过单机时限'),
    ('expiry', 'stale', 'sample_stale'),
])
async def test_collection_alerts_are_independent_of_gpu_occupancy(tmp_path, fault, status, evidence):
    host = machine(interval_seconds=10)
    config = Config(data_dir=tmp_path, machines=(host,), interval_seconds=1,
                    stale_seconds=3, timeout_seconds=.1, gpu_timeout_seconds=.05)
    clock = ManualTime()
    sample = data()
    sample['gpus'][0].update(state='free', processes=[])
    sample['gpus'].append(dict(sample['gpus'][0], uuid=OTHER_GPU, state='unknown',
                               process_visibility='partial'))
    sample['warnings'] = ['部分 GPU 的利用率或实时功耗缺失']
    response = 'valid'

    async def collect(_):
        if response == 'timeout':
            await asyncio.Event().wait()
        return dict(sample, host_id=None) if response == 'failure' else sample

    monitor = Monitor(config, collect, clock.clock)
    monitor.history.prepare()
    monitor.registry_loaded = True
    try:
        await run_monitor_iteration(monitor, monitor.run, host)
        view, = monitor.snapshot()['machines']
        assert [gpu['state'] for gpu in view['metrics']['gpus']] == ['free', 'unknown']
        assert view['status'] == 'warning'
        assert (await monitor.alert_events(True, 10, 0))['events'] == []

        if fault == 'expiry':
            clock.advance(view['stale_ms']/1000-.001)
            await run_monitor_iteration(monitor, monitor.check_freshness)
            assert (await monitor.alert_events(True, 10, 0))['events'] == []
            clock.advance(.001)
            await run_monitor_iteration(monitor, monitor.check_freshness)
        else:
            response = fault
            clock.advance(1)
            await run_monitor_iteration(monitor, monitor.run, host)

        assert monitor.snapshot()['machines'][0]['status'] == status
        event, = (await monitor.alert_events(True, 10, 0))['events']
        assert (event['rule'], event['evidence'], event['first_at']) == ('collection', evidence, clock.clock())
        assert event['last_success_at'] == view['observed_at']

        response = 'valid'
        clock.advance(1)
        await run_monitor_iteration(monitor, monitor.run, host)
        assert (await monitor.alert_events(True, 10, 0))['events'] == []
        recovered = await monitor.alert_event(event['id'])
        assert recovered['recovered_at'] == clock.clock()
        assert recovered['recovery_evidence'] == 'collection_resumed'
        assert monitor.snapshot()['machines'][0]['metrics']['gpus'][1]['state'] == 'unknown'
    finally:
        monitor.history.close()


async def test_collection_recovery_respects_sample_timing(tmp_path):
    host = machine()
    config = Config(data_dir=tmp_path, machines=(host,))
    clock = ManualTime()
    response = 'valid'

    async def collect(_):
        if response == 'crosses_previous_expiry':
            clock.advance(.001)
            await run_monitor_iteration(monitor, monitor.check_freshness)
        if response == 'already_expired':
            clock.advance(monitor.stale_seconds(host))
        return dict(data(), host_id=None) if response == 'failure' else data()

    monitor = Monitor(config, collect, clock.clock)
    monitor.history.prepare()
    monitor.registry_loaded = True
    try:
        await run_monitor_iteration(monitor, monitor.run, host)
        clock.advance(monitor.stale_seconds(host)-.001)
        response = 'crosses_previous_expiry'
        await run_monitor_iteration(monitor, monitor.run, host)
        expiry, = (await monitor.alert_events(False, 10, 0))['events']
        assert expiry['evidence'] == 'sample_stale'
        assert expiry['recovered_at'] == clock.clock() == expiry['first_at']
        assert monitor.latest[host.id]['observed_at'] < expiry['first_at']

        response = 'failure'
        clock.advance(2)
        await run_monitor_iteration(monitor, monitor.run, host)
        fault, = (await monitor.alert_events(True, 10, 0))['events']

        # A late write of a superseded sample can have a later receipt time.
        response = 'valid'
        clock.advance(-1)
        older = await monitor.observe(host)
        clock.advance(2)
        older['received_at'] = clock.clock()
        await monitor.write(monitor.history.append, host.history_key, monitor.epoch,
                            dict(older, alert_event=monitor.compute_alert(host, older)))
        assert (await monitor.alert_events(True, 10, 0))['events'] == [fault]

        response = 'already_expired'
        await run_monitor_iteration(monitor, monitor.run, host)
        active, = (await monitor.alert_events(True, 10, 0))['events']
        assert (active['id'], active['evidence'], active['recovered_at']) == (fault['id'], 'sample_stale', None)
    finally:
        monitor.history.close()


async def test_container_cpu_uses_remote_elapsed_time_and_resets_on_group_change(tmp_path):
    host = machine()
    clock = ManualTime()
    group = 1

    async def collect(node):
        return {'host_id':ID,'boot_id':'boot','scope':'container','cpu_count':1.5,
                'container_cpu':{'observed_ns':int(3e9*clock.seconds),'usage_ns':int(1.125e9*clock.seconds),
                                 'capacity':1.5,'group':group},
                'memory':{'total_bytes':None,'used_bytes':1024,'available_bytes':None}}

    monitor = Monitor(Config(data_dir=tmp_path,machines=(host,)),collect,clock.clock)
    initial = await monitor.observe(host)
    assert initial['status'] == 'normal' and initial['metrics']['cpu_percent'] is None
    clock.advance(1)
    metrics = (await monitor.observe(host))['metrics']
    assert metrics['cpu_percent'] == 25
    assert metrics['memory_percent'] is None and metrics['memory']['used_bytes'] == 1024
    group = 2
    clock.advance(1)
    assert (await monitor.observe(host))['metrics']['cpu_percent'] is None


async def test_inventory_confidence_survives_failed_samples_and_recovers(tmp_path, monkeypatch):
    host = machine()
    config = Config(data_dir=tmp_path, machines=(host,))
    now = 100_000
    xml = b''
    mode = 'sample'

    def card(uuid):
        return f'<gpu><uuid>{uuid}</uuid><product_name>NVIDIA B300 SXM6 AC</product_name></gpu>'.encode()

    async def collect(_):
        if mode == 'offline':
            raise asyncio.TimeoutError
        warnings = []
        probed = host_probe.monitor_gpus({'monitor_processes':False}, tmp_path, warnings)
        return dict(data(), **probed) | {'warnings':warnings}

    monkeypatch.setattr(host_probe.subprocess, 'run',
                        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=xml))
    monitor = Monitor(config, collect, clock=lambda: now)

    async def sample(devices, *, offline=False):
        nonlocal now, xml, mode
        now += 1_000
        xml = b'<nvidia_smi_log>' + devices + b'</nvidia_smi_log>'
        mode = 'offline' if offline else 'sample'
        monitor.latest[host.id] = await monitor.observe(host)
        return monitor.snapshot()['machines'][0]

    assert monitor.snapshot()['machines'][0]['gpu_inventory_complete'] is None
    partial = await sample(card(GPU) + card('N/A'))
    assert partial['gpu_inventory_complete'] is partial['metrics']['gpu_inventory_complete'] is False
    first_failure = await sample(b'', offline=True)
    assert first_failure['status'] == 'offline' and first_failure['metrics'] is None
    assert first_failure['gpu_inventory_complete'] is False
    assert first_failure['devices'] == partial['devices']

    full = await sample(card(GPU) + card(OTHER_GPU))
    assert full['gpu_inventory_complete'] is full['metrics']['gpu_inventory_complete'] is True
    now += full['stale_ms']
    stale = monitor.snapshot()['machines'][0]
    assert stale['status'] == 'stale' and stale['metrics'] is None
    assert stale['gpu_inventory_complete'] is True
    assert (await sample(b'', offline=True))['gpu_inventory_complete'] is True

    merged = await sample(card(GPU) + card('N/A'))
    assert {gpu['uuid'] for gpu in merged['devices']} == {GPU, OTHER_GPU}
    assert merged['gpu_inventory_complete'] is False
    assert (await sample(b'', offline=True))['gpu_inventory_complete'] is False
    recovered = await sample(card(GPU))
    assert recovered['gpu_inventory_complete'] is True
    assert [gpu['uuid'] for gpu in recovered['devices']] == [GPU]
    no_devices = await sample(b'')
    assert no_devices['gpu_inventory_complete'] is False
    assert no_devices['devices'] == recovered['devices']
    assert (await sample(b'', offline=True))['gpu_inventory_complete'] is False


@pytest.mark.parametrize('packed', [False, True], ids=['hot', 'warm'])
async def test_inventory_confidence_restores_with_device_history(tmp_path, packed):
    evidence = {'full':True, 'partial':False, 'legacy':None, 'later-empty':False}
    hosts = tuple(machine(name, index * 32, enabled=False)
                  for name, index in zip(evidence, 'abcd'))
    config = Config(data_dir=tmp_path, machines=hosts)
    now = 10 * DAY_MS
    recorded_at = now - 2 * DAY_MS
    history = History(tmp_path)
    history.prepare()
    for host in hosts:
        metrics = {'gpus':data()['gpus']}
        complete = evidence[host.id]
        if complete is not None:
            metrics['gpu_inventory_complete'] = complete if host.id != 'later-empty' else True
        sample = dict(observed_at=recorded_at, received_at=recorded_at, source='ssh', boot='boot',
                      status='normal', metrics=metrics)
        history.append(host.history_key, 'fixture', sample)
        if host.id == 'later-empty':
            history.append(host.history_key, 'fixture', dict(
                sample, observed_at=recorded_at+1, metrics={'cpu_percent':20, 'gpu_inventory_complete':False}))
        history.append(host.history_key, 'fixture', dict(
            sample, observed_at=recorded_at+2, boot=None, status='offline', metrics=None))
    if packed:
        assert history.pack(now-DAY_MS) == 9
    history.close()

    restored = Monitor(config, clock=lambda: now)
    try:
        await restored.load_registry()
        for view in restored.snapshot()['machines']:
            assert view['status'] == 'disabled' and view['metrics'] is None
            assert view['gpu_inventory_complete'] is evidence[view['id']]
            assert [gpu['name'] for gpu in view['devices']] == ['Fixture GPU']
    finally:
        restored.history.close()


async def test_background_scheduling_timeout_disk_fault_boot_and_shutdown(tmp_path, monkeypatch):
    slow = machine('slow', 'b'*32)
    enabled = machine()
    disabled = machine('disabled', 'c'*32, enabled=False)
    config = Config(data_dir=tmp_path, machines=(slow, enabled, disabled), interval_seconds=1,
                    stale_seconds=3, timeout_seconds=.25, gpu_timeout_seconds=.1, concurrency=2)
    clock = ManualTime()
    calls = {node.id:0 for node in config.machines}
    release = asyncio.Event()

    async def collect(node):
        calls[node.id] += 1
        if node == slow and calls[node.id] == 1:
            await release.wait()
        count = calls[node.id]
        return data(host=node.expected_host_id, boot='boot-1' if count < 3 else 'boot-2',
                    ticks=[100+count*20,0,20,300+count*30,0,0,0,0])

    service = Monitor(config,collect,clock.clock,clock.sleep,lambda:clock.seconds)
    append = service.history.append

    def disk_failure(*args):
        raise sqlite3.OperationalError('fixture write failure')

    await service.start()
    try:
        await eventual(lambda:enabled.id in service.latest)
        assert service.latest[enabled.id]['metrics']['cpu_percent'] is None
        clock.advance(1.05)
        await eventual(lambda:calls[enabled.id] == 2 and service.latest[enabled.id]['metrics']['cpu_percent'] == 40)
        assert calls[slow.id] == 1 and calls[disabled.id] == 0
        await eventual(lambda:service.latest.get(slow.id,{}).get('status') == 'offline')
        monkeypatch.setattr(service.history, 'append', disk_failure)
        clock.advance(1)
        await eventual(lambda: not service.history_ok and calls[enabled.id] == 3)
        assert service.latest[enabled.id]['metrics']['cpu_percent'] is None
        assert next(node for node in service.snapshot()['machines'] if node['id']==enabled.id)['metrics']['gpus']
        monkeypatch.setattr(service.history, 'append', append)
        clock.advance(1)
        await eventual(lambda: service.history_ok and calls[enabled.id] >= 4)
        assert service.latest[enabled.id]['metrics']['cpu_percent'] == 40
    finally:
        await service.close()
    assert all(task.done() for task in service.tasks)
    clock.advance(4)
    assert next(node for node in service.snapshot()['machines'] if node['id']==enabled.id)['status'] == 'stale'


def test_sqlite_interruption_restart_retention_device_and_privacy(tmp_path):
    db = History(tmp_path)
    now = 1700000000000
    # The installed service may already have a version-zero database.
    with db.connect() as legacy:
        for statement in HOT_SCHEMA:
            legacy.execute(statement)

    def put(at, boot, epoch, gpu=None, status='normal'):
        metrics = {'cpu_percent':30, 'gpu_percent':0, 'gpu_util_count':1, 'gpus':data(gpu=gpu)['gpus']} if gpu else None
        db.append(ID, epoch, {'observed_at':at, 'received_at':at+1, 'boot':boot,
                              'source':'ssh', 'status':status, 'metrics':metrics})

    put(now-WARM_MS-1, 'boot-1', 'service-1', GPU)
    put(now-WARM_MS, 'boot-1', 'service-1', GPU)
    put(now-DAY_MS-1, 'boot-1', 'service-1', GPU)
    put(now-DAY_MS, 'boot-1', 'service-1', GPU)
    put(now-50000, 'boot-1', 'service-1', GPU)
    put(now-40000, None, 'service-1', status='offline')
    put(now-30000, 'boot-1', 'service-1', GPU)
    put(now-20000, 'boot-2', 'service-2', GPU)
    put(now-10000, 'boot-2', 'service-2', OTHER_GPU)
    db.close()
    reopened = History(tmp_path)
    reopened.prepare()
    try:
        with pytest.raises(HistoryInUse):
            History(tmp_path).prepare()
        points = reopened.series([], ID, GPU, 'gpu', 1, now, 10000, 30000)['points']
        assert [item['values'][0] for item in points] == [0,None,0,0,None]
        assert all(item['breaks'][0] for item in points)
        assert reopened.series([], ID, OTHER_GPU,'power',1,now,10000,30000)['points'][-1]['values'] == [125]
        aggregate = reopened.series([], ID, GPU,'gpu',24,now,10000,30000)
        assert len(aggregate['points']) <= 400 and aggregate['bucket_ms']
        assert aggregate['points'][0]['time'] == now-DAY_MS
        before = reopened.series([], ID, GPU, 'gpu', WARM_HOURS, now, 10000, 30000)
        assert reopened.begin_archive(now) == now
        assert reopened.pack(now-DAY_MS) == 3
        assert reopened.pack(now-DAY_MS) == 0
        assert reopened.series([], ID, GPU, 'gpu', WARM_HOURS, now, 10000, 30000) == before
        assert before['points'][0]['time'] == now-WARM_MS
        exported = reopened.export(now-WARM_MS)
        assert (exported.hosts, exported.gpus) == (1, 1)
        target = reopened.cold_directory/exported.filename
        with gzip.open(target,'rt') as compressed:
            header, payload = map(json.loads, compressed)
        assert header['before_ms'] == now-WARM_MS
        assert payload['observed_at'] == now-WARM_MS-1
        assert payload['gpus'][0]['uuid'] == GPU and payload['gpus'][0]['power_w'] == 125
        target.unlink()
        with pytest.raises(FileNotFoundError):
            reopened.finish_archive(now,now-WARM_MS,exported)
        assert reopened.begin_archive(now+DAY_MS) == now
        exported = reopened.export(now-WARM_MS)
        reopened.finish_archive(now,now-WARM_MS,exported)
        assert reopened.begin_archive(now) is None
        with reopened.connect(read=True) as conn:
            assert conn.execute('SELECT MIN(at) FROM gpu_ticks').fetchone()[0] == now-DAY_MS
            assert conn.execute('SELECT MIN(at) FROM warm_gpu_ticks').fetchone()[0] == now-WARM_MS
            payloads = str(conn.execute('SELECT metrics FROM gpu_ticks').fetchall())
            assert 'fixture-owner' not in payloads and 'processes' not in payloads and 'cmdline' not in payloads
    finally:
        reopened.close()


def test_archive_runs_at_three_local_time():
    before = datetime(2025,1,2,2,59,59,tzinfo=ARCHIVE_ZONE)
    due, following = archive_slots(int(before.timestamp()*1000))
    assert datetime.fromtimestamp(due/1000, ARCHIVE_ZONE).isoformat() == '2025-01-01T03:00:00+00:00'
    current, tomorrow = archive_slots(following)
    assert current == following and tomorrow-current == DAY_MS


def test_direct_http_auth_and_loopback_host_boundaries(tmp_path):
    password = tmp_path/'test-pass'
    password.write_text('fake-test-only\n')
    config = Config(data_dir=tmp_path/'data', machines=(machine(),), viewer_password_file=password)

    async def collect(node):
        sample = data()
        sample['gpus'][0]['processes'][0].update(started_at=1_789_995_503_750, elapsed_seconds=4496)
        return sample

    service = Monitor(config, collect)
    app = create_app(config, monitor=service)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        assert client.get('/').status_code == 401
        assert client.get('/api/history').status_code == 401
        assert client.put('/api/machines/lab-01/alias',json={'alias':'protected'}).status_code == 401
        assert client.get('/api/snapshot', auth=('monitor','wrong')).status_code == 401
        auth = ('monitor','fake-test-only')
        assert client.get('/api/snapshot', auth=auth, headers={'Host':'outside.invalid'}).status_code == 400
        assert client.get('/api/history', params={'machine':'another'}, auth=auth).status_code == 404
        assert client.get('/api/history', params={'hours':25}, auth=auth).status_code == 422
        assert client.get('/', auth=auth).status_code == 200
        assert client.get('/static/monitor.js', auth=auth).status_code == 200
        for _ in range(100):
            response = client.get('/api/snapshot', auth=auth)
            host = response.json()['machines'][0]
            if host.get('metrics'):
                break
            time.sleep(.01)
        assert response.headers['Cache-Control'] == 'no-store'
        assert host['metrics']['memory_percent'] == 25
        process = host['metrics']['gpus'][0]['processes'][0]
        assert process['user'] == 'fixture-owner'
        assert (process['started_at'], process['elapsed_seconds']) == (1_789_995_503_750, 4496)
        assert all(value not in response.text for value in ('start_ticks','cmdline','expected_host_id','ssh_alias'))


def test_overview_history_returns_aligned_machine_series_and_metrics(tmp_path):
    now = int(time.time()*1000)
    start = now-DAY_MS
    first_at, second_at = start+250*300000, start+251*300000
    first = machine('first', expected_host_id='b'*32)
    second = machine('second', expected_host_id='c'*32)
    config = Config(data_dir=tmp_path, machines=(first,second), interval_seconds=300, stale_seconds=400)
    history = History(tmp_path)
    history.prepare()

    def put(host, at, gpu, cpu, memory, power):
        history.append(host.history_key,'epoch-1',{'observed_at':at,'received_at':at,'boot':'boot-1',
            'source':'ssh','status':'normal','metrics':{'gpu_percent':gpu,'gpu_util_count':1,
            'cpu_percent':cpu,'memory_percent':memory,'gpu_power_w':power}})

    put(first,first_at,0,10,20,100)
    put(first,second_at,40,30,40,200)
    put(second,second_at,80,50,60,300)
    history.close()

    async def collect(node):
        raise CollectionError('offline','合成离线')

    service = Monitor(config, collect, clock=lambda: now)
    with TestClient(create_app(config,monitor=service),base_url='http://127.0.0.1') as client:
        body = client.get('/api/history').json()
        assert body['keys'] == ['gpu'] and body['machines'] == ['first','second']
        points = {point['time']:point for point in body['points']}
        assert points[first_at]['values'] == [0,None] and points[first_at]['breaks'][1] is False
        assert points[second_at]['values'] == [40,80]
        expected = {'cpu':([10,None],[30,50]),'memory':([20,None],[40,60]),'power':([100,None],[200,300])}
        for metric,(opening,closing) in expected.items():
            data = client.get('/api/history',params={'hours':24,'metric':metric}).json()
            indexed = {point['time']:point['values'] for point in data['points']}
            assert data['keys'] == [metric] and indexed[first_at] == opening and indexed[second_at] == closing
        assert client.get('/api/history',params={'metric':'temp'}).status_code == 422
        assert client.get('/api/history',params={'metric':'memory_used'}).status_code == 422
        assert client.get('/api/history',params={'gpu':GPU}).status_code == 422
        assert client.get('/api/history',params={'hours':25}).status_code == 422
        detail = client.get('/api/history',params={'machine':'first','metric':'cpu','hours':24}).json()
        assert detail['keys'] == ['cpu'] and 'machines' not in detail
        assert {point['time']:point['values'] for point in detail['points']}[first_at] == [10]


async def test_overview_history_uses_each_machines_recorded_continuity(tmp_path):
    now = 1_800_000_000_000
    start = now-DAY_MS
    fast = machine('fast', expected_host_id='b'*32)
    slow = machine('slow', expected_host_id='c'*32, interval_seconds=300)
    config = Config(data_dir=tmp_path, machines=(fast,slow))

    async def collect(node):
        raise AssertionError('History reads must not start collection')

    service = Monitor(config, collect, clock=lambda:now)
    service.history.prepare()

    def put(host, at, value, boot='boot-1'):
        metrics = {'gpu_percent':value,'gpu_util_count':1,'gpu_generation':GPU,
                   'gpus':[{'uuid':GPU,'utilization_percent':value}]}
        record = {'observed_at':at,'received_at':at,'boot':boot,'source':'ssh',
                  'status':'normal','metrics':metrics}
        if host == slow:
            record['stale_ms'] = round(service.stale_seconds(slow)*1000)
        service.history.append(host.history_key,'epoch-1',record)

    try:
        put(slow,start-1,99)
        for index in range(8):
            put(slow,start+index*300000,index*11)
        put(slow,start+2400000,None)
        put(slow,start+2700000,80)
        put(slow,start+3000000,81)
        put(slow,start+3600000,82)
        put(slow,start+3900000,83)
        put(slow,start+4200000,84,boot='boot-2')
        put(slow,now,85,boot='boot-2')
        put(slow,now+1,99,boot='boot-2')
        put(fast,start+648000,15)
        put(fast,start+658000,17)

        overview = await service.series(None,None,'gpu',24)
        assert overview['machines'] == ['fast','slow']
        assert (overview['from'],overview['to'],overview['bucket_ms']) == (start,now,216000)
        points = overview['points']
        assert (points[0]['time'],points[-1]['time']) == (start,now)
        assert points[3]['values'] == [16,None] and points[3]['breaks'] == [True,False]
        assert [(point['values'][1],point['breaks'][1]) for point in points if point['values'][1] is not None] == [
            (0,True), (11,False), (22,False), (33,False), (44,False), (55,False), (66,False), (77,False),
            (80,True), (81,False), (82,True), (83,False), (84,True), (85,True),
        ]
        missing = points[2400000//overview['bucket_ms']]
        assert missing['values'][1] is None and missing['breaks'][1] is True
        assert all(point['values'][0] is None for i,point in enumerate(points) if i != 3)

        for gpu in (None,GPU):
            detail = await service.series(slow.history_key,gpu,'gpu',1)
            assert 'machines' not in detail and detail['points'][-1]['values'] == [85]
            assert detail['points'][-1]['time'] == now
        detail = await service.series(slow.history_key,None,'gpu',24)
        assert [(point['values'][0],point['breaks'][0]) for point in detail['points'][:8]] == [
            (index*11,index == 0) for index in range(8)
        ]
        assert detail['points'][7]['time'] == start+2100000
    finally:
        service.history.close()


def test_display_alias_migrates_and_persists_under_fixed_machine_identity(tmp_path):
    host = machine(name='默认名称')
    config = Config(data_dir=tmp_path,machines=(host,))
    history = History(tmp_path)
    history.prepare()
    original_at = int(time.time()*1000)-10000
    history.append(ID,'before-upgrade',{'observed_at':original_at,'received_at':original_at,
        'boot':'boot-1','source':'ssh','status':'normal','metrics':{'gpu_percent':13}})
    with history.connect() as conn:
        conn.execute('DROP TABLE machine_aliases')
        conn.execute('DROP TABLE machine_settings')
        conn.execute('DROP TABLE machine_ssh_pins')
        conn.execute('DROP TABLE machine_order')
        conn.execute('DROP TABLE removed_config_machines')
        conn.execute('DROP TABLE pending_machine_removals')
        set_legacy_registry_version(conn, 2)
    history.close()

    async def collect(node):
        return data()

    url = '/api/machines/lab-01/alias'
    def app():
        return create_app(config,monitor=Monitor(config,collect))

    with TestClient(app(),base_url='http://127.0.0.1') as client:
        assert client.put(url,json={'alias':'cross'},headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
        assert client.put('/api/machines/unknown/alias',json={'alias':'any'}).status_code == 404
        assert client.put(url,json={'alias':'a'*81}).status_code == 422
        assert client.put(url,json={'alias':'one\ntwo'}).status_code == 422
        assert client.put(url,json={'alias':'新名字','ssh_alias':'different'}).status_code == 422
        assert client.put(url,json={'alias':'  显示节点  '}).json() == {
            'id':'lab-01','alias':'显示节点','name':'显示节点',
        }
        assert client.get('/api/snapshot').json()['machines'][0]['name'] == '显示节点'

    with TestClient(app(),base_url='http://127.0.0.1') as client:
        assert client.get('/api/snapshot').json()['machines'][0]['name'] == '显示节点'
        params={'machine':'lab-01','metric':'gpu','hours':1}
        points=client.get('/api/history',params=params).json()['points']
        assert any(point['time']==original_at and point['values']==[13] for point in points)
        assert client.put(url,json={'alias':None}).json()['name'] == '默认名称'


def set_legacy_registry_version(db, version):
    for table in ('global_configuration','cluster_resources','resource_rooms','resource_order','clusters','rooms',
                      'storage_ticks','storage_resources','alerts','shared_users'):
        db.execute(f'DROP TABLE {table}')
    db.execute('DROP TABLE machine_assignees')
    db.execute('DROP TABLE people')
    db.execute(f'PRAGMA user_version={version}')


def test_assignees_migrate_legacy_names_once_and_retry_atomically(tmp_path):
    hosts = [machine(f'lab-{i}', char*32, enabled=False) for i, char in enumerate('abcde')]
    config = Config(data_dir=tmp_path, machines=tuple(hosts[:-1]))
    history = History(tmp_path)
    history.prepare()
    old = MachineSettings(enabled=False).model_dump(mode='json', exclude={'alias'})
    rows = [dict(old, assigned_user='  张三  '), dict(old, assigned_user='张三'),
            dict(old, assigned_user=None), old, dict(old, assigned_user='  ')]
    for host, settings in zip(hosts, rows):
        registration = host.model_dump_json() if host == hosts[-1] else None
        history.save_machine(host.history_key, registration, json.dumps(settings), '旧别名', {})
    with history.connect() as db:
        set_legacy_registry_version(db, 7)
        db.execute("""CREATE TRIGGER fail_migration BEFORE UPDATE OF settings ON machine_settings
                      WHEN OLD.machine LIKE 'b%'
                      BEGIN SELECT RAISE(ABORT, 'fixture migration failure'); END""")
    history.close()

    with pytest.raises(sqlite3.IntegrityError, match='fixture migration failure'):
        try:
            history.prepare()
        finally:
            history.close()
    with history.connect() as db:
        assert db.execute('PRAGMA user_version').fetchone() == (7,)
        assert not db.execute("SELECT name FROM sqlite_master WHERE name IN ('people','machine_assignees')").fetchall()
        assert [json.loads(row[0]) for row in db.execute(
            'SELECT settings FROM machine_settings ORDER BY machine')] == rows
        db.execute('DROP TRIGGER fail_migration')

    with TestClient(create_app(config), base_url='http://127.0.0.1') as client:
        snapshot = client.get('/api/snapshot').json()
        person, = snapshot['people']
        assert person['name'] == '张三'
        assert [item['assigned_users'] for item in snapshot['machines']] == [[person], [person], [], [], []]
        assert all(item['name'] == '旧别名' for item in snapshot['machines'])
        assert client.put('/api/machines/lab-0/assignees', json={'person_ids': []}).status_code == 200
        assert client.put(f"/api/people/{person['id']}", json={'name': '张工'}).status_code == 200

    renamed_config = config.model_copy(update={'machines': (
        hosts[0], hosts[1].model_copy(update={'id': 'new-public-id'}), *hosts[2:-1],
    )})
    with TestClient(create_app(renamed_config), base_url='http://127.0.0.1') as client:
        snapshot = client.get('/api/snapshot').json()
        assert snapshot['people'] == [dict(person, name='张工')]
        hosts_by_id = {item['id']: item for item in snapshot['machines']}
        assert hosts_by_id['lab-0']['assigned_users'] == []
        assert hosts_by_id['new-public-id']['assigned_users'] == snapshot['people']
    with history.connect(read=True) as db:
        assert db.execute('PRAGMA user_version').fetchone() == (SCHEMA_VERSION,)
        assert [json.loads(row[0]) for row in db.execute('SELECT settings FROM machine_settings')] == [old]*5


def test_people_directory_and_machine_assignees_persist_and_preserve_settings(tmp_path):
    first = machine(enabled=False)
    second = machine('lab-02', 'b'*32, enabled=False)
    config = Config(data_dir=tmp_path, machines=(first, second))
    directory = '/api/people'
    assign_first = '/api/machines/lab-01/assignees'
    assign_second = '/api/machines/lab-02/assignees'
    settings = '/api/machines/lab-01/settings'
    with TestClient(create_app(config), base_url='http://127.0.0.1') as client:
        assert client.post(directory, json={'name': '跨站'}, headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        assert client.put(assign_first, json={'person_ids': []}, headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
        assert client.post(directory, content='name=x', headers={'Content-Type': 'text/plain'}).status_code == 415
        created = client.post(directory, json={'name': '  Ada  '})
        assert created.status_code == 201
        ada = created.json()
        assert ada['name'] == 'Ada'
        bob = client.post(directory, json={'name': 'Bob'}).json()
        unused = client.post(directory, json={'name': 'ada'}).json()
        assert client.post(directory, json={'name': ' Ada '}).json()['detail'] == 'person_name_taken'
        assert client.put(f"{directory}/{ada['id']}", json={'name': 'Bob'}).json()['detail'] == 'person_name_taken'
        rejected = ('', '  ', 'a'*81, 'first\nsecond', '\nnext', 'next\r', 'next\t', '\x00next', 'next\x7f',
                    'first\u0085second', 'first\u009bsecond', 'first\u2028second', '\u2029next', 'next\u2029',
                    '\n', '\u0085', '\u2028', '\u2029', None, 12)
        for name in rejected:
            assert client.put(f"{directory}/{ada['id']}", json={'name': name}).status_code == 422, repr(name)

        def assigned(client, path, *ids):
            return client.put(path, json={'person_ids': ids})

        assert assigned(client, assign_first, bob['id'], ada['id']).json()['assigned_users'] == [ada, bob]
        assert assigned(client, assign_second, ada['id']).json()['assigned_users'] == [ada]
        assert assigned(client, assign_first, ada['id'], ada['id']).status_code == 422
        assert assigned(client, assign_first, True).status_code == 422
        assert assigned(client, assign_first, 1.0).status_code == 422
        assert assigned(client, assign_first, 999).json()['detail'] == 'person_missing'
        assert assigned(client, '/api/machines/missing/assignees').status_code == 404
        assert client.request('DELETE', f"{directory}/{ada['id']}", json={}).json()['detail'] == 'person_in_use'
        assert client.request('DELETE', f"{directory}/{unused['id']}", json={}).status_code == 204
        assert assigned(client, assign_first, unused['id']).status_code == 409
        another = client.post(directory, json={'name': 'New Person'}).json()
        assert another['id'] != unused['id']
        assert client.put(settings, json={'assigned_user': 'old API', 'enabled': False}).status_code == 422
        updated = client.put(settings, json={'alias': '保留设置', 'enabled': False, 'interval_seconds': 60}).json()
        assert updated['assigned_users'] == [ada, bob]

    with TestClient(create_app(config), base_url='http://127.0.0.1') as client:
        ada = client.put(f"{directory}/{ada['id']}", json={'name': 'Ada Renamed'}).json()
        snapshot = client.get('/api/snapshot').json()
        assert [node['assigned_users'] for node in snapshot['machines']] == [[ada, bob], [ada]]
        assert client.request('DELETE', '/api/machines/lab-02', json={'confirm': True}).status_code == 200
        snapshot = client.get('/api/snapshot').json()
        assert [node['assigned_users'] for node in snapshot['machines']] == [[ada, bob]]
        assert snapshot['people'] == [ada, bob, another]
        updated = assigned(client, assign_first, bob['id']).json()
        assert updated['assigned_users'] == [bob]
        assert (updated['name'], updated['interval_seconds'], updated['enabled']) == ('保留设置', 60, False)
        assert assigned(client, assign_first).json()['assigned_users'] == []
        assert client.request('DELETE', f"{directory}/{ada['id']}", json={}).status_code == 204
    assert History(tmp_path).people_and_assignees() == ({bob['id']: 'Bob', another['id']: 'New Person'}, {})


def test_assignee_and_person_save_failure_roll_back_without_changing_snapshot(tmp_path):
    config = Config(data_dir=tmp_path, machines=(machine(enabled=False),))
    url = '/api/machines/lab-01/assignees'
    history = History(tmp_path)
    with TestClient(create_app(config), base_url='http://127.0.0.1') as client:
        first = client.post('/api/people', json={'name': 'First'}).json()
        second = client.post('/api/people', json={'name': 'Second'}).json()
        assert client.put(url, json={'person_ids': [first['id']]}).status_code == 200
        with history.connect() as db:
            db.execute(f"""CREATE TRIGGER fail_assign BEFORE INSERT ON machine_assignees
                       WHEN NEW.person = {second['id']}
                       BEGIN SELECT RAISE(ABORT, 'fixture failure'); END""")
            db.execute("""CREATE TRIGGER fail_rename BEFORE UPDATE ON people
                       BEGIN SELECT RAISE(ABORT, 'fixture failure'); END""")
        assert client.put(url, json={'person_ids': [second['id']]}).status_code == 503
        assert client.put(f"/api/people/{first['id']}", json={'name': 'Changed'}).status_code == 503
        snapshot = client.get('/api/snapshot').json()
        assert snapshot['people'] == [first, second]
        assert snapshot['machines'][0]['assigned_users'] == [first]
        assert history.people_and_assignees() == (
            {first['id']: 'First', second['id']: 'Second'}, {ID: (first['id'],)},
        )


def test_register_and_reconfigure_with_pinned_host_and_persistent_settings(tmp_path):
    config = Config(data_dir=tmp_path, machines=(machine(),))
    commands = []

    async def transport(argv, payload, timeout):
        options = json.loads(payload)
        commands.append((argv[-2],options))
        assert '-oPreferredAuthentications=publickey' in argv
        assert '-oPasswordAuthentication=no' in argv
        assert '-oStrictHostKeyChecking=yes' in argv
        if argv[-2] == '2001:db8::114':
            assert '-oConnectTimeout=10' in argv and timeout == 17
        else:
            assert '-oConnectTimeout=5' in argv and timeout == 12
        if not options.get('expected_host_id'):
            assert argv[-1].endswith('--monitor-identity')
            if argv[-2] == 'offline.invalid':
                return 255,b'',b''
            return 0,json.dumps({'data':{'host_id':'b'*32,'boot_id':'boot'}}).encode(),b''
        return 0,json.dumps({'data':data(host=options['expected_host_id'])}).encode(),b''

    def app():
        return create_app(config, monitor=Monitor(config,Collector(config,transport)))

    with TestClient(app(),base_url='http://127.0.0.1') as client:
        assert client.post('/api/machines',json={'host':'-oProxyCommand=invalid'}).status_code == 422
        assert client.post('/api/machines',json={'host':'example.test','password':'invalid'}).status_code == 422
        assert client.post('/api/machines',json={'host':'example.test'},
                           headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
        assert client.post('/api/machines',json={'host':'offline.invalid'}).status_code == 502
        response = client.post('/api/machines',json={'host':'2001:db8::114','ssh_user':'observer',
            'alias':'新机器','enabled':False,'interval_seconds':60,'checks':['gpu'],
            'ssh_connect_timeout_seconds':10})
        assert response.status_code == 201
        created = response.json()
        assert created['name'] == '新机器' and created['status'] == 'disabled'
        assert created['assigned_users'] == []
        person = client.post('/api/people', json={'name': '值班员'}).json()
        assignees = f"/api/machines/{created['id']}/assignees"
        assert client.put(assignees, json={'person_ids': [person['id']]}).json()['assigned_users'] == [person]
        assert 'expected_host_id' not in created
        assert client.post('/api/machines',json={'host':'different-name'}).status_code == 409
        assert all('expected_host_id' not in options for host, options in commands if host == '2001:db8::114')
        url = f"/api/machines/{created['id']}/settings"
        assert client.put(url,json={'checks':['processes']}).status_code == 422
        assert client.put(url,json={'ssh_connect_timeout_seconds':0}).status_code == 422
        assert client.put(url,json={'host':'other.invalid'}).status_code == 422
        result = client.put(url,json={'alias':'新名称','enabled':True,
                                      'checks':['gpu'],'interval_seconds':90}).json()
        assert result['name'] == '新名称' and result['stale_ms'] == 107000
        assert (result['assigned_users'], result['ssh_connect_timeout_seconds']) == ([person], 10)
        for _ in range(100):
            if any(options.get('expected_host_id') == 'b'*32 for _, options in commands):
                break
            time.sleep(.01)
        assert any(options.get('expected_host_id') == 'b'*32 and options['checks'] == ['gpu']
                   for _, options in commands)
        assert client.get('/api/history',params={'machine':created['id'],'metric':'gpu'}).status_code == 200

    with TestClient(app(),base_url='http://127.0.0.1') as client:
        restored = next(node for node in client.get('/api/snapshot').json()['machines'] if node['id'] == created['id'])
        assert (restored['name'],restored['enabled'],restored['interval_seconds'],restored['checks']) == (
            '新名称',True,90,['gpu'])
        assert (restored['assigned_users'], restored['ssh_connect_timeout_seconds']) == ([person], 10)
        assert client.request('DELETE', f"/api/machines/{restored['id']}", json={'confirm': True}).status_code == 200
        reenrolled = client.post('/api/machines', json={'host': '2001:db8::114', 'ssh_user': 'observer',
                                 'enabled': False, 'ssh_connect_timeout_seconds': 10})
        assert reenrolled.status_code == 201
        assert reenrolled.json()['assigned_users'] == []
        assert client.get('/api/snapshot').json()['people'] == [person]


def test_duplicate_machine_id_with_verified_distinct_keys_keeps_histories_separate(tmp_path):
    first = machine('node-first',enabled=False)
    config = Config(data_dir=tmp_path,machines=(first,))
    original_at = int(time.time()*1000)-10000
    history = History(tmp_path)
    history.prepare()
    history.append(ID,'original',{'observed_at':original_at,'received_at':original_at,'source':'ssh',
                                 'boot':'boot-1','status':'normal','metrics':{'cpu_percent':23}})
    history.set_alias(ID,'第一台')
    with history.connect() as db:
        db.execute('DROP TABLE machine_ssh_pins')
        db.execute('DROP TABLE machine_order')
        db.execute('DROP TABLE removed_config_machines')
        db.execute('DROP TABLE pending_machine_removals')
        set_legacy_registry_version(db, 4)
    history.close()
    keys = {'node-first':'A'*43, 'node-second':'B'*43, 'other-alias-for-first':'A'*43}

    async def transport(argv,payload,timeout):
        host = argv[-2]
        options = json.loads(payload)
        if '-v' in argv:
            assert '-oControlPath=none' in argv
            algorithm, fingerprint = 'ssh-ed25519', keys[host]
            if host == 'other-alias-for-first' and '-oHostKeyAlgorithms=ssh-ed25519' not in argv:
                algorithm, fingerprint = 'ssh-rsa', 'D'*43
            stderr = f'debug1: Server host key: {algorithm} SHA256:{fingerprint}\nAuthenticated to {host}\n'.encode()
        else:
            stderr = b''
        sample = data(host=ID) if options.get('expected_host_id') else {'host_id':ID,'boot_id':'boot'}
        return 0,json.dumps({'data':sample}).encode(),stderr

    def app():
        return create_app(config,monitor=Monitor(config,Collector(config,transport)))

    with TestClient(app(),base_url='http://127.0.0.1') as client:
        assert client.post('/api/machines',json={'host':'other-alias-for-first'}).status_code == 409
        response = client.post('/api/machines',json={'host':'node-second','alias':'第二台'})
        assert response.status_code == 201
        second = response.json()['id']
        assert 'history_id' not in response.text and 'ssh_host_key' not in response.text
        for _ in range(100):
            hosts = client.get('/api/snapshot').json()['machines']
            if hosts[-1].get('metrics'):
                break
            time.sleep(.01)
        assert hosts[0]['name'] == '第一台'
        assert hosts[-1]['name'] == '第二台' and hosts[-1]['metrics']['gpus']
        keys['node-second'] = 'C'*43

    reopened = app()
    with TestClient(reopened,base_url='http://127.0.0.1') as client:
        for _ in range(100):
            hosts = client.get('/api/snapshot').json()['machines']
            if hosts[-1]['status'] == 'unknown':
                break
            time.sleep(.01)
        assert 'SSH 主机密钥指纹' in hosts[-1]['reason']
        for id, expected in ((first.id,True), (second,False)):
            points = client.get('/api/history',params={'machine':id,'metric':'cpu','hours':1}).json()['points']
            assert any(point['time']==original_at and point['values']==[23] for point in points) is expected


def test_machine_order_survives_restart_and_appends_new_machines(tmp_path):
    first = machine('first',enabled=False)
    second = machine('second','b'*32,enabled=False)
    config = Config(data_dir=tmp_path,machines=(first,second))
    history = History(tmp_path)
    history.prepare()
    with history.connect() as db:
        db.execute('DROP TABLE machine_order')
        db.execute('DROP TABLE removed_config_machines')
        db.execute('DROP TABLE pending_machine_removals')
        set_legacy_registry_version(db, 5)
    history.close()

    async def identify(host,user,timeout):
        return HostIdentity(('d' if host == 'third' else 'c')*32,None)

    def app():
        collector = Collector(config)
        collector.identify = identify
        return create_app(config,monitor=Monitor(config,collector))

    def ids(client):
        return [node['id'] for node in client.get('/api/snapshot').json()['machines']]

    url = '/api/machines/order'
    order = ['second','first']
    with TestClient(app(),base_url='http://127.0.0.1') as client:
        assert ids(client) == ['first','second']
        assert client.put(url,json={'machines':order},headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
        assert client.put(url,json={'machines':['first','first']}).status_code == 422
        assert client.put(url,json={'machines':['first','missing']}).status_code == 409
        assert client.put(url,json={'machines':order}).json() == {'machines':order}
        assert ids(client) == order
        for host in ('third','fourth'):
            result = client.post('/api/machines',json={'host':host,'enabled':False})
            assert result.status_code == 201
            order.append(result.json()['id'])
        assert ids(client) == order

    with TestClient(app(),base_url='http://127.0.0.1') as client:
        assert ids(client) == order


def test_remove_scrubs_all_history_and_keeps_other_archived_records(tmp_path):
    removed = machine('remove-me',enabled=False)
    kept = machine('keep-me','b'*32,enabled=False)
    config = Config(data_dir=tmp_path,machines=(removed,kept))
    now = int(time.time()*1000)
    history = History(tmp_path)
    history.prepare()
    identities = (removed.history_key,kept.history_key)

    def sample(key, at):
        history.append(key,'fixture',{'observed_at':at,'received_at':at,'source':'ssh','status':'normal','boot':'boot',
                                     'metrics':{'cpu_percent':33,'gpu_generation':GPU,'gpus':data(gpu=GPU)['gpus']}})

    for key in identities:
        for age in (8*DAY_MS-3600000,2*DAY_MS,10000):
            sample(key,now-age)
    sample(removed.history_key,now-9*DAY_MS)
    history.pack(now-DAY_MS)
    archives = []
    for slot in (now-DAY_MS,now):
        assert history.begin_archive(slot) == slot
        export = history.export(slot-WARM_MS)
        history.finish_archive(slot,slot-WARM_MS,export)
        archives.append(history.cold_directory/export.filename)
    with gzip.open(archives[1],'rb') as shared:
        original = [line for line in shared if json.loads(line).get('machine') != removed.history_key]
    orphan = archives[1].with_name('before-orphan.jsonl.gz')
    orphan.write_bytes(archives[1].read_bytes())
    (history.cold_directory/'.archive-stale').write_bytes(archives[1].read_bytes())
    history.save_machine(removed.history_key,None,MachineSettings(enabled=False).model_dump_json(),'旧别名',
                         {removed.history_key:'fixture-pin'},{removed.history_key:0,kept.history_key:1})
    with history.connect() as db:
        db.execute('DROP TABLE removed_config_machines')
        db.execute('DROP TABLE pending_machine_removals')
        set_legacy_registry_version(db, 6)
    history.close()

    with TestClient(create_app(config),base_url='http://127.0.0.1') as client:
        url='/api/machines/remove-me'
        assert client.request('DELETE',url,json={'confirm':False}).status_code == 422
        assert client.request('DELETE',url,json={'confirm':True},headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
        assert client.request('DELETE',url,json={'confirm':True}).json() == {'id':'remove-me','cleanup_pending':False}
        assert client.get('/api/history',params={'machine':'remove-me'}).status_code == 404
        assert client.put(url+'/alias',json={'alias':'不能写回'}).status_code == 404
        assert client.put(url+'/settings',json={'enabled':False}).status_code == 404
        assert [node['id'] for node in client.get('/api/snapshot').json()['machines']] == ['keep-me']
        assert client.get('/api/history',params={'machine':'keep-me','metric':'cpu','hours':168}).json()['points']

    assert not archives[0].exists()
    for target in (archives[1],orphan):
        with gzip.open(target,'rb') as shared:
            assert list(shared) == original
    assert not (history.cold_directory/'.archive-stale').exists()
    with history.connect(read=True) as db:
        for table in ('host_ticks','gpu_ticks','machine_settings','machine_ssh_pins','machine_aliases','machine_order'):
            assert db.execute(f'SELECT COUNT(*) FROM {table} WHERE machine=?',(removed.history_key,)).fetchone() == (0,)
        assert db.execute('SELECT identity FROM history_machines').fetchall() == [(kept.history_key,)]
        assert db.execute('SELECT COUNT(*) FROM warm_host_ticks').fetchone() == (1,)
        assert db.execute('SELECT COUNT(*) FROM warm_gpu_ticks').fetchone() == (1,)
        assert db.execute('SELECT host_count,gpu_count,file_bytes FROM cold_archives').fetchall() == [
            (1,1,archives[1].stat().st_size),
        ]

    with TestClient(create_app(config),base_url='http://127.0.0.1') as client:
        assert [node['id'] for node in client.get('/api/snapshot').json()['machines']] == ['keep-me']


async def test_remove_stops_sampler_and_resumes_failed_archive_cleanup_after_restart(tmp_path,monkeypatch):
    host = machine()
    config = Config(data_dir=tmp_path,machines=(host,))
    clock = ManualTime()
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def collect(node):
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def identify(host,user,timeout):
        return HostIdentity(ID,None)

    collect.identify = identify
    service = Monitor(config,collect,clock.clock,clock.sleep,lambda:clock.seconds)

    def failed(*args):
        raise OSError('fixture')

    monkeypatch.setattr(service.history,'purge_machine_archives',failed)
    await service.start()
    try:
        await eventual(started.is_set)
        assert (await service.remove(host.id))['cleanup_pending']
        assert stopped.is_set()
        assert service.snapshot()['machines'] == []
        with pytest.raises(CollectionError,match='正在清理'):
            await service.register(MachineRegistration(host='lab-02',enabled=False))
    finally:
        await service.close()

    recovered = Monitor(config,collect,clock.clock,clock.sleep,lambda:clock.seconds)
    await recovered.start()
    try:
        assert recovered.snapshot()['removal_pending'] == 1
        assert recovered.snapshot()['machines'] == []
        await asyncio.sleep(0)
        clock.advance(31)
        await eventual(lambda: recovered.snapshot()['removal_pending'] == 0)
        added = await recovered.register(MachineRegistration(host='lab-02',enabled=False))
        assert (await recovered.series(ID,None,'cpu',168))['points'] == []
        assert recovered.snapshot()['machines'][0]['id'] == added['id']
    finally:
        await recovered.close()


async def test_settings_replace_sampler_without_overlap_and_disabled_hosts_stay_idle(tmp_path):
    host = machine()
    config = Config(data_dir=tmp_path, machines=(host,))
    clock = ManualTime()
    calls = []
    stopped = asyncio.Event()

    async def collect(node):
        calls.append(node)
        if len(calls) == 1:
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        assert stopped.is_set()
        return data()

    service = Monitor(config,collect,clock.clock,clock.sleep,lambda:clock.seconds)
    await service.start()
    try:
        await eventual(lambda:len(calls) == 1)
        settings = MachineSettings(interval_seconds=60, checks=['gpu'])
        await service.configure(host.id,settings)
        await eventual(lambda:len(calls) == 2 and host.id in service.latest)
        clock.advance(50)
        assert service.snapshot()['machines'][0]['status'] == 'normal'
        assert len(calls) == 2
        clock.advance(10)
        await eventual(lambda:len(calls) == 3)
        await service.configure(host.id,settings.model_copy(update={'enabled':False}))
        clock.advance(120)
        await asyncio.sleep(0)
        assert len(calls) == 3
        assert service.snapshot()['machines'][0]['status'] == 'disabled'
    finally:
        await service.close()


async def test_gpu_tolerance_settings_apply_to_later_samples_and_persist(tmp_path, monkeypatch):
    field = 'idle_memory_tolerance_mib'
    settings = {'checks':['gpu', 'processes'], 'interval_seconds':10}
    host = machine(checks=tuple(settings['checks']))
    file_override = machine('lab-02', 'b'*32, enabled=False, idle_memory_tolerance_mib=0)
    legacy_registration = machine('lab-03', 'c'*32, idle_memory_tolerance_mib=0)
    config = Config(data_dir=tmp_path, machines=(host, file_override))
    history = History(tmp_path)
    history.prepare()
    try:
        for node, registration in ((file_override, None), (legacy_registration, legacy_registration.model_dump_json())):
            history.save_machine(node.history_key, registration, json.dumps({'enabled':False}), None, {})
    finally:
        history.close()

    (tmp_path/'uptime').write_text('1000.00 0')
    used = '256 MiB'
    monkeypatch.setattr(host_probe.subprocess, 'run',
                        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=idle_gpu_xml(used)))
    thresholds = []

    async def transport(argv, payload, timeout):
        options = json.loads(payload)
        assert options['checks'] == settings['checks']
        thresholds.append(options[field])
        warnings = []
        measured = host_probe.monitor_gpus(options, tmp_path, warnings)
        return 0, json.dumps({'data':dict(data(), **measured, warnings=warnings)}).encode(), b''

    clock = ManualTime()
    service = Monitor(config, Collector(config, transport), clock.clock, clock.sleep, lambda: clock.seconds)
    url = f'/api/machines/{host.id}/settings'

    async def read_nodes(client):
        response = await client.get('/api/snapshot')
        assert response.status_code == 200
        return {node['id']:node for node in response.json()['machines']}

    async def expect_sample(client, at, tolerance, state):
        await eventual(lambda: service.latest.get(host.id, {}).get('observed_at') == at)
        node = (await read_nodes(client))[host.id]
        assert thresholds[-1] == node[field] == tolerance
        assert node['metrics']['gpus'][0]['state'] == state
        assert '部分 GPU 占用状态无法核实' not in node['warnings']

    app = create_app(config, monitor=service)
    async with app.router.lifespan_context(app), AsyncClient(
        transport=ASGITransport(app=app), base_url='http://127.0.0.1'
    ) as client:
        await expect_sample(client, clock.clock(), 256, 'free')
        sampler = service.samplers[host.id]
        nodes = await read_nodes(client)
        assert nodes[file_override.id][field] == 0
        assert nodes[legacy_registration.id][field] == 256
        for node, expected in ((file_override, 0), (legacy_registration, 256)):
            response = await client.put(f'/api/machines/{node.id}/settings', json={'enabled':False})
            assert response.status_code == 200 and response.json()[field] == expected

        tolerance = 300.50000000000006
        response = await client.put(url, json=dict(settings, **{field:tolerance}))
        assert response.status_code == 200 and response.json()[field] == tolerance
        assert (await read_nodes(client))[host.id][field] == tolerance
        assert thresholds == [256] and service.samplers[host.id] is sampler
        assert (await client.put(url, json=settings)).json()[field] == tolerance
        stored = {identity:json.loads(values) for identity, _, values in service.history.machine_settings()}
        assert stored[host.history_key][field] == tolerance
        assert field not in stored[file_override.history_key]
        assert field not in stored[legacy_registration.history_key]
        used = f'{tolerance} MiB'
        clock.advance(10)
        await expect_sample(client, clock.clock(), tolerance, 'free')
        used = '300.75 MiB'
        clock.advance(10)
        await expect_sample(client, clock.clock(), tolerance, 'unknown')

        assert (await client.put(url, json=dict(settings, **{field:0}))).json()[field] == 0
        assert (await client.put(url, json=settings)).json()[field] == 0
        used = '0 MiB'
        clock.advance(10)
        await expect_sample(client, clock.clock(), 0, 'free')
        saved_rows = service.history.machine_settings()
        for raw_value in ('-1', '1e309', 'NaN', 'Infinity', '-Infinity', 'true', '"12"', '{"value": NaN}'):
            body = json.dumps(dict(settings, **{field:'value'})).replace('"value"', raw_value)
            response = await client.put(url, content=body, headers={'Content-Type':'application/json'})
            assert response.status_code == 422
            assert response.json()['detail'][0]['loc'] == ['body', field]

        # Fail after the transaction has already attempted to update the settings row.
        with service.history.connect() as db:
            db.execute("""CREATE TRIGGER reject_alias BEFORE INSERT ON machine_aliases
                          BEGIN SELECT RAISE(ABORT, 'synthetic settings failure'); END""")
        response = await client.put(url, json=dict(settings, alias='will fail', **{field:800}))
        assert response.status_code == 503
        assert service.history.machine_settings() == saved_rows
        assert service.samplers[host.id] is sampler
        used = '1 MiB'
        clock.advance(10)
        await expect_sample(client, clock.clock(), 0, 'unknown')

    service = Monitor(config, Collector(config, transport), clock.clock, clock.sleep, lambda: clock.seconds)
    app = create_app(config, monitor=service)
    async with app.router.lifespan_context(app), AsyncClient(
        transport=ASGITransport(app=app), base_url='http://127.0.0.1'
    ) as client:
        await expect_sample(client, clock.clock(), 0, 'unknown')
        nodes = await read_nodes(client)
        assert nodes[file_override.id][field] == 0
        assert nodes[legacy_registration.id][field] == 256


async def test_layered_tolerance_uses_membership_at_start_of_each_sample(tmp_path, monkeypatch):
    field = 'idle_memory_tolerance_mib'
    host = machine(checks=('gpu', 'processes'))
    config = Config(data_dir=tmp_path, machines=(host,))
    clock = ManualTime()
    (tmp_path/'uptime').write_text('1000.00 0')
    monkeypatch.setattr(host_probe.subprocess, 'run',
                        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=idle_gpu_xml('300 MiB')))
    started, finish = asyncio.Event(), asyncio.Event()
    captured = []

    async def transport(_argv, payload, _timeout):
        options = json.loads(payload)
        captured.append(options[field])
        if len(captured) == 2:
            started.set()
            await finish.wait()
        warnings = []
        measured = host_probe.monitor_gpus(options, tmp_path, warnings)
        return 0, json.dumps({'data':dict(data(), **measured, warnings=warnings)}).encode(), b''

    service = Monitor(config, Collector(config, transport), clock.clock, clock.sleep, lambda: clock.seconds)
    app = create_app(config, monitor=service)
    async with app.router.lifespan_context(app), AsyncClient(
        transport=ASGITransport(app=app), base_url='http://127.0.0.1'
    ) as client:
        async def mutation(method, path, **values):
            response = await client.request(method, path, json=values)
            response.raise_for_status()
            return response.json()

        async def sample(value, source, state):
            await eventual(lambda: service.latest.get(host.id, {}).get('observed_at') == clock.clock())
            snapshot = (await client.get('/api/snapshot')).json()
            node = snapshot['machines'][0]
            seen = node['sample_idle_memory_configuration']
            assert (seen['effective'], seen['source']['scope'], captured[-1]) == (value, source, value)
            assert node['metrics']['gpus'][0]['state'] == state
            assert snapshot['alerts']['events'] == []
            return node

        await sample(256, 'default', 'unknown')
        await mutation('PUT', '/api/configuration', **{field:400})
        room = (await mutation('POST', '/api/rooms', name='East', **{field:280}))['id']
        west = (await mutation('POST', '/api/rooms', name='West', **{field:410}))['id']
        await mutation('PUT', f'/api/resources/{host.id}/room', room_id=room)
        main = (await mutation('POST', '/api/clusters', name='Primary', members=[host.id], **{field:320}))['id']
        await mutation('POST', '/api/clusters', name='Other', members=[host.id], **{field:220})
        clock.advance(10)
        await asyncio.wait_for(started.wait(), 3)
        try:
            settings = dict(checks=['gpu', 'processes'], interval_seconds=10)
            edited = await mutation('PUT', f'/api/machines/{host.id}/settings', **settings,
                                    room_id=west, configuration_cluster_id=main)
            assert edited['idle_memory_configuration']['source'] == {'scope':'cluster', 'ids':[main]}
            assert edited[field] == 320
        finally:
            finish.set()
        in_flight = await sample(280, 'room', 'unknown')
        assert in_flight[field] == 320 and in_flight['room_id'] == west
        assert in_flight['sample_idle_memory_configuration']['cluster_conflict']
        sampler = service.samplers[host.id]
        clock.advance(10)
        latest = await sample(320, 'cluster', 'free')
        assert latest['sample_idle_memory_configuration'] == latest['idle_memory_configuration']
        await mutation('POST', '/api/clusters', name='Third', members=[host.id], **{field:440})
        await mutation('PUT', f'/api/clusters/{main}', name='Primary', members=[])
        clock.advance(10)
        latest = await sample(410, 'room', 'free')
        assert latest['idle_memory_configuration']['invalid_cluster_selection']
        assert latest['idle_memory_configuration']['cluster_conflict']
        await mutation('PUT', f'/api/rooms/{west}', name='West', **{field:None})
        clock.advance(10)
        await sample(400, 'global', 'free')
        await mutation('PUT', '/api/configuration', **{field:None})
        clock.advance(10)
        await sample(256, 'default', 'unknown')
        assert service.samplers[host.id] is sampler
