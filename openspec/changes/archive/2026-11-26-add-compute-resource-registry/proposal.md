## Why

AN-164 phase 1 implements the resource and alert foundations approved in AN-154 v0.2. Wattline needs CPU-focused and shared-storage records alongside GPU machines and an auditable in-app alert lifecycle.

## What Changes

- Register CPU and GPU SSH machines, NAS and shared storage clusters. Show metrics and detail appropriate to each type.
- Use the directory for an individual user, Shared or an unset assignment. Keep old multi-person assignments readable and keep the existing machine endpoint compatible.
- Store alert occurrence, latest evidence, recovery and administrative closure. The overview and alert center show persisted events.
- Accept with synthetic CPU/GPU and read-only storage fixtures, migration and restart checks, and the browser flows for registration and alert navigation. Vendor adapters, SSH multiplexing and Feishu have separate scope.

## Capabilities

### New Capabilities

- `storage-resources`: Storage inventory and optional read-only observations.
- `in-app-alerts`: Persistent resource alert lifecycle and navigation.

### Modified Capabilities

- `machine-registry`: CPU/GPU type and shared user mode compatible with legacy entries.

## Impact

Adds SQLite tables and additive fields and endpoints. Existing machine IDs, host bindings, GPU evidence, history and person IDs continue to apply. Existing configuration remains valid. A consistent pre-upgrade data backup supports rollback to an older binary.
