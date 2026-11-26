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
