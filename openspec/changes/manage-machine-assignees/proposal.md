# Proposal

## Why

AN-102 feedback and implementation task AN-116 ask for a visible list of the people using each machine and an entry point beside its configuration button. A shared directory lets operators reuse and maintain those names across machines.

## What Changes

- Show all registered assignees in the normal machine list and detail view. Place a dedicated assignee editor beside Configure, with multi-select, deselection, clear, save, and cancel available for offline machines.
- Allow operators to add, rename, and delete people in a shared directory. Block deletion while any machine still references the person and ask the operator to clear the associations first.
- Import existing non-empty single assignments into the directory and preserve their machine associations. Test validation, persistence, failed saves, machine removal, and bilingual desktop and narrow layouts using synthetic data.
- **BREAKING** The snapshot replaces `assigned_user` with `assigned_users`. Machine settings and enrollment requests no longer accept `assigned_user`. Use the dedicated assignment API after enrollment. Downgrading across the SQLite schema change requires a pre-upgrade backup.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `machine-registry`: shared directory, multi-person assignments, migration, and visible registration in both views.

## Impact

The machine registry, SQLite schema, dashboard API, and bilingual interface change. Existing configuration files stay valid. The rollout uses the existing service startup migration. AN-116 delivers a local implementation and verification for independent review under AN-115.
