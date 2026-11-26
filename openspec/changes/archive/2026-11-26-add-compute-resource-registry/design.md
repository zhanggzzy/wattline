## Context

AN-154 v0.2 pages 4–8 and the AN-162 component handoff cover type, migration, storage and alert behavior. Existing SSH registration validates a fixed host identity. History uses a stable history key while the dashboard uses public resource IDs.

## Goals / Non-Goals

Use the existing local SQLite and access protections. Provide a pluggable read-only adapter contract and synthetic acceptance. Real vendor protocols, SSH reuse and Feishu are separate work.

## Decisions

- Keep compute registration and history keys intact. Add an optional hardware-kind override and infer legacy hardware from trusted inventory or explicit CPU configuration. Reuse the people directory. Old assignee arrays retain write semantics through the legacy endpoint.
- Store storage records alongside compute metadata but outside the SSH registry, with a shared API view shape where useful. Inject registered adapters into the monitor. Only test fixtures supply a synthetic adapter. Store bounded time-series samples separately from existing archive tables.
- Use the same SQLite write boundary for alert and observation transitions. A unique active row per resource and rule prevents duplicate events across retries and restarts. Administrative closure is distinct from verified recovery. Keep ended events for 90 days and retain active alerts.
- Reuse the dashboard navigation and forms, GPU views and chart primitives. Add a persisted event center and a storage-specific detail view.

## Risks / Trade-offs

Incomplete observations can coexist with multiple active rules. Rule-specific evidence governs recovery. Legacy classifications remain conservative until verified.

## Migration Plan

Add idempotent schema setup. Existing identifiers and directory references are reused directly. Restore a consistent pre-upgrade data backup for rollback.
