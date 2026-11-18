# Dashboard languages

The dashboard defaults to Simplified Chinese (`zh-CN`). Use the Language / 语言
selector in the top bar to choose English (`en`). The browser remembers this
choice in localStorage (`wattline.locale`); it is independent of machine settings
and does not send a preference to the server. Unsupported saved locales or blocked
storage use Chinese. If writing storage fails, switching still works for the
current page. There is no automatic browser-language detection.

`wattline/static/locales.js` owns the locale registry (native display labels) and
all messages. `i18n.js` exposes `WattlineI18n`: `locale`, `setLocale(id)`,
`t(key, parameters)`, `number(value, IntlOptions)`, `date(timestamp, IntlOptions)`
and `apply(root)` for static `data-i18n`, `data-i18n-aria-label`,
`data-i18n-placeholder` and `data-i18n-title` attributes. Translation lookup falls
back to Chinese and finally to the literal key. Named `{parameters}` are replaced
literally; absent parameters stay visible for diagnosis. `t()` returns plain text:
use textContent or the dashboard's `escape()` when inserting arbitrary values in
HTML. Never put markup or executable content into resources. HTML structure stays
in templates. Date/time uses the browser time zone, preserving existing behavior.

To add a language, add one registry entry to `locales.js` with its BCP 47 locale,
native label and a complete message dictionary. The selector is generated from the
registry. Keep existing message IDs stable when changing wording; use named
parameters for complete dynamic messages. No page-level locale conditionals are
needed. Verify every dictionary has the same keys and placeholders:

~~~sh
node tools/test_i18n.cjs
.venv/bin/python tools/browser_smoke.py
~~~

Static content is hidden until synchronous localization bootstrap completes, so a
saved English preference does not expose Chinese during loading. Language switching
rerenders the current view while retaining selection, search, filters and history.
Native modal dialogs make the top-bar selector inert while editing; form data is
not discarded. Browser-native validation wording follows the browser's own language.

Machine names, SSH addresses and process/workload evidence retain their original
text. Known application diagnostics are translated through `diagnostic(text)`
using centralized `diagnostic_` messages (including named dynamic fields). Unknown
server details retain their original text after localized operation context. This preserves diagnostic evidence
without changing existing business HTTP APIs or attempting to translate user data.
The nvidia-smi field names and technical units remain canonical.
