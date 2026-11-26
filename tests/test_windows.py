import asyncio
from base64 import b64decode, b64encode
import json
import time

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from wattline import windows
from wattline.app import create_app
from wattline.collector import CollectionError, Collector
from wattline.config import Config, Machine
from wattline.history import History
from wattline.service import Monitor


HOST = '12'*16
GPU = 'GPU-12345678-abcd-1234-abcd-123456789012'
SECOND_GPU = 'GPU-abcd5678-abcd-1234-abcd-123456789012'
PIN = 'SHA256:'+'A'*43


def nvidia(*devices, count=None):
    count = len(devices) if count is None else count
    xml = (f'<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE nvidia_smi_log SYSTEM "nvsmi_device_v12.dtd">'
           f'<nvidia_smi_log><attached_gpus>{count}</attached_gpus><driver_version>fixture</driver_version>'
           + ''.join(devices) + '</nvidia_smi_log>')
    return {'xml':b64encode(xml.encode()).decode()}


def card(uuid=GPU, utilization=27, rows=(), default_limit='N/A'):
    processes = ''.join(f'<process_info><pid>{pid}</pid><type>C+G</type><used_memory>{memory}</used_memory>'
                        r'<process_name>C:\Synthetic\example.exe</process_name></process_info>' for pid, memory in rows)
    return (f'<gpu><uuid>{uuid}</uuid><product_name>NVIDIA Fixture</product_name>'
            f'<utilization><gpu_util>{utilization} %</gpu_util></utilization>'
            '<gpu_power_readings><instant_power_draw>42 W</instant_power_draw>'
            f'<default_power_limit>{default_limit}</default_power_limit><enforced_power_limit>200 W</enforced_power_limit>'
            '<max_power_limit>450 W</max_power_limit></gpu_power_readings>'
            '<module_power_readings><default_power_limit>900 W</default_power_limit></module_power_readings>'
            '<fb_memory_usage><used>0 MiB</used><total>8192 MiB</total></fb_memory_usage>'
            f'<processes>{processes}</processes></gpu>')


def wire_sample(**changes):
    data = {
        'host_id':HOST, 'boot_id':'boot-1', 'source_observed_at':100, 'cpu_count':4,
        'cpu_samples':[{'name':f'{group},{index}', 'percent':percent}
                       for group, index, percent in [(0,0,5),(0,1,25),(1,0,35),(1,1,55)]],
        'memory':{'total_bytes':2000,'available_bytes':1500},
        'root_disk':{'volume':'D:','total_bytes':10000,'available_bytes':5000},
        'uptime_seconds':300, 'nvidia':nvidia(card()),
    }
    return dict(data, **changes)


def packet(data, pin=PIN):
    stderr = (f'debug1: Server host key: ssh-ed25519 {pin}\r\n'
              'Authenticated to synthetic.invalid using "publickey".\r\n').encode() if pin else b''
    return 0, json.dumps({'data':data}, ensure_ascii=False).encode(), stderr


def windows_options(argv, payload):
    assert all(option in argv for option in (
        '-T', '-oStrictHostKeyChecking=yes', '-oPreferredAuthentications=publickey', '-oUpdateHostKeys=no',
        '-oHostKeyAlgorithms=ssh-ed25519', '-oControlPath=none',
    ))
    assert argv[-1] == ' '.join(windows.COMMAND)
    assert len(argv[-1]) < 1024
    source, settings = payload.splitlines()
    assert b64decode(source).startswith(b"$ErrorActionPreference = 'Stop'")
    return json.loads(settings)


def test_windows_registration_api_and_pins(tmp_path):
    config = Config(data_dir=tmp_path)
    assert Machine(id='legacy', mode='local', expected_host_id=HOST).target_os == 'linux'
    with pytest.raises(ValidationError):
        Machine(id='bad', mode='local', target_os='windows', expected_host_id=HOST)

    keys = {'synthetic.invalid':PIN, 'alias.invalid':PIN, 'clone.invalid':'SHA256:'+'B'*43, 'no-key.invalid':None}

    async def transport(argv, payload, timeout):
        assert windows_options(argv, payload)['identity_only']
        return packet(wire_sample(), keys[argv[-2]])

    def app():
        return create_app(config, monitor=Monitor(config, Collector(config, transport)))

    settings = {'target_os':'windows','enabled':False}
    with TestClient(app(), base_url='http://127.0.0.1') as client:
        assert client.post('/api/machines', json=dict(settings, host='bad.invalid', target_os='other')).status_code == 422
        assert client.post('/api/machines', json=dict(settings, host='no-key.invalid')).status_code == 422
        response = client.post('/api/machines', json=dict(settings, host='synthetic.invalid'))
        assert response.status_code == 201
        machine_id = response.json()['id']
        assert response.json()['target_os'] == 'windows'
        assert client.post('/api/machines', json=dict(settings, host='alias.invalid')).status_code == 409
        clone = client.post('/api/machines', json=dict(settings, host='clone.invalid'))
        assert clone.status_code == 201
        assert client.put(f'/api/machines/{machine_id}/settings', json={'enabled':False,'alias':'Windows'}).status_code == 200

    reopened = app()
    with TestClient(reopened, base_url='http://127.0.0.1') as client:
        view = client.get('/api/snapshot').json()['machines']
        assert [(node['target_os'], node['status']) for node in view] == [('windows','disabled')]*2
        assert view[0]['name'] == 'Windows'
    pins = History(tmp_path).ssh_pins()
    assert pins[HOST] == PIN and set(pins.values()) == {PIN, keys['clone.invalid']}


def test_windows_multigroup_counter_coverage():
    source = wire_sample()
    options = {'checks':['cpu','memory','system']}
    metrics = windows.metrics(source, options)
    assert (metrics['cpu_count'], metrics['cpu_percent'], metrics['load_average']) == (4,30,[])
    assert metrics['root_disk']['volume'] == 'D:'
    assert metrics['memory']['available_bytes'] == 1500
    for samples in (source['cpu_samples'][:2], [source['cpu_samples'][0]]*4,
                    [dict(row, percent=None) for row in source['cpu_samples']]):
        metrics = windows.metrics(dict(source, cpu_samples=samples), options)
        assert metrics['cpu_percent'] is None and metrics['warnings']


def test_windows_gpu_partial_measurements_and_empty_inventory():
    source = wire_sample(nvidia=nvidia(card(rows=[(pid, 'N/A') for pid in range(10,17)], default_limit='250 W'),
                                      card(SECOND_GPU)),
                         process_evidence={'10':{'started_at':95_000,'user':'测试域\\巡检','name':'训练.exe'},
                                           '11':{'started_at':101_000,'user':'fixture-reused'}},
                         gpu_observed_at=100_000)
    options = {'checks':['gpu','processes']}
    metrics = windows.metrics(source, options)
    full, unseen = metrics['gpus']
    assert metrics['gpu_inventory_complete'] is True
    assert full['state'] == 'occupied' and len(full['processes']) == 7
    assert full['process_visibility'] == 'partial'
    assert (full['power_w'], full['power_kind']) == (42, 'instantaneous')
    assert (full['power_limit_w'], full['default_power_limit_w']) == (200, 250)
    assert unseen['default_power_limit_w'] is None
    first, reused = full['processes'][:2]
    assert first['user'] == '测试域\\巡检' and first['elapsed_seconds'] == 5
    assert first['used_memory_mib'] is None and 'uid' not in first and 'workload' not in first
    assert 'user' not in reused and 'started_at' not in reused
    assert reused['name'] == 'example.exe'
    assert unseen['state'] == 'unknown' and unseen['process_visibility'] == 'partial'
    disabled = windows.metrics(source, {'checks':['gpu']})['gpus'][0]
    assert disabled['processes'] == [] and disabled['state'] == 'unknown'
    for query in (nvidia(), {'empty':True}):
        empty = windows.metrics(wire_sample(nvidia=query), options)
        assert empty['gpu_inventory_complete'] and empty['gpu_inventory_empty'] and empty['gpus'] == []
        expected = windows.metrics(wire_sample(nvidia=query), dict(options, expected_gpu_count=1))
        assert not expected['gpu_inventory_complete'] and expected['warnings']
    for query in (None, {'xml':'!'}, nvidia(card(), card(), count=2), nvidia(count=1)):
        missing = windows.metrics(wire_sample(nvidia=query), options)
        assert not missing['gpu_inventory_complete'] and missing['warnings']


@pytest.mark.asyncio
async def test_windows_sampling_history_reboot_identity_and_inventory(tmp_path):
    now = int(time.time()*1000)-60_000
    sample, key = wire_sample(), PIN
    machine = Machine(id='windows', target_os='windows', mode='ssh', ssh_alias='synthetic.invalid',
                      expected_host_id=HOST)
    config = Config(data_dir=tmp_path, machines=(machine,))

    async def transport(argv, payload, timeout):
        options = windows_options(argv, payload)
        assert options['expected_host_id'] == HOST and timeout == config.timeout_seconds
        return packet(sample, key)

    monitor = Monitor(config, Collector(config, transport), clock=lambda:now)
    monitor.history.prepare()
    monitor.ssh_pins[HOST] = PIN
    try:
        async def observe():
            nonlocal now
            now += 5000
            snapshot = await monitor.observe(machine)
            monitor.history.append(HOST, 'windows-fixture', snapshot)
            return snapshot

        first = await observe()
        assert first['metrics']['cpu_percent'] == 30
        sample = wire_sample(boot_id='boot-2', uptime_seconds=3, nvidia=nvidia(card(SECOND_GPU), card(utilization=83)))
        second = await observe()
        assert second['boot'] != first['boot']
        assert second['metrics']['cpu_percent'] == 30 and second['metrics']['uptime_seconds'] == 3
        assert second['metrics']['gpus'][1]['uuid'] == GPU
        history = await monitor.series(HOST, GPU, 'gpu', 1)
        readings = [p for p in history['points'] if p['values'][0] is not None]
        assert [p['values'][0] for p in readings] == [27,83]
        assert readings[1]['breaks'] == [True]

        key = 'SHA256:'+'B'*43
        rejected = await observe()
        assert rejected['metrics'] is None and 'SSH 主机密钥指纹' in rejected['reason']
        key = PIN
        sample = wire_sample(host_id='34'*16)
        assert (await observe())['metrics'] is None

        sample = wire_sample(nvidia=nvidia())
        empty = await observe()
        assert empty['metrics']['gpu_inventory_complete'] and monitor.inventory[machine.id] == []
        assert monitor.history.inventory(HOST, now, True)[1:] == ([], 'host', True)
        monitor.history.pack(now+1)
        assert monitor.history.inventory(HOST, now, True)[1:] == ([], 'host', True)
        sample = wire_sample(nvidia=None)
        partial = await observe()
        assert partial['status'] == 'warning' and not partial['metrics']['gpu_inventory_complete']
        assert monitor.history.inventory(HOST, now, True)[1:] == ([], 'host', False)
        gpu_only = machine.model_copy(update={'checks':('gpu',)})
        result = await monitor.observe(gpu_only)
        assert result['status'] == 'warning' and result['metrics']['gpus'] == []
    finally:
        monitor.history.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('transport_failure', ['timeout','ssh','unreadable'])
async def test_windows_transport_failures(tmp_path, transport_failure):
    async def run(argv, payload, timeout):
        windows_options(argv, payload)
        if transport_failure == 'timeout':
            raise asyncio.TimeoutError
        return (255 if transport_failure == 'ssh' else 1), b'', b'fixture'

    collector = Collector(Config(data_dir=tmp_path), run)
    with pytest.raises(CollectionError) as error:
        await collector.identify('synthetic.invalid', None, 5, target_os='windows')
    assert error.value.status == ('unknown' if transport_failure == 'unreadable' else 'offline')
