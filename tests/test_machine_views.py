from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from wattline.app import create_app
from wattline.collector import CollectionError
from wattline.config import Config, Machine
from wattline.history import DAY_MS, WARM_MS
from wattline.machine_views import SourceObservation
from wattline.service import Monitor


SHARED_BOOT = '11111111-1111-4111-8111-111111111111'
OTHER_BOOT = '22222222-2222-4222-8222-222222222222'
CONTAINER_ID = 'ab' * 32


def node(id, identity):
    return Machine(id=id, expected_host_id=identity*32, mode='ssh', ssh_alias=id, address='shared-label.invalid')


def api(monitor):
    return AsyncClient(transport=ASGITransport(app=create_app(monitor.config, monitor=monitor)),
                       base_url='http://127.0.0.1')


def monitor_for(tmp_path, machines, clock, collector=None):
    monitor = Monitor(Config(data_dir=tmp_path, machines=machines), collector, clock=clock)
    monitor.start_sampler = lambda _node: None
    return monitor


def gpu(uuid, power):
    return {'uuid':uuid, 'name':uuid, 'utilization_percent':0, 'power_w':power, 'power_kind':'reported'}


async def test_machine_roster_uses_verified_boots_and_survives_collection_failure(tmp_path):
    host, container, sibling, independent, unknown, mismatch = (
        node(name,key) for name,key in zip(('host','container','sibling','independent','unknown','mismatch'),'abcdef'))
    machines = host, container, sibling, independent, unknown, mismatch
    now = 1_800_000_000_000
    offline = set()
    boots = {host.id:SHARED_BOOT, container.id:SHARED_BOOT, sibling.id:SHARED_BOOT,
             independent.id:OTHER_BOOT, unknown.id:'unverified', mismatch.id:SHARED_BOOT}

    async def collect(source):
        if source.id in offline:
            raise CollectionError('offline', 'fixture')
        scoped = source in (container,sibling)
        gpus = [gpu('GPU-shared',100)] if source in (host,container) else []
        if source == sibling:
            gpus = [gpu('GPU-second',50)]
        return {'host_id':source.expected_host_id if source != mismatch else independent.expected_host_id,
                'boot_id':boots[source.id], 'scope':'container' if scoped else 'host',
                'container_id':CONTAINER_ID if source == container else None,
                'cpu_count':2 if scoped else 16, 'gpus':gpus, 'gpu_inventory_complete':not scoped,
                'memory':{'used_bytes':20 if scoped else 50, 'total_bytes':100 if scoped else 1000}}

    monitor = monitor_for(tmp_path, machines, lambda:now, collect)
    await monitor.load_registry()

    async def sample(*nodes):
        for source in nodes:
            result = await monitor.observe(source)
            monitor.latest[source.id] = result
            monitor.history.append(source.history_key, 'fixture', result)

    try:
        async with api(monitor) as client:
            await sample(*machines)
            await client.put('/api/resources/container/room', json={'room_id':None})
            cluster = (await client.post('/api/clusters', json={'name':'Cluster','members':['container','host']})).json()['id']
            snapshot = (await client.get('/api/snapshot')).json()
            assert [item['id'] for item in snapshot['machines']] == ['host','independent','unknown','mismatch']
            machine = snapshot['machines'][0]
            assert [source['id'] for source in machine['sources']] == ['host','container','sibling']
            assert machine['sources'][1]['container_id'] == CONTAINER_ID
            assert machine['scope'] == 'host' and machine['metrics']['memory']['used_bytes'] == 50
            assert snapshot['summary']['registered'] == 4 and snapshot['summary']['online'] == 3
            assert snapshot['summary']['gpu_power'] == {'value':150,'valid':2,'total':2}
            group, = snapshot['groups']['clusters']
            assert group['id'] == cluster and group['members'] == ['host']
            assert group['summary']['machine']['memory']['total_bytes'] == 1000
            assert (await client.put('/api/resources/order', json={
                'resources':['unknown','independent','host','mismatch']})).json()['resources'] == [
                'unknown','independent','host','mismatch']
            assert (await client.put('/api/machines/container/settings', json={
                'checks':['cpu','memory','gpu'], 'alias':'Container label'})).status_code == 200

            # A confirmed host going offline leaves the machine intact. Cgroup usage stays scoped.
            now += 1000
            offline.add(host.id)
            await sample(host, container, sibling)
            snapshot = (await client.get('/api/snapshot')).json()
            machine = next(item for item in snapshot['machines'] if item['id'] == host.id)
            assert machine['scope'] == 'container' and machine['metrics']['memory']['used_bytes'] == 20
            assert machine['sources'][1]['name'] == 'Container label'
            assert snapshot['groups']['clusters'][0]['summary']['machine']['memory']['valid'] == 1
            assert snapshot['groups']['clusters'][0]['summary']['machine']['memory']['total'] == 1
            assert snapshot['summary']['registered'] == 4 and snapshot['summary']['visible_gpu'] == 2

            # One verified source moves to a different boot. Its old evidence cannot hold the group together.
            now += 1000
            boots[sibling.id] = '33333333-3333-4333-8333-333333333333'
            await sample(sibling)
            assert len((await client.get('/api/snapshot')).json()['machines']) == 5
    finally:
        await monitor.close()

    now += WARM_MS + 1
    recovered = monitor_for(tmp_path, machines, lambda:now, collect)
    await recovered.load_registry()
    try:
        async with api(recovered) as client:
            snapshot = (await client.get('/api/snapshot')).json()
            assert snapshot['resource_order'] == ['unknown','independent','host','sibling','mismatch']
            assert snapshot['summary']['registered'] == 5 and snapshot['summary']['online'] == 0
            assert (await client.request('DELETE', '/api/machines/container', json={'confirm':True})).status_code == 200
            evidence = recovered.history.source_observations([host.history_key,container.history_key],now)
            assert evidence[host.history_key].boot == SHARED_BOOT and container.history_key not in evidence
            assert host.id in recovered.machines
    finally:
        await recovered.close()


async def test_machine_history_and_cold_archive_keep_source_provenance(tmp_path):
    host, container, independent = (node(name,key) for name,key in [('host','a'),('container','b'),('independent','c')])
    now = int(datetime(2026, 4, 10, 12, tzinfo=timezone.utc).timestamp()*1000)
    monitor = monitor_for(tmp_path, (host,container,independent), lambda:now)
    history = monitor.history
    history.prepare()

    def append(source, at, scope, value, boot, gpus=(), memory=None):
        history.append(source.history_key, 'fixture', {
            'observed_at':at, 'received_at':at, 'source':'ssh', 'boot':boot, 'status':'normal',
            'metrics':{'scope':scope,'cpu_percent':value,'cpu_count':4,'gpus':gpus,'memory':memory,
                       'gpu_percent':value, 'gpu_generation':','.join(card['uuid'] for card in gpus)},
        })

    cold = now-9*DAY_MS
    warm = now-2*DAY_MS
    recent = now-15_000
    for at in (cold, warm, recent):
        append(container,at-3_600_000,'container',99,OTHER_BOOT)
        append(container,at-1_800_000,'container',88,None)
        append(host,at-900_000,'host',None,SHARED_BOOT,memory={'used_bytes':8,'total_bytes':None})
        append(container,at-900_000,'container',0,SHARED_BOOT,memory={'used_bytes':10,'total_bytes':20})
        append(host,at,'host',21,SHARED_BOOT,[gpu('GPU-shared',100)])
        append(container,at,'container',76,SHARED_BOOT,[gpu('GPU-shared',100),gpu('GPU-extra',50)],
               {'used_bytes':0,'total_bytes':20})
        append(independent,at,'host',33,OTHER_BOOT)
    history.pack(now-DAY_MS)
    assert history.begin_archive(now) == now
    exported = history.export(now-WARM_MS)
    history.finish_archive(now,now-WARM_MS,exported)
    archive_file = history.cold_directory / exported.filename
    original = archive_file.read_bytes()
    await monitor.load_registry()

    def values(response):
        response.raise_for_status()
        return [point['values'][0] for point in response.json()['points'] if point['values'][0] is not None]

    try:
        async with api(monitor) as client:
            cpu = await client.get('/api/history', params={'machine':'container','metric':'cpu','hours':72})
            assert values(cpu) == [21,21] and cpu.json()['scope'] == 'host'
            source = await client.get('/api/history',params={'machine':'host','source':'container','metric':'cpu','hours':72})
            assert values(source) == [99,88,0,76,99,88,0,76]
            projected = await client.get('/api/history',params={'machine':'host','metric':'cpu','scope':'container','hours':72})
            assert values(projected) == [0,76,0,76]
            assert (await client.get('/api/history',params={'machine':'host','source':'independent'})).status_code == 404
            overview = (await client.get('/api/history',params={'metric':'cpu'})).json()
            assert overview['machines'] == ['host','independent']
            assert overview['points'][-1]['values'] == [21,33]
            assert any(point['values'] == [0,None] for point in overview['points'])
            machine_query = {'machine':'host','view':'machine','hours':72}
            for metric, expected in [('cpu',[0,21,0,21]), ('memory',[0,0]), ('memory_used',[8,0,8,0])]:
                response = await client.get('/api/history', params=dict(machine_query, metric=metric))
                assert values(response) == expected and 'scope' not in response.json()
                if metric == 'cpu':
                    assert all(point['breaks'][0] for point in response.json()['points'])
            assert values(await client.get('/api/history', params=dict(machine_query, metric='cpu',
                                                                        scope='host'))) == [21,21]

            cluster = (await client.post('/api/clusters',json={'name':'Cluster','members':['host','container']})).json()['id']
            params = {'group':cluster,'kind':'cluster','metric':'power','view':'machine'}
            group_history = (await client.get('/api/group-history',params=params)).json()
            assert [series['scope'] for series in group_history['series']] == ['machine']
            assert group_history['points'][-1]['values'] == [150]
            hosts_only = (await client.get('/api/group-history',params=dict(params,metric='cpu'))).json()
            assert hosts_only['points'][-1]['values'] == [21]
            assert hosts_only['points'][-1]['coverage'] == [[1,1]]

            path = '/api/machines/host/archive-analysis'
            for source_id, scope, expected in [(None,None,[21]),(None,'container',[0,76]),
                                               ('container',None,[99,88,0,76])]:
                select = {'source':source_id} if source_id else {}
                assert (await client.post(path,params=select,json={})).status_code == 200
                await monitor.archive_analyses[monitor.archive_selection(host.id,source_id)].task
                params = dict(select, start='2026-04-01', end='2026-04-01', metric='cpu')
                if scope:
                    params['scope'] = scope
                assert values(await client.get(path+'/series',params=params)) == expected
            for metric, expected in [('cpu',[0,21]), ('memory',[0]), ('memory_used',[8,0])]:
                params = {'start':'2026-04-01','end':'2026-04-01','metric':metric,'view':'machine'}
                assert values(await client.get(path+'/series',params=params)) == expected
            assert archive_file.read_bytes() == original
    finally:
        await monitor.close()


async def test_two_container_sources_without_a_host_show_cgroup_values_once(tmp_path):
    first, second = node('first','a'), node('second','b')
    now = 1_800_000_000_000

    async def collect(source):
        return {'host_id':source.expected_host_id, 'boot_id':SHARED_BOOT, 'scope':'container',
                'memory':{'used_bytes':30 if source == first else 50, 'total_bytes':100}}

    monitor = monitor_for(tmp_path, (first,second), lambda:now, collect)
    await monitor.load_registry()
    try:
        for source in (first,second):
            monitor.latest[source.id] = await monitor.observe(source)
        async with api(monitor) as client:
            snapshot = (await client.get('/api/snapshot')).json()
            machine, = snapshot['machines']
            assert machine['scope'] == 'container' and machine['metrics']['memory']['used_bytes'] == 30
            assert snapshot['summary']['registered'] == snapshot['summary']['online'] == 1
            assert snapshot['summary']['machine']['memory']['valid'] == 1
            assert snapshot['summary']['machine']['memory_used']['value'] == 30
            assert snapshot['summary']['machine']['memory']['total'] == 1
    finally:
        await monitor.close()


async def test_group_resources_select_each_machine_metric_once(tmp_path):
    host, container, sibling, other, empty = (
        node(name, key) for name, key in zip(('host','container','sibling','other','empty'), 'abcde'))
    now = 1_800_000_000_000
    monitor = monitor_for(tmp_path, (host, container, sibling, other, empty), lambda:now)
    await monitor.load_registry()

    def record(source, scope, boot, cpu, cores, memory, age=0):
        at = now-age
        observation = SourceObservation.from_sample(boot, scope, None, at)
        sample = {'observed_at':at, 'received_at':at, 'boot':boot, 'status':'normal', 'source':'ssh',
                  'source_observation':observation,
                  'metrics':{'scope':scope, 'cpu_percent':cpu, 'cpu_count':cores, 'memory':memory}}
        monitor.source_observations[source.id] = observation
        monitor.latest[source.id] = sample
        monitor.history.append(source.history_key, 'fixture', sample)

    try:
        record(host, 'host', SHARED_BOOT, 0, 16, None, age=3000)
        record(container, 'container', SHARED_BOOT, 90, 2, {'used_bytes':0,'total_bytes':20})
        record(sibling, 'container', SHARED_BOOT, 100, 4, {'used_bytes':15,'total_bytes':30}, age=1000)
        record(other, 'container', OTHER_BOOT, 90, 2, {'used_bytes':12,'total_bytes':None})
        record(empty, 'host', None, None, 32, None)
        async with api(monitor) as client:
            cluster = (await client.post('/api/clusters', json={
                'name':'Cluster', 'members':['host','container','sibling','other','empty']})).json()['id']
            snapshot = (await client.get('/api/snapshot')).json()
            group, = snapshot['groups']['clusters']
            assert group['members'] == ['host','other','empty']
            summary = group['summary']['machine']
            assert summary['cpu'] == {'value':10,'valid':2,'total':3}
            assert summary['memory_used'] == {'value':12,'valid':2,'total':3}
            assert summary['memory'] == {'used_bytes':0,'total_bytes':20,'percent':0,
                                         'unbounded_used_bytes':12,'valid':1,'total':3}
            projected = snapshot['machines'][0]['machine_metrics']
            assert (projected['cpu_percent'], projected['cpu_scope'], projected['cpu_count']) == (0,'host',16)
            assert (projected['memory_scope'], projected['memory_percent']) == ('container',0)
            assert snapshot['machines'][1]['machine_metrics']['memory_percent'] is None
            assert snapshot['machines'][2]['machine_metrics']['cpu_percent'] is None
            assert group['summary']['host']['memory_used']['valid'] == 0
            assert group['summary']['container']['memory_used']['value'] == 12

            base = {'kind':'cluster', 'group':cluster}
            for metric, expected, valid in [('cpu',10,2), ('memory_used',12,2), ('memory',0,1)]:
                response = await client.get('/api/group-history', params=dict(base, metric=metric, view='machine'))
                point = response.json()['points'][-1]
                assert point['values'] == [expected] and point['coverage'] == [[valid,3]]
            scoped = (await client.get('/api/group-history', params=dict(base, metric='memory_used'))).json()
            assert [series['scope'] for series in scoped['series']] == ['host','container']
            assert scoped['points'][-1]['values'] == [None,12]

            # Reverse the missing metric and use a newer container with no CPU reading.
            now += 1000
            record(host, 'host', SHARED_BOOT, None, 16, {'used_bytes':40,'total_bytes':100})
            record(container, 'container', SHARED_BOOT, None, 2, {'used_bytes':0,'total_bytes':20})
            projected = (await client.get('/api/snapshot')).json()['machines'][0]['machine_metrics']
            assert (projected['cpu_percent'], projected['cpu_scope'], projected['cpu_count']) == (100,'container',4)
            assert (projected['memory_scope'], projected['memory_percent']) == ('host',40)
    finally:
        await monitor.close()
