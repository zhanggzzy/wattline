# AN-164 phase 1 verification

- Baseline `bede7a15e1a14cbf36c3d8a8f3a5da467d4f4b64`. Local HEAD, `origin/main` and `git ls-remote origin refs/heads/main` matched at start.
- Phase 1 implementation patch saved locally as `artifacts/an-164-design/phase1.patch`, SHA-256 `2f92179246e9e95bfd2c3e8d8ef1148d542b080458912f7125c49c29e48c8781`. The final working-tree review and verification are indexed in [phase 2 verification](../add-room-cluster-overview/verification.md). Mika owns reviewed integration.
- `.venv/bin/python -m pytest -q` exited 0 with 47 passed and one existing Starlette TestClient deprecation warning before phase 2 changes. Coverage includes v8 upgrade, legacy people, fixed host identity and archives, storage capacity and alert transitions.
- `node tools/test_i18n.cjs` exited 0 with 369 keys before phase 2. `node --check wattline/static/monitor.js` and the pinned `validate add-compute-resource-registry --strict` exited 0.
- `.venv/bin/python tools/resource_browser_smoke.py --browser "$CHROME_BINARY"` exited 0 for storage enrollment, pending state, synthetic capacity, persisted alert navigation and narrow layout.
- The first default browser launch exited 1 because Playwright's pinned browser was missing. Two local Chrome runs exited 1 while taking a screenshot in the legacy people journey due to DOM detachment. After installing Playwright's Chromium with `.venv/bin/python -m playwright install chromium`, `.venv/bin/python tools/browser_smoke.py` reported PASS in Chromium 159.0.8154.6 with zero page errors. The phase 2 record includes the final rerun.
- The adapter is supplied only by a synthetic fixture. Vendor endpoints, real nodes, deployed data and SSH reuse are outside this verification. Independent review is pending.
