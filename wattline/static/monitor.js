
'use strict';

const i18n = WattlineI18n;
const t = i18n.t;
i18n.apply();
const byId = id => document.getElementById(id);
const fmt = (value, unit = '', digits = 0) => Number.isFinite(value) ? i18n.number(value, {minimumFractionDigits:digits, maximumFractionDigits:digits, useGrouping:false}) + unit : '—';
const gib = bytes => bytes == null ? null : bytes / 1024 ** 3;
const vram = mib => mib == null ? null : mib / 1024;
const time = value => Number.isFinite(value) ? i18n.date(value, {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}) : '—';
const shortTime = ({format:value => i18n.date(value, {hour:'2-digit', minute:'2-digit', hour12:false})});
const shortDate = ({format:value => i18n.date(value, {month:'2-digit', day:'2-digit'})});
const tooltipTime = ({format:value => i18n.date(value, {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false})});
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const escape = value => String(value ?? '').replace(/[&<>"']/g, character =>
  ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[character]);
let machineStates, gpuStates, workloads, descriptors, colors, powerModes;
function localizeLabels() {
  machineStates = {normal:t('healthy'), warning:t('needs_attention'), offline:t('connection_failed'), stale:t('stale'),
    unknown:t('unverified'), disabled:t('disabled'), waiting:t('awaiting_sample')};
  gpuStates = {occupied:t('in_use'), free:t('no_usage_seen'), unknown:t('usage_unknown')};
  workloads = {host:t('host_process'), docker:'Docker', kubernetes:'Pod', containerd:'containerd', 'cri-o':'CRI-O'};
  descriptors = {cpu:[t('cpu_usage'),'%'], memory:[t('memory_usage'),'%'], memory_used:[t('memory_used'),' GiB'], gpu:[t('gpu_utilization'),'%'],
    power:[t('gpu_power'),' W'], vram:[t('vram_used'),' GiB'], temp:[t('gpu_temperature'),' °C']};
  colors = {cpu:'#0b836a', memory:'#456ab4', memory_used:'#456ab4', gpu:'#506dc3', power:'#0b836a', temp:'#b16e23', vram:'#8b57a2'};
  powerModes = {average:t('average_power'), instantaneous:t('instantaneous_power'), reported:t('driver_reported_power')};
}
localizeLabels();
const machineIcon = '<span class="machine-icon" aria-hidden="true"><i></i><i></i></span>';
const state = {snapshot:null, received:0, syncFailed:false, machine:null, gpu:null, metric:'cpu',
  hours:24, filter:'all', query:'', history:null, historyError:false};
let layoutKey = '';
let chart = null;
let historyRequest = null;
let snapshotRevision = 0;
let rowDrag = null;
let orderSaving = false;
let orderMessage = '';

const status = (tone, label) => `<span class="status ${escape(tone)}"><span class="status-dot" aria-hidden="true"></span>${escape(label)}</span>`;
const field = key => `<span data-value="${escape(key)}" class="value">—</span>`;
const meter = (key, kind = '') => `<span data-meter="${escape(key)}" class="meter ${kind}" hidden aria-hidden="true"></span>`;
const metricTile = (name, key, suffix, icon, foot) => `<article class="metric">
  <p class="metric-name"><span>${escape(name)}</span><span aria-hidden="true">${icon}</span></p>
  <strong>${field(key)}</strong>${suffix ? '<span class="unit">' + suffix + '</span>' : ''}
  <small>${foot}</small>
</article>`;
const toggle = (label, attr, value, active) => `<button type="button" ${attr}="${value}" aria-pressed="${active}">${label}</button>`;
const heading = (title, badge = '') => `<div class="title-line"><h1 id="page-heading" tabindex="-1">${escape(title)}</h1>${badge}</div>`;

function nodes() {
  if (!state.snapshot) return [];
  const { server_time, stale_ms, machines } = state.snapshot;
  const now = server_time + performance.now() - state.received;
  return machines.map(node => node.metrics && now - node.observed_at >= (node.stale_ms ?? stale_ms)
    ? {...node, metrics:null, status:'stale', reason:t('valid_sample_expired_awaiting_a_new_sample'), warnings:[]} : node);
}

const getHost = () => nodes().find(node => node.id === state.machine);
const getDevice = host => host?.devices.find(gpu => gpu.uuid === state.gpu);
const currentDevice = (host, device) => host.metrics?.gpus.find(gpu => gpu.uuid === device.uuid);
const supported = (host, gpu) => gpu ? ['gpu','vram','power','temp']
  : ['cpu','memory', ...(host?.scope === 'container' ? ['memory_used'] : []),
    ...(host?.require_gpu ? ['gpu','power'] : [])];
const reason = host => i18n.diagnostic(host.reason) || host.warnings?.map(i18n.diagnostic).join(' · ') || machineStates[host.status];
const checks = host => host.checks ?? ['gpu','processes','cpu','memory','system'];
const configUnavailable = () => state.snapshot.registry_loaded === false;
const unlimitedMemory = host => host?.scope === 'container' && host.metrics?.memory?.total_bytes === null;

function navigation(hosts, host) {
  byId('rail-nav').innerHTML = `<button class="rail-nav" type="button" data-overview ${host ? '' : 'aria-current="page"'}>
      <span class="overview-icon" aria-hidden="true"></span><strong>${t('overview')}</strong></button>
    <p class="rail-label">${t('machine')}</p>${hosts.map(node => `<button class="rail-nav rail-machine" type="button"
      data-host="${escape(node.id)}" ${node.id === host?.id ? 'aria-current="page"' : ''}>
      ${machineIcon}<strong>${escape(node.name)}</strong><span class="status-dot ${escape(node.status)}" title="${escape(machineStates[node.status])}"></span>
    </button>`).join('')}`;
  byId('breadcrumb').innerHTML = host
    ? `<button type="button" data-overview class="crumb-button">${t('overview')}</button><span aria-hidden="true">›</span><strong>${escape(host.name)}</strong>`
    : `<strong>${t('overview')}</strong>`;
}

function renderPage(force = false) {
  if (rowDrag || document.querySelector('dialog[open]')) return;
  const hosts = nodes();
  const host = hosts.find(node => node.id === state.machine);
  const device = getDevice(host);
  const shape = JSON.stringify([host?.id, device?.uuid, state.filter, state.syncFailed, state.snapshot?.registry_loaded,
    hosts.map(node => [node.id, node.name, node.address, node.status, node.require_gpu, node.scope, checks(node), reason(node)]),
    host?.devices, host?.metrics?.gpus.map(gpu => [gpu.uuid, gpu.state, gpu.process_visibility,
      gpu.processes.map(proc => [proc.pid, proc.name, proc.uid, proc.user, proc.workload, proc.used_memory_mib])]),
    host?.metrics?.driver_version, unlimitedMemory(host)]);
  if (!force && shape === layoutKey) return;
  layoutKey = shape;
  const focused = document.activeElement;
  const focusId = focused?.id;
  const focusContainerId = focused?.parentElement?.closest('[id]')?.id;
  const focusClass = focused?.className;
  const focusData = focused?.tagName === 'BUTTON' ? Object.entries(focused.dataset) : [];
  const inputFocused = document.activeElement?.id === 'host-search';
  const focusedSort = document.activeElement?.dataset.sortHost;
  const caret = inputFocused ? document.activeElement.selectionStart : null;
  const deviceExpanded = byId('smi')?.open;
  if (chart) chart.observer.disconnect();
  chart = null;

  navigation(hosts, host);
  const content = byId('content');
  if (!state.snapshot) {
    content.setAttribute('aria-busy', String(!state.syncFailed));
    content.innerHTML = state.syncFailed
      ? `<div class="loading-state" role="status"><h1>${t('workbench_unavailable')}</h1><p>${t('machine_list_unavailable_retrying_automatically_check_the_monitor')}</p></div>`
      : `<div class="loading-state" role="status"><span class="loading-mark" aria-hidden="true"></span><h1>${t('connecting_to_workbench')}</h1><p>${t('loading_machines_and_latest_samples')}</p></div>`;
    return;
  }
  content.removeAttribute('aria-busy');
  content.innerHTML = host ? hostPage(host, device) : overviewPage(hosts);
  if (!host) {
    byId('host-search').value = state.query;
    drawRows(hosts);
    if (inputFocused) {
      byId('host-search').focus({preventScroll:true});
      if (caret != null) byId('host-search').setSelectionRange(caret, caret);
    } else if (focusedSort) {
      byId('host-rows').querySelector(`[data-sort-host="${CSS.escape(focusedSort)}"]`)?.focus({preventScroll:true});
    }
  }
  if (deviceExpanded && byId('smi')) byId('smi').open = true;
  bindChart();
  // Snapshot refreshes may replace controls; keep keyboard users on the same action.
  if (focused && !focused.isConnected) {
    // Rows, attention items and rail links can share data-host. Restore within
    // the original container and control kind, not the first global match.
    const controls = byId(focusContainerId)?.querySelectorAll('button') || [];
    const replacement = (focusId && byId(focusId)) || [...controls].find(button =>
      button.className === focusClass && focusData.length &&
      Object.keys(button.dataset).length === focusData.length &&
      focusData.every(([key,value]) => button.dataset[key] === value));
    replacement?.focus({preventScroll:true});
    if (replacement) {
      const rect = replacement.getBoundingClientRect();
      if (rect.top < 0 || rect.bottom > innerHeight || rect.left < 0 || rect.right > innerWidth) {
        replacement.scrollIntoView({block:'nearest', inline:'nearest'});
      }
    }
  }
}

function overviewPage(hosts) {
  const issues = hosts.filter(host => ['warning','offline','unknown','stale'].includes(host.status));
  const filters = [['all',t('all')],['normal',t('healthy')],['warning',t('needs_attention')],['unavailable',t('unavailable')]];
  return `<section class="page-title"><div><p class="eyebrow">WATTLINE / OVERVIEW</p>${heading(t('compute_at_a_glance'))}
      <p>${t('current_machine_and_physical_gpu_status_with_trends_over_the_last')}</p></div>
      <button type="button" class="control primary-control" data-add-machine ${configUnavailable() ? 'disabled' : ''}>${t('add_machine')}</button></section>
    <section class="metrics" aria-label="${t('current_sample_overview')}">
      ${metricTile(t('machines_online'),'online','', '◉',t('includes_nodes_needing_attention'))}
      ${metricTile(t('visible_gpus'),'visible',t('gpus'),'▤', field('configured-gpu'))}
      ${metricTile(t('visible_gpu_processes'),'processes',t('processes'),'≋',t('unique_pids_per_host'))}
      ${metricTile(t('total_gpu_power'),'watts','W','⌁',field('power-count'))}
    </section>
    <div class="layout overview-layout"><section class="panel">
      <div class="panel-head"><h2>${t('machines')}</h2><small id="row-count"></small></div>
      <div class="tools"><div class="seg" role="group" aria-label="${t('filter_by_machine_status')}">
        ${filters.map(([key,label]) => toggle(label, 'data-filter', key, state.filter === key)).join('')}
        </div><input class="search" id="host-search" type="search" aria-label="${t('search_machines')}" placeholder="${t('search_name_or_address')}"></div>
      <p id="order-message" class="order-message" role="status" ${orderMessage ? '' : 'hidden'}>${escape(orderMessage)}</p>
      <div class="scroll machine-scroll" tabindex="0" role="region" aria-label="${t('machines')}"><table class="machine-table">
        <thead><tr><th>${t('machine')}</th><th>${t('status')}</th><th><span class="wide-label">${t('gpu_utilization')}</span><span class="compact-label" title="${t('average_gpu_utilization')}">GPU</span></th>
        <th aria-label="${t('gpu_power')}"><span class="power-label">${t('gpu_power')}</span><span class="narrow-power-label">${t('power')}</span></th><th>CPU</th><th>${t('memory')}</th></tr></thead>
        <tbody id="host-rows"></tbody></table></div>
    </section><div class="column">
      <section class="panel">
        <div class="panel-head"><h2>${t('needs_attention_m051')}</h2><small>${t('machine_count',{count:issues.length})}</small></div>
        ${issues.length ? `<div class="issues">${issues.map(node => `<button type="button" class="issue" data-host="${escape(node.id)}">
          <span class="issue-mark ${escape(node.status)}" aria-hidden="true">${node.status === 'stale' ? '◷' : '!'}</span>
          <span><strong>${escape(node.name)}</strong><small>${escape(reason(node))}</small></span>${status(node.status,machineStates[node.status])}
        </button>`).join('')}</div>` : `<p class="empty">${t('no_machines_need_attention')}</p>`}
      </section>${chartPanel(null,null)}
    </div></div>`;
}

function drawRows(hosts) {
  const query = state.query.trim().toLowerCase();
  const filtered = hosts.filter(node => (state.filter === 'all' || node.status === state.filter
      || (state.filter === 'unavailable' && !['normal','warning'].includes(node.status)))
    && (node.name + ' ' + node.id + ' ' + node.address).toLowerCase().includes(query));
  byId('row-count').textContent = t('filtered_machine_count',{visible:filtered.length,total:hosts.length});
  const sortable = filtered.length > 1 && !configUnavailable();
  byId('host-rows').innerHTML = filtered.length ? filtered.map(node => `<tr data-machine-row="${escape(node.id)}">
    <td><div class="machine-cell">
      <button type="button" class="sort-handle" data-sort-host="${escape(node.id)}"
        aria-label="${t('reorder')} ${escape(node.name)}" title="${t('drag_to_reorder_or_use_up_and_down_arrow_keys')}"
        aria-keyshortcuts="ArrowUp ArrowDown" ${sortable ? '' : 'disabled'}></button>
      <button type="button" class="row-open" data-host="${escape(node.id)}" aria-label="${t('view')} ${escape(node.name)}">
      ${machineIcon}<span><strong>${escape(node.name)}</strong><small class="mono">${escape(node.address)}</small>
      ${node.scope === 'container' ? `<small>${t('container_scope')}</small>` : ''}</span></button></div></td>
    <td data-label="${t('status')}">${status(node.status, machineStates[node.status])}</td>
    ${['gpu','power','cpu','memory'].map(key => `<td class="number-cell" data-label="${{gpu:t('gpu_utilization'),power:t('gpu_power'),cpu:'CPU',memory:t('memory')}[key]}">${field(node.id+'-'+key)}
      ${key === 'power' ? '' : meter(node.id+'-'+key, key === 'memory' ? 'memory' : '')}</td>`).join('')}
  </tr>`).join('') : `<tr><td colspan="6" class="empty">${hosts.length ? t('no_matching_machines_adjust_the_filter_or_search') : t('no_machines_yet_select_add_machine_to_start_monitoring')}</td></tr>`;
}

function showOrderMessage(message) {
  orderMessage = message;
  const notice = byId('order-message');
  if (notice) {
    notice.textContent = message;
    notice.hidden = !message;
  }
}

async function moveMachine(from, target, after) {
  if (orderSaving || from === target) return;
  const visible = [...byId('host-rows').querySelectorAll('[data-machine-row]')].map(row => row.dataset.machineRow);
  const remaining = visible.filter(id => id !== from);
  const slot = remaining.indexOf(target);
  if (!visible.includes(from) || slot < 0) return;
  remaining.splice(slot + Number(after), 0, from);
  if (visible.every((id,index) => id === remaining[index])) return;

  const moved = remaining.values();
  const visibleSet = new Set(visible);
  const machines = state.snapshot.machines.map(node => visibleSet.has(node.id) ? moved.next().value : node.id);
  orderSaving = true;
  showOrderMessage(t('saving_order'));
  try {
    const response = await fetch('/api/machines/order', {
      method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({machines}),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof result.detail === 'string'
      ? t('could_not_save_order_please_retry')+' '+i18n.diagnostic(result.detail) : t('could_not_save_order_please_retry'));
    snapshotRevision++;
    const ranks = new Map(result.machines.map((id,index) => [id,index]));
    state.snapshot.machines.sort((a,b) => (ranks.get(a.id) ?? ranks.size) - (ranks.get(b.id) ?? ranks.size));
    showOrderMessage('');
  } catch (error) {
    showOrderMessage(error instanceof Error && error.name !== 'TypeError' ? error.message : t('could_not_save_order_please_retry'));
  } finally {
    orderSaving = false;
    renderPage();
    paint();
  }
}

document.addEventListener('pointerdown', event => {
  const handle = event.target.closest('[data-sort-host]:enabled');
  if (!handle || orderSaving || rowDrag || !event.isPrimary || event.button !== 0) return;
  handle.setPointerCapture(event.pointerId);
  rowDrag = {pointer:event.pointerId, from:handle.closest('tr'), start:event.clientY, target:null, after:false};
});

document.addEventListener('pointermove', event => {
  if (rowDrag?.pointer !== event.pointerId) return;
  const {from,start,target} = rowDrag;
  if (!from.classList.contains('sorting') && Math.abs(event.clientY-start) < 5) return;
  from.classList.add('sorting');
  target?.classList.remove('drop-before','drop-after');
  const row = document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-machine-row]');
  rowDrag.target = row && row !== from ? row : null;
  if (rowDrag.target) {
    const bounds = row.getBoundingClientRect();
    rowDrag.after = event.clientY > bounds.top + bounds.height/2;
    row.classList.add(rowDrag.after ? 'drop-after' : 'drop-before');
  }
});

function finishDrag(event) {
  if (rowDrag?.pointer !== event.pointerId) return;
  const {from,target,after} = rowDrag;
  rowDrag = null;
  from.classList.remove('sorting');
  target?.classList.remove('drop-before','drop-after');
  if (event.type === 'pointerup' && target && byId('host-rows')) {
    void moveMachine(from.dataset.machineRow,target.dataset.machineRow,after);
  }
  renderPage();
  paint();
}

document.addEventListener('pointerup',finishDrag);
document.addEventListener('pointercancel',finishDrag);
document.addEventListener('lostpointercapture',finishDrag);
document.addEventListener('keydown', event => {
  const handle = event.target.closest('[data-sort-host]:enabled');
  if (!handle || !['ArrowUp','ArrowDown'].includes(event.key) || rowDrag) return;
  event.preventDefault();
  const row = handle.closest('tr');
  const down = event.key === 'ArrowDown';
  const target = down ? row.nextElementSibling : row.previousElementSibling;
  if (target) void moveMachine(row.dataset.machineRow,target.dataset.machineRow,down);
});

function chartPanel(host, device) {
  return `<section class="panel chart-panel">
    <div class="panel-head"><h2>${host ? t('resource_trends') : t('last_24_hours')}</h2>
      <small>${host ? device ? 'GPU ' + device.index : (host.scope === 'container' ? t('container_scope') : t('whole_machine')) : t('average_of_valid_samples_in_each_period')}</small></div>
    ${host ? `<div class="trend-controls"><div class="seg" role="group" aria-label="${t('trend_metric')}">
      ${supported(host,device).map(key => toggle(descriptors[key][0],'data-metric',key,state.metric===key)).join('')}</div>
      <div class="seg" role="group" aria-label="${t('time_range')}">${[[1,t('1_hour')],[6,t('6_hours')],[24,t('24_hours')],[72,t('3_days')],[168,t('7_days')]]
        .filter(([hours]) => hours <= (state.snapshot?.machine_history_hours ?? 24))
        .map(([hours,label]) => toggle(label,'data-range',hours,state.hours===hours)).join('')}</div></div>` : ''}
    <div class="plot ${host ? 'large' : ''}"><canvas id="trend-chart" tabindex="0" role="img"
      aria-label="${t('resource_timeline_focus_and_use_left_and_right_arrows_to_inspect_')}" aria-describedby="chart-summary"></canvas><div class="chart-tip" id="chart-tip" hidden></div></div>
    <p class="chart-summary" id="chart-summary"></p><div class="sr-only" id="chart-announcement" role="status"></div><div class="chart-legend" id="chart-legend"></div><p class="chart-error" id="chart-error" hidden>${t('historical_metrics_unavailable')}</p>
  </section>`;
}

function hostPage(host, device) {
  const gpu = device && currentDevice(host, device);
  const statusBadge = status(host.status, machineStates[host.status]);
  const container = host.scope === 'container';
  const unlimited = unlimitedMemory(host);
  const active = checks(host);
  return `<section class="page-title"><div><p class="eyebrow">WATTLINE / NODE</p>${heading(host.name,statusBadge)}
    <p><span class="mono">${escape(host.address)}</span> · ${host.mode==='ssh' ? 'SSH' : t('local')}
    ${container ? t('container_scope_m077') : ''}${device ? ' · '+escape(device.name || 'NVIDIA GPU') : ''}</p></div>
    <div class="title-actions"><span class="time">${t('last_valid_sample')} ${field('host-time')}</span>
    <button type="button" class="control" data-configure-machine ${configUnavailable() ? 'disabled' : ''}>${t('configure')}</button>
    <button type="button" class="control danger-control" data-remove-machine ${configUnavailable() ? 'disabled' : ''}>${t('remove_node')}</button></div></section>
    ${container ? `<p class="message scope-note"><strong>${t('container_scope')}</strong> ${t('cpu_and_memory_describe_this_container_gpu_metrics_cover_visible_')}</p>` : ''}
    ${host.reason || host.warnings?.length ? '<p class="message">'+escape(reason(host))+'</p>' : ''}
    <section class="metrics" aria-label="${t('live_machine_resources')}" ${active.some(key => ['gpu','cpu','memory'].includes(key)) ? '' : 'hidden'}>
      ${active.includes('gpu') ? metricTile(device ? t('gpu_device_utilization',{index:device.index}) : t('average_gpu_utilization'),'card-gpu','%','≋',
        device ? field('gpu-memory') : t('only_devices_reporting_utilization')) : ''}
      ${active.includes('gpu') ? metricTile(device ? t('gpu_device_power',{index:device.index}) : container ? t('visible_gpu_power') : t('total_gpu_power'),'card-power','W','⌁',
        device ? field('gpu-limit') : container ? t('total_power_of_devices_visible_to_container') : t('calculated_when_device_power_modes_agree')) : ''}
      ${active.includes('cpu') ? metricTile(t('cpu_usage'),'card-cpu','%','◉',container ? t('share_of_container_cpu_capacity') : t('machine_logical_cpus')) : ''}
      ${active.includes('memory') ? metricTile(unlimited ? t('memory_used') : t('memory_usage'),'card-memory',unlimited ? 'GiB' : '%','▤',field('memory-detail')) : ''}
    </section>
    ${host.metrics && (host.metrics.driver_version || active.some(key => key === 'cpu' || key === 'memory' || (!container && key === 'system'))) ? `<div class="panel facts" aria-label="${t('additional_resource_metrics')}">
      ${active.includes('cpu') ? `<span>${container ? t('container_cpu_capacity') : t('logical_cpus')} <strong>${field('cores')}</strong></span>` : ''}
      ${!container && active.includes('cpu') ? `<span>${t('1_minute_load')} <strong>${field('load')}</strong></span>` : ''}
      ${!container && active.includes('system') ? `<span>${t('system_disk_available')} <strong>${field('disk')}</strong></span><span>${t('uptime')} <strong>${field('uptime')}</strong></span>` : ''}
      ${active.includes('memory') && !unlimited ? `<span>${container ? t('memory_limit_headroom') : t('memory_available')} <strong>${field('available')}</strong></span>` : ''}
      ${host.metrics.driver_version ? `<span>${t('nvidia_driver')} <strong>`+escape(host.metrics.driver_version)+'</strong></span>' : ''}</div>` : ''}
    <div class="layout details-layout">${chartPanel(host,device)}<section class="panel">
      <div class="panel-head"><h2>${t('physical_gpus')}</h2>
        ${device ? `<button type="button" class="control" data-all-gpus>${t('back_to_machine')}</button>` : '<small>'+t('observed_device_count',{count:host.devices.length})+'</small>'}</div>
      ${host.devices.length ? `<div class="gpu-list">${host.devices.map(card => gpuButton(host,device,card)).join('')}</div>`
        : '<p class="empty">'+(active.includes('gpu') ? t('no_verified_devices_yet')
          : host.require_gpu ? t('gpu_checks_are_disabled') : t('monitored_as_a_cpu_only_machine'))+'</p>'}
    </section></div>
    <div class="column device-details">${device ? gpuInfo(host,device,gpu) : ''}
      ${active.includes('processes') ? processTable(host,device) : ''}</div>`;
}

function gpuButton(host, device, card) {
  const gpu = currentDevice(host, card);
  return `<button class="gpu-row" type="button" data-gpu="${escape(card.uuid)}" aria-label="${t('view_gpu')} ${card.index}"
    aria-pressed="${card.uuid === device?.uuid}">
    <div class="gpu-row-name"><strong>GPU ${card.index}</strong><span>${escape(card.name || 'NVIDIA GPU')}</span></div>
    ${status(gpu?.state ?? 'stale', gpuStates[gpu?.state] || t('no_fresh_sample'))}
    ${meter(card.uuid)}<span class="number-cell">${field(card.uuid)}</span>
  </button>`;
}

function gpuInfo(host, device, gpu) {
  return `<section class="panel">
    <div class="panel-head"><h2>${t('gpu_device_info',{index:device.index})}</h2><small>nvidia-smi</small></div>
    <dl class="gpu-info">
      <div class="wide"><dt>${t('physical_uuid')}</dt><dd class="mono">${escape(device.uuid)}</dd></div>
      <div><dt>${t('pci_address')}</dt><dd class="mono">${escape(device.bus_id || '—')}</dd></div>
      <div><dt>${t('driver_version')}</dt><dd>${escape(host.metrics?.driver_version || '—')}</dd></div>
      <div><dt>${t('vram_used_total')}</dt><dd>${field('gpu-memory')}</dd></div>
      <div><dt>${t('core_temperature')}</dt><dd>${field('gpu-temperature')}</dd></div>
      <div><dt>${t('measured_power')}</dt><dd>${field('gpu-power')}</dd></div>
      <div><dt>${t('current_power_limit')}</dt><dd>${field('gpu-power-limit')}</dd></div>
    </dl>
    <details class="smi" id="smi"><summary>${t('show_nvidia_smi_sample_fields')}</summary><pre data-value="smi-detail"></pre></details>
    ${gpu?.process_visibility === 'partial' ? `<p class="empty">${t('process_enumeration_is_only_partially_visible_for_this_device')}</p>` : ''}
  </section>`;
}

function workloadEvidence(process) {
  const workload = process.workload;
  if (!workload) return t('unverified');
  const id = workload.pod_uid || workload.container_id;
  return (workloads[workload.kind] || t('workload')) + (id ? ' · ' + id.slice(0,12) : '');
}

function processTable(host, device) {
  const devices = (host.metrics?.gpus ?? []).filter(gpu => !device || device.uuid === gpu.uuid);
  const rows = devices.flatMap(gpu => gpu.processes.map(process => ({gpu,process})));
  let empty = t('no_gpu_processes_found');
  if (!devices.length || devices.some(gpu => gpu.process_visibility !== 'complete' || gpu.state === 'unknown')) {
    empty = t('no_verifiable_gpu_process_records_available');
  }
  return `<section class="panel">
    <div class="panel-head"><h2>${t('current_gpu_processes')}</h2><small>${device ? 'GPU '+device.index : t('whole_machine')} · ${t('visible_record_count',{count:rows.length})}</small></div>
    ${rows.length ? `<div class="scroll" tabindex="0" role="region" aria-label="${t('gpu_process_list')}"><table class="process-table">
      <thead><tr><th>${t('process_pid')}</th><th>${t('host_account')}</th><th>${t('ownership_evidence')}</th><th>${t('device')}</th><th>${t('process_vram')}</th></tr></thead>
      <tbody>${rows.map(({gpu,process}) => `<tr><td><strong>${escape(process.name || t('unverified'))}</strong><small class="mono">PID ${escape(process.pid)}</small></td>
      <td>${escape(process.user || (process.uid == null ? t('unverified') : 'UID '+process.uid))}
      ${process.user ? '<small>UID '+escape(process.uid)+'</small>' : ''}</td><td>${escape(workloadEvidence(process))}</td>
      <td>GPU ${gpu.index}</td><td class="value">${fmt(vram(process.used_memory_mib),' GiB',1)}</td></tr>`).join('')}</tbody>
    </table></div>` : '<p class="empty">'+empty+'</p>'}
  </section>`;
}

function uptime(seconds) {
  if (!Number.isFinite(seconds)) return '—';
  const hours = Math.floor(seconds / 3600);
  if (hours >= 24) return t('uptime_days',{days:Math.floor(hours/24),hours:hours%24});
  return hours ? t('uptime_hours',{hours}) : t('uptime_minutes',{minutes:Math.floor(seconds/60)});
}

function paint() {
  const hosts = nodes();
  const host = hosts.find(node => node.id === state.machine);
  const sync = byId('sync-state');
  sync.textContent = state.syncFailed ? t('sync_interrupted') : state.snapshot ? t('auto_updating') : t('waiting_for_data');
  sync.className = 'status ' + (state.syncFailed ? 'warning' : state.snapshot ? 'normal' : 'stale');
  byId('clock').textContent = state.snapshot ? t('synced_time',{time:time(state.snapshot.server_time)}) : '';
  const banner = byId('sync-error');
  const warnings = [];
  if (state.syncFailed) warnings.push(t('monitoring_service_unavailable_retrying'));
  if (state.snapshot?.registry_loaded === false) warnings.push(t('machine_configuration_unavailable_service_is_retrying'));
  else if (state.snapshot?.history_writable === false) warnings.push(t('history_is_read_only_live_sampling_continues'));
  if (state.snapshot?.archive_ok === false) warnings.push(t('history_archive_pending_retry_source_samples_retained'));
  if (state.snapshot?.removal_pending) warnings.push(t('removed_node_archives_are_being_cleaned_up_failures_retry_automat'));
  banner.hidden = warnings.length === 0;
  banner.textContent = warnings.join(' · ');

  const values = {};
  const scales = {};
  if (host) {
    const metrics = host.metrics;
    const selected = getDevice(host);
    const gpu = selected ? currentDevice(host,selected) : undefined;
    const memory = metrics?.memory;
    values['card-gpu'] = fmt(selected ? gpu?.utilization_percent : metrics?.gpu_percent);
    values['card-power'] = fmt(selected ? gpu?.power_w : metrics?.gpu_power_w);
    values['card-cpu'] = fmt(metrics?.cpu_percent);
    values['card-memory'] = unlimitedMemory(host) ? fmt(gib(memory.used_bytes),'',1) : fmt(metrics?.memory_percent);
    values['host-time'] = time(host.last_success_at);
    values['cores'] = fmt(metrics?.cpu_count,t('cores'),Number.isInteger(metrics?.cpu_count) ? 0 : 2);
    values['load'] = fmt(metrics?.load_average[0],'',2);
    values['disk'] = fmt(gib(metrics?.root_disk?.available_bytes),' GiB',1);
    values['available'] = fmt(gib(memory?.available_bytes),' GiB',1);
    values['uptime'] = uptime(metrics?.uptime_seconds);
    values['memory-detail'] = memory?.total_bytes != null
      ? fmt(gib(memory.used_bytes),'',1)+' / '+fmt(gib(memory.total_bytes),' GiB',1)+(host.scope === 'container' ? t('used_including_cache') : t('used'))
      : memory ? t('no_cgroup_memory_limit_usage_includes_cache') : t('no_current_reading');
    for (const device of host.devices) {
      const reading = currentDevice(host,device)?.utilization_percent;
      values[device.uuid] = fmt(reading,'%');
      scales[device.uuid] = reading;
    }
    if (selected) {
      values['gpu-memory'] = gpu ? fmt(vram(gpu.memory_used_mib),'',1)+' / '+fmt(vram(gpu.memory_total_mib),' GiB',1) : t('no_current_reading');
      values['gpu-temperature'] = fmt(gpu?.temperature_c,' °C');
      values['gpu-power'] = fmt(gpu?.power_w,' W',1) + (gpu?.power_kind ? ' · '+powerModes[gpu.power_kind] : '');
      values['gpu-power-limit'] = fmt(gpu?.power_limit_w,' W');
      values['gpu-limit'] = t('current_power_limit_m146')+values['gpu-power-limit'];
      values['smi-detail'] = [
        'GPU UUID                 '+selected.uuid,
        'Product Name             '+(selected.name || '—'),
        'Driver Version           '+(metrics?.driver_version || '—'),
        'PCI Bus                  '+(selected.bus_id || '—'),
        'GPU Utilization          '+fmt(gpu?.utilization_percent,'%'),
        'Framebuffer Memory       '+values['gpu-memory'],
        'GPU Temperature          '+values['gpu-temperature'],
        'GPU Power Draw           '+values['gpu-power'],
        'Current Power Limit      '+values['gpu-power-limit'],
      ].join('\n');
    }
  } else {
    const sampled = hosts.filter(node => node.metrics);
    const devices = sampled.flatMap(node => node.metrics.gpus);
    const powers = devices.map(gpu => gpu.power_w).filter(Number.isFinite);
    const configured = hosts.filter(node => node.require_gpu);
    values.online = sampled.length+' / '+hosts.length;
    values.visible = devices.length;
    values['configured-gpu'] = configured.every(node => node.expected_gpu_count != null)
      ? t('configured_device_count',{count:configured.reduce((total,node) => total+node.expected_gpu_count,0)}) : t('current_samples_only');
    const processSamples = sampled.filter(node => checks(node).includes('processes') && node.metrics.gpus.length);
    values.processes = processSamples.length ? processSamples.reduce((total,node) => total+new Set(node.metrics.gpus.flatMap(gpu =>
      gpu.processes.map(process => process.pid))).size, 0) : '—';
    values.watts = powers.length ? i18n.number(Math.round(powers.reduce((sum,watts) => sum+watts,0))) : '—';
    values['power-count'] = t('power_reading_count',{count:powers.length});
    for (const node of hosts) {
      for (const [key, value] of Object.entries({gpu:node.metrics?.gpu_percent, power:node.metrics?.gpu_power_w,
        cpu:node.metrics?.cpu_percent, memory:node.metrics?.memory_percent})) {
        const id = node.id+'-'+key;
        values[id] = fmt(value,key === 'power' ? ' W' : '%');
        scales[id] = value;
      }
      if (unlimitedMemory(node)) values[node.id+'-memory'] = fmt(gib(node.metrics.memory.used_bytes),' GiB',1);
    }
  }

  for (const node of document.querySelectorAll('[data-value]')) {
    const value = values[node.dataset.value] ?? '—';
    node.textContent = value;
    const unit = node.parentElement.nextElementSibling;
    if (node.closest('.metric') && node.parentElement.tagName === 'STRONG' && unit?.classList.contains('unit')) {
      unit.hidden = value === '—';
    }
  }
  for (const node of document.querySelectorAll('[data-meter]')) {
    const value = scales[node.dataset.meter];
    node.hidden = !Number.isFinite(value);
    if (!node.hidden) node.style.setProperty('--fill',clamp(value,0,100)+'%');
  }
}

async function get(path, signal = AbortSignal.timeout(5000)) {
  const response = await fetch(path, {signal,cache:'no-store'});
  if (!response.ok) throw new Error('HTTP '+response.status);
  return response.json();
}

async function refreshHistory(reset = false) {
  if (reset) {
    historyRequest?.abort();
    state.history = null;
    state.historyError = false;
    if (chart) chart.pointer = chart.keyboardAt = null;
    drawChart();
  } else if (historyRequest) return;
  if (!state.snapshot) return;

  const host = getHost();
  const gpu = getDevice(host);
  const params = new URLSearchParams({hours:state.hours});
  if (host) {
    params.set('machine',host.id);
    params.set('metric',state.metric);
    if (gpu) params.set('gpu',gpu.uuid);
  }
  const controller = new AbortController();
  historyRequest = controller;
  try {
    const history = await get('/api/history?'+params, AbortSignal.any([controller.signal,AbortSignal.timeout(5000)]));
    if (historyRequest === controller) {
      state.history = history;
      state.historyError = false;
    }
  } catch {
    if (historyRequest === controller) state.historyError = true;
  } finally {
    if (historyRequest === controller) {
      historyRequest = null;
      drawChart();
    }
  }
}

async function refresh() {
  const revision = snapshotRevision;
  try {
    const snapshot = await get('/api/snapshot');
    if (revision === snapshotRevision) {
      state.snapshot = snapshot;
      state.received = performance.now();
    }
    state.syncFailed = false;
  } catch {
    state.syncFailed = true;
  }
  if (state.machine && !getHost()) openHost(null);
  const replaced = state.gpu && !getDevice(getHost());
  if (replaced) {
    state.gpu = null;
    state.metric = 'gpu';
  }
  renderPage();
  paint();
  const lastQuery = state.history?.to ?? 0;
  const liveTrendDue = state.hours <= 24 && state.snapshot?.server_time-lastQuery >= 5000;
  if (replaced || !state.history || liveTrendDue) void refreshHistory(Boolean(replaced));
  window.setTimeout(refresh,2000);
}

function chartSeries() {
  const keys = state.history?.keys || (state.machine ? [state.metric] : ['gpu','cpu']);
  return keys.map(key => {
    const [title,unit] = descriptors[key];
    const label = !state.machine ? key === 'gpu' ? t('device_average_gpu') : t('machine_average_cpu')
      : key === 'power' && !state.gpu ? (getHost()?.scope === 'container' ? t('visible_gpu_power') : t('total_gpu_power')) : title;
    return {key,label,unit,color:colors[key]};
  });
}

function bindChart() {
  const canvas = byId('trend-chart');
  const observer = new ResizeObserver(drawChart);
  chart = {canvas,observer,pointer:null,keyboardAt:null,points:[]};
  observer.observe(canvas);
  canvas.addEventListener('pointermove',event => {
    chart.pointer = event.clientX-canvas.getBoundingClientRect().left;
    chart.keyboardAt = null;
    drawChart();
  });
  canvas.addEventListener('pointerleave',() => {chart.pointer = null;drawChart();});
  canvas.addEventListener('keydown',event => {
    if (!['ArrowLeft','ArrowRight','Escape'].includes(event.key)) return;
    event.preventDefault();
    chart.pointer = null;
    if (event.key === 'Escape') chart.keyboardAt = null;
    else if (chart.points.length) chart.keyboardAt = clamp((chart.keyboardAt ?? chart.points.length-1)
      + (event.key === 'ArrowLeft' ? -1 : 1),0,chart.points.length-1);
    drawChart();
    const point = chart.points[chart.keyboardAt];
    byId('chart-announcement').textContent = point
      ? tooltipTime.format(point.time)+' · '+chartSeries().map((item,i) => item.label+' '+fmt(point.values[i],item.unit,1)).join(' · ') : '';
  });
  canvas.addEventListener('blur',() => {
    // Replacing a focused canvas can emit blur while the previous chart is detached.
    if (chart?.canvas !== canvas) return;
    chart.keyboardAt = null;
    drawChart();
  });
  drawChart();
}

function chartCeiling(series, points) {
  const metric = series[0];
  if (metric.unit === '%') return 100;
  const max = Math.max(0,...points.flatMap(point => point.values.filter(Number.isFinite)));
  const step = metric.key === 'power' ? max > 800 ? 400 : max > 180 ? 100 : 40 : metric.key === 'temp' ? 25 : 16;
  return Math.max(step, Math.ceil(max/step)*step);
}

function drawChart() {
  if (!chart) return;
  const {canvas} = chart;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (width < 40 || height < 40) return;
  const ratio = window.devicePixelRatio || 1;
  const backingWidth = Math.round(width*ratio);
  const backingHeight = Math.round(height*ratio);
  if (canvas.width !== backingWidth || canvas.height !== backingHeight) {
    canvas.width = backingWidth;
    canvas.height = backingHeight;
  }
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.setTransform(ratio,0,0,ratio,0,0);
  ctx.clearRect(0,0,width,height);
  const history = state.history;
  const end = history?.to ?? state.snapshot?.server_time ?? Date.now();
  const start = history?.from ?? end-state.hours*3600000;
  const points = (history?.points || []).map(point => ({...point, values:point.values.map((value,i) =>
    history.keys[i] === 'vram' ? vram(value) : history.keys[i] === 'memory_used' ? gib(value) : value)}));
  chart.points = points;
  const series = chartSeries();
  const ceiling = chartCeiling(series,points);
  const left = series[0].key === 'power' ? 50 : 41;
  const right = width-12;
  const top = 13;
  const bottom = height-25;
  const x = timestamp => left+(timestamp-start)/(end-start)*(right-left);
  const y = value => bottom-value/ceiling*(bottom-top);
  const layout = {bottom,left,right,top,x,y,gap:state.machine ? Infinity : history?.gap_ms ?? Infinity};
  ctx.font = '10.5px system-ui, sans-serif';
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'right';
  for (let i=0;i<=4;i++) {
    const value = ceiling*i/4;
    ctx.fillStyle = '#526862';
    ctx.fillText(fmt(value, series[0].unit === '%' ? '%' : '', Number.isInteger(value) ? 0 : 1),left-6,y(value));
    ctx.strokeStyle = '#e9f0ec';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(left,y(value));
    ctx.lineTo(right,y(value));
    ctx.stroke();
  }
  const intervals = state.hours > 24 ? Math.min(state.hours/24,width >= 550 ? 6 : 3)
    : width >= 540 ? 6 : width >= 355 ? 4 : 3;
  const tickFormat = state.hours > 24 ? shortDate : shortTime;
  for (let i=0;i<=intervals;i++) {
    const timestamp = start+(end-start)*i/intervals;
    ctx.textAlign = i === 0 ? 'left' : i === intervals ? 'right' : 'center';
    ctx.fillText(tickFormat.format(timestamp),x(timestamp),bottom+13);
  }
  const valid = points.filter(point => point.values.some(Number.isFinite));
  byId('chart-summary').textContent = state.historyError ? t('could_not_load_history_retrying_automatically')
    : !history ? t('loading_historical_samples') : !valid.length ? t('no_valid_samples_in_this_window')
    : t('history_summary',{count:valid.length,latest:series.map((item,i) =>
      item.label+' '+fmt(valid.at(-1).values[i],item.unit,1)).join(' / ')});
  const bucket = history?.bucket_ms;
  byId('chart-legend').innerHTML = series.map(item =>
    '<span><i class="legend-line" aria-hidden="true" data-series="'+item.key+'"></i>'+item.label+
    (item.unit==='%' ? '' : ' · '+item.unit.trim())+'</span>').join('')+
    '<span class="chart-note">'+(bucket ? fmt(bucket/1000,t('second_average'))+' · ' : '')+`${t('gaps_indicate_discontinuous_samples')}</span>`;
  byId('chart-error').hidden = !state.historyError;
  if (!points.some(point => point.values.some(Number.isFinite))) {
    ctx.font = '12px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(history ? t('no_valid_samples_in_this_window_m159') : t('waiting_for_historical_samples'),(left+right)/2,(top+bottom)/2);
  }
  paintSeries(ctx,points,layout,series);
  paintTooltip(ctx,series,layout,width);
}

function openHost(id) {
  state.machine = id;
  state.gpu = null;
  state.metric = 'cpu';
  state.hours = 24;
  renderPage(true);
  paint();
  void refreshHistory(true);
  window.scrollTo(0,0);
  byId('page-heading')?.focus({preventScroll:true});
}

// Keep the marker on the button so text replacement cannot remove localization.
function setButtonLabel(button, key) {
  button.dataset.i18n = key;
  button.textContent = t(key);
}

const machineDialog = byId('machine-dialog');
const machineForm = byId('machine-form');
const machineFields = byId('machine-fields');
const machineError = byId('machine-error');
const machineCancel = byId('machine-cancel');
const machineSave = byId('machine-save');
const checkboxes = [...machineForm.querySelectorAll('input[name="checks"]')];
const gpuCheck = checkboxes.find(input => input.value === 'gpu');
const processCheck = checkboxes.find(input => input.value === 'processes');

function updateProcessCheck() {
  processCheck.disabled = !gpuCheck.checked;
  if (processCheck.disabled) processCheck.checked = false;
}

function openMachineDialog(host) {
  machineForm.reset();
  machineForm.dataset.machine = host?.id ?? '';
  byId('machine-dialog-title').textContent = host ? t('machine_settings') : t('add_machine');
  byId('machine-target').textContent = host?.address ?? '';
  byId('machine-target').hidden = !host;
  byId('machine-connection').hidden = !!host;
  const fields = machineForm.elements;
  fields.host.disabled = fields.ssh_user.disabled = !!host;
  fields.alias.value = host?.alias ?? '';
  fields.alias.placeholder = host?.default_name ?? t('leave_blank_for_default_name');
  fields.interval_seconds.value = host?.interval_seconds ?? state.snapshot.period_ms / 1000;
  const local = host?.mode === 'local';
  byId('ssh-timeout-field').hidden = local;
  fields.ssh_connect_timeout_seconds.disabled = local;
  fields.ssh_connect_timeout_seconds.value = host?.ssh_connect_timeout_seconds ?? state.snapshot.default_ssh_connect_timeout_seconds;
  fields.enabled.checked = host?.enabled ?? true;
  for (const input of checkboxes) input.checked = !host || checks(host).includes(input.value);
  updateProcessCheck();
  machineError.hidden = true;
  machineDialog.showModal();
  (host ? fields.alias : fields.host).focus();
}

gpuCheck.addEventListener('change', updateProcessCheck);
machineCancel.addEventListener('click', () => machineDialog.close());
machineDialog.addEventListener('cancel', event => {
  if (machineSave.disabled) event.preventDefault();
});
machineForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (machineSave.disabled) return;
  const id = machineForm.dataset.machine;
  const fields = new FormData(machineForm);
  const settings = {
    alias:fields.get('alias').trim() || null,
    enabled:fields.has('enabled'),
    interval_seconds:Number(fields.get('interval_seconds')),
    checks:fields.getAll('checks'),
  };
  if (fields.has('ssh_connect_timeout_seconds')) {
    settings.ssh_connect_timeout_seconds = Number(fields.get('ssh_connect_timeout_seconds'));
  }
  if (settings.enabled && !settings.checks.length) {
    machineError.textContent = t('select_at_least_one_check_when_monitoring_is_enabled');
    machineError.hidden = false;
    gpuCheck.focus();
    return;
  }
  if (!id) {
    settings.host = fields.get('host').trim();
    settings.ssh_user = fields.get('ssh_user').trim() || null;
  }
  machineSave.disabled = machineCancel.disabled = machineFields.disabled = true;
  setButtonLabel(machineSave, id ? 'saving' : 'verifying_connection');
  machineError.hidden = true;
  try {
    const response = await fetch(id ? '/api/machines/'+encodeURIComponent(id)+'/settings' : '/api/machines', {
      method:id ? 'PUT' : 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(settings),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof result.detail === 'string' ? t('could_not_save_please_retry_later')+' '+i18n.diagnostic(result.detail)
        : response.status === 422 ? t('check_the_address_username_and_monitoring_settings') : t('could_not_save_please_retry_later');
      throw new Error(detail);
    }
    snapshotRevision++;
    machineDialog.close();
    const index = state.snapshot.machines.findIndex(node => node.id === result.id);
    if (index === -1) state.snapshot.machines.push(result);
    else state.snapshot.machines[index] = result;
    if (!id) {
      openHost(result.id);
    } else {
      renderPage(true);
      paint();
      document.querySelector('[data-configure-machine]')?.focus({preventScroll:true});
    }
  } catch (error) {
    machineError.textContent = error instanceof Error && error.name !== 'TypeError'
      ? error.message : t('could_not_save_please_retry_later');
    machineError.hidden = false;
  } finally {
    machineSave.disabled = machineCancel.disabled = machineFields.disabled = false;
    setButtonLabel(machineSave, 'save');
  }
});

const removeDialog = byId('remove-dialog');
const removeForm = byId('remove-form');
const removeConfirm = byId('remove-confirm');
const removeCancel = byId('remove-cancel');
const removeError = byId('remove-error');

function openRemoveDialog(host) {
  removeForm.dataset.machine = host.id;
  byId('remove-name').textContent = host.name;
  byId('remove-address').textContent = host.address === host.name ? '' : host.address;
  removeError.hidden = true;
  removeDialog.showModal();
}

removeCancel.addEventListener('click', () => removeDialog.close());
removeDialog.addEventListener('cancel', event => {
  if (removeConfirm.disabled) event.preventDefault();
});
removeForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (removeConfirm.disabled) return;
  const id = removeForm.dataset.machine;
  removeConfirm.disabled = removeCancel.disabled = true;
  setButtonLabel(removeConfirm, 'removing');
  removeError.hidden = true;
  try {
    const response = await fetch('/api/machines/'+encodeURIComponent(id), {
      method:'DELETE', headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:true}),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? t('could_not_remove_please_retry_later')+' '+i18n.diagnostic(result.detail) : t('could_not_remove_please_retry_later'));
    snapshotRevision++;
    state.snapshot.machines = state.snapshot.machines.filter(node => node.id !== id);
    if (result.cleanup_pending) state.snapshot.removal_pending = Math.max(state.snapshot.removal_pending ?? 0,1);
    removeDialog.close();
    openHost(null);
  } catch (error) {
    removeError.textContent = error instanceof Error && error.name !== 'TypeError' ? error.message : t('could_not_remove_please_retry_later');
    removeError.hidden = false;
  } finally {
    removeConfirm.disabled = removeCancel.disabled = false;
    setButtonLabel(removeConfirm, 'confirm_removal');
  }
});

document.addEventListener('click',event => {
  const button = event.target.closest('button');
  if (!button) return;
  const {host,gpu,filter,metric,range} = button.dataset;
  if (button.hasAttribute('data-overview')) openHost(null);
  else if (button.hasAttribute('data-add-machine')) openMachineDialog(null);
  else if (button.hasAttribute('data-configure-machine')) openMachineDialog(getHost());
  else if (button.hasAttribute('data-remove-machine')) openRemoveDialog(getHost());
  else if (host) openHost(host);
  else if (filter) {
    state.filter = filter;
    for (const node of document.querySelectorAll('[data-filter]')) node.setAttribute('aria-pressed',String(node.dataset.filter === filter));
    drawRows(nodes());
    paint();
  } else if (gpu || button.hasAttribute('data-all-gpus')) {
    const selected = gpu || state.gpu;
    state.gpu = gpu || null;
    state.metric = state.gpu ? 'gpu' : 'cpu';
    renderPage(true);
    paint();
    void refreshHistory(true);
    [...document.querySelectorAll('[data-gpu]')].find(node => node.dataset.gpu === selected)?.focus({preventScroll:true});
  } else if (metric || range) {
    if (metric) state.metric = metric;
    if (range) state.hours = Number(range);
    for (const node of document.querySelectorAll('[data-metric]')) node.setAttribute('aria-pressed',String(node.dataset.metric === state.metric));
    for (const node of document.querySelectorAll('[data-range]')) node.setAttribute('aria-pressed',String(Number(node.dataset.range) === state.hours));
    void refreshHistory(true);
  }
});
document.addEventListener('input',event => {
  if (event.target.id !== 'host-search') return;
  state.query = event.target.value;
  drawRows(nodes());
  paint();
});

function paintSeries(ctx, points, layout, series) {
  const { bottom, left, right, top, x, y } = layout;
  ctx.save();
  ctx.beginPath();
  ctx.rect(left, top - 1, right - left, bottom - top + 2);
  ctx.clip();

  series.forEach((metric, index) => {
    const segments = [];
    let segment = [];
    let time = null;
    for (const point of points) {
      const value = point.values[index];
      if (segment.length && (!Number.isFinite(value) || point.breaks?.[index] || point.time - time > layout.gap)) {
        segments.push(segment);
        segment = [];
      }
      if (Number.isFinite(value)) segment.push([x(point.time), y(value)]);
      time = point.time;
    }
    if (segment.length) segments.push(segment);

    for (const part of segments) {
      const [firstX, firstY] = part[0];
      if (part.length === 1) {
        ctx.fillStyle = metric.color;
        ctx.beginPath();
        ctx.arc(firstX, firstY, 2, 0, 2 * Math.PI);
        ctx.fill();
        continue;
      }
      if (series.length === 1) {
        const gradient = ctx.createLinearGradient(0, top, 0, bottom);
        gradient.addColorStop(0, metric.color + '33');
        gradient.addColorStop(1, metric.color + '05');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.moveTo(firstX, bottom);
        for (const [px, py] of part) ctx.lineTo(px, py);
        ctx.lineTo(part.at(-1)[0], bottom);
        ctx.closePath();
        ctx.fill();
      }
      ctx.lineWidth = 1.8;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.strokeStyle = metric.color;
      ctx.beginPath();
      ctx.moveTo(firstX, firstY);
      for (const [px, py] of part.slice(1)) ctx.lineTo(px, py);
      ctx.stroke();
    }
  });
  ctx.restore();
}

function paintTooltip(ctx, series, layout, width) {
  const tip = byId('chart-tip');
  const { points, pointer, keyboardAt } = chart;
  if (!points.length || (pointer == null && keyboardAt == null)) {
    tip.hidden = true;
    return;
  }
  const { x, y, top, bottom, left, right } = layout;
  const px = clamp(pointer ?? 0, left, right);
  const point = keyboardAt != null ? points[clamp(keyboardAt, 0, points.length - 1)]
    : points.reduce((nearest, item) => Math.abs(x(item.time) - px) < Math.abs(x(nearest.time) - px) ? item : nearest);
  if (!point) return;
  const position = x(point.time);
  ctx.lineWidth = 1;
  ctx.strokeStyle = '#b4c7bd';
  ctx.beginPath();
  ctx.moveTo(position, top);
  ctx.lineTo(position, bottom);
  ctx.stroke();
  for (const [index, value] of point.values.entries()) {
    if (!Number.isFinite(value)) continue;
    ctx.fillStyle = series[index].color;
    ctx.beginPath();
    ctx.arc(position, y(value), 3.2, 0, 2 * Math.PI);
    ctx.fill();
  }
  tip.hidden = false;
  tip.innerHTML = '<time>' + tooltipTime.format(point.time) + '</time>' + series.map((metric, index) =>
    '<div>' + metric.label + ' · ' + fmt(point.values[index], metric.unit, metric.key === 'vram' ? 1 : 0) + '</div>'
  ).join('');
  const preferred = position + tip.offsetWidth + 10 < width ? position + 9 : position - tip.offsetWidth - 9;
  tip.style.left = clamp(preferred, 2, Math.max(2, width - tip.offsetWidth - 2)) + 'px';
  tip.style.top = '13px';
}

const localeSelect = byId('locale-select');
for (const [value, entry] of Object.entries(i18n.registry)) {
  const option = document.createElement('option');
  option.value = value;
  option.textContent = entry.label;
  localeSelect.append(option);
}
localeSelect.value = i18n.locale;
localeSelect.addEventListener('change', () => {
  i18n.setLocale(localeSelect.value);
  i18n.apply();
  localizeLabels();
  orderMessage = '';
  renderPage(true);
  paint();
});

void refresh();
