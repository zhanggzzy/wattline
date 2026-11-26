# Design

## Context

The registry pins the expected identity of each endpoint. SSH fingerprint pins distinguish colliding machine IDs where required. History is keyed by the original endpoint identity in raw, warm and v1 gzip storage. The Linux probe already reports the kernel boot UUID and observation scope.

## Decisions

- Use matching, valid Linux kernel boot UUIDs from accepted endpoint observations as positive evidence of a shared machine. Keep registration constraints and pinned identity checks. Windows, unknown IDs and different boots stay independent. A failed or stale collection retains the last successful identity. A new conflicting boot separates the endpoints until matching evidence arrives. Persist the last successful evidence independently of history retention, and seed it from verified recent history when available. Container networks with a virtualized boot UUID can remain separate.
- Prefer a known host endpoint as the canonical machine ID, with endpoint ID as the stable tie breaker. Resolve old endpoint IDs to the same machine in dashboard navigation. Keep original IDs for settings, removals and historic source downloads. Project clusters as the union of their source memberships. Choose the canonical endpoint's room when assigned and otherwise the first assigned source's room, with the canonical ID used for navigation. Ordering a machine moves its source registrations as a block.
- Select one fresh observation, preferring a host over containers, then the latest sample. For the overview and group statistics, combine visible GPU observations by verified UUID with single contributions. Machine detail uses the selected observation and labels its CPU, memory and GPU scope. Group CPU and memory require host scope and report coverage against all machines. No host sample means unavailable host CPU and memory. Container cgroup readings remain available in machine detail.
- Keep all source histories in place. A machine trend uses one value per time bucket and a common scope for CPU and memory. The canonical source retains its history. Secondary samples join the machine trend only within the currently confirmed shared boot. Other boots stay accessible through the source selector, which also opens the source's archive. Cold analysis uses the same source and boot filtering and stages data in the existing temporary workspace. Preserve time, missing values and continuity across boot, scope and source changes.
- Preserve legacy group history scope series for API callers. The dashboard requests machine aggregates, which use host CPU and memory and unique visible GPUs including container observations where available.

## Risks / Trade-offs

- A reboot or relocation can temporarily show additional entries until the same kernel UUID is verified again. A matching name, container label, address, GPU or machine-id alone provides insufficient evidence.
- Existing group metadata can conflict across sources. The projected room uses the documented precedence, and each source keeps its placement and other settings.
- Older container samples may lack a runtime container ID. The registered endpoint label identifies the source in this case.

## Migration Plan

SQLite retains a small table for the latest verified source observation using the existing schema upgrade path. Original settings, sample keys, archive format and single-source cleanup remain valid. Rolling back to a binary with the old schema version requires restoring a consistent pre-upgrade backup.
