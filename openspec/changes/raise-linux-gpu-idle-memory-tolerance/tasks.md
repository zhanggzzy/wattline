# Tasks

## 1. Linux idle tolerance default

- [x] 1.1 Raise the `Machine.idle_memory_tolerance_mib` default and the host probe fallback to 256 MiB while preserving explicit values including 0. Verify configuration tests cover the default, an explicit 0 and an explicit non-zero override.
- [x] 1.2 Cover the Linux occupancy decision with synthetic `nvidia-smi` XML: valid PID stays occupied, 256 MiB used is free, above 256 MiB is unknown with the occupancy warning, and missing used VRAM, incomplete inventory or incomplete process enumeration stay unknown. Verify the new tests pass.
- [x] 1.3 Cover unchanged Windows and container behavior with synthetic samples. Verify the platform-specific tests pass.

## 2. Verification and handoff

- [x] 2.1 Run the repository checks and record commands, exit codes and limits in [verification.md](verification.md): `.venv/bin/python -m pytest -q`, `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate raise-linux-gpu-idle-memory-tolerance --strict`, `git diff --check`.
- [x] 2.2 Produce the local commit and the applyable patch against the recorded baseline for the AN-211 handoff.

## 3. Dynamic tolerance settings

- [x] 3.1 Extend the existing settings API and sampler. Verify API and synthetic collection cover the default, per-machine override, immediate readback, later samples, restart, old clients and rows, invalid values and a failed transaction.
- [x] 3.2 Add the control to the localized machine configuration dialog. Verify the Chinese and English labels, eligibility, validation, saving zero and readback in the synthetic browser checks.
- [x] 3.3 Run repository checks and record the commands and results in verification.md. Verify both commits apply in order on the AN-211 baseline.

## 4. Review follow-up

- [x] 4.1 Verify the optional Linux XML count, preserving PID priority. Test matching, absent, mismatched and invalid counts with synthetic XML through collection alert evaluation.
- [x] 4.2 Align the proposal, design and spec with the inventory gate, PID priority and partial container visibility. Verify both container states with synthetic samples and run OpenSpec strict validation.
- [x] 4.3 Run the regression suite and record results in [verification.md](verification.md). Replay the complete three-commit handoff from the original baseline and compare the resulting trees.

## 5. Independent review

- [ ] 5.1 AN-212 independently verifies the complete handoff and retests AN-210 findings before Mika integrates.

## Workflow follow-up

- Sync the `linux-gpu-occupancy` capability and archive only after independent review passes.
