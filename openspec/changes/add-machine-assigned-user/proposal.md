# Proposal

## Why

AN-102 asks the operator to record who is currently using each monitored environment. Wattline identifies machines and their GPU process owners, but it has no place to note the human or team assigned to a machine, so that context lives outside the workbench.

## What Changes

- Add an optional per-machine assigned-user text value that the operator can fill, edit, or clear in the existing machine settings dialog.
- Persist the value with the existing per-machine settings record, keyed by the stable machine identity. Machines without a recorded value, including machines registered before this change, remain unassigned.
- Expose the recorded value in the machine snapshot and show it on the machine detail page and machine list, localized in Chinese and English and escaped as user text.
- Keep the field advisory only: GPU process ownership and SSH login configuration continue to come from their existing sources.

## Capabilities

### New Capabilities

- `machine-registry`: durable per-machine registration metadata, including an optional operator-recorded assigned user shown with the machine.

### Modified Capabilities

## Impact

`MachineSettings`, the machine settings API payload and snapshot view gain an optional `assigned_user` field. The existing `machine_settings` row stores it without a schema migration; existing configurations and history stay readable. The machine settings dialog and machine detail/list views gain localized controls and labels. Process ownership, SSH users, monitoring and archive behavior are unchanged.
