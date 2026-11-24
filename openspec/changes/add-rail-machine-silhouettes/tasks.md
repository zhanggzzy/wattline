# Tasks

## 1. Contract and mapping

- [x] 1.1 Complete proposal, spec delta, design and tasks; verify `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-rail-machine-silhouettes --strict` passes.
- [x] 1.2 Implement reliable GPU-name classification with conservative all-device agreement and generic fallback in `wattline/static/monitor.js`; verify the classification matrix through the synthetic browser check.
- [x] 1.3 Emit a monochrome silhouette with a stable `data-model`, plus instance name, status and all distinct full model names in the accessible name and title; verify accessible labels for known, unknown, mixed and model-less machines.

## 2. Compact and expanded rail

- [x] 2.1 Lay out the 24px silhouette, independent status dot and optional suffix in the 64px collapsed rail while preserving the existing expanded name/status row; verify at 64px, 320px, 390px and 1440px with no horizontal overflow.
- [x] 2.2 Generate unique short suffixes only for machines sharing one silhouette class; verify duplicate B300 instances show distinct visible suffixes, single instances show none, and model-less duplicates still differ.

## 3. Verification and handoff

- [x] 3.1 Extend the synthetic Chromium check with B300, PRO 6000, GB10, RTX 5090, unknown, mixed, legacy and duplicate instances; assert glyph distinctness at actual size, status/selection/navigation, hover and keyboard labels, expand/collapse, both actual surface colors and monochrome stroke, and capture screenshots.
- [x] 3.2 Run pytest, `node --check`, the synthetic browser check, OpenSpec strict and diff checks; record real commands, results, screenshots and limits in `verification.md`.
- [x] 3.3 Commit the implementation and evidence in the fixed repository with baseline and delivery SHA recorded; keep the change active for independent review.
- [ ] 3.4 Independent reviewer verifies the change, implementation diff, tests and strict result against the accepted scheme A.
- [ ] 3.5 After review passes, sync the modified capability spec and archive the change; Mika integrates and verifies remote main.

## Workflow follow-up

- Parent AN-62 remains `in_review` for user acceptance after independent review and main delivery.
