# in-app-alerts Specification

## Purpose

Store resource alert evidence for operators to locate devices and review incidents.

## Requirements

### Requirement: Persistent alert lifecycle

Wattline SHALL persist offline, stale and abnormal collection events and explicit storage health faults. At most one event per resource and rule SHALL be active. Events SHALL carry first and latest observation times and evidence, plus a recovery or administrative closure time where applicable.

#### Scenario: Sustained fault, restart and verified recovery
- **WHEN** the same rule triggers repeatedly, including after restart
- **THEN** the same event remains active until evidence confirms recovery, after which a new trigger starts another event.

#### Scenario: Insufficient data and intentional stop
- **WHEN** observations are missing or the device is stopped or removed
- **THEN** missing observations do not prove recovery, and intentional stop or removal closes affected active events without a recovery timestamp.

### Requirement: Alert overview and center

The overview SHALL summarize active stored events. The alert center SHALL filter and inspect stored lifecycle records with local timestamps, underlying evidence and navigation to available device details.

#### Scenario: Locate a device from persisted evidence
- **WHEN** an operator selects an alert
- **THEN** the event detail shows its lifecycle, last success when known and a link to the affected device if it still exists.
