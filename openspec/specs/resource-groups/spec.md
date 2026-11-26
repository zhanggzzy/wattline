# resource-groups Specification

## Purpose

Organize computing and storage resources by physical room and logical cluster.

## Requirements

### Requirement: Room and cluster memberships

A resource SHALL have at most one room and SHALL be eligible for multiple clusters. Rooms SHALL support one optional owner and a location. Clusters SHALL support one directory user, Shared or unset. Operators SHALL be able to create, edit and delete these groups.

#### Scenario: Remove a populated group
- **WHEN** an operator confirms deletion after reviewing the affected resources
- **THEN** only the group and its links are removed, devices and history remain, and directory references prevent deletion while in use.

### Requirement: Cross-group navigation

A room SHALL list all its resources and their intersecting clusters. A cluster SHALL list all members across rooms and show how many are in each room or have no room.

#### Scenario: Open a cross-room cluster
- **WHEN** an operator follows a cluster from one room
- **THEN** the cluster shows all members and links back to each associated room, and device links lead to canonical detail.

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

### Requirement: Machine membership projection

Group views SHALL list a machine once when any of its sources belongs to the group. Cluster memberships SHALL include source memberships and a machine SHALL have one displayed room. Existing source placement SHALL remain accessible.

#### Scenario: Several sources share the same cluster
- **WHEN** two linked sources are assigned to a cluster or conflicting rooms
- **THEN** the cluster lists and counts one machine, the machine appears in its effective room, and detail links resolve to the machine
