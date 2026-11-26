from fastapi.testclient import TestClient

from wattline.app import create_app
from wattline.config import Config, Machine


def machine(id, identity):
    return Machine(id=id, expected_host_id=identity*32, mode='ssh', ssh_alias=id, enabled=False)


def client_for(config):
    return TestClient(create_app(config), base_url='http://127.0.0.1')


def test_room_cluster_members_and_directory_references(tmp_path):
    first, second, independent = (machine('first','a'),machine('second','b'),machine('independent','c'))
    config = Config(data_dir=tmp_path, machines=(first,second,independent))
    with client_for(config) as client:
        get = lambda:client.get('/api/snapshot').json()
        person = client.post('/api/people',json={'name':'Owner'}).json()['id']
        east = client.post('/api/rooms',json={'name':'East','location':'R1','owner_id':person}).json()['id']
        west = client.post('/api/rooms',json={'name':'West'}).json()['id']
        storage = client.post('/api/storage',json={'name':'NAS','storage_kind':'nas'}).json()['id']
        assert client.put('/api/resources/first/room',json={'room_id':east}).status_code == 200
        assert client.put('/api/machines/second/settings',json={
            'room_id':west,'enabled':False,'checks':['cpu']}).status_code == 200
        assert client.put('/api/resources/independent/room',json={'room_id':east}).status_code == 200
        body = {'name':'Across','person_id':person,'members':['first','second',storage]}
        cluster = client.post('/api/clusters',json=body).json()['id']
        cluster2 = client.post('/api/clusters',json={'name':'Overlap','members':['first']}).json()['id']
        snapshot = get()
        assert set(snapshot['groups']['rooms'][0]['members']) == {'first','independent'}
        assert {row['id']:row['count'] for row in snapshot['groups']['clusters'][0]['rooms']} == {east:1,west:1,None:1}
        assert set(snapshot['machines'][0]['cluster_ids']) == {cluster,cluster2}
        refs = client.request('DELETE',f'/api/people/{person}?include_references=true',json={})
        assert refs.status_code == 409
        assert refs.json()['detail']['references'] == {'devices':[],'rooms':['East'],'clusters':['Across']}
        assert client.put(f'/api/people/{person}',json={'name':'New owner'}).status_code == 200
        assert client.put('/api/resources/order',json={'resources':[storage,'second','independent','first']}).status_code == 200
    with client_for(config) as client:
        snapshot = client.get('/api/snapshot').json()
        assert snapshot['groups']['rooms'][0]['owner'] == 'New owner'
        assert snapshot['resource_order'] == [storage,'second','independent','first']
        assert client.put('/api/machines/order',json={'machines':['first','second','independent']}).status_code == 200
        assert client.request('DELETE',f'/api/rooms/{east}',json={'confirm':True}).status_code == 204
        assert client.request('DELETE',f'/api/clusters/{cluster2}',json={'confirm':True}).status_code == 204
        snapshot = client.get('/api/snapshot').json()
        assert snapshot['resource_order'] == [storage,'first','second','independent']
        assert snapshot['machines'][0]['room_id'] is None
        assert snapshot['machines'][0]['cluster_ids'] == [cluster]
        assert set(snapshot['groups']['clusters'][0]['members']) == {'first','second',storage}
        assert client.request('DELETE',f'/api/storage/{storage}',json={'confirm':True}).status_code == 200
        assert set(client.get('/api/snapshot').json()['groups']['clusters'][0]['members']) == {'first','second'}


def test_group_history_uses_latest_hot_warm_ticks_and_scope(tmp_path):
    from wattline.groups import GROUP_BUCKET_MS
    from wattline.history import DAY_MS, History
    from wattline.resources import StorageObservation, StorageSettings
    from wattline.service import Monitor

    now = 1_800_000_000_000
    start = now-DAY_MS
    first,second,container = (machine('first','a'),machine('second','b'),machine('container','c'))
    config = Config(data_dir=tmp_path, machines=(first,second,container))
    history = History(tmp_path)
    history.prepare()
    gpu = {'uuid':'GPU-group-fixture','utilization_percent':0,'power_w':100,'power_kind':'reported'}

    def append(node, at, scope, usage, cores, used, total, gpus=(), status='normal'):
        metrics = {'scope':scope,'cpu_percent':usage,'cpu_count':cores,
                   'memory':{'used_bytes':used,'total_bytes':total},'gpus':gpus}
        history.append(node.history_key,'fixture',{
            'observed_at':at,'received_at':at,'source':'ssh','status':status,'metrics':metrics})

    append(first,start+10,'host',90,4,95,100)
    append(first,start+20,'host',0,4,20,100,[gpu])
    history.pack(start+21)
    append(second,start+50,'host',40,12,50,200,[gpu])
    append(container,start+40,'container',30,2,18,None,[gpu])
    append(first,start+GROUP_BUCKET_MS+10,'host',90,4,90,100)
    append(first,start+GROUP_BUCKET_MS+20,'host',None,None,None,None,status='offline')

    for id in ('storage-one','storage-two','storage-unverified','storage-child'):
        kind = 'storage_cluster' if id == 'storage-one' else 'nas'
        history.save_storage(id, StorageSettings(name=id,storage_kind=kind),None)
        observation = StorageObservation(identity='child-pool' if id == 'storage-child' else 'duplicate-pool',
            covered_identities=['child-pool'] if kind == 'storage_cluster' else [], observed_at=start+60,
            scope='unverified' if id.endswith('unverified') else 'logical',health='healthy',
            capacity={'used_bytes':80,'total_bytes':200})
        history.append_storage(id,start+60,'normal',observation)
    history.close()

    with TestClient(create_app(config, monitor=Monitor(config,clock=lambda:now)),base_url='http://127.0.0.1') as client:
        room = client.post('/api/rooms',json={'name':'Room'}).json()['id']
        for id in ('first','second','container','storage-one','storage-two','storage-unverified','storage-child'):
            assert client.put(f'/api/resources/{id}/room',json={'room_id':room}).status_code == 200

        def points(metric):
            response = client.get('/api/group-history',params={'kind':'room','group':room,'metric':metric})
            assert response.status_code == 200, response.text
            result = response.json()
            assert result['membership'] == 'current'
            assert result['to']-result['from'] == DAY_MS
            assert len(result['points']) == 288
            return result['points']

        cpu = points('cpu')
        assert cpu[0]['values'] == [30,30] and cpu[0]['coverage'] == [[2,2],[1,1]]
        assert cpu[1]['values'] == [None,None] and cpu[1]['breaks'] == [True,True]
        assert points('memory')[0]['values'] == [70/3,None]
        assert points('memory_used')[0]['values'] == [70,18]
        assert points('gpu')[0]['values'] == [0,0]
        assert points('power')[0]['values'] == [100,100]
        assert points('storage')[0]['values'] == [40]
        assert points('storage')[0]['coverage'] == [[1,4]]
        assert client.get('/api/history?metric=cpu').json()['keys'] == ['cpu']
        assert client.get('/api/history?machine=first').json()['keys'] == ['cpu']


def test_live_overview_power_deduplicates_and_reports_independent_coverage(tmp_path):
    import json

    from wattline.history import History
    from wattline.service import Monitor, metrics_from

    first, second, stale = (machine('first','a'),machine('second','b'),machine('stale','c'))
    hosts = tuple(node.model_copy(update={'enabled':True}) for node in (first,second,stale))
    config = Config(data_dir=tmp_path, machines=hosts)
    now = 1_800_000_000_000
    monitor = Monitor(config, clock=lambda:now)
    monitor.start_sampler = lambda _machine: None

    def sample(scope, at, gpus):
        metrics = metrics_from({'scope':scope,'gpus':gpus}, None)
        return {'observed_at':at,'received_at':at,'source':'ssh','status':'normal','metrics':metrics}

    monitor.latest.update(
        first=sample('host',now-200,[
            {'uuid':'GPU-shared','power_w':80,'power_limit_w':200,'default_power_limit_w':350},
            {'uuid':'GPU-legacy','power_w':22,'power_limit_w':700},
            {'uuid':'GPU-zero','power_w':0,'default_power_limit_w':0},
        ]),
        second=sample('container',now-100,[
            {'uuid':'GPU-SHARED','power_w':90},
            {'uuid':'GPU-rated-only','default_power_limit_w':500},
            {'uuid':'GPU-missing','default_power_limit_w':True},
        ]),
        stale=sample('host',now-3_600_000,[
            {'uuid':'GPU-stale','power_w':1000,'default_power_limit_w':2000},
        ]),
    )
    with TestClient(create_app(config, monitor=monitor),base_url='http://127.0.0.1') as client:
        view = client.get('/api/snapshot').json()
        assert view['summary']['visible_gpu'] == 5
        assert view['summary']['gpu_power'] == {'value':112,'valid':3,'total':5}
        assert view['summary']['gpu_rated_power'] == {'value':850,'valid':2,'total':5}
        host = view['machines'][0]
        assert host['metrics']['gpus'][0]['power_limit_w'] == 200
        assert host['metrics']['gpus'][0]['default_power_limit_w'] == 350
        monitor.latest['first']['metrics']['gpus'][0].pop('default_power_limit_w')
        monitor.latest['second']['metrics']['gpus'][1].pop('default_power_limit_w')
        assert client.get('/api/snapshot').json()['summary']['gpu_rated_power'] == {'value':None,'valid':0,'total':5}

    history = History(tmp_path)
    history.prepare()
    try:
        snapshot = sample('host',now-1000,[{'uuid':'GPU-shared','power_w':80,'power_limit_w':200,
                                           'default_power_limit_w':350}])
        history.append(first.history_key,'fixture',snapshot)
        with history.connect(read=True) as db:
            saved, = db.execute('SELECT metrics FROM gpu_ticks').fetchone()
        assert json.loads(saved) == {'uuid':'GPU-shared','index':0,'power_w':80,'power_limit_w':200}
    finally:
        history.close()


def test_layered_configuration_keeps_legacy_values_and_group_writes_atomic(tmp_path):
    import json

    from wattline.history import History

    field = 'idle_memory_tolerance_mib'
    first = machine('first','a').model_copy(update={field:0})
    second, third = machine('second','b'), machine('third','c')
    legacy = machine('legacy','d')
    config = Config(data_dir=tmp_path, machines=(first,second,third))
    history = History(tmp_path)
    history.prepare()
    try:
        registration = legacy.model_copy(update={field:0}).model_dump_json()
        history.save_machine(legacy.history_key, registration, json.dumps({'enabled':False}), None, {})
        history.save_machine(third.history_key, None, json.dumps({'enabled':False, field:0}), None, {})
        with history.connect() as db:
            db.execute('ALTER TABLE rooms DROP COLUMN idle_memory_tolerance_mib')
            db.execute('ALTER TABLE clusters DROP COLUMN idle_memory_tolerance_mib')
            db.execute('DROP TABLE global_configuration')
            db.execute('DROP TABLE machine_observations')
            db.execute("INSERT INTO rooms(id,name) VALUES ('east','East'), ('west','West')")
            db.execute("INSERT INTO clusters(id,name,shared) VALUES ('across','Across',0)")
            db.execute('INSERT INTO resource_rooms(resource,room) VALUES (?,?),(?,?)',
                       ('compute:'+first.history_key,'east','compute:'+second.history_key,'west'))
            db.execute('INSERT INTO cluster_resources(cluster,resource) VALUES (?,?),(?,?)',
                       ('across','compute:'+first.history_key,'across','compute:'+second.history_key))
            db.execute('PRAGMA user_version=10')
    finally:
        history.close()

    def snapshot(client):
        return client.get('/api/snapshot').json()

    def policies(client):
        return {node['id']:node['idle_memory_configuration'] for node in snapshot(client)['machines']}

    def put(client, path, **values):
        response = client.put(path,json=values)
        response.raise_for_status()
        return response.json()

    first_settings = '/api/machines/first/settings'
    with client_for(config) as client:
        baseline = policies(client)
        assert {id:policy['effective'] for id,policy in baseline.items()} == {
            'first':0,'second':256,'third':0,'legacy':256}
        assert snapshot(client)['groups']['clusters'][0]['members'] == ['first','second']
        assert snapshot(client)['groups']['rooms'][0]['idle_memory_configuration']['override'] is None
        put(client, '/api/configuration', **{field:380})
        put(client, '/api/rooms/east', name='East', **{field:192})
        assert put(client, first_settings, enabled=False, **{field:None})[field] == 192
        assert put(client, first_settings, enabled=False, alias='Fixture')[field] == 192
        current = policies(client)
        assert current['first']['source'] == {'scope':'room','ids':['east']}
        assert current['second']['effective'] == current['legacy']['effective'] == 380
        assert current['third']['effective'] == 0
        primary = '/api/clusters/across'
        put(client, primary, name='Across', members=['first','second'], **{field:64})
        other = client.post('/api/clusters',json={'name':'Other','members':['first'],field:64}).json()['id']
        consensus = policies(client)['first']
        assert consensus['effective'] == 64
        assert consensus['source'] == {'scope':'cluster','ids':sorted(['across',other])}
        put(client, '/api/clusters/'+other, name='A renamed cluster', members=['first'])
        assert policies(client)['first'] == consensus
        put(client, '/api/clusters/'+other, name='A renamed cluster', members=['first'], **{field:0})
        assert policies(client)['first']['cluster_conflict']
        assert policies(client)['first']['effective'] == 192
        invalid = client.put(first_settings,json={'enabled':False,'configuration_cluster_id':'missing'})
        assert invalid.status_code == 409
        chosen = put(client, first_settings, enabled=False, configuration_cluster_id=other)
        assert chosen[field] == 0 and chosen['idle_memory_configuration']['override'] is None
        assert put(client, first_settings, enabled=False, **{field:10})[field] == 10
        assert put(client, first_settings, enabled=False, **{field:None})[field] == 0
        assert put(client, first_settings, enabled=False)[field] == 0
        assert client.put('/api/configuration', content='{"idle_memory_tolerance_mib":NaN}',
                          headers={'Content-Type':'application/json'}).status_code == 422
        assert client.put('/api/configuration', json={field:192},
                          headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
        with history.connect() as db:
            db.execute("""CREATE TRIGGER reject_cluster_membership BEFORE INSERT ON cluster_resources
                          WHEN NEW.cluster='across' BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END""")
        before = snapshot(client)['groups']
        assert client.put(primary,json={'name':'Should roll back','members':['second'],field:600}).status_code == 503
        assert snapshot(client)['groups'] == before
        with history.connect() as db:
            db.execute("""CREATE TRIGGER reject_global_configuration BEFORE UPDATE ON global_configuration
                          BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END""")
        assert client.put('/api/configuration',json={field:400}).status_code == 503
        assert policies(client)['legacy']['effective'] == 380

    with client_for(config) as client:
        current = policies(client)
        assert current['first']['source'] == {'scope':'cluster','ids':[other]}
        assert current['first']['override'] is None and current['first']['effective'] == 0
        assert current['second']['effective'] == 64 and current['legacy']['effective'] == 380
        group, = [group for group in snapshot(client)['groups']['clusters'] if group['id'] == 'across']
        assert group['name'] == 'Across' and group['members'] == ['first','second'] and group[field] == 64
        assert client.request('DELETE', '/api/clusters/'+other, json={'confirm':True}).status_code == 204
        current = policies(client)['first']
        assert current['invalid_cluster_selection'] and current['effective'] == 64
        assert put(client, first_settings, enabled=False, configuration_cluster_id=None)[field] == 64
        with history.connect() as db:
            db.execute('DROP TRIGGER reject_cluster_membership')
            db.execute('DROP TRIGGER reject_global_configuration')
        put(client, primary, name='Across', members=['first','second'], **{field:None})
        put(client, '/api/rooms/east', name='East', **{field:None})
        assert policies(client)['first']['effective'] == 380
        put(client, '/api/configuration', **{field:None})
        current = policies(client)
        assert current['first']['effective'] == 256 and current['third']['effective'] == 0
