"""Synthetic browser checks. No server, collector, SSH, or real node is used.
Run: .venv/bin/python tools/browser_smoke.py [--browser /path/to/chromium]
Requires: pip install playwright; python -m playwright install chromium
"""
import argparse
import copy
import json
from pathlib import Path
import time
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts"
OUT.mkdir(exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument("--browser")
args = parser.parse_args()
gpu = dict(uuid="GPU-synthetic-01", index=0, name="NVIDIA Synthetic GPU", bus_id="0000:01:00.0",
           state="occupied", utilization_percent=76, memory_used_mib=24576, memory_total_mib=81920,
           temperature_c=62, power_w=285, power_limit_w=400, power_kind="average",
           process_visibility="complete", processes=[dict(pid=120, uid=1000, user="demo-user",
           name="training.py", used_memory_mib=24576, workload=dict(kind="docker", container_id="synthetic123"))])
metrics = dict(gpus=[gpu], gpu_percent=76, gpu_power_w=285, cpu_percent=42, memory_percent=38,
               cpu_count=64, load_average=[12, 10, 8], memory=dict(total_bytes=128*1024**3,
               used_bytes=48*1024**3, available_bytes=80*1024**3), root_disk=dict(available_bytes=500*1024**3),
               uptime_seconds=123456, driver_version="synthetic-580")
def node(i, status="normal"):
    return dict(id=f"demo-{i}", name=["训练节点 Alpha", "推理节点 Beta", "离线节点 Gamma"][i-1],
                address=f"demo-{i}.invalid", status=status, metrics=copy.deepcopy(metrics) if status=="normal" else None,
                reason="连接超时 · 合成离线样本" if status=="offline" else "", warnings=[], devices=[gpu],
                require_gpu=True, expected_gpu_count=1, scope="host", observed_at=int(time.time()*1000),
                last_success_at=int(time.time()*1000), enabled=True, interval_seconds=5,
                mode="ssh", checks=["gpu", "processes", "cpu", "memory", "system"],
                ssh_connect_timeout_seconds=5)
machines = [node(1), node(2), node(3, "offline")]
mode = "normal"
mutations = []
def handle(route):
    global machines
    path = route.request.url.split("http://wattline.test", 1)[1].split("?")[0]
    if path == "/":
        return route.fulfill(path=str(ROOT / "wattline/static/index.html"), content_type="text/html")
    if path.startswith("/static/"):
        return route.fulfill(path=str(ROOT / "wattline" / path.lstrip("/")),
                             content_type="text/css" if path.endswith(".css") else "text/javascript")
    if path == "/api/snapshot":
        if mode == "loading":
            return route.abort()
        if mode == "error":
            return route.fulfill(status=503, json={"detail": "synthetic failure"})
        now = int(time.time()*1000)
        return route.fulfill(json=dict(server_time=now, stale_ms=600000, period_ms=5000,
            default_ssh_connect_timeout_seconds=5, machine_history_hours=168, registry_loaded=True,
            history_writable=True, archive_ok=True, machines=[] if mode=="empty" else machines))
    if path == "/api/history":
        now = int(time.time()*1000)
        from urllib.parse import parse_qs, urlsplit
        q = parse_qs(urlsplit(route.request.url).query)
        keys = [q["metric"][0]] if "metric" in q else ["gpu", "cpu"]
        hours = int(q.get("hours", [24])[0])
        return route.fulfill(json=dict(keys=keys, to=now, **{"from":now-hours*3600000},
            points=[dict(time=now-hours*3600000+i*hours*360000, values=[30+(i*7)%50]*len(keys)) for i in range(11)]))
    mutations.append((route.request.method, path, route.request.post_data))
    if path == "/api/machines/order":
        order = json.loads(route.request.post_data)["machines"]
        machines = sorted(machines, key=lambda n: order.index(n["id"]))
        return route.fulfill(json={"machines":order})
    if path.endswith("/settings"):
        n = next(n for n in machines if n["id"] in path)
        n.update(json.loads(route.request.post_data))
        n["name"] = n["alias"] or n["name"]
        return route.fulfill(json=n)
    return route.fulfill(status=422, json={"detail":"合成验证错误：地址不可达"})

def check_dialog_locales(browser):
    """Exercise real submissions, hold busy states, then switch without navigation."""
    global machines
    results = []
    labels = {
        'zh-CN': {'save':'保存', 'confirm':'确认移除', 'add_busy':'验证连接…',
                  'settings_busy':'保存中…', 'remove_busy':'移除中…'},
        'en': {'save':'Save', 'confirm':'Confirm removal', 'add_busy':'Verifying connection…',
               'settings_busy':'Saving…', 'remove_busy':'Removing…'},
    }
    for source, target in [('zh-CN','en'), ('en','zh-CN')]:
        for action in ['add','settings','remove']:
            for success in [True, False]:
                machines = [node(1),node(2)]
                test_page = browser.new_page(viewport={'width':1440,'height':1100})
                page_errors, pending = [], []
                test_page.on('pageerror', lambda error: page_errors.append(str(error)))
                test_page.route('**/*', handle)
                test_page.route('**/api/machines**', lambda route: pending.append(route))
                test_page.goto('http://wattline.test')
                expect(test_page.locator('#host-rows tr')).to_have_count(2)
                test_page.evaluate('window.dialogTestDocument = {}')
                document_handle = test_page.evaluate_handle('window.dialogTestDocument')
                test_page.locator('#locale-select').select_option(source)

                def open_dialog(machine_id='demo-1'):
                    if action == 'add':
                        test_page.locator('[data-overview]').first.click()
                        test_page.locator('[data-add-machine]').click()
                    else:
                        test_page.locator('#rail-nav [data-host="'+machine_id+'"]').click()
                        test_page.locator('[data-configure-machine]' if action == 'settings'
                                          else '[data-remove-machine]').click()

                open_dialog()
                button = test_page.locator('#remove-confirm' if action == 'remove' else '#machine-save')
                idle_key = 'confirm' if action == 'remove' else 'save'
                expect(button).to_have_text(labels[source][idle_key])
                expect(button).to_have_accessible_name(labels[source][idle_key])
                if action == 'add':
                    test_page.locator('[name="host"]').fill('synthetic.invalid')
                if action != 'remove':
                    test_page.locator('[name="alias"]').fill('Dialog matrix alias')
                button.click()
                expect(button).to_have_text(labels[source][action+'_busy'])
                expect(button).to_have_accessible_name(labels[source][action+'_busy'])
                expect(button).to_be_disabled()
                # Reapplying localization must retain the active operation's busy label.
                test_page.evaluate('WattlineI18n.apply()')
                expect(button).to_have_text(labels[source][action+'_busy'])
                assert len(pending) == 1
                route = pending.pop()
                if not success:
                    route.fulfill(status=422,json={'detail':'synthetic mutation failure'})
                    expect(test_page.locator('#remove-error' if action == 'remove' else '#machine-error')).to_be_visible()
                elif action == 'remove':
                    machines = [machine for machine in machines if machine['id'] != 'demo-1']
                    route.fulfill(json={'removed':True,'cleanup_pending':False})
                else:
                    saved = node(3) if action == 'add' else machines[0]
                    saved.update(route.request.post_data_json)
                    saved['name'] = saved['alias']
                    if action == 'add':
                        machines.append(saved)
                    route.fulfill(json=saved)
                expect(button).to_be_enabled()
                expect(button).to_have_text(labels[source][idle_key])
                if success:
                    expect(test_page.locator('#remove-dialog' if action == 'remove' else '#machine-dialog')).not_to_be_visible()
                else:
                    expect(button).to_have_accessible_name(labels[source][idle_key])
                    test_page.keyboard.press('Escape')
                test_page.locator('#locale-select').select_option(target)
                open_dialog('demo-2' if action == 'remove' and success else 'demo-1')
                expect(button).to_have_text(labels[target][idle_key])
                expect(button).to_have_accessible_name(labels[target][idle_key])
                expect(button).to_be_enabled()
                assert test_page.evaluate('(original) => window.dialogTestDocument === original',document_handle)
                assert not page_errors, page_errors
                result = {'source':source,'target':target,'action':action,'success':success,
                          'label':button.inner_text(),'no_reload':True,'page_errors':page_errors}
                results.append(result)
                if action in ['add','remove'] and not success:
                    test_page.screenshot(path=str(OUT/f'dialog-{action}-{source}-to-{target}.png'))
                test_page.close()
    return results

def check_unlimited_container(browser):
    """A container without a cgroup limit shows used GiB once, never a fabricated percent or zero."""
    global machines
    sample = node(1)
    sample.update(scope='container', checks=['cpu', 'memory'])
    sample['metrics']['memory'] = {'total_bytes': None, 'used_bytes': 1024**3, 'available_bytes': None}
    sample['metrics']['memory_percent'] = None
    machines = [sample]
    test_page = browser.new_page(viewport={'width':1440,'height':1100})
    page_errors = []
    test_page.on('pageerror', lambda error: page_errors.append(str(error)))
    test_page.route('**/*', handle)
    test_page.goto('http://wattline.test')
    expect(test_page.locator('#host-rows tr')).to_have_count(1)
    cell = test_page.locator('#host-rows tr [data-label="内存"]')
    expect(cell.locator('[data-value="demo-1-memory"]')).to_have_text('1.0 GiB')
    expect(cell.locator('.memory-used')).to_be_hidden()
    expect(cell).not_to_contain_text('0.0 GiB')
    used_text = cell.locator('[data-value="demo-1-memory"]').inner_text()
    test_page.get_by_role('button', name='查看 训练节点 Alpha', exact=True).click()
    expect(test_page.locator('.metric [data-value="card-memory"]')).to_have_text('1.0')
    expect(test_page.locator('.metric [data-value="memory-detail"]')).to_contain_text('无 cgroup 内存上限')
    expect(test_page.locator('.metric [data-value="memory-detail"]')).not_to_contain_text('0.0 GiB')
    test_page.screenshot(path=str(OUT/'container-unlimited.png'), full_page=True)
    assert not page_errors, page_errors
    test_page.close()
    return {'used_text':used_text, 'duplicate_hidden':True, 'page_errors':page_errors}

def check_focus_layout(browser):
    """AN-48 synthetic acceptance: navigation, metric comparisons, hardware and modal focus."""
    global machines, mode
    machines = [node(1), node(2), node(3, 'offline')]
    idle = copy.deepcopy(gpu)
    idle.update(uuid='GPU-synthetic-02', index=1, state='free', processes=[],
                utilization_percent=0, memory_used_mib=0, power_w=35, temperature_c=30)
    machines[0]['devices'] = [copy.deepcopy(gpu), idle]
    machines[0]['metrics']['gpus'].append(idle)
    page = browser.new_page(viewport={'width':1440,'height':1100})
    errors, requests = [], []
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda request:requests.append(request.url) if '/api/history?' in request.url else None)
    page.route('**/*',handle)
    page.goto('http://wattline.test')
    expect(page.locator('#host-rows tr')).to_have_count(3)
    toggle_rail = page.locator('#rail-toggle')
    toggle_rail.press('Enter')
    expect(toggle_rail).to_have_attribute('aria-expanded','false')
    rail = page.locator('#rail-nav [data-host="demo-1"]')
    expect(rail).to_have_accessible_name('训练节点 Alpha · 正常')
    assert rail.locator('strong').is_hidden()
    assert rail.locator('.machine-icon').is_hidden()
    assert rail.locator('.status-dot').is_visible()
    rail.press('Enter')
    expect(page.locator('#rail-nav [data-host="demo-1"]')).to_have_attribute('aria-current','page')
    # CPU/system facts remain on the machine page and trends span the whole detail row.
    expect(page.locator('[data-value="card-cpu"]')).to_have_text('42')
    expect(page.locator('[data-value="cores"]')).to_contain_text('64')
    expect(page.locator('[data-value="load"]')).to_have_text('12.00')
    expect(page.locator('[data-value="disk"]')).to_contain_text('500.0')
    assert page.locator('.chart-panel').bounding_box()['width'] == page.locator('.hardware-panel').bounding_box()['width']
    assert page.locator('.hardware-panel').bounding_box()['y'] > page.locator('.chart-panel').bounding_box()['y']
    expect(page.locator('.hardware-table tbody tr')).to_have_count(2)
    expect(page.locator('.hardware-table tbody tr').first).to_contain_text('PID 120')
    expect(page.locator('.hardware-table tbody tr').first).to_contain_text('demo-user')
    expect(page.locator('.hardware-table tbody tr').nth(1)).to_contain_text('未发现 GPU 进程')
    page.screenshot(path=str(OUT/'an48-desktop.png'),full_page=True)
    for width in [320,390,640,731,975,1440]:
        page.set_viewport_size({'width':width,'height':1100})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), ('compact',width)
        assert toggle_rail.is_visible()
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(OUT/'an48-narrow.png'),full_page=True)
    button = page.get_by_role('button',name='查看 GPU 1',exact=True)
    button.press('Enter')
    expect(page.locator('#gpu-dialog')).to_be_visible()
    expect(page.locator('#gpu-dialog')).to_have_accessible_name('GPU 1 设备信息')
    expect(page.locator('#gpu-dialog .gpu-info')).to_contain_text('GPU-synthetic-02')
    expect(page.locator('#gpu-dialog')).to_contain_text('未发现 GPU 进程')
    page.screenshot(path=str(OUT/'an48-dialog-narrow.png'))
    # A snapshot shape change is deferred while the invoker must stay attached.
    page.evaluate("state.snapshot.machines[0].reason='synthetic update during inspection'; renderPage()")
    assert button.is_visible()
    page.keyboard.press('Escape')
    expect(button).to_be_focused()
    page.evaluate('renderPage(); paint()')
    expect(page.get_by_role('button',name='查看 GPU 1',exact=True)).to_be_focused()
    page.locator('#rail-toggle').press('Space')
    expect(page.locator('#rail-toggle')).to_have_attribute('aria-expanded','true')
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
    # Inspect a device without changing trends, then explicitly enter per-device trends.
    page.get_by_role('button',name='查看 GPU 0',exact=True).click()
    expect(page.locator('#gpu-dialog .process-table')).to_contain_text('Docker')
    page.get_by_role('button',name='查看此 GPU 趋势',exact=True).click()
    expect(page.locator('[data-metric="gpu"]')).to_have_attribute('aria-pressed','true')
    # Inspecting another device must not overwrite the selected device's metric card.
    page.get_by_role('button',name='查看 GPU 1',exact=True).click()
    expect(page.locator('[data-value="selected-gpu-memory"]')).to_have_text('24.0 / 80.0 GiB')
    expect(page.locator('#gpu-dialog [data-value="gpu-memory"]')).to_have_text('0.0 / 80.0 GiB')
    page.get_by_role('button',name='关闭详情',exact=True).click()
    expect(page.get_by_role('button',name='查看 GPU 1',exact=True)).to_be_focused()
    page.locator('[data-metric="power"]').click()
    page.set_viewport_size({'width':1440,'height':1100})
    page.locator('#focus-trends').press('Enter')
    expect(page.locator('#exit-trends')).to_be_focused()
    expect(page.locator('.trend-stack canvas')).to_have_count(1)
    page.screenshot(path=str(OUT/'an48-single-power.png'),full_page=True)
    page.locator('[data-metric="gpu"]').press('Space')
    expect(page.locator('.trend-stack canvas')).to_have_count(2)
    for summary in page.locator('.chart-summary').all():
        expect(summary).to_contain_text('11 个有效时段')
    expect(page.locator('[data-range="24"]')).to_have_attribute('aria-pressed','true')
    assert page.evaluate('state.focusMetrics.join(",")') == 'power,gpu'
    assert page.evaluate('Object.values(state.histories).every(h => h.to-h.from === 24*3600000)')
    assert any('gpu=GPU-synthetic-01' in url and 'metric=power' in url for url in requests)
    # Every plot has its own backing size, announcement and tooltip after resizing.
    resized = []
    for width in [1440,975,731,640,390,320]:
        page.set_viewport_size({'width':width,'height':1100})
        page.wait_for_function("""() => [...document.querySelectorAll('.trend-stack canvas')].every(c =>
          Math.abs(c.width-c.clientWidth*devicePixelRatio)<=1 && Math.abs(c.height-c.clientHeight*devicePixelRatio)<=1)""")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), ('focus',width)
        bounds = [canvas.bounding_box() for canvas in page.locator('.trend-stack canvas').all()]
        assert bounds[0]['y']+bounds[0]['height'] <= bounds[1]['y']
        resized.append({'width':width,'plots':len(bounds),'overflow':False})
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(OUT/'an48-two-charts-narrow.png'),full_page=True)
    page.set_viewport_size({'width':1440,'height':1100})
    page.screenshot(path=str(OUT/'an48-power-utilization-24h.png'),full_page=True)
    for canvas, label in zip(page.locator('.trend-stack canvas').all(),['GPU 功耗','GPU 利用率']):
        canvas.press('ArrowLeft')
        suffix = canvas.get_attribute('id').removeprefix('trend-chart')
        expect(page.locator('#chart-announcement'+suffix)).to_contain_text(label)
        expect(page.locator('#chart-tip'+suffix)).to_be_visible()
        canvas.press('Escape')  # Clear the point without leaving focus mode.
        expect(page.locator('#exit-trends')).to_be_visible()
    page.locator('#chart-data summary').click()
    expect(page.locator('#chart-data tbody tr')).to_have_count(11)
    expect(page.locator('#chart-data table')).to_contain_text('50.0 W')
    page.locator('#chart-data summary').click()
    # Selection cannot become empty and can include every supported metric.
    page.locator('[data-metric="gpu"]').click()
    page.locator('[data-metric="power"]').click()
    expect(page.locator('.trend-stack canvas')).to_have_count(1)
    page.locator('[data-metric="vram"]').click()
    page.locator('[data-metric="temp"]').click()
    expect(page.locator('.trend-stack canvas')).to_have_count(3)
    page.locator('[data-range="168"]').click()
    expect(page.locator('#chart-summary')).to_contain_text('11 个有效时段')
    page.wait_for_function('Object.values(state.histories).length === 3 && Object.values(state.histories).every(h => h.to-h.from === 168*3600000)')
    # Independent failure: one chart errors without losing another chart's samples.
    def fail_temperature(route):
        if 'metric=temp' in route.request.url:
            return route.fulfill(status=503,json={'detail':'synthetic chart failure'})
        handle(route)
    page.route('**/api/history?**',fail_temperature)
    page.locator('[data-range="72"]').click()
    expect(page.locator('#chart-error-temp')).to_be_visible()
    expect(page.locator('#chart-summary')).to_contain_text('11 个有效时段')
    page.unroute('**/api/history?**',fail_temperature)
    page.evaluate('refresh()')
    expect(page.locator('#chart-error-temp')).to_be_hidden()
    # Hold obsolete six-hour requests, switch to 24h, then release old responses.
    held = []
    def hold_old(route):
        if 'hours=6&' in route.request.url:
            held.append(route)
        else:
            handle(route)
    page.route('**/api/history?**',hold_old)
    page.locator('[data-range="6"]').click()
    page.wait_for_function('state.hours === 6')
    page.locator('[data-range="24"]').click()
    expect(page.locator('#chart-summary')).to_contain_text('11 个有效时段')
    assert held
    for route in held:
        handle(route)
    page.wait_for_function('Object.values(state.histories).length === 3 && Object.values(state.histories).every(h => h.to-h.from === 24*3600000)')
    page.unroute('**/api/history?**',hold_old)
    page.locator('#exit-trends').press('Escape')
    expect(page.locator('#focus-trends')).to_be_focused()
    expect(page.locator('.hardware-table')).to_be_visible()
    page.locator('#focus-trends').click()
    page.locator('#exit-trends').click()
    expect(page.locator('#focus-trends')).to_be_focused()
    # Overview also supports a stack and localized controls.
    page.locator('#rail-nav [data-overview]').click()
    page.locator('#locale-select').select_option('en')
    page.locator('#focus-trends').click()
    page.locator('[data-metric="cpu"]').click()
    expect(page.locator('.chart-title').first).to_contain_text('GPU utilization')
    expect(page.locator('.chart-title').nth(1)).to_contain_text('CPU usage')
    page.locator('#exit-trends').click()
    page.locator('#rail-nav [data-host="demo-3"]').click()
    expect(page.locator('.hardware-table')).to_contain_text('No fresh sample')
    expect(page.locator('[data-value="GPU-synthetic-01-memory"]')).to_have_text('—')
    # Unknown/partial visibility and empty inventory keep precise empty states.
    page.locator('#rail-nav [data-host="demo-1"]').click()
    page.evaluate("state.snapshot.machines[0].metrics.gpus[1].process_visibility='partial'; renderPage(); paint()")
    expect(page.locator('.hardware-table tbody tr').nth(1)).to_contain_text('No verifiable GPU process records available')
    page.evaluate("state.snapshot.machines[0].devices=[]; state.snapshot.machines[0].metrics.gpus=[]; renderPage(); paint()")
    expect(page.locator('.hardware-panel')).to_contain_text('No verified devices yet')
    page.evaluate("state.snapshot.machines[0].checks=['cpu','memory']; state.snapshot.machines[0].require_gpu=false; renderPage(); paint()")
    expect(page.locator('.hardware-panel')).to_contain_text('Monitored as a CPU-only machine')
    expect(page.locator('[data-value="card-cpu"]')).to_have_text('42')
    assert not errors, errors
    page.close()
    # Persistence and unavailable storage are exercised separately.
    saved = browser.new_context(viewport={'width':390,'height':844})
    persistent = saved.new_page()
    persistent.route('**/*',handle)
    persistent.goto('http://wattline.test')
    persistent.locator('#rail-toggle').click()
    persistent.reload()
    expect(persistent.locator('#rail-toggle')).to_have_attribute('aria-expanded','false')
    saved.close()
    blocked = browser.new_page(viewport={'width':320,'height':844})
    blocked.route('**/*',handle)
    blocked.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw Error('blocked')}})")
    blocked.goto('http://wattline.test')
    blocked.locator('#rail-toggle').press('Space')
    expect(blocked.locator('#rail-toggle')).to_have_attribute('aria-expanded','false')
    blocked.locator('#rail-toggle').press('Space')
    expect(blocked.locator('#rail-toggle')).to_have_attribute('aria-expanded','true')
    blocked.close()
    return {'result':'PASS','resized':resized,'held_obsolete_requests':len(held),'page_errors':errors,
            'screenshots':['an48-desktop.png','an48-narrow.png','an48-dialog-narrow.png','an48-power-utilization-24h.png','an48-single-power.png','an48-two-charts-narrow.png']}

with sync_playwright() as p:
    browser = p.chromium.launch(**({"executable_path":args.browser} if args.browser else {}))
    page = browser.new_page(viewport={"width":1440,"height":1100}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/*", handle)
    page.goto("http://wattline.test")
    expect(page.locator("#host-rows tr")).to_have_count(3)
    expect(page.locator("#chart-summary")).to_contain_text("11 个有效时段")
    alpha_memory = page.locator('#host-rows tr[data-machine-row="demo-1"] [data-label="内存"]')
    expect(alpha_memory).to_contain_text("38%")
    expect(alpha_memory.locator(".memory-used")).to_contain_text("48.0 GiB 已用")
    offline_memory = page.locator('#host-rows tr[data-machine-row="demo-3"] [data-label="内存"]')
    expect(offline_memory.locator(".memory-used")).to_be_hidden()
    expect(offline_memory).not_to_contain_text("0.0 GiB")
    # A tile can clip its number even when the document fits the viewport.
    layout_widths = [320, 390, 514, 515, 516, 640, 729, 730, 731, 732,
                     759, 760, 761, 974, 975, 976, 977, 1024, 1440]
    page.evaluate("""() => {
      for (const host of state.snapshot.machines) {
        if (host.metrics) {
          host.metrics.gpu_power_w = 1234;
          for (const gpu of host.metrics.gpus) gpu.power_w = 1234;
        }
      }
      paint();
    }""")
    expect(page.locator('.metric [data-value="watts"]')).to_have_text("2,468")
    layout_results = []
    for width in layout_widths:
        page.set_viewport_size({"width":width,"height":1100})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
        tiles = page.locator(".metric").evaluate_all("""tiles => tiles.map(tile => {
          const card = tile.getBoundingClientRect();
          const value = tile.querySelector('strong .value');
          const range = document.createRange();
          range.selectNodeContents(value);
          const text = range.getBoundingClientRect();
          return {value: value.textContent, left: text.left, right: text.right,
                  cardLeft: card.left, cardRight: card.right,
                  fits: text.left >= card.left && text.right <= card.right};
        })""")
        assert len(tiles) == 4 and all(tile["fits"] for tile in tiles), (width, tiles)
        layout_results.append({"width":width, "values_fit":True})
        if width in [731, 760]:
            page.locator(".metrics").screenshot(path=str(OUT/f"metrics-{width}.png"))
    page.set_viewport_size({"width":1440,"height":1100})
    page.evaluate("delete state.snapshot.machines[0].metrics.memory.used_bytes; paint()")
    expect(alpha_memory).to_contain_text("38%")
    expect(alpha_memory.locator(".memory-used")).to_be_hidden()
    expect(alpha_memory).not_to_contain_text("0.0 GiB")
    page.reload()
    expect(page.locator("#host-rows tr")).to_have_count(3)
    expect(alpha_memory.locator(".memory-used")).to_contain_text("48.0 GiB 已用")
    page.screenshot(path=str(OUT/"desktop.png"), full_page=True)
    page.get_by_role("button", name="需关注", exact=True).click()
    expect(page.locator("#host-rows")).to_contain_text("没有符合条件")
    page.get_by_role("button", name="全部", exact=True).click()
    page.get_by_role("searchbox").fill("Alpha")
    expect(page.locator("#host-rows tr")).to_have_count(1)
    page.get_by_role("searchbox").fill("")
    page.get_by_role("button", name="排序 训练节点 Alpha", exact=True).press("ArrowDown")
    expect(page.locator("#host-rows tr").first).to_have_attribute("data-machine-row", "demo-2")
    page.get_by_role("button", name="查看 训练节点 Alpha", exact=True).click()
    expect(page.get_by_role("heading", name="硬件与 GPU 进程")).to_be_visible()
    expect(page.locator(".hardware-table")).to_contain_text("demo-user")
    expect(page.locator('.metric [data-value="card-memory"]')).to_have_text("38")
    expect(page.locator('.metric [data-value="memory-detail"]')).to_have_text("48.0 GiB / 128.0 GiB 已用")
    page.get_by_role("button", name="查看 GPU 0", exact=True).click()
    expect(page.locator(".gpu-info")).to_contain_text("GPU-synthetic-01")
    expect(page.locator("#gpu-dialog .process-table")).to_contain_text("demo-user")
    page.get_by_role("button", name="查看此 GPU 趋势", exact=True).click()
    page.get_by_role("button", name="7 天", exact=True).click()
    expect(page.get_by_role("button", name="7 天", exact=True)).to_have_attribute("aria-pressed","true")
    expect(page.locator("#chart-summary")).to_contain_text("11 个有效时段")
    page.locator("#trend-chart").press("ArrowLeft")
    expect(page.locator("#chart-announcement")).to_contain_text("GPU 利用率")
    page.get_by_role("button", name="配置", exact=True).click()
    page.locator('[name="alias"]').fill("合成训练节点")
    page.get_by_role("button", name="保存", exact=True).click()
    expect(page.locator("#machine-dialog")).not_to_be_visible()
    expect(page.locator("#page-heading")).to_contain_text("合成训练节点")
    page.get_by_role("button", name="移除节点", exact=True).click()
    expect(page.locator("#remove-cancel")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.get_by_role("button", name="移除节点", exact=True)).to_be_focused()
    page.screenshot(path=str(OUT/"detail.png"), full_page=True)
    page.get_by_role("button", name="机器总览", exact=True).first.click()
    page.set_viewport_size({"width":390,"height":844})
    page.screenshot(path=str(OUT/"mobile.png"))
    page.locator(".machine-scroll").screenshot(path=str(OUT/"mobile-list.png"))
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    expect(page.locator('#host-rows tr').first.locator('[data-label="内存"]')).to_be_visible()
    expect(page.locator('#host-rows tr').first.locator('.memory-used')).to_contain_text("48.0 GiB 已用")
    page.get_by_role("button", name="新增机器", exact=True).click()
    page.locator('[name="host"]').fill("unreachable.invalid")
    page.get_by_role("button", name="保存", exact=True).click()
    expect(page.locator("#machine-error")).to_contain_text("合成验证错误")
    page.keyboard.press("Escape")
    # Rebuild the shape while focus is in a row, attention item, or rail.
    # These controls share data-host: global .first() would hide a focus jump.
    focus_results = []
    for width in [390, 731, 1440]:
        page.set_viewport_size({"width":width,"height":700})
        for selector in ['#host-rows [data-host="demo-2"]',
                         '#content .issue[data-host="demo-3"]',
                         '#rail-nav [data-host="demo-2"]']:
            control = page.locator(selector)
            control.scroll_into_view_if_needed()
            control.focus()
            expect(control).to_be_focused()
            # Assert an actual replacement occurred, not the no-op render path.
            previous = control.element_handle()
            page.evaluate("state.snapshot.machines[0].reason += 'changed'; renderPage(); paint()")
            assert previous.evaluate("el => !el.isConnected")
            expect(control).to_be_focused()
            assert control.evaluate("""el => {
              const r = el.getBoundingClientRect();
              return r.top >= 0 && r.bottom <= innerHeight &&
                     r.left >= 0 && r.right <= innerWidth;
            }"""), (width, selector)
            focus_results.append({"width":width, "selector":selector, "visible":True})
            if width == 390 and selector.startswith("#host-rows"):
                page.screenshot(path=str(OUT/"focus-row-390.png"))
    mode = "empty"
    page.reload()
    expect(page.locator("#host-rows")).to_contain_text("尚未添加机器")
    page.screenshot(path=str(OUT/"empty.png"), full_page=True)
    mode = "error"
    page.reload()
    expect(page.get_by_role("heading", name="暂时无法连接工作台")).to_be_visible()
    page.screenshot(path=str(OUT/"error.png"), full_page=True)
    mode = "normal"
    # Retain API routes until the screenshot: real pending fetch, no state injection.
    loading = browser.new_page(viewport={"width":390,"height":844})
    pending = []
    loading.route("**/*", handle)
    loading.route("**/api/**", lambda route: pending.append(route))
    loading.goto("http://wattline.test", wait_until="domcontentloaded")
    expect(loading.get_by_role("heading", name="正在连接工作台")).to_be_visible()
    loading.screenshot(path=str(OUT/"loading.png"), full_page=True)
    for route in pending:
        route.abort()
    loading.close()
    page.goto("http://wattline.test")
    for width in [320, 640, 1024]:
        page.set_viewport_size({"width":width,"height":900})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
    page.get_by_role("button", name="新增机器", exact=True).click()
    # Polling while a modal is open must preserve its invoker for native focus return.
    page.evaluate("renderPage(true)")
    page.keyboard.press("Escape")
    expect(page.get_by_role("button", name="新增机器", exact=True)).to_be_focused()
    assert not errors, errors
    assert any(path.endswith("/order") for _,path,_ in mutations)
    assert any(path.endswith("/settings") for _,path,_ in mutations)
    # English end-to-end: preference, current selection, dialogs and raw evidence.
    page.set_viewport_size({"width":1440,"height":1100})
    page.locator('#locale-select').select_option('en')
    expect(page.locator('html')).to_have_attribute('lang','en')
    expect(page.locator('#page-heading')).to_have_text('Compute at a glance')
    expect(page.locator('#chart-summary')).to_contain_text('11 valid periods')
    assert page.evaluate("localStorage.getItem('wattline.locale')") == 'en'
    page.get_by_role('searchbox').fill('Beta')
    page.locator('#locale-select').select_option('zh-CN')
    expect(page.get_by_role('searchbox')).to_have_value('Beta')
    page.locator('#locale-select').select_option('en')
    expect(page.locator('#host-rows tr')).to_have_count(1)
    page.get_by_role('searchbox').fill('')
    page.reload()
    expect(page.locator('html')).to_have_attribute('lang','en')
    expect(page.locator('#page-heading')).to_have_text('Compute at a glance')
    expect(page.locator('#host-rows tr[data-machine-row="demo-1"] [data-label="Memory"] .memory-used')).to_contain_text('48.0 GiB used')
    page.screenshot(path=str(OUT/'english-overview.png'), full_page=True)
    for width in layout_widths:
        page.set_viewport_size({"width":width,"height":1100})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), ('en',width)
        assert page.locator('.metric').evaluate_all('''tiles => tiles.every(tile => {
            const range=document.createRange(); range.selectNodeContents(tile.querySelector('strong .value'));
            const r=range.getBoundingClientRect(), card=tile.getBoundingClientRect();
            return r.left >= card.left && r.right <= card.right;
        })'''), ('en tiles',width)
    page.set_viewport_size({"width":390,"height":844})
    page.screenshot(path=str(OUT/'english-mobile.png'), full_page=True)
    page.get_by_role('button',name='Unavailable',exact=True).click()
    expect(page.locator('#host-rows tr')).to_have_count(1)
    page.get_by_role('button',name='All',exact=True).click()
    page.locator('#host-rows [data-sort-host="demo-2"]').press('ArrowDown')
    page.locator('#host-rows [data-host="demo-2"]').click()
    expect(page.get_by_role('heading',name='Hardware & GPU processes')).to_be_visible()
    expect(page.locator('.hardware-table')).to_contain_text('demo-user')
    expect(page.locator('.metric [data-value="memory-detail"]')).to_have_text('48.0 GiB / 128.0 GiB used')
    page.get_by_role('button',name='View GPU 0',exact=True).click()
    expect(page.locator('#gpu-dialog-title')).to_have_text('GPU 0 device information')
    expect(page.locator('#gpu-dialog .process-table')).to_contain_text('demo-user')
    page.get_by_role('button',name='View this GPU’s trends',exact=True).click()
    page.get_by_role('button',name='7 days',exact=True).click()
    expect(page.locator('#chart-summary')).to_contain_text('11 valid periods')
    page.locator('#trend-chart').press('ArrowLeft')
    expect(page.locator('#chart-announcement')).to_contain_text('GPU utilization')
    page.locator('#locale-select').select_option('zh-CN')
    expect(page.get_by_role('button',name='7 天',exact=True)).to_have_attribute('aria-pressed','true')
    page.locator('#locale-select').select_option('en')
    expect(page.get_by_role('button',name='7 days',exact=True)).to_have_attribute('aria-pressed','true')
    page.set_viewport_size({"width":1440,"height":1100})
    page.locator('#trend-chart').blur()
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(OUT/'english-gpu.png'), full_page=True)
    page.get_by_role('button',name='Configure',exact=True).click()
    page.locator('[name="alias"]').fill('English synthetic alias')
    # App validation is localized; failed validation retains the draft.
    for checkbox in page.locator('input[name="checks"]').all():
        checkbox.uncheck(force=True)
    page.get_by_role('button',name='Save',exact=True).click()
    expect(page.locator('#machine-error')).to_have_text('Select at least one check when monitoring is enabled.')
    expect(page.locator('[name="alias"]')).to_have_value('English synthetic alias')
    page.locator('input[name="checks"][value="cpu"]').check()
    page.get_by_role('button',name='Save',exact=True).click()
    expect(page.locator('#machine-dialog')).not_to_be_visible()
    page.get_by_role('button',name='Remove node',exact=True).click()
    expect(page.locator('#remove-description')).to_contain_text('This cannot be undone.')
    page.get_by_role('button',name='Confirm removal',exact=True).click()
    expect(page.locator('#remove-error')).to_contain_text('Could not remove.')
    expect(page.locator('#remove-error')).to_contain_text('合成验证错误')
    page.keyboard.press('Escape')
    page.get_by_role('button',name='Overview',exact=True).first.click()
    page.get_by_role('button',name='Add machine',exact=True).click()
    page.locator('[name="host"]').fill('unreachable.invalid')
    page.get_by_role('button',name='Save',exact=True).click()
    expect(page.locator('#machine-error')).to_contain_text('Could not save.')
    page.screenshot(path=str(OUT/'english-validation.png'), full_page=True)
    page.keyboard.press('Escape')
    mode = 'empty'
    page.reload()
    expect(page.locator('#host-rows')).to_contain_text('No machines yet.')
    mode = 'error'
    page.reload()
    expect(page.get_by_role('heading',name='Workbench unavailable')).to_be_visible()
    mode = 'normal'
    page.evaluate("localStorage.setItem('wattline.locale','unsupported')")
    page.reload()
    expect(page.locator('html')).to_have_attribute('lang','zh-CN')
    expect(page.locator('#page-heading')).to_have_text('算力，一目了然')
    # A separate page with blocked storage remains usable, including session switching.
    blocked = browser.new_page()
    blocked.route('**/*',handle)
    blocked.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})")
    blocked.goto('http://wattline.test')
    expect(blocked.locator('#page-heading')).to_have_text('算力，一目了然')
    blocked.locator('#locale-select').select_option('en')
    expect(blocked.locator('#page-heading')).to_have_text('Compute at a glance')
    blocked.close()
    assert not errors, errors

    page.close()
    dialog_locales = check_dialog_locales(browser)
    unlimited_container = check_unlimited_container(browser)
    focus_layout = check_focus_layout(browser)
    print(json.dumps({"focus_layout":focus_layout,"result":"PASS", "browser":browser.version, "page_errors":errors,
                      "mutations":len(mutations), "screenshots":25, "locales":["zh-CN","en"], "dialog_locales":dialog_locales,
                      "metric_layouts":layout_results, "focus_refreshes":focus_results,
                      "unlimited_container":unlimited_container}, ensure_ascii=False))
    browser.close()
