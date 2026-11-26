# AN-154 integration closeout

Date: 2026-11-26. Scope: AN-164 phases 1 and 2 and the three-card revision. [AN-168 independent review](review-an-168.md) passed without required changes, performed by Reviewer-DeepSeek (`deepseek/deepseek-flash`). The full report lists four non-blocking observations and the remaining verification limits.

- Reviewed baseline: `bede7a15e1a14cbf36c3d8a8f3a5da467d4f4b64`.
- Reviewed cumulative patch SHA-256: `1a50263b7d5f93b9e882fb148b084fce4eecad03b381053451ace91d36dacd54`.
- Implementation integrated to local main as `c5906326b97a10129a4563577ad4b60bc61aaa53`. The staged patch passed the reverse-apply check. The commit also records the two implementation verification reports and the independent review. The staged AGENTS.md matched the baseline and excludes local runtime content.
- [Phase 1 implementation evidence](../2026-11-26-add-compute-resource-registry/verification.md) and [phase 2 implementation evidence](verification.md) describe the actual checks and patch files. The final main SHA and remote readback are tracked on AN-154.

## Integration checks

| Command | Exit | Observed result |
| --- | ---: | --- |
| `.venv/bin/python -m pytest -q` | 0 | 51 passed; existing Starlette TestClient deprecation warning. |
| `node --check wattline/static/monitor.js` and `node --check wattline/static/groups.js` | 0 | No syntax errors. |
| `node tools/test_i18n.cjs` | 0 | 415 message keys; locale and placeholder checks passed. |
| `.venv/bin/python tools/resource_browser_smoke.py` | 0 | Three cards, both power readings and coverage, storage, alarms, group management, keyboard and narrow layout passed. |
| `.venv/bin/python tools/browser_smoke.py` | 0 | Chromium 159.0.8154.6, both locales, 122 history queries and zero page errors. |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate <change> --strict` | 0 | Both active changes passed. |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate --specs --strict` | 0 | All 10 main specs passed after synchronization and after archive. |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 list --json` | 0 | Before archive, 5/5 and 7/7 tasks complete. After archive, neither change remains active. |
| `git diff --check` and `git diff --cached --check` | 0 | No whitespace errors. |

The `spec-driven` changes `add-compute-resource-registry` and `add-room-cluster-overview` were moved to the 2026-11-26 archive after synchronizing their six capabilities and verifying every changed requirement. Local synthetic verification covered Chromium, storage adapter fixtures and Linux/Windows payloads. Live hardware, vendor adapters, production concurrency, SSH reuse, Feishu and deployment were outside this closeout.
