## ADDED Requirements

### Requirement: Capacity and percentage by observation scope

Device and group views SHALL expose used bytes, comparable total bytes and percentage when measured. Group host and container observations SHALL be displayed separately. Group percent SHALL divide summed used by summed total over the same valid pairs.

#### Scenario: Container with unbounded memory
- **WHEN** an observation has used memory but no limit
- **THEN** observed usage remains available, and no limit or ratio is fabricated or borrowed from the host.
