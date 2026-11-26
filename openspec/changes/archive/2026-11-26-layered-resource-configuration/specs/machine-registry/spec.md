## MODIFIED Requirements

### Requirement: Optional assigned user per machine

A registered machine SHALL support zero or more distinct people from the shared directory. Its detail view SHALL expose the assignee editor in the Configure dialog regardless of collection status. The editor SHALL use native checkbox chips, report the current selection count, and support editing, saving, cancelling, clearing and directory maintenance.

#### Scenario: Record and clear a value
- **WHEN** an operator selects several directory entries, saves, removes one and later saves an empty selection
- **THEN** each save reports the current set of distinct people for that machine, and the editor also provides access to directory maintenance

#### Scenario: Existing machine after upgrade
- **WHEN** a machine has no assignment and the operator opens its assignee editor
- **THEN** no people are selected and the reported count is zero until the operator makes a selection

#### Scenario: Selection count and controls
- **WHEN** the operator opens the editor, toggles a chip with a pointer or Space, clears the selection, or changes the directory while the editor stays open
- **THEN** the count matches checked people, each native checkbox has its literal person name as its label, decorative marks do not affect its accessible name, selected states are visibly distinct, keyboard focus is visible, and the hit target is at least 44×44 CSS px

#### Scenario: Unavailable machine
- **WHEN** the machine is offline or monitoring is disabled
- **THEN** the operator can still save or clear its assignees

#### Scenario: Cancel selection changes
- **WHEN** the operator changes the draft selection and cancels
- **THEN** the previous selection remains saved and visible

#### Scenario: Names differing by spacing
- **WHEN** the directory contains names that are identical except for consecutive internal spaces, including at a width where the names wrap
- **THEN** each picker chip keeps its literal text and accessible name, and the wider spacing remains visible

## ADDED Requirements

### Requirement: Unified machine detail configuration

Machine details SHALL expose a single configuration entry for editable attributes, monitoring, room placement and assignment. Removal SHALL retain explicit confirmation and existing access checks.

#### Scenario: Open an offline machine
- **WHEN** an operator opens Configure on an offline machine
- **THEN** properties and assignment are reachable and the removal action opens a separate confirmation before any delete request
