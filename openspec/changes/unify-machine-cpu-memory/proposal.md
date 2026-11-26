# Proposal

## Why

The AN-226 acceptance feedback in AN-232 identified host-specific labels and missing CPU or memory values on machine-based group views even when a container observation was available.

## What Changes

- Use CPU and 内存 / Memory in room and cluster tables and summary cards, with neutral labels in machine views and unified charts.
- Select CPU and memory independently per machine. Prefer a valid host reading, then a valid container reading. Retain zero, missing values, and memory usage without a comparable capacity.
- Use the same source selection rules in current summaries and machine-based history. Test the localized pages and chart data with synthetic sources that include overlap and gaps.

## Capabilities

### New Capabilities

### Modified Capabilities

- `overview` — per-metric machine selection, group aggregation and history labels.
- `dashboard-memory-metrics` — same-source capacity, measured usage and coverage.
- `machine-archive-analysis` — per-metric selection in the machine-wide view of archived observations.

## Impact

Machine snapshots add CPU and memory readings for presentation. Group machine summaries and charts gain container fallback. The overview history response keeps its structure, and machine recent and archive history offer a machine view alongside existing source and scope queries. The existing SQLite schema and gzip format support all paths.
