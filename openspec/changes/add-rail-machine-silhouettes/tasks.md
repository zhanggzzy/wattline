# Tasks

## 1. Contract and mapping

- [x] 1.1 Complete proposal, spec delta, design and tasks; verify `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-rail-machine-silhouettes --strict` passes.
- [x] 1.2 Implement reliable GPU-name classification with conservative all-device agreement and generic fallback in `wattline/static/monitor.js`; verify the classification matrix through the synthetic browser check.
- [x] 1.3 Emit a monochrome silhouette with a stable `data-model`, plus instance name, status and all distinct full model names in the accessible name and title; verify accessible labels for known, unknown, mixed and model-less machines.

## 2. Compact and expanded rail

- [x] 2.1 Lay out the 24px silhouette, independent status dot and optional suffix in the 64px collapsed rail while preserving the existing expanded name/status row; verify at 64px, 320px, 390px and 1440px with no horizontal overflow.
- [x] 2.2 Generate unique short suffixes for machines sharing one silhouette class; verify duplicate B300 instances show distinct visible suffixes, uniquely named single instances show none, and model-less duplicates still differ.

## 3. Verification and handoff

- [x] 3.1 Extend the synthetic Chromium check with B300, PRO 6000, GB10, RTX 5090, unknown, mixed, legacy and duplicate instances; assert glyph distinctness at actual size, status/selection/navigation, hover and keyboard labels, expand/collapse, both actual surface colors and monochrome stroke, and capture screenshots.
- [x] 3.2 Run pytest, `node --check`, the synthetic browser check, OpenSpec strict and diff checks; record real commands, results, screenshots and limits in `verification.md`.
- [x] 3.3 Commit the implementation and evidence in the fixed repository with baseline and delivery SHA recorded; keep the change active for independent review.
- [ ] 3.4 Independent reviewer verifies the change, implementation diff, tests and strict result against the accepted scheme A.
- [ ] 3.5 After review passes, sync the modified capability spec and archive the change; Mika integrates and verifies remote main.

## 4. AN-63 review remediation

- [x] 4.1 Include every machine's derived model kind and complete device names in the render signature so an ordinary poll refreshes rail, overview, hints and same-model suffixes without navigation, including while another machine is selected.
- [x] 4.2 Treat blank device names, configured expected-count mismatch and a live sample marked incomplete as unreliable: fall back to `generic` while keeping known complete names, and keep last known silhouettes for offline machines with a complete trusted inventory.
- [x] 4.3 Reject per-name ambiguity and digit overruns (`B300 / RTX 5090`, `PRO 60000`) instead of taking the first matching model.
- [x] 4.4 Derive suffixes by grapheme so Unicode is never truncated, and append the visible suffix to accessible names/titles when two instances share identical identity text.
- [x] 4.5 Remove the status marker's own tooltip so hovering any part of the machine button shows the same complete identity.
- [x] 4.6 Extend `tools/browser_smoke.py` with all five regressions, rerun AN-63's `review_browser.py`, pytest, i18n, JavaScript, Chromium and OpenSpec strict checks.
- [ ] 4.7 Independent re-review of the remediation (AN-67).

## 5. AN-67 review remediation

- [x] 5.1 Carry inventory completeness from collection and hot or warm history into the machine snapshot. Verify full, partial, offline, stale and recovery transitions and conservative legacy compatibility.
- [x] 5.2 Distinguish identical and Unicode-equivalent names in visible suffixes, keyboard focus hints and accessible names. Preserve original instance names.
- [x] 5.3 Match PRO 6000 at model token boundaries. Verify supported editions and unknown attached suffixes in the synthetic UI.
- [x] 5.4 Run the XML/API regressions, AN-63 and AN-67 browser cases, repository checks and OpenSpec strict. Record commands, results and limits in [verification.md](verification.md#an-70-第二轮整改验证2026-11-24).
- [ ] 5.5 Independent re-review of the second remediation (AN-69).

## Workflow follow-up

- Parent AN-62 remains `in_review` for user acceptance after independent review and main delivery.
