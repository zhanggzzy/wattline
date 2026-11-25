# windows-node-monitoring Specification

## Purpose

Allows Wattline to monitor native Windows endpoints through SSH and query their machine and NVIDIA GPU history from the existing dashboard.

## Requirements

### Requirement: Windows SSH sampling

Wattline SHALL verify stable Windows machine and boot identities over non-interactive SSH. It SHALL read CPU utilization and logical processor count, memory, the volume containing the operating system, and uptime when enabled and available. Windows CPU SHALL use the endpoint's formatted processor samples, including after a restart, and SHALL be unknown when coverage of active logical processors cannot be established. Windows load average SHALL be unavailable.

#### Scenario: Continuous and post-restart sampling
- **WHEN** identities and enabled counters are readable before and after a reboot
- **THEN** host history stays with the same machine, CPU uses the current Windows measurement and uptime reflects the new boot

#### Scenario: Incomplete processor coverage
- **WHEN** the Windows counter provider does not account for every reported logical processor
- **THEN** CPU utilization is unknown and other available measurements remain usable

### Requirement: Windows NVIDIA evidence

Wattline SHALL record supported NVIDIA measurements by GPU UUID, preserve every valid observed process record and represent unavailable fields as unknown. Unverified enumeration SHALL remain partial, with observed processes establishing occupancy and an empty partial list leaving occupancy unknown. An unavailable probe SHALL leave inventory unverified.

#### Scenario: WDDM provides only partial records
- **WHEN** Windows reports some PIDs without per-process VRAM or account information
- **THEN** GPU status indicates occupancy and the snapshot retains all observed records with only the available fields

#### Scenario: Empty or unavailable inventory
- **WHEN** the probe explicitly confirms zero visible GPUs or fails to verify inventory
- **THEN** the former reports an empty inventory and the latter reports incomplete inventory without asserting idle devices
