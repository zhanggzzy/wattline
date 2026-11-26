# Raise Linux GPU idle memory tolerance

## Why

AN-211 follows the AN-202 investigation of the “部分 GPU 占用状态无法核实” collection
warning. The Linux host probe treats a GPU as externally occupied when it is idle by
process evidence but still holds any used VRAM, because the default
`idle_memory_tolerance_mib` is 0 MiB. Small residual allocations left by background
drivers and service processes therefore turn idle cards into “unknown occupancy” and
produce frequent false alarms. Operators accept small residue and only care about large
compute usage.

## What Changes

- Raise the default Linux host `idle_memory_tolerance_mib` from 0 MiB to 256 MiB per
  card. A card with complete inventory, complete process enumeration, no valid GPU
  process PID and used VRAM from 0 through 256 MiB inclusive is classified free.
- Keep the unknown classification and the existing warning for used VRAM above 256 MiB,
  for missing used-memory readings, for incomplete GPU inventory and for incomplete
  process enumeration.
- Keep observed valid PIDs as occupied. GPU utilization, power and temperature stay out
  of the occupancy decision and keep their current behavior.
- Keep explicit per-machine `idle_memory_tolerance_mib` values authoritative, including
  an explicit 0 MiB.
- Keep the configuration model default and the host probe fallback identical, so a
  directly invoked probe without the field matches a node without explicit
  configuration.
- Preserve Windows and container collection behavior unchanged: the Windows probe has
  its own occupancy rule and never reads this tolerance, and a container endpoint has
  incomplete process visibility and therefore stays unknown.

## Capabilities

### New Capabilities

- `linux-gpu-occupancy`: Linux host GPU occupancy classification from process evidence,
  inventory completeness, used VRAM and the per-machine idle memory tolerance.

### Modified Capabilities

None.

## Impact

- `wattline/config.py`: `Machine.idle_memory_tolerance_mib` default.
- `wattline/host_probe.py`: probe fallback for the same field.
- `tests/test_monitor.py`: synthetic probe and configuration coverage for the default,
  the inclusive boundary, higher usage and explicit overrides.
- Existing `config.json` files stay valid. Nodes without the field adopt 256 MiB; nodes
  with an explicit value keep it. No API shape, persistence or history format change.
  Deployed configuration and running instances are out of scope for this stage.
