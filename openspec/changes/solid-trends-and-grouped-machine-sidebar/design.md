# Design

## Context

All trend entry points share a canvas renderer and legend swatch painter in `monitor.js`. Snapshot construction already projects a verified merged machine onto one displayed room and its sources' combined cluster memberships. The device table uses pointer and arrow-key handlers to persist the server order.

## Goals / Non-Goals

**Goals:** Reuse the chart, device navigation and ordering paths so chart surfaces, both sidebar densities and the device table agree.

**Non-Goals:** Change resource placement, history aggregation, APIs, collection or SQLite schema.

## Decisions

- Assign distinct colors to multi-series charts by stable identity within a chart family. Seed new series in identifier order and keep assignments during the dashboard session. Use a qualitative palette with additional hues once it is exhausted. Array position and translated labels can change when polling, changing metric or renaming a group, so they are unsuitable as identity.
- Render clusters in snapshot order and rooms as subheadings. Use the projected room and cluster IDs on the existing displayed device list, including any storage entries already accessible from the sidebar. A machine's own detailed configuration still shows its placement by source. Resolve group IDs against the current snapshot so a removed placement falls back cleanly.
- Use a native selector for the two modes. In compact mode its current choice is represented with an icon, while the selector keeps its full localized options and accessible name. Use the same reorder handle and persistence logic for the manual sidebar and the existing device table, with grouping limited to navigation. Keep the same machine button and identity in each group, qualified by its cluster and room.
- Keep mobile primary links and the manual list horizontally scrollable. Give the mobile cluster list a bounded vertical scroll area. Keep the compact rail vertically scrollable.

## Risks / Trade-offs

- Dense plots or similar hues can make individual data paths difficult to track. Keep the interactive group legend, readings and sample table available. A given session preserves existing color assignments when membership changes, so a new session with a different roster can assign different initial colors.
- Duplicating a machine across groups can complicate keyboard focus. Track the focused cluster occurrence and preserve it across refreshes when available. If it moves, use another occurrence of the same machine.
- Drag gestures on a narrow manual sidebar share space with horizontal scrolling. Limit pointer capture and touch-action changes to the reorder handle.

## Migration Plan

The selector reads a new, optional browser preference. Existing installations open in manual order. The current saved device order remains directly usable across a frontend rollback.
