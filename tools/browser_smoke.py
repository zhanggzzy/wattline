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

with sync_playwright() as p:
    browser = p.chromium.launch(**({"executable_path":args.browser} if args.browser else {}))
    page = browser.new_page(viewport={"width":1440,"height":1100}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/*", handle)
    page.goto("http://wattline.test")
    expect(page.locator("#host-rows tr")).to_have_count(3)
    expect(page.locator("#chart-summary")).to_contain_text("11 个有效时段")
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
    page.reload()
    expect(page.locator("#host-rows tr")).to_have_count(3)
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
    expect(page.get_by_role("heading", name="当前 GPU 进程")).to_be_visible()
    expect(page.locator(".process-table")).to_contain_text("demo-user")
    page.get_by_role("button", name="查看 GPU 0", exact=True).click()
    expect(page.locator(".gpu-info")).to_contain_text("GPU-synthetic-01")
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
    expect(page.get_by_role('heading',name='Current GPU processes')).to_be_visible()
    expect(page.locator('.process-table')).to_contain_text('demo-user')
    page.get_by_role('button',name='View GPU 0',exact=True).click()
    expect(page.get_by_role('heading',name='GPU 0 device information')).to_be_visible()
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

    print(json.dumps({"result":"PASS", "browser":browser.version, "page_errors":errors,
                      "mutations":len(mutations), "screenshots":14, "locales":["zh-CN","en"],
                      "metric_layouts":layout_results, "focus_refreshes":focus_results}, ensure_ascii=False))
    browser.close()
