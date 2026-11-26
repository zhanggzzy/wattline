## ADDED Requirements

### Requirement: Evidence-based machine view

The dashboard SHALL project verified same-machine sources as one machine and attach container identifiers or registered source labels. Original endpoint settings, links, identity validation and individually scoped removal SHALL remain available.

#### Scenario: Host and two containers share one verified boot
- **WHEN** Linux observations from the host and both containers pass their pinned identities and report the same kernel boot
- **THEN** navigation and machine details lead to one machine, and its container identifiers or source labels and settings are available on that machine

#### Scenario: Insufficient evidence or a changed boot
- **WHEN** names or addresses match, or sources report different or unknown boot identities
- **THEN** each independently registered source remains separately visible until a shared machine is verified

#### Scenario: A known source becomes unreachable
- **WHEN** a previously matched source fails or the workbench restarts without new samples
- **THEN** the last confirmed match still applies and only fresh readings contribute to current values
