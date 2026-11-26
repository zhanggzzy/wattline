# Spec Delta

## MODIFIED Requirements

### Requirement: Capacity and percentage by observation scope

Device and group views SHALL expose used bytes, comparable total bytes and percentage when measured. Each machine SHALL contribute one selected memory observation and coverage SHALL be measured against member machines. Group percent SHALL divide summed used by summed total over the same valid pairs. Scope-specific API queries SHALL retain their measured scope.

#### Scenario: Container with unbounded memory
- **WHEN** the selected observation has used memory but no limit
- **THEN** measured usage is shown and counts toward used-memory coverage. Capacity and percent remain missing and the observation contributes no pair to group percent coverage.

#### Scenario: Host and container capacities are both available
- **WHEN** both views report valid memory for a verified machine
- **THEN** the machine contributes only the host memory pair. For a machine with just valid container memory, its selected used and total bytes participate as a pair.
