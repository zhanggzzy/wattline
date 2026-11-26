# Design

## Context

See proposal.md - Why. The Linux host decision lives in `host_probe.monitor_gpus`, which
reads `idle_memory_tolerance_mib` from the probe options with a literal fallback. The
collector builds those options from the `Machine` model and always includes the field
when it is not `None`. The Windows probe (`windows.nvidia_metrics`) computes occupancy
from process rows alone and never reads the tolerance. A container endpoint forces
`host_processes=False`, so `visible` is always false there and the state stays unknown.

## Goals / Non-Goals

Goals: one authoritative default of 256 MiB for Linux hosts, explicit per-machine
override precedence, an inclusive `<=` boundary, and no change to Windows or container
results. Non-goals: changing the alert text, adding a UI control, tuning individual
deployed nodes, or changing Windows/container collection.

## Decisions

- Set `Machine.idle_memory_tolerance_mib` default to 256 and raise the probe's literal
  fallback to 256. The probe is also executed as standalone source over SSH, so it cannot
  import the configuration module; keeping both numbers equal is the only way to match
  the model and probe defaults. A shared constant would be unusable in the injected
  source, and adding a second configuration key would create a compatibility surface for
  no benefit.
- Keep the tolerance on the shared `Machine` model instead of conditioning it on
  `target_os`. Windows ignores the field by construction, so a Linux-scoped default needs
  no new field, migration or API shape. Conditioning the default would add a special case
  with no observable effect.
- Keep the existing comparison `used <= tolerance`, which makes the boundary inclusive as
  required. Do not add an epsilon: memory values are already reported in MiB and an
  epsilon would silently move the documented boundary.
- Leave the container `visible` gate and the Windows rule untouched. Both are the
  mechanisms that already preserve their behavior.

## Risks / Trade-offs

- Residual VRAM between 0 and 256 MiB no longer raises the occupancy warning for Linux
  hosts, so a real process whose GPU allocation is invisible while its PID is absent
  would be hidden up to 256 MiB. Mitigation: larger allocations still warn, and the
  tolerance remains configurable per machine, including 0.
- Nodes relying on the old implicit 0 MiB default become quieter after an upgrade.
  Mitigation: the change is additive for configuration compatibility, and the default is
  the user-requested operating point. Deployment stays out of this stage.

## Migration Plan

No data or configuration migration. Existing files remain valid; nodes without the field
adopt 256 MiB on restart. Rollback is reverting the default and restarting, or setting
`idle_memory_tolerance_mib: 0` explicitly on affected nodes.

## Open Questions

None.
