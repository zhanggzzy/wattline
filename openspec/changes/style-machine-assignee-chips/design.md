# Design

## Context

See proposal.md — Why. `monitor.js` renders the machine table and the native assignee `<dialog>` from the snapshot's `people` and each machine's `assigned_users`. The narrow table reflows at a 620px container query into labelled cards. The existing API and SQLite layout already satisfy the data contract.

## Goals / Non-Goals

**Goals:**

- Present assignees without changing the snapshot or assignment contract.
- Keep native checkbox, label and keyboard behavior while the visible control is a pill-shaped chip.
- Keep long and untrusted names inside the cell and dialog at desktop and narrow widths.

**Non-Goals:**

- Changing API fields, validation, directory rules, persistence or schema.
- Adding client-side frameworks, icon fonts or new runtime dependencies.
- Redesigning the detail summary or the people-directory dialog.

## Decisions

- Render list assignees inside a dedicated `<td data-label="使用者">` right after Status. A wrapping `<ul>` of read-only chips preserves a list structure; an empty list yields a localized muted text node. Remove `assigneeSummary` from the identity cell but keep it on the detail page. Searching and status filtering keep their current semantics.
- In the picker, keep a real `<input type="checkbox">` inside each `<label>` chip and stretch the input over the chip with zero opacity, so pointer clicks, Space, focus, accessible naming and disabled state remain native. The check/plus glyph lives in an `aria-hidden` span and is drawn with CSS generated content, so it cannot enter the accessible name. Focus is shown on the label with `:has(input:focus-visible)`; the chip's `min-height` and padding provide a hit target of at least 44×44 CSS px.
- Keep selection state in the checked inputs, as today. A single `updateAssigneeCount()` derives the count from checked inputs and runs after rendering, on `change`, and after clear. Re-rendering options after directory changes recomputes both the chip list and count from the same selected IDs.
- Add three translated keys: `unassigned`, `choose_from_people_directory`, and `selected_people_count`. Use `role="status"` on the count for polite announcement.
- Extend the existing synthetic Chromium check rather than adding a second harness. Header order, empty values, literal names, long names, 320px cards, count transitions, pointer/Space toggling, focus and 44px targets are asserted against the real page JavaScript and in-process API.

## Risks / Trade-offs

- Chips are taller than the previous checkbox rows, so a large directory scrolls inside the existing 35dvh options region. That is preferable to shrinking targets below 44px.
- The table gains a column and increases its minimum width; between the existing 620px card breakpoint and the table minimum, the existing horizontal scroll remains the fallback.
- A transparent stretched checkbox relies on the label/hit-area pattern; the accessible name remains the name text because the decorative mark is hidden from assistive technology.
