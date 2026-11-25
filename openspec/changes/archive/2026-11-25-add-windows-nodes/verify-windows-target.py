"""Read-only Windows verification. The SSH destination is supplied outside Git."""
import base64
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient

from wattline.app import create_app
from wattline.collector import Collector
from wattline.config import Config
from wattline.service import Monitor
from wattline.transport import command


def summarize(data):
    cpus = data.get('cpu_samples') or []
    xml = data.get('nvidia') or {}
    root = ET.fromstring(base64.b64decode(xml['xml'])) if xml.get('xml') else None
    print(json.dumps({
        'processor_groups':len({row['name'].split(',')[0] for row in cpus}),
        'logical_processors':data.get('cpu_count'), 'unique_cpu_rows':len({row['name'] for row in cpus}),
        'system_volume_reported':bool((data.get('root_disk') or {}).get('volume')),
        'driver_models':[gpu.findtext('driver_model/current_dm') for gpu in root.findall('gpu')] if root is not None else [],
    }))


with TemporaryDirectory() as directory:
    cfg = Config(data_dir=Path(directory))
    wire = []

    async def capture(argv, payload, timeout):
        code, output, error = await command(argv, payload, timeout)
        if code == 0 and not json.loads(payload.splitlines()[1]).get('identity_only'):
            wire.append(json.loads(output)['data'])
        if code:
            print('SSH status', code, 'No route to host' if b'No route to host' in error else 'unverified response')
        return code, output, error

    service = Monitor(cfg, Collector(cfg, capture))
    with TestClient(create_app(cfg, monitor=service), base_url='http://127.0.0.1') as client:
        response = client.post('/api/machines', json={'host':sys.argv[1],'target_os':'windows','interval_seconds':5})
        assert response.status_code == 201, response.status_code
        machine = response.json()['id']
        print('register', response.status_code, 'OS', response.json()['target_os'])
        for _ in range(120):
            with service.history.connect(read=True) as db:
                count = db.execute('SELECT count(*) FROM host_ticks WHERE boot IS NOT NULL').fetchone()[0]
                gpu_count = db.execute('SELECT count(*) FROM gpu_ticks').fetchone()[0]
            if count >= 2 and gpu_count >= 2:
                break
            time.sleep(0.25)
        assert count >= 2 and gpu_count >= 2, (count, gpu_count)
        summarize(wire[0])
        snap = client.get('/api/snapshot').json()['machines'][0]
        metrics = snap['metrics']
        assert metrics and metrics['cpu_percent'] is not None and metrics['memory'] and metrics['root_disk']
        assert metrics['load_average'] == [] and metrics['uptime_seconds'] >= 0
        print('persisted host/GPU samples', count, gpu_count, 'snapshot status', snap['status'])
        for gpu in metrics['gpus']:
            print('GPU measurements', [field for field in (
                'utilization_percent','memory_total_mib','memory_used_mib','temperature_c','power_w','power_limit_w'
            ) if gpu.get(field) is not None])
            print('GPU state', gpu['state'], 'visibility', gpu['process_visibility'], 'records', len(gpu['processes']),
                  'known VRAM', sum(p.get('used_memory_mib') is not None for p in gpu['processes']),
                  'known account', sum(bool(p.get('user')) for p in gpu['processes']),
                  'verified timing', sum('started_at' in p for p in gpu['processes']))
            for metric, uuid in (('cpu',None),('memory',None),('gpu',gpu['uuid']),('vram',gpu['uuid'])):
                params = {'machine':machine,'metric':metric,'hours':1}
                if uuid:
                    params['gpu'] = uuid
                result = client.get('/api/history', params=params)
                valid = sum(point['values'][0] is not None for point in result.json().get('points', []))
                assert result.status_code == 200 and valid > 0, (metric, result.status_code, valid)
                print('history', metric, result.status_code, 'valid bins', valid)
        assert metrics['gpu_inventory_complete'] and metrics['gpus']
