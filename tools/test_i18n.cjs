'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname, '../wattline/static');
function boot(saved, blocked = false) {
  const storage = {value:saved, getItem() {if (blocked) throw Error('blocked');return this.value;},
    setItem(key,value) {if (blocked) throw Error('blocked');this.value=value;}};
  const context = vm.createContext({Intl,localStorage:storage});
  for (const file of ['locales.js','i18n.js']) vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'), context);
  return {api:context.WattlineI18n, storage};
}
const {api,storage} = boot();
assert.equal(api.locale,'zh-CN');
assert.equal(api.t('save'),'保存');
const baseline = Object.keys(api.registry['zh-CN'].messages).sort();
const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(x=>x[1]).sort();
for (const entry of Object.values(api.registry)) {
  assert.deepEqual(Object.keys(entry.messages).sort(), baseline);
  for (const key of baseline) {
    assert.ok(entry.messages[key].trim(),key);
    assert.deepEqual(placeholders(entry.messages[key]),placeholders(api.registry['zh-CN'].messages[key]),key);
  }
}
for (const file of ['monitor.js','index.html']) {
  const source=fs.readFileSync(path.join(root,file),'utf8');
  for (const match of source.matchAll(/\bt\('([^']+)'|data-i18n(?:-[\w-]+)?="([^"]+)"/g)) {
    assert.ok(baseline.includes(match[1] || match[2]),match[0]);
  }
}
assert.equal(api.setLocale('en'),'en');
assert.equal(storage.value,'en');
assert.equal(boot(storage.value).api.locale,'en');
assert.equal(api.t('history_summary',{count:3,latest:'GPU 42%'}),'3 valid periods · Latest GPU 42%');
assert.equal(api.diagnostic('采集超过单机时限'),'Sampling exceeded the per-machine time limit');
assert.equal(api.diagnostic('GPU-123 的温度已达到 GPU 降频阈值'),'Temperature of GPU-123 reached the GPU throttling threshold');
assert.equal(api.diagnostic('部分 GPU 占用状态无法核实；无法读取容器内存用量'),'Some GPU usage states cannot be verified · Cannot read container memory usage');
assert.equal(api.diagnostic('raw evidence <test>'),'raw evidence <test>');
assert.equal(api.number(1234.5),new Intl.NumberFormat('en').format(1234.5));
const timestamp=Date.UTC(2026,0,2,13,14);
assert.equal(api.date(timestamp,{timeZone:'UTC',month:'long'}),'January');
delete api.registry.en.messages.save;
assert.equal(api.t('save'),'保存');
assert.equal(api.t('unknown_key'),'unknown_key');
assert.equal(api.t('toString'),'toString');
assert.equal(api.t('__proto__'),'__proto__');
assert.equal(api.t('history_summary',{count:0,latest:'$& <img>'}),'0 valid periods · Latest $& <img>');
assert.equal(boot('xx').api.locale,'zh-CN');
assert.equal(boot('__proto__').api.locale,'zh-CN');
const denied=boot('en',true).api;
assert.equal(denied.locale,'zh-CN');
assert.equal(denied.setLocale('en'),'en');
assert.equal(denied.setLocale('invalid'),'zh-CN');
console.log(`PASS: ${baseline.length} message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage`);
