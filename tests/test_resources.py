import time

from fastapi.testclient import TestClient

from wattline.app import create_app
from wattline.config import Config, Machine
from wattline.history import History
from wattline.service import Monitor


def client_for(config, monitor=None):
    return TestClient(create_app(config, monitor=monitor), base_url='http://127.0.0.1')


def wait_for(fn):
    deadline = time.monotonic()+3
    while time.monotonic() < deadline:
        if result := fn():
            return result
        time.sleep(0.01)
    raise AssertionError('Synthetic observation did not arrive')


def test_resource_types_and_legacy_assignees_survive_upgrade(tmp_path):
    cpu = Machine(id='cpu', expected_host_id='a'*32, mode='ssh', ssh_alias='cpu', enabled=False, require_gpu=False)
    unknown = Machine(id='unknown', expected_host_id='b'*32, mode='ssh', ssh_alias='unknown', enabled=False)
    config = Config(data_dir=tmp_path, machines=(cpu, unknown))
    history = History(tmp_path)
    history.prepare()
    first = history.save_person(None, 'First')
    second = history.save_person(None, 'Second')
    history.save_assignees(cpu.history_key, (first, second))
    with history.connect() as db:
        for table in ('machine_observations','global_configuration','cluster_resources','resource_rooms','resource_order','clusters','rooms',
                      'storage_ticks','storage_resources','alerts','shared_users'):
            db.execute(f'DROP TABLE {table}')
        db.execute('PRAGMA user_version=8')
    history.close()
    with client_for(config) as client:
        snapshot = client.get('/api/snapshot').json()
        by_id = {device['id']:device for device in snapshot['machines']}
        assert by_id['cpu']['assignment_mode'] == 'legacy'
        assert by_id['cpu']['hardware_kind'] == 'cpu'
        assert by_id['unknown']['hardware_kind'] == 'unconfirmed'
        assert client.put('/api/machines/cpu/settings', json={'enabled':False, 'checks':['cpu']}).status_code == 200
        assert len(client.get('/api/snapshot').json()['machines'][0]['assigned_users']) == 2
        shared = client.put('/api/machines/cpu/assignees', json={'mode':'shared','person_ids':[]})
        assert shared.json()['assignment_mode'] == 'shared'
        assert client.put('/api/machines/cpu/assignees', json={'mode':'person','person_ids':[first,second]}).status_code == 422
    with client_for(config) as client:
        assert client.get('/api/snapshot').json()['machines'][0]['assignment_mode'] == 'shared'
        restored = client.put('/api/machines/cpu/assignees', json={'person_ids':[first,second]})
        assert restored.json()['assignment_mode'] == 'legacy'


def test_storage_pending_and_synthetic_capacity(tmp_path):
    config = Config(data_dir=tmp_path)

    async def adapter(id, settings):
        pool = {'id':'pool-1','name':'Pool','used_bytes':30,'total_bytes':100,'health':'healthy'}
        return {'identity':'synthetic-logical','scope':'logical','observed_at':int(time.time()*1000),
                'health':'healthy','capacity':{'used_bytes':30,'total_bytes':100},
                'pools':[pool,pool],'members':[{'name':'member-1','capacity_bytes':100}]}

    with client_for(config, Monitor(config, storage_adapters={'synthetic-test':adapter})) as client:
        pending = client.post('/api/storage', json={'name':'Pending NAS','storage_kind':'nas','shared':True}).json()
        assert pending['status'] == 'pending' and pending['storage_observation'] is None
        assert pending['assignment_mode'] == 'shared'
        response = client.post('/api/storage', json={'name':'Observed pool','storage_kind':'storage_cluster',
                                                     'adapter':'synthetic-test'})
        assert response.status_code == 201
        id = response.json()['id']

        def observe():
            stored = next(node for node in client.get('/api/snapshot').json()['storage'] if node['id'] == id)
            return stored['storage_observation']

        result = wait_for(observe)
        assert result['capacity'] == {'used_bytes':30,'total_bytes':100}
        assert len(result['pools']) == len(result['members']) == 1
        assert client.get(f'/api/storage/{id}/history').json()['points'][-1]['values'] == [30]
    with client_for(config) as client:
        snapshot = client.get('/api/snapshot').json()
        assert all(item['status'] == 'pending' for item in snapshot['storage'])
        assert snapshot['storage_adapters'] == []
        updated = client.put(f'/api/storage/{id}',json={'name':'New name','storage_kind':'nas',
                                                       'adapter':'synthetic-test'})
        assert updated.status_code == 200 and updated.json()['status'] == 'pending'
        assert client.put(f'/api/storage/{id}',json={'name':'New name','storage_kind':'nas',
                                                    'adapter':'another-adapter'}).status_code == 409


def test_alert_transitions_restart_and_close(tmp_path):
    config = Config(data_dir=tmp_path)
    id = 'storage-fixture'
    history = History(tmp_path)
    history.prepare()

    from wattline.resources import StorageSettings
    history.save_storage(id, StorageSettings(name='Fixture',storage_kind='nas'), None)

    def sample(at, triggered=None, cleared=None):
        history.append_storage(id, at, 'unknown', None,
            (id,'nas','Fixture',at,triggered or {},cleared or {},None))

    at = int(time.time()*1000)
    sample(at, {'storage_health':('warning','pool unavailable')})
    original, = history.alert_events()['events']
    history.close()
    history.prepare()
    sample(at+1, {'storage_health':('warning','still unavailable')})
    sample(at+2)
    active, = history.alert_events(active=True)['events']
    assert (active['id'],active['first_at'],active['last_at']) == (original['id'],at,at+1)
    sample(at+3, cleared={'storage_health':'pool healthy'})
    sample(at+4, {'storage_health':('warning','failure recurred')})
    history.remove_storage(id, at+5)
    latest, recovered = history.alert_events()['events']
    assert recovered['id'] == original['id'] and recovered['recovered_at'] == at+3
    assert latest['id'] != original['id'] and latest['recovered_at'] is None
    assert latest['status'] == 'closed' and latest['closed_at'] == at+5
    history.close()
    with client_for(config) as client:
        persisted = client.get(f"/api/alerts/{original['id']}")
        assert persisted.status_code == 200 and persisted.json()['status'] == 'resolved'
        assert client.get('/api/alerts/999999').status_code == 404


def test_explicit_cpu_registration_preserves_fixed_host_and_default_checks(tmp_path):
    from wattline.collector import Collector, HostIdentity

    config = Config(data_dir=tmp_path)
    collector = Collector(config)

    async def identify(host, user, timeout):
        assert host == 'synthetic-cpu.invalid'
        return HostIdentity('c'*32, None)

    collector.identify = identify
    with client_for(config, Monitor(config, collector)) as client:
        body = {'host':'synthetic-cpu.invalid','enabled':False,'hardware_kind':'cpu'}
        response = client.post('/api/machines',json=body)
        assert response.status_code == 201
        id = response.json()['id']
        assert response.json()['checks'] == ['cpu','memory','system']
        assert response.json()['require_gpu'] is False
    with client_for(config) as client:
        device, = client.get('/api/snapshot').json()['machines']
        assert device['id'] == id and device['hardware_kind'] == 'cpu'
        assert client.get(f'/api/history?machine={id}').status_code == 200
