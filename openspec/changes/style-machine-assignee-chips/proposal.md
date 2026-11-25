# Proposal

## Why

AN-102 feedback (comment 01a211c9-15c0-7134-96aa-02a99e73e213) rejects the checkbox multi-select as visually dated and asks for tag-like assignee chips plus a dedicated assignee column beside Status in the machine list. The user approved the two AN-102 mockups in comment 01a211cb-89ed-7ef9-b783-2be25b96aed8 and authorized development in comment 01a211cd-1958-7bf8-ad8f-01040a68abde.

AN-137 found that real metric strings still push the table beyond its container near the layout switch, and the different spaces in two names can disappear visually when both names break at the space.

## What Changes

- Put a read-only **使用者 / Assignees** column immediately after Status in the ordinary machine list. Show one light chip per person, wrapping for multiple people, and the localized **未登记 / Not assigned** when empty. Remove the repeated assignee summary under the machine name in list rows; keep the detail-page summary and the existing editor entry beside Configure.
- Preserve consecutive internal spaces in list and picker chip names, so directory records such as `Ada Lovelace` and `Ada  Lovelace` stay visually distinguishable on the same line and after wrapping. Long names still wrap without widening or truncating the column.
- Fit all seven columns within the list container or show labelled cards. Verify the English review fixture at 1156 CSS px with expanded navigation and at 986 and 1024 CSS px with collapsed navigation. Check both languages and navigation states on either side of the layout switch and through repeated resizing with long machine names, multiple assignees and large resource values.
- Replace the checkbox list in the assignee dialog with clickable full-name chips. Selected chips use a light blue fill and check mark; unselected chips use an outline and plus sign. Show the selected count, refreshed on initial render, mouse or Space toggling, clear, and directory updates.
- Keep native checkbox and label semantics, a visible keyboard focus ring, at least 44×44 CSS px hit targets, and an accessible name that is exactly the person's name. Keep the people directory, clear, cancel, save, failure draft and disabled states.
- Preserve the snapshot fields, `PUT /api/machines/{id}/assignees`, people directory API, persistence, validation, permissions and SQLite schema. No migration.
- Extend the synthetic Chromium regression for column order, empty values, literal names including consecutive spaces, long names, 320–1440px layouts, the card switch boundary, picker counts, mouse and keyboard selection, save and cancel.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `machine-registry`: assignee presentation in the machine list and the chip-based multi-select editor.

## Impact

Only the dashboard HTML, CSS, JavaScript, translations, browser regression and front-end documentation change. API, configuration, database, history archives and deployment stay compatible. AN-135 delivered the initial implementation, AN-138 addressed the first review, and AN-141 addresses the remaining findings from AN-137. AN-140 independently re-reviews AN-141 before Mika integrates the change.
