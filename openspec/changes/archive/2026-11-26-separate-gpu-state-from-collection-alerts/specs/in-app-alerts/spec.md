# Spec Delta

## MODIFIED Requirements

### Requirement: Persistent alert lifecycle

Wattline SHALL persist abnormal machine collection events and storage offline, stale, abnormal collection and explicit health events. At most one event per resource and rule SHALL be active. Events SHALL carry first and latest observation times and evidence, plus a recovery or administrative closure time where applicable.

#### Scenario: Sustained fault, restart and verified recovery
- **WHEN** the same rule triggers repeatedly, including after restart
- **THEN** the same event remains active until evidence confirms recovery, after which a new trigger starts another event.

#### Scenario: Insufficient data and intentional stop
- **WHEN** observations are missing or the device is stopped or removed
- **THEN** missing observations do not prove recovery, and intentional stop or removal closes affected active events without a recovery timestamp.

## ADDED Requirements

### Requirement: Machine collection issues and GPU occupancy

Wattline SHALL open a collection issue for machine sample failure, timeout or expiration of the most recent valid live sample. A new valid sample received within the machine's configured validity window SHALL resolve the collection issue. GPU occupancy SHALL be shown in the device status independently of sample validity.

#### Scenario: Valid sample with idle or unconfirmed GPU occupancy
- **WHEN** machine sampling succeeds and a GPU is idle or its occupancy is unconfirmed
- **THEN** the GPU device shows its occupancy status and no collection issue opens for that sample.

#### Scenario: Failed or timed out collection
- **WHEN** the sampler fails to obtain a valid sample or exceeds the sampling timeout
- **THEN** the collection issue records the failure or timeout evidence.

#### Scenario: Valid sample expires
- **WHEN** the most recent valid live sample reaches the machine's freshness limit
- **THEN** the collection issue records expiry as evidence.

#### Scenario: New valid sample recovers collection
- **WHEN** a newer valid sample arrives within its validity window during an active collection issue
- **THEN** the issue resolves even if GPU occupancy remains unconfirmed.

#### Scenario: Expired or superseded sample cannot prove recovery
- **WHEN** a sample arrives already past its freshness limit or is superseded by a newer stored sample
- **THEN** the older sample does not resolve the current collection issue.
