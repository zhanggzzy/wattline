# Proposal

## Why

AN-226 asks Wattline to present physical machines as the units of monitoring. Separate SSH registrations can observe one machine through its host and through containers, producing extra rows and inconsistent totals.

## What Changes

- Use verified Linux boot identity to associate monitoring sources and present one machine in the overview, navigation, groups and trends. Keep sources with insufficient evidence separate.
- Show monitored container endpoints on their machine and keep per-source settings and history reachable.
- Prefer fresh host observations for machine readings. Label container readings and limit group CPU and memory statistics to verified host observations. Deduplicate GPU readings by device UUID.

## Capabilities

### New Capabilities

### Modified Capabilities

- `machine-registry` associates registrations into a machine view while retaining their settings and identity checks.
- `overview` uses machine-based roster, statistics and trends.
- `resource-groups` presents one machine per group and retains existing source associations.
- `dashboard-memory-metrics` distinguishes group host capacity from the container memory readings shown in machine details.
- `machine-archive-analysis` resolves the same selected machine and retains access to each registered source archive.

## Impact

Registration, registry and history keys remain valid. SQLite retains source observation metadata across restarts and existing gzip archives remain readable. The dashboard uses the machine projection and keeps existing settings and detail routes available. Synthetic checks cover hosts and containers on the same machine, separate and unverified sources, partial failure, and recent and cold history.
