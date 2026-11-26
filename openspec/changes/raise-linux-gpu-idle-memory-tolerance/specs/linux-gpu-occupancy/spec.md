## Purpose

Define how Wattline classifies a Linux host GPU as occupied, free or unknown from process
evidence, inventory completeness and a per-machine idle VRAM tolerance, so operators can
trust the resulting occupancy state and collection warning.

## ADDED Requirements

### Requirement: Configurable Linux idle memory tolerance

For Linux hosts, the default idle memory tolerance SHALL be 256 MiB per card. An explicit
per-machine `idle_memory_tolerance_mib` value, including 0, SHALL take precedence over
that default. The tolerance SHALL apply per GPU to used framebuffer memory, not to total
capacity.

#### Scenario: Existing configuration without the field

- **WHEN** a Linux machine is loaded from configuration that omits
  `idle_memory_tolerance_mib`
- **THEN** its tolerance is 256 MiB and small residual VRAM does not by itself make an
  idle card unknown.

#### Scenario: Explicit per-machine override

- **WHEN** a Linux machine explicitly sets `idle_memory_tolerance_mib` to 0 or another
  non-negative value
- **THEN** that value is used instead of the 256 MiB default.

### Requirement: Edit the effective Linux GPU tolerance

Wattline SHALL show the effective per-card tolerance in Machine details → Configure
for Linux GPU hosts and accept a finite non-negative number of MiB, including zero.
The settings API SHALL report the effective value.

#### Scenario: Localized setting and saved readback

- **WHEN** an operator opens the settings in either supported language and saves a valid
  tolerance
- **THEN** the localized control shows the current value, the save response and
  subsequent reads report the new value, and later samples use it without a service restart

#### Scenario: Inapplicable device

- **WHEN** the operator opens settings for Windows, a known container endpoint, a CPU
  machine or a storage device
- **THEN** the tolerance control is hidden

### Requirement: Preserve the tolerance across settings updates

A successfully saved override SHALL take precedence over the base configuration and
survive service restart. An omitted field SHALL preserve the effective value and its
inheritance. An invalid value or failed write SHALL preserve both the effective and
stored settings.

#### Scenario: Existing machine or client

- **WHEN** an old settings row or a settings request omits the threshold
- **THEN** Wattline uses any stored override, the explicit base configuration if present,
  or the 256 MiB default

#### Scenario: Existing registration serialized the old default

- **WHEN** a machine registered before AN-211 has 0 MiB in its registration record
  and its settings omit the threshold
- **THEN** the machine inherits the 256 MiB default

#### Scenario: Rejected update

- **WHEN** the service receives a negative or non-finite value, or the settings
  transaction fails
- **THEN** the API returns an error and later samples and reads use the previously
  effective threshold, including after restart

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
- **THEN** the inventory is unverified, that GPU is `unknown` and the occupancy warning
  is emitted when enabled.

#### Scenario: Reported count is invalid

- **WHEN** the count is present but blank, malformed, negative, or repeated
- **THEN** the inventory is unverified.

#### Scenario: Reported count is absent or consistent

- **WHEN** the XML omits the count or supplies a matching count and all other inventory
  checks succeed
- **THEN** the inventory is verified.

### Requirement: Unverifiable occupancy evidence

When no valid PID is observed, missing used VRAM, incomplete GPU inventory or incomplete
process enumeration SHALL keep the affected GPU unknown. When any visible GPU remains
unknown and occupancy warnings are enabled, Wattline SHALL report the existing
“部分 GPU 占用状态无法核实” warning.

#### Scenario: Evidence cannot prove idle

- **WHEN** no valid PID is observed and any idle evidence is unavailable due to missing
  used VRAM, incomplete inventory or incomplete process enumeration
- **THEN** the GPU state is unknown and the occupancy warning is emitted when enabled.

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
