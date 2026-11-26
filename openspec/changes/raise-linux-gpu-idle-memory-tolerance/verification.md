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
