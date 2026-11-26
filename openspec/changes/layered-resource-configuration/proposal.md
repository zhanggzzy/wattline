## Why

AN-219 revises AN-202 after operator feedback. Per-machine tolerance edits duplicate work across related machines, and separate detail actions make configuration hard to find.

## What Changes

- Resolve each inheritable setting from machine, cluster, room and global values in that order. Use Linux host GPU idle VRAM tolerance as the first field and retain the built-in 256 MiB default.
- Show overrides, effective values and sources. Support explicit zero, clearing an override and choosing the source for machines with conflicting cluster values.
- Put machine, room and cluster detail edits behind one localized Configure entry per detail. Add Global configuration to the overview. Keep explicit deletion confirmation and preserve existing entity metadata and membership semantics.
- Apply committed policy and membership changes at the next sample start. Preserve stored thresholds, explicit file settings, legacy clients and the existing Linux, Windows and container occupancy evidence rules.
- Follow AN-215 for collection events. A valid sample still reports each GPU's occupancy state and existing diagnostic evidence.

## Capabilities

### Modified Capabilities

- `linux-gpu-occupancy` gains layered tolerance resolution, source reporting and sample timing.
- `machine-registry` moves the assignee editor behind the machine configuration entry.
- `resource-groups` exposes scoped settings and member-effective values from group configuration.
- `overview` provides a global configuration entry.

## Impact

The registry, SQLite schema, snapshot, settings and group APIs, sampling boundary and localized frontend change. The old machine settings route and registration contract remain usable. Acceptance uses temporary SQLite, synthetic GPU XML and Chromium. The change remains active for independent review.
