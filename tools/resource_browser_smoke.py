"""Run browser journeys against the in-process resource API and synthetic data."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from wattline.app import create_app
from wattline.config import Config, Machine
from wattline.machine_views import SourceObservation
from wattline.service import Monitor, metrics_from

ORIGIN = 'http://localhost'
OUT = Path(__file__).resolve().parents[1] / 'artifacts'


def open_api_page(browser, client):
    def forward(route):
        request = route.request
        if not request.url.startswith(ORIGIN+'/'):
            return route.abort()
        headers = {name:value for name,value in request.headers.items() if name in ('content-type','sec-fetch-site')}
        response = client.request(request.method, request.url.removeprefix(ORIGIN),
                                  headers=headers, content=request.post_data_buffer)
        route.fulfill(status=response.status_code, body=response.content,
                      content_type=response.headers.get('content-type'))

    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/*', forward)
    page.goto(ORIGIN)
    return page, errors


def check_overview_power(browser):
    with TemporaryDirectory() as directory:
        hosts = tuple(Machine(id=id, expected_host_id=identity*32, mode='ssh', ssh_alias=id)
                      for id,identity in (('synthetic-host','a'),('synthetic-container','b')))
        config = Config(data_dir=Path(directory), machines=hosts)
        now = int(time.time()*1000)
        monitor = Monitor(config, clock=lambda:now)
        monitor.start_sampler = lambda _machine: None

        def synthetic(scope, at, gpus):
            return {'status':'normal','observed_at':at,'received_at':at,
                    'metrics':metrics_from({'scope':scope,'gpus':gpus}, None)}

        monitor.latest.update({
            'synthetic-host':synthetic('host',now-200,[
                {'uuid':'GPU-shared','power_w':120,'power_limit_w':225,'default_power_limit_w':450},
                {'uuid':'GPU-measured','power_w':50,'power_limit_w':200},
                {'uuid':'GPU-idle','power_w':0},
            ]),
            'synthetic-container':synthetic('container',now-100,[
                {'uuid':'GPU-shared','power_w':150},
                {'uuid':'GPU-rating-only','default_power_limit_w':350},
            ]),
        })
        with TestClient(create_app(config, monitor=monitor), base_url=ORIGIN) as client:
            page, errors = open_api_page(browser, client)
            cards = page.locator('.overview-metrics > .metric')
            power = cards.last
            expect(cards).to_have_count(3)
            expect(power).to_contain_text('当前总功率')
            expect(power).to_contain_text('额定口径为 GPU 默认功率上限')
            expect(power.locator('[data-value=watts]')).to_have_text('200')
            expect(power.locator('[data-value=rated-watts]')).to_have_text('800')
            expect(power.locator('[data-value=power-count]')).to_have_text('3/4 张可见 GPU 有读数')
            expect(power.locator('[data-value=rated-power-count]')).to_have_text('2/4 张可见 GPU 有读数')

            for locale in ('zh-CN','en'):
                page.locator('#locale-select').select_option(locale)
                expect(power).to_contain_text('总额定功率' if locale == 'zh-CN' else 'Total rated power')
                for width in (1440, 976, 975, 730, 390, 320):
                    page.set_viewport_size({'width':width,'height':900})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (locale,width)
                    bounds = cards.evaluate_all("""cards => cards.map(card => ({
                      top:card.getBoundingClientRect().top, width:card.clientWidth, scrollWidth:card.scrollWidth
                    }))""")
                    if width > 975:
                        assert len({card['top'] for card in bounds}) == 1, bounds
                    else:
                        assert bounds[0]['top'] == bounds[1]['top'] < bounds[2]['top'], bounds
                    assert all(card['scrollWidth'] <= card['width'] for card in bounds), (locale,width,bounds)

            page.locator('.overview-metrics').screenshot(path=OUT/'an164-power-320.png')
            page.set_viewport_size({'width':1440,'height':900})
            page.locator('#locale-select').select_option('zh-CN')
            page.locator('.overview-metrics').screenshot(path=OUT/'an164-power-desktop.png')
            for snapshot in monitor.latest.values():
                for gpu in snapshot['metrics']['gpus']:
                    gpu.pop('default_power_limit_w', None)
            page.reload()
            expect(power.locator('[data-value=rated-watts]')).to_have_text('—')
            expect(power.locator('[data-value=rated-power-count]')).to_have_text('0/4 张可见 GPU 有读数')
            expect(power.locator('[data-value=watts]')).to_have_text('200')
            assert not errors, errors
            page.close()


def check_machine_sources(browser):
    with TemporaryDirectory() as directory:
        ids = ('fixture-host','fixture-container-one','fixture-container-two','fixture-other')
        hosts = tuple(Machine(id=id, expected_host_id=key*32, mode='ssh', ssh_alias=id)
                      for id,key in zip(ids,'abcd'))
        config = Config(data_dir=Path(directory), machines=hosts)
        now = int(time.time()*1000)
        monitor = Monitor(config, clock=lambda:now)
        monitor.start_sampler = lambda _source: None
        monitor.history.prepare()
        for index, source in enumerate(hosts):
            container = index in (1,2)
            scope = 'container' if container else 'host'
            boot = ('11111111-1111-4111-8111-111111111111' if index < 3
                    else '22222222-2222-4222-8222-222222222222')
            at = now-1000+index
            metrics = metrics_from({
                'scope':scope, 'cpu_count':2 if container else 8,
                'memory':{'used_bytes':1024**3, 'total_bytes':(2 if container else 8)*1024**3} if index else None,
                'gpu_inventory_complete':True,
                'gpus':[{'uuid':'GPU-fixture-one','power_w':100,'power_kind':'reported'}] if index < 3 else [],
            }, 60 if container else 0 if index == 0 else 25)
            observation = SourceObservation.from_sample(boot, scope, 'ab'*32 if index == 1 else None, at)
            sample = {'source':'ssh','observed_at':at,'received_at':at,'status':'normal','boot':boot,
                      'metrics':metrics,'source_observation':observation}
            monitor.history.append(source.history_key,'synthetic',sample)
            monitor.latest[source.id] = sample

        with TestClient(create_app(config, monitor=monitor), base_url=ORIGIN) as client:
            room = client.post('/api/rooms',json={'name':'Fixture room'}).json()['id']
            for source in hosts[:3]:
                client.put(f'/api/resources/{source.id}/room',json={'room_id':room}).raise_for_status()
            client.post('/api/clusters',json={'name':'Fixture cluster','members':list(ids[:3])}).raise_for_status()
            page, errors = open_api_page(browser, client)
            expect(page.locator('[data-value=online]')).to_have_text('2 / 2')
            expect(page.locator('[data-value=watts]')).to_have_text('100')
            for locale, memory_label in [('en','Memory'), ('zh-CN','内存')]:
                page.locator('#locale-select').select_option(locale)
                for kind in ('room','cluster'):
                    page.locator(f'#overview-tab-{kind}').click()
                    table = page.locator('.group-summary')
                    expect(table.get_by_role('columnheader',name='CPU',exact=True)).to_be_visible()
                    expect(table.get_by_role('columnheader',name=memory_label,exact=True)).to_be_visible()
                    expect(table.locator('[data-group-reading=cpu]')).to_have_text('0% · 1/1')
                    expect(table.locator('[data-group-reading=memory]')).to_contain_text('1.0 GiB / 2.0 GiB')
                    page.locator('[data-overview-metric=memory]').click()
                    page.wait_for_function('state.history?.keys[0] === "memory" && state.history.points.at(-1).values[0] === 50')
                    expect(page.locator('#chart-legend [data-legend-group]')).to_have_text(f'Fixture {kind}')
                    table.get_by_role('button',name=f'Fixture {kind}',exact=True).click()
                    expect(page.locator('.metric:has([data-group-reading=cpu]) .metric-name')).to_have_text('CPU')
                    expect(page.locator('.metric:has([data-group-reading=memory]) .metric-name')).to_have_text(memory_label)
                    expect(page.locator('.metric [data-group-reading=memory]')).to_contain_text('50%')
                    page.locator('#breadcrumb [data-overview]').click()
            page.locator('#overview-tab-machine').click()
            expect(page.locator('#host-rows [data-machine-row]')).to_have_count(2)
            page.locator('#host-search').fill('fixture-container-one')
            expect(page.locator('#host-rows [data-machine-row]')).to_have_attribute('data-machine-row',ids[0])
            page.locator('#host-rows .row-open').click()
            expect(page.locator('#page-heading')).to_have_text(ids[0])
            expect(page.locator('[data-value=card-cpu]')).to_have_text('0')
            expect(page.locator('[data-value=card-memory]')).to_have_text('50')
            page.wait_for_function('state.history?.points.at(-1)?.values[0] === 0 && !state.history.scope')
            page.locator('.machine-sources summary').click()
            expect(page.locator('.machine-sources')).to_contain_text('abababababab')
            expect(page.locator('.machine-sources')).to_contain_text(ids[2])
            page.locator(f'[data-configure-source="{ids[1]}"]').click()
            expect(page.locator('#machine-target')).to_have_text(ids[1])
            page.locator('#machine-cancel').click()
            page.locator('#trend-source').select_option(ids[1])
            page.wait_for_function('state.history?.scope === "container" && state.history.points.at(-1).values[0] === 60')

            monitor.latest[ids[0]] = {'observed_at':now,'received_at':now,'status':'offline','metrics':None}
            page.wait_for_function('getHost()?.scope === "container"')
            expect(page.locator('.scope-note')).to_contain_text('容器')
            expect(page.locator('[data-value=card-cpu]')).to_have_text('60')
            page.goto(ORIGIN+'/#device/'+ids[1])
            expect(page.locator('#page-heading')).to_have_text(ids[0])
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors, errors
            page.close()


def check_resources(browser):
    with TemporaryDirectory() as directory:
        hosts = tuple(Machine(id=id, expected_host_id=identity*32, mode='ssh',
                              ssh_alias=id, enabled=False, require_gpu=False)
                      for id,identity in (('east-cpu','a'),('west-cpu','b'),('unplaced-cpu','c')))
        config = Config(data_dir=Path(directory), machines=hosts)

        async def synthetic(resource_id, settings):
            return {'identity':'synthetic-pool','scope':'logical','observed_at':int(time.time()*1000),
                    'health':'degraded','capacity':{'used_bytes':3*1024**4,'total_bytes':8*1024**4},
                    'pools':[{'id':'p1','name':'Logical pool','used_bytes':3*1024**4,
                              'total_bytes':8*1024**4,'health':'degraded'}],
                    'members':[{'name':'Synthetic member','role':'data','health':'degraded'}]}

        monitor = Monitor(config, storage_adapters={'fixture':synthetic})
        with TestClient(create_app(config, monitor=monitor), base_url=ORIGIN) as client:
            page, errors = open_api_page(browser, client)
            expect(page.locator('.attention-panel')).to_be_visible()
            page.locator('[data-add-machine]').click()
            page.locator('[name=hardware_kind]').select_option('storage')
            page.locator('[name=storage_name]').fill('Synthetic NAS')
            page.locator('[name=resource_user]').select_option('shared')
            page.locator('#machine-save').click()
            expect(page.locator('#page-heading')).to_have_text('Synthetic NAS')
            expect(page.locator('.page-title .status')).to_have_text('待接入采集')
            expect(page.locator('.machine-assignees')).to_have_text('共享')
            expect(page.locator('.metric').first).to_contain_text('—')

            page.locator('[data-configure-machine]').click()
            page.locator('[name=storage_kind]').select_option('storage_cluster')
            page.locator('[name=adapter]').select_option('fixture')
            page.locator('#machine-save').click()
            expect(page.locator('.metric').first).to_contain_text('3.0 TiB / 8.0 TiB')
            expect(page.get_by_text('Logical pool', exact=True)).to_be_visible()
            expect(page.get_by_text('Synthetic member · data', exact=True)).to_be_visible()

            page.locator('#rail-nav [data-overview]').click()
            page.locator('.attention-panel [data-event]').press('Enter')
            expect(page.locator('#alert-detail')).to_contain_text('Synthetic NAS')
            expect(page.locator('#alert-detail')).to_contain_text('Z')
            page.locator('#alert-detail [data-host]').click()
            expect(page.locator('#page-heading')).to_contain_text('Synthetic NAS')
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors, errors
            page.set_viewport_size({'width':1440,'height':1000})
            check_groups(page,client)
            assert not errors, errors
            page.close()


def check_groups(page, client):
    owner = client.post('/api/people',json={'name':'Synthetic owner'}).json()['id']
    page.locator('#rail-nav [data-workspace-manage]').click()
    expect(page.locator('#manage-tab-room')).to_have_attribute('aria-selected','true')

    def add_room(name, person=''):
        page.locator('#manage-tab-panel [data-edit-group=room]:not([data-edit-id])').click()
        page.locator('#group-form [name=group_name]').fill(name)
        if person:
            page.locator('#group-form [name=person]').select_option(person)
        page.locator('#group-save').click()
        expect(page.locator('#manage-tab-panel').get_by_text(name,exact=True)).to_be_visible()

    # Allow the next poll to pick up the test directory entry before opening the editor.
    page.wait_for_function('state.snapshot.people.some(person => person.name === "Synthetic owner")')
    add_room('East Room',str(owner))
    add_room('West Room')

    snapshot = client.get('/api/snapshot').json()
    rooms = {room['name']:room['id'] for room in snapshot['groups']['rooms']}
    storage = snapshot['storage'][0]['id']
    for resource,room in ((storage,'East Room'),('east-cpu','East Room'),('west-cpu','West Room')):
        client.put(f'/api/resources/{resource}/room',json={'room_id':rooms[room]}).raise_for_status()
    page.wait_for_function('state.snapshot.groups.rooms[0].members.length === 2')
    page.locator('#manage-tab-room').press('ArrowRight')
    expect(page.locator('#manage-tab-cluster')).to_be_focused()
    page.locator('#manage-tab-panel [data-edit-group=cluster]').click()
    page.locator('#group-form [name=group_name]').fill('Across Rooms')
    page.locator('#group-form [name=person]').select_option('shared')
    page.locator('#group-form [name=member_search]').fill('Synthetic NAS')
    page.locator(f'#group-member-options [value="{storage}"]').check()
    page.locator('#group-form [name=member_search]').fill('')
    page.locator('#group-member-options [value=west-cpu]').check()
    page.locator('#group-member-options [value=unplaced-cpu]').check()
    page.locator('#group-save').click()
    expect(page.locator('#manage-tab-panel').get_by_text('Across Rooms',exact=True)).to_be_visible()
    page.locator('#rail-nav [data-overview]').click()
    expect(page.locator('#overview-tab-room')).to_have_attribute('aria-selected','true')
    expect(page.locator('.overview-metrics .metric')).to_have_count(3)
    expect(page.locator('.overview-metrics')).not_to_contain_text('存储')
    expect(page.locator('.group-summary')).to_contain_text('3.0 TiB / 8.0 TiB')
    assert page.locator('.overview-metrics').bounding_box()['y'] < page.locator('.attention-panel').bounding_box()['y']
    assert page.locator('.attention-panel').bounding_box()['y'] < page.locator('#overview-tab-room').bounding_box()['y']
    expect(page.locator('.attention-panel')).to_be_visible()
    expect(page.locator('.chart-panel')).to_be_visible()
    page.locator('#group-search').fill('East')
    expect(page.locator('.group-summary .resource-table tbody tr')).to_have_count(1)
    page.locator('.group-summary').get_by_role('button',name='East Room').click()
    expect(page.locator('#page-heading')).to_have_text('East Room')
    expect(page.locator('#host-rows')).to_contain_text('east-cpu')
    expect(page.locator('#host-rows')).to_contain_text('未入集群')
    page.locator('.resource-panel').get_by_role('button',name='Across Rooms').click()
    expect(page.locator('#page-heading')).to_have_text('Across Rooms')
    expect(page.locator('#breadcrumb')).to_contain_text('East Room')
    expect(page.locator('.resource-panel').get_by_role('button',name='West Room')).to_be_visible()
    expect(page.locator('.resource-panel')).to_contain_text('未设机房')
    expect(page.locator('#host-rows [data-machine-row]')).to_have_count(3)
    page.locator('[data-overview-metric=storage]').click()
    page.wait_for_function('state.history?.series?.length === 1 && state.history.keys[0] === "storage"')
    page.locator('#trend-chart').press('ArrowLeft')
    expect(page.locator('#chart-announcement')).to_contain_text('有效')
    page.locator('#chart-data > summary').click()
    expect(page.locator('#chart-data table')).to_contain_text('Across Rooms')
    page.locator('#focus-trends').click()
    page.locator('[data-metric=cpu]').click()
    expect(page.locator('.trend-stack .plot canvas')).to_have_count(2)
    page.locator('#exit-trends').click()
    expect(page.locator('#focus-trends')).to_be_focused()

    page.locator('#rail-nav [data-overview]').click()
    expect(page.locator('#group-search')).to_have_value('East')
    page.locator('#overview-tab-room').press('End')
    expect(page.locator('#overview-tab-machine')).to_be_focused()
    expect(page.locator('.chart-panel')).to_have_count(0)
    page.locator('#device-kind').select_option('storage')
    expect(page.locator('#host-rows [data-machine-row]')).to_have_count(1)
    page.locator('#device-kind').select_option('')
    page.locator(f'[data-sort-host="{storage}"]').press('ArrowUp')
    expect(page.locator(f'[data-sort-host="{storage}"]')).to_be_focused()
    expect(page.locator('#host-rows [data-machine-row]').nth(2)).to_have_attribute('data-machine-row',storage)
    assert client.get('/api/snapshot').json()['resource_order'][-2] == storage
    page.locator('#overview-tab-machine').press('ArrowLeft')
    expect(page.locator('#overview-tab-cluster')).to_be_focused()
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=OUT/'an164-cluster-desktop.png',full_page=True)
    for width in (390,320):
        page.set_viewport_size({'width':width,'height':840})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
    page.screenshot(path=OUT/'an164-cluster-320.png',full_page=True)


def check_layered_configuration(browser):
    field = 'idle_memory_tolerance_mib'
    hosts = tuple(Machine(id=id, expected_host_id=identity*32, mode='ssh', ssh_alias=id,
                          enabled=False, hardware_kind='gpu') for id,identity in (('east-gpu','a'),('west-gpu','b')))
    with TemporaryDirectory() as directory:
        config = Config(data_dir=Path(directory), machines=hosts)
        with TestClient(create_app(config), base_url=ORIGIN) as client:
            def seed(path, **body):
                return client.post(path, json=body).raise_for_status().json()['id']

            east = seed('/api/rooms', name='East Room', **{field:128})
            west = seed('/api/rooms', name='West Room')
            for machine,room in zip(hosts,(east,west)):
                client.put(f'/api/resources/{machine.id}/room',json={'room_id':room}).raise_for_status()
            across = seed('/api/clusters', name='Across Rooms', members=[host.id for host in hosts])
            local = seed('/api/clusters', name='East Workloads', members=['east-gpu'])
            page, errors = open_api_page(browser, client)
            page.set_viewport_size({'width':390,'height':844})
            deletes = []
            page.on('request', lambda request: deletes.append(request) if request.method == 'DELETE' else None)
            field_selector = f'[name={field}]'
            group_dialog = page.locator('#group-dialog')
            group_entry = page.locator('.page-title [data-edit-group]')
            global_dialog = page.locator('#global-configuration-dialog')
            machine_dialog = page.locator('#machine-dialog')

            page.get_by_role('button',name='全局配置').click()
            expect(global_dialog.locator(field_selector)).to_have_value('')
            expect(global_dialog.locator('#global-configuration-summary')).to_contain_text('256 MiB')
            global_dialog.locator(field_selector).fill('384')
            page.locator('#global-configuration-save').click()
            expect(global_dialog).to_be_hidden()

            page.locator('.group-summary').get_by_role('button',name='West Room',exact=True).click()
            group_entry.click()
            expect(group_dialog.locator('#group-configuration-summary')).to_contain_text('全局')
            expect(group_dialog.locator('#group-configuration-summary')).to_contain_text('384 MiB')
            expect(group_dialog.locator('[name=person]')).to_be_visible()
            page.locator('#group-cancel').click()
            page.locator('.resource-panel').get_by_role('button',name='Across Rooms').click()
            group_entry.click()
            expect(group_dialog.locator('#group-configuration-summary')).to_contain_text('按成员机器')
            rows = group_dialog.locator('#group-member-values li')
            expect(rows.filter(has_text='east-gpu')).to_contain_text('128 MiB')
            expect(rows.filter(has_text='east-gpu')).to_contain_text('East Room')
            expect(rows.filter(has_text='west-gpu')).to_contain_text('384 MiB')
            assert group_dialog.evaluate('dialog => dialog.scrollWidth <= dialog.clientWidth')
            group_dialog.screenshot(path=OUT/'an219-cross-room-zh.png')
            group_dialog.locator(field_selector).fill('512')
            page.locator('#group-save').click()
            expect(group_dialog).to_be_hidden()
            assert client.get('/api/snapshot').json()['groups']['clusters'][0][field] == 512
            client.put(f'/api/clusters/{local}',json={'name':'East Workloads','members':['east-gpu'],field:64}).raise_for_status()
            page.wait_for_function("state.snapshot.machines.find(node => node.id === 'east-gpu').idle_memory_configuration.cluster_conflict")
            page.locator('#host-rows [data-host=east-gpu]').first.click()
            page.locator('#locale-select').select_option('en')
            expect(page.locator('.page-title [data-remove-machine], .page-title [data-edit-assignees]')).to_have_count(0)
            page.get_by_role('button',name='Configure',exact=True).click()
            expect(machine_dialog.get_by_role('button',name='Edit assignees')).to_be_visible()
            expect(machine_dialog.locator('[name=room_id]')).to_have_value(east)
            expect(machine_dialog.locator('#machine-configuration-conflict')).to_contain_text('conflicting')
            expect(machine_dialog.locator('#machine-configuration-summary')).to_contain_text('128 MiB')
            machine_dialog.locator('[name=configuration_cluster_id]').select_option(across)
            page.locator('#machine-save').click()
            expect(machine_dialog).to_be_hidden()
            page.get_by_role('button',name='Configure',exact=True).click()
            expect(machine_dialog.locator('#machine-configuration-conflict')).to_be_hidden()
            expect(machine_dialog.locator('#machine-configuration-summary')).to_contain_text('512 MiB')
            expect(machine_dialog.locator('#machine-configuration-summary')).to_contain_text('Across Rooms')
            machine_dialog.locator(field_selector).fill('0')
            page.locator('#machine-save').click()
            page.get_by_role('button',name='Configure',exact=True).click()
            expect(machine_dialog.locator('#machine-configuration-summary')).to_contain_text('Local override')
            expect(machine_dialog.locator(field_selector)).to_have_value('0')
            machine_dialog.locator(field_selector).clear()
            page.locator('#machine-save').click()
            page.get_by_role('button',name='Configure',exact=True).click()
            expect(machine_dialog.locator('#machine-configuration-summary')).to_contain_text('512 MiB')
            assert machine_dialog.evaluate('dialog => dialog.scrollWidth <= dialog.clientWidth')
            page.locator('[data-remove-machine]').click()
            expect(page.locator('#remove-dialog')).to_be_visible()
            assert not deletes
            page.locator('#remove-cancel').click()
            expect(machine_dialog).to_be_visible()
            page.locator('#machine-cancel').click()
            page.locator(f'.device-group-links [data-group-id="{across}"]').click()
            group_entry.click()
            page.locator('#group-remove').click()
            expect(group_dialog.locator('#group-delete-preview')).to_contain_text('east-gpu')
            expect(group_dialog.get_by_role('button',name='Confirm removal')).to_be_visible()
            assert not deletes
            page.locator('#group-cancel').click()
            assert not deletes and not errors, errors
            page.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser')
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.browser)
        check_overview_power(browser)
        check_machine_sources(browser)
        check_resources(browser)
        check_layered_configuration(browser)
        browser.close()
    print('PASS: three overview cards, deduplicated current and rated GPU power, verified machine and container source views, independent coverage, storage enrollment, synthetic capacity, persisted alerts, room/cluster management and navigation, '
          '24-hour chart samples and coverage, keyboard tabs and sorting, filters, narrow layout, and localized layered configuration with explicit deletion confirmation')
