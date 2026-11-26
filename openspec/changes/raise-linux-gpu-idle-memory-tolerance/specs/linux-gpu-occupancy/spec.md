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
