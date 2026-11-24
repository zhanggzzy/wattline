# Design

## Context

The Linux probe reads proc uptime before running `nvidia-smi`. It uses that reading and repeated reads of each process's start ticks to guard against PID reuse. Container-only endpoints can report NVIDIA PIDs without a verified host PID mapping. The live snapshot already projects process fields through an allowlist.

## Goals / Non-Goals

Use one source-clock sample per GPU enumeration and preserve the confidence boundary for host process identity. This change covers the current snapshot and current process views. History continues to store device metrics.

## Decisions

- Pair proc uptime with the endpoint's Unix wall clock immediately before querying NVIDIA. Subtract process start ticks converted to seconds from uptime for elapsed runtime, then subtract that same interval from the sampled wall clock for the start timestamp. The duration includes suspend time at the resolution provided by the kernel. [Linux uptime](https://github.com/torvalds/linux/blob/master/fs/proc/uptime.c) and [Linux process stat](https://github.com/torvalds/linux/blob/master/fs/proc/array.c)
- Enrich the identity only after its start ticks have been rechecked, including after a failed cgroup read. Require the process's entire start tick to precede the enumeration boundary for timing, since a start in the boundary tick could represent a replacement. Existing ownership eligibility still uses the established start limit.
- Publish the optional pair `started_at` (Unix epoch milliseconds) and `elapsed_seconds` (completed seconds). A partial or invalid pair renders as unknown. Timing is fixed until a new sample arrives.
- Reuse the dashboard's localized date and number formatting. Show a full date and time in the browser's local zone. Show the duration to seconds for recent starts and use larger units for longer runtimes. Update timing as a live field without rebuilding the page; refresh the dialog process list when its rows change.

## Risks / Trade-offs

- The start timestamp is approximate at the probe's uptime and tick resolution and reflects the source clock as observed at sampling.
- An unavailable wall-clock reading still permits independently verified ownership. An unavailable uptime reading removes the evidence used to validate a PID against the enumeration boundary.
- A horizontal scroll region keeps the GPU detail time columns accessible on narrow viewports.

## Migration Plan

Current snapshots can omit both fields. The dashboard handles those snapshots during upgrade and rollback, and existing configuration and stored history can be used directly.
