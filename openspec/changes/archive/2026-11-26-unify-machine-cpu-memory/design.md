# Design

## Context

The machine roster already resolves verified links. The snapshot currently projects a single observation and the group machine summary reuses its host-only totals. Group history already reads the latest tick per source per five-minute bucket. Recent and cold machine charts currently request an explicit scope tied to the current sample.

## Goals

- Use the roster's stable source order for ties. Select among current samples and historical ticks by each metric's validity, observed scope, and timestamp.
- Keep each metric's measurement and provenance together, including CPU weight, memory capacity, and load or cache semantics in the detail view.

## Decisions

- Add selected CPU and memory fields to the machine snapshot alongside the existing source-level metrics. Select by valid measurement first, then host, then recency. This keeps the original observation available for scoped summaries, GPU inventory and system facts. For weighted CPU coverage a selected reading also needs its own positive capacity. Legacy standalone percentages remain readable when used bytes were absent.
- Reuse the same selection for group history and machine history. Unified history considers the latest observation per source per bucket and preserves discontinuities on source or observation identity changes. Group memory usage and percent use separate coverage, each derived from the chosen memory observation.
- Recent and cold detail charts can request `view=machine`. Requests with a `source` or `scope` use the existing path. The overview's unscoped per-machine CPU and memory series use the unified reading while preserving the aligned response shape. Chart labels in the machine view use the metric or group name, and source details provide endpoint identifiers.

## Risks / Trade-offs

- A machine's chart can switch measurement scope as sources become available. Machine detail history breaks the line on source changes, and no group statistic borrows capacity from another source.
- Memory with measured usage and missing capacity participates in used-memory summaries. Percent remains based on paired readings, with its own coverage.

## Migration Plan

The projection is computed on read from the existing snapshots, sample database and gzip archives. The change requires no data migration.
