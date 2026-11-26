
'use strict';

const i18n = WattlineI18n;
const t = i18n.t;
i18n.apply();
const byId = id => document.getElementById(id);
const fmt = (value, unit = '', digits = 0) => Number.isFinite(value) ? i18n.number(value, {minimumFractionDigits:digits, maximumFractionDigits:digits, useGrouping:false}) + unit : '—';
const gib = bytes => bytes == null ? null : bytes / 1024 ** 3;
const vram = mib => mib == null ? null : mib / 1024;
const time = value => Number.isFinite(value) ? i18n.date(value, {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}) : '—';
const chartDate = (value, options) => i18n.date(value, {...options,timeZone:state.archive?.timezone});
const shortTime = ({format:value => chartDate(value, {hour:'2-digit', minute:'2-digit', hour12:false})});
const shortDate = ({format:value => chartDate(value, {month:'2-digit', day:'2-digit'})});
const tooltipTime = ({format:value => {
  const options = {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'};
  return chartDate(value,state.archive
    ? {...options,year:'numeric',second:'2-digit',hourCycle:'h23'} : {...options,hour12:false});
}});
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const escape = value => String(value ?? '').replace(/[&<>"']/g, character =>
  ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[character]);
let machineStates, gpuStates, workloads, descriptors, colors, powerModes;
function localizeLabels() {
  machineStates = {normal:t('healthy'), warning:t('needs_attention'), offline:t('connection_failed'), stale:t('stale'),
    unknown:t('unverified'), disabled:t('disabled'), waiting:t('awaiting_sample'), pending:t('storage_pending')};
  gpuStates = {occupied:t('in_use'), free:t('no_usage_seen'), unknown:t('usage_unknown')};
  workloads = {host:t('host_process'), docker:'Docker', kubernetes:'Pod', containerd:'containerd', 'cri-o':'CRI-O'};
  descriptors = {cpu:[t('cpu_usage'),'%'], memory:[t('memory_usage'),'%'], memory_used:[t('memory_used'),' GiB'], gpu:[t('gpu_utilization'),'%'],
    power:[t('gpu_power'),' W'], vram:[t('vram_used'),' GiB'], temp:[t('gpu_temperature'),' °C'],
    storage:[t('storage_ratio'),'%'], storage_read:[t('storage_read'),' MiB/s'], storage_write:[t('storage_write'),' MiB/s']};
  colors = {cpu:'#0b836a', memory:'#456ab4', memory_used:'#456ab4', gpu:'#506dc3', power:'#0b836a', temp:'#b16e23', vram:'#8b57a2', storage:'#0b836a', storage_read:'#456ab4', storage_write:'#8b57a2'};
  powerModes = {average:t('average_power'), instantaneous:t('instantaneous_power'), reported:t('driver_reported_power')};
}
localizeLabels();
let railCollapsed = false;
try { railCollapsed = localStorage.getItem('wattline.railCollapsed') === 'true'; } catch {}
function updateRail() {
  document.querySelector('.shell').classList.toggle('rail-collapsed', railCollapsed);
  const button = byId('rail-toggle');
  button.textContent = railCollapsed ? '›' : '‹';
  button.setAttribute('aria-expanded', String(!railCollapsed));
  button.setAttribute('aria-label', t(railCollapsed ? 'expand_sidebar' : 'collapse_sidebar'));
  button.title = button.getAttribute('aria-label');
}
byId('rail-toggle').addEventListener('click', () => {
  railCollapsed = !railCollapsed;
  try { localStorage.setItem('wattline.railCollapsed', String(railCollapsed)); } catch {}
  updateRail();
});
updateRail();
const machineColors = ['#506dc3','#0b836a','#b16e23','#8b57a2','#c14953','#2f7f9e','#7d8b2f','#a35d2c'];
const machineDashes = [
  [], [8,4], [2,4], [12,4], [8,4,2,4], [8,4,2,4,2,4], [2,4,2,8], [12,4,4,4],
  [12,4,2,4,2,4], [5,7], [12,8], [3,8], [12,4,6,4], [6,4,6,8], [6,8,2,4], [12,4,2,8]
];
const overviewMetrics = ['gpu','cpu','memory','power'];
const archiveMetrics = ['cpu','memory','memory_used','gpu','power'];
const modelRules = [
  ['b300', /\bB300\b/i],
  ['pro6000', /(?:^|[^\p{L}\p{M}\p{N}\p{Pc}])PRO\s*6000(?![\p{L}\p{M}\p{N}\p{Pc}])/iu],
  ['spark', /\bGB10\b|\bDGX\s*Spark\b/i],
  ['rtx5090', /\bRTX\s*5090\b|\b5090\b/i],
];
const modelShapes = {
  b300: '<rect x="4.5" y="2.5" width="15" height="19" rx="2.5" stroke-width="2"/><path d="M7.5 6.5h9M7.5 10.5h9M7.5 14.5h9" stroke-width="1.6"/><path d="M7.5 18h9" stroke-width="2.4"/>',
  pro6000: '<rect x="2.5" y="7" width="19" height="10" rx="1.5" stroke-width="1.8"/><path d="M5.5 10.5h13" stroke-width="1.5"/><path d="M7.5 17v3.5h7V17" stroke-width="1.5"/>',
  spark: '<rect x="6" y="6" width="12" height="12" rx="3.5" stroke-width="1.8"/><path d="M9 12h6" stroke-width="1.5"/><circle cx="15.5" cy="15.5" r="1.2" fill="currentColor" stroke="none"/>',
  rtx5090: '<rect x="2.5" y="7" width="19" height="10" rx="3" stroke-width="1.6"/><circle cx="8.5" cy="12" r="2.5" stroke-width="1.4"/><circle cx="15.5" cy="12" r="2.5" stroke-width="1.4"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2" stroke-width="1.8"/><path d="M9 3v3m6-3v3m-6 12v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3" stroke-width="1.6"/>',
  nas: '<rect x="5" y="3" width="14" height="18" rx="2" stroke-width="2"/><path d="M9 8h6m-6 4h6m-6 4h6" stroke-width="1.5"/>',
  storage_cluster: '<rect x="3" y="5" width="8" height="14" rx="1.4" stroke-width="1.6"/><rect x="13" y="5" width="8" height="14" rx="1.4" stroke-width="1.6"/><path d="M6 10h2m-2 4h2m8-4h2m-2 4h2" stroke-width="1.4"/>',
  generic: '<rect x="4.5" y="3.5" width="15" height="7.5" rx="1.5" stroke-width="1.6"/><rect x="4.5" y="13" width="15" height="7.5" rx="1.5" stroke-width="1.6"/><circle cx="7.5" cy="7.25" r="0.9" fill="currentColor" stroke="none"/><circle cx="7.5" cy="16.75" r="0.9" fill="currentColor" stroke="none"/>',
};
function classifyModel(name) {
  const kinds = new Set(modelRules.filter(([, pattern]) => pattern.test(name)).map(([kind]) => kind));
  return kinds.size === 1 ? [...kinds][0] : null;
}
function machineModel(node) {
  const devices = Array.isArray(node?.devices) ? node.devices : [];
  const names = [];
  const inventoryComplete = node && Object.hasOwn(node, 'gpu_inventory_complete')
    ? node.gpu_inventory_complete : node?.metrics?.gpu_inventory_complete;
  let complete = inventoryComplete === true && devices.length > 0;
  for (const device of devices) {
    const name = typeof device?.name === 'string' ? device.name.trim() : '';
    if (!name) complete = false;
    else if (!names.includes(name)) names.push(name);
  }
  if (node?.expected_gpu_count != null && devices.length !== node.expected_gpu_count) complete = false;
  const kinds = new Set(names.map(classifyModel));
  if (['cpu','nas','storage_cluster'].includes(node?.hardware_kind)) return {kind:node.hardware_kind,names:[]};
  const kind = complete && kinds.size === 1 && !kinds.has(null) ? [...kinds][0] : 'generic';
  return {kind, names};
}
const graphemeSegmenter = typeof Intl !== 'undefined' && typeof Intl.Segmenter === 'function'
  ? new Intl.Segmenter(undefined, {granularity:'grapheme'}) : null;
const splitGraphemes = label => graphemeSegmenter
  ? [...graphemeSegmenter.segment(label)].map(part => part.segment) : Array.from(label);
function machineGlyph(node) {
  const {kind} = machineModel(node);
  return `<span class="machine-icon" data-model="${kind}" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false">${modelShapes[kind]}</svg></span>`;
}
const instanceNameKey = node => String(node.name || node.id).normalize('NFC');
function machineSuffixes(hosts, nameCounts) {
  const groups = new Map();
  const suffixes = new Map();
  const ordinals = new Map(hosts.map((node, index) => [node.id, String(index + 1)]));
  for (const node of hosts) {
    const {kind} = machineModel(node);
    if (!groups.has(kind)) groups.set(kind, []);
    groups.get(kind).push(node);
    if (nameCounts.get(instanceNameKey(node)) > 1) suffixes.set(node.id, ordinals.get(node.id));
  }
  for (const group of groups.values()) {
    if (group.length < 2) continue;
    // Split by grapheme so surrogates, combining marks and emoji sequences stay whole.
    const labels = group.map(node => {
      return splitGraphemes(instanceNameKey(node).replace(/\s+/g, '') || String(node.id).normalize('NFC'));
    });
    let picked = null;
    for (let length = 2; length <= 4 && !picked; length += 1) {
      const candidates = group.map((node, index) => suffixes.get(node.id) || labels[index].slice(-length).join(''));
      if (new Set(candidates).size === candidates.length) picked = candidates;
    }
    group.forEach((node, index) => suffixes.set(node.id, picked ? picked[index] : ordinals.get(node.id)));
  }
  return suffixes;
}
function machineIdentity(node, instanceSuffix) {
  const {names} = machineModel(node);
  const identity = [node.name, machineStates[node.status], ...names];
  if (instanceSuffix) identity.push(t('instance_suffix', {suffix:instanceSuffix}));
  return identity.join(' · ');
}
const state = {snapshot:null, received:0, syncFailed:false, machine:null, gpu:null, metric:'cpu',
  tab:'room', manageTab:'room', group:null, trail:[], overviewScroll:0, routeReady:false, hiddenGroups:new Set(),
  groupFilters:{room:{query:'',person:'',status:''},cluster:{query:'',person:'',status:''}}, groupMetric:'cpu',
  deviceFilters:{query:'',kind:'',room:'',user:'',status:'all'}, detailFilters:{query:'',kind:'',room:'',user:'',status:'all'},
  page:null, archive:null, event:null, alerts:null, directAlert:null, alertError:false, alertLoading:false, alertQuery:'', alertFilter:'all', alertKind:'all',
  overviewMetric:'gpu', hours:24, filter:'all', query:'', history:null, historyError:false,
  focused:false, focusMetrics:[], histories:{}, historyErrors:{}};
let layoutKey = '';
let chart = null;
let charts = [];
let focusScroll = 0;
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
  const resources = [...machines,...(state.snapshot.storage ?? [])];
  if (state.snapshot.resource_order) {
    const ranks = new Map(state.snapshot.resource_order.map((id,index) => [id,index]));
    resources.sort((left,right) => (ranks.get(left.id) ?? Infinity) - (ranks.get(right.id) ?? Infinity));
  }
  return resources.map(node => node.metrics && now - node.observed_at >= (node.stale_ms ?? stale_ms)
    ? {...node, metrics:null, status:'stale', reason:t('valid_sample_expired_awaiting_a_new_sample'), warnings:[]} : node);
}

const machineForId = (id, hosts = nodes()) =>
  hosts.find(node => node.id === id || node.sources?.some(source => source.id === id));
const getHost = () => machineForId(state.machine);
const sourceForId = (host, id) => host?.sources?.find(source => source.id === id);
const configurationTarget = () => sourceForId(getHost(), machineForm.dataset.machine) ?? getHost();
const historyScope = host => sourceForId(host, state.historySource)?.scope ?? null;
const machineMetrics = host => host?.machine_metrics ?? host?.metrics;
const getDevice = host => host?.devices.find(gpu => gpu.uuid === state.gpu);
const currentDevice = (host, device) => host.metrics?.gpus?.find(gpu => gpu.uuid === device.uuid);
const supported = (host, gpu) => gpu ? ['gpu','vram','power','temp']
  : host?.storage_kind ? ['storage','storage_read','storage_write'] : ['cpu','memory',
    ...((historyScope(host) === 'container' || !state.historySource &&
      (host?.scope === 'container' || host?.sources?.some(source => source.scope === 'container') || unlimitedMemory(host))) ? ['memory_used'] : []),
    ...(host?.require_gpu && host.hardware_kind !== 'cpu' ? ['gpu','power'] : [])];
const reason = host => i18n.diagnostic(host.reason) || host.warnings?.map(i18n.diagnostic).join(' · ') || machineStates[host.status];
const checks = host => host.storage_kind ? [] : host.hardware_kind === 'cpu'
  ? (host.reading_checks ?? host.checks ?? ['cpu','memory','system']).filter(key => !['gpu','processes'].includes(key))
  : host.reading_checks ?? host.checks ?? ['gpu','processes','cpu','memory','system'];
const typedResources = () => Array.isArray(state.snapshot?.storage);
const resourcePath = host => (host?.storage_kind ? '/api/storage/' : '/api/machines/')+encodeURIComponent(host.id);
const configUnavailable = () => state.snapshot.registry_loaded === false;
const unlimitedMemory = host => {
  const memory = machineMetrics(host)?.memory;
  return memory?.total_bytes === null && Number.isFinite(memory.used_bytes);
};
const windowsHost = host => host.target_os === 'windows';
const processMemory = process => Number.isFinite(process.used_memory_mib) ? process.used_memory_mib : -1;

function displayedProcesses(host, gpu) {
  const records = gpu?.processes ?? [];
  if (!windowsHost(host) || records.length <= 1) return {rows:records, omitted:0};
  const rows = [...records].sort((left,right) => processMemory(right)-processMemory(left) || left.pid-right.pid).slice(0,5);
  return {rows, omitted:records.length-rows.length};
}

function processVram(host, process) {
  if (windowsHost(host) && !Number.isFinite(process.used_memory_mib)) return t('unknown_value');
  return fmt(vram(process.used_memory_mib),' GiB',1);
}

function omittedProcesses(count) {
  return count ? `<small>${t('omitted_gpu_processes',{count:i18n.number(count)})}</small>` : '';
}

const processShape = gpu => [gpu?.uuid, gpu?.state, gpu?.process_visibility,
  gpu?.processes.map(proc => [proc.pid, proc.name, proc.uid, proc.user, proc.workload, proc.used_memory_mib])];

function navigation(hosts, host) {
  const nameCounts = countLabels(hosts.map(instanceNameKey));
  const suffixes = machineSuffixes(hosts, nameCounts);
  byId('rail-nav').innerHTML = `<button class="rail-nav" type="button" data-overview aria-label="${t('overview')}" title="${t('overview')}" ${host || state.page ? '' : 'aria-current="page"'}>
      <span class="overview-icon" aria-hidden="true"></span><strong>${t('overview')}</strong></button>
    ${typedResources() ? `<button type="button" class="rail-nav" data-alert-center aria-label="${t('alerts_center')}" ${state.page === 'alerts' ? 'aria-current="page"' : ''}>
      <span aria-hidden="true">!</span><strong>${t('alerts_center')}</strong></button>` : ''}
    ${groupedOverview() ? `<button type="button" class="rail-nav" data-workspace-manage aria-label="${t('group_management')}"
      ${state.page === 'manage' ? 'aria-current="page"' : ''}><span aria-hidden="true">≡</span><strong>${t('group_management')}</strong></button>` : ''}
    <p class="rail-label">${t('machine')}</p>${hosts.map(node => {
      const suffix = suffixes.get(node.id);
      const identity = machineIdentity(node, nameCounts.get(instanceNameKey(node)) > 1 ? suffix : null);
      return `<button class="rail-nav rail-machine" type="button"
      data-host="${escape(node.id)}" aria-label="${escape(identity)}" title="${escape(identity)}" ${node.id === host?.id ? 'aria-current="page"' : ''}>
      ${machineGlyph(node)}<strong>${escape(node.name)}</strong>${suffix ? `<span class="machine-suffix" aria-hidden="true">${escape(suffix)}</span>` : ''}<span class="status-dot ${escape(node.status)}" aria-hidden="true"></span>
    </button>`;
    }).join('')}`;
  byId('breadcrumb').innerHTML = state.page === 'alerts'
    ? `<button type="button" data-overview class="crumb-button">${t('overview')}</button><span aria-hidden="true">›</span><strong>${t('alerts_center')}</strong>`
    : groupBreadcrumb() ?? (host
    ? `<button type="button" data-overview class="crumb-button">${t('overview')}</button><span aria-hidden="true">›</span><strong>${escape(host.name)}</strong>`
    : `<strong>${t('overview')}</strong>`);
}

function renderPage(force = false) {
  if (state.archive && state.page !== 'archive') {
    state.archive.controller.abort();
    state.archive = null;
  }
  if (rowDrag || document.querySelector('dialog[open]')) return;
  const hosts = nodes();
  const host = machineForId(state.machine, hosts);
  const device = getDevice(host);
  const shape = JSON.stringify([state.page, state.tab, state.manageTab, state.group, host?.id,
    ...['room','cluster'].map(kind => groupList(kind).map(group =>
      [group.id,group.name,group.location,groupPerson(group,kind),group.members,group.rooms,
        state.groupFilters[kind].status ? [group.summary.online,activeGroupAlerts(group)] : null])), device?.uuid, host?.storage_observation,
    state.page === 'alerts' || !typedResources() ? null :
      [state.snapshot.alerts?.total, state.snapshot.alerts?.events?.map(event => [event.id,event.resource,event.name,event.severity])], state.filter, state.syncFailed, state.snapshot?.registry_loaded,
    hosts.map(node => {
      const model = machineModel(node);
      return [node.id, node.name, node.address, node.assigned_users, node.assignment_mode, node.room_id, node.cluster_ids, node.hardware_kind, node.status, node.require_gpu, node.scope,
        checks(node), reason(node), model.kind, model.names, node.target_os, node.gpu_inventory_complete];
    }),
    state.historySource, host?.reading_source_id,
    machineMetrics(host)?.cpu_source_id, machineMetrics(host)?.memory_source_id,
    machineMetrics(host)?.cpu_scope, machineMetrics(host)?.memory_scope,
    host?.sources?.map(source => [source.id,source.name,source.address,source.scope,source.container_id]),
    host?.devices, host?.metrics?.gpus?.map(processShape),
    host?.metrics?.driver_version, unlimitedMemory(host)]);
  if (!force && shape === layoutKey) return;
  layoutKey = shape;
  const focused = document.activeElement;
  const focusId = focused?.id;
  const focusContainerId = focused?.parentElement?.closest('[id]')?.id;
  const focusClass = focused?.className;
  const focusData = focused?.tagName === 'BUTTON' ? Object.entries(focused.dataset) : [];
  const inputFocused = ['host-search','group-search','alert-search'].includes(focusId);
  const focusedSort = document.activeElement?.dataset.sortHost;
  const caret = inputFocused ? document.activeElement.selectionStart : null;
  for (const instance of charts) instance.observer.disconnect();
  charts = [];
  chart = null;

  navigation(hosts, host);
  const content = byId('content');
  const openSources = content.querySelector('.machine-sources[open]')?.dataset.machine;
  if (!state.snapshot) {
    content.setAttribute('aria-busy', String(!state.syncFailed));
    content.innerHTML = state.syncFailed
      ? `<div class="loading-state" role="status"><h1>${t('workbench_unavailable')}</h1><p>${t('machine_list_unavailable_retrying_automatically_check_the_monitor')}</p></div>`
      : `<div class="loading-state" role="status"><span class="loading-mark" aria-hidden="true"></span><h1>${t('connecting_to_workbench')}</h1><p>${t('loading_machines_and_latest_samples')}</p></div>`;
    return;
  }
  content.removeAttribute('aria-busy');
  document.body.classList.toggle('trends-focused', state.focused);
  const group = detailGroup();
  content.innerHTML = state.focused ? focusPage(host, device) : state.page === 'alerts' ? alertCenter()
    : state.page === 'manage' ? managementPage() : state.page === 'group' && group ? groupDetailPage(group,state.group.kind)
    : state.archive && host ? archivePage(host)
    : host?.storage_kind ? storagePage(host) : host ? hostPage(host, device) : groupedOverview() ? workspaceOverview() : overviewPage(hosts);
  const sources = content.querySelector('.machine-sources');
  if (sources && sources.dataset.machine === openSources) sources.open = true;
  if (byId('host-search') && !state.focused) {
    byId('host-search').value = groupedOverview() ? deviceFilterState().query : state.query;
    drawRows(membersForPanel(hosts));
    if (focusedSort) {
      byId('host-rows').querySelector(`[data-sort-host="${CSS.escape(focusedSort)}"]`)?.focus({preventScroll:true});
    }
  }
  if (state.page === 'alerts') paintAlerts();
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
    if (inputFocused && caret != null && replacement) replacement.setSelectionRange(caret,caret);
    if (replacement) {
      const rect = replacement.getBoundingClientRect();
      if (rect.top < 0 || rect.bottom > innerHeight || rect.left < 0 || rect.right > innerWidth) {
        replacement.scrollIntoView({block:'nearest', inline:'nearest'});
      }
    }
  }
}

function overviewCards() {
  const workspace = groupedOverview();
  const powerReading = (label, key, coverage) => `<div>
    <p>${t(label)}</p><strong>${field(key)}</strong><span class="unit">W</span><small>${field(coverage)}</small>
  </div>`;
  return `<section class="metrics overview-metrics" aria-label="${t('current_sample_overview')}">
    ${metricTile(t(workspace ? 'devices_online' : 'machines_online'),'online','','◉',
      t(workspace ? 'online_registered' : 'includes_nodes_needing_attention'))}
    ${metricTile(t('visible_gpus'),'visible',t('gpus'),'▤',workspace ? t('current_samples_only') : field('configured-gpu'))}
    <article class="metric gpu-power-card">
      <p class="metric-name"><span>${t('gpu_power')}</span><span aria-hidden="true">⌁</span></p>
      <div class="gpu-power-readings">
        ${powerReading('gpu_current_total_power','watts','power-count')}
        ${powerReading('gpu_total_rated_power','rated-watts','rated-power-count')}
      </div>
      <small>${t('gpu_rated_power_basis')}</small>
    </article>
  </section>`;
}

function overviewPage(hosts) {
  const issues = hosts.filter(host => ['warning','offline','unknown','stale'].includes(host.status));
  return `<section class="page-title"><div><p class="eyebrow">WATTLINE / OVERVIEW</p>${heading(t('compute_at_a_glance'))}
      <p>${t('current_machine_and_physical_gpu_status_with_trends_over_the_last')}</p></div>
      <div class="title-actions">${globalConfigurationButton()}
      <button type="button" class="control primary-control" data-add-machine ${configUnavailable() ? 'disabled' : ''}>${t(typedResources() ? 'add_resource' : 'add_machine')}</button></div></section>
    ${overviewCards()}
    <div class="overview-stack">
      ${typedResources() ? overviewAlerts(state.snapshot.alerts) : `<section class="panel attention-panel">
        <div class="panel-head"><h2>${t('needs_attention_m051')}</h2><small>${t('machine_count',{count:issues.length})}</small></div>
        ${issues.length ? `<div class="issues">${issues.map(node => `<button type="button" class="issue" data-host="${escape(node.id)}">
          <span class="issue-mark ${escape(node.status)}" aria-hidden="true">${node.status === 'stale' ? '◷' : '!'}</span>
          <span class="issue-copy"><strong>${escape(node.name)}</strong><small>${escape(reason(node))}</small></span>${status(node.status,machineStates[node.status])}
        </button>`).join('')}</div>` : `<p class="empty">${t('no_machines_need_attention')}</p>`}
      </section>`}
      ${chartPanel(null,null)}
      ${machinePanel()}
    </div>`;
}

function machinePanel(detail = false) {
  const filters = [['all',t('all')],['normal',t('healthy')],['warning',t('needs_attention')],['unavailable',t('unavailable')]];
  const selectedStatus = groupedOverview() ? deviceFilterState().status : state.filter;
  return `<section class="panel machine-panel">
        <div class="panel-head"><h2>${t(detail ? 'group_members' : 'machines')}</h2><small id="row-count"></small>
          <button type="button" class="control" data-people-directory ${configUnavailable() ? 'disabled' : ''}>${t('people_directory')}</button></div>
        <div class="tools"><div class="seg" role="group" aria-label="${t('filter_by_machine_status')}">
          ${filters.map(([key,label]) => toggle(label, 'data-filter', key, selectedStatus === key)).join('')}
          </div><input class="search" id="host-search" type="search" aria-label="${t('search_machines')}" placeholder="${t('search_name_or_address')}"></div>
        ${groupedOverview() ? deviceFilters() : ''}
        <p id="order-message" class="order-message" role="status" ${orderMessage ? '' : 'hidden'}>${escape(orderMessage)}</p>
        <div class="scroll machine-scroll" tabindex="0" role="region" aria-label="${t('machines')}"><table class="machine-table ${groupedOverview() ? 'resource-device-table' : ''}">
          <thead><tr><th>${t('machine')}</th><th>${t('status')}</th><th>${t('assignees')}</th><th><span class="wide-label">${t('gpu_utilization')}</span><span class="compact-label" title="${t('average_gpu_utilization')}">GPU</span></th>
          <th aria-label="${t('gpu_power')}"><span class="power-label">${t('gpu_power')}</span><span class="narrow-power-label">${t('power')}</span></th><th>CPU</th><th>${t('memory')}</th>
          ${groupedOverview() ? `<th>${t('storage_capacity_short')}</th><th>${t('device_room_and_clusters')}</th>` : ''}</tr></thead>
          <tbody id="host-rows"></tbody></table></div>
      </section>`;
}

function assigneeSummary(node) {
  if (node.assignment_mode === 'shared') return `<p class="machine-assignees">${t('shared_user')}</p>`;
  const names = node.assigned_users?.map(person => person.name);
  if (!names?.length) return '';
  const list = new Intl.ListFormat(i18n.locale).format(names);
  return `<p class="machine-assignees">${escape(t('assignees_value',{names:list}))}</p>`;
}

function chipName(name) {
  return name.split(/(\s+\S+)/u).map((part, index) => {
    if (index % 2 === 0) return escape(part);
    // A wrapped word keeps its spaces beside its first visible character.
    const spaces = part.match(/^\s+/u)[0];
    const [first] = splitGraphemes(part.slice(spaces.length));
    const prefix = spaces + first;
    return `<span class="chip-name-word"><span class="chip-name-prefix">${escape(prefix)}</span>${escape(part.slice(prefix.length))}</span>`;
  }).join('');
}

function assigneeChips(node) {
  if (node.assignment_mode === 'shared') return `<span class="person-chip">${t('shared_user')}</span>`;
  const names = node.assigned_users?.map(person => person.name);
  return names?.length
    ? `<ul class="assignee-chips">${names.map(name => `<li class="person-chip">${chipName(name)}</li>`).join('')}</ul>`
    : `<span class="unassigned">${t('unassigned')}</span>`;
}

function drawRows(hosts) {
  const filters = groupedOverview() ? deviceFilterState() : {query:state.query,status:state.filter};
  const query = filters.query.trim().toLowerCase();
  const filtered = hosts.filter(node => passesDeviceFilters(node) && (filters.status === 'all' || node.status === filters.status
      || (filters.status === 'unavailable' && !['normal','warning'].includes(node.status)))
    && [node.name,node.id,node.address,...(node.sources ?? []).flatMap(source =>
      [source.name,source.address,source.container_id])].join(' ').toLowerCase().includes(query));
  byId('row-count').textContent = t('filtered_machine_count',{visible:filtered.length,total:hosts.length});
  const sortable = filtered.length > 1 && !configUnavailable();
  byId('host-rows').innerHTML = filtered.length ? filtered.map(node => `<tr data-machine-row="${escape(node.id)}">
    <td><div class="machine-cell">
      <button type="button" class="sort-handle" data-sort-host="${escape(node.id)}"
        aria-label="${t('reorder')} ${escape(node.name)}" title="${t('drag_to_reorder_or_use_up_and_down_arrow_keys')}"
        aria-keyshortcuts="ArrowUp ArrowDown" ${sortable && (groupedOverview() || !node.storage_kind) ? '' : 'disabled'}></button>
      <div class="machine-identity"><button type="button" class="row-open" data-host="${escape(node.id)}" aria-label="${t('view')} ${escape(node.name)}">
      ${machineGlyph(node)}<span><strong>${escape(node.name)}</strong><small class="mono">${escape(node.address)}${node.hardware_kind ? ` · ${hardwareLabel(node.hardware_kind)}` : ''}</small>
      ${node.scope === 'container' ? `<small>${t('container_scope')}</small>` : ''}</span></button>
      </div></div></td>
    <td class="status-cell" data-label="${t('status')}">${status(node.status, machineStates[node.status])}</td>
    <td class="assignee-cell" data-label="${t('assignees')}">${assigneeChips(node)}</td>
    ${['gpu','power','cpu','memory'].map(key => `<td class="number-cell" data-label="${{gpu:t('gpu_utilization'),power:t('gpu_power'),cpu:'CPU',memory:t('memory')}[key]}">${field(node.id+'-'+key)}
      ${key === 'power' ? '' : meter(node.id+'-'+key, key === 'memory' ? 'memory' : '')}
      ${key === 'memory' ? `<small class="memory-used">· ${field(node.id+'-memory-used')}<span>${t('used')}</span></small>` : ''}</td>`).join('')}
    ${groupedOverview() ? `<td data-label="${t('storage_capacity_short')}">${field(node.id+'-storage')}</td>
      <td data-label="${t('device_room_and_clusters')}">${deviceGroupLinks(node)}</td>` : ''}
  </tr>`).join('') : `<tr><td colspan="${groupedOverview() ? 9 : 7}" class="empty">${hosts.length ? t('no_matching_machines_adjust_the_filter_or_search') : t('no_machines_yet_select_add_machine_to_start_monitoring')}</td></tr>`;
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
  const visible = [...byId('host-rows').querySelectorAll('[data-machine-row]:has([data-sort-host]:enabled)')].map(row => row.dataset.machineRow);
  const remaining = visible.filter(id => id !== from);
  const slot = remaining.indexOf(target);
  if (!visible.includes(from) || slot < 0) return;
  remaining.splice(slot + Number(after), 0, from);
  if (visible.every((id,index) => id === remaining[index])) return;

  const moved = remaining.values();
  const visibleSet = new Set(visible);
  const mixed = groupedOverview();
  const all = mixed ? nodes() : state.snapshot.machines;
  const ids = all.map(node => visibleSet.has(node.id) ? moved.next().value : node.id);
  orderSaving = true;
  showOrderMessage(t('saving_order'));
  try {
    const response = await fetch(mixed ? '/api/resources/order' : '/api/machines/order', {
      method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(mixed ? {resources:ids} : {machines:ids}),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof result.detail === 'string'
      ? t('could_not_save_order_please_retry')+' '+i18n.diagnostic(result.detail) : t('could_not_save_order_please_retry'));
    snapshotRevision++;
    if (mixed) state.snapshot.resource_order = result.resources;
    else {
      const ranks = new Map(result.machines.map((id,index) => [id,index]));
      state.snapshot.machines.sort((a,b) => (ranks.get(a.id) ?? ranks.size) - (ranks.get(b.id) ?? ranks.size));
    }
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

function chartControls(host, device) {
  const group = groupChartContext();
  const available = host ? supported(host,device) : group ? groupMetrics : overviewMetrics;
  return `<div class="trend-controls"><div class="seg" role="group" aria-label="${t('trend_metric')}">
    ${available.map(key => toggle(descriptors[key][0], host || state.focused ? 'data-metric' : 'data-overview-metric', key,
      state.focused ? state.focusMetrics.includes(key) : (host ? state.metric : group ? state.groupMetric : state.overviewMetric) === key)).join('')}</div>
    ${host ? `<div class="seg" role="group" aria-label="${t('time_range')}">${[[1,t('1_hour')],[6,t('6_hours')],[24,t('24_hours')],[72,t('3_days')],[168,t('7_days')]]
      .filter(([hours]) => hours <= (state.snapshot?.machine_history_hours ?? 24))
      .map(([hours,label]) => toggle(label,'data-range',hours,state.hours===hours)).join('')}</div>` : ''}</div>`;
}

function chartPlot(host, key = null, index = 0) {
  const suffix = index ? '-'+key : '';
  return `<section class="chart-instance" data-chart-metric="${key || ''}" data-chart-suffix="${suffix}">
    ${key ? `<h2 class="chart-title">${descriptors[key][0]} <small>${descriptors[key][1].trim()}</small></h2>` : ''}
    <div class="plot ${host ? 'large' : ''}"><canvas id="trend-chart${suffix}" tabindex="0" role="img"
      aria-label="${key ? descriptors[key][0]+' · ' : ''}${t('resource_timeline_focus_and_use_left_and_right_arrows_to_inspect_')}" aria-describedby="chart-summary${suffix}"></canvas><div class="chart-tip" id="chart-tip${suffix}" hidden></div></div>
    <p class="chart-summary" id="chart-summary${suffix}"></p><div class="sr-only" id="chart-announcement${suffix}" role="status"></div><div class="chart-legend" id="chart-legend${suffix}"></div><p class="chart-error" id="chart-error${suffix}" hidden>${t(state.archive ? 'archive_chart_failed' : 'historical_metrics_unavailable')}</p>
    <details class="chart-values" id="chart-data${suffix}"><summary>${t('view_chart_data')}</summary><div class="scroll" tabindex="0" role="region" aria-label="${t('view_chart_data')}"></div></details>
  </section>`;
}

function chartPanel(host, device) {
  const source = sourceForId(host, state.historySource);
  const scope = historyScope(host);
  return `<section class="panel chart-panel"><div class="panel-head"><div><h2>${host ? t('resource_trends') : t('last_24_hours')}</h2><small>${host ? device ? 'GPU '+device.index : host.sources?.length > 1 ? '' : t('whole_machine') : t(groupChartContext() ? 'current_group_membership' : 'overview_trend_scope')}</small></div>
    <div class="title-actions">${device ? `<button type="button" class="control" data-all-gpus>${t('back_to_machine')}</button>` : ''}
      ${host && !host.storage_kind && !device ? `<button type="button" id="open-archive" class="control" ${configUnavailable() ? 'disabled' : ''}>${t('archive_analysis')}</button>` : ''}
      <button type="button" id="focus-trends" class="control" data-focus-trends>${t('focus_charts')}</button></div></div>
    ${host?.sources?.length > 1 ? `<div class="tools"><label>${t('trend_source')}
      <select id="trend-source"><option value="">${t('whole_machine')}</option>
      ${host.sources.map(item => `<option value="${escape(item.id)}" ${item === source ? 'selected' : ''}>${escape(sourceLabel(item))}</option>`).join('')}</select>
      </label>${scope ? `<small>${t(scope === 'container' ? 'container_scope' : 'host_scope_label')}</small>` : ''}</div>` : ''}
    ${chartControls(host,device)}${chartPlot(host)}
  </section>`;
}

function setTrendFocus(enabled) {
  if (enabled) {
    focusScroll = window.scrollY;
    state.focusMetrics = [getHost() ? state.metric : groupChartContext() ? state.groupMetric : state.overviewMetric];
  }
  state.focused = enabled;
  renderPage(true);
  paint();
  void refreshHistory(true);
  window.scrollTo(0,enabled ? 0 : focusScroll);
  byId(enabled ? 'exit-trends' : 'focus-trends')?.focus({preventScroll:true});
}

function focusPage(host, device) {
  return `<section class="focus-heading"><div><p class="eyebrow">WATTLINE / ${t('resource_trends')}</p>${heading(host?.name || detailGroup()?.name || t('overview'))}<p>${device ? 'GPU '+device.index+' · ' : ''}${t('choose_charts')}</p></div>
    <button type="button" id="exit-trends" class="control" data-exit-focus>${t('return_to_dashboard')}</button></section>
    ${chartControls(host,device)}<div class="trend-stack" style="--chart-count:${state.focusMetrics.length}">
      ${state.focusMetrics.map((key,index) => `<div class="panel">${chartPlot(host,key,index)}</div>`).join('')}</div>`;
}

function archivePage(host) {
  const archive = state.archive;
  const title = `<section class="page-title"><div>${heading(t('archive_analysis'))}<p>${escape(host.name)}
    ${archive.source ? ' · '+escape(sourceLabel(sourceForId(host,archive.source))) : ''}</p></div>
    <button type="button" id="exit-archive" class="control">${t('back_to_machine')}</button></section>`;
  if (archive.status === 'preparing') {
    return title+`<section class="panel archive-preparation"><p role="status">${t('archive_preparing')}</p>
      <div class="archive-progress"><progress id="archive-progress" max="100" value="${archive.progress}"
        aria-label="${t('archive_preparing')}"></progress><span id="archive-percent">${archive.progress}%</span></div></section>`;
  }
  if (archive.status !== 'ready') {
    const message = {empty:'archive_empty', failed:'archive_failed', expired:'archive_expired'}[archive.status];
    return title+`<section class="panel archive-preparation"><p role="status">${t(message)}</p>
      ${archive.status === 'empty' ? '' : `<button type="button" id="retry-archive" class="control">${t('archive_retry')}</button>`}</section>`;
  }
  return title+`<section class="panel chart-panel">
    <div class="panel-head"><h2>${t('resource_trends')}</h2><small>${t('archive_timezone_label',{zone:escape(archive.timezone)})}</small></div>
    <form class="archive-filters" id="archive-filters">
      <label for="archive-start">${t('archive_start_date')}<input type="date" id="archive-start" value="${escape(archive.start)}" required></label>
      <label for="archive-end">${t('archive_end_date')}<input type="date" id="archive-end" value="${escape(archive.end)}" required></label>
      <label for="archive-metric">${t('trend_metric')}<select id="archive-metric">
        ${archiveMetrics.map(key => `<option value="${key}" ${archive.metric === key ? 'selected' : ''}>${descriptors[key][0]}</option>`).join('')}</select></label>
      <button type="submit" class="control primary-control">${t('archive_apply_range')}</button>
    </form><p id="archive-range-error" class="chart-error" role="alert" ${archive.invalidRange ? '' : 'hidden'}>${t('archive_invalid_range')}</p>
    ${chartPlot(host)}</section>`;
}

function exitArchive() {
  const scroll = state.archive.scroll;
  state.page = null;
  renderPage(true);
  paint();
  void refreshHistory();
  window.scrollTo(0,scroll);
  byId('open-archive')?.focus({preventScroll:true});
}

async function openArchive() {
  const previous = state.archive;
  previous?.controller.abort();
  const host = getHost();
  const archive = state.archive = {path:resourcePath(host)+'/archive-analysis', controller:new AbortController(),
    source:state.historySource, scope:historyScope(host),
    status:'preparing', progress:0, scroll:previous?.scroll ?? window.scrollY,
    start:previous?.start ?? '', end:previous?.end ?? '', metric:previous?.metric ?? state.metric};
  state.page = 'archive';
  renderPage(true);
  window.scrollTo(0,0);
  byId('page-heading')?.focus({preventScroll:true});
  const {controller} = archive;
  const path = archive.path + (archive.source ? '?source='+encodeURIComponent(archive.source) : '');
  const signal = () => AbortSignal.any([controller.signal,AbortSignal.timeout(5000)]);
  try {
    const response = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',signal:signal()});
    if (!response.ok) throw new Error('HTTP '+response.status);
    let info = await response.json();
    while (info.status === 'preparing' && !controller.signal.aborted) {
      archive.progress = info.progress;
      const progress = byId('archive-progress');
      if (progress) progress.value = info.progress;
      const percent = byId('archive-percent');
      if (percent) percent.textContent = info.progress+'%';
      await new Promise(resolve => setTimeout(resolve,350));
      if (controller.signal.aborted) return;
      info = await get(path,signal());
    }
    if (controller.signal.aborted) return;
    archive.status = info.status;
    archive.timezone = info.timezone;
    archive.start ||= info.first_date;
    archive.end ||= info.last_date;
    renderPage(true);
    if (archive.status === 'ready') void refreshArchiveChart(archive);
  } catch {
    if (controller.signal.aborted) return;
    archive.status = 'failed';
    renderPage(true);
  }
}

async function refreshArchiveChart(archive) {
  archive.invalidRange = archive.start > archive.end;
  byId('archive-range-error').hidden = !archive.invalidRange;
  if (archive.invalidRange) return;
  archive.query?.abort();
  const request = archive.query = new AbortController();
  const signal = AbortSignal.any([archive.controller.signal,request.signal]);
  const params = new URLSearchParams({metric:archive.metric,start:archive.start,end:archive.end});
  if (archive.source) params.set('source',archive.source);
  if (archive.scope) params.set('scope',archive.scope);
  if (!archive.source) params.set('view','machine');
  archive.history = null;
  archive.chartError = false;
  archive.singleDay = archive.start === archive.end;
  chart.metric = archive.chartMetric = archive.metric;
  chart.pointer = chart.keyboardAt = null;
  byId('chart-announcement').textContent = '';
  drawChart();
  try {
    const response = await fetch(archive.path+'/series?'+params,{signal});
    if (request.signal.aborted || archive.controller.signal.aborted) return;
    if (response.status === 409) {
      archive.status = 'expired';
      renderPage(true);
      return;
    }
    if (!response.ok) throw new Error('HTTP '+response.status);
    const history = await response.json();
    if (request.signal.aborted || archive.controller.signal.aborted) return;
    archive.history = history;
  } catch {
    if (request.signal.aborted || archive.controller.signal.aborted) return;
    archive.chartError = true;
  }
  drawChart();
}

function sourceLabel(source) {
  return [source?.name, source?.address !== source?.name ? source?.address : null,
    source?.container_id?.slice(0,12)].filter(Boolean).join(' · ');
}

function machineSourceList(host) {
  if (!host.sources?.some(source => source.scope === 'container') && !(host.sources?.length > 1)) return '';
  const {cpu_source_id, memory_source_id} = host.machine_metrics ?? {};
  return `<details class="panel facts machine-sources" data-machine="${escape(host.id)}"><summary>${t('monitoring_sources')}</summary>
    <ul>${host.sources.map(source => {
      const readings = [['cpu',cpu_source_id],['memory',memory_source_id]]
        .filter(([,id]) => source.id === id).map(([key]) => t(key));
      return `<li><span>${t(source.scope === 'container' ? 'container_scope' :
      source.scope === 'host' ? 'host_scope_label' : 'unknown')} · ${escape(sourceLabel(source))}</span>
      ${readings.length ? `<small>${t('current_readings')} · ${readings.join(' / ')}</small>` : ''}
      <button type="button" class="control" data-configure-source="${escape(source.id)}"
        aria-label="${escape(t('configure_source',{source:sourceLabel(source)}))}" ${configUnavailable() ? 'disabled' : ''}>${t('configure')}</button>
    </li>`;
    }).join('')}</ul></details>`;
}

function hostPage(host, device) {
  const statusBadge = status(host.status, machineStates[host.status]);
  const container = host.scope === 'container';
  const unlimited = unlimitedMemory(host);
  const active = checks(host);
  const resources = machineMetrics(host);
  const cpuContainer = (resources?.cpu_scope ?? host.scope) === 'container';
  const memoryContainer = (resources?.memory_scope ?? host.scope) === 'container';
  const showCpu = active.includes('cpu') || resources?.cpu_percent != null;
  const showMemory = active.includes('memory') || resources?.memory_percent != null || unlimited;
  const containerSource = container ? sourceLabel(sourceForId(host,host.reading_source_id)) : '';
  return `<section class="page-title"><div><p class="eyebrow">WATTLINE / NODE</p>${heading(host.name,statusBadge)}
    <p><span class="mono">${escape(host.address)}</span> ${host.hardware_kind ? ` · ${hardwareLabel(host.hardware_kind)}` : ''} · ${host.mode==='ssh' ? 'SSH' : t('local')}
    ${windowsHost(host) ? ' · Windows' : ''}${container ? t('container_scope_m077') : ''}${device ? ' · '+escape(device.name || 'NVIDIA GPU') : ''}</p>
    ${assigneeSummary(host)}${deviceGroupLinks(host)}</div>
    <div class="title-actions"><span class="time">${t('last_valid_sample')} ${field('host-time')}</span>
    <button type="button" class="control" data-configure-machine ${configUnavailable() ? 'disabled' : ''}>${t('configure')}</button></div></section>
    ${typedResources() ? deviceAlerts(host) : ''}
    ${!device ? machineSourceList(host) : ''}
    ${container ? `<p class="message scope-note"><strong>${t('container_scope')}${containerSource ? ' · '+escape(containerSource) : ''}</strong>
      ${active.includes('gpu') ? t('container_gpu_scope_note') : ''}</p>` : ''}
    ${host.reason || host.warnings?.length ? '<p class="message">'+escape(reason(host))+'</p>' : ''}
    <section class="metrics" aria-label="${t('live_machine_resources')}" ${showCpu || showMemory || active.includes('gpu') ? '' : 'hidden'}>
      ${active.includes('gpu') ? metricTile(device ? t('gpu_device_utilization',{index:device.index}) : t('average_gpu_utilization'),'card-gpu','%','≋',
        device ? field('selected-gpu-memory') : t('only_devices_reporting_utilization')) : ''}
      ${active.includes('gpu') ? metricTile(device ? t('gpu_device_power',{index:device.index}) : container ? t('visible_gpu_power') : t('total_gpu_power'),'card-power','W','⌁',
        device ? field('selected-gpu-limit') : container ? t('total_power_of_devices_visible_to_container') : t('calculated_when_device_power_modes_agree')) : ''}
      ${showCpu ? metricTile(t('cpu'),'card-cpu','%','◉',cpuContainer ? t('share_of_container_cpu_capacity') : t('machine_logical_cpus')) : ''}
      ${showMemory ? metricTile(t('memory'),'card-memory',unlimited ? 'GiB' : '%','▤',field('memory-detail')) : ''}
      ${host.hardware_kind === 'cpu' ? metricTile(t('1_minute_load'),'load','','⌁',field('cpu-detail')) +
        metricTile(t('system_disk_available'),'disk','','▥',field('uptime')) : ''}
    </section>
    ${host.metrics && (host.metrics.driver_version || showCpu || showMemory || (!container && active.includes('system'))) ? `<div class="panel facts" aria-label="${t('additional_resource_metrics')}">
      ${showCpu ? `<span>${cpuContainer ? t('container_cpu_capacity') : t('logical_cpus')} <strong>${field('cores')}</strong></span>` : ''}
      ${!cpuContainer && !windowsHost(host) && showCpu ? `<span>${t('1_minute_load')} <strong>${field('load')}</strong></span>` : ''}
      ${!container && active.includes('system') ? `<span>${t('system_disk_available')} <strong>${field('disk')}</strong></span><span>${t('uptime')} <strong>${field('uptime')}</strong></span>` : ''}
      ${showMemory && !unlimited ? `<span>${memoryContainer ? t('memory_limit_headroom') : t('memory_available')} <strong>${field('available')}</strong></span>` : ''}
      ${host.metrics.driver_version ? `<span>${t('nvidia_driver')} <strong>`+escape(host.metrics.driver_version)+'</strong></span>' : ''}</div>` : ''}
    <div class="column details-layout">${chartPanel(host,device)}${host.hardware_kind === 'cpu' ? '' : hardwareTable(host)}</div>`;
}

function hardwareTable(host) {
  const active = checks(host);
  const label = t('hardware_and_processes');
  return `<section class="panel hardware-panel"><div class="panel-head"><h2>${label}</h2><small>${t('observed_device_count',{count:host.devices.length})}</small></div>
    ${host.devices.length ? `<div class="scroll hardware-scroll" tabindex="0" role="region" aria-label="${label}"><table class="hardware-table">
      <caption class="sr-only">${label}</caption><thead><tr>${[t('device'),t('status')+' / '+t('gpu_utilization'),t('vram_used_total'),t('gpu_power')+' / '+t('gpu_temperature'),t('current_gpu_processes')].map(text => `<th scope="col">${text}</th>`).join('')}</tr></thead>
      <tbody>${host.devices.map(device => {
        const gpu = currentDevice(host,device);
        const {rows:processes, omitted} = displayedProcesses(host, active.includes('processes') ? gpu : null);
        const empty = !active.includes('processes') ? t('process_checks_disabled')
          : !gpu || gpu.process_visibility !== 'complete' || gpu.state === 'unknown' ? t('no_verifiable_gpu_process_records_available') : t('no_gpu_processes_found');
        return `<tr><th scope="row"><button type="button" class="gpu-open" data-gpu="${escape(device.uuid)}" aria-haspopup="dialog" aria-label="${t('view_gpu')} ${device.index}"><strong>GPU ${device.index}</strong><span>${escape(device.name || 'NVIDIA GPU')}</span></button></th>
          <td data-label="${t('status')} / ${t('gpu_utilization')}">${status(gpu?.state || 'stale',gpuStates[gpu?.state] || t('no_fresh_sample'))}<strong>${field(device.uuid)}</strong></td>
          <td data-label="${t('vram_used_total')}">${field(device.uuid+'-memory')}</td>
          <td data-label="${t('gpu_power')} / ${t('gpu_temperature')}">${field(device.uuid+'-power')}<small>${field(device.uuid+'-temperature')}</small></td>
          <td data-label="${t('current_gpu_processes')}">${processes.length ? `<ul class="gpu-processes">${processes.map(process => `<li><strong>${escape(process.name || t('unverified'))}</strong> <span class="mono">PID ${escape(process.pid)}</span><small>${t('host_account')}: ${escape(process.user || (process.uid == null ? t('unverified') : 'UID '+process.uid))}${process.user && process.uid != null ? ' · UID '+escape(process.uid) : ''}</small><small>${t('ownership_evidence')}: ${escape(workloadEvidence(process))} · ${t('process_vram')}: ${processVram(host,process)}</small>
          <small>${t('process_started_at')}: ${field(processTimingKey(gpu,process,'start'))}</small>
          <small>${t('process_elapsed')}: ${field(processTimingKey(gpu,process,'elapsed'))}</small></li>`).join('')}</ul>` : `<span class="process-empty">${empty}</span>`}
          ${omittedProcesses(omitted)}${gpu?.process_visibility === 'partial' ? `<small>${t('process_enumeration_is_only_partially_visible_for_this_device')}</small>` : ''}</td></tr>`;
      }).join('')}</tbody></table></div>` : `<p class="empty">${active.includes('gpu')
      ? t(windowsHost(host) && host.gpu_inventory_complete === true ? 'no_nvidia_devices_detected' : 'no_verified_devices_yet')
      : host.require_gpu ? t('gpu_checks_are_disabled') : t('monitored_as_a_cpu_only_machine')}</p>`}
  </section>`;
}

const gpuDialog = byId('gpu-dialog');
gpuDialog.addEventListener('close', () => {
  renderPage();
  paint();
});

function openGpuDialog(uuid) {
  const host = getHost();
  const device = host?.devices.find(item => item.uuid === uuid);
  if (!device) return;
  gpuDialog.dataset.gpu = uuid;
  byId('gpu-dialog-title').textContent = t('gpu_device_info',{index:device.index});
  byId('gpu-dialog-content').innerHTML = gpuInfo(host,device,currentDevice(host,device)) + '<div id="gpu-dialog-processes" hidden></div>';
  gpuDialog.showModal();
  paint();
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
  </section>`;
}

function workloadEvidence(process) {
  const workload = process.workload;
  if (!workload) return t('unverified');
  const id = workload.pod_uid || workload.container_id;
  return (workloads[workload.kind] || t('workload')) + (id ? ' · ' + id.slice(0,12) : '');
}

const processTimingKey = (gpu, process, fieldName) => `process-${gpu.uuid}-${process.pid}-${fieldName}`;

function processRuntime(seconds) {
  const minutes = Math.floor(seconds/60);
  const hours = Math.floor(minutes/60);
  const number = value => i18n.number(value);
  if (hours >= 24) return t('uptime_days',{days:number(Math.floor(hours/24)),hours:number(hours%24)});
  if (hours) return t('process_runtime_hours',{hours:number(hours),minutes:number(minutes%60)});
  if (minutes) return t('process_runtime_minutes',{minutes:number(minutes),seconds:number(seconds%60)});
  return t('process_runtime_seconds',{seconds:number(seconds)});
}

function processTiming(process) {
  const {started_at: startedAt, elapsed_seconds: elapsed} = process;
  if (!Number.isSafeInteger(startedAt) || startedAt <= 0 || startedAt > 8.64e15 ||
      !Number.isSafeInteger(elapsed) || elapsed < 0) {
    const unknown = t('unknown_value');
    return [unknown,unknown];
  }
  return [i18n.date(startedAt,{year:'numeric',month:'2-digit',day:'2-digit',
    hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}), processRuntime(elapsed)];
}

function processTable(host, device, gpu) {
  const {rows, omitted} = displayedProcesses(host, gpu);
  const empty = gpu?.process_visibility === 'complete' && gpu.state !== 'unknown'
    ? t('no_gpu_processes_found') : t('no_verifiable_gpu_process_records_available');
  return `<section class="panel">
    <div class="panel-head"><h2>${t('current_gpu_processes')}</h2><small>GPU ${device.index} · ${t('visible_record_count',{count:gpu?.processes.length ?? 0})}</small>${omittedProcesses(omitted)}</div>
    ${rows.length ? `<div class="scroll" tabindex="0" role="region" aria-label="${t('gpu_process_list')}"><table class="process-table">
      <thead><tr>${['process_pid','host_account','ownership_evidence','device','process_vram','process_started_at','process_elapsed'].map(key => `<th scope="col">${t(key)}</th>`).join('')}</tr></thead>
      <tbody>${rows.map(process => `<tr><td><strong>${escape(process.name || t('unverified'))}</strong><small class="mono">PID ${escape(process.pid)}</small></td>
      <td>${escape(process.user || (process.uid == null ? t('unverified') : 'UID '+process.uid))}
      ${process.user && process.uid != null ? '<small>UID '+escape(process.uid)+'</small>' : ''}</td><td>${escape(workloadEvidence(process))}</td>
      <td>GPU ${device.index}</td><td class="value">${processVram(host,process)}</td>
      <td class="process-timing">${field(processTimingKey(gpu,process,'start'))}</td>
      <td class="process-timing">${field(processTimingKey(gpu,process,'elapsed'))}</td></tr>`).join('')}</tbody>
    </table></div>` : '<p class="empty">'+empty+'</p>'}
    ${gpu?.process_visibility === 'partial' ? `<p class="empty">${t('process_enumeration_is_only_partially_visible_for_this_device')}</p>` : ''}
  </section>`;
}

function paintGpuDialogProcesses(host, device, gpu) {
  const panel = byId('gpu-dialog-processes');
  const shape = device && checks(host).includes('processes') ? JSON.stringify([i18n.locale,device.index,host.target_os,processShape(gpu)]) : '';
  if (panel.dataset.shape === shape) return;
  const focused = panel.contains(document.activeElement);
  const scrollLeft = panel.querySelector('.scroll')?.scrollLeft ?? 0;
  panel.dataset.shape = shape;
  panel.hidden = !shape;
  panel.innerHTML = shape ? processTable(host,device,gpu) : '';
  const region = panel.querySelector('.scroll');
  if (region) region.scrollLeft = scrollLeft;
  if (focused) (region || gpuDialog.querySelector('[autofocus]')).focus({preventScroll:true});
}

function uptime(seconds) {
  if (!Number.isFinite(seconds)) return '—';
  const hours = Math.floor(seconds / 3600);
  if (hours >= 24) return t('uptime_days',{days:Math.floor(hours/24),hours:hours%24});
  return hours ? t('uptime_hours',{hours}) : t('uptime_minutes',{minutes:Math.floor(seconds/60)});
}

function overviewPowerFromSamples(sampled) {
  const devices = new Map();
  const observations = [...sampled].sort((a,b) => (b.observed_at ?? 0)-(a.observed_at ?? 0));
  for (const host of observations) {
    for (const gpu of host.metrics.gpus ?? []) {
      if (typeof gpu.uuid !== 'string' || !gpu.uuid.startsWith('GPU-') || gpu.uuid.length <= 4) continue;
      const id = gpu.uuid.toLowerCase();
      if (!devices.has(id)) devices.set(id,{});
      const reading = devices.get(id);
      if (reading.current == null && Number.isFinite(gpu.power_w) && gpu.power_w >= 0) reading.current = gpu.power_w;
      if (reading.rated == null && Number.isFinite(gpu.default_power_limit_w) && gpu.default_power_limit_w > 0) {
        reading.rated = gpu.default_power_limit_w;
      }
    }
  }
  const readings = [...devices.values()];
  const totals = key => {
    const values = readings.map(reading => reading[key]).filter(Number.isFinite);
    return {value:values.length ? values.reduce((sum,value) => sum+value,0) : null,valid:values.length};
  };
  return {visible_gpu:devices.size,gpu_power:totals('current'),gpu_rated_power:totals('rated')};
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
    const resources = machineMetrics(host);
    const memory = resources?.memory;
    const cpuContainer = (resources?.cpu_scope ?? host.scope) === 'container';
    const memoryContainer = (resources?.memory_scope ?? host.scope) === 'container';
    values['card-gpu'] = fmt(selected ? gpu?.utilization_percent : metrics?.gpu_percent);
    values['card-power'] = fmt(selected ? gpu?.power_w : metrics?.gpu_power_w);
    values['selected-gpu-memory'] = gpu ? fmt(vram(gpu.memory_used_mib),'',1)+' / '+fmt(vram(gpu.memory_total_mib),' GiB',1) : t('no_current_reading');
    values['selected-gpu-limit'] = t('current_power_limit_m146')+fmt(gpu?.power_limit_w,' W');
    values['card-cpu'] = fmt(resources?.cpu_percent);
    values['card-memory'] = unlimitedMemory(host) ? fmt(gib(memory.used_bytes),'',1) : fmt(resources?.memory_percent);
    values['host-time'] = time(host.last_success_at);
    values['cores'] = fmt(resources?.cpu_count,t('cores'),Number.isInteger(resources?.cpu_count) ? 0 : 2);
    values['load'] = fmt(resources?.load_average?.[0],'',2);
    values['cpu-detail'] = cpuContainer ? t('container_scope') : values['cores'];
    const disk = metrics?.root_disk;
    values['disk'] = (disk?.volume ? disk.volume + ' · ' : '') + fmt(gib(disk?.available_bytes),' GiB',1);
    values['available'] = fmt(gib(memory?.available_bytes),' GiB',1);
    values['uptime'] = uptime(metrics?.uptime_seconds);
    values['memory-detail'] = memory?.total_bytes != null
      ? fmt(gib(memory.used_bytes),' GiB',1)+' / '+fmt(gib(memory.total_bytes),' GiB',1)+(memoryContainer ? t('used_including_cache') : t('used'))
      : unlimitedMemory(host) ? t(memoryContainer ? 'no_cgroup_memory_limit_usage_includes_cache' : 'unbounded_memory') : t('no_current_reading');
    for (const device of host.devices) {
      const reading = currentDevice(host,device)?.utilization_percent;
      values[device.uuid] = fmt(reading,'%');
      const live = currentDevice(host,device);
      values[device.uuid+'-memory'] = live ? fmt(vram(live.memory_used_mib),'',1)+' / '+fmt(vram(live.memory_total_mib),' GiB',1) : '—';
      values[device.uuid+'-power'] = fmt(live?.power_w,' W',1);
      values[device.uuid+'-temperature'] = fmt(live?.temperature_c,' °C');
      scales[device.uuid] = reading;
    }
    const detailDevice = gpuDialog.open ? host.devices.find(item => item.uuid === gpuDialog.dataset.gpu) : selected;
    const detailGpu = detailDevice && currentDevice(host,detailDevice);
    if (gpuDialog.open) paintGpuDialogProcesses(host,detailDevice,detailGpu);
    for (const gpu of metrics?.gpus ?? []) {
      for (const process of gpu.processes) {
        const [startedAt, elapsed] = processTiming(process);
        values[processTimingKey(gpu,process,'start')] = startedAt;
        values[processTimingKey(gpu,process,'elapsed')] = elapsed;
      }
    }
    if (detailDevice) {
      const selected = detailDevice, gpu = detailGpu;
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
    const configured = hosts.filter(node => node.require_gpu);
    const summary = state.snapshot?.summary;
    const power = summary ?? overviewPowerFromSamples(sampled);
    values.online = (summary?.online ?? sampled.length+hosts.filter(node => node.storage_observation).length)+
      ' / '+(summary?.registered ?? hosts.length);
    values.visible = power.visible_gpu;
    values['configured-gpu'] = configured.every(node => node.expected_gpu_count != null)
      ? t('configured_device_count',{count:configured.reduce((total,node) => total+node.expected_gpu_count,0)}) : t('current_samples_only');
    for (const [reading,key,coverage] of [[power.gpu_power,'watts','power-count'],
      [power.gpu_rated_power,'rated-watts','rated-power-count']]) {
      values[key] = Number.isFinite(reading?.value) ? i18n.number(reading.value,{maximumFractionDigits:1}) : '—';
      values[coverage] = t('gpu_power_coverage',{valid:i18n.number(reading?.valid ?? 0),total:i18n.number(power.visible_gpu)});
    }
    for (const node of hosts) {
      if (node.storage_kind) {
        values[node.id+'-storage'] = capacityLabel(node.storage_observation?.capacity);
        continue;
      }
      const resources = machineMetrics(node);
      for (const [key, value] of Object.entries({gpu:node.metrics?.gpu_percent, power:node.metrics?.gpu_power_w,
        cpu:resources?.cpu_percent, memory:resources?.memory_percent})) {
        const id = node.id+'-'+key;
        values[id] = fmt(value,key === 'power' ? ' W' : '%');
        scales[id] = value;
      }
      if (unlimitedMemory(node)) values[node.id+'-memory'] = fmt(gib(resources.memory.used_bytes),' GiB',1);
      else {
        const memory = resources?.memory;
        values[node.id+'-memory-used'] = groupedOverview() && memory?.total_bytes != null && Number.isFinite(memory.used_bytes)
          ? bytesLabel(memory.used_bytes)+' / '+bytesLabel(memory.total_bytes) : fmt(gib(memory?.used_bytes),' GiB',1);
      }
    }
  }

  for (const node of document.querySelectorAll('[data-value]')) {
    const value = values[node.dataset.value] ?? '—';
    node.textContent = value;
    const used = node.closest('.memory-used');
    if (used) used.hidden = value === '—';
    const unit = node.parentElement.nextElementSibling;
    if (node.closest('.metric') && node.parentElement.tagName === 'STRONG' && unit?.classList.contains('unit')) {
      unit.hidden = value === '—';
    }
  }
  if (groupedOverview()) paintGroups();
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

const activeMetrics = () => state.focused ? state.focusMetrics : [state.archive?.chartMetric ??
  (state.machine ? state.metric : groupChartContext() ? state.groupMetric : state.overviewMetric)];
const historyHours = () => state.machine ? state.hours : 24;
async function refreshHistory(reset = false) {
  if (state.archive) return;
  if (reset) {
    historyRequest?.abort();
    state.history = null;
    state.histories = {};
    state.historyErrors = {};
    state.historyError = false;
    for (const instance of charts) instance.pointer = instance.keyboardAt = null;
    drawChart();
  } else if (historyRequest) return;
  if (!state.snapshot || !charts.length) return;
  const host = getHost(), gpu = getDevice(host);
  const group = groupChartContext();
  if (group && !group.groups.length) return;
  const controller = new AbortController();
  historyRequest = controller;
  const metrics = [...activeMetrics()];
  await Promise.all(metrics.map(async metric => {
    const params = new URLSearchParams({hours:historyHours()});
    if (host) params.set('machine',host.id);
    if (host && !host.storage_kind) {
      if (state.historySource) params.set('source',state.historySource);
      const scope = historyScope(host);
      if (scope && ['cpu','memory','memory_used'].includes(metric)) params.set('scope',scope);
      if (!state.historySource && !gpu) params.set('view','machine');
    }
    params.set('metric',metric);
    if (gpu) params.set('gpu',gpu.uuid);
    if (group) {
      params.delete('hours');
      params.set('kind',group.kind);
      params.set('view','machine');
      for (const record of group.groups) params.append('group',record.id);
    }
    try {
      const path = group ? '/api/group-history?' : host?.storage_kind ? resourcePath(host)+'/history?' : '/api/history?';
      const history = await get(path+params, AbortSignal.any([controller.signal,AbortSignal.timeout(5000)]));
      if (historyRequest !== controller) return;
      state.histories[metric] = history;
      state.historyErrors[metric] = false;
      if (metric === metrics[0]) state.history = history;
    } catch {
      if (historyRequest === controller) state.historyErrors[metric] = true;
    }
    if (historyRequest === controller) drawChart();
  }));
  if (historyRequest === controller) {
    state.historyError = Boolean(state.historyErrors[metrics[0]]);
    historyRequest = null;
  }
}

async function refresh() {
  const previousHost = getHost();
  const previousScope = historyScope(previousHost);
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
  if (groupedOverview() && !state.routeReady) {
    state.routeReady = true;
    if (location.hash) restoreWorkspaceURL();
  }
  const host = getHost();
  if (state.machine && !host) openHost(null);
  if (host && state.machine !== host.id) {
    state.machine = host.id;
    if (groupedOverview()) window.history.replaceState(null,'','#device/'+encodeURIComponent(host.id));
  }
  const resetSource = state.historySource && !sourceForId(host,state.historySource);
  if (resetSource) state.historySource = null;
  if (state.page === 'group' && !detailGroup()) openHost(null);
  if (machineDialog.open && machineForm.dataset.machine) updateMachineConfiguration(configurationTarget());
  if (state.page === 'alerts' && (state.alerts?.events.length ?? 0) <= 200 &&
      performance.now()-(state.alertRefreshAt ?? 0) > 10000) void loadAlerts();
  const replaced = state.gpu && !getDevice(getHost());
  if (replaced) {
    state.gpu = null;
    state.metric = 'gpu';
    state.focusMetrics = ['gpu'];
  }
  renderPage();
  paint();
  const lastQuery = state.history?.to ?? 0;
  const liveTrendDue = historyHours() <= 24 && state.snapshot?.server_time-lastQuery >= 5000;
  const scopeChanged = previousHost?.id !== host?.id || previousScope !== historyScope(host);
  if (replaced || resetSource || scopeChanged || !state.history || liveTrendDue || Object.values(state.historyErrors).some(Boolean)) {
    void refreshHistory(Boolean(replaced || resetSource || scopeChanged));
  }
  window.setTimeout(refresh,2000);
}

function countLabels(labels) {
  const counts = new Map();
  for (const label of labels) counts.set(label,(counts.get(label) || 0)+1);
  return counts;
}

const chartHistory = metric => state.archive ? state.archive.history : state.histories[metric];

function chartSeries(instance, history) {
  if (groupChartContext()) {
    const [,unit] = descriptors[instance.metric];
    return (history?.series ?? []).map((item,index) => ({
      key:instance.metric, id:item.group, hidden:state.hiddenGroups.has(item.group), unit,
      label:item.name+(['host','container'].includes(item.scope)
        ? ' · '+t(item.scope === 'container' ? 'container_scope' : 'host_scope_label') : ''),
      color:machineColors[index % machineColors.length],
      dash:machineDashes[item.scope === 'container' ? 1+(index%3) : index%3],
    }));
  }
  if (!state.machine) {
    const hosts = nodes();
    const ids = history?.machines ?? hosts.filter(host => host.enabled).map(host => host.id);
    const hostsById = new Map(hosts.map(host => [host.id,host]));
    const names = ids.map(id => hostsById.get(id)?.name || id);
    const nameCounts = countLabels(names);
    const labels = names.map((name,index) => {
      const id = ids[index];
      return nameCounts.get(name) > 1 ? name+' · '+(hostsById.get(id)?.address || id) : name;
    });
    const labelCounts = countLabels(labels);
    const [,unit] = descriptors[instance.metric];
    return labels.map((label,index) => ({
      key:instance.metric,
      label:labelCounts.get(label) > 1 ? label+' · '+ids[index] : label,
      unit, color:machineColors[index % machineColors.length],
      dash:machineDashes[Math.floor(index / machineColors.length) % machineDashes.length]
    }));
  }
  const keys = history?.keys || [instance.metric];
  return keys.map(key => {
    const [title,unit] = descriptors[key];
    const label = history?.scope ? title+' · '+t(history.scope === 'container' ? 'container_scope' : 'host_scope_label')
      : key === 'power' && !state.gpu && !state.archive
        ? (historyScope(getHost()) === 'container' || getHost()?.scope === 'container' || getHost()?.sources?.length > 1
          ? t('visible_gpu_power') : t('total_gpu_power')) : title;
    return {key,label,unit,color:colors[key],dash:[]};
  });
}

function bindChart() {
  for (const element of document.querySelectorAll('.chart-instance')) {
    const canvas = element.querySelector('canvas');
    const instance = {canvas, suffix:element.dataset.chartSuffix,
      metric:element.dataset.chartMetric || activeMetrics()[0],
      pointer:null,keyboardAt:null,points:[]};
    const observer = new ResizeObserver(() => drawChart(instance));
    instance.observer = observer;
    charts.push(instance);
    observer.observe(canvas);
    byId('chart-data'+instance.suffix).addEventListener('toggle', () => drawChart(instance));
    canvas.addEventListener('pointermove',event => {
      instance.pointer = event.clientX-canvas.getBoundingClientRect().left;
      instance.keyboardAt = null;
      drawChart(instance);
    });
    canvas.addEventListener('pointerleave',() => {instance.pointer = null;drawChart(instance);});
    canvas.addEventListener('keydown',event => {
      if (!['ArrowLeft','ArrowRight','Escape'].includes(event.key)) return;
      event.preventDefault();
      if (event.key === 'Escape' && (instance.keyboardAt != null || instance.pointer != null)) event.stopPropagation();
      instance.pointer = null;
      if (event.key === 'Escape') instance.keyboardAt = null;
      else if (instance.points.length) instance.keyboardAt = clamp((instance.keyboardAt ?? instance.points.length-1)
        + (event.key === 'ArrowLeft' ? -1 : 1),0,instance.points.length-1);
      drawChart(instance);
      const point = instance.points[instance.keyboardAt];
      byId('chart-announcement'+instance.suffix).textContent = point
        ? tooltipTime.format(point.time)+' · '+chartSeries(instance,chartHistory(instance.metric)).flatMap((item,i) => item.hidden ? [] : [item.label+' '+chartReading(point,i,item,1)]).join(' · ') : '';
    });
    canvas.addEventListener('blur',() => {
      if (!canvas.isConnected) return;
      instance.keyboardAt = null;
      drawChart(instance);
    });
  }
  chart = charts[0] || null;
  drawChart();
}

function chartCeiling(series, points) {
  const metric = series[0];
  if (metric.unit === '%') return 100;
  const max = Math.max(0,...points.flatMap(point => point.values.filter((value,index) => !series[index]?.hidden && Number.isFinite(value))));
  const step = metric.key === 'power' ? max > 800 ? 400 : max > 180 ? 100 : 40 : metric.key === 'temp' ? 25 : 16;
  return Math.max(step, Math.ceil(max/step)*step);
}

function setSeriesStroke(ctx, series) {
  ctx.lineWidth = 1.8;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.strokeStyle = series.color;
  ctx.setLineDash(series.dash);
}

function paintLegend(chart, series, bucket) {
  const key = JSON.stringify([series,bucket,i18n.locale]);
  if (chart.legendKey === key) return;
  chart.legendKey = key;
  const legend = byId('chart-legend'+chart.suffix);
  const entries = series.map(item => {
    const entry = document.createElement(item.id ? 'button' : 'span');
    if (item.id) {
      entry.type = 'button';
      entry.setAttribute('aria-pressed',String(!item.hidden));
      entry.dataset.legendGroup = item.id;
      entry.addEventListener('click',() => {
        const ids = new Set(series.filter(other => !other.hidden).map(other => other.id));
        if (!item.hidden && ids.size <= 1) return;
        if (item.hidden) state.hiddenGroups.delete(item.id);
        else state.hiddenGroups.add(item.id);
        drawChart();
        byId('chart-legend'+chart.suffix).querySelector(`[data-legend-group="${CSS.escape(item.id)}"]`)?.focus();
      });
    }
    entry.className = 'chart-legend-item';
    const swatch = document.createElement('canvas');
    swatch.className = 'legend-line';
    swatch.width = 104;
    swatch.height = 8;
    swatch.setAttribute('aria-hidden','true');
    const ctx = swatch.getContext('2d');
    ctx.scale(2,2);
    setSeriesStroke(ctx,item);
    ctx.beginPath();
    ctx.moveTo(1,2);
    ctx.lineTo(51,2);
    ctx.stroke();
    const label = document.createElement('span');
    label.textContent = item.label+(item.unit === '%' ? '' : ' · '+item.unit.trim());
    entry.append(swatch,label);
    return entry;
  });
  if (series.length) {
    const note = document.createElement('span');
    note.className = 'chart-note';
    note.textContent = (groupChartContext() ? t('current_group_membership')+' · ' :
      bucket ? fmt(bucket/1000,t('second_average'))+' · ' : '')+t('gaps_indicate_discontinuous_samples');
    entries.push(note);
  }
  legend.replaceChildren(...entries);
}

function drawChart(instance) {
  if (!instance) { charts.forEach(item => drawChart(item)); return; }
  const chart = instance;
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
  const history = chartHistory(chart.metric);
  const historyError = state.archive ? state.archive.chartError : state.historyErrors[chart.metric];
  const end = history?.to ?? state.snapshot?.server_time ?? Date.now();
  const hours = state.archive && history ? (history.to-history.from)/3600000 : historyHours();
  const start = history?.from ?? end-hours*3600000;
  const points = (history?.points || []).map(point => ({...point, values:point.values.map((value,i) =>
    history.keys?.[i] === 'vram' ? vram(value) : history.keys?.[i] === 'memory_used' ? gib(value) : value)}));
  chart.points = points;
  const series = chartSeries(chart,history);
  paintLegend(chart,series,history?.bucket_ms);
  const data = byId('chart-data'+chart.suffix);
  // Build the accessible alternative only on demand, never on every pointer move.
  const visible = series.map((item,index) => ({item,index})).filter(({item}) => !item.hidden);
  if (data.open && (chart.tableHistory !== history || chart.tableLegendKey !== chart.legendKey)) {
    chart.tableHistory = history;
    chart.tableLegendKey = chart.legendKey;
    data.querySelector('.scroll').innerHTML = visible.length ? `<table><caption>${visible.map(({item}) => escape(item.label)).join(' / ')}</caption>
      <thead><tr><th scope="col">${t('sample_time')}</th>${visible.map(({item}) => `<th scope="col">${escape(item.label)} (${item.unit.trim()})</th>`).join('')}</tr></thead>
      <tbody>${points.map(point => `<tr><th scope="row">${tooltipTime.format(point.time)}</th>${visible.map(({item,index}) => `<td>${chartReading(point,index,item,1)}</td>`).join('')}</tr>`).join('')}</tbody></table>` : '';
  }
  byId('chart-error'+chart.suffix).hidden = !historyError;
  const summary = byId('chart-summary'+chart.suffix);
  if (!series.length) {
    const group = groupChartContext();
    summary.textContent = historyError ? t('could_not_load_history_retrying_automatically') :
      t(group ? group.groups.length ? 'loading_historical_samples' : 'no_groups_for_chart' : 'no_enabled_machines');
    byId('chart-tip'+chart.suffix).hidden = true;
    ctx.font = '12px system-ui, sans-serif';
    ctx.fillStyle = '#526862';
    ctx.textAlign = 'center';
    ctx.fillText(summary.textContent,width/2,height/2);
    return;
  }
  const ceiling = chartCeiling(series,points);
  const left = series[0].key === 'power' ? 50 : 41;
  const right = width-12;
  const top = 13;
  const bottom = height-25;
  const x = timestamp => left+(timestamp-start)/Math.max(1,end-start)*(right-left);
  const y = value => bottom-value/ceiling*(bottom-top);
  const layout = {bottom,left,right,top,x,y};
  ctx.font = '10.5px system-ui, sans-serif';
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'right';
  const axisUnit = series[0].unit === '%' || (!state.machine && chart.metric === 'power') ? series[0].unit : '';
  for (let i=0;i<=4;i++) {
    const value = ceiling*i/4;
    ctx.fillStyle = '#526862';
    ctx.fillText(fmt(value, axisUnit, Number.isInteger(value) ? 0 : 1),left-6,y(value));
    ctx.strokeStyle = '#e9f0ec';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(left,y(value));
    ctx.lineTo(right,y(value));
    ctx.stroke();
  }
  const dateTicks = state.archive && history ? !state.archive.singleDay : hours > 24;
  const intervals = dateTicks ? Math.min(Math.ceil(hours/24),width >= 550 ? 6 : 3)
    : width >= 540 ? 6 : width >= 355 ? 4 : 3;
  const tickFormat = dateTicks ? shortDate : shortTime;
  for (let i=0;i<=intervals;i++) {
    const timestamp = start+(end-start)*i/intervals;
    ctx.textAlign = i === 0 ? 'left' : i === intervals ? 'right' : 'center';
    ctx.fillText(tickFormat.format(timestamp),x(timestamp),bottom+13);
  }
  const valid = points.filter(point => visible.some(({index}) => Number.isFinite(point.values[index])));
  summary.textContent = historyError ? (state.archive ? '' : t('could_not_load_history_retrying_automatically'))
    : !history ? t('loading_historical_samples') : !valid.length ? t('no_valid_samples_in_this_window')
    : state.machine ? t('history_summary',{count:i18n.number(valid.length),latest:series.map((item,i) =>
      item.label+' '+fmt(valid.at(-1).values[i],item.unit,1)).join(' / ')})
    : groupChartContext() ? t('group_count',{count:new Set(visible.map(({item}) => item.id)).size})
    : t('overview_history_summary',{count:i18n.number(valid.length),machines:i18n.number(series.length)});
  if (!valid.length && (!state.archive || !historyError)) {
    ctx.font = '12px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(history ? t('no_valid_samples_in_this_window_m159') : t('waiting_for_historical_samples'),(left+right)/2,(top+bottom)/2);
  }
  paintSeries(ctx,points,layout,series);
  paintTooltip(ctx,series,layout,width,chart);
}

function openHost(id, remember = true) {
  id = machineForId(id)?.id ?? id;
  if (id && !state.page && !state.machine) state.overviewScroll = window.scrollY;
  if (id && state.page === 'group' && state.group) state.trail = [...state.trail,state.group].slice(-2);
  if (!id || state.page !== 'group' && !state.machine) state.trail = [];
  state.group = null;
  if (remember) updateWorkspaceURL(id ? 'device' : 'overview',id);
  state.focused = false;
  state.page = null;
  state.machine = id;
  state.historySource = null;
  state.gpu = null;
  state.metric = getHost()?.storage_kind ? 'storage' : 'cpu';
  state.hours = 24;
  renderPage(true);
  paint();
  void refreshHistory(true);
  window.scrollTo(0,id ? 0 : state.overviewScroll);
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

function isLinuxGpu(host, kind = host?.configured_hardware_kind ?? '', gpu = host?.require_gpu) {
  return Boolean(host && !host.storage_kind && (kind === 'gpu' || (!kind && gpu))
    && !windowsHost(host) && host.scope !== 'container');
}

function updateMachineConfiguration(host) {
  const policy = host?.idle_memory_configuration;
  const sampled = host?.sample_idle_memory_configuration;
  const section = byId('machine-sampled-configuration');
  byId('machine-configuration-summary').textContent = configurationSummary(policy);
  const differs = policy && sampled && (policy.effective !== sampled.effective
    || JSON.stringify(policy.source) !== JSON.stringify(sampled.source));
  section.hidden = !differs || !(host.has_sample ?? Boolean(host.metrics));
  section.textContent = differs ? t('configuration_latest_sample', {policy:effectiveConfiguration(sampled)}) : '';
  const conflict = byId('machine-configuration-conflict');
  conflict.hidden = !policy?.cluster_conflict && !policy?.invalid_cluster_selection;
  conflict.textContent = [
    policy?.cluster_conflict ? t('configuration_cluster_conflict') : '',
    policy?.invalid_cluster_selection ? t('configuration_cluster_ineligible') : '',
  ].filter(Boolean).join(' ');
  const assignees = host?.assigned_users?.map(person => person.name) ?? [];
  byId('machine-assignment-preview').textContent = host?.assignment_mode === 'shared' ? t('shared_user')
    : assignees.length ? new Intl.ListFormat(i18n.locale).format(assignees) : t('unassigned');
}

function openMachineDialog(host) {
  machineForm.reset();
  machineForm.dataset.machine = host?.id ?? '';
  byId('machine-dialog-title').textContent = host ? t('machine_settings') : t(typedResources() ? 'add_resource' : 'add_machine');
  byId('machine-target').textContent = host?.address ?? '';
  byId('machine-target').hidden = !host;
  byId('machine-connection').hidden = !!host;
  const fields = machineForm.elements;
  fields.host.disabled = fields.ssh_user.disabled = fields.target_os.disabled = !!host;
  fields.alias.value = host?.alias ?? '';
  fields.alias.placeholder = host?.default_name ?? t('leave_blank_for_default_name');
  fields.interval_seconds.value = host?.interval_seconds ?? state.snapshot.period_ms / 1000;
  const local = host?.mode === 'local';
  byId('ssh-timeout-field').hidden = local;
  fields.ssh_connect_timeout_seconds.disabled = local;
  fields.ssh_connect_timeout_seconds.value = host?.ssh_connect_timeout_seconds ?? state.snapshot.default_ssh_connect_timeout_seconds;
  const policy = host?.idle_memory_configuration;
  initializeTolerance(fields.idle_memory_tolerance_mib, policy ?? {override:host?.idle_memory_tolerance_mib});
  const source = fields.configuration_cluster_id;
  source.innerHTML = `<option value="">${t('configuration_cluster_auto')}</option>` +
    (policy?.cluster_candidates ?? []).map(({id,value}) => `<option value="${escape(id)}">${escape(
      (groupRecord('cluster',id)?.name ?? id) + ' · ' + configurationValue(value))}</option>`).join('');
  if (policy?.invalid_cluster_selection) {
    const id = policy.selected_cluster_id;
    source.add(new Option(t('configuration_cluster_stale', {name:groupRecord('cluster',id)?.name ?? id}), id));
  }
  source.value = source.dataset.savedValue = policy?.selected_cluster_id ?? '';
  byId('machine-properties-heading').hidden = byId('machine-assignment-section').hidden = !host;
  const remove = machineForm.querySelector('[data-remove-machine]');
  remove.hidden = !host;
  setButtonLabel(remove, getHost()?.sources?.length > 1 ? 'remove_source' : 'remove_node');
  updateMachineConfiguration(host);
  fields.enabled.checked = host?.enabled ?? true;
  for (const input of checkboxes) input.checked = !host || checks(host).includes(input.value);
  fields.hardware_kind.value = host?.storage_kind ? 'storage' : host?.configured_hardware_kind ?? '';
  fields.hardware_kind.querySelector('[value=storage]').hidden = !typedResources() || Boolean(host && !host.storage_kind);
  fields.hardware_kind.disabled = !typedResources() || Boolean(host?.storage_kind);
  fields.storage_name.value = host?.storage_kind ? host.name : '';
  fields.storage_kind.value = host?.storage_kind ?? 'nas';
  fields.storage_enabled.checked = host?.enabled ?? true;
  const adapters = new Set([...(state.snapshot.storage_adapters ?? []), ...(host?.adapter ? [host.adapter] : [])]);
  fields.adapter.innerHTML = `<option value="">${t('storage_pending')}</option>`+
    [...adapters].map(id => `<option value="${escape(id)}">${escape(id)}</option>`).join('');
  fields.adapter.value = host?.adapter ?? '';
  const room = groupedOverview();
  byId('machine-placement-heading').hidden = !host || !room;
  byId('registration-room').hidden = fields.room_id.disabled = !room;
  fields.room_id.innerHTML = roomOptions(host?.room_id ?? (state.group?.kind === 'room' ? state.group.id : null));
  const names = (host?.cluster_ids ?? []).map(id => groupRecord('cluster',id)?.name ?? id);
  byId('machine-clusters').hidden = !host || !room;
  byId('machine-clusters').textContent = t('configuration_machine_clusters', {
    clusters:names.length ? new Intl.ListFormat(i18n.locale).format(names) : t('no_cluster'),
  });
  byId('registration-user').hidden = Boolean(host) || !typedResources();
  fields.resource_user.innerHTML = personOptions(true);
  updateResourceForm();
  machineError.hidden = true;
  machineDialog.showModal();
  (host?.storage_kind ? fields.storage_name : host ? fields.alias : fields.host).focus();
}

function personOptions(shared = false) {
  return `<option value="">${t('unassigned')}</option>${shared ? `<option value="shared">${t('shared_user')}</option>` : ''}` +
    directoryPeople().map(person => `<option value="${person.id}">${escape(person.name)}</option>`).join('');
}

function updateResourceForm() {
  const {hardware_kind, idle_memory_tolerance_mib, configuration_cluster_id} = machineForm.elements;
  const storage = hardware_kind.value === 'storage';
  byId('storage-fields').hidden = byId('storage-fields').disabled = !storage;
  byId('compute-fields').hidden = byId('compute-fields').disabled = storage;
  gpuCheck.disabled = hardware_kind.value === 'cpu';
  if (gpuCheck.disabled) gpuCheck.checked = false;
  updateProcessCheck();
  const host = machineForm.dataset.machine ? configurationTarget() : null;
  const showTolerance = isLinuxGpu(host, hardware_kind.value, host?.require_gpu || gpuCheck.checked)
    && Number.isFinite(host.idle_memory_tolerance_mib);
  byId('idle-memory-tolerance-field').hidden = idle_memory_tolerance_mib.disabled = !showTolerance;
  byId('machine-source-field').hidden = configuration_cluster_id.disabled = !showTolerance
    || configuration_cluster_id.options.length <= 1;
}

machineForm.elements.hardware_kind.addEventListener('change', updateResourceForm);
gpuCheck.addEventListener('change', updateResourceForm);
machineCancel.addEventListener('click', () => machineDialog.close());
machineDialog.addEventListener('cancel', event => {
  if (machineSave.disabled) event.preventDefault();
});
machineDialog.addEventListener('close', () => {
  renderPage();
  paint();
});
machineForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (machineSave.disabled) return;
  const id = machineForm.dataset.machine;
  const fields = new FormData(machineForm);
  const storage = machineForm.elements.hardware_kind.value === 'storage';
  const settings = storage ? {
    name:fields.get('storage_name').trim(),
    storage_kind:fields.get('storage_kind'),
    adapter:fields.get('adapter') || null,
    enabled:fields.has('storage_enabled'),
  } : {
    alias:fields.get('alias').trim() || null,
    enabled:fields.has('enabled'),
    interval_seconds:Number(fields.get('interval_seconds')),
    checks:fields.getAll('checks'),
  };
  if (fields.has('ssh_connect_timeout_seconds')) {
    settings.ssh_connect_timeout_seconds = Number(fields.get('ssh_connect_timeout_seconds'));
  }
  const {idle_memory_tolerance_mib, configuration_cluster_id} = machineForm.elements;
  includeToleranceChange(settings, idle_memory_tolerance_mib);
  if (fields.has(configuration_cluster_id.name) && configuration_cluster_id.value !== configuration_cluster_id.dataset.savedValue) {
    settings.configuration_cluster_id = configuration_cluster_id.value || null;
  }
  if (!storage && settings.enabled && !settings.checks.length) {
    machineError.textContent = t('select_at_least_one_check_when_monitoring_is_enabled');
    machineError.hidden = false;
    gpuCheck.focus();
    return;
  }
  if (fields.has('room_id')) settings.room_id = fields.get('room_id') || null;
  if (!storage && fields.has('hardware_kind')) settings.hardware_kind = fields.get('hardware_kind') || null;
  if (!id && typedResources()) {
    const user = fields.get('resource_user');
    settings.shared = user === 'shared';
    settings.person_id = user && !settings.shared ? Number(user) : null;
  }
  if (!id && !storage) {
    settings.host = fields.get('host').trim();
    settings.ssh_user = fields.get('ssh_user').trim() || null;
    settings.target_os = fields.get('target_os');
  }
  machineSave.disabled = machineCancel.disabled = machineFields.disabled = true;
  setButtonLabel(machineSave, id || storage ? 'saving' : 'verifying_connection');
  machineError.hidden = true;
  try {
    const path = storage ? id ? '/api/storage/'+encodeURIComponent(id) : '/api/storage'
      : id ? '/api/machines/'+encodeURIComponent(id)+'/settings' : '/api/machines';
    const response = await fetch(path, {
      method:id ? 'PUT' : 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(settings),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = result.detail === 'configuration_cluster_ineligible' ? t(result.detail)
        : typeof result.detail === 'string' ? t('could_not_save_please_retry_later')+' '+alertEvidence(result.detail)
        : response.status === 422 ? t('check_the_address_username_and_monitoring_settings') : t('could_not_save_please_retry_later');
      throw new Error(detail);
    }
    snapshotRevision++;
    machineDialog.close();
    if (!storage && state.snapshot.machines.some(node => node.sources)) {
      await refreshWorkspace();
      if (!id) openHost(result.id);
      else document.querySelector('[data-configure-machine]')?.focus({preventScroll:true});
      return;
    }
    const resources = storage ? state.snapshot.storage : state.snapshot.machines;
    const index = resources.findIndex(node => node.id === result.id);
    if (index === -1) resources.push(result);
    else resources[index] = result;
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

const assigneeDialog = byId('assignee-dialog');
const assigneeForm = byId('assignee-form');
const assigneeOptions = byId('assignee-options');
const assigneeMode = byId('assignee-mode');
const assigneeSave = byId('assignee-save');
const assigneeCancel = byId('assignee-cancel');
const assigneeClear = byId('assignee-clear');
const assigneeManage = byId('assignee-manage');
const assigneeError = byId('assignee-error');
const assigneeCount = byId('assignee-count');
const peopleDialog = byId('people-dialog');
const peopleForm = byId('people-form');
const peopleList = byId('people-list');
const peopleName = peopleForm.elements.name;
const peopleSave = byId('people-save');
const peopleCancelEdit = byId('people-cancel-edit');
const peopleClose = byId('people-close');
const peopleError = byId('people-error');
let editingPerson = null;

function directoryPeople() {
  return [...(state.snapshot.people ?? [])].sort((a,b) => a.name.localeCompare(b.name, i18n.locale));
}

async function peopleRequest(path, method, body, invalidKey) {
  const response = await fetch(path, {method, headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  if (response.status === 204) return null;
  const result = await response.json();
  if (response.ok) return result;
  if (result.detail?.references) {
    const {devices,rooms,clusters} = result.detail.references;
    const lists = [[t('machines'),devices],[t('rooms'),rooms],[t('clusters'),clusters]]
      .filter(([,names]) => names.length).map(([label,names]) => label+' '+names.join(', '));
    throw new Error(t('person_in_use')+' '+lists.join(' · '));
  }
  const known = ['person_in_use', 'person_name_taken', 'person_missing', 'assignee_machine_missing'];
  const key = known.includes(result.detail) ? result.detail : response.status === 422 ? invalidKey : 'people_save_failed';
  throw new Error(t(key));
}

function showPeopleError(target, error) {
  target.textContent = error.name === 'Error' ? error.message : t('people_save_failed');
  target.hidden = false;
}

function selectedAssignees() {
  return new Set([...assigneeOptions.querySelectorAll('input:checked')].map(input => Number(input.value)));
}

function updateAssigneeCount() {
  assigneeCount.textContent = t('selected_people_count',{count:selectedAssignees().size});
}

function renderAssigneeOptions(selected) {
  const people = directoryPeople();
  assigneeOptions.innerHTML = people.length ? people.map(person =>
    `<label class="assignee-chip"><input type="checkbox" value="${person.id}" aria-label="${escape(person.name)}" ${selected.has(person.id) ? 'checked' : ''}>
      <span class="assignee-chip-mark" aria-hidden="true"></span><span class="assignee-chip-name">${chipName(person.name)}</span></label>`).join('') : `<p>${t('no_people')}</p>`;
  updateAssigneeMode();
}

function updateAssigneeMode() {
  const typed = !byId('assignee-mode-field').hidden;
  assigneeOptions.hidden = typed && !['person','legacy'].includes(assigneeMode.value);
  assigneeClear.hidden = assigneeOptions.hidden;
  updateAssigneeCount();
}

assigneeMode.addEventListener('change', () => {
  if (assigneeMode.value === 'person') {
    for (const input of [...assigneeOptions.querySelectorAll('input:checked')].slice(1)) input.checked = false;
  }
  updateAssigneeMode();
});

function openAssigneeDialog(host) {
  assigneeForm.dataset.machine = host.id;
  byId('assignee-machine').textContent = host.name;
  assigneeError.hidden = true;
  byId('assignee-mode-field').hidden = !host.assignment_mode;
  assigneeMode.querySelector('[value=legacy]').hidden = host.assignment_mode !== 'legacy';
  assigneeMode.value = host.assignment_mode ?? 'person';
  renderAssigneeOptions(new Set(host.assigned_users?.map(person => person.id)));
  assigneeDialog.showModal();
}

assigneeClear.addEventListener('click', () => {
  for (const input of assigneeOptions.querySelectorAll('input:checked')) input.checked = false;
  updateAssigneeCount();
});
assigneeOptions.addEventListener('change', event => {
  if (!byId('assignee-mode-field').hidden && assigneeMode.value === 'person' && event.target.checked) {
    for (const input of assigneeOptions.querySelectorAll('input:checked')) if (input !== event.target) input.checked = false;
  }
  updateAssigneeCount();
});
assigneeCancel.addEventListener('click', () => assigneeDialog.close());
assigneeManage.addEventListener('click', openPeopleDialog);
assigneeDialog.addEventListener('cancel', event => {
  if (assigneeSave.disabled) event.preventDefault();
});
assigneeDialog.addEventListener('close', () => {
  if (machineDialog.open) updateMachineConfiguration(configurationTarget());
  renderPage();
  paint();
});
assigneeForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (assigneeSave.disabled) return;
  const id = assigneeForm.dataset.machine;
  const typed = !byId('assignee-mode-field').hidden;
  const mode = typed ? assigneeMode.value : 'legacy';
  const personIds = ['unset','shared'].includes(mode) ? [] : [...selectedAssignees()];
  if (mode === 'person' && personIds.length !== 1) {
    showPeopleError(assigneeError,new Error(t('invalid_assignees')));
    return;
  }
  assigneeSave.disabled = assigneeCancel.disabled = assigneeOptions.disabled = assigneeClear.disabled = assigneeManage.disabled = true;
  setButtonLabel(assigneeSave, 'saving');
  assigneeError.hidden = true;
  try {
    const body = mode === 'legacy' ? {person_ids:personIds} : {person_ids:personIds,mode};
    const saved = await peopleRequest(resourcePath(configurationTarget())+'/assignees', 'PUT', body, 'invalid_assignees');
    snapshotRevision++;
    const records = getHost()?.storage_kind ? state.snapshot.storage : state.snapshot.machines;
    const host = machineForId(id,records);
    const values = {assigned_users:saved.assigned_users,assignment_mode:saved.assignment_mode};
    const source = sourceForId(host,id);
    if (source) Object.assign(source,values);
    if (host?.id === id) Object.assign(host,values);
    assigneeDialog.close();
  } catch (error) {
    showPeopleError(assigneeError, error);
  } finally {
    assigneeSave.disabled = assigneeCancel.disabled = assigneeOptions.disabled = assigneeClear.disabled = assigneeManage.disabled = false;
    setButtonLabel(assigneeSave, 'save');
  }
});

function renderPeopleList() {
  const query = byId('people-search').value.trim().toLocaleLowerCase();
  const people = directoryPeople().filter(person => person.name.toLocaleLowerCase().includes(query));
  byId('people-empty').hidden = people.length > 0;
  byId('people-empty').textContent = t(query ? 'no_matching_people' : 'no_people');
  peopleList.innerHTML = people.map(person =>
    `<li><span>${escape(person.name)}</span><div class="people-actions">
      <button type="button" class="control" data-rename-person="${person.id}" aria-label="${escape(t('rename_person_named',{name:person.name}))}">${t('rename_person')}</button>
      <button type="button" class="control danger-control" data-remove-person="${person.id}" aria-label="${escape(t('remove_person_named',{name:person.name}))}">${t('remove_person')}</button>
    </div></li>`).join('');
}

function editPerson(person = null) {
  editingPerson = person?.id ?? null;
  peopleName.value = person?.name ?? '';
  peopleCancelEdit.hidden = !person;
  setButtonLabel(peopleSave, person ? 'save' : 'add_person');
  peopleError.hidden = true;
}

function openPeopleDialog() {
  byId('people-search').value = '';
  editPerson();
  renderPeopleList();
  peopleDialog.showModal();
}

async function changePeople(person, {remove = false} = {}) {
  if (peopleClose.disabled) return;
  byId('people-edit-fields').disabled = peopleClose.disabled = true;
  for (const button of peopleList.querySelectorAll('button')) button.disabled = true;
  peopleError.hidden = true;
  setButtonLabel(peopleSave, 'saving');
  try {
    const path = person === null ? '/api/people' : '/api/people/'+person+
      (remove && groupedOverview() ? '?include_references=true' : '');
    const saved = await peopleRequest(path, remove ? 'DELETE' : person === null ? 'POST' : 'PUT',
      remove ? {} : {name:peopleName.value}, 'person_name_invalid');
    snapshotRevision++;
    const others = directoryPeople().filter(entry => entry.id !== person && entry.id !== saved?.id);
    state.snapshot.people = saved ? [...others, saved] : others;
    if (saved && person !== null) {
      for (const host of [...state.snapshot.machines,...(state.snapshot.storage ?? [])]) {
        for (const record of [host,...(host.sources ?? [])]) {
          record.assigned_users = (record.assigned_users ?? []).map(entry => entry.id === person ? saved : entry);
        }
      }
    }
    if (saved && person !== null && groupedOverview()) {
      for (const room of groupList('room')) if (room.owner_id === person) room.owner = saved.name;
      for (const cluster of groupList('cluster')) if (cluster.person_id === person) cluster.person = saved.name;
    }
    if (!remove || editingPerson === person) editPerson();
    renderPeopleList();
  } catch (error) {
    showPeopleError(peopleError, error);
    return;
  } finally {
    byId('people-edit-fields').disabled = peopleClose.disabled = false;
    for (const button of peopleList.querySelectorAll('button')) button.disabled = false;
    setButtonLabel(peopleSave, editingPerson === null ? 'add_person' : 'save');
  }
  peopleName.focus();
}

byId('people-search').addEventListener('input',renderPeopleList);
peopleList.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (button?.hasAttribute('data-rename-person')) {
    const person = directoryPeople().find(entry => entry.id === Number(button.dataset.renamePerson));
    if (person) {
      editPerson(person);
      peopleName.focus();
    }
  } else if (button?.hasAttribute('data-remove-person')) {
    void changePeople(Number(button.dataset.removePerson), {remove:true});
  }
});
peopleName.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.isComposing) {
    event.preventDefault();
    peopleForm.requestSubmit(peopleSave);
  }
});
peopleForm.addEventListener('submit', event => {
  event.preventDefault();
  void changePeople(editingPerson);
});
peopleCancelEdit.addEventListener('click', () => {
  editPerson();
  peopleName.focus();
});
peopleClose.addEventListener('click', () => peopleDialog.close());
peopleDialog.addEventListener('cancel', event => {
  if (peopleClose.disabled) event.preventDefault();
});
peopleDialog.addEventListener('close', () => {
  if (assigneeDialog.open) renderAssigneeOptions(selectedAssignees());
  renderPage();
  paint();
});

const removeDialog = byId('remove-dialog');
const removeForm = byId('remove-form');
const removeConfirm = byId('remove-confirm');
const removeCancel = byId('remove-cancel');
const removeError = byId('remove-error');

function openRemoveDialog(host) {
  removeForm.dataset.machine = host.id;
  const grouped = getHost()?.sources?.length > 1;
  setButtonLabel(byId('remove-title').querySelector('span'), grouped ? 'remove_source_title' : 'remove_node_m193');
  setButtonLabel(byId('remove-description').querySelector('span'), grouped ? 'remove_source_description' :
    'stops_monitoring_and_deletes_this_node_s_configuration_and_all_mo');
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
    const response = await fetch(resourcePath(configurationTarget()), {
      method:'DELETE', headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:true}),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? t('could_not_remove_please_retry_later')+' '+i18n.diagnostic(result.detail) : t('could_not_remove_please_retry_later'));
    snapshotRevision++;
    if (getHost()?.sources) {
      const other = getHost().sources.find(source => source.id !== id)?.id;
      removeDialog.close();
      machineDialog.close();
      await refreshWorkspace();
      openHost(other ?? null);
      return;
    }
    const list = getHost()?.storage_kind ? 'storage' : 'machines';
    state.snapshot[list] = state.snapshot[list].filter(node => node.id !== id);
    if (result.cleanup_pending) state.snapshot.removal_pending = Math.max(state.snapshot.removal_pending ?? 0,1);
    removeDialog.close();
    machineDialog.close();
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
  const {host,gpu,filter,metric,range,overviewMetric} = button.dataset;
  if (button.id === 'open-archive' || button.id === 'retry-archive') void openArchive();
  else if (button.id === 'exit-archive') exitArchive();
  else if (button.hasAttribute('data-alert-center')) openAlerts();
  else if (button.hasAttribute('data-more-alerts')) void loadAlerts(true);
  else if (button.dataset.event && state.page === 'alerts') {
    state.event = Number(button.dataset.event);
    updateWorkspaceURL('alerts',state.event);
    paintAlerts();
    byId('alert-rows')?.querySelector(`[data-event="${state.event}"]`)?.focus();
  }
  else if (button.dataset.event) openAlerts(Number(button.dataset.event));
  else if (button.hasAttribute('data-overview')) openHost(null);
  else if (button.hasAttribute('data-add-machine')) openMachineDialog(null);
  else if (button.hasAttribute('data-configure-machine')) openMachineDialog(sourceForId(getHost(),getHost()?.id) ?? getHost());
  else if (button.hasAttribute('data-configure-source')) openMachineDialog(sourceForId(getHost(),button.dataset.configureSource));
  else if (button.hasAttribute('data-edit-assignees') && !machineSave.disabled) openAssigneeDialog(configurationTarget());
  else if (button.hasAttribute('data-people-directory')) openPeopleDialog();
  else if (button.hasAttribute('data-remove-machine') && !machineSave.disabled) openRemoveDialog(configurationTarget());
  else if (button.hasAttribute('data-focus-trends')) setTrendFocus(true);
  else if (button.hasAttribute('data-exit-focus')) setTrendFocus(false);
  else if (button.hasAttribute('data-gpu-trends')) {
    const uuid = gpuDialog.dataset.gpu;
    gpuDialog.close();
    state.gpu = uuid;
    state.metric = 'gpu';
    renderPage(true);
    paint();
    void refreshHistory(true);
    byId('focus-trends')?.focus();
  }
  else if (host) openHost(host);
  else if (filter) {
    if (groupedOverview()) deviceFilterState().status = filter;
    else state.filter = filter;
    for (const node of document.querySelectorAll('[data-filter]')) node.setAttribute('aria-pressed',String(node.dataset.filter === filter));
    drawRows(membersForPanel(nodes()));
    paint();
  } else if (gpu) openGpuDialog(gpu);
  else if (button.hasAttribute('data-all-gpus')) {
    state.gpu = null;
    state.metric = 'cpu';
    renderPage(true);
    paint();
    void refreshHistory(true);
    byId('focus-trends')?.focus();
  } else if (overviewMetric) {
    if (groupChartContext()) state.groupMetric = overviewMetric;
    else state.overviewMetric = overviewMetric;
    if (chart) chart.metric = overviewMetric;
    for (const node of document.querySelectorAll('[data-overview-metric]'))
      node.setAttribute('aria-pressed',String(node.dataset.overviewMetric === overviewMetric));
    void refreshHistory(true);
  } else if (metric || range) {
    if (metric && state.focused) {
      const selected = state.focusMetrics.includes(metric);
      if (selected && state.focusMetrics.length === 1) return;
      state.focusMetrics = selected ? state.focusMetrics.filter(key => key !== metric) : [...state.focusMetrics,metric];
      renderPage(true);
    } else if (metric) {
      state.metric = metric;
      if (chart) chart.metric = metric;
    }
    if (range) state.hours = Number(range);
    for (const node of document.querySelectorAll('[data-metric]')) node.setAttribute('aria-pressed',String(state.focused ? state.focusMetrics.includes(node.dataset.metric) : node.dataset.metric === state.metric));
    for (const node of document.querySelectorAll('[data-range]')) node.setAttribute('aria-pressed',String(Number(node.dataset.range) === state.hours));
    void refreshHistory(true);
  }
});

document.addEventListener('change', event => {
  if (event.target.id !== 'trend-source') return;
  state.historySource = event.target.value || null;
  const host = getHost();
  if (!supported(host,getDevice(host)).includes(state.metric)) state.metric = 'memory';
  renderPage(true);
  paint();
  void refreshHistory(true);
  byId('trend-source')?.focus({preventScroll:true});
});
document.addEventListener('keydown',event => {
  if (event.key !== 'Escape' || document.querySelector('dialog[open]')) return;
  if (state.archive) {
    event.preventDefault();
    exitArchive();
  } else if (state.focused) {
    event.preventDefault();
    setTrendFocus(false);
  }
});
document.addEventListener('input',event => {
  if (event.target.id === 'archive-start') state.archive.start = event.target.value;
  if (event.target.id === 'archive-end') state.archive.end = event.target.value;
  if (event.target.id === 'alert-search') {
    state.alertQuery = event.target.value;
    state.event = null;
    paintAlerts();
  }
  if (event.target.id !== 'host-search') return;
  if (groupedOverview()) deviceFilterState().query = event.target.value;
  else state.query = event.target.value;
  drawRows(membersForPanel(nodes()));
  paint();
});

document.addEventListener('submit',event => {
  if (event.target.id !== 'archive-filters') return;
  event.preventDefault();
  const archive = state.archive;
  archive.start = byId('archive-start').value;
  archive.end = byId('archive-end').value;
  archive.metric = byId('archive-metric').value;
  void refreshArchiveChart(archive);
});

function paintSeries(ctx, points, layout, series) {
  const { bottom, left, right, top, x, y } = layout;
  const overview = !state.machine;
  ctx.save();
  ctx.beginPath();
  ctx.rect(left, top - 1, right - left, bottom - top + 2);
  ctx.clip();

  series.forEach((metric, index) => {
    if (metric.hidden) return;
    const segments = [];
    let segment = [];
    for (const point of points) {
      const value = point.values[index];
      const valid = Number.isFinite(value);
      const discontinuity = point.breaks?.[index];
      if (overview && !valid && discontinuity === false) continue;
      if (segment.length && (!valid || discontinuity)) {
        segments.push(segment);
        segment = [];
      }
      if (valid) segment.push([x(point.time), y(value)]);
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
      setSeriesStroke(ctx,metric);
      ctx.beginPath();
      ctx.moveTo(firstX, firstY);
      for (const [px, py] of part.slice(1)) ctx.lineTo(px, py);
      ctx.stroke();
    }
  });
  ctx.restore();
}

function chartReading(point,index,item,digits) {
  const value = fmt(point.values[index],item.unit,digits);
  const coverage = point.coverage?.[index];
  return coverage ? value+' · '+t('live_coverage',{valid:coverage[0],total:coverage[1]}) : value;
}

function paintTooltip(ctx, series, layout, width, chart) {
  const tip = byId('chart-tip'+chart.suffix);
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
    if (!Number.isFinite(value) || series[index].hidden) continue;
    ctx.fillStyle = series[index].color;
    ctx.beginPath();
    ctx.arc(position, y(value), 3.2, 0, 2 * Math.PI);
    ctx.fill();
  }
  tip.hidden = false;
  const timestamp = document.createElement('time');
  timestamp.textContent = tooltipTime.format(point.time);
  const readings = series.flatMap((metric,index) => {
    if (metric.hidden) return [];
    const reading = document.createElement('div');
    reading.textContent = metric.label+' · '+chartReading(point,index,metric,metric.key === 'vram' ? 1 : 0);
    return [reading];
  });
  tip.replaceChildren(timestamp,...readings);
  const preferred = position + tip.offsetWidth + 10 < width ? position + 9 : position - tip.offsetWidth - 9;
  tip.style.left = clamp(preferred, 2, Math.max(2, width - tip.offsetWidth - 2)) + 'px';
  tip.style.top = '13px';
}

function hardwareLabel(kind) {
  return {cpu:'CPU',gpu:'GPU',nas:'NAS',storage_cluster:t('storage_cluster'),unconfirmed:t('unconfirmed_hardware')}[kind] || '—';
}

function bytesLabel(bytes) {
  return Number.isFinite(bytes) && bytes >= 1024**4 ? fmt(bytes/1024**4,' TiB',1) : fmt(gib(bytes),' GiB',1);
}

function capacityLabel(capacity) {
  if (!capacity) return '—';
  const ratio = capacity.total_bytes ? fmt(100*capacity.used_bytes/capacity.total_bytes,'%') : '—';
  return bytesLabel(capacity.used_bytes)+' / '+bytesLabel(capacity.total_bytes)+' · '+ratio;
}

function basicTable(labels, rows) {
  if (!rows.length) return '<p class="empty">—</p>';
  return `<table class="resource-table"><thead><tr>${labels.map(label => `<th scope="col">${escape(label)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(row => '<tr>'+row.map((value,index) => `<td data-label="${escape(labels[index])}">${value}</td>`).join('')+'</tr>').join('')}</tbody></table>`;
}

function resourceActions() {
  const disabled = configUnavailable() ? 'disabled' : '';
  return `<div class="title-actions"><button type="button" class="control" data-configure-machine ${disabled}>${t('configure')}</button></div>`;
}

function storagePage(host) {
  const sample = host.storage_observation;
  const health = value => value ? t(`storage_${value}`) : '—';
  const pools = sample?.pools ?? [];
  const members = sample?.members ?? [];
  const cards = [
    [t('storage_capacity'),capacityLabel(sample?.capacity),sample?.scope === 'unverified' ? t('storage_unverified') : ''],
    [t('storage_health'),health(sample?.health),pools.length ? pools.filter(pool => pool.health === 'healthy').length+' / '+pools.length+' '+t('storage_pool') : ''],
    [t('storage_read')+' / '+t('storage_write'),[sample?.read_bytes_per_second,sample?.write_bytes_per_second]
      .map(value => fmt(Number.isFinite(value) ? value/1024**2 : null,' MiB/s',1)).join(' / '),''],
    [t('storage_adapter'),host.adapter ?? '—',sample?.identity ?? ''],
  ];
  return `<section class="page-title"><div>${heading(host.name,status(host.status,machineStates[host.status]))}
    <p>${hardwareLabel(host.storage_kind)} · ${t('last_valid_sample')} ${escape(time(host.last_success_at))}</p>${assigneeSummary(host)}${deviceGroupLinks(host)}</div>
    ${resourceActions()}</section>
    ${deviceAlerts(host)}
    ${host.status === 'pending' ? `<p class="message scope-note">${t('storage_registered')}</p>` : ''}
    <section class="metrics">${cards.map(([label,value,foot]) => `<article class="metric"><p class="metric-name">${label}</p><strong>${escape(value)}</strong><small>${escape(foot)}</small></article>`).join('')}</section>
    <div class="column details-layout">
    ${host.status === 'pending' && !host.last_success_at ? '' : chartPanel(host,null)}
    <section class="panel resource-panel"><h2>${t('storage_pool')}</h2>${basicTable([t('device_name'),t('storage_health'),t('storage_capacity')],
      pools.map(pool => [escape(pool.name),health(pool.health),capacityLabel(pool)]))}</section>
    ${host.storage_kind === 'storage_cluster' ? `<section class="panel resource-panel"><h2>${t('storage_members')}</h2>${basicTable(
      [t('device_name'),t('storage_health'),t('storage_capacity')],members.map(member => [escape(member.name+(member.role ? ' · '+member.role : '')),
        health(member.health),bytesLabel(member.capacity_bytes)]))}</section>` : ''}</div>`;
}

function eventTime(value, utc = false) {
  if (!Number.isFinite(value)) return '—';
  const local = i18n.date(value,{dateStyle:'short',timeStyle:'medium'});
  return utc ? local+' / '+new Date(value).toISOString() : local;
}

const alertName = event => t(`alert_rule_${event.rule}`);
const alertEvidence = value => ['storage_health','storage_timeout','storage_observation_unavailable','sample_stale',
  'collection_resumed','storage_health_confirmed','adapter_removed','removed','disabled'].includes(value)
  ? t(value) : i18n.diagnostic(value);

function eventButton(event, label, style = 'control') {
  return `<button type="button" class="${style}" data-event="${event.id}">${escape(label)}</button>`;
}

function deviceButton(id, label = t('locate_device')) {
  return machineForId(id)
    ? `<button type="button" class="control" data-host="${escape(id)}">${escape(label)}</button>` : '';
}

function overviewAlerts(alerts) {
  const events = alerts?.events ?? [];
  return `<section class="panel attention-panel"><div class="panel-head"><h2>${t('site_alerts')}</h2>
    <small>${t('alert_active')} · ${alerts == null ? '—' : i18n.number(alerts.total)}</small><button type="button" class="control" data-alert-center>${t('alerts_all')}</button></div>
    ${events.length ? `<div class="issues">${events.map(event => `<div class="issue resource-issue">
      <span class="issue-mark ${event.severity === 'critical' ? 'offline' : 'warning'}" aria-hidden="true">!</span>
      <span class="issue-copy"><strong>${escape(event.name)} · ${alertName(event)}</strong><small>${eventTime(event.first_at)}</small></span>
      ${eventButton(event,t('see_evidence'))}${deviceButton(event.resource)}</div>`).join('')}</div>`
      : `<p class="empty">${t(alerts ? 'no_machines_need_attention' : 'alerts_unavailable')}</p>`}</section>`;
}

function deviceAlerts(host) {
  const ids = new Set(host.sources?.map(source => source.id) ?? [host.id]);
  const alerts = (state.snapshot.alerts?.events ?? []).filter(event => ids.has(event.resource) && event.status === 'active');
  return alerts.length ? `<div class="message resource-issue">${alerts.map(event => eventButton(event,alertName(event))).join('')}</div>` : '';
}

function alertCenter() {
  return `<section class="page-title">${heading(t('alerts_center'))}</section>
    <div class="alert-columns"><section class="panel resource-panel" aria-label="${t('alerts_all')}">
      <div class="tools"><label>${t('status')} <select id="alert-status">${['all','active','resolved','closed'].map(key =>
        `<option value="${key}" ${key === state.alertFilter ? 'selected' : ''}>${t(key === 'all' ? 'all' : `alert_${key}`)}</option>`).join('')}</select></label>
      <label>${t('resource_kind')} <select id="alert-kind">${['all','cpu','gpu','nas','storage_cluster','unconfirmed'].map(key =>
        `<option value="${key}" ${key === state.alertKind ? 'selected' : ''}>${key === 'all' ? t('all') : hardwareLabel(key)}</option>`).join('')}</select></label>
      <input type="search" class="search" id="alert-search" aria-label="${t('alert_filter')}" placeholder="${t('alert_filter')}" value="${escape(state.alertQuery)}"></div>
      <div id="alert-rows"></div></section><section class="panel resource-panel" id="alert-detail" aria-label="${t('alert_evidence')}"></section></div>`;
}

function paintAlerts() {
  const rows = byId('alert-rows');
  const detail = byId('alert-detail');
  if (!rows || !detail) return;
  const query = state.alertQuery.trim().toLocaleLowerCase();
  const focus = document.activeElement?.closest('#alert-rows button, #alert-detail button');
  const focusedEvent = focus?.dataset.event;
  const focusedDevice = focus?.dataset.host;
  const events = state.alerts?.events ?? [];
  const matches = events.filter(event => (state.alertFilter === 'all' || state.alertFilter === event.status)
    && (state.alertKind === 'all' || state.alertKind === event.kind)
    && (event.name+' '+alertName(event)+' '+event.id).toLocaleLowerCase().includes(query));
  rows.innerHTML = matches.length ? basicTable([t('status'),t('alert_evidence'),t('alert_first_at'),t('alert_recovered_at')],
    matches.map(event => [t(`alert_${event.status}`),eventButton(event,event.name+' · '+alertName(event),'row-open'),
      eventTime(event.first_at),eventTime(event.recovered_at)]))
    : `<p class="empty" role="status">${t(state.alertError ? 'alerts_unavailable' : state.alerts ? 'alert_no_matches' : 'loading_historical_samples')}</p>`;
  if (events.length < (state.alerts?.total ?? 0)) rows.insertAdjacentHTML('beforeend',
    `<button type="button" class="control" data-more-alerts>${t('alert_load_more')}</button>`);
  const selected = matches.find(event => event.id === state.event) ||
    (state.directAlert?.id === state.event ? state.directAlert : null) || matches[0];
  const device = selected && nodes().find(node => node.id === selected.resource);
  detail.innerHTML = selected ? `<h2>${escape(selected.name)} · ${alertName(selected)}</h2>
    <p>${t(`alert_${selected.status}`)} · #${selected.id}</p><dl class="event-facts">
    ${[['alert_first_at','first_at'],['alert_last_at','last_at'],['alert_recovered_at','recovered_at'],
      ['alert_closed_at','closed_at'],['last_valid_sample','last_success_at']].map(([label,key]) =>
      `<dt>${t(label)}</dt><dd>${escape(eventTime(selected[key],true))}</dd>`).join('')}</dl>
    <p class="message">${escape(alertEvidence(selected.evidence) || '—')}</p>
    ${selected.recovery_evidence ? `<p>${escape(alertEvidence(selected.recovery_evidence))}</p>` : ''}
    ${selected.closure_reason ? `<p>${escape(alertEvidence(selected.closure_reason))}</p>` : ''}
    ${device ? deviceGroupLinks(device) : ''}
    ${deviceButton(selected.resource)}` : '<p class="empty">—</p>';
  if (focusedEvent) rows.querySelector(`[data-event="${CSS.escape(focusedEvent)}"]`)?.focus({preventScroll:true});
  else if (focusedDevice) detail.querySelector(`[data-host="${CSS.escape(focusedDevice)}"]`)?.focus({preventScroll:true});
}

async function loadAlerts(more = false) {
  if (state.alertLoading) return;
  state.alertLoading = true;
  state.alertRefreshAt = performance.now();
  try {
    const next = await get('/api/alerts?offset='+(more ? state.alerts.events.length : 0));
    const entries = more ? [...state.alerts.events,...next.events] : next.events;
    state.alerts = {total:next.total,events:[...new Map(entries.map(event => [event.id,event])).values()]};
    const selected = state.event;
    if (Number.isSafeInteger(selected) && selected > 0 && !entries.some(event => event.id === selected)) {
      const direct = await get('/api/alerts/'+selected).catch(() => null);
      if (state.event === selected) state.directAlert = direct;
    } else state.directAlert = null;
    state.alertError = false;
  } catch {
    state.alertError = true;
  } finally {
    state.alertLoading = false;
    paintAlerts();
  }
}

function openAlerts(id = null, remember = true) {
  if (remember && !state.page && !state.machine) state.overviewScroll = window.scrollY;
  if (remember) updateWorkspaceURL('alerts',id);
  state.page = 'alerts';
  state.group = null;
  state.trail = [];
  state.event = id;
  state.directAlert = null;
  if (id !== null) {
    state.alertFilter = state.alertKind = 'all';
    state.alertQuery = '';
  }
  state.machine = state.gpu = null;
  state.focused = false;
  renderPage(true);
  void loadAlerts();
  void refreshHistory(true);
  window.scrollTo(0,0);
  byId('page-heading')?.focus();
}

document.addEventListener('change', event => {
  if (event.target.id === 'archive-metric') state.archive.metric = event.target.value;
  if (event.target.id === 'alert-status') state.alertFilter = event.target.value;
  else if (event.target.id === 'alert-kind') state.alertKind = event.target.value;
  else return;
  state.event = null;
  paintAlerts();
});

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
  updateRail();
  orderMessage = '';
  renderPage(true);
  paint();
});

setupGroupUI();
void refresh();
