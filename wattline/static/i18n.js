'use strict';

// Kept independent of the DOM for resource and preference contract tests.
globalThis.WattlineI18n = (() => {
  const registry = globalThis.WattlineLocales;
  const defaultLocale = 'zh-CN';
  const storageKey = 'wattline.locale';
  const supported = locale => Object.hasOwn(registry, locale);
  let locale = defaultLocale;
  try {
    const saved = globalThis.localStorage?.getItem(storageKey);
    if (supported(saved)) locale = saved;
  } catch { /* Storage may be disabled; use the session default. */ }

  function t(key, parameters = {}) {
    const lookup = messages => Object.hasOwn(messages,key) ? messages[key] : undefined;
    const message = lookup(registry[locale].messages) ?? lookup(registry[defaultLocale].messages) ?? key;
    return message.replace(/\{(\w+)\}/g, (token, name) =>
      Object.hasOwn(parameters, name) ? String(parameters[name]) : token);
  }
  // Match only known application diagnostics; arbitrary evidence stays untouched.
  const diagnostics = Object.entries(registry[defaultLocale].messages)
    .filter(([key]) => key.startsWith('diagnostic_') || key === 'valid_sample_expired_awaiting_a_new_sample')
    .map(([key, source]) => {
      const names = [...source.matchAll(/\{(\w+)\}/g)].map(match => match[1]);
      const escaped = source.split(/\{\w+\}/g).map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
      return {key, names, pattern:new RegExp('^'+escaped.join('(.+?)')+'$')};
    });
  function diagnostic(value) {
    if (typeof value !== 'string') return '';
    return value.split('；').map(part => {
      for (const {key,names,pattern} of diagnostics) {
        const match = part.match(pattern);
        if (match) return t(key, Object.fromEntries(names.map((name,i) => [name,match[i+1]])));
      }
      return part;
    }).join(' · ');
  }
  const number = (value, options = {}) => new Intl.NumberFormat(locale, options).format(value);
  const date = (value, options = {}) => new Intl.DateTimeFormat(locale, options).format(value);

  function apply(root = document) {
    document.documentElement.lang = locale;
    for (const node of root.querySelectorAll('[data-i18n]')) node.textContent = t(node.dataset.i18n);
    for (const attr of ['aria-label', 'placeholder', 'title']) {
      for (const node of root.querySelectorAll('[data-i18n-'+attr+']')) {
        node.setAttribute(attr, t(node.getAttribute('data-i18n-'+attr)));
      }
    }
    const selector = document.getElementById('locale-select');
    if (selector) selector.value = locale;
    document.documentElement.removeAttribute('data-localizing');
  }
  function setLocale(value) {
    locale = supported(value) ? value : defaultLocale;
    try { globalThis.localStorage?.setItem(storageKey, locale); } catch { /* Session remains usable. */ }
    return locale;
  }
  return {registry, defaultLocale, storageKey, t, diagnostic, number, date, setLocale, apply, get locale() { return locale; }};
})();
