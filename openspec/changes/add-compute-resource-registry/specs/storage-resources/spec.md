## Purpose

Register shared storage as a resource with auditable read-only observations.

## ADDED Requirements

### Requirement: Storage inventory and pending collection

Wattline SHALL register, edit, show and remove NAS and shared storage clusters with a stable resource ID, name and optional user assignment. Records without a configured adapter SHALL show pending collection and unknown readings.

#### Scenario: Register a NAS before integration
- **WHEN** an operator saves a NAS with no adapter
- **THEN** the NAS is visible in inventory and detail after restart, with pending collection and no fabricated zeros.

### Requirement: Read-only storage observations

The adapter contract SHALL report identity, scope, timestamp, logical capacity and health with optional throughput, pools and members. Capacity SHALL count a verified logical storage object once. Member capacity and duplicate representations SHALL NOT be added to the same total.

#### Scenario: Inspect a synthetic shared storage cluster
- **WHEN** a test adapter observes a logical pool also represented by its members
- **THEN** detail shows the pool capacity once, displays the member evidence separately and offers capacity and throughput history with gaps for missing observations.
