# Machine registry delta

## MODIFIED Requirements

### Requirement: Optional assigned user per machine

A registered machine SHALL support zero or more distinct people from the shared directory. Its detail view SHALL expose an assignee editor beside Configure. The editor SHALL present every directory person as a multi-select chip that keeps a native checkbox and label, shows selected and unselected states, reports the current selected count, and supports selecting, deselecting and clearing people, saving the selection, cancelling edits, and reaching directory maintenance. The selected count SHALL reflect the initial selection, mouse or Space-key changes, clearing, and directory additions, renames or removals. Decorative marks SHALL NOT change a checkbox's accessible name. Each chip SHALL expose a visible keyboard focus indicator and at least a 44×44 CSS px hit target. The editor SHALL work regardless of collection status.

#### Scenario: Record and clear a value
- **WHEN** an operator selects several directory entries, saves, removes one and later saves an empty selection
- **THEN** each save reports the current set of distinct people for that machine

#### Scenario: Existing machine after upgrade
- **WHEN** a machine has no assignment and the operator opens its assignee editor
- **THEN** no people are selected and the reported count is zero until the operator makes a selection

#### Scenario: Selection count and controls
- **WHEN** the operator opens the editor, toggles a chip with a pointer or Space, clears the selection, or changes the directory while the editor stays open
- **THEN** the selected count matches the checked people and each chip keeps its native checkbox semantics, accessible name, focus ring and hit target

#### Scenario: Unavailable machine
- **WHEN** the machine is offline or monitoring is disabled
- **THEN** the operator can still save or clear its assignees

#### Scenario: Cancel selection changes
- **WHEN** the operator changes the draft selection and cancels
- **THEN** the previous selection remains saved and visible

### Requirement: Assignment is displayed as advisory metadata

The ordinary expanded machine list SHALL show assigned people in a dedicated column immediately after Status, and machine details SHALL show all assigned names without hover, including at narrow widths. Each list entry SHALL appear as a light read-only chip containing the full name; multiple people SHALL wrap within the cell, and an empty assignment SHALL show a localized **未登记 / Not assigned** value. The list SHALL NOT repeat the assignee summary below the machine name. Narrow containers SHALL render the column as a labelled card without horizontal overflow or truncated names. Names SHALL render as literal text. GPU process accounts, process ownership evidence, and SSH login SHALL continue to reflect their existing sources.

#### Scenario: Assigned machine displayed
- **WHEN** an operator views the machine list or details for a machine with multiple assignees including a long name
- **THEN** the column or summary shows the full names, wraps them within the available space, and remains inside the viewport

#### Scenario: Empty assignment
- **WHEN** a machine has no assigned people
- **THEN** its list cell shows the localized unassigned value and no chips

#### Scenario: List column placement
- **WHEN** the operator views the machine list or changes the dashboard language
- **THEN** the assignee column is immediately after Status and the previous duplicate summary under the machine name is absent

#### Scenario: Narrow card
- **WHEN** the machine table reflows to cards in a narrow container
- **THEN** the assignee cell shows its localized field label, wraps every chip, and does not cause horizontal overflow

#### Scenario: Untrusted text
- **WHEN** an assigned name contains markup characters
- **THEN** the dashboard displays the literal text without creating elements or executing content
