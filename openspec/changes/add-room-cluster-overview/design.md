## Context

AN-154 v0.2 pages 2, 3, 6 and 7 specify current-membership history, 24-hour buckets and distinct observation scope. The current history API serves per-machine and overview series against hot and warm history.

## Goals / Non-Goals

Provide physical and logical group navigation and actionable coverage. Keep existing API and device detail paths compatible.

## Decisions

- Store room and cluster identities separately from resource IDs. Store one room relation per resource and many cluster relations. Derive inverse relations from the same membership data. Edits and removal unlink atomically.
- Read existing hot and warm history at a fixed 24-hour window. The group API carries metric value, scope and valid/eligible coverage per five-minute bucket. Use newest observation within each bucket and current membership. Historical samples without weighting inputs contribute only to metrics with sufficient data.
- Reuse charts and focus behavior. Use three overview cards as requested in AN-154 on 2026-11-26, followed by the alert section, with keyboard tabs and canonical links. The machine list keeps existing sort semantics for compute, with storage integrated into the workspace.

- Report the default GPU power limit from the existing NVIDIA read-only XML sample. The Linux and Windows observation paths share the GPU parser. Accept only positive finite values from the GPU default field. GPU current draw, adjusted or enforced limits, limits of the supported range, module power and system readings retain their original meanings. See the [NVIDIA GPU power reference](https://docs.nvidia.com/deploy/nvidia-smi/index.html#gpu-power-readings).
- Form independent totals from the freshest usable readings for each verified visible GPU UUID across the same host and container scope used for the overview. Show coverage against the unique visible count for each reading, and unknown when a total has no readings. Add rated power only to the live snapshot. Older snapshots, hot and warm history, and the cold archive retain their existing contracts. On narrow screens the power card spans the row.

## Risks / Trade-offs

Current membership is applied across the window. Show that fact in the UI. Historical measurements without sufficient scope or capacity information appear as gaps.

## Migration Plan

Add empty group tables and links on first startup. Existing resources initially have no room or cluster. For rollback, restore a consistent data backup if group metadata must be discarded.
