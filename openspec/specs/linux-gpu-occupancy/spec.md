# linux-gpu-occupancy Specification

## Purpose

Define how Wattline classifies a Linux host GPU as occupied, free or unknown from process
evidence, inventory completeness and a per-machine idle VRAM tolerance, so operators can
trust the resulting occupancy state and collection warning.

## Requirements

### Requirement: Configurable Linux idle memory tolerance

Wattline SHALL resolve the Linux host idle tolerance per card from machine, member cluster, room and global in descending order. The built-in global fallback SHALL be 256 MiB. The tolerance SHALL apply to used framebuffer memory per GPU.

#### Scenario: Existing configuration without the field

- **WHEN** a Linux machine omits a local tolerance and no higher-than-default value applies
- **THEN** the tolerance is 256 MiB and small residual VRAM does not by itself make an idle card unknown

#### Scenario: Explicit per-machine override

- **WHEN** a Linux machine explicitly sets zero or another non-negative value
- **THEN** it overrides cluster, room and global values

#### Scenario: Clear overrides successively

- **WHEN** machine, cluster, room and global overrides are removed in order
- **THEN** the effective threshold and reported source move through cluster, room, global and the built-in default

### Requirement: Edit the effective Linux GPU tolerance

Wattline SHALL show the local override or inherited state, effective per-card value and source in Machine details → Configure for Linux GPU hosts. It SHALL accept finite non-negative MiB, including zero, and clearing the override. The settings API SHALL report the effective value and source.

#### Scenario: Localized setting and saved readback

- **WHEN** an operator saves a tolerance or clears it in either language
- **THEN** the response and later reads show the effective value and source, and the next sample uses that policy without a restart

#### Scenario: Inapplicable device

- **WHEN** an operator opens settings for Windows, a known container endpoint, a CPU machine or storage
- **THEN** the machine tolerance control is hidden

### Requirement: Preserve the tolerance across settings updates

A saved override or explicit clear SHALL survive restart. Omitted request fields SHALL preserve the existing local state. Invalid values and failed writes SHALL preserve stored and effective policy.

#### Scenario: Existing machine or client

- **WHEN** an old settings row or client omits the tolerance
- **THEN** a numeric stored override or explicit file threshold still applies, and a machine with neither inherits

#### Scenario: Existing registration serialized the old default

- **WHEN** an old registration contains the implicit zero and its settings omit the threshold
- **THEN** the machine inherits its applicable cluster, room or global value

#### Scenario: Clear a file-configured threshold

- **WHEN** an operator clears a machine with an explicit file threshold
- **THEN** the machine inherits and continues to inherit after unrelated updates and restart

#### Scenario: Rejected update

- **WHEN** a tolerance is negative or non-finite, or the transaction fails
- **THEN** the API reports failure and subsequent reads and samples use the previous policy, including after restart

### Requirement: Linux GPU occupancy classification

Wattline SHALL classify each visible Linux GPU as occupied when at least one valid GPU
process PID is observed. It SHALL classify the GPU as free when inventory and process
enumeration are complete, no valid PID is observed and used VRAM is at most the effective
tolerance. Any other case SHALL remain unknown. Utilization, power and temperature SHALL
not affect this classification.

#### Scenario: Valid PID establishes occupancy with incomplete evidence

- **WHEN** a GPU reports a valid process PID despite unavailable used VRAM, unverified
  inventory or partial process visibility
- **THEN** its occupancy is `occupied`.

#### Scenario: Inclusive tolerance boundary

- **WHEN** enumeration is complete, no valid PID is observed and used VRAM is exactly
  256 MiB under the default tolerance
- **THEN** the GPU is free. With the same evidence and used VRAM above 256 MiB, it is
  unknown.

### Requirement: Linux GPU inventory count verification

When Linux NVIDIA XML supplies `attached_gpus`, Wattline SHALL require a single count
in ASCII decimal digits matching the number of returned GPU records to verify inventory.
Wattline SHALL apply the existing inventory checks when that field is absent or matches
the returned count.

#### Scenario: Reported count contradicts the GPU records

- **WHEN** `attached_gpus` reports two GPUs and the XML returns one valid GPU record with
  128 MiB used VRAM and an empty process table
- **THEN** the inventory is unverified, that GPU is `unknown`, and the device reports the inventory diagnostic.

#### Scenario: Reported count is invalid

- **WHEN** the count is present but blank, malformed, negative, or repeated
- **THEN** the inventory is unverified.

#### Scenario: Reported count is absent or consistent

- **WHEN** the XML omits the count or supplies a matching count and all other inventory
  checks succeed
- **THEN** the inventory is verified.

### Requirement: Unverifiable occupancy evidence

When no valid PID is observed, missing used VRAM, incomplete GPU inventory or incomplete
process enumeration SHALL keep the affected GPU unknown. A valid machine sample SHALL
report occupancy independently of the collection issue lifecycle defined by in-app-alerts.

#### Scenario: Evidence cannot prove idle

- **WHEN** a valid sample returns no valid PID and idle evidence is missing because of
  unavailable used VRAM, incomplete inventory or incomplete process enumeration
- **THEN** the GPU state is unknown and the sample opens no collection issue.

### Requirement: Windows and container occupancy

Windows probes SHALL retain their existing occupancy rule and SHALL NOT use the idle
memory tolerance. With process checks enabled, Linux container endpoints SHALL report
`partial` process visibility and classify each visible GPU as `occupied` when a valid
PID is observed or `unknown` otherwise, independently of used VRAM.

#### Scenario: Windows GPU with no process rows

- **WHEN** a Windows GPU reports no process rows
- **THEN** its occupancy is `unknown`.

#### Scenario: Partial container process visibility

- **WHEN** process checks are enabled and the container reports a visible GPU
- **THEN** process visibility is `partial`. Occupancy is `occupied` if a valid PID is
  observed and `unknown` otherwise.

### Requirement: Resolve conflicting cluster overrides explicitly

Machines SHALL inherit agreeing explicit member-cluster values independent of listing order. Conflicting values SHALL use a valid chosen member cluster for the field or fall back to room and global. Configuration SHALL identify the competing clusters, any chosen source and an unusable selection.

#### Scenario: Conflict introduction and recovery

- **WHEN** a machine without an override belongs to two differently configured clusters
- **THEN** it shows the conflict and effective fallback until the operator selects an eligible source or the cluster values come into agreement

#### Scenario: Membership or room changes

- **WHEN** a selected cluster is removed, no longer includes the machine, or clears its override
- **THEN** the selection can be corrected or cleared and a remaining unresolved conflict uses the current room or global value

### Requirement: Keep samples aligned with their captured policy

A sample SHALL use the effective value captured when collection begins. The latest sample SHALL retain its captured policy in API readback while it is displayed.

#### Scenario: Change while collection is underway

- **WHEN** an operator saves a configuration or membership change during a sample
- **THEN** current configuration reflects the successful write, the in-flight sample retains its starting policy, and the next sample uses the newly resolved policy
