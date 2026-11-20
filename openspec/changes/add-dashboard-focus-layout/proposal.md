# Proposal

## Why

AN-48 / AN-50: operators need room to compare resource trends and inspect GPU workloads without losing machine context. The current detail page splits trends and physical GPUs into columns, shows only one metric, and uses inline GPU details.

## What Changes

- Add a reversible, accessible status-only navigation rail, including narrow screens.
- Give detail trends a full row and a page focus mode with any nonempty selection of supported metrics stacked vertically. Accept the explicit 24-hour power + GPU utilization example; preserve time ranges and a clear return action.
- Combine hardware/GPU summaries and current processes in a table with a native GPU detail dialog. Preserve CPU/memory cards, CPU count/load and system facts, raw GPU evidence and process ownership semantics.
- Verify desktop/narrow layout, keyboard interaction, empty/offline/multiple GPUs, bilingual labels and chart resizing using synthetic APIs. Check actual Modern Web Guidance sources and document evidence.

## Capabilities

### New Capabilities

- `dashboard-focus-layout`: navigation density, focused metric comparison and integrated hardware/process inspection.

### Modified Capabilities

None. Existing localization and memory contracts remain in force.

## Impact

Native static HTML/CSS/JS, centralized locale resources and isolated browser checks. No business API, collector, persistence schema or runtime dependency changes. Modern browser support stays as documented in README. No user instance access or deployment. Independent review, main integration and spec archival remain pending for the assigned owners.
