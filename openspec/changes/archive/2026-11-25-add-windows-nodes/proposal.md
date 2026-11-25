# Proposal

## Why

AN-128 implements the Windows monitoring approved in AN-126. The current SSH probe requires Linux facilities, and rendering every visible GPU process would crowd the Windows machine view.

## What Changes

- Select Linux or Windows when enrolling an SSH target. Existing registrations and configuration default to Linux.
- Collect Windows machine identity, CPU, memory, system volume, uptime and available NVIDIA measurements through a non-interactive PowerShell probe. Reuse history, with GPU series keyed by UUID.
- Show up to five observed processes per Windows GPU with an omitted count in both views. Preserve all observed records and treat unverified coverage or fields as unknown.

## Capabilities

### New Capabilities

- `windows-node-monitoring` provides SSH-based Windows sampling and history.

### Modified Capabilities

- `machine-registry` persists and exposes target OS.
- `dashboard-focus-layout` limits visible Windows GPU rows and preserves evidence semantics.

## Impact

Registration, collection, snapshot and dashboard gain Windows support. The service continues to run on its existing supported platforms. Linux behavior, stored records and history schema are compatible. Acceptance requires Linux regressions, synthetic Windows failure and browser coverage, and a read-only target check with any limits recorded.
