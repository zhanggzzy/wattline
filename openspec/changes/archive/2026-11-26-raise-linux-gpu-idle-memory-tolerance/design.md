# Design

## Context

See proposal.md - Why. The Linux host decision lives in `host_probe.monitor_gpus`, which
reads `idle_memory_tolerance_mib` from the probe options with a literal fallback. The
collector builds those options from the `Machine` model and always includes the field
when it is not `None`. The Windows probe (`windows.nvidia_metrics`) computes occupancy
from process rows alone and never reads the tolerance. A container endpoint forces
`host_processes=False`, so with process checks enabled it reports partial visibility.
A valid GPU PID establishes occupancy in that scope even without host process details.

## Goals / Non-Goals

Use a 256 MiB default for Linux hosts and let operators adjust the threshold per machine
from Configure. Keep the inclusive `<=` comparison and verify reported GPU counts
before using the inventory as evidence of idle.

## Decisions

- Set `Machine.idle_memory_tolerance_mib` default to 256 and raise the probe's literal
  fallback to 256. The probe is also executed as standalone source over SSH, so it cannot
  import the configuration module; keeping both numbers equal is the only way to match
  the model and probe defaults. A shared constant would be unusable in the injected
  source, and adding a second configuration key would create a compatibility surface for
  no benefit.
- Expose the effective tolerance in the machine view used by the snapshot and settings
  response. The dialog shows it for GPU-capable Linux machines, including those awaiting
  their first sample, and hides it for known container endpoints, Windows, CPU and
  storage. The form submits a changed value through the existing settings endpoint.
- Layer an explicit override in the existing settings JSON on top of the file or
  registration value. The settings merge uses field presence so 0 is explicit. An
  omitted field preserves any previous override in the same SQLite transaction and
  continues to inherit the base value if there was none.
- Registrations created before AN-211 serialized the implicit 0 MiB default. The old
  registration API had no tolerance input, so this stored zero inherits the current
  default. File-configured zero and zero saved through the settings API remain explicit.
  New registrations store tolerance only in their settings when explicitly supplied.
- Publish the new machine configuration after the settings write commits. The sampler
  reads the current machine just before collecting in its normal slot, so a change to
  tolerance alone preserves cadence and the CPU baseline. A collection already underway
  can finish with the value it started with.
- Keep the existing comparison `used <= tolerance`, which makes the boundary inclusive as
  required. Do not add an epsilon: memory values are already reported in MiB and an
  epsilon would silently move the documented boundary.
- Fold the optional Linux XML `attached_gpus` count into the existing inventory gate.
  A present field must be a single scalar count that matches the number of direct
  `gpu` records. A missing field leaves the configured count, UUID and allowlist checks
  to determine completeness. The sampler continues using the existing inventory warning.
- Check for a valid PID before applying the idle evidence gates. Without a valid PID,
  an unverified inventory or incomplete process visibility leaves occupancy unknown.
  Containers can still report a valid PID. When container resource monitoring is
  enabled, the existing warning suppression for unknown occupancy applies.

## Risks / Trade-offs

- Residual VRAM between 0 and 256 MiB no longer raises the occupancy warning for Linux
  hosts, so a real process whose GPU allocation is invisible while its PID is absent
  would be hidden up to 256 MiB. Mitigation: larger allocations still warn, and the
  tolerance remains configurable per machine, including 0.
- Nodes relying on the old implicit 0 MiB default become quieter after an upgrade.
  Mitigation: the change is additive for configuration compatibility, and the default is
  the user-requested operating point. Deployment stays out of this stage.

## Migration Plan

Existing files and settings rows need no migration. On startup a row with an override
takes precedence, and a row without one inherits the file, registration or 256 MiB
default. To run a binary from before AN-213 after using this setting, use a consistent
pre-upgrade data backup. Its settings model rejects unknown keys in persisted rows.

## Open Questions

None.
