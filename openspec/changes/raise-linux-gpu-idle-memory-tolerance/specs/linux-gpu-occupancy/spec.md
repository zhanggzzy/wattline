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

#### Scenario: Inverse occupancy decision ladder

- **WHEN** a GPU reports a valid process PID, or reports no valid PID with used VRAM above
  the tolerance
- **THEN** the first case is occupied and the second is unknown, regardless of utilization
  being 0 or above 0.

#### Scenario: Inclusive tolerance boundary

- **WHEN** enumeration is complete, no valid PID is observed and used VRAM is exactly
  256 MiB under the default tolerance
- **THEN** the GPU is free; used VRAM above 256 MiB keeps it unknown.

### Requirement: Unverifiable occupancy evidence

Missing used VRAM, incomplete GPU inventory or incomplete process enumeration SHALL keep
the affected GPU unknown and SHALL NOT assert idle. When any visible GPU remains unknown
and occupancy warnings are enabled, Wattline SHALL report the existing “部分 GPU 占用状态
无法核实” warning.

#### Scenario: Evidence cannot prove idle

- **WHEN** the used VRAM reading is unavailable, the GPU inventory is incomplete, or the
  process table cannot be fully enumerated
- **THEN** the GPU state is unknown and the occupancy warning is emitted.

### Requirement: Unchanged Windows and container occupancy

Windows probes SHALL retain their existing occupancy rule and SHALL NOT use the idle
memory tolerance. Container endpoints without complete host process visibility SHALL
retain their existing unknown or partial occupancy behavior.

#### Scenario: Other collection branches stay the same

- **WHEN** a Windows GPU reports no process rows, or a container endpoint reports visible
  GPUs with partial process visibility
- **THEN** their occupancy states remain unknown and partial respectively, independent of
  used VRAM.
