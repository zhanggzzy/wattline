# Tasks

## 1. Machine list presentation

- [x] 1.1 Add the localized assignee column immediately after Status, render each person as a read-only chip with an empty `未登记 / Not assigned` value, remove the duplicate row summary, and update empty-row spans, wrapping, table width and narrow card labels. Verify bilingual desktop and 320px layouts with multiple and 80-character names.

## 2. Chip assignee editor

- [x] 2.1 Replace the checkbox rows with native-checkbox chips, selected count, pointer and Space toggling, clear and directory-update synchronization, visible focus and 44px targets while preserving save, cancel, failure draft and disabled states. Verify accessible names, literal names and count transitions with the synthetic API browser check.
- [x] 2.2 Add the bilingual keys, CSS and front-end documentation for the chip presentation.

## 3. Verification and handoff

- [x] 3.1 Run pytest, JavaScript and translation checks, the synthetic Chromium regression, OpenSpec strict validation and diff checks; record commands, outputs, commits, screenshots and limits in [`verification.md`](verification.md).
- [ ] 3.2 Record the independent review of AN-134 and resolve its findings. Review report: pending.
- [ ] 3.3 Mika integrates the reviewed result and records the verified remote SHA.

## Workflow follow-up

- Sync the applicable spec and archive only after implementation, verification and independent review pass; the review and integration tasks stay unchecked in this handoff.
