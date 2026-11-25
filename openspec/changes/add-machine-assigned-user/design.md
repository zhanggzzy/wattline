# Design

## Context

`Machine` models the monitored inventory and is frozen; operator display aliases live in a separate `machine_aliases` table and `Monitor.aliases` map keyed by the stable `history_key`. Every other per-machine setting is stored as JSON in `machine_settings.settings`, written by `History.save_machine` from `MachineSettings`, and reapplied over the machine on load. The machine settings API already enforces same-origin JSON requests, and the frontend renders untrusted values through `escape()` or `textContent`.

## Goals / Non-Goals

**Goals:**

- Reuse the existing per-machine settings write path, snapshot projection, and settings dialog without a database schema migration.
- Keep the assigned user visibly separate from collected process accounts and SSH login configuration.
- Keep existing machines readable and make a failed save report failure with no in-memory assignment change.

**Non-Goals:**

- No assignment history, audit trail, automatic inference, or multi-user assignment.
- No change to process ownership, SSH users, monitoring checks, removal, or cold archives.
- No separate API endpoint; the existing machine settings endpoint carries the field.

## Decisions

- **Store in the existing settings JSON, not in `Machine` or a new table.** `MachineSettings` gains `assigned_user`; because it is operator metadata rather than inventory, it is excluded from `with_settings` (like `alias`) and held in a `Monitor.assigned_users` map keyed by `history_key`. Rationale: no schema version bump, the same atomic write as other settings, and configuration files stay an inventory source. Alternatives: adding it to frozen `Machine` would make config files an unintended assignment source; a dedicated table would require a schema migration and removal bookkeeping for one optional string.
- **Omit the key when unassigned.** Persist `assigned_user` only for a non-null value and drop it when cleared. This keeps cleared state durable and lets an unassigned database remain readable by the previous release. A non-null assignment does make that settings row unreadable to the previous release; see the rollback risk.
- **Validate with the existing text conventions.** Reject ASCII C0/DEL controls, C1 controls, and U+2028/U+2029 line or paragraph separators on the raw input before trimming, so leading, trailing, or rejection-only values cannot be trimmed into an accepted value; then trim ordinary whitespace, cap at 80 characters, and normalize empty to `None`. The settings endpoint's same-origin JSON dependency and 422/503 responses are reused unchanged.
- **Keep pasted line breaks available to the API.** Use a one-row text area because a single-line text input can discard or rewrite CR/LF when pasting. The text area normalizes CR/CRLF to LF, which still fails validation. Submit the control value without application trimming or browser length truncation, keep the draft on rejection, and display the assignment returned after successful persistence. Enter still submits the form outside IME composition.
- **Update in-memory state only after the database write completes.** `save_settings` already performs `History.save_machine` before mutating caches; the assigned-user map follows that ordering so a failed write leaves the snapshot and API response on the previous value.
- **Use one localized label with the value escaped.** The snapshot adds `assigned_user` to every machine view. The settings dialog gains a text field and a localized validation message. The machine detail subtitle and machine-list identity block show `使用者：…` / `Assigned user: …`, reusing the existing `escape()`/text-content paths. No process or SSH field uses this value.

## Risks / Trade-offs

- **Rollback:** a settings row containing `assigned_user` is rejected by a pre-change server with `extra='forbid'`. Mitigation: the change notes this in delivery; clearing affected assignments before downgrade restores readability, and unassigned databases remain compatible.
- **Stale metadata:** the value is human-maintained and may not match reality. Mitigation: the UI labels it as an operator record, never as verified ownership.
- **Identity lifecycle:** assignments follow `history_key`; removal deletes them with the rest of the machine settings, and re-registration starts unassigned. Verified by the removal and restart tests.
- **Length semantics:** the API enforces the 80-code-point limit after validating raw characters and trimming ordinary whitespace. The field accepts the full pasted value so the browser cannot truncate a rejected suffix into a valid assignment.

## Migration Plan

No schema or configuration migration. Existing settings JSON without the key loads as unassigned. New saves include the value only when set. Deployment is a normal service restart; old history and snapshots remain valid.

## Open Questions

None.
