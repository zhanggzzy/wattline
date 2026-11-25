# Tasks

## 1. Machine list presentation

- [x] 1.1 Add the localized assignee column immediately after Status, render each person as a read-only chip with an empty `未登记 / Not assigned` value, remove the duplicate row summary, and update empty-row spans, wrapping, table width and narrow card labels. Preserve consecutive internal spaces in chip names. Switch to labelled cards at the container width where the seven-column table stops fitting, so 700, 730, 950 and 1024 CSS px layouts show every metric field without horizontal scrolling. Verify bilingual 320 and 1440 layouts with multiple, 80-character and double-space names, and both sides of the card switch boundary.

## 2. Chip assignee editor

- [x] 2.1 Replace the checkbox rows with native-checkbox chips, selected count, pointer and Space toggling, clear and directory-update synchronization, visible focus and 44px targets while preserving save, cancel, failure draft and disabled states. Preserve consecutive internal spaces in chip names so names differing only in spacing stay distinguishable. Verify accessible names, literal names and count transitions with the synthetic API browser check.
- [x] 2.2 Add the bilingual keys, CSS and front-end documentation for the chip presentation.

## 3. Verification and handoff

- [x] 3.1 Run pytest, JavaScript and translation checks, the synthetic Chromium regression, OpenSpec strict validation and diff checks; record commands, outputs, commits, screenshots and limits in [`verification.md`](verification.md). The regression SHALL cover 700, 730, 950, 1024 and the actual container switch boundary in both languages plus 320 and 1440, distinct double-space names in list and picker chips, and the absence of horizontal list or page scrolling with all four metric fields visible.
- [x] 3.2 Record the independent review of AN-134 in [`review-an-134.md`](review-an-134.md) and resolve both findings there: collapsed internal spacing and medium-width horizontal scrolling.
- [ ] 3.3 Mika integrates the reviewed result and records the verified remote SHA.

## Workflow follow-up

- Sync the applicable spec and archive only after implementation, verification and independent review pass; the review and integration tasks stay unchecked in this handoff.
