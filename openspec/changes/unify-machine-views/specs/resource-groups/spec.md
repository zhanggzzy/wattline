## ADDED Requirements

### Requirement: Machine membership projection

Group views SHALL list a machine once when any of its sources belongs to the group. Cluster memberships SHALL include source memberships and a machine SHALL have one displayed room. Existing source placement SHALL remain accessible.

#### Scenario: Several sources share the same cluster
- **WHEN** two linked sources are assigned to a cluster or conflicting rooms
- **THEN** the cluster lists and counts one machine, the machine appears in its effective room, and detail links resolve to the machine
