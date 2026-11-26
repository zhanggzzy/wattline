# AN-211 verification

- Baseline: `origin/main` at `0123c748d9c628902105738a7e5a080aaf3e92d4` (local HEAD matched). Branch `agent/executor-omp/0154f802fb33`.
- Change: `raise-linux-gpu-idle-memory-tolerance`, OpenSpec CLI 1.14.2 with the default `spec-driven` schema.
- Environment: `/opt/homebrew/bin/python3.11` venv at `.venv`, `pip install -e ".[test]"`, Node 26.11.0.

## Commands and results

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` (before changes) | exit 0, 51 passed, one existing Starlette deprecation warning |
| `.venv/bin/python -m pytest -q` (after changes) | exit 0, 63 passed, same warning |
| `node --check wattline/static/monitor.js` | exit 0 (no frontend change; repository check retained) |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate raise-linux-gpu-idle-memory-tolerance --strict` | exit 0, `Change ... is valid` |
| `git diff --check` | exit 0 |

## Coverage added

Synthetic `nvidia-smi` XML through `host_probe.monitor_gpus` and configuration parsing
through `Config.model_validate_json`:

- Default 256 MiB when the field is omitted, explicit 0 and explicit 512 preserved.
- Complete inventory and enumeration with no PID: 0 MiB and exactly 256 MiB are free;
  256.5 MiB is unknown and emits `部分 GPU 占用状态无法核实`.
- Explicit 0 keeps 128 MiB unknown; explicit 2048 MiB treats 1024 MiB as free.
- An observed valid PID stays occupied even with 0 MiB used.
- Missing used VRAM, incomplete inventory (`expected_gpu_count` mismatch), partial
  enumeration text and MIG mode stay unknown and warn.
- Container view (`host_processes=False`, `warn_on_unknown=False`) stays unknown with
  partial visibility and emits no occupancy warning.
- Windows `windows.metrics` receives `idle_memory_tolerance_mib: 256` and still reports
  unknown for a card with 0 MiB used and no process rows.

## Limits

- All evidence is synthetic; no real node was contacted, no instance was reconfigured or
  upgraded, and no collection was triggered.
- Verification is implementer self-testing, not independent review. AN-210 performs the
  independent review against this change and the handoff patch.
- The change stays unarchived; spec sync and archive belong to the post-review workflow.

# AN-213 verification

- Replay order starts at `origin/main` `0123c748d9c628902105738a7e5a080aaf3e92d4`, then
  AN-211 `0dfcace7941925b157f5473c8f51459482d8a8a2`, then the AN-213 commit that adds this record.
- The downloaded AN-211 patch had SHA-256
  `ad23304db57c9774a3c6fd774c15ead5c779c61a63c0abe3d894b9a3dbd5dda2`
  and matched `git format-patch -1 --stdout` of the AN-211 commit byte for byte.
  The source email header was empty and standalone `git am` reported
  `empty ident name`. The combined delivery fills only the AN-211 patch author header
  with the stage 1 agent identity so it can replay with standard Git.
- The managed checkout had empty identity values. The AN-213 commit uses the
  one-command identity `Executor-Codex <executor-codex@localhost>`.
- Used Python 3.11.17 with `pip install -e '.[test,browser-test]'`, Node 26.11.0,
  OpenSpec CLI 1.14.2 and Chromium 159.0.8154.6.

## Commands and results

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` on AN-211 | Exit 0, 63 passed, one existing Starlette deprecation warning |
| `.venv/bin/python -m pytest -q` on AN-213 | Exit 0, 64 passed, same warning |
| `node --check wattline/static/monitor.js` | Exit 0 |
| `node tools/test_i18n.cjs` | Exit 0, PASS, 417 message keys and placeholder parity |
| `.venv/bin/python tools/browser_smoke.py` | Exit 0, PASS, no page errors. Chinese settings saved and read back 0 MiB from 256 MiB. English settings saved and read back 512.5 MiB from 0 MiB. Both locales rejected negative input, omitted unchanged values and hid the field for inapplicable machines. |
| `.venv/bin/python tools/resource_browser_smoke.py` | Exit 0, PASS |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate raise-linux-gpu-idle-memory-tolerance --strict` | Exit 0, change is valid |
| `git diff --check` and `git diff --cached --check` | Exit 0 |
| `git read-tree <baseline>`, `git apply --cached <AN-211 patch>`, `git apply --check --cached <AN-213 diff>` in a temporary index | Exit 0, AN-211 tree matched its recorded commit and AN-213 applied on top |

## Coverage

- The real settings API, SQLite and sampler ran in-process. The real collector passed
  the saved threshold into the Linux probe against synthetic NVIDIA XML. Readback was
  immediate and subsequent samples used the new threshold on the original cadence.
- Verified inclusive 256 MiB, a precise fractional override, occupancy above the limit,
  explicit 0 MiB and restart. An old client's save preserved the precise override. A
  legacy settings row inherited a file-configured zero, and a legacy registration that
  had serialized its old default inherited 256 MiB.
- Negative, non-finite and nonnumeric payloads returned 422. An SQLite trigger failed
  the save after the settings upsert. The API returned 503, and stored values and
  subsequent sample classifications remained consistent before and after restart.
- Linux process and inventory evidence checks, Windows and container behavior kept the
  existing synthetic regression coverage.

## Limits

Verification used synthetic data and an isolated browser. The change remains active
for independent review in AN-210 and AN-212. Rollback of an instance that has stored
dynamic settings requires the pre-upgrade data backup described in the design.

# AN-214 verification

- The managed checkout started at `origin/main` `0123c748d9c628902105738a7e5a080aaf3e92d4`.
  The AN-213 attachment SHA-256 matched the handoff
  (`fcf9547e7302951d68775a38c93e2bc5d64b0b124d3182360e589a69f115c443`).
  `git am an-211-an-213-linux-gpu-idle-vram.patch` imported both messages in order.
  The resulting AN-211 tree `445b6bfc4c689dbb8607820497bda28ba3fa265e` matched
  `0dfcace7941925b157f5473c8f51459482d8a8a2^{tree}`. The resulting AN-213 tree
  `79274670e844444f5d83143e67405436ae15818e` matched
  `34008b6f5b5726c384451d75c9cf25734a21e3f7^{tree}`.
- The checkout had empty Git identity values. Import and commit used the
  command-scoped `Executor-Codex <executor-codex@localhost>` identity, and
  `git am` retained both patch authors. The local replay produced new commit IDs.
- Verification used Python 3.11.17, OpenSpec 1.14.2 and Chromium 159.0.8154.6.

## Reproduction

The AN-210 script's `seed` command ran on the original baseline and stored the
implicit 0 MiB default in a temporary SQLite registration. Running
`PYTHONPATH=. .venv/bin/python ../attachments/an-210-repro.py check ../attachments/an-210-fixture`
on AN-213 showed the count discrepancy before the script stopped at a `KeyError`.
The script expected new registrations to store a threshold. AN-213 omits that field
for inherited defaults. After the fix, the same script's `observe` helper sampled
the seeded registration at its effective 256 MiB threshold and produced these results.

| XML count / one returned GPU | Used VRAM | PID | Verified inventory | Occupancy | Occupancy warning |
| --- | --- | --- | --- | --- | --- |
| `1` | 128 MiB | none | yes | `free` | absent |
| `2` | 128 MiB | none | no | `unknown` | present |
| `N/A` | 128 MiB | none | no | `unknown` | present |
| `2` | unavailable | 93 | no | `occupied` | absent |

The committed pytest regression also checks present but invalid counts, compatibility
with the missing field, partial process visibility with a valid PID, inventory and
occupancy warnings in collection alert evidence, and both container occupancy states.

## Commands and results

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q 'tests/test_monitor.py::test_linux_gpu_inventory_count_alert[mismatch]'` before the fix | Exit 1, the inventory was incorrectly verified |
| `.venv/bin/python -m pytest -q tests/test_monitor.py -k 'linux_gpu_inventory_count_alert or linux_gpu_occupancy_tolerance or container_view_keeps_partial_process_visibility or gpu_tolerance_settings_apply_to_later_samples_and_persist'` | Exit 0, 25 passed |
| `.venv/bin/python -m pytest -q` | Exit 0, 77 passed and one existing Starlette deprecation warning |
| `.venv/bin/python tools/browser_smoke.py` | Exit 0, PASS, no page errors. Chinese settings saved 0 MiB and English settings saved 512.5 MiB. |
| `.venv/bin/python tools/resource_browser_smoke.py` | Exit 0, PASS |
| `node --check wattline/static/monitor.js` and `node tools/test_i18n.cjs` | Exit 0, 417 message keys and placeholder parity |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate raise-linux-gpu-idle-memory-tolerance --strict` | Exit 0, change is valid |
| `git diff --check` and `git diff --cached --check` | Exit 0 |

## Patch replay

The local sequence is AN-211 `63dbd8377b2352c02c86df15aa7f347e81833033`, AN-213
`45ce62c5c9c1a818c94f377fd576ae042f1e44ec`, then the AN-214 commit containing this record.
Export with `git format-patch --stdout 0123c748d9c628902105738a7e5a080aaf3e92d4..HEAD`.
From a clean detached worktree at that baseline, run
`git am an-211-an-213-an-214-linux-gpu-idle-vram.patch` with a configured Git committer.
Replay exited 0 and all three trees matched the export. Compare the three trees in
each worktree with `git rev-parse 'HEAD~2^{tree}' 'HEAD~1^{tree}' 'HEAD^{tree}'`.

## Scope

Verification used synthetic XML, temporary SQLite data and an isolated browser. AN-212
will independently review the complete patch series before integration.
