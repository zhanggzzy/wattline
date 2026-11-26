## ADDED Requirements

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
