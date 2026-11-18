# AN-43 review rework, round 1

Recorded 2026-11-18 by Executor-Codex. Issue AN-44, parent AN-42;
change `add-english-i18n`. Rework baseline is the reviewed implementation
`76b8e391ee140580f4f8d7f7a6b3af5b4adc31ee`. The commit containing this record is
this round's delivery; its exact head is in the attached handoff report.

## Problem and minimal correction

AN-43 identified P2: action handlers replaced button textContent and deleted the
nested data-i18n span. Saving (including a failed save) or removing left a label
that locale changes could no longer translate. The original browser smoke used a
reload after operations and missed that sequence.

The save/removal translation markers now belong to the buttons themselves.
`setButtonLabel(button,key)` updates the marker and text together, using existing
central resource keys for verifying connection, saving, removing and restored
labels. It does not add page-level locale branches, rewrite i18n.apply, or change
business APIs. Both success and failure paths restore the idle key in finally.
The active locale is applied by the existing switch handler when reopening.

Files: `wattline/static/index.html`, `wattline/static/monitor.js`,
`tools/browser_smoke.py`, and this change's design/spec/tasks/evidence records.

## Reproducible checks and actual results

Commands ran from the task checkout root unless noted. Existing task-local .venv
and Chromium 159.0.8154.6 were reused. All API responses are synthetic.

| Command | Actual result | Exit |
| --- | --- | --- |
| `.venv/bin/python tools/browser_smoke.py` before production fix | new matrix reproduced expected Save / actual 保存 after a successful Chinese add, then English switch without reload | 1 |
| `.venv/bin/python tools/browser_smoke.py` after fix | PASS, original bilingual flows plus 12 mutation/locale cases, no page errors, 18 declared screenshots, 19 layout widths | 0 |
| `.venv/bin/python -m pytest -q` | 16 passed, 1 Starlette/httpx deprecation warning, 0.67s | 0 |
| `node tools/test_i18n.cjs` | PASS, 261 keys and placeholder parity, fallback/persistence/Intl/diagnostic checks | 0 |
| `node --check wattline/static/monitor.js` | syntax valid | 0 |
| `node --check wattline/static/i18n.js` | syntax valid | 0 |
| `node --check wattline/static/locales.js` | syntax valid | 0 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-english-i18n --strict` | change valid | 0 |
| `git diff --check` / `git diff --cached --check` | clean | 0 |

The new matrix covers add, settings-save and remove × success/failure × zh-CN→en
and en→zh-CN. Each case holds the mutation response while checking disabled state,
visible busy text and accessible name, reapplies localization while pending, then
releases the response and checks restoration. After closing, it switches locale
and opens again, checking idle text and accessible name. A document object identity
assertion verifies that no navigation/reload occurred. Successful removal reopens
on the remaining synthetic node. Successful add returns via overview before
reopening. Hidden buttons have no exposed accessible name; name assertions are
made while the dialog is visible, and restoration text is also checked while hidden.

The final pre-fix failure and full post-fix output are included as raw logs in the
handoff. During test development, assertions were corrected to account for hidden
button accessibility and successful-add navigation before recording the pre-fix
language failure. Those harness issues are not product defects or passing runs.

## Original reviewer reproduction

Downloaded the original AN-43 report and script via the authenticated Multica CLI,
read both before execution. The script was rerun as a task-local copy with only
ROOT and screenshot output paths adapted to this checkout; its interaction logic
was unchanged. From the task working directory:

```sh
wattline/.venv/bin/python review-input/AN-43-repro-local.py
```

Result (exit 0):

```json
{"en_dialog_save_label":"Save","en_dialog_title":"Add machine","zh_dialog_save_label":"保存","zh_remove_confirm_label":"确认移除","page_errors":[]}
```

This is an implementer's rerun of the review script, not a new independent review.
Four new matrix screenshots were generated; English add and Chinese removal
screenshots were visually inspected. Logs, screenshots, adapted reproduction
script, patch and bundle are attached to the issue handoff.

## Scope limits and remaining review

The two nonblocking observations are unchanged: Chinese compound diagnostic
separators currently use ` · `, and filtered English counts can read
`1 / 1 machines`. This round deliberately keeps resources, formatting and the
public localization API stable and confines the production fix to dialog-button
state. Neither observation loses data or prevents operation; Mika/reviewer may
track copy refinements separately.

No live SSH, real collection, deployment, push, merge, remote SHA verification or
other browsers were exercised. Packaging was already checked in the original
implementation and was not rerun for this markup/text-state fix. The complete
original limitations remain in verification.md. Independent re-review and main
integration remain unchecked; no spec synchronization or archive was performed.
