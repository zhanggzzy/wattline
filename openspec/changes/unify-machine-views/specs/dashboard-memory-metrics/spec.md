## MODIFIED Requirements

### Requirement: Capacity and percentage by observation scope

Device and group views SHALL expose used bytes, comparable total bytes and percentage when measured. Group machine statistics SHALL use host observations and express coverage against the member machines. Container memory SHALL retain its measured scope in machine details and scope-specific API queries. Group percent SHALL divide summed used by summed total over the same valid pairs.

#### Scenario: Container with unbounded memory
- **WHEN** an observation has used memory but no limit
- **THEN** observed usage remains available, and no limit or ratio is fabricated or borrowed from the host.

#### Scenario: Host and container capacities are both available
- **WHEN** both views report memory for a verified machine
- **THEN** group memory totals count only the host capacity once and a container-only machine contributes no capacity to the group host total
