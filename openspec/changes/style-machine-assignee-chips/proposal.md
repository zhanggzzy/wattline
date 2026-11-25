# Proposal

## Why

AN-102 feedback (comment 01a211c9-15c0-7134-96aa-02a99e73e213) rejects the checkbox multi-select as visually dated and asks for tag-like assignee chips plus a dedicated assignee column beside Status in the machine list. The user approved the two AN-102 mockups in comment 01a211cb-89ed-7ef9-b783-2be25b96aed8 and authorized development in comment 01a211cd-1958-7bf8-ad8f-01040a68abde.

AN-137 found that real metric strings still push the table beyond its container near the layout switch, and the different spaces in two names can disappear visually when both names break at the space.

AN-140 verified those two fixes, then found a regression from the fixed 24% first-column proportion: between roughly 861 and 1012 CSS px of list-container width (including expanded navigation at 1156/1200 CSS px and collapsed navigation at 986/1024 CSS px), `.row-open` kept its intrinsic button width (~196 px with a 170 px text cap) and extended past the first column under the adjacent Status badge. In AN-102 comment 01a21211-5092-7dc6-865b-c938d89bfa39 the user authorized a focused supplemental fix (AN-144) limited to keeping long machine names, addresses, and SSH aliases inside the machine column.

## What Changes

- Put a read-only **使用者 / Assignees** column immediately after Status in the ordinary machine list. Show one light chip per person, wrapping for multiple people, and the localized **未登记 / Not assigned** when empty. Remove the repeated assignee summary under the machine name in list rows; keep the detail-page summary and the existing editor entry beside Configure.
- Preserve consecutive internal spaces in list and picker chip names, so directory records such as `Ada Lovelace` and `Ada  Lovelace` stay visually distinguishable on the same line and after wrapping. Long names still wrap without widening or truncating the column.
- Fit all seven columns within the list container or show labelled cards. In table mode, keep the machine-identity button and its long machine name, address, SSH alias, and container-scope text within the first column using in-column ellipsis truncation without overlapping the adjacent Status badge, while keeping the full accessible name, navigation, drag-to-reorder, keyboard focus, and narrow-card wrapping. Verify the English review fixture at 1156 and 1200 CSS px with expanded navigation and at 986 and 1024 CSS px with collapsed navigation, across critical container widths (~861–1012 CSS px), both languages and navigation states on either side of the layout switch and through repeated resizing with long machine names, long addresses/aliases, multiple assignees and large resource values.
- Replace the checkbox list in the assignee dialog with clickable full-name chips. Selected chips use a light blue fill and check mark; unselected chips use an outline and plus sign. Show the selected count, refreshed on initial render, mouse or Space toggling, clear, and directory updates.
- Keep native checkbox and label semantics, a visible keyboard focus ring, at least 44×44 CSS px hit targets, and an accessible name that is exactly the person's name. Keep the people directory, clear, cancel, save, failure draft and disabled states.
- Preserve the snapshot fields, `PUT /api/machines/{id}/assignees`, people directory API, persistence, validation, permissions and SQLite schema. No migration.
- Extend the synthetic Chromium regression for column order, empty values, literal names including consecutive spaces, long names, machine-identity column containment and ellipsis without skipping the first column, 320–1440px layouts, the card switch boundary, picker counts, mouse and keyboard selection, save and cancel.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `machine-registry`: assignee presentation in the machine list and the chip-based multi-select editor.

## Impact

Only the dashboard HTML, CSS, JavaScript, translations, browser regression and front-end documentation change. API, configuration, database, history archives and deployment stay compatible. AN-135 delivered the initial implementation, AN-138 addressed the first review, AN-141 addressed AN-137, and AN-144 addresses the first-column overflow reported in AN-140. AN-143 independently re-reviews AN-144 before Mika integrates the change.
