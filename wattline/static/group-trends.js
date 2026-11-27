'use strict';

const groupTrendContrast = matchMedia('(forced-colors: active)');
const groupTrendViews = new Map();
const groupTrendSelections = new Map();
const groupTrendLayoutKey = 'wattline.groupTrendLayout';
let groupTrendLayout = 'split';
try {
  if (localStorage.getItem(groupTrendLayoutKey) === 'overlay') groupTrendLayout = 'overlay';
} catch {}

groupTrendContrast.addEventListener('change', () => drawChart());

function groupTrendPlot(suffix, metric) {
  const layoutButton = (layout,label) => `<button type="button" id="trend-layout-${layout}${suffix}"
    data-group-layout="${layout}" aria-pressed="${groupTrendLayout === layout}">${t(label)}</button>`;
  return `<div class="group-trend-toolbar">
      <div class="seg" role="group" aria-label="${t('group_trend_view')}">
        ${layoutButton('split','group_trend_split')}${layoutButton('overlay','group_trend_overlay')}
      </div>
      <span id="group-trend-scale${suffix}"></span>
    </div>
    <div class="group-trend-ruler">
      <span id="group-trend-time${suffix}"></span>
      <button type="button" class="control" id="trend-clear${suffix}" data-group-clear aria-disabled="true">${t('group_trend_clear')}</button>
    </div>
    <div class="group-trend-surface" id="trend-chart${suffix}" role="group" tabindex="0"
      aria-label="${descriptors[metric][0]} · ${t('group_trend_ruler')}"
      aria-describedby="group-trend-help${suffix} chart-summary${suffix}">
      <canvas class="group-trend-overlay" data-group-plot aria-hidden="true" hidden></canvas>
      <div class="group-trend-rows"></div>
      <canvas class="group-trend-axis" aria-hidden="true"></canvas>
    </div>
    <p class="group-trend-help" id="group-trend-help${suffix}">${t('group_trend_help')}</p>
    <p class="group-trend-help"><span class="group-trend-hatch" aria-hidden="true"></span><span id="group-trend-gaps${suffix}"></span></p>`;
}

function groupTrendView(chart) {
  const key = state.tab + '/' + chart.metric;
  if (!groupTrendViews.has(key)) groupTrendViews.set(key,{time:null, highlight:null, tableOpen:false});
  return groupTrendViews.get(key);
}

function groupTrendSelection() {
  if (!groupTrendSelections.has(state.tab)) groupTrendSelections.set(state.tab,{isolated:null});
  return groupTrendSelections.get(state.tab);
}

function bindGroupTrend(chart, element, surface) {
  const data = byId('chart-data'+chart.suffix);
  const legend = byId('chart-legend'+chart.suffix);
  const groupTrend = chart.groupTrend = {
    element, surface, legend, data, rows:surface.querySelector('.group-trend-rows'),
    overlay:surface.querySelector('.group-trend-overlay'), axis:surface.querySelector('.group-trend-axis'),
    time:byId('group-trend-time'+chart.suffix), scale:byId('group-trend-scale'+chart.suffix),
    gaps:byId('group-trend-gaps'+chart.suffix),
    clear:element.querySelector('[data-group-clear]'), hoverTime:null, hoverGroup:null,
  };
  data.open = groupTrendView(chart).tableOpen;
  data.addEventListener('toggle',() => {
    groupTrendView(chart).tableOpen = data.open;
    drawChart(chart);
  });
  chart.observer = new ResizeObserver(() => paintGroupTrendPlots(chart));
  chart.observer.observe(surface);

  const setPointer = (event, commit) => {
    const canvas = event.target.closest('[data-group-plot]');
    if (!canvas || !chart.points.length) return;
    const {start,end,left,right} = groupTrendGeometry(chart,canvas.clientWidth);
    const position = event.clientX - canvas.getBoundingClientRect().left;
    const timestamp = start + clamp((position-left)/(right-left),0,1)*(end-start);
    const point = nearestGroupBucket(chart.points,timestamp);
    if (commit) {
      groupTrendView(chart).time = point.time;
      groupTrend.hoverTime = null;
      paintGroupTrendPlots(chart);
      announceGroupBucket(chart,point);
    } else {
      if (groupTrend.hoverTime === point.time) return;
      groupTrend.hoverTime = point.time;
      if (!groupTrend.hoverFrame) groupTrend.hoverFrame = requestAnimationFrame(() => {
        groupTrend.hoverFrame = null;
        paintGroupTrendPlots(chart);
      });
    }
  };
  surface.addEventListener('pointermove',event => {
    if (event.pointerType === 'mouse' && event.target.matches('[data-group-plot]')) setPointer(event,false);
    else if (groupTrend.hoverTime != null) {
      groupTrend.hoverTime = null;
      paintGroupTrendPlots(chart);
    }
  });
  surface.addEventListener('pointerleave',() => {
    groupTrend.hoverTime = null;
    paintGroupTrendPlots(chart);
  });
  surface.addEventListener('click',event => setPointer(event,true));

  element.addEventListener('keydown',event => {
    const view = groupTrendView(chart);
    if (event.key === 'Escape' && (view.time != null || groupTrend.hoverTime != null)) {
      event.preventDefault();
      event.stopPropagation();
      clearGroupBucket(chart);
      return;
    }
    if (event.target !== surface || !chart.points.length) return;
    const steps = {ArrowLeft:-1, ArrowRight:1, PageUp:-12, PageDown:12};
    if (!(event.key in steps) && !['Home','End'].includes(event.key)) return;
    event.preventDefault();
    const points = chart.points;
    const current = groupBucket(chart);
    const step = steps[event.key] * (event.shiftKey && event.key.startsWith('Arrow') ? 12 : 1);
    let index;
    if (event.key === 'Home' || event.key === 'End') {
      const valid = point => groupTrend.visible.some(({index}) => Number.isFinite(point.values[index]));
      index = event.key === 'Home' ? Math.max(0,points.findIndex(valid)) : points.findLastIndex(valid);
      if (index < 0) index = points.length-1;
    } else {
      index = points.indexOf(current);
      index = clamp((index < 0 ? points.length-1 : index)+step,0,points.length-1);
    }
    view.time = points[index].time;
    groupTrend.hoverTime = null;
    paintGroupTrendPlots(chart);
    announceGroupBucket(chart,points[index]);
  });

  element.addEventListener('click',event => {
    const button = event.target.closest('button');
    if (!button || button.getAttribute('aria-disabled') === 'true') return;
    const {groupLayout, groupClear, trendAction, legendGroup} = button.dataset;
    if (groupLayout) {
      groupTrendLayout = groupLayout;
      try { localStorage.setItem(groupTrendLayoutKey,groupLayout); } catch {}
    } else if (groupClear != null) {
      clearGroupBucket(chart);
      return;
    } else if (trendAction === 'visibility') {
      if (!state.hiddenGroups.delete(legendGroup)) state.hiddenGroups.add(legendGroup);
    } else if (trendAction === 'solo') {
      const selection = groupTrendSelection();
      selection.isolated = selection.isolated === legendGroup ? null : legendGroup;
    } else if (trendAction === 'highlight') {
      const view = groupTrendView(chart);
      view.highlight = view.highlight === legendGroup ? null : legendGroup;
      groupTrend.hoverGroup = null;
      groupTrend.focusGroup = null;
    } else return;
    drawChart();
  });
  const legendGroup = target => target?.closest('[data-trend-action="visibility"]')?.dataset.legendGroup;
  for (const [event, key] of [['pointerover','hoverGroup'],['pointerout','hoverGroup'],['focusin','focusGroup'],['focusout','focusGroup']]) {
    legend.addEventListener(event,change => {
      if (change.pointerType && change.pointerType !== 'mouse') return;
      const id = legendGroup(change.type.endsWith('out') ? change.relatedTarget : change.target);
      if (groupTrend[key] === id) return;
      groupTrend[key] = id;
      if (groupTrendLayout === 'overlay') paintGroupTrendPlots(chart);
    });
  }
}

function clearGroupBucket(chart) {
  groupTrendView(chart).time = chart.groupTrend.hoverTime = null;
  paintGroupTrendPlots(chart);
  announceGroupBucket(chart,null);
}

function nearestGroupBucket(points, timestamp) {
  if (timestamp == null || !points.length) return null;
  // The API returns a time-ordered, fixed-interval window.
  const step = points[1]?.time - points[0].time;
  const index = step > 0 ? clamp(Math.round((timestamp-points[0].time)/step),0,points.length-1) : 0;
  return points[index];
}

function groupBucket(chart) {
  const time = chart.groupTrend.hoverTime ?? groupTrendView(chart).time;
  return nearestGroupBucket(chart.points,time);
}

function announceGroupBucket(chart,point) {
  const trend = chart.groupTrend;
  const message = point ? [tooltipTime.format(point.time), ...trend.visible.map(({item,index}) =>
    item.label+' · '+chartReading(point,index,item,1))].join(' · ') : t('group_trend_ruler_cleared');
  clearTimeout(trend.announcement);
  trend.announcement = setTimeout(() => {
    if (trend.element.isConnected) byId('chart-announcement'+chart.suffix).textContent = message;
  },120);
}

function groupTrendStatistics(points, index, item) {
  let peak = null, sum = 0, count = 0;
  for (const point of points) {
    const value = point.values[index];
    if (!Number.isFinite(value)) continue;
    if (!peak || value > peak.values[index]) peak = point;
    sum += value;
    count++;
  }
  return {
    peak:peak ? t('group_trend_peak_time',{value:fmt(peak.values[index],item.unit,1),time:tooltipTime.format(peak.time)}) : t('group_trend_peak_unknown'),
    mean:t('group_trend_mean',{value:fmt(count ? sum/count : null,item.unit,1)}),
    missing:t('group_trend_missing',{count:i18n.number(points.length-count)}),
  };
}

function groupTrendLegend(chart, groups, note) {
  const {legend} = chart.groupTrend;
  const key = JSON.stringify([groups.map(({id,name,series}) => [id,name,series.map(({item}) => item.color)]),note]);
  if (key === chart.groupTrend.controlsKey) return;
  chart.groupTrend.controlsKey = key;
  const focusId = legend.contains(document.activeElement) ? document.activeElement.id : null;
  legend.innerHTML = groups.map(({id,name,series}) => {
    const swatches = series.map(({item}) => `<span class="group-trend-swatch" style="--series-color:${item.color}" aria-hidden="true"></span>`).join('');
    const button = (action, label, accessibleName = label, prefix = '') => `<button type="button" class="control"
      id="trend-${action}${chart.suffix}-${escape(id)}" data-trend-action="${action}" data-legend-group="${escape(id)}"
      aria-label="${escape(accessibleName)}" aria-pressed="false">${prefix}${escape(label)}</button>`;
    return `<div class="group-trend-legend" data-trend-group="${escape(id)}" role="group" aria-label="${escape(name)}">
      ${button('visibility',name,name,swatches)}${button('highlight',t('group_trend_highlight'),t('group_trend_highlight_group',{name}))}
      ${button('solo',t('group_trend_solo'),t('group_trend_solo_group',{name}))}
    </div>`;
  }).join('') + `<span class="chart-note">${note}</span>`;
  if (focusId) (byId(focusId) ?? chart.groupTrend.surface).focus({preventScroll:true});
}

function groupTrendRows(chart, groups) {
  const trend = chart.groupTrend;
  const key = JSON.stringify(groups.map(group => [group.id,group.name,group.series.map(({item,index}) =>
    [index,item.scopeName,item.color])]));
  if (key === trend.rowsKey) return;
  trend.rowsKey = key;
  trend.statisticsHistory = undefined;
  trend.rows.innerHTML = groups.map(group => `<section class="group-trend-row" data-trend-group="${escape(group.id)}">
    <h3>${escape(group.name)}</h3>
    <div class="group-trend-statistics">${group.series.map(({item,index}) => `<div class="group-trend-stat" data-series-index="${index}">
      <span class="scope"><span class="group-trend-swatch" style="--series-color:${item.color}" aria-hidden="true"></span>${escape(item.scopeName)}</span>
      <span class="stat-values"></span><output class="group-trend-reading" aria-live="off"></output>
    </div>`).join('')}</div>
    <canvas class="group-trend-lane" data-group-plot aria-hidden="true"></canvas>
  </section>`).join('');
}

function drawGroupTrend(chart) {
  const trend = chart.groupTrend;
  const context = groupChartContext();
  // The page can change during an outstanding resize or table update.
  if (!trend.element.isConnected || !(context?.total >= 2)) return;
  const history = chartHistory(chart.metric);
  const view = groupTrendView(chart);
  const selection = groupTrendSelection();
  const names = countLabels(groupList(context.kind).map(group => group.name.normalize('NFC')));
  const groups = context.groups.map(({id,name}) => ({
    id, name:names.get(name.normalize('NFC')) > 1 ? name+' · '+id : name, series:[],
  }));
  const byGroup = new Map(groups.map(group => [group.id,group]));
  if (!byGroup.has(selection.isolated)) selection.isolated = null;
  if (groups.every(group => state.hiddenGroups.has(group.id))) state.hiddenGroups.delete(groups[0].id);
  const series = chartSeries(chart,history).map((item,index) => {
    const group = byGroup.get(item.id);
    if (!group) return {...item,hidden:true};
    const scopeName = t({host:'host_scope_label',container:'container_scope',storage:'storage_resource'}[item.scope] || 'whole_machine');
    const scoped = ['host','container'].includes(item.scope) || history.series.filter(other => other.group === item.id).length > 1;
    const entry = {...item, scopeName, hidden:selection.isolated ? item.id !== selection.isolated : item.hidden,
      label:scoped ? group.name+' · '+scopeName : group.name};
    group.series.push({item:entry,index});
    return entry;
  });
  if (trend.history !== history) chart.points = chartPoints(history);
  trend.visible = groups.flatMap(group => group.series.filter(({item}) => !item.hidden));
  trend.series = series;
  trend.groups = groups;
  trend.history = history;
  const [,unit] = descriptors[chart.metric];
  trend.ceiling = chartCeiling(series.length ? series : [{key:chart.metric,unit}],chart.points);
  trend.view = groupTrendLayout;
  trend.overlay.hidden = trend.view !== 'overlay';
  trend.surface.dataset.view = trend.view;
  trend.surface.setAttribute('aria-label',descriptors[chart.metric][0]+' · '+t('group_trend_ruler'));
  for (const button of trend.element.querySelectorAll('[data-group-layout]')) {
    button.setAttribute('aria-pressed',String(button.dataset.groupLayout === trend.view));
  }
  trend.scale.textContent = t('group_trend_scale',{from:fmt(0,unit),to:fmt(trend.ceiling,unit)});
  if (trend.data.open !== view.tableOpen) trend.data.open = view.tableOpen;

  const members = context.groups.flatMap(group => group.members);
  const shared = new Set(members).size !== members.length;
  groupTrendLegend(chart,groups,[t('current_group_membership'),shared ? t('group_trend_shared_members') : ''].filter(Boolean).join(' · '));
  groupTrendRows(chart,groups);
  const visibleGroups = groups.filter(group => selection.isolated ? group.id === selection.isolated : !state.hiddenGroups.has(group.id));
  const visibleIds = new Set(visibleGroups.map(group => group.id));
  const error = state.historyErrors[chart.metric];
  byId('chart-error'+chart.suffix).hidden = !error;
  const summary = byId('chart-summary'+chart.suffix);
  const limit = context.total > groups.length
    ? t('group_trend_limit',{shown:i18n.number(groups.length),total:i18n.number(context.total)}) : '';
  const status = !history ? t(error ? 'could_not_load_history_retrying_automatically' : 'loading_historical_samples')
    : !chart.points.some(point => trend.visible.some(({index}) => Number.isFinite(point.values[index])))
      ? t('no_valid_samples_in_this_window') : '';
  summary.textContent = [t('group_trend_visible',{count:i18n.number(visibleGroups.length)}),limit,status].filter(Boolean).join(' · ');
  for (const group of groups) {
    const selector = `[data-trend-group="${CSS.escape(group.id)}"]`;
    const row = trend.rows.querySelector(selector);
    row.hidden = !visibleIds.has(group.id) || !group.series.length;
    row.querySelector('canvas').hidden = trend.view !== 'split';
    const buttons = trend.legend.querySelector(selector).children;
    const [visibility, highlight, solo] = buttons;
    const visible = visibleIds.has(group.id);
    const isolated = selection.isolated === group.id;
    visibility.setAttribute('aria-pressed',String(visible));
    visibility.setAttribute('aria-disabled',String(Boolean(selection.isolated) || visible && visibleGroups.length === 1));
    highlight.hidden = trend.view !== 'overlay';
    highlight.setAttribute('aria-pressed',String(view.highlight === group.id && visible));
    highlight.setAttribute('aria-disabled',String(!visible));
    solo.setAttribute('aria-pressed',String(isolated));
    solo.textContent = t(isolated ? 'group_trend_restore' : 'group_trend_solo');
    solo.setAttribute('aria-label',t(isolated ? 'group_trend_restore' : 'group_trend_solo_group',{name:group.name}));
    if (trend.statisticsHistory !== history) {
      for (const {item,index} of group.series) {
        const stats = groupTrendStatistics(chart.points,index,item);
        row.querySelector(`[data-series-index="${index}"] .stat-values`).textContent =
          [stats.peak,stats.mean,stats.missing].join(' · ');
      }
    }
  }
  trend.statisticsHistory = history;
  chart.legendKey = JSON.stringify([trend.visible,i18n.locale]);
  paintChartTable(trend.data,chart,history,trend.visible,chart.points);
  paintGroupTrendPlots(chart);
}

function groupTrendGeometry(chart, width, height = 0) {
  const {history} = chart.groupTrend;
  const end = history?.to ?? state.snapshot?.server_time ?? Date.now();
  const start = history?.from ?? end-86400000;
  const left = 48, right = width-12, top = 10, bottom = height-9;
  return {start,end,left,right,top,bottom,
    x:time => left+(time-start)/Math.max(1,end-start)*(right-left),
    y:value => bottom-value/chart.groupTrend.ceiling*(bottom-top)};
}

function groupTrendCanvas(canvas) {
  const width = canvas.clientWidth, height = canvas.clientHeight;
  if (width < 64 || height < 18) return null;
  const scale = devicePixelRatio || 1;
  if (canvas.width !== Math.round(width*scale) || canvas.height !== Math.round(height*scale)) {
    canvas.width = Math.round(width*scale);
    canvas.height = Math.round(height*scale);
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(scale,0,0,scale,0,0);
  ctx.clearRect(0,0,width,height);
  ctx.font = '10.5px system-ui, sans-serif';
  ctx.fillStyle = groupTrendContrast.matches ? 'CanvasText' : '#334f48';
  return {ctx,width,height};
}

function paintMissingBuckets(ctx, points, indices, layout, bucket) {
  if (!indices.length || !bucket) return;
  const {left,right,top,bottom,x} = layout;
  const bands = [];
  for (const point of points) {
    if (indices.some(index => Number.isFinite(point.values[index]))) continue;
    const prior = bands.at(-1);
    if (prior?.end === point.time-bucket) prior.end = point.time;
    else bands.push({start:point.time-bucket,end:point.time});
  }
  if (!bands.length) return;
  ctx.save();
  ctx.beginPath();
  for (const band of bands) {
    const start = clamp(x(band.start),left,right), end = clamp(x(band.end),left,right);
    ctx.rect(start,top,end-start,bottom-top);
  }
  ctx.clip();
  ctx.fillStyle = groupTrendContrast.matches ? 'Canvas' : '#edf1f6';
  ctx.fillRect(left,top,right-left,bottom-top);
  ctx.strokeStyle = groupTrendContrast.matches ? 'CanvasText' : '#aebcce';
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let px=left-(bottom-top);px<right;px+=6) {
    ctx.moveTo(px,bottom);
    ctx.lineTo(px+bottom-top,top);
  }
  ctx.stroke();
  ctx.restore();
}

function paintGroupTrendPlot(chart, canvas, entries, point, highlight) {
  const drawing = groupTrendCanvas(canvas);
  if (!drawing) return;
  const {ctx,width,height} = drawing;
  const layout = groupTrendGeometry(chart,width,height);
  const {left,right,top,bottom,x,y} = layout;
  const solid = groupTrendContrast.matches ? 'CanvasText' : undefined;
  const indices = entries.map(({index}) => index);
  const focused = highlight ? entries.filter(({item}) => item.id === highlight) : entries;
  paintMissingBuckets(ctx,chart.points,focused.map(({index}) => index),layout,chart.groupTrend.history?.bucket_ms);
  const [,unit] = descriptors[chart.metric];
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'right';
  for (const share of [1,.5,0]) {
    const value = chart.groupTrend.ceiling*share;
    ctx.fillText(fmt(value,unit === '%' ? unit : '',Number.isInteger(value) ? 0 : 1),left-6,y(value));
    ctx.strokeStyle = solid || '#e2e9e6';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(left,y(value));
    ctx.lineTo(right,y(value));
    ctx.stroke();
  }
  const plotted = [];
  for (const {item,index} of entries) plotted[index] = item;
  paintSeries(ctx,chart.points,layout,plotted,{highlight,solid,alignedGroup:true});
  if (!point) return;
  const position = x(point.time);
  ctx.strokeStyle = solid ? 'Highlight' : '#496781';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(position,top);
  ctx.lineTo(position,bottom);
  ctx.stroke();
  for (const index of indices) {
    const value = point.values[index];
    if (!Number.isFinite(value)) continue;
    const item = chart.groupTrend.series[index];
    ctx.fillStyle = solid || item.color;
    ctx.globalAlpha = highlight && item.id !== highlight ? .18 : 1;
    ctx.beginPath();
    ctx.arc(position,y(value),3,0,2*Math.PI);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function paintGroupTrendPlots(chart) {
  const trend = chart.groupTrend;
  if (!trend.groups || !trend.element.isConnected) return;
  const view = groupTrendView(chart);
  const point = groupBucket(chart);
  const time = point ? t('group_trend_at',{time:tooltipTime.format(point.time)}) : t('group_trend_no_cursor');
  if (trend.time.textContent !== time) trend.time.textContent = time;
  trend.clear.setAttribute('aria-disabled',String(!point));
  const highlight = trend.view === 'overlay' ? [trend.hoverGroup,trend.focusGroup,view.highlight].find(id =>
    id && trend.visible.some(({item}) => item.id === id)) : null;
  const gaps = highlight ? t('group_trend_gaps_highlight',{name:trend.groups.find(group => group.id === highlight).name}) : t('group_trend_gaps');
  if (trend.gaps.textContent !== gaps) trend.gaps.textContent = gaps;
  if (trend.view === 'overlay') paintGroupTrendPlot(chart,trend.overlay,trend.visible,point,highlight);
  for (const group of trend.groups) {
    const row = trend.rows.querySelector(`[data-trend-group="${CSS.escape(group.id)}"]`);
    if (row.hidden) continue;
    if (trend.view === 'split') paintGroupTrendPlot(chart,row.querySelector('canvas'),group.series,point);
    for (const {item,index} of group.series) {
      const output = row.querySelector(`[data-series-index="${index}"] output`);
      const reading = point ? chartReading(point,index,item,1) : '';
      if (output.textContent !== reading) output.textContent = reading;
    }
  }
  const drawing = groupTrendCanvas(trend.axis);
  if (!drawing) return;
  const {ctx,width} = drawing;
  const {start,end,x} = groupTrendGeometry(chart,width);
  const intervals = width >= 540 ? 6 : width >= 340 ? 4 : 3;
  for (let i=0;i<=intervals;i++) {
    const time = start+(end-start)*i/intervals;
    ctx.textAlign = i === 0 ? 'left' : i === intervals ? 'right' : 'center';
    ctx.fillText(shortTime.format(time),x(time),12);
  }
}
