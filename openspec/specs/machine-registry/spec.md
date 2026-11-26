# machine-registry Specification

## Purpose

Records durable operator-supplied registration metadata for each monitored machine so the workbench can show who is currently responsible for an environment without confusing it with collected process ownership.

## Requirements

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

### Requirement: Assigned user input constraints

Person names SHALL be non-empty single-line text, trimmed to at most 80 characters. ASCII and C1 controls and Unicode line or paragraph separators SHALL be rejected before trimming. Assignment requests SHALL reference distinct existing directory IDs, or an empty list to clear. Invalid requests SHALL preserve saved data.

#### Scenario: Invalid assignment rejected
- **WHEN** a request supplies an unknown or duplicate directory ID
- **THEN** the request is rejected and the previous assignments remain saved

#### Scenario: Invalid assignment entered or pasted into machine settings
- **WHEN** a name contains a control character or line separator at any position, consists only of whitespace, or exceeds 80 characters after trimming
- **THEN** the directory shows a failure, keeps the draft available for correction, and leaves the saved name and associations intact

#### Scenario: Ordinary whitespace still trims
- **WHEN** a directory request supplies a name padded with ordinary spaces around legal text
- **THEN** the stored name is the trimmed legal text

### Requirement: Persistent and machine-isolated assignment

Assignments SHALL persist under stable machine identity and be independently editable from general configuration. A failed write SHALL preserve the previous stored and visible state. Removing a machine SHALL clear its associations and retain shared people and other machines' associations.

#### Scenario: Restart and isolation
- **WHEN** two machines have assignments and the service restarts
- **THEN** each machine reports its own saved list and changing one preserves the other

#### Scenario: Save failure
- **WHEN** persisting an assignment fails
- **THEN** the API reports failure, the editor preserves the draft, and the machine retains its last saved list

#### Scenario: Existing stored settings
- **WHEN** Wattline opens settings persisted before assignment support
- **THEN** the machine loads normally with an empty assignment list

#### Scenario: General settings save
- **WHEN** an operator saves a machine's configuration
- **THEN** its separately edited assignee list stays saved

#### Scenario: Remove and re-enroll a machine
- **WHEN** a machine is removed and re-enrolled under the same stable identity
- **THEN** it starts with no assignees and the directory and other machines keep their records

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

### Requirement: Shared people directory

The dashboard SHALL let the operator add, rename, and delete people in a shared directory. An exact normalized name SHALL identify one directory entry. Renaming SHALL preserve the person's machine associations. A person associated with any machine SHALL be protected from deletion with an explanation to clear the associations first.

#### Scenario: Directory entry reused and renamed
- **WHEN** the same person is selected for two machines and then renamed
- **THEN** both machines show the new name and keep their associations

#### Scenario: Duplicate name and deletion of a linked person
- **WHEN** the operator tries to create or rename to an existing name, or delete a linked person
- **THEN** the operation fails with an explanation and existing names and associations are preserved

#### Scenario: Delete an unused person
- **WHEN** the operator removes a person who has no associations
- **THEN** the person disappears from the directory and from machine selection options

### Requirement: Upgrade single-person registration

Upgrade SHALL import each non-empty saved `assigned_user` into the directory and associate it with its original machine identity. Exact normalized names SHALL share one directory record. Import SHALL be atomic and repeated startups SHALL neither duplicate entries nor restore cleared associations. Older rows without a value SHALL load with an empty assignment list.

#### Scenario: Existing machine after upgrade
- **WHEN** a pre-upgrade database has same-name assignments on multiple machines and older rows with missing, null or blank values
- **THEN** the matching machines share a directory entry and the other machines remain unassigned

#### Scenario: Migration failure and retry
- **WHEN** upgrade fails after writing part of the migration and the operator starts the service again after the cause is fixed
- **THEN** the failed migration leaves the prior assignments intact and the retry imports each legacy assignment once

### Requirement: Target operating system of SSH registration

The enrollment UI, API, and machine configuration SHALL support Linux and Windows SSH targets. Omitted OS values SHALL resolve to Linux for existing configuration and stored registration. The selected OS SHALL survive reload and appear in the snapshot. Windows enrollment SHALL require public-key login, strict known-host verification, a stable machine identity and an ED25519 host key pinned for future sampling.

#### Scenario: Registration and reload
- **WHEN** an operator enrolls a verified Windows SSH target and restarts Wattline
- **THEN** the reloaded registration uses the Windows probe and the original pinned identity and key

#### Scenario: Identity collision or change
- **WHEN** two aliases identify the same machine and key, or a sampled identity or key differs from the enrolled evidence
- **THEN** duplicate enrollment or the mismatched sample is rejected, preserving existing history

### Requirement: Computing resource classification

The registry SHALL support explicit CPU and GPU classifications. Existing machines SHALL retain IDs and settings. Classification without explicit selection SHALL use positive observations or explicit CPU configuration, with unconfirmed displayed for insufficient evidence.

#### Scenario: Distinguish device details and legacy inventory
- **WHEN** a CPU machine and an existing machine with incomplete GPU inventory are shown
- **THEN** CPU details prioritize CPU and memory with no GPU section, while the existing machine does not become CPU solely because GPU readings are missing.

### Requirement: Shared resource assignment

The dashboard SHALL offer a single directory person, Shared or unset for new operator assignments. Existing multiple-assignee records SHALL stay visible and survive unrelated updates. Existing person_ids clients SHALL remain compatible.

#### Scenario: Switch a legacy assignment explicitly
- **WHEN** an operator saves Shared for a previously multi-assigned resource
- **THEN** its assignment becomes Shared and future reloads show Shared.

### Requirement: Unified machine detail configuration

Machine details SHALL expose a single configuration entry for editable attributes, monitoring, room placement and assignment. Removal SHALL retain explicit confirmation and existing access checks.

#### Scenario: Open an offline machine
- **WHEN** an operator opens Configure on an offline machine
- **THEN** properties and assignment are reachable and the removal action opens a separate confirmation before any delete request
