# Tasks

## 1. Memory display implementation

- [x] 1.1 Add the used-capacity secondary reading to the overview memory cell and refresh it from `memory.used_bytes` in `paint()`, hiding it when unavailable; verify with synthetic browser assertions for 38% / 48.0 GiB.
- [x] 1.2 Give the detail-card used amount an explicit per-value `GiB` unit while keeping the percentage primary and unlimited-container behavior unchanged; verify the rendered text in the browser check.
- [x] 1.3 Extend `tools/browser_smoke.py` with Chinese/English, desktop/mobile and missing-sample assertions; verify the smoke run passes without page errors.

## 2. Verification evidence

- [x] 2.1 Run `python -m pytest -q`, `node --check wattline/static/monitor.js`, `node tools/test_i18n.cjs`, browser smoke, `validate --strict` and `git diff --check`; record commands, outputs and limits in `verification.md`.
- [x] 2.2 Inspect the diff for scope and confirm no backend/API/schema changes are included.

## 3. Review and delivery

- [x] 3.1 Independent reviewer verifies the change, diff, screenshots and checks (AN-46 passed on 2026-11-19; see verification.md).
- [ ] 3.2 Mika integrates the reviewed commit and verifies the remote SHA.

## Workflow follow-up

- After independent review passes, synchronize the `dashboard-memory-metrics` spec and archive this change with the official skills.
- Record the review conclusion and archive outcome in this change before closing the parent task.
