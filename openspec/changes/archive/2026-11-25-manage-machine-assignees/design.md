# Design

## Context

The current machine settings JSON stores optional `assigned_user` by stable history identity. Wattline already serializes registry mutations and uses a SQLite transaction for the first phase of machine deletion.

## Goals

Keep person IDs stable across renames, save machine selections atomically, and keep assignments independent of sampling state and configuration writes.

## Decisions

- Use a unique name per directory entry and a machine-to-person table with a composite primary key and a restrictive person foreign key. Exact matches after trimming share an entry, with case and Unicode spelling preserved. Stable IDs allow a single rename to update display on every associated machine. Storing names directly in each machine's settings would require rewriting all matching settings on each rename and would give no durable identity.
- Require unassignment before deletion. The API rejects deletion of a linked person atomically. The directory tells the operator to clear the associations and preserves every existing link. Automatic cascade would change the registrations of multiple machines during one directory edit.
- Use a dedicated `PUT /api/machines/{id}/assignees` with `person_ids`, and create, rename and delete through `/api/people`. The snapshot provides `people` and each machine's `assigned_users` as ID/name objects. Reuse existing request guards and registry locking. Publish only committed changes in the snapshot. Independent config and assignment write paths protect one operation from overwriting the other.
- Open a dedicated native assignee dialog beside Configure. Launch the shared directory from the machine list or within the assignee editor, preserving the assignment draft while editing the directory. Use raw multiline-capable input for names so pasted invalid line separators reach validation, then present API errors in the current language.

## Risks / Trade-offs

- Two people with exactly the same trimmed spelling need distinct operator-provided display names. Case and Unicode variants stay distinct to preserve the original spelling.
- A person linked to a configured machine temporarily absent from the configuration remains protected. Restore that machine configuration to edit the saved links.
- A directory deletion that races a selection either leaves the committed association intact or causes the stale selection to fail validation. Mutation requests use last successful save for updates of the same selection.

## Migration Plan

Upgrade schema 7 to 8 within the existing startup transaction, including databases entering from older supported versions. Import each saved non-empty name and its original machine identity, then remove the obsolete field from settings JSON. Missing, null and whitespace-only values create no record. A failed migration rolls back the schema, data and version. The existing version gate prevents an older release from loading the upgraded registry. For downgrade, restore a consistent pre-upgrade data-directory backup with the previous binary. Post-upgrade assignments, directory changes and monitoring data are outside that backup.
