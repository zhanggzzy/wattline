"""Browser checks with synthetic fixtures. No listening server, collection, or SSH is used.
Run: .venv/bin/python tools/browser_smoke.py [--browser /path/to/chromium]
Requires: pip install -e '.[test,browser-test]'; python -m playwright install chromium
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

from wattline.app import create_app
from wattline.archive_analysis import ArchiveAnalysis
from wattline.config import Config, Machine, MachineSettings
from wattline.history import History, WARM_MS
from wattline.service import Monitor

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
                assigned_users=[{"id": 1, "name": "张工"}] if i == 1 else [],
                ssh_connect_timeout_seconds=5)
machines = [node(1), node(2), node(3, "offline")]
mode = "normal"
mutations = []
history_queries = []
def curve(machine_id, index, metric):
    base = {"demo-1":[10,15,22,30,42,55,63,71,80,88,92],
            "demo-2":[85,90,78,None,None,None,40,52,61,73,84],
            "demo-3":[None]*11}.get(machine_id,[10,18,27,36,44,53,62,70,79,87,95])[index]
    if base is None:
        return None
    factor = {"gpu":1, "cpu":0.6, "memory":0.4, "power":7}[metric]
    return round(base*factor, 1)


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
        q = parse_qs(urlsplit(route.request.url).query)
        metric = q.get("metric", ["gpu"])[0]
        hours = int(q.get("hours", [24])[0])
        history_queries.append({"metric":metric, "hours":hours, "machine":q.get("machine",[None])[0]})
        if "machine" in q:
            return route.fulfill(json=dict(keys=[metric], to=now, **{"from":now-hours*3600000},
                points=[dict(time=now-hours*3600000+i*hours*360000, values=[30+(i*7)%50]) for i in range(11)]))
        ids = [host["id"] for host in machines if host["enabled"]] if mode != "empty" else []
        points = []
        if ids:
            for i in range(11):
                values = [curve(machine_id, i, metric) for machine_id in ids]
                points.append(dict(time=now-hours*3600000+i*hours*360000, values=values,
                                   breaks=[value is None for value in values]))
        return route.fulfill(json=dict(keys=[metric], machines=ids, to=now,
            **{"from":now-hours*3600000}, points=points))
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
                        test_page.locator('[data-configure-machine]').click()
                        if action == 'remove':
                            test_page.locator('[data-remove-machine]').click()

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
                    if action == 'remove':
                        test_page.locator('#machine-cancel').click()
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

def check_gpu_tolerance_settings(browser):
    global machines
    linux = dict(node(1), target_os='linux', scope=None, idle_memory_tolerance_mib=256)
    windows = dict(node(2), target_os='windows', idle_memory_tolerance_mib=256)
    container = dict(node(3), scope='container', idle_memory_tolerance_mib=256)
    cpu = dict(node(2), id='cpu-fixture', name='CPU fixture', hardware_kind='cpu', configured_hardware_kind='cpu',
               require_gpu=False, checks=['cpu'], idle_memory_tolerance_mib=256)
    machines = [linux, windows, container, cpu]
    page = browser.new_page(viewport={'width':390, 'height':844})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/*', handle)
    page.goto('http://wattline.test')
    dialog = page.locator('#machine-dialog')
    url = 'http://wattline.test/api/machines/demo-1/settings'
    results = {}

    def configure(id, label):
        page.locator(f'#rail-nav [data-host="{id}"]').click()
        page.get_by_role('button', name=label, exact=True).click()

    for locale, entry, label, previous, new in (
        ('zh-CN', '配置', '空闲显存容差（MiB）', '256', '0'),
        ('en', 'Configure', 'Idle VRAM tolerance (MiB)', '0', '512.5'),
    ):
        page.locator('#locale-select').select_option(locale)
        configure('demo-1', entry)
        tolerance = dialog.get_by_role('spinbutton', name=label, exact=True)
        expect(tolerance).to_be_visible()
        expect(tolerance).to_have_value(previous)
        count = len(mutations)
        tolerance.fill('-1')
        page.locator('#machine-save').click()
        assert tolerance.evaluate('(input) => input.validity.rangeUnderflow')
        assert len(mutations) == count
        tolerance.fill(new)
        with page.expect_response(url) as saved:
            page.locator('#machine-save').click()
        response = saved.value
        assert response.ok and response.request.post_data_json['idle_memory_tolerance_mib'] == float(new)
        expect(dialog).to_be_hidden()
        configure('demo-1', entry)
        expect(tolerance).to_have_value(new)
        with page.expect_response(url) as unchanged:
            page.locator('#machine-save').click()
        assert 'idle_memory_tolerance_mib' not in unchanged.value.request.post_data_json
        expect(dialog).to_be_hidden()
        for id in ('demo-2', 'demo-3', 'cpu-fixture'):
            configure(id, entry)
            field = dialog.locator('[name="idle_memory_tolerance_mib"]')
            expect(field).to_be_hidden()
            expect(field).to_be_disabled()
            page.locator('#machine-cancel').click()
        results[locale] = {'initial_mib':float(previous), 'saved_mib':float(new), 'inapplicable_hidden':True}
    assert not errors, errors
    page.close()
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

def check_windows_processes(browser):
    global machines
    windows_host = node(1)
    windows_host.update(target_os='windows', gpu_inventory_complete=True)
    windows_host['metrics'].update(load_average=[], root_disk={'volume':'D:', 'available_bytes':2**34})
    measured = windows_host['metrics']['gpus'][0]
    measured.update(process_visibility='partial', processes=[
        dict(pid=16, used_memory_mib=None),
        dict(pid=14, used_memory_mib=400, user=r'Fixture\Operator'),
        dict(pid=13, used_memory_mib=512),
        dict(pid=10, used_memory_mib=None),
        dict(pid=12, used_memory_mib=512),
        dict(pid=11, used_memory_mib=0),
        dict(pid=15, used_memory_mib=None),
    ])
    empty = dict(measured, uuid='GPU-synthetic-empty', index=1, processes=[], state='unknown')
    windows_host['metrics']['gpus'].append(empty)
    windows_host['devices'] = [measured, empty]
    linux = node(2)
    linux['metrics']['gpus'][0]['processes'] = measured['processes']
    no_cards = node(3)
    no_cards.update(target_os='windows', devices=[], gpu_inventory_complete=True)
    no_cards['metrics']['gpus'] = []
    machines = [windows_host, linux, no_cards]

    page = browser.new_page(viewport={'width':390,'height':844})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/*', handle)
    page.goto('http://wattline.test')
    page.locator('#locale-select').select_option('en')
    expect(page.locator('.overview-metrics > .metric')).to_have_count(3)
    expect(page.locator('.overview-metrics [data-value=processes]')).to_have_count(0)
    assert page.evaluate("""state.snapshot.machines.flatMap(machine =>
      machine.metrics.gpus.flatMap(gpu => gpu.processes)).length""") == 14
    page.locator('[data-add-machine]').click()
    selector = page.get_by_label('Target operating system')
    expect(selector).to_have_value('linux')
    selector.select_option('windows')
    page.locator('#machine-form [name=host]').fill('synthetic.invalid')
    page.locator('#machine-save').click()
    expect(page.locator('#machine-error')).to_be_visible()
    assert json.loads(mutations[-1][2])['target_os'] == 'windows'
    page.keyboard.press('Escape')

    page.locator('#rail-nav [data-host=demo-1]').click()
    hardware = page.locator('.hardware-table')
    expect(page.locator('[data-value=disk]')).to_have_text('D: · 16.0 GiB')
    expect(page.locator('[data-value=load]')).to_have_count(0)
    expected = [f'PID {pid}' for pid in (12,13,14,11,10)]
    expect(hardware.locator('.gpu-processes .mono')).to_have_text(expected)
    expect(hardware).to_contain_text('2 more observed records omitted')
    expect(hardware).to_contain_text('No verifiable GPU process records available')
    expect(hardware).to_contain_text('Usage unknown')
    expect(hardware).to_contain_text('In use')
    page.locator('#locale-select').select_option('zh-CN')
    expect(hardware).to_contain_text('占用未确认')
    page.locator('#locale-select').select_option('en')
    page.get_by_role('button',name='View GPU 0',exact=True).click()
    dialog = page.locator('#gpu-dialog')
    expect(dialog.locator('.process-table .mono')).to_have_text(expected)
    expect(dialog).to_contain_text('2 more observed records omitted')
    expect(dialog).to_contain_text('Visible records: 7')
    expect(dialog).to_contain_text(r'Fixture\Operator')
    expect(dialog.locator('.process-table')).not_to_contain_text('UID')
    expect(dialog.locator('.process-table tbody tr').last.locator('td').nth(4)).to_have_text('Unknown')
    page.keyboard.press('Escape')
    page.get_by_role('button',name='View GPU 1',exact=True).click()
    expect(dialog).to_contain_text('No verifiable GPU process records available')
    page.keyboard.press('Escape')

    page.locator('#rail-nav [data-host=demo-3]').click()
    expect(page.locator('.hardware-panel')).to_contain_text('No NVIDIA GPUs detected.')
    no_cards['gpu_inventory_complete'] = False
    expect(page.locator('.hardware-panel')).to_contain_text('No verified devices yet.', timeout=8000)
    page.locator('#rail-nav [data-host=demo-2]').click()
    expect(hardware.locator('.gpu-processes li')).to_have_count(7)
    assert not errors, errors
    page.close()
    return {'enrollment_os':True, 'displayed_per_card':5, 'observed_per_card':7, 'omitted_per_card':2,
            'unknown_empty_processes':True, 'confirmed_and_unavailable_inventory':True,
            'account_without_uid':True, 'linux_rows':7, 'page_errors':errors}


def check_gpu_process_timing(browser):
    page = browser.new_page(viewport={'width':1440,'height':900}, timezone_id='America/Los_Angeles')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    machine = node(1)
    device = machine['metrics']['gpus'][0]
    valid = device['processes'][0]
    started_at = int(datetime(2026, 11, 24, 0, 30, 12, tzinfo=timezone.utc).timestamp()*1000)
    valid.update(started_at=started_at, elapsed_seconds=62)
    device['processes'].extend([
        dict(pid=121, name='legacy', used_memory_mib=512),
        dict(pid=122, name='partial', used_memory_mib=512, started_at=started_at),
        dict(pid=123, name='invalid', used_memory_mib=512, started_at=9_000_000_000_000_000, elapsed_seconds=3),
        dict(pid=124, name='just started', used_memory_mib=512, started_at=started_at, elapsed_seconds=0),
    ])

    def snapshot(route):
        route.fulfill(json=dict(server_time=int(time.time()*1000), stale_ms=600000, period_ms=5000,
            default_ssh_connect_timeout_seconds=5, machine_history_hours=168, registry_loaded=True,
            history_writable=True, archive_ok=True, machines=[machine]))

    def timing(pane, pid, key):
        return pane.locator(f'[data-value="process-{device["uuid"]}-{pid}-{key}"]')

    def unknown_timings(pane, pids, label):
        for pid in pids:
            expect(timing(pane, pid, 'start')).to_have_text(label)
            expect(timing(pane, pid, 'elapsed')).to_have_text(label)

    page.route('**/*', handle)
    page.route('**/api/snapshot', snapshot)
    page.goto('http://wattline.test')
    page.locator('.rail-machine[data-host="demo-1"]').click()
    hardware = page.locator('.hardware-table')
    expect(hardware).to_contain_text('启动时间')
    expect(hardware).to_contain_text('截至采样已运行')
    expect(timing(hardware, 120, 'start')).to_have_text('2026/11/23 16:30:12')
    expect(timing(hardware, 120, 'elapsed')).to_have_text('1 分钟 2 秒')
    expect(timing(hardware, 124, 'elapsed')).to_have_text('0 秒')
    unknown_timings(hardware, [121, 122, 123], '未知')
    page.locator('.gpu-open').click()
    dialog = page.locator('#gpu-dialog')
    expect(dialog.get_by_role('columnheader',name='启动时间')).to_be_visible()
    expect(timing(dialog, 120, 'start')).to_have_text('2026/11/23 16:30:12')
    expect(timing(dialog, 120, 'elapsed')).to_have_text('1 分钟 2 秒')
    unknown_timings(dialog, [121, 122, 123], '未知')
    page.keyboard.press('Escape')
    expect(page.locator('.gpu-open')).to_be_focused()

    page.locator('#locale-select').select_option('en')
    page.set_viewport_size({'width':320,'height':844})
    expect(timing(hardware, 120, 'start')).to_have_text('11/23/2026, 16:30:12')
    expect(hardware).to_contain_text('Runtime at sample')
    unknown_timings(hardware, [121, 122, 123], 'Unknown')
    page.locator('.gpu-open').click()
    expect(dialog.get_by_role('columnheader',name='Start time')).to_be_visible()
    expect(dialog.get_by_role('columnheader',name='Runtime at sample')).to_be_visible()
    expect(timing(dialog, 120, 'start')).to_have_text('11/23/2026, 16:30:12')
    expect(timing(dialog, 124, 'elapsed')).to_have_text('0 s')
    unknown_timings(dialog, [121, 122, 123], 'Unknown')
    region = dialog.get_by_role('region',name='GPU process list')
    region.focus()
    assert region.evaluate('(el) => el.scrollWidth > el.clientWidth')
    assert region.evaluate('(el) => (el.scrollLeft = el.scrollWidth)') > 0
    assert dialog.evaluate('(el) => el.scrollWidth <= el.clientWidth')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    original_region = region.element_handle()
    valid['elapsed_seconds'] = 3660
    expect(timing(dialog, 120, 'elapsed')).to_have_text('1 h 1 min')
    expect(timing(hardware, 120, 'elapsed')).to_have_text('1 h 1 min')
    assert original_region.evaluate('(el) => el === document.activeElement && el.scrollLeft > 0')
    valid.pop('elapsed_seconds')
    unknown_timings(dialog, [120], 'Unknown')
    unknown_timings(hardware, [120], 'Unknown')
    assert original_region.evaluate('(el) => el === document.activeElement')
    device['processes'].clear()
    expect(dialog).to_contain_text('No GPU processes found.')
    expect(dialog.get_by_role('button',name='Close details')).to_be_focused()
    page.keyboard.press('Escape')
    expect(page.locator('.gpu-open')).to_be_focused()
    expect(hardware).to_contain_text('No GPU processes found.', timeout=1000)
    assert not errors, errors
    page.close()
    return {'locales':['zh-CN','en'], 'timezone':'America/Los_Angeles', 'narrow_width':320,
            'timing_only_poll':True, 'missing_pair_poll':True, 'departed_processes_poll':True, 'page_errors':errors}


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
    expect(rail).to_have_accessible_name('训练节点 Alpha · 正常 · NVIDIA Synthetic GPU')
    assert rail.locator('strong').is_hidden()
    assert rail.locator('.machine-icon').is_visible()
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
    expect(page.locator('.hardware-table tbody tr').nth(1)).to_contain_text('空闲')
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
    expect(page.locator('.trend-stack .plot canvas')).to_have_count(1)
    page.screenshot(path=str(OUT/'an48-single-power.png'),full_page=True)
    page.locator('[data-metric="gpu"]').press('Space')
    expect(page.locator('.trend-stack .plot canvas')).to_have_count(2)
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
        page.wait_for_function("""() => [...document.querySelectorAll('.trend-stack .plot canvas')].every(c =>
          Math.abs(c.width-c.clientWidth*devicePixelRatio)<=1 && Math.abs(c.height-c.clientHeight*devicePixelRatio)<=1)""")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), ('focus',width)
        bounds = [canvas.bounding_box() for canvas in page.locator('.trend-stack .plot canvas').all()]
        assert bounds[0]['y']+bounds[0]['height'] <= bounds[1]['y']
        resized.append({'width':width,'plots':len(bounds),'overflow':False})
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(OUT/'an48-two-charts-narrow.png'),full_page=True)
    page.set_viewport_size({'width':1440,'height':1100})
    page.screenshot(path=str(OUT/'an48-power-utilization-24h.png'),full_page=True)
    for canvas, label in zip(page.locator('.trend-stack .plot canvas').all(),['GPU 功耗','GPU 利用率']):
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
    expect(page.locator('.trend-stack .plot canvas')).to_have_count(1)
    page.locator('[data-metric="vram"]').click()
    page.locator('[data-metric="temp"]').click()
    expect(page.locator('.trend-stack .plot canvas')).to_have_count(3)
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
    expect(page.get_by_role('group',name='Trend metric')).to_be_visible()
    expect(page.locator('.chart-panel .panel-head')).to_contain_text('By machine · Fixed 24-hour window')
    page.locator('#focus-trends').click()
    page.locator('[data-metric="cpu"]').click()
    expect(page.locator('.chart-title').first).to_contain_text('GPU utilization')
    expect(page.locator('.chart-title').nth(1)).to_contain_text('CPU usage')
    expect(page.locator('#chart-summary')).to_have_text('11 valid periods · Machines: 3')
    expect(page.locator('#chart-summary-cpu')).to_have_text('11 valid periods · Machines: 3')
    assert page.evaluate('Object.values(state.histories).every(h => h.machines.length === 3 && h.to-h.from === 24*3600000)')
    expect(page.locator('[data-range]')).to_have_count(0)
    page.locator('[data-metric="power"]').click()
    expect(page.locator('.chart-title').nth(2)).to_contain_text('GPU power')
    expect(page.locator('#chart-summary-power')).to_have_text('11 valid periods · Machines: 3')
    page.locator('#chart-data-power summary').click()
    expect(page.locator('#chart-data-power thead')).to_contain_text('训练节点 Alpha (W)')
    expect(page.locator('#chart-data-power tbody tr').first).to_contain_text('70.0 W')
    page.locator('#trend-chart-power').press('ArrowLeft')
    expect(page.locator('#chart-announcement-power')).to_contain_text('训练节点 Alpha 616.0 W')
    page.locator('#exit-trends').click()
    expect(page.locator('[data-overview-metric="gpu"]')).to_have_attribute('aria-pressed','true')
    page.get_by_role('button',name='Memory usage',exact=True).click()
    page.locator('#focus-trends').click()
    expect(page.locator('.chart-title')).to_contain_text('Memory usage')
    expect(page.locator('#chart-summary')).to_have_text('11 valid periods · Machines: 3')
    page.locator('#exit-trends').click()
    expect(page.locator('[data-overview-metric="memory"]')).to_have_attribute('aria-pressed','true')
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

def check_overview_regressions(browser):
    page = browser.new_page(viewport={"width":320,"height":844})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    label = "<b>字面</b>&" + "W" * (80-len("<b>字面</b>&"))
    active = [dict(node(1), id=f"trend-{i}", name=f"合成节点 {i}") for i in range(1,10)]
    for host in (active[0],active[-1]):
        host.update(name=label, address="<i>合成地址</i>.invalid")
    slow = [0,11,22,None,33,44,55,None,66,77,None,90,91]
    now = int(time.time()*1000)
    start = now-86400000
    points = [
        dict(time=start+i*216000, values=[i+5*j for j in range(1,9)]+[value],
             breaks=[i == 0]*8+[i in (0,10,11)])
        for i,value in enumerate(slow)
    ]
    # Missing polls can also be signalled on the next observed bucket.
    points[4]["values"][1] = None
    points[5]["breaks"][1] = True
    page.route("**/*", handle)
    page.route("**/api/snapshot", lambda route: route.fulfill(json=dict(
        server_time=now, period_ms=10000, stale_ms=30000, machines=active)))
    page.route("**/api/history?*", lambda route: route.fulfill(json={
        "from":start, "to":now, "bucket_ms":216000, "gap_ms":324000, "keys":["gpu"],
        "machines":[host["id"] for host in active], "points":points,
    }))
    # Observe real canvas strokes and segment lengths while leaving rendering in place.
    page.add_init_script("""(() => {
      const edges = new WeakMap();
      const traces = new WeakMap();
      const context = CanvasRenderingContext2D.prototype;
      const wrap = (method, observe) => {
        const original = context[method];
        context[method] = function (...args) {
          observe(this);
          return original.apply(this,args);
        };
      };
      wrap('beginPath', ctx => edges.set(ctx,0));
      wrap('lineTo', ctx => edges.set(ctx,(edges.get(ctx) || 0)+1));
      wrap('clearRect', ctx => traces.set(ctx.canvas,[]));
      wrap('stroke', ctx => {
        const trace = traces.get(ctx.canvas) || [];
        trace.push({color:ctx.strokeStyle,dash:ctx.getLineDash(),edges:edges.get(ctx)});
        traces.set(ctx.canvas,trace);
      });
      window.strokeTrace = canvas => traces.get(canvas);
    })()""")
    page.goto("http://wattline.test")
    expect(page.locator("#chart-summary")).to_contain_text("13 个有效时段")
    legend = page.locator("#chart-legend")
    tip = page.locator("#chart-tip")
    canvas = page.locator("#trend-chart")
    entries = legend.locator(".chart-legend-item")
    expect(entries).to_have_count(9)
    expected_labels = [f"{label} · {host['address']} · {host['id']}" for host in (active[0],active[-1])]
    for entry,expected in zip((entries.first,entries.last),expected_labels):
        expect(entry).to_have_text(expected)
    expect(legend.locator("b, i")).to_have_count(0)

    swatches = entries.locator("canvas").evaluate_all("canvases => canvases.map(canvas => strokeTrace(canvas)[0])")
    assert swatches[0]["color"] == swatches[-1]["color"]
    assert swatches[0]["dash"] != swatches[-1]["dash"]
    assert len({(item["color"],tuple(item["dash"])) for item in swatches}) == 9
    strokes = canvas.evaluate("canvas => strokeTrace(canvas)")
    for index,swatch in enumerate(swatches):
        lengths = [stroke["edges"] for stroke in strokes
                   if (stroke["color"],stroke["dash"]) == (swatch["color"],swatch["dash"])]
        assert lengths == {1:[3,7], 8:[7,1]}.get(index,[12]), (index, lengths)

    canvas.press("ArrowLeft")
    expect(tip).to_be_visible()
    for expected in expected_labels:
        expect(tip).to_contain_text(expected)
    expect(tip.locator("b, i")).to_have_count(0)
    assert page.evaluate("""() => {
      const legend = document.querySelector('#chart-legend').getBoundingClientRect();
      const plot = document.querySelector('.plot').getBoundingClientRect();
      const tip = document.querySelector('#chart-tip').getBoundingClientRect();
      const textFits = (parent, element) => {
        const range = document.createRange();
        range.selectNodeContents(element);
        const rects = [...range.getClientRects()];
        return rects.length > 1 && rects.every(r => r.left >= parent.left && r.right <= parent.right);
      };
      return document.documentElement.scrollWidth === innerWidth
        && tip.left >= plot.left && tip.right <= plot.right
        && textFits(legend,document.querySelector('.chart-legend-item span'))
        && textFits(tip,document.querySelector('#chart-tip div'));
    }""")
    canvas.hover(position={"x":41,"y":20})
    expect(tip).to_contain_text(expected_labels[-1]+" · 0%")
    page.locator('#locale-select').select_option('en')
    expect(page.locator('#chart-summary')).to_have_text('13 valid periods · Machines: 9')
    page.locator('#chart-data summary').click()
    headers = page.locator('#chart-data thead th')
    expect(headers).to_have_count(10)
    expect(headers.first).to_have_text('Sample time')
    expect(headers.last).to_have_text(expected_labels[-1]+' (%)')
    expect(page.locator('#chart-data b, #chart-data i')).to_have_count(0)
    expect(page.locator('#chart-data tbody tr').first.locator('td').last).to_have_text('0.0%')
    assert page.evaluate('document.documentElement.scrollWidth === innerWidth')
    assert not errors, errors
    page.close()
    return {"width":320,"machines":9,"slow_segment_edges":[7,1],"lapse_segment_edges":[3,7]}


def check_machine_silhouettes(browser):
    """AN-64 synthetic acceptance: model silhouettes, fallback, identity and rail semantics."""
    global machines, mode
    mode = 'normal'

    def silhouette_host(identifier, name, models, status='normal', *, complete=True, expected=None):
        host = node(1)
        host.update(id=identifier, name=name, address=f'{identifier}.invalid', status=status)
        if models is None:
            host.pop('devices', None)
        else:
            host['devices'] = [dict(gpu, uuid=f'{identifier}-gpu-{index}', index=index, name=model)
                               for index, model in enumerate(models)]
            host['expected_gpu_count'] = expected if expected is not None else (len(models) or None)
        if status in ('normal', 'warning'):
            host['metrics'] = copy.deepcopy(metrics)
            host['metrics']['gpus'] = [dict(gpu, uuid=f'{identifier}-gpu-{index}', index=index, name=model)
                                       for index, model in enumerate(models or [])]
            host['metrics']['gpu_inventory_complete'] = complete
        else:
            host['metrics'] = None
            host['reason'] = '连接超时 · 合成离线样本'
        return host

    def build_machines(live_models):
        return [
            silhouette_host('live', '更新节点', live_models),
            silhouette_host('b300-a', '机柜 B300 甲', ['NVIDIA B300 SXM6 AC']),
            silhouette_host('b300-b', '机柜 B300 乙', ['NVIDIA B300 SXM6 AC']),
            silhouette_host('pro', '工作站 PRO 6000', ['NVIDIA RTX PRO 6000 Blackwell Workstation Edition']),
            silhouette_host('spark', 'Spark 方盒', ['NVIDIA GB10']),
            silhouette_host('rtx', '桌面 5090', ['NVIDIA GeForce RTX 5090']),
            silhouette_host('unknown', '未知机型', ['NVIDIA Synthetic GPU'], status='warning'),
            silhouette_host('mixed', '混合机型', ['NVIDIA B300 SXM6 AC', 'NVIDIA GeForce RTX 5090']),
            silhouette_host('legacy', '旧配置无型号', None, status='offline'),
            silhouette_host('missing', '部分名称为空', ['NVIDIA B300 SXM6 AC', None]),
            silhouette_host('partial', '数量不全', ['NVIDIA B300 SXM6 AC'], status='warning',
                            complete=False, expected=2),
            silhouette_host('ambiguous', '复合名称', ['NVIDIA B300 / GeForce RTX 5090']),
            silhouette_host('near', '非 6000', ['NVIDIA PRO 60000']),
            silhouette_host('duplicate-a', '相同别名', ['NVIDIA B300 SXM6 AC']),
            silhouette_host('duplicate-b', '相同别名', ['NVIDIA B300 SXM6 AC']),
            silhouette_host('unicode-a', 'Alpha 🚀🚀', ['NVIDIA GeForce RTX 5090']),
            silhouette_host('unicode-b', 'Beta 🛸🚀', ['NVIDIA GeForce RTX 5090']),
        ]

    machines = build_machines([])
    cases = [
        ('live', 'generic', '更新节点 · 正常'),
        ('b300-a', 'b300', '机柜 B300 甲 · 正常 · NVIDIA B300 SXM6 AC'),
        ('b300-b', 'b300', '机柜 B300 乙 · 正常 · NVIDIA B300 SXM6 AC'),
        ('pro', 'pro6000', '工作站 PRO 6000 · 正常 · NVIDIA RTX PRO 6000 Blackwell Workstation Edition'),
        ('spark', 'spark', 'Spark 方盒 · 正常 · NVIDIA GB10'),
        ('rtx', 'rtx5090', '桌面 5090 · 正常 · NVIDIA GeForce RTX 5090'),
        ('unknown', 'generic', '未知机型 · 需关注 · NVIDIA Synthetic GPU'),
        ('mixed', 'generic', '混合机型 · 正常 · NVIDIA B300 SXM6 AC · NVIDIA GeForce RTX 5090'),
        ('legacy', 'generic', '旧配置无型号 · 连接失败'),
        ('missing', 'generic', '部分名称为空 · 正常 · NVIDIA B300 SXM6 AC'),
        ('partial', 'generic', '数量不全 · 需关注 · NVIDIA B300 SXM6 AC'),
        ('ambiguous', 'generic', '复合名称 · 正常 · NVIDIA B300 / GeForce RTX 5090'),
        ('near', 'generic', '非 6000 · 正常 · NVIDIA PRO 60000'),
    ]
    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/*', handle)
    page.goto('http://wattline.test')
    expect(page.locator('#host-rows tr')).to_have_count(17)

    matrix = page.evaluate("""() => {
      const cases = [
        [['NVIDIA B300 SXM6 AC'],'b300'],
        [['NVIDIA RTX PRO 6000 Blackwell Workstation Edition'],'pro6000'],
        [['NVIDIA RTX PRO 6000 Blackwell Max-Q'],'pro6000'],
        [['NVIDIA GB10'],'spark'],
        [['NVIDIA DGX Spark'],'spark'],
        [['NVIDIA GeForce RTX 5090'],'rtx5090'],
        [['NVIDIA GeForce RTX 5090 D'],'rtx5090'],
        [['NVIDIA RTX 6000 Ada Generation'],'generic'],
        [['NVIDIA Synthetic GPU'],'generic'],
        [['NVIDIA B300 SXM6 AC','NVIDIA GeForce RTX 5090'],'generic'],
        [['NVIDIA B300 SXM6 AC','NVIDIA Graphics Device'],'generic'],
        [['NVIDIA B300 SXM6 AC','NVIDIA B300 SXM6 AC'],'b300'],
        [['NVIDIA B300 SXM6 AC', null],'generic'],
        [['NVIDIA B300 / GeForce RTX 5090'],'generic'],
        [['NVIDIA PRO 60000'],'generic'],
        [['NVIDIA PRO 6000X'],'generic'],
        [['NVIDIA PRO 6000_Engineering'],'generic'],
        [['NVIDIA PRO 6000版'],'generic'],
        [['NVIDIA XRTPRO 6000'],'generic'],
        [[null],'generic'],
        [[],'generic'],
      ];
      const incomplete = [
        {devices:[{name:'NVIDIA B300 SXM6 AC'}], expected_gpu_count:2, metrics:{gpu_inventory_complete:false}},
        {devices:[{name:'NVIDIA B300 SXM6 AC'}], expected_gpu_count:2, gpu_inventory_complete:true},
        {devices:[{name:'NVIDIA B300 SXM6 AC'}], metrics:{gpu_inventory_complete:true}},
      ];
      return cases.map(([names,expected]) => ({names, expected,
        actual: machineModel({devices:names.map(name => ({name})), gpu_inventory_complete:true}).kind}))
        .concat(incomplete.map((node, index) => ({expected:index === 2 ? 'b300' : 'generic',
          actual:machineModel(node).kind})));
    }""")
    assert all(item['actual'] == item['expected'] for item in matrix), matrix

    toggle = page.locator('#rail-toggle')
    toggle.press('Enter')
    expect(toggle).to_have_attribute('aria-expanded', 'false')
    rail_width = page.locator('.rail').bounding_box()['width']
    assert 63 <= rail_width <= 65, rail_width

    for machine_id, kind, identity in cases:
        item = page.locator(f'#rail-nav [data-host="{machine_id}"]')
        expect(item.locator('.machine-icon')).to_have_attribute('data-model', kind)
        expect(item.locator('.machine-icon')).to_be_visible()
        expect(item.locator('.status-dot')).to_be_visible()
        expect(item).to_have_attribute('aria-label', identity)
        expect(item).to_have_attribute('title', identity)
        icon_box = item.locator('.machine-icon').bounding_box()
        assert icon_box and 23 <= icon_box['width'] <= 25 and 23 <= icon_box['height'] <= 25, icon_box

    b300_suffixes = [page.locator(f'#rail-nav [data-host="{machine_id}"] .machine-suffix').inner_text()
                     for machine_id in ('b300-a', 'b300-b')]
    generic_ids = ('live', 'unknown', 'mixed', 'legacy', 'missing', 'partial', 'ambiguous', 'near')
    generic_suffixes = [page.locator(f'#rail-nav [data-host="{machine_id}"] .machine-suffix').inner_text()
                        for machine_id in generic_ids]
    assert len(set(b300_suffixes)) == 2 and all(0 < len(value) <= 4 for value in b300_suffixes), b300_suffixes
    assert len(set(generic_suffixes)) == 8 and all(0 < len(value) <= 4 for value in generic_suffixes), generic_suffixes
    for machine_id in ('pro', 'spark'):
        assert page.locator(f'#rail-nav [data-host="{machine_id}"] .machine-suffix').count() == 0, machine_id

    duplicate_labels = {
        machine_id: page.locator(f'#rail-nav [data-host="{machine_id}"]').get_attribute('aria-label')
        for machine_id in ('duplicate-a', 'duplicate-b')
    }
    duplicate_titles = {
        machine_id: page.locator(f'#rail-nav [data-host="{machine_id}"]').get_attribute('title')
        for machine_id in ('duplicate-a', 'duplicate-b')
    }
    assert duplicate_labels['duplicate-a'] != duplicate_labels['duplicate-b'], duplicate_labels
    assert duplicate_labels == duplicate_titles, duplicate_titles
    for label in duplicate_labels.values():
        assert label.startswith('相同别名 · 正常 · NVIDIA B300 SXM6 AC · 实例 '), label

    unicode_suffixes = {}
    for machine_id in ('unicode-a', 'unicode-b'):
        suffix = page.locator(f'#rail-nav [data-host="{machine_id}"] .machine-suffix')
        text = suffix.inner_text()
        assert '\ufffd' not in text, text
        screenshot = OUT / f'an64-suffix-{machine_id}.png'
        suffix.screenshot(path=str(screenshot))
        unicode_suffixes[machine_id] = {'suffix': text,
                                        'rendered_sha256': hashlib.sha256(screenshot.read_bytes()).hexdigest()}
    assert unicode_suffixes['unicode-a']['rendered_sha256'] != unicode_suffixes['unicode-b']['rendered_sha256'], \
        unicode_suffixes

    # The status dot must not replace the button's complete identity tooltip.
    hover_titles = {}
    mixed_button = page.locator('#rail-nav [data-host="mixed"]')
    for selector in ('.machine-icon', '.status-dot'):
        target = mixed_button.locator(selector)
        target.hover()
        hover_titles[selector] = target.evaluate("""el => {
          const box = el.getBoundingClientRect();
          return document.elementFromPoint(box.x + box.width/2, box.y + box.height/2)
            .closest('[title]').getAttribute('title');
        }""")
    assert hover_titles['.machine-icon'] == hover_titles['.status-dot'] == \
        '混合机型 · 正常 · NVIDIA B300 SXM6 AC · NVIDIA GeForce RTX 5090', hover_titles

    dot_colors = {
        machine_id: page.locator(f'#rail-nav [data-host="{machine_id}"] .status-dot')
        .evaluate('dot => getComputedStyle(dot).backgroundColor')
        for machine_id in ('b300-a', 'unknown', 'legacy')
    }
    assert dot_colors == {'b300-a': 'rgb(107, 212, 173)', 'unknown': 'rgb(255, 198, 111)',
                          'legacy': 'rgb(250, 155, 139)'}, dot_colors

    glyph_hashes = {}
    for machine_id, kind in (('b300-a', 'b300'), ('pro', 'pro6000'), ('spark', 'spark'),
                             ('rtx', 'rtx5090'), ('unknown', 'generic')):
        path = OUT / f'an64-glyph-{kind}.png'
        page.locator(f'#rail-nav [data-host="{machine_id}"] .machine-icon').screenshot(path=str(path))
        glyph_hashes[kind] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(set(glyph_hashes.values())) == 5, glyph_hashes

    monochrome = page.evaluate("""() => {
      const icons = [...document.querySelectorAll('#rail-nav .machine-icon')];
      return {
        colors: [...new Set(icons.map(icon => getComputedStyle(icon).color))],
        attrs: icons.every(icon => [...icon.querySelectorAll('*')].every(el => {
          const fill = el.getAttribute('fill');
          const stroke = el.getAttribute('stroke');
          return (fill === null || fill === 'currentColor')
            && (stroke === null || stroke === 'currentColor' || (stroke === 'none' && fill === 'currentColor'));
        })),
        rail: getComputedStyle(document.querySelector('.rail')).backgroundColor,
      };
    }""")
    assert monochrome == {'colors': ['rgb(195, 206, 224)'], 'attrs': True,
                          'rail': 'rgb(16, 31, 53)'}, monochrome

    # Keyboard identity, selection and navigation survive the new glyph markup.
    selected = page.locator('#rail-nav [data-host="b300-a"]')
    unselected_background = page.locator('#rail-nav [data-host="b300-b"]').evaluate(
        'item => getComputedStyle(item).backgroundColor')
    selected.press('Enter')
    expect(selected).to_have_attribute('aria-current', 'page')
    expect(page.locator('#page-heading')).to_be_focused()
    expect(page.locator('#page-heading')).to_have_text('机柜 B300 甲')
    assert selected.evaluate('item => getComputedStyle(item).backgroundColor') != unselected_background
    page.locator('#rail-nav [data-host="spark"]').press('Enter')
    expect(page.locator('#page-heading')).to_have_text('Spark 方盒')
    page.locator('#rail-nav [data-overview]').press('Enter')
    expect(page.locator('#page-heading')).to_have_text('算力，一目了然')
    page.locator('#rail-nav [data-host="mixed"]').hover()
    expect(page.locator('#rail-nav [data-host="mixed"]')).to_have_attribute(
        'title', '混合机型 · 正常 · NVIDIA B300 SXM6 AC · NVIDIA GeForce RTX 5090')

    page.locator('.rail').screenshot(path=str(OUT / 'an64-rail-collapsed.png'))
    page.screenshot(path=str(OUT / 'an64-collapsed-desktop.png'))

    toggle.press('Space')
    expect(toggle).to_have_attribute('aria-expanded', 'true')
    for machine_id, _, identity in cases:
        item = page.locator(f'#rail-nav [data-host="{machine_id}"]')
        expect(item.locator('strong')).to_be_visible()
        expect(item.locator('.machine-icon')).to_be_visible()
        expect(item).to_have_accessible_name(identity)
    expect(page.locator('#rail-nav [data-host="b300-a"] .machine-suffix')).to_be_hidden()
    surfaces = page.evaluate("""() => {
      const railGlyph = document.querySelector('#rail-nav .machine-icon');
      const rowGlyph = document.querySelector('#host-rows .machine-icon');
      return {
        railGlyph: getComputedStyle(railGlyph).color,
        rowGlyph: getComputedStyle(rowGlyph).color,
        panel: getComputedStyle(document.querySelector('.machine-panel')).backgroundColor,
      };
    }""")
    assert surfaces['panel'] == 'rgb(255, 255, 255)', surfaces
    assert surfaces['railGlyph'] != surfaces['rowGlyph'], surfaces
    page.locator('.rail').screenshot(path=str(OUT / 'an64-rail-expanded.png'))
    page.locator('.machine-panel').screenshot(path=str(OUT / 'an64-overview-light.png'))

    toggle.press('Space')
    expect(toggle).to_have_attribute('aria-expanded', 'false')
    for width in (320, 390, 640, 731, 1440):
        page.set_viewport_size({'width': width, 'height': 1100})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), ('collapsed', width)
        if width == 390:
            page.screenshot(path=str(OUT / 'an64-collapsed-390.png'))
    toggle.press('Space')
    for width in (320, 390, 731):
        page.set_viewport_size({'width': width, 'height': 1100})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), ('expanded', width)
        if width == 390:
            page.screenshot(path=str(OUT / 'an64-expanded-390.png'))
    page.set_viewport_size({'width': 1440, 'height': 1100})
    toggle.press('Space')
    expect(toggle).to_have_attribute('aria-expanded', 'false')
    expect(page.locator('#rail-nav [data-overview]')).to_have_attribute('aria-current', 'page')

    # An ordinary poll that only changes the device model must repaint overview and rail.
    machines = build_machines(['NVIDIA B300 SXM6 AC'])
    page.wait_for_function(
        "document.querySelector('#rail-nav [data-host=\"live\"] .machine-icon')?.dataset.model === 'b300'")
    poll = {
        'overview_model': page.locator('#host-rows [data-host="live"] .machine-icon').get_attribute('data-model'),
        'rail_model': page.locator('#rail-nav [data-host="live"] .machine-icon').get_attribute('data-model'),
        'title': page.locator('#rail-nav [data-host="live"]').get_attribute('title'),
        'suffix': page.locator('#rail-nav [data-host="live"] .machine-suffix').inner_text(),
    }
    assert poll['overview_model'] == poll['rail_model'] == 'b300', poll
    assert poll['title'] == '更新节点 · 正常 · NVIDIA B300 SXM6 AC', poll

    # Same repaint while another machine is selected, including regrouped suffixes.
    pro_suffix = page.locator('#rail-nav [data-host="pro"] .machine-suffix')
    expect(pro_suffix).to_have_count(0)
    page.locator('#rail-nav [data-host="spark"]').click()
    expect(page.locator('#page-heading')).to_have_text('Spark 方盒')
    machines = build_machines(['NVIDIA RTX PRO 6000 Blackwell Workstation Edition'])
    page.wait_for_function(
        "document.querySelector('#rail-nav [data-host=\"live\"] .machine-icon')?.dataset.model === 'pro6000'")
    assert page.locator('#page-heading').inner_text() == 'Spark 方盒'
    assert page.locator('#rail-nav [data-host="spark"]').get_attribute('aria-current') == 'page'
    poll['selected_model'] = page.locator('#rail-nav [data-host="live"] .machine-icon').get_attribute('data-model')
    poll['selected_title'] = page.locator('#rail-nav [data-host="live"]').get_attribute('title')
    poll['selected_suffix'] = page.locator('#rail-nav [data-host="live"] .machine-suffix').inner_text()
    expect(pro_suffix).to_be_visible()
    poll['selected_peer_suffix'] = pro_suffix.inner_text()
    assert poll['selected_model'] == 'pro6000', poll
    assert 'NVIDIA RTX PRO 6000 Blackwell Workstation Edition' in poll['selected_title'], poll
    assert poll['selected_suffix'] != poll['selected_peer_suffix'], poll

    assert not errors, errors
    page.close()
    return {'result': 'PASS', 'rail_width': rail_width, 'classification': matrix,
            'glyph_sha256': glyph_hashes, 'suffixes': {'b300': b300_suffixes, 'generic': generic_suffixes},
            'duplicate_labels': duplicate_labels, 'unicode_suffixes': unicode_suffixes,
            'hover_titles': hover_titles, 'poll': poll,
            'dot_colors': dot_colors, 'monochrome': monochrome, 'surfaces': surfaces,
            'page_errors': errors,
            'screenshots': ['an64-rail-collapsed.png', 'an64-collapsed-desktop.png', 'an64-rail-expanded.png',
                            'an64-overview-light.png', 'an64-collapsed-390.png', 'an64-expanded-390.png',
                            'an64-glyph-b300.png', 'an64-glyph-pro6000.png', 'an64-glyph-spark.png',
                            'an64-glyph-rtx5090.png', 'an64-glyph-generic.png']}


def check_rail_identity_edges(browser):
    """AN-70 inventory-confidence polling, legacy snapshots, and alias/model edges."""
    global machines
    b300 = 'NVIDIA B300 SXM6 AC'
    spark = 'NVIDIA GB10'
    unknown_pro = 'NVIDIA RTX PRO 6000X'

    def host(identifier, name, model, status='normal', *, complete=None):
        result = node(1, status)
        device = dict(gpu, uuid=f'GPU-{identifier}', name=model)
        result.update(id=identifier, name=name, devices=[device], expected_gpu_count=None,
                      gpu_inventory_complete=complete)
        if result['metrics'] is not None:
            result['metrics'].update(gpus=[device], gpu_inventory_complete=complete)
        return result

    legacy_online = host('legacy-online', '旧在线', b300, complete=True)
    legacy_offline = host('legacy-offline', '旧离线', b300, 'offline')
    for legacy in (legacy_online, legacy_offline):
        del legacy['gpu_inventory_complete']
    machines = [
        host('partial', '部分清单', b300, complete=False),
        host('trusted', '完整清单', b300, complete=True),
        legacy_online, legacy_offline,
        host('accent-a', 'Café', spark, complete=True),
        host('accent-b', 'Cafe\u0301', spark, complete=True),
        host('accent-c', 'Café', unknown_pro, complete=True),
    ]
    errors = []
    page = browser.new_page(viewport={'width':1440, 'height':900})
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/*', handle)
    page.goto('http://wattline.test')
    toggle = page.locator('#rail-toggle')
    toggle.press('Enter')
    expect(toggle).to_have_attribute('aria-expanded', 'false')

    def button(identifier):
        return page.locator(f'#rail-nav [data-host="{identifier}"]')

    def check_model(identifier, kind, model, status):
        item = button(identifier)
        expect(item.locator(f'.status-dot.{status}')).to_be_visible()
        expect(item.locator('.machine-icon')).to_have_attribute('data-model', kind)
        assert model in item.get_attribute('title')
        return kind

    transitions = {
        'partial_online':check_model('partial', 'generic', b300, 'normal'),
        'trusted_online':check_model('trusted', 'b300', b300, 'normal'),
        'legacy_online':check_model('legacy-online', 'b300', b300, 'normal'),
        'legacy_offline':check_model('legacy-offline', 'generic', b300, 'offline'),
        'unknown_pro':check_model('accent-c', 'generic', unknown_pro, 'normal'),
    }
    aliases = {}
    for identifier, alias in [('accent-a', 'Café'), ('accent-b', 'Cafe\u0301'), ('accent-c', 'Café')]:
        item = button(identifier)
        suffix = item.locator('.machine-suffix')
        expect(suffix).to_be_visible()
        ordinal = suffix.inner_text()
        identity = item.get_attribute('title')
        assert identity.startswith(alias + ' · ') and identity.endswith(f' · 实例 {ordinal}')
        expect(item).to_have_accessible_name(identity)
        item.focus()
        expect(item).to_be_focused()
        focus_hint = item.evaluate("""el => el.matches(':focus-visible')
          && JSON.parse(getComputedStyle(el, '::after').content)""")
        assert focus_hint == identity
        aliases[identifier] = {'suffix':ordinal, 'identity':identity, 'focus_hint':focus_hint}
    assert len({entry['suffix'] for entry in aliases.values()}) == len(aliases), aliases

    machines[:2] = [
        host('partial', '部分清单', b300, 'offline', complete=False),
        host('trusted', '完整清单', b300, 'offline', complete=True),
    ]
    transitions['partial_offline'] = check_model('partial', 'generic', b300, 'offline')
    transitions['trusted_offline'] = check_model('trusted', 'b300', b300, 'offline')

    machines[:2] = [
        host('partial', '部分清单', b300, complete=True),
        dict(host('trusted', '完整清单', b300, complete=True), observed_at=1),
    ]
    transitions['partial_recovered'] = check_model('partial', 'b300', b300, 'normal')
    transitions['trusted_stale'] = check_model('trusted', 'b300', b300, 'stale')

    machines[0] = host('partial', '部分清单', b300, complete=False)
    transitions['complete_to_partial'] = check_model('partial', 'generic', b300, 'normal')
    assert not errors, errors
    page.close()
    return {'transitions':transitions, 'aliases':aliases, 'page_errors':errors}


def check_people_directory(browser):
    """Exercise the real API and old registry using a browser without a listening server."""
    first = Machine(id="assignment-test", name="Assignment fixture", mode="ssh",
                    ssh_alias="assignment.invalid", expected_host_id="a" * 32)
    second = Machine(id="second-test", name="Second fixture", mode="ssh",
                     ssh_alias="second.invalid", expected_host_id="b" * 32, enabled=False)
    origin = "http://localhost"
    assign_url = f"/api/machines/{first.id}/assignees"
    initial_name = "原登记"
    literal_name = "李工 <b>值班</b>"
    long_name = "LongUser" * 10
    layout_results = []
    with TemporaryDirectory() as directory:
        data_dir = Path(directory)
        history = History(data_dir)
        history.prepare()
        for host in (first, second):
            old = MachineSettings(enabled=host.enabled).model_dump(mode="json", exclude={"alias"}, exclude_unset=True)
            history.save_machine(host.history_key, None, json.dumps(dict(old, assigned_user=initial_name)), None, {})
        with history.connect() as db:
            for table in ("machine_observations","global_configuration","cluster_resources","resource_rooms","resource_order","clusters","rooms",
                          "storage_ticks","storage_resources","alerts","shared_users"):
                db.execute(f"DROP TABLE {table}")
            db.execute("DROP TABLE machine_assignees")
            db.execute("DROP TABLE people")
            db.execute("PRAGMA user_version=7")
        history.close()

        config = Config(data_dir=data_dir, machines=(first, second))
        monitor = Monitor(config)
        monitor.start_sampler = lambda _machine: None
        monitor.latest[first.id] = dict(status="offline", reason="synthetic offline", metrics=None)
        app = create_app(config, monitor=monitor)
        with TestClient(app, base_url=origin) as client:
            def snapshot():
                return client.get("/api/snapshot").json()

            def assignments():
                return [[person["name"] for person in machine["assigned_users"]] for machine in snapshot()["machines"]]

            def forward(route):
                request = route.request
                path = request.url.removeprefix(origin)
                if not path.startswith("/"):
                    return route.abort()
                headers = {name: value for name, value in request.headers.items()
                           if name in ("content-type", "sec-fetch-site")}
                response = client.request(request.method, path, headers=headers,
                                          content=request.post_data_buffer)
                if path == "/api/snapshot":
                    snapshot = response.json()
                    snapshot.pop("storage", None)
                    snapshot.pop("groups", None)
                    for device in snapshot["machines"]:
                        device.pop("assignment_mode", None)
                        device.pop("sources", None)
                    return route.fulfill(json=snapshot)
                if path.endswith("/assignees") and response.is_success:
                    updated = response.json()
                    updated.pop("assignment_mode", None)
                    return route.fulfill(json=updated)
                route.fulfill(status=response.status_code, body=response.content,
                              content_type=response.headers.get("content-type"))

            initial_person, = snapshot()["people"]
            assert assignments() == [[initial_name], [initial_name]]
            assert [node["status"] for node in snapshot()["machines"]] == ["offline", "disabled"]
            context = browser.new_context(permissions=["clipboard-read", "clipboard-write"],
                                          viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("**/*", forward)
            page.goto(origin)
            config_button = page.locator("[data-configure-machine]")
            assign_button = page.locator("[data-edit-assignees]")
            picker = page.locator("#assignee-dialog")
            directory_dialog = page.locator("#people-dialog")
            people_error = page.locator("#people-error")
            name_field = directory_dialog.locator("textarea")
            row = page.locator(f'[data-machine-row="{first.id}"]')

            def request(path, method, action, status):
                with page.expect_response(lambda response: response.url == origin + path
                                          and response.request.method == method) as pending:
                    action()
                response = pending.value
                assert response.status == status, (path, response.status, response.text())
                return response

            def checkbox(name):
                return picker.get_by_role("checkbox", name=name, exact=True)

            def expect_count(number):
                expect(picker.locator("#assignee-count")).to_have_text(
                    f"{number} selected" if page.locator("#locale-select").input_value() == "en" else f"已选 {number} 人")

            def save_assignments(status=200):
                return request(assign_url, "PUT", page.locator("#assignee-save").click, status)

            def paste(text):
                name_field.fill("")
                page.evaluate("(text) => navigator.clipboard.writeText(text)", text)
                name_field.press("ControlOrMeta+v")

            expect(row.locator(".assignee-cell .person-chip")).to_have_text(initial_name)
            expect(row.locator(".machine-identity .machine-assignees")).to_have_count(0)
            page.locator("[data-people-directory]").click()
            expect(directory_dialog.get_by_text(initial_name, exact=True)).to_be_visible()
            page.locator("#people-close").click()
            row.locator(".row-open").click()
            expect(page.locator(".page-title [data-edit-assignees]")).to_have_count(0)
            config_button.click()
            expect(assign_button).to_have_text("编辑使用者")
            assign_button.click()
            expect(checkbox(initial_name)).to_be_checked()
            expect_count(1)
            if page.evaluate("document.activeElement?.type === 'checkbox'"):
                page.keyboard.press("Tab")
                page.keyboard.press("Shift+Tab")
            else:
                for _ in range(10):
                    page.keyboard.press("Tab")
                    if page.evaluate("document.activeElement?.type === 'checkbox'"):
                        break
            focused_name = page.evaluate(
                "document.activeElement?.closest('.assignee-chip')?.querySelector('.assignee-chip-name')?.textContent")
            assert focused_name, page.evaluate("document.activeElement?.outerHTML")
            target = page.evaluate("""() => {
              const chip = document.activeElement.closest('.assignee-chip');
              const box = chip.getBoundingClientRect();
              return {width: box.width, height: box.height, outline: getComputedStyle(chip).outlineStyle};
            }""")
            assert target["width"] >= 44 and target["height"] >= 44, target
            assert target["outline"] != "none", target
            page.keyboard.press("Space")
            expect_count(0 if focused_name == initial_name else 2)
            page.keyboard.press("Space")
            expect_count(1)
            page.locator("#assignee-manage").click()
            expect(directory_dialog).to_be_visible()
            rename_url = f"/api/people/{initial_person['id']}"
            directory_dialog.get_by_role("button", name=f"为 {initial_name} 改名").click()
            expect(name_field).to_have_value(initial_name)

            rejected = [
                ("\u2028", "\u2028"), ("\u2029", "\u2029"),
                ("\u2028next", "\u2028next"), ("next\u2029", "next\u2029"),
                ("first\u2028second\u2029third", "first\u2028second\u2029third"),
                ("\n", "\n"), ("\r", "\n"), ("first\r\nsecond", "first\nsecond"),
                ("next\t", "next\t"), ("next\u0085", "next\u0085"),
                ("a" * 80 + "\u2028", "a" * 80 + "\u2028"), ("a" * 81, "a" * 81),
            ]
            for raw, draft in rejected:
                paste(raw)
                expect(name_field).to_have_value(draft)
                response = request(rename_url, "PUT", page.locator("#people-save").click, 422)
                assert response.request.post_data_json["name"] == draft
                expect(people_error).to_have_text("请填写不超过 80 个字符的单行姓名。")
                expect(name_field).to_have_value(draft)
                assert assignments() == [[initial_name], [initial_name]]

            paste("  " + literal_name + "  ")
            request(rename_url, "PUT", lambda: name_field.press("Enter"), 200)
            expect(directory_dialog.get_by_text(literal_name, exact=True)).to_be_visible()
            assert directory_dialog.locator("b").count() == 0
            assert assignments() == [[literal_name], [literal_name]]
            name_field.fill(long_name)
            long_person = request("/api/people", "POST", page.locator("#people-save").click, 201).json()
            name_field.fill("可移除人员")
            unused_person = request("/api/people", "POST", page.locator("#people-save").click, 201).json()
            request(rename_url, "DELETE", directory_dialog.get_by_role("button", name=f"移除 {literal_name}").click, 409)
            expect(people_error).to_contain_text("解除关联")
            assert assignments() == [[literal_name], [literal_name]]
            request(f"/api/people/{unused_person['id']}", "DELETE",
                    directory_dialog.get_by_role("button", name="移除 可移除人员").click, 204)
            expect(directory_dialog.get_by_text("可移除人员", exact=True)).to_have_count(0)
            page.locator("#people-close").click()
            expect(checkbox(literal_name)).to_be_checked()
            expect(checkbox(long_name)).not_to_be_checked()
            expect_count(1)
            checkbox(long_name).check()
            expect_count(2)
            page.locator("#assignee-cancel").click()
            assert assignments() == [[literal_name], [literal_name]]
            assign_button.click()
            expect(checkbox(long_name)).not_to_be_checked()
            expect_count(1)
            page.screenshot(path=str(OUT / "assignee-picker-zh-CN.png"))

            with history.connect() as db:
                db.execute(f"""CREATE TRIGGER fail_browser_assignment BEFORE INSERT ON machine_assignees
                           WHEN NEW.person = {long_person['id']}
                           BEGIN SELECT RAISE(ABORT, 'fixture failure'); END""")
            checkbox(long_name).check()
            expect_count(2)
            save_assignments(503)
            expect(picker).to_be_visible()
            expect(checkbox(long_name)).to_be_checked()
            expect_count(2)
            expect(page.locator("#assignee-error")).to_have_text("保存失败，请稍后重试。")
            expect(page.locator(".page-title .machine-assignees")).not_to_contain_text(long_name)
            assert assignments() == [[literal_name], [literal_name]]
            with history.connect() as db:
                assert history.people_and_assignees()[1] == {
                    first.history_key: (initial_person["id"],), second.history_key: (initial_person["id"],)
                }
                db.execute("DROP TRIGGER fail_browser_assignment")
            save_assignments()
            expect(picker).not_to_be_visible()
            assert set(assignments()[0]) == {literal_name, long_name}
            assert assignments()[1] == [literal_name]

            expect(page.locator("#machine-dialog")).to_be_visible()
            expect(page.locator("#machine-dialog textarea")).to_have_count(0)
            page.locator("#machine-dialog input[name=alias]").fill("Renamed fixture")
            settings = request(f"/api/machines/{first.id}/settings", "PUT", page.locator("#machine-save").click, 200)
            assert "assigned_user" not in settings.request.post_data_json
            expect(page.locator("#page-heading")).to_have_text("Renamed fixture")
            assert set(assignments()[0]) == {literal_name, long_name}

            def inspect_summary(summary, label, width):
                expect(summary).to_be_visible()
                for value in (label, literal_name, long_name):
                    expect(summary).to_contain_text(value)
                expect(summary).to_contain_text(long_name + ("和" if label == "使用者：" else " and ") + literal_name)
                assert summary.locator("b").count() == 0
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                box = summary.evaluate("""el => ({
                  right: el.getBoundingClientRect().right, width: el.clientWidth, scrollWidth: el.scrollWidth,
                  height: el.clientHeight, scrollHeight: el.scrollHeight,
                })""")
                assert box["right"] <= width and box["scrollWidth"] <= box["width"], box
                assert box["scrollHeight"] <= box["height"], box
                return box

            def inspect_listing(cell, label, width):
                expect(cell).to_be_visible()
                chips = cell.locator(".person-chip")
                expect(chips).to_have_count(2)
                for value in (literal_name, long_name):
                    expect(cell).to_contain_text(value)
                assert cell.locator("b").count() == 0
                assert label not in cell.inner_text(), cell.inner_text()
                assert cell.get_attribute("data-label") == label.rstrip("：:"), cell.get_attribute("data-label")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                box = cell.evaluate("""el => ({
                  right: el.getBoundingClientRect().right, width: el.clientWidth, scrollWidth: el.scrollWidth,
                  height: el.clientHeight, scrollHeight: el.scrollHeight,
                })""")
                assert box["right"] <= width and box["scrollWidth"] <= box["width"], box
                assert box["scrollHeight"] <= box["height"], box
                chip_boxes = chips.evaluate_all("""els => els.map(el => {
                  const box = el.getBoundingClientRect();
                  return {right: box.right, width: el.clientWidth, scrollWidth: el.scrollWidth};
                })""")
                assert all(chip["right"] <= width and chip["scrollWidth"] <= chip["width"]
                           for chip in chip_boxes), chip_boxes
                return box

            for locale, label in (("zh-CN", "使用者："), ("en", "Assignees:")):
                page.locator("#locale-select").select_option(locale)
                for width in (1440, 320):
                    page.set_viewport_size({"width": width, "height": 900})
                    detail = inspect_summary(page.locator(".page-title .machine-assignees"), label, width)
                    expect(config_button).to_be_visible()
                    expect(assign_button).to_be_hidden()
                    if width == 320:
                        page.screenshot(path=str(OUT / f"assignees-detail-{locale}.png"), full_page=True)
                    page.locator("#breadcrumb [data-overview]").click()
                    headers = [text.strip() for text in page.locator(".machine-table thead th").all_inner_texts()]
                    assert headers[:3] == (["机器", "状态", "使用者"] if locale == "zh-CN"
                                           else ["Machine", "Status", "Assignees"]), headers
                    listing = inspect_listing(row.locator(".assignee-cell"), label, width)
                    if width == 1440:
                        page.locator(".machine-scroll").screenshot(path=str(OUT / f"assignees-list-desktop-{locale}.png"))
                    if width == 320:
                        page.locator(".machine-scroll").screenshot(path=str(OUT / f"assignees-list-{locale}.png"))
                    layout_results.append({"locale": locale, "width": width, "detail": detail, "list": listing})
                    row.locator(".row-open").click()

            config_button.click()
            assign_button.click()
            expect(picker.get_by_role("heading", name="Assignees")).to_be_visible()
            expect(checkbox(literal_name)).to_be_checked()
            expect(checkbox(long_name)).to_be_checked()
            expect_count(2)
            checkbox(literal_name).uncheck()
            expect_count(1)
            picker.get_by_role("button", name="People directory").click()
            expect(directory_dialog.get_by_role("heading", name="People directory")).to_be_visible()
            expect(directory_dialog.get_by_text(long_name, exact=True)).to_be_visible()
            directory_dialog.get_by_role("button", name="Close directory").click()
            expect(checkbox(literal_name)).not_to_be_checked()
            expect_count(1)
            save_assignments()
            expect(page.locator("#machine-assignment-preview")).to_have_text(long_name)
            assert assignments() == [[long_name], [literal_name]]
            assign_button.click()
            expect_count(1)
            page.get_by_role("button", name="Clear selection").click()
            expect_count(0)
            save_assignments()
            expect(page.locator("#machine-assignment-preview")).to_have_text("Not assigned")
            page.locator("#machine-cancel").click()
            expect(page.locator(".page-title .machine-assignees")).to_have_count(0)
            page.locator("#breadcrumb [data-overview]").click()
            expect(row.locator(".assignee-cell .person-chip")).to_have_count(0)
            expect(row.locator(".assignee-cell .unassigned")).to_have_text("Not assigned")
            assert assignments() == [[], [literal_name]]
            assert not errors, errors
            context.close()
    return {"legacy_migration": True, "offline_assignment": True, "invalid_name_submissions": len(rejected),
            "assignment_write_failure": 503, "linked_person_removal": 409, "layouts": layout_results,
            "directory_rename_add_remove": True, "cancel_multi_select_deselect_clear": True}


def check_assignee_responsive(browser):
    """Keep long metrics and literal names visible across the list layout switch."""
    origin = "http://localhost"
    spaced_names = ("Ada Lovelace", "Ada  Lovelace")
    long_name = "W" * 80
    literal_name = '字面 " <b>名</b> & 姓'
    names = (*spaced_names, long_name, literal_name)
    layouts, boundaries, spacing = [], [], []
    with TemporaryDirectory() as directory:
        hosts = (Machine(id="active", name="Machine" * 11 + "ABC", mode="ssh",
                         ssh_alias="w" * 63 + ".invalid", expected_host_id="a" * 32),
                 Machine(id="idle", name="Synthetic unassigned", mode="ssh",
                         ssh_alias="idle.invalid", expected_host_id="b" * 32))
        config = Config(data_dir=Path(directory), machines=hosts)
        monitor = Monitor(config, clock=lambda: 1800000000000)
        monitor.start_sampler = lambda _machine: None
        monitor.latest["active"] = dict(
            status="warning", observed_at=monitor.clock(),
            metrics=dict(gpus=[], gpu_percent=76, gpu_power_w=123456789012, cpu_count=128,
                         cpu_percent=100, load_average=[120, 91, 81], memory_percent=90,
                         memory=dict(used_bytes=18000000 * 1024**3, total_bytes=20000000 * 1024**3)))
        monitor.latest["idle"] = dict(status="offline", metrics=None)
        with TestClient(create_app(config, monitor=monitor), base_url=origin) as client:
            person_ids = []
            for name in names:
                response = client.post("/api/people", json={"name": name})
                response.raise_for_status()
                person_ids.append(response.json()["id"])
            client.put("/api/machines/active/assignees",
                       json={"person_ids": person_ids}).raise_for_status()

            def forward(route):
                request = route.request
                path = request.url.removeprefix(origin)
                if not path.startswith("/"):
                    return route.abort()
                headers = {name: value for name, value in request.headers.items()
                           if name in ("content-type", "sec-fetch-site")}
                response = client.request(request.method, path, headers=headers,
                                          content=request.post_data_buffer)
                if path == "/api/snapshot":
                    snapshot = response.json()
                    snapshot.pop("groups", None)
                    return route.fulfill(json=snapshot)
                route.fulfill(status=response.status_code, body=response.content,
                              content_type=response.headers.get("content-type"))

            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("**/*", forward)
            page.goto(origin)
            expect(page.locator("[data-machine-row]")).to_have_count(2)
            region = page.locator(".machine-scroll")
            row = page.locator('[data-machine-row="active"]')
            expect(row.locator('[data-value="active-memory-used"]')).to_have_text("18000000.0 GiB")
            cell = row.locator(".assignee-cell")
            picker = page.locator("#assignee-dialog")

            def resize(width):
                page.set_viewport_size({"width": width, "height": 900})

            def cards():
                return page.locator(".machine-table thead").evaluate(
                    'header => getComputedStyle(header).display === "none"')

            def check_layout(locale, rail, width):
                resize(width)
                box = region.evaluate("""region => {
                  const table = region.querySelector('table');
                  const card = getComputedStyle(table.tHead).display === 'none';
                  const edge = region.getBoundingClientRect();
                  const within = (rect, bounds) =>
                    rect.left >= bounds.left - .5 && rect.right <= bounds.right + .5;
                  const textRects = element => {
                    const range = document.createRange();
                    range.selectNodeContents(element);
                    return [...range.getClientRects()];
                  };
                  const cells = [...table.querySelectorAll('tbody td')];
                  const identityIssues = [];
                  for (const row of table.querySelectorAll('tbody tr[data-machine-row]')) {
                    const td = row.querySelector('td');
                    const open = td.querySelector('.row-open');
                    const statusCell = row.querySelector('.status-cell');
                    const badge = row.querySelector('.status');
                    const tdBox = td.getBoundingClientRect();
                    const tdStyle = getComputedStyle(td);
                    const contentBox = {
                      left: tdBox.left + parseFloat(tdStyle.paddingLeft),
                      right: tdBox.right - parseFloat(tdStyle.paddingRight),
                    };
                    const openBox = open.getBoundingClientRect();
                    const textWrap = open.querySelector(':scope > span:last-child');
                    const parts = [td.querySelector('.machine-cell'), td.querySelector('.machine-identity'),
                                   open, textWrap, ...open.querySelectorAll('strong, small')];
                    if (parts.some(el => !within(el.getBoundingClientRect(), contentBox))) {
                      identityIssues.push({row: row.dataset.machineRow, reason: 'box-overflow',
                        contentRight: +contentBox.right.toFixed(2), openRight: +openBox.right.toFixed(2)});
                    }
                    if (!card) {
                      const statusLeft = Math.min(statusCell.getBoundingClientRect().left,
                                                  badge.getBoundingClientRect().left);
                      if (openBox.right > statusLeft + .5) {
                        identityIssues.push({row: row.dataset.machineRow, reason: 'overlaps-status',
                          openRight: +openBox.right.toFixed(2), statusLeft: +statusLeft.toFixed(2)});
                      }
                      for (const el of open.querySelectorAll('strong, small')) {
                        const cs = getComputedStyle(el);
                        const er = el.getBoundingClientRect();
                        if (cs.overflowX !== 'hidden' || cs.textOverflow !== 'ellipsis') {
                          identityIssues.push({row: row.dataset.machineRow, reason: 'missing-ellipsis',
                            tag: el.localName, overflowX: cs.overflowX, textOverflow: cs.textOverflow});
                        }
                        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
                        const range = document.createRange();
                        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                          for (let i = 0; i < node.length; i++) {
                            range.setStart(node, i);
                            range.setEnd(node, i + 1);
                            const gr = range.getBoundingClientRect();
                            const paintedRight = cs.overflowX === 'hidden' ? Math.min(gr.right, er.right) : gr.right;
                            if (gr.left < er.right - .5 && paintedRight > tdBox.right + .5) {
                              identityIssues.push({row: row.dataset.machineRow, reason: 'glyph-past-cell',
                                tag: el.localName, glyphRight: +paintedRight.toFixed(2), tdRight: +tdBox.right.toFixed(2)});
                              break;
                            }
                          }
                        }
                      }
                    }
                  }
                  return {card, container: region.clientWidth, scrollWidth: region.scrollWidth,
                          pageWidth: document.documentElement.scrollWidth,
                          identityIssues,
                          overflowing: cells.filter(cell => {
                            const bounds = cell.getBoundingClientRect();
                            const wraps = card || !cell.querySelector('.row-open');
                            return !within(bounds, edge) ||
                              (wraps && textRects(cell).some(rect => !within(rect, bounds)));
                          }).map(cell => cell.textContent.trim()),
                          metrics: [...table.querySelectorAll('[data-machine-row="active"] .number-cell')]
                            .map(cell => ({label: cell.dataset.label, text: cell.textContent.trim(),
                                 labelled: getComputedStyle(cell, '::before').content !== 'none'}))};
                }""")
                result = {"locale": locale, "rail": rail, "width": width, **box}
                assert box["scrollWidth"] == box["container"] and box["pageWidth"] <= width, result
                assert not box["overflowing"], result
                assert not box["identityIssues"], result
                assert len(box["metrics"]) == 4, result
                memory = "18000000.0 GiB used" if locale == "en" else "18000000.0 GiB 已用"
                for metric, value in zip(box["metrics"], ("76%", "123456789012 W", "100%", memory)):
                    assert value in metric["text"] and metric["label"], result
                    assert metric["labelled"] == box["card"], result
                return result

            def check_names(surface, width=None, lines=None):
                values = surface.evaluate_all(r"""(elements, width) => elements.map(element => {
                  if (width !== null && element.textContent.startsWith('Ada')) element.style.width = width + 'px';
                  const box = element.getBoundingClientRect();
                  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
                  const range = document.createRange();
                  const glyphs = [];
                  let fits = true;
                  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                    for (let i = 0; i < node.length; i++) {
                      if (/\s/u.test(node.data[i])) continue;
                      range.setStart(node, i);
                      range.setEnd(node, i + 1);
                      const glyph = range.getBoundingClientRect();
                      glyphs.push([Math.round((glyph.left - box.left) * 100) / 100,
                                   Math.round((glyph.top - box.top) * 100) / 100]);
                      fits &&= glyph.left >= box.left - .5 && glyph.right <= box.right + .5;
                    }
                  }
                  return {name: element.textContent, glyphs, fits,
                          lines: new Set(glyphs.map(([, y]) => y)).size};
                })""", width)
                assert set(value["name"] for value in values) == set(names), values
                assert all(value["fits"] for value in values), values
                mapping = {value["name"]: value for value in values}
                first, second = (mapping[name] for name in spaced_names)
                if width is not None:
                    assert min(first["lines"], second["lines"]) >= 2, (first, second)
                    if lines is not None:
                        assert first["lines"] == second["lines"] == lines, (first, second)
                    assert second["glyphs"][3][0] > first["glyphs"][3][0], (first, second)
                assert first["glyphs"] != second["glyphs"], (first, second)
                assert mapping[long_name]["lines"] > 1, mapping[long_name]
                assert surface.locator("b").count() == 0
                return {name: mapping[name] for name in spaced_names}

            for rail in ("expanded", "collapsed"):
                resize(1440)
                if rail == "collapsed":
                    page.locator("#rail-toggle").click()
                    expect(page.locator("#rail-toggle")).to_have_attribute("aria-expanded", "false")
                for locale, headers in (("en", ["Machine", "Status", "Assignees"]),
                                        ("zh-CN", ["机器", "状态", "使用者"])):
                    page.locator("#locale-select").select_option(locale)
                    for width in (320, 700, 730, 950, 986, 1024, 1080, 1140, 1156, 1200, 1260, 1310, 1440):
                        result = check_layout(locale, rail, width)
                        layouts.append(result)
                        if width in (320, 1440):
                            assert result["card"] == (width == 320), result
                    assert page.locator(".machine-table thead th").all_inner_texts()[:3] == headers
                    expected_open_name = (f"View {hosts[0].name}" if locale == "en" else f"查看 {hosts[0].name}")
                    expect(row.locator(".row-open")).to_have_accessible_name(expected_open_name)
                    low, high = 730, 1440
                    while high - low > 1:
                        middle = (low + high) // 2
                        resize(middle)
                        if cards():
                            low = middle
                        else:
                            high = middle
                    # Check each viewport on the way down and back up across the switch.
                    widths = range(high + 12, low - 13, -1)
                    for width in (*widths, *reversed(widths)):
                        result = check_layout(locale, rail, width)
                        assert result["card"] == (width <= low), result
                    boundaries.append({"locale": locale, "rail": rail, "last_card": low, "first_table": high})

                    resize(high)
                    list_chips = cell.locator(".person-chip")
                    list_spacing = check_names(list_chips)
                    if locale == "en" and rail == "expanded":
                        region.screenshot(path=str(OUT / "assignee-responsive-boundary-en.png"))
                    # Keep the AN-137 two-line case even if future columns have more room.
                    list_wrapped = check_names(list_chips, width=80, lines=2)
                    if locale == "en" and rail == "expanded":
                        cell.screenshot(path=str(OUT / "assignee-chip-spacing.png"))
                    check_names(list_chips, width=70)
                    row.locator(".row-open").click()
                    page.locator("[data-configure-machine]").click()
                    edit = page.locator("[data-edit-assignees]")
                    edit.click()
                    expect(picker.locator("input:checked")).to_have_count(len(names))
                    for name, person_id in zip(names, person_ids):
                        checkbox = picker.locator(f'input[value="{person_id}"]')
                        expect(checkbox).to_have_attribute("aria-label", name)
                        expect(checkbox).to_have_accessible_name(name)
                    picker_chips = picker.locator(".assignee-chip-name")
                    picker_spacing = check_names(picker_chips)
                    picker_wrapped = check_names(picker_chips, width=65, lines=2)
                    if locale == "en" and rail == "expanded":
                        picker.screenshot(path=str(OUT / "assignee-picker-wrapped-en.png"))
                    check_names(picker_chips, width=56)
                    page.locator("#assignee-cancel").click()
                    expect(edit).to_be_focused()
                    page.locator("#machine-cancel").click()
                    page.locator("#breadcrumb [data-overview]").click()
                    spacing.append({"locale": locale, "rail": rail, "list": list_spacing,
                                    "list_wrapped": list_wrapped, "picker": picker_spacing,
                                    "picker_wrapped": picker_wrapped})

            assert not errors, errors
            context.close()
    return {"spacing": spacing, "layouts": layouts, "boundaries": boundaries}

def check_archive_analysis(browser):
    zone = ZoneInfo('Asia/Shanghai')
    midnight = int(datetime(2026, 10, 2, tzinfo=zone).timestamp()) * 1000
    day = 86400000
    with patch.dict(globals(), machines=[node(1), node(2), node(3, 'offline')], mode='normal'), TemporaryDirectory() as directory:
        hosts = tuple(Machine(id=f'demo-{index}', mode='ssh', ssh_alias=f'demo-{index}',
                              expected_host_id=str(index)*32, enabled=False) for index in (1, 2, 3))
        config = Config(data_dir=Path(directory), machines=hosts, archive_timezone=zone.key)
        store = History(config.data_dir)
        store.prepare()

        def append(host, at, value):
            store.append(host.history_key, 'fixture', dict(observed_at=at, received_at=at,
                         boot='fixture', status='normal', source='ssh', metrics={'cpu_percent':value}))

        def publish(cutoff):
            slot = store.begin_archive(cutoff + WARM_MS)
            store.pack(cutoff)
            exported = store.export(cutoff)
            store.finish_archive(slot, cutoff, exported)
            return store.cold_directory / exported.filename

        append(hosts[0], midnight, 21)
        append(hosts[1], midnight, 98)
        first = publish(midnight + 3600000)
        append(hosts[0], midnight + day - 1, 24)
        append(hosts[0], midnight + day, 35)
        second = publish(midnight + 2 * day)
        store.close()
        original = second.read_bytes()
        second.write_bytes(original[:-4])
        release = Event()
        rows = ArchiveAnalysis.rows

        def hold_first_progress(job, files, identity, notify):
            def progress(value):
                notify(value)
                if not release.is_set():
                    assert release.wait(10)
            yield from rows(job, files, identity, progress)

        monitor = Monitor(config, clock=lambda: midnight + 2 * day + WARM_MS)
        app = create_app(config, monitor=monitor)
        with patch.object(ArchiveAnalysis, 'rows', hold_first_progress), TestClient(
                app, base_url='http://127.0.0.1') as client:
            context = browser.new_context(viewport={'width':390, 'height':844}, timezone_id='America/Los_Angeles')
            page = context.new_page()
            errors, requests = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))

            def route_archive(route):
                url = urlsplit(route.request.url)
                if '/archive-analysis' not in url.path:
                    return handle(route)
                method = route.request.method
                requests.append((method, url.path))
                options = {'json':route.request.post_data_json} if method == 'POST' else {}
                response = client.request(method, url.path + ('?' + url.query if url.query else ''), **options)
                route.fulfill(status=response.status_code, json=response.json())

            page.route('**/*', route_archive)
            try:
                page.goto('http://wattline.test')
                expect(page.locator('#host-rows tr')).to_have_count(3)
                expect(page.locator('#open-archive')).to_have_count(0)
                assert requests == []
                page.locator('#rail-nav [data-host="demo-1"]').click()
                entry = page.locator('#open-archive')
                expect(entry).to_have_accessible_name('历史归档分析')
                page.locator('#focus-trends').click()
                expect(entry).to_have_count(0)
                page.keyboard.press('Escape')
                page.get_by_role('button', name='查看 GPU 0', exact=True).click()
                page.locator('[data-gpu-trends]').click()
                expect(entry).to_have_count(0)
                page.locator('[data-all-gpus]').click()
                expect(page.locator('#chart-summary')).to_contain_text('CPU')
                page.locator('#locale-select').select_option('en')
                expect(entry).to_have_accessible_name('Archive analysis')
                entry.click()
                expect(page.get_by_role('heading', name='Archive analysis')).to_be_focused()
                bar = page.get_by_role('progressbar', name='Decompressing history archives')
                partial = first.stat().st_size * 100 // (first.stat().st_size + second.stat().st_size)
                expect(bar).to_have_attribute('value', str(partial))
                expect(page.locator('#archive-percent')).to_have_text(f'{partial}%')
                release.set()

                expect(page.get_by_text('The archive could not be prepared. You can retry.')).to_be_visible()
                assert second.read_bytes() == original[:-4]
                second.write_bytes(original)
                page.get_by_role('button', name='Decompress again').click()
                expect(page.locator('#archive-start')).to_have_value('2026-10-02')
                expect(page.locator('#archive-end')).to_have_value('2026-10-03')
                expect(page.get_by_text('Archive time zone Asia/Shanghai')).to_be_visible()
                expect(page.locator('#chart-summary')).to_contain_text('35.0%')
                page.locator('#archive-end').fill('2026-10-02')
                apply = page.get_by_role('button', name='Apply filters')
                apply.click()
                expect(page.locator('#chart-summary')).to_contain_text('24.0%')
                page.get_by_text('View chart data', exact=True).click()
                rows_on_page = page.locator('#chart-data tbody tr')
                expect(rows_on_page).to_have_count(2)
                expect(rows_on_page.first).to_contain_text('10/02/2026, 00:00:00')
                expect(rows_on_page.first).to_contain_text('21.0%')
                expect(rows_on_page.last).to_contain_text('23:59:59')
                expect(rows_on_page.last).to_contain_text('24.0%')
                expect(page.locator('#chart-data')).not_to_contain_text('98.0%')
                page.screenshot(path=str(OUT/'archive-analysis.png'), full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')

                page.locator('#archive-start').fill('2026-10-04')
                apply.click()
                expect(page.get_by_text('The start date must be on or before the end date.')).to_be_visible()
                page.locator('#archive-end').fill('2026-10-04')
                apply.click()
                expect(page.locator('#chart-summary')).to_have_text('No valid samples in this window.')
                page.get_by_role('button', name='Back to machine').click()
                expect(entry).to_be_focused()
                expect(page.locator('#chart-summary')).to_contain_text('CPU')
                page.locator('#rail-nav [data-host="demo-3"]').click()
                entry.click()
                expect(page.get_by_text('This machine has no archived history.')).to_be_visible()
                assert not errors, errors
                assert first.exists() and second.read_bytes() == original
                return {'progress':partial, 'range_rows':2, 'timezone':zone.key, 'retry':True,
                        'no_archive':True, 'no_samples':True, 'entry_only':True, 'requests':len(requests)}
            finally:
                release.set()
                context.close()


with sync_playwright() as p:
    browser = p.chromium.launch(**({"executable_path":args.browser} if args.browser else {}))
    people_directory = check_people_directory(browser)
    assignee_responsive = check_assignee_responsive(browser)
    page = browser.new_page(viewport={"width":1440,"height":1100}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/*", handle)
    page.goto("http://wattline.test")
    expect(page.locator("#host-rows tr")).to_have_count(3)
    alpha_row = page.locator('#host-rows tr[data-machine-row="demo-1"]')
    beta_row = page.locator('#host-rows tr[data-machine-row="demo-2"]')
    expect(alpha_row.locator(".assignee-cell .person-chip")).to_have_text("张工")
    expect(alpha_row.locator(".machine-identity .machine-assignees")).to_have_count(0)
    expect(beta_row.locator(".assignee-cell .unassigned")).to_have_text("未登记")
    headers = [text.strip() for text in page.locator(".machine-table thead th").all_inner_texts()]
    assert headers[:3] == ["机器", "状态", "使用者"], headers
    page.locator('#locale-select').select_option('en')
    expect(alpha_row.locator(".assignee-cell .person-chip")).to_have_text("张工")
    expect(beta_row.locator(".assignee-cell .unassigned")).to_have_text("Not assigned")
    headers = [text.strip() for text in page.locator(".machine-table thead th").all_inner_texts()]
    assert headers[:3] == ["Machine", "Status", "Assignees"], headers
    page.locator('#locale-select').select_option('zh-CN')
    expect(page.locator("#chart-summary")).to_contain_text("11 个有效时段")
    def assert_card_stack():
        cards = [page.locator(selector).bounding_box()
                 for selector in ('.attention-panel','.chart-panel','.machine-panel')]
        assert all(cards), cards
        for upper, lower in zip(cards, cards[1:]):
            assert upper["y"] + upper["height"] <= lower["y"], cards
            assert upper["x"] == lower["x"] and upper["width"] == lower["width"], cards

    assert_card_stack()
    legend = page.locator("#chart-legend")
    expect(legend).to_contain_text("训练节点 Alpha")
    expect(legend).to_contain_text("推理节点 Beta")
    expect(legend).to_contain_text("离线节点 Gamma")
    expect(legend).not_to_contain_text("平均")
    gpu_button = page.locator('[data-overview-metric="gpu"]')
    expect(gpu_button).to_have_attribute("aria-pressed","true")
    assert history_queries[-1] == {"metric":"gpu","hours":24,"machine":None}, history_queries[-1]
    page.locator("#trend-chart").focus()
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#chart-announcement")).to_contain_text("训练节点 Alpha")
    page.locator('[data-overview-metric="cpu"]').click()
    expect(page.locator('[data-overview-metric="cpu"]')).to_have_attribute("aria-pressed","true")
    page.wait_for_function("state.history?.keys[0] === 'cpu'")
    assert history_queries[-1] == {"metric":"cpu","hours":24,"machine":None}, history_queries[-1]
    page.locator('[data-overview-metric="memory"]').click()
    expect(page.locator('[data-overview-metric="memory"]')).to_have_attribute("aria-pressed","true")
    page.wait_for_function("state.history?.keys[0] === 'memory'")
    assert history_queries[-1] == {"metric":"memory","hours":24,"machine":None}, history_queries[-1]
    page.locator('[data-overview-metric="power"]').click()
    expect(page.locator('[data-overview-metric="power"]')).to_have_attribute("aria-pressed","true")
    page.wait_for_function("state.history?.keys[0] === 'power'")
    expect(legend).to_contain_text(" · W")
    page.locator('[data-overview-metric="gpu"]').click()
    page.wait_for_function("state.history?.keys[0] === 'gpu'")
    # Same display names must stay distinguishable by address.
    page.evaluate("state.snapshot.machines[1].name = state.snapshot.machines[0].name; renderPage(); paint()")
    expect(legend).to_contain_text("demo-1.invalid")
    expect(legend).to_contain_text("demo-2.invalid")
    page.locator(".chart-panel").screenshot(path=str(OUT/"overview-trend.png"))
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
    # Both live rows expose the same physical UUID in this fixture.
    expect(page.locator('.metric [data-value="watts"]')).to_have_text("1,234")
    expect(page.locator('.metric [data-value="rated-watts"]')).to_have_text("—")
    layout_results = []
    for width in layout_widths:
        page.set_viewport_size({"width":width,"height":1100})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
        tiles = page.locator(".overview-metrics > .metric").evaluate_all("""tiles => tiles.flatMap(tile => {
          const card = tile.getBoundingClientRect();
          return [...tile.querySelectorAll('strong .value')].map(value => {
            const range = document.createRange();
            range.selectNodeContents(value);
            const text = range.getBoundingClientRect();
            return {value: value.textContent, left: text.left, right: text.right,
                    cardLeft: card.left, cardRight: card.right,
                    fits: text.left >= card.left && text.right <= card.right};
          });
        })""")
        assert page.locator(".overview-metrics > .metric").count() == 3
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
    expect(page.locator(".page-title")).to_contain_text("使用者：张工")
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
    expect(page.locator(".page-title")).to_contain_text("使用者：张工")
    page.get_by_role("button", name="配置", exact=True).click()
    page.get_by_role("button", name="移除节点", exact=True).click()
    expect(page.locator("#remove-cancel")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.get_by_role("button", name="移除节点", exact=True)).to_be_focused()
    page.locator("#machine-cancel").click()
    page.screenshot(path=str(OUT/"detail.png"), full_page=True)
    page.get_by_role("button", name="机器总览", exact=True).first.click()
    page.wait_for_function("!state.machine && state.history?.machines?.length === 3")
    expect(page.locator('#host-rows tr[data-machine-row="demo-1"] .assignee-cell .person-chip')).to_have_text("张工")
    assert history_queries[-1]["machine"] is None and history_queries[-1]["hours"] == 24, history_queries[-1]
    page.set_viewport_size({"width":390,"height":844})
    assert_card_stack()
    page.screenshot(path=str(OUT/"mobile.png"))
    page.locator(".machine-scroll").screenshot(path=str(OUT/"mobile-list.png"))
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    expect(page.locator('#host-rows tr[data-machine-row="demo-1"] [data-label="使用者"]')).to_be_visible()
    expect(page.locator('#host-rows tr[data-machine-row="demo-1"] .person-chip')).to_have_text("张工")
    expect(page.locator('#host-rows tr[data-machine-row="demo-1"] [data-label="内存"]')).to_be_visible()
    expect(page.locator('#host-rows tr[data-machine-row="demo-1"] .memory-used')).to_contain_text("48.0 GiB 已用")
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
    expect(page.locator("#chart-summary")).to_have_text("暂无启用机器")
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
        assert_card_stack()
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
    page.get_by_role('button',name='Configure',exact=True).click()
    page.get_by_role('button',name='Remove node',exact=True).click()
    expect(page.locator('#remove-description')).to_contain_text('This cannot be undone.')
    page.get_by_role('button',name='Confirm removal',exact=True).click()
    expect(page.locator('#remove-error')).to_contain_text('Could not remove.')
    expect(page.locator('#remove-error')).to_contain_text('合成验证错误')
    page.keyboard.press('Escape')
    page.locator('#machine-cancel').click()
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
    expect(page.locator('#chart-summary')).to_have_text('No enabled machines')
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
    gpu_tolerance = check_gpu_tolerance_settings(browser)
    unlimited_container = check_unlimited_container(browser)
    windows_processes = check_windows_processes(browser)
    gpu_process_timing = check_gpu_process_timing(browser)
    focus_layout = check_focus_layout(browser)
    overview_regressions = check_overview_regressions(browser)
    silhouettes = check_machine_silhouettes(browser)
    rail_identity_edges = check_rail_identity_edges(browser)
    print(json.dumps({"archive_analysis":check_archive_analysis(browser)}, ensure_ascii=False))
    print(json.dumps({"focus_layout":focus_layout,"result":"PASS", "browser":browser.version, "page_errors":errors,
                      "mutations":len(mutations), "history_queries":len(history_queries), "screenshots":28, "locales":["zh-CN","en"], "dialog_locales":dialog_locales,
                      "metric_layouts":layout_results, "focus_refreshes":focus_results,
                      "people_directory":people_directory, "assignee_responsive":assignee_responsive,
                      "unlimited_container":unlimited_container,"gpu_process_timing":gpu_process_timing,
                      "windows_processes":windows_processes, "gpu_tolerance":gpu_tolerance, "overview_regressions":overview_regressions,
                      "silhouettes":silhouettes, "rail_identity_edges":rail_identity_edges}, ensure_ascii=False))
    browser.close()
