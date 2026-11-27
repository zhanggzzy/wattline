'use strict';

const groupMetrics = ['cpu','memory_used','memory','gpu','power','storage'];
const overviewTabs = ['room','cluster','machine'];
const managementTabs = ['room','cluster','people'];
const groupLabel = kind => t({room:'rooms',cluster:'clusters',machine:'machines',people:'people_directory'}[kind]);
const groupedOverview = () => Boolean(state.snapshot?.groups);
const groupList = kind => state.snapshot?.groups?.[kind === 'room' ? 'rooms' : 'clusters'] ?? [];
const groupRecord = (kind,id) => groupList(kind).find(group => group.id === id);
const detailGroup = () => state.group && groupRecord(state.group.kind,state.group.id);
const roomName = id => groupRecord('room',id)?.name || t('no_room');
const groupPerson = (group,kind) => kind === 'room' ? group.owner : group.shared ? t('shared_user') : group.person;
const groupCounts = () => state.snapshot?.alerts?.by_resource ?? {};
const activeGroupAlerts = group => {
  const counts = groupCounts();
  const hosts = nodes();
  return group.members.flatMap(id => machineForId(id,hosts)?.sources?.map(source => source.id) ?? [id])
    .reduce((count,id) => count+(counts[id] ?? 0),0);
};

const configurationValue = value => i18n.number(value, {maximumSignificantDigits:17}) + ' MiB';

function effectiveConfiguration(policy) {
  if (!policy?.source) return t('configuration_member_specific');
  const {scope, ids} = policy.source;
  const label = t({machine:'configuration_source_machine', cluster:'configuration_source_cluster',
    room:'configuration_source_room', global:'configuration_source_global', default:'configuration_source_default'}[scope]);
  const names = ['room','cluster'].includes(scope) ? ids.map(id => groupRecord(scope,id)?.name ?? id) : [];
  const source = names.length ? label + ' · ' + new Intl.ListFormat(i18n.locale).format(names) : label;
  return t('configuration_effective', {value:configurationValue(policy.effective),source});
}

function configurationSummary(policy) {
  if (!policy) return '';
  return t(policy.override == null ? 'configuration_inherited' : 'configuration_overridden')
    + ' · ' + effectiveConfiguration(policy);
}

function initializeTolerance(field, policy) {
  field.value = field.defaultValue = policy?.override ?? '';
}

function includeToleranceChange(body, field) {
  if (!field.disabled && field.value !== field.defaultValue) {
    body[field.name] = field.value === '' ? null : field.valueAsNumber;
  }
}

function globalConfigurationButton() {
  return `<button type="button" class="control" data-global-configuration ${configUnavailable() ? 'disabled' : ''}>${t('global_configuration')}</button>`;
}

function openGlobalConfiguration() {
  const form = byId('global-configuration-form');
  const policy = state.snapshot.idle_memory_configuration;
  initializeTolerance(form.elements.idle_memory_tolerance_mib, policy);
  byId('global-configuration-summary').textContent = configurationSummary(policy);
  byId('global-configuration-error').hidden = true;
  byId('global-configuration-dialog').showModal();
}

async function saveGlobalConfiguration(event) {
  event.preventDefault();
  const field = event.currentTarget.elements.idle_memory_tolerance_mib;
  const dialog = byId('global-configuration-dialog');
  const save = byId('global-configuration-save');
  const cancel = byId('global-configuration-cancel');
  const error = byId('global-configuration-error');
  if (save.disabled) return;
  const body = {[field.name]:field.value === '' ? null : field.valueAsNumber};
  save.disabled = cancel.disabled = field.disabled = true;
  setButtonLabel(save, 'saving');
  error.hidden = true;
  try {
    const response = await fetch('/api/configuration', {method:'PUT', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)});
    if (!response.ok) throw new Error(t('configuration_save_failed'));
    state.snapshot.idle_memory_configuration = await response.json();
    dialog.close();
    await refreshWorkspace();
  } catch {
    error.textContent = t('configuration_save_failed');
    error.hidden = false;
  } finally {
    save.disabled = cancel.disabled = field.disabled = false;
    setButtonLabel(save, 'save');
  }
}

function tabs(keys,selected,area) {
  return `<div class="workspace-tabs" role="tablist" aria-label="${t(area === 'overview' ? 'overview_granularity' : 'group_management')}">
    ${keys.map(kind => `<button type="button" role="tab" id="${area}-tab-${kind}" aria-controls="${area}-tab-panel"
      aria-selected="${selected === kind}" tabindex="${selected === kind ? '0' : '-1'}"
      data-workspace-tab="${kind}" data-tab-area="${area}">${groupLabel(kind)}</button>`).join('')}</div>`;
}

function roomOptions(selected, all = false) {
  return `<option value="">${t(all ? 'all' : 'no_room')}</option>`+
    (all ? `<option value="unassigned" ${selected === 'unassigned' ? 'selected' : ''}>${t('no_room')}</option>` : '')+
    groupList('room').map(room => `<option value="${escape(room.id)}" ${selected === room.id ? 'selected' : ''}>${escape(room.name)}</option>`).join('');
}

function userFilterOptions(selected, shared) {
  return `<option value="">${t('all')}</option><option value="unset" ${selected === 'unset' ? 'selected' : ''}>${t('unassigned')}</option>`+
    (shared ? `<option value="shared" ${selected === 'shared' ? 'selected' : ''}>${t('shared_user')}</option>` : '')+
    directoryPeople().map(person => `<option value="${person.id}" ${String(person.id) === selected ? 'selected' : ''}>${escape(person.name)}</option>`).join('');
}

function selectFilter(id, label, options) {
  return `<label class="workspace-filter"><span>${label}</span><select id="${id}">${options}</select></label>`;
}

function groupButton(kind,id,label,style = 'row-open') {
  return `<button type="button" class="${style}" data-group-kind="${kind}" data-group-id="${escape(id)}">${escape(label)}</button>`;
}

function deviceGroupLinks(node) {
  if (!groupedOverview()) return '';
  const clusterLinks = (node.cluster_ids ?? []).flatMap(id => {
    const group = groupRecord('cluster',id);
    return group ? [groupButton('cluster',id,group.name,'crumb-button')] : [];
  });
  return `<p class="device-group-links">${node.room_id ? groupButton('room',node.room_id,roomName(node.room_id),'crumb-button') : escape(t('no_room'))}
    <span aria-hidden="true"> · </span>${clusterLinks.length ? clusterLinks.join(' ') : escape(t('no_cluster'))}</p>`;
}

function groupRows(kind) {
  const filter = state.groupFilters[kind];
  return groupList(kind).filter(group => {
    const person = kind === 'room' ? group.owner_id : group.person_id;
    const query = filter.query.trim().toLocaleLowerCase();
    return (group.name+' '+(group.location ?? '')).toLocaleLowerCase().includes(query)
      && (!filter.person || (filter.person === 'shared' ? group.shared
        : filter.person === 'unset' ? !group.shared && !person : String(person) === filter.person))
      && (!filter.status || (filter.status === 'warning' ? activeGroupAlerts(group) > 0
        : filter.status === 'normal' ? group.summary.online > 0 && activeGroupAlerts(group) === 0 : group.summary.online === 0));
  });
}

function groupChartContext() {
  if (!groupedOverview() || state.machine || state.page === 'alerts' || state.page === 'manage') return null;
  if (state.page === 'group') return {kind:state.group.kind,groups:[detailGroup()].filter(Boolean)};
  if (state.tab === 'machine') return null;
  const matches = groupRows(state.tab);
  return {kind:state.tab,groups:matches.slice(0,6),total:matches.length};
}

function summaryReading(value,suffix) {
  return fmt(value.value,suffix) + (value.total ? ` · ${value.valid}/${value.total}` : '');
}

function memoryReading(value) {
  const pair = value.total_bytes != null ? capacityLabel(value)+` · ${value.valid}/${value.total}` : '—';
  const unbounded = value.unbounded_used_bytes != null ? bytesLabel(value.unbounded_used_bytes)+' · '+t('unbounded_memory') : '';
  return unbounded ? (pair === '—' ? unbounded : pair+' · '+unbounded) : pair;
}

function summaryCell(group,kind,metric,scope = '') {
  return `<span data-group-reading="${metric}" data-reading-id="${escape(group.id)}" data-reading-kind="${kind}" data-reading-scope="${scope}">—</span>`;
}

function paintGroups() {
  const rows = [];
  for (const kind of ['room','cluster']) {
    const lookup = new Map(groupList(kind).map(group => [group.id,group]));
    for (const node of document.querySelectorAll(`[data-reading-kind="${kind}"]`)) rows.push([node,lookup.get(node.dataset.readingId)]);
  }
  for (const [node,group] of rows) {
    if (!group) continue;
    const summary = group.summary;
    const scope = summary[node.dataset.readingScope] ??
      (node.dataset.readingScope === 'machine' ? summary.host : null);
    let text = '—';
    switch (node.dataset.groupReading) {
      case 'online': text = summary.online+' / '+summary.registered; break;
      case 'cpu': text = summaryReading(scope.cpu,'%'); break;
      case 'memory': text = memoryReading(scope.memory); break;
      case 'gpu': text = summaryReading(scope.gpu,'%')+' / '+summaryReading(scope.power,' W'); break;
      case 'storage': text = summary.storage.total_bytes != null ? capacityLabel(summary.storage)+` · ${summary.storage.valid}/${summary.storage.total}` : '—'; break;
      case 'alerts': text = i18n.number(activeGroupAlerts(group)); break;
    }
    node.textContent = text;
  }
}

function summaryTable(kind,groups) {
  const clusters = kind === 'cluster';
  const labels = [groupLabel(kind),t(clusters ? 'resource_user_mode' : 'room_owner')];
  if (clusters) labels.push(t('rooms'));
  labels.push(t('online_registered'),t('cpu'),t('memory'),
    t('gpu_utilization')+' / '+t('gpu_power'),t('storage_resource'),t('site_alerts'));
  return basicTable(labels,groups.map(group => {
    const row = [groupButton(kind,group.id,group.name),escape(groupPerson(group,kind) || t('unassigned'))];
    if (clusters) row.push(i18n.number(group.rooms.filter(room => room.id).length));
    return [...row,summaryCell(group,kind,'online'),summaryCell(group,kind,'cpu','machine'),summaryCell(group,kind,'memory','machine'),
      summaryCell(group,kind,'gpu','machine'),
      summaryCell(group,kind,'storage'),summaryCell(group,kind,'alerts')];
  }));
}

function groupFilters(kind) {
  const filter = state.groupFilters[kind];
  return `<div class="tools">
    <input type="search" class="search" id="group-search" aria-label="${t('group_search')}" placeholder="${t('group_search')}" value="${escape(filter.query)}">
    ${selectFilter('group-person',t(kind === 'room' ? 'room_owner' : 'resource_user_mode'),userFilterOptions(filter.person,kind === 'cluster'))}
    ${selectFilter('group-status',t('status'),[['',t('all')],['normal',t('healthy')],['warning',t('needs_attention')],['unavailable',t('unavailable')]]
      .map(([key,label]) => `<option value="${key}" ${key === filter.status ? 'selected' : ''}>${label}</option>`).join(''))}
    ${filter.query || filter.person || filter.status ? `<button class="control" type="button" data-clear-groups>${t('clear_filters')}</button>` : ''}
  </div>`;
}

function groupOverviewPanel() {
  const kind = state.tab;
  const groups = kind === 'machine' ? [] : groupRows(kind);
  return tabs(overviewTabs,kind,'overview')+`<section id="overview-tab-panel" role="tabpanel" aria-labelledby="overview-tab-${kind}">
    ${kind === 'machine' ? machinePanel() : `${chartPanel(null,null)}
      <section class="panel resource-panel group-summary"><h2>${groupLabel(kind)}</h2>${groupFilters(kind)}
      ${groups.length ? summaryTable(kind,groups) : `<p class="empty">${t(groupList(kind).length ? 'group_no_matches' : 'group_empty')}</p>`}</section>`}
  </section>`;
}

function workspaceOverview() {
  const disabled = configUnavailable() ? 'disabled' : '';
  return `<section class="page-title"><div>${heading(t('resource_overview'))}</div><div class="title-actions">
    ${globalConfigurationButton()}
    <button type="button" class="control" data-workspace-manage ${disabled}>${t('group_management')}</button>
    <button type="button" class="control primary-control" data-add-machine ${disabled}>${t('add_resource')}</button></div></section>
    ${overviewCards()}<div class="overview-stack">${overviewAlerts(state.snapshot.alerts)}${groupOverviewPanel()}</div>`;
}

function groupDetailPage(group,kind) {
  const room = kind === 'room';
  const links = room ? groupList('cluster').flatMap(cluster => {
    const count = cluster.members.filter(id => group.members.includes(id)).length;
    return count ? [[groupButton('cluster',cluster.id,cluster.name),`${count} / ${cluster.members.length} · ${cluster.rooms.filter(item => item.id).length} ${t('rooms')}`]] : [];
  }) : group.rooms.map(item => [
    item.id ? groupButton('room',item.id,roomName(item.id)) : escape(t('no_room')),i18n.number(item.count),
  ]);
  const cards = [[t('online_registered'),'online',''],[t('cpu'),'cpu','machine'],[t('memory'),'memory','machine'],[t('storage_resource'),'storage','']];
  return `<section class="page-title"><div>${heading(group.name)}
    <p>${groupLabel(kind)} · ${t(room ? 'room_owner' : 'resource_user_mode')} · ${escape(groupPerson(group,kind) || t('unassigned'))}
      ${group.location ? ' · '+escape(group.location) : ''}</p></div>
    <div class="title-actions"><button type="button" class="control" data-edit-group="${kind}" data-edit-id="${escape(group.id)}" ${configUnavailable() ? 'disabled' : ''}>${t('configure')}</button>
    ${room ? `<button type="button" class="control primary-control" data-add-machine>${t('add_resource')}</button>` : ''}</div></section>
    <section class="metrics">${cards.map(([label,key,scope]) => `<article class="metric"><p class="metric-name">${label}</p>
      <strong>${summaryCell(group,kind,key,scope)}</strong></article>`).join('')}</section>
    <div class="column details-layout">
    <section class="panel resource-panel"><h2>${t(room ? 'related_clusters' : 'related_rooms')}</h2>
      ${basicTable([groupLabel(room ? 'cluster' : 'room'),t('group_members')],links)}</section>
    ${chartPanel(null,null)}${machinePanel(true)}</div>`;
}

function managementPage() {
  const kind = state.manageTab;
  const groups = kind === 'people' ? [] : groupList(kind);
  return `<section class="page-title">${heading(t('group_management'))}</section>${tabs(managementTabs,kind,'manage')}
    <section class="panel resource-panel" id="manage-tab-panel" role="tabpanel" aria-labelledby="manage-tab-${kind}">
    ${kind === 'people' ? `<div class="panel-head"><h2>${t('people_directory')}</h2>
      <button type="button" class="control" data-people-directory>${t('configure')}</button></div>
      ${basicTable([t('person_name')],directoryPeople().map(person => [escape(person.name)]))}`
      : `<div class="panel-head"><h2>${groupLabel(kind)}</h2>
      <button type="button" class="control primary-control" data-edit-group="${kind}">${t(kind === 'room' ? 'add_room' : 'add_cluster')}</button></div>
      ${basicTable([groupLabel(kind),t(kind === 'room' ? 'room_owner' : 'resource_user_mode'),t('group_members'),t('configure')],
        groups.map(group => [groupButton(kind,group.id,group.name),escape(groupPerson(group,kind) || t('unassigned')),
          i18n.number(group.members.length),`<span class="title-actions">
          <button type="button" class="control" data-edit-group="${kind}" data-edit-id="${escape(group.id)}">${t('configure')}</button>
          <button type="button" class="control danger-control" data-delete-group="${kind}" data-edit-id="${escape(group.id)}">${t('remove_group')}</button>
          </span>`]))}`}</section>`;
}

function groupBreadcrumb() {
  if (!state.group && !state.trail.length && state.page !== 'manage') return null;
  const link = `<button type="button" data-overview class="crumb-button">${t('overview')}</button>`;
  if (state.page === 'manage') return link+`<span aria-hidden="true">›</span><strong>${t('group_management')}</strong>`;
  const trail = state.trail.flatMap(item => {
    const group = groupRecord(item.kind,item.id);
    return group ? [`<span aria-hidden="true">›</span>${groupButton(item.kind,item.id,group.name,'crumb-button')}`] : [];
  }).join('');
  const title = getHost()?.name || detailGroup()?.name || t('overview');
  return link+trail+`<span aria-hidden="true">›</span><strong>${escape(title)}</strong>`;
}

function setGroupPage(kind,id,remember = true) {
  if (!groupRecord(kind,id)) return;
  if (remember && !state.page && !state.machine) state.overviewScroll = window.scrollY;
  const previous = state.group;
  const previousIndex = state.trail.findIndex(item => item.kind === kind && item.id === id);
  if (previousIndex >= 0) state.trail = state.trail.slice(0,previousIndex);
  else if (previous && previous.id !== id) state.trail = [...state.trail,previous].slice(-2);
  state.group = {kind,id};
  state.page = 'group';
  state.machine = state.gpu = null;
  state.focused = false;
  state.detailFilters = {query:'',kind:'',room:'',user:'',status:'all'};
  if (remember) updateWorkspaceURL(kind,id);
  renderPage(true);
  paint();
  void refreshHistory(true);
  window.scrollTo(0,0);
  byId('page-heading')?.focus({preventScroll:true});
}

function openManagement(remember = true) {
  if (remember && !state.page && !state.machine) state.overviewScroll = window.scrollY;
  state.page = 'manage';
  state.machine = state.gpu = state.group = null;
  state.trail = [];
  state.focused = false;
  if (remember) updateWorkspaceURL('manage');
  renderPage(true);
  window.scrollTo(0,0);
  byId('page-heading')?.focus();
}

function updateWorkspaceURL(kind, id) {
  if (!groupedOverview()) return;
  const hash = '#'+kind+(id == null ? '' : '/'+encodeURIComponent(id));
  if (location.hash !== hash) window.history.pushState(null,'',hash);
}

function restoreWorkspaceURL() {
  if (!groupedOverview()) return;
  const [kind,part] = location.hash.slice(1).split('/');
  let id;
  try { id = part ? decodeURIComponent(part) : null; } catch { return; }
  if (kind === 'device' && machineForId(id)) openHost(id,false);
  else if ((kind === 'room' || kind === 'cluster') && groupRecord(kind,id)) setGroupPage(kind,id,false);
  else if (kind === 'alerts') openAlerts(id ? Number(id) : null,false);
  else if (kind === 'manage') openManagement(false);
  else if (!kind || kind === 'overview') openHost(null,false);
}

function deviceFilterState() {
  return state.page === 'group' ? state.detailFilters : state.deviceFilters;
}

function deviceFilters() {
  const values = deviceFilterState();
  return `<div class="tools workspace-device-filters">
    ${selectFilter('device-kind',t('resource_kind'),['','gpu','cpu','storage','unconfirmed'].map(kind =>
      `<option value="${kind}" ${values.kind === kind ? 'selected' : ''}>${kind === '' ? t('all') : kind === 'storage' ? t('storage_resource') : hardwareLabel(kind)}</option>`).join(''))}
    ${selectFilter('device-room',t('rooms'),roomOptions(values.room,true))}
    ${selectFilter('device-user',t('resource_user_mode'),userFilterOptions(values.user,true))}
    ${values.kind || values.room || values.user || values.query || values.status !== 'all' ? `<button class="control" type="button" data-clear-devices>${t('clear_filters')}</button>` : ''}</div>`;
}

function passesDeviceFilters(node) {
  if (!groupedOverview()) return true;
  const values = deviceFilterState();
  return (!values.kind || (values.kind === 'storage' ? node.storage_kind : node.hardware_kind === values.kind))
    && (!values.room || (values.room === 'unassigned' ? !node.room_id : node.room_id === values.room))
    && (!values.user || (['shared','unset'].includes(values.user) ? node.assignment_mode === values.user
      : node.assigned_users?.some(person => String(person.id) === values.user)));
}

function membersForPanel(hosts) {
  const group = detailGroup();
  if (!group) return hosts;
  const ids = new Set(group.members);
  return hosts.filter(node => ids.has(node.id));
}

async function refreshWorkspace() {
  snapshotRevision++;
  const revision = snapshotRevision;
  const snapshot = await get('/api/snapshot');
  if (revision === snapshotRevision) {
    state.snapshot = snapshot;
    state.received = performance.now();
  }
  renderPage(true);
  paint();
  void refreshHistory(true);
}

function openGroupDialog(kind, id, remove = false) {
  const group = groupRecord(kind,id);
  const dialog = byId('group-dialog');
  const form = byId('group-form');
  const fields = form.elements;
  form.dataset.kind = kind;
  form.dataset.id = id || '';
  form.dataset.remove = String(remove);
  byId('group-dialog-title').textContent = remove ? t('remove_group') : t(id ? 'configure' : kind === 'room' ? 'add_room' : 'add_cluster');
  byId('group-fields').disabled = byId('group-fields').hidden = remove;
  byId('group-delete-preview').hidden = !remove;
  byId('group-remove').hidden = !id || remove;
  byId('group-error').hidden = true;
  fields.group_name.value = group?.name ?? '';
  fields.location.value = group?.location ?? '';
  fields.person.innerHTML = personOptions(kind === 'cluster');
  fields.person.value = String(kind === 'room' ? group?.owner_id ?? '' : group?.shared ? 'shared' : group?.person_id ?? '');
  byId('group-person-label').textContent = t(kind === 'room' ? 'room_owner' : 'resource_user_mode');
  byId('group-location-field').hidden = kind !== 'room';
  byId('group-members-field').hidden = kind !== 'cluster';
  fields.member_search.value = '';
  const members = new Set(group?.members ?? []);
  const devices = nodes();
  const policy = !remove && group?.idle_memory_configuration;
  fields.idle_memory_tolerance_mib.disabled = byId('group-configuration').hidden = !policy;
  initializeTolerance(fields.idle_memory_tolerance_mib, policy);
  byId('group-configuration-summary').textContent = configurationSummary(policy);
  byId('group-member-configuration').hidden = !policy;
  byId('group-member-values').innerHTML = policy ? devices
    .filter(node => members.has(node.id) && isLinuxGpu(node) && node.idle_memory_configuration)
    .map(node => `<li><strong>${escape(node.name)}</strong><span>${escape(effectiveConfiguration(node.idle_memory_configuration))}</span></li>`).join('') : '';
  byId('group-member-options').innerHTML = kind === 'cluster' ? devices.map(node =>
    `<label><input type="checkbox" value="${escape(node.id)}" ${members.has(node.id) ? 'checked' : ''}>
    <span>${escape(node.name)} · ${hardwareLabel(node.hardware_kind)} · ${escape(roomName(node.room_id))}</span></label>`).join('') : '';
  byId('group-delete-preview').innerHTML = remove ? `<p><strong>${escape(group.name)}</strong></p><p>${t('group_delete_unlinks')}</p>
    ${members.size ? `<ul>${devices.filter(node => members.has(node.id)).map(node => `<li>${escape(node.name)}</li>`).join('')}</ul>` : ''}` : '';
  setButtonLabel(byId('group-save'),remove ? 'confirm_removal' : 'save');
  dialog.showModal();
  (remove ? byId('group-cancel') : fields.group_name).focus();
}

async function saveGroupForm(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const {kind,id,remove} = form.dataset;
  const fields = form.elements;
  const save = byId('group-save');
  const error = byId('group-error');
  if (save.disabled) return;
  const isRemoving = remove === 'true';
  const person = fields.person.value;
  const personId = person && person !== 'shared' ? Number(person) : null;
  let body = {name:fields.group_name.value.trim()};
  if (isRemoving) body = {confirm:true};
  else if (kind === 'room') Object.assign(body,{owner_id:personId,location:fields.location.value.trim() || null});
  else Object.assign(body,{person_id:personId,shared:person === 'shared',
    members:[...byId('group-member-options').querySelectorAll('input:checked')].map(input => input.value)});
  if (!isRemoving) includeToleranceChange(body, fields.idle_memory_tolerance_mib);
  save.disabled = byId('group-cancel').disabled = true;
  error.hidden = true;
  try {
    const response = await fetch('/api/'+(kind === 'room' ? 'rooms' : 'clusters')+(id ? '/'+encodeURIComponent(id) : ''),
      {method:isRemoving ? 'DELETE' : id ? 'PUT' : 'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if (!response.ok) {
      const data = await response.json();
      throw new Error(t(typeof data.detail === 'string' ? data.detail : 'group_save_failed'));
    }
    byId('group-dialog').close();
    await refreshWorkspace();
    if (isRemoving && state.group?.id === id) openHost(null);
  } catch (failure) {
    error.textContent = failure instanceof TypeError ? t('group_save_failed') : failure.message;
    error.hidden = false;
  } finally {
    save.disabled = byId('group-cancel').disabled = false;
  }
}

function activateTab(area, tab) {
  if (area === 'overview') {
    if (tab === state.tab) return;
    state.tab = tab;
    state.hiddenGroups.clear();
  } else {
    if (tab === state.manageTab) return;
    state.manageTab = tab;
  }
  renderPage(true);
  paint();
  void refreshHistory(true);
  byId(`${area}-tab-${tab}`)?.focus({preventScroll:true});
}

function setupGroupUI() {
  const globalDialog = byId('global-configuration-dialog');
  byId('global-configuration-form').addEventListener('submit',saveGlobalConfiguration);
  byId('global-configuration-cancel').addEventListener('click', () => globalDialog.close());
  globalDialog.addEventListener('cancel',event => {
    if (byId('global-configuration-save').disabled) event.preventDefault();
  });
  byId('group-cancel').addEventListener('click', () => byId('group-dialog').close());
  byId('group-remove').addEventListener('click', () => {
    if (byId('group-save').disabled) return;
    const {kind,id} = byId('group-form').dataset;
    openGroupDialog(kind,id,true);
  });
  byId('group-dialog').addEventListener('cancel',event => {
    if (byId('group-save').disabled) event.preventDefault();
  });
  byId('group-form').addEventListener('submit',saveGroupForm);
  byId('group-form').elements.member_search.addEventListener('input',event => {
    const query = event.target.value.trim().toLocaleLowerCase();
    for (const label of byId('group-member-options').children) label.hidden = !label.textContent.toLocaleLowerCase().includes(query);
  });
  window.addEventListener('popstate',restoreWorkspaceURL);
  document.addEventListener('keydown',event => {
    const control = event.target.closest('[data-workspace-tab]');
    if (!control || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    const {workspaceTab,tabArea} = control.dataset;
    const options = tabArea === 'overview' ? overviewTabs : managementTabs;
    const index = options.indexOf(workspaceTab);
    const next = {ArrowLeft:(index+options.length-1)%options.length,ArrowRight:(index+1)%options.length,
      Home:0,End:options.length-1}[event.key];
    event.preventDefault();
    activateTab(tabArea,options[next]);
  });
  document.addEventListener('click',event => {
    const button = event.target.closest('button');
    if (!button) return;
    const {workspaceTab,tabArea,groupKind,groupId,editGroup,editId,deleteGroup} = button.dataset;
    if (workspaceTab) activateTab(tabArea,workspaceTab);
    else if (groupKind) setGroupPage(groupKind,groupId);
    else if (button.hasAttribute('data-workspace-manage')) openManagement();
    else if (button.hasAttribute('data-global-configuration')) openGlobalConfiguration();
    else if (editGroup || deleteGroup) openGroupDialog(editGroup || deleteGroup,editId,Boolean(deleteGroup));
    else if (button.hasAttribute('data-clear-groups')) {
      state.groupFilters[state.tab] = {query:'',person:'',status:''};
      refreshGroupFilter('group-search');
    } else if (button.hasAttribute('data-clear-devices')) {
      Object.assign(deviceFilterState(),{query:'',kind:'',room:'',user:'',status:'all'});
      renderPage(true);
      paint();
      byId('host-search')?.focus();
    }
  });
  document.addEventListener('input',event => {
    if (event.target.id !== 'group-search') return;
    state.groupFilters[state.tab].query = event.target.value;
    refreshGroupFilter('group-search');
  });
  document.addEventListener('change',event => {
    const {id,value} = event.target;
    if (id === 'group-person' || id === 'group-status') {
      state.groupFilters[state.tab][id.split('-')[1]] = value;
      refreshGroupFilter(id);
    } else if (['device-kind','device-room','device-user'].includes(id)) {
      deviceFilterState()[id.split('-')[1]] = value;
      drawRows(membersForPanel(nodes()));
      paint();
    }
  });
}

function refreshGroupFilter(focus) {
  const caret = focus === 'group-search' ? byId(focus)?.selectionStart : null;
  renderPage(true);
  paint();
  void refreshHistory(true);
  byId(focus)?.focus({preventScroll:true});
  if (caret != null) byId(focus)?.setSelectionRange(caret,caret);
}
