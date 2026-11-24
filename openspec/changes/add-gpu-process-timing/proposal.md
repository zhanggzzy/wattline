# Proposal

## Why

AN-73 requests the start time and time already spent running for each current GPU process. The hardware list and GPU details currently show PID, account, ownership and memory, so operators cannot tell when a workload began or how long it had been running at collection.

## What Changes

- Show a localized start date and time and the elapsed runtime at sampling for every visible process in the machine hardware list and GPU details.
- Derive both values from a verified process start and the monitored endpoint's time at the beginning of GPU process collection. Keep the timing values together and display “Unknown” for both when they are unavailable.
- Preserve existing records and ownership rules for container endpoints, unverifiable processes, and snapshots that predate the new fields.

## Capabilities

### New Capabilities

### Modified Capabilities

- `dashboard-focus-layout` adds current GPU process timing to integrated hardware and process inspection.

## Impact

The Linux probe and current snapshot API gain optional per-process timing fields. Current process rendering and Chinese and English resources consume them. Existing configurations and history require no migration. Acceptance covers trusted host values, identity races, incomplete or legacy data, both languages, and narrow-screen access using synthetic data.
