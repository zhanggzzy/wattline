# Machine registry delta

## MODIFIED Requirements

### Requirement: Optional assigned user per machine

A registered machine SHALL support zero or more distinct people from the shared directory. Its detail view SHALL expose a multi-select assignee editor beside Configure regardless of collection status. The editor SHALL use native checkbox chips, report the current selection count, and support editing, saving, cancelling, clearing and directory maintenance.

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

### Requirement: Assignment is displayed as advisory metadata

The expanded machine list SHALL place assignees immediately after Status and show every assigned name as a read-only chip with localized labels. Machine details SHALL show every assigned name without hover. Narrow layouts SHALL keep assignees and every metric visible. Names SHALL render as literal text. GPU process accounts, process ownership evidence, and SSH login SHALL continue to reflect their existing sources.

#### Scenario: Assigned machine displayed
- **WHEN** an operator views the machine list or details for a machine with multiple assignees including a long name
- **THEN** the column shows each full name as a light read-only chip, while machine details show every full name without hover. The names wrap within their available space without widening the cell, truncating the names, or extending outside the viewport

#### Scenario: Empty assignment
- **WHEN** a machine has no assigned people
- **THEN** its list cell shows the localized unassigned value and no chips

#### Scenario: List column placement
- **WHEN** the operator views the machine list or changes the dashboard language
- **THEN** the assignee column is immediately after Status and the previous duplicate summary under the machine name is absent

#### Scenario: Narrow card
- **WHEN** the machine table reflows to cards in a narrow container
- **THEN** the assignee cell shows its localized field label, wraps every chip, and does not cause horizontal overflow

#### Scenario: Medium container without a fitting table
- **WHEN** the list container is narrower than the seven-column table's full width
- **THEN** the list renders labelled cards, keeps every metric field visible, and neither the list nor the page scrolls horizontally

#### Scenario: Resizing with large metric values
- **WHEN** window or navigation changes resize a list containing long machine names, multiple assignees, and large metric values across the layout boundary
- **THEN** the table or labelled cards keep every metric value and memory usage explanation visible, and neither the list nor the page scrolls horizontally

#### Scenario: Long machine name and address in table mode
- **WHEN** the list renders as a seven-column table in a tight container (around 861 to 1012 CSS px, including expanded 1156/1200 and collapsed 986/1024 CSS px) with a long machine name, address or SSH alias
- **THEN** the machine identity button and its name, address, SSH alias and scope text stay inside the machine column. Truncated text uses a visible in-column ellipsis, the adjacent status badge remains unobstructed, and the button retains its full accessible name and existing navigation, drag-to-reorder and keyboard behavior. Identity text continues to wrap in narrow cards

#### Scenario: Names differing by spacing
- **WHEN** an assigned name contains consecutive internal spaces, including at a width where the name wraps
- **THEN** its list chip keeps the literal text and renders the extra spacing, distinguishing it from a similarly named person

#### Scenario: Untrusted text
- **WHEN** an assigned name contains markup characters
- **THEN** the dashboard displays the literal text without creating elements or executing content
