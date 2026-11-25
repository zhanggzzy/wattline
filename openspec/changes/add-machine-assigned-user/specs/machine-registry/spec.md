# Spec Delta

## Purpose

Records durable operator-supplied registration metadata for each monitored machine so the workbench can show who is currently responsible for an environment without confusing it with collected process ownership.

## ADDED Requirements

### Requirement: Optional assigned user per machine

Each registered machine SHALL support one optional assigned-user text value. The operator SHALL be able to enter, replace, or clear it in the machine settings regardless of whether the machine is online, and a machine with no recorded value SHALL remain unregistered rather than showing a placeholder identity.

#### Scenario: Record and clear a value
- **WHEN** the operator saves a non-empty assigned-user value for a machine and later saves an empty value for the same machine
- **THEN** the machine first reports the saved value and then reports no assigned user

#### Scenario: Existing machine after upgrade
- **WHEN** a machine was registered before assigned users existed and the operator opens its settings
- **THEN** the field is empty and the machine reports no assigned user until one is saved

#### Scenario: Unavailable machine
- **WHEN** the machine is offline or monitoring is disabled
- **THEN** the operator can still save or clear its assigned user

### Requirement: Assigned user input constraints

The assigned-user value SHALL be trimmed single-line text within the existing machine-settings field limits. Empty input SHALL be stored as no assigned user. Values containing ASCII control characters, C1 control characters, Unicode line or paragraph separators, or exceeding the length limit SHALL be rejected without changing the stored value, including when such characters appear only at the start or end of the input or make up the whole input.

#### Scenario: Invalid assignment rejected
- **WHEN** a settings request supplies an over-length value or a value containing a control character or line/paragraph separator at any position, including a value made only of such characters
- **THEN** the request is rejected and the previously stored assignment remains unchanged

#### Scenario: Invalid assignment entered or pasted into machine settings
- **WHEN** the operator attempts to save a draft containing a control character or line/paragraph separator entered or pasted into the assigned-user field
- **THEN** the dialog shows the failure and keeps the draft available for correction, and the machine snapshot and stored assignment retain the previous value

#### Scenario: Ordinary whitespace still trims
- **WHEN** a settings request supplies a value padded with ordinary spaces around legal text
- **THEN** the stored assignment is the trimmed legal text

### Requirement: Persistent and machine-isolated assignment

The assigned user SHALL persist with the machine's existing settings under its stable machine identity. Saving or clearing one machine SHALL NOT change another machine's assignment, the value SHALL survive service restart, and a failed save SHALL NOT be reported as success or leave the in-memory view claiming the new value.

#### Scenario: Restart and isolation
- **WHEN** two machines have different assignments and the service restarts
- **THEN** each machine reports its own assignment and changing one leaves the other unchanged

#### Scenario: Save failure
- **WHEN** persisting a settings update fails
- **THEN** the API reports the failure and the machine keeps its previously stored assignment

#### Scenario: Existing stored settings
- **WHEN** the service reads settings written before this field existed
- **THEN** those machines load normally with no assigned user

### Requirement: Assignment is displayed as advisory metadata

The machine detail view and machine list SHALL show a recorded assigned user in the selected dashboard language, escaped as user text. The assignment SHALL remain distinct from GPU process accounts, process ownership evidence, and the SSH login user, which SHALL continue to come from their existing sources.

#### Scenario: Assigned machine displayed
- **WHEN** the operator views the machine list or opens a machine with a recorded assigned user
- **THEN** the recorded value appears with a localized user label while process accounts and SSH configuration are unchanged

#### Scenario: Untrusted text
- **WHEN** a recorded assigned-user value contains markup characters
- **THEN** the dashboard displays it as literal text without creating markup or executing content
