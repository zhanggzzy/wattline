# Raise Linux GPU idle memory tolerance

## Why

AN-211 follows the AN-202 investigation of the “部分 GPU 占用状态无法核实” collection
warning. With the original 0 MiB default, a Linux GPU with no observed process and
any used VRAM had unknown occupancy. Small residual allocations left by background
drivers and service processes therefore turn idle cards into “unknown occupancy” and
produce frequent false alarms. Operators accept small residue and only care about large
compute usage. AN-213 lets operators tune that same threshold on each Linux GPU machine
from its existing configuration dialog. AN-210 found that a Linux sample can report
more GPUs than it returns and still qualify as complete. AN-214 corrects that check.

## What Changes

- Raise the default Linux host `idle_memory_tolerance_mib` from 0 MiB to 256 MiB per
  card. A card with complete inventory, complete process enumeration, no valid GPU
  process PID and used VRAM from 0 through 256 MiB inclusive is classified free.
- When no valid PID is observed, keep the unknown classification and the existing
  warning for used VRAM above the effective tolerance, missing used-memory readings,
  incomplete GPU inventory and incomplete process enumeration.
- Check the Linux XML card count when `attached_gpus` is present. An invalid or
  mismatched count leaves the inventory unverified. XML without that field still
  uses the existing inventory checks.
- Keep observed valid PIDs as occupied. GPU utilization, power and temperature stay out
  of the occupancy decision and keep their current behavior.
- Keep explicit per-machine `idle_memory_tolerance_mib` values authoritative, including
  an explicit 0 MiB. An explicit settings save takes precedence over the base machine
  configuration. Omission by an older client preserves the override or the inherited value.
- Show the effective tolerance in Machine details → Configure for Linux GPU machines
  using the dashboard's Chinese and English locales. Accept finite non-negative MiB
  values and apply successful saves on subsequent samples and after a service restart.
- Keep the configuration model default and the host probe fallback identical, so a
  directly invoked probe without the field matches a node without explicit
  configuration.
- Preserve the Windows occupancy rule. With process checks enabled, Linux container
  endpoints report partial process visibility and classify visible GPUs as occupied
  when a valid PID is observed or unknown otherwise.

## Capabilities

### New Capabilities

- `linux-gpu-occupancy`: Linux host GPU occupancy classification from process evidence,
  inventory completeness, used VRAM and the per-machine idle memory tolerance.

### Modified Capabilities

None.

## Impact

- `wattline/config.py`: machine default and settings request validation.
- `wattline/host_probe.py` applies the probe fallback and verifies the reported card count.
- Existing snapshot, machine settings API and settings persistence carry the tolerance.
- The machine settings dialog, API and synthetic collector checks cover saving and
  reading the effective value, invalid input and failed writes.
- Existing `config.json` files stay valid. Nodes without the field adopt 256 MiB; nodes
  with an explicit value keep it until an operator saves an override. Existing settings
  rows load without migration. The setting uses the existing JSON payload in SQLite.
