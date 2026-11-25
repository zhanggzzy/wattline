# Tasks

## 1. Machine list presentation

- [x] 1.1 Add the localized assignee column immediately after Status, render each person as a read-only chip with an empty `未登记 / Not assigned` value, remove the duplicate row summary, and update empty-row spans, wrapping, table width and narrow card labels. Preserve consecutive internal spaces in chip names. Switch to labelled cards at the container width where the seven-column table stops fitting, so 700, 730, 950 and 1024 CSS px layouts show every metric field without horizontal scrolling. Constrain column content and verify AN-137 at expanded 1156 and collapsed 986/1024 CSS px, both navigation states and languages across the boundary and during repeated resizing, and long machine names, multiple people and large metric values.
- [x] 1.2 Constrain `.machine-identity`, `.row-open`, and its `strong`/`small` text inside the machine column in table mode with in-column ellipsis truncation so long machine names, addresses, and SSH aliases never extend into or overlap the adjacent Status badge, while keeping full accessible names, focus outlines, navigation, drag-to-reorder, keyboard interactions, narrow-card wrapping, and previously passing 7-column, metric, and chip behaviors.

## 2. Chip assignee editor

- [x] 2.1 Replace the checkbox rows with native-checkbox chips, selected count, pointer and Space toggling, clear and directory-update synchronization, visible focus and 44px targets while preserving save, cancel, failure draft and disabled states. Preserve consecutive internal spaces in chip names so names differing only in spacing stay distinguishable. Verify accessible names, literal text, visible glyph positions when both names wrap, 80-character names and count transitions with the synthetic API browser check.
- [x] 2.2 Add the bilingual keys, CSS and front-end documentation for the chip presentation.

## 3. Verification and handoff

- [ ] 3.1 Run pytest, JavaScript and translation checks, the README synthetic Chromium regression (including machine-identity column assertions across ~861–1012 CSS px containers, expanded 1156/1200, collapsed 986/1024, 320px cards, and 1440px table in both navigation states and languages, without skipping `.row-open`), replay the AN-140 synthetic fixtures, run OpenSpec 1.14.2 strict validation and diff checks, and record commands, outputs, commits, screenshots and limits in [`verification.md`](verification.md).
- [x] 3.2 Preserve the independent findings and evidence from [AN-134](review-an-134.md), [AN-137](review-an-137.md), and [AN-140](review-an-140.md).
- [ ] 3.3 Record the AN-143 independent re-review of AN-144 against the reviewed SHA, diff, AN-140 reproduction and evidence. Prior independent findings are linked in [`review-an-134.md`](review-an-134.md), [`review-an-137.md`](review-an-137.md), and [`review-an-140.md`](review-an-140.md).
- [ ] 3.4 Mika integrates the reviewed result and records the verified remote SHA.

## Workflow follow-up

- Sync the applicable spec and archive only after implementation, verification and independent review pass; the review and integration tasks stay unchecked in this handoff.
