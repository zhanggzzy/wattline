# AN-219 verification

## Baseline and patch

- The task checkout initially had `origin/main` at `0123c748d9c628902105738a7e5a080aaf3e92d4`. The authenticated AN-202 attachment was 103,313 bytes with SHA-256 `cf94203d1d7ee9045539388c04b1758442fe22fd6b35e45c428a00ce5ba47ece`. Its original four commits applied there and produced tree `7077650dc8a556eccac693513b28256186ce6019`.
- `git fetch origin main` and `git ls-remote origin refs/heads/main` identified `10f966f2d0da4390d3de5502b0dadcab85056642` as the delivery base. That tree contains AN-215 and still has the old 0 MiB default and no Linux GPU occupancy specification. The four prerequisite changes were replayed once onto that base with `git rebase --onto origin/main 0123c74`.
- The Windows test conflict kept both the upstream valid-sample warning assertion and the explicit 256 MiB probe fixture. The final implementation converts older aggregate occupancy warning assertions to checks for the state, inventory diagnostic and independent collection validity. AN-202's archived records describe the original review on its original base.
- The replayed commits are `270f7c7`, `0431604`, `a238a3d`, `8824f83` and implementation commit `df5b48f659be443e7ac3ced4be3780b4bc4bbb3e`. Git identity was supplied per command for local commits because the checkout had no configured committer. The prerequisite authors were preserved.
- A detached worktree at `10f966f` applied all five candidate commits with plain `git am`, with three-way fallback disabled. Its resulting tree `2c24877a816097ff722b13879ddcdf709fdd8b03` matched the implementation tree exactly. Apply the full AN-219 attachment on that base. It contains the prerequisite changes, implementation and this verification record.

## Automated verification

Commands ran in the replay worktree using the task virtual environment, Python 3.11.17 and Playwright 1.65.2. The browser ran Chromium 159.0.8154.6.

| Command | Exit | Output |
| --- | --- | --- |
| `PYTHONPATH=. ../bin/python -m pytest -q` | 0 | `83 passed, 1 warning in 2.02s`. The warning is a Starlette TestClient deprecation for the existing HTTPX client. |
| `PYTHONPATH=. ../bin/python tools/browser_smoke.py` | 0 | `result: PASS`, both locales, 12 dialog scenarios, `page_errors: []`. |
| `PYTHONPATH=. ../bin/python tools/resource_browser_smoke.py` | 0 | `PASS` including localized layered configuration, cross-room member sources, conflict selection, explicit zero, clearing and deletion confirmation. |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate layered-resource-configuration --strict` | 0 | `Change 'layered-resource-configuration' is valid`. |
| `node --check wattline/static/monitor.js` and `node --check wattline/static/groups.js` | 0 | Both files parsed. |
| `node tools/test_i18n.cjs` | 0 | `PASS: 444 message keys` with placeholder parity, interpolation and locale fallback. |
| `git diff --check 10f966f..HEAD` and `git diff --cached --check` | 0 | No whitespace diagnostics. |

`test_layered_tolerance_uses_membership_at_start_of_each_sample` injects NVIDIA XML through the production collector and checks state, accepted threshold and source when room and cluster membership change during an in-flight sample. It also checks that valid samples with unknown GPU occupancy leave collection events clear. `test_layered_configuration_keeps_legacy_values_and_group_writes_atomic` covers all four levels, agreeing and conflicting clusters, selected-source invalidation, cross-room membership, old client omissions, file overrides, explicit zero, schema 10 migration and restart. Trigger-injected failures verify that cluster fields and memberships roll back together and that failed global writes retain their prior value. The existing machine-save failure test verifies rollback when alias persistence fails after the settings row is written.

## Scope

Evidence comes from synthetic host and device fixtures, temporary SQLite and Chromium with the in-process HTTP API or intercepted requests. Real SSH, physical GPU or Windows machines, other browser engines and instance deployment are outside this verification. AN-218 is the independent review. Its task remains open in this active change.

## Independent review and local integration (AN-218 / AN-202)

On 2026-11-26 Reviewer-DeepSeek (DeepSeek 4.1 Flash) passed the six-commit
handoff in AN-218 (comment `01a2179c-ffab-7d7f-b2e5-57d2cf82dd19`). The reviewer
applied the patch in an independent checkout on `10f966f2d0da4390d3de5502b0dadcab85056642`
and matched tree `69b7560d2f7c74ef8a40737b82ba01745f3479ef`.

The reviewer reran 83 tests, both Chromium smoke checks, OpenSpec 1.14.2 strict
change validation, JavaScript syntax and localization checks, and the Git diff
check. Independent probes covered scope deletion, conflicts and invalid
selections, explicit zero at each level, omitted fields, failed writes,
invalid input and collection alert evidence.

Mika replayed the same reviewed tree, recorded the review and synchronized the
Linux GPU occupancy, machine registry, overview and resource group specifications.
The closure commit adds OpenSpec records only. The verification used synthetic
GPU XML, temporary SQLite and isolated Chromium. Live SSH, physical GPUs,
Windows and container hosts, and production deployment were outside its scope.
