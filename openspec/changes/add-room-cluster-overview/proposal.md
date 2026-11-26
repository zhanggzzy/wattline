## Why

AN-164 phase 2 adds physical room and logical cluster views so operators can read capacity and usage at useful scales and navigate to individual devices.

## What Changes

- Maintain rooms, directory-based owners, clusters, users and members. Derive cross-room and cross-cluster links from device membership.
- Show three persistent overview cards for online devices, visible GPUs and GPU power, followed by alerts. Under them provide Room, Cluster and Machine tabs with matching lists and 24-hour group trends on the first two tabs.
- Show current and rated GPU totals with independent coverage. Define rating by a verified GPU default power limit and retain storage observations in device and group views.
- Report capacity, coverage and container scope separately. Accept with cross-room and ungrouped fixtures, independent metric coverage, and narrow-screen and keyboard checks.

## Capabilities

### New Capabilities

- `resource-groups`: Room and cluster registry, memberships and details.

### Modified Capabilities

- `overview`: Grouped tabs and trends, while preserving existing history consumers.
- `dashboard-memory-metrics`: Used and total memory, percent and separate observation scopes.

## Impact

Requires phase 1 `add-compute-resource-registry`. Adds SQLite relations and API contracts for group summaries and history. Existing per-machine and overview history callers retain their existing responses. Rated GPU power adds live snapshot fields and uses the existing probe call and archive format.
