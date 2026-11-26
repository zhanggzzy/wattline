## ADDED Requirements

### Requirement: Unified configuration for rooms and clusters

Room and cluster details SHALL expose localized Configure controls for attributes, owner or user, cluster membership and the local Linux idle tolerance override. Their configuration SHALL show the level's value or inheritance state. Existing group deletion SHALL keep its member preview and explicit confirmation.

#### Scenario: View a room with inherited policy
- **WHEN** an operator views room configuration without a room override
- **THEN** the global effective value and its source are shown as the room baseline

#### Scenario: View a cluster spanning rooms
- **WHEN** an operator views cluster configuration with members in distinct rooms
- **THEN** each applicable member can show its own effective value and source, even if the cluster has no single inherited value

#### Scenario: Fail to save a group
- **WHEN** changing policy and group fields together fails
- **THEN** the saved policy, group attributes and membership all remain at their previous values
