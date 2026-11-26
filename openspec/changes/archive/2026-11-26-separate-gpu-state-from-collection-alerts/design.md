# Design

## Context

The sampler stores machine samples and alert transitions in one SQLite transaction. The freshness worker checks the machine view and records expiry against the most recent stored sample. See [proposal](proposal.md) for the reported behavior.

## Goals

- Base collection alerts on sample validity using the existing machine view's freshness limit and sampler timeout.
- Preserve GPU occupancy confidence, machine health diagnostics, and historical alert records.

## Decisions

- Reuse the existing `collection` rule for machine failures, timeouts and expiry. Carry the existing diagnostic for failed and timed-out attempts, keeping critical severity for offline observations. Expiry uses `sample_stale` at the effective deadline. The first usable sample also resolves active legacy machine `offline` and `stale` events.
- Retain the sampler's existing definition of a usable observation. For Windows, a verified empty GPU inventory counts as usable. A GPU-only response with no readings and an unverified inventory counts as a failure, while inventory confidence stays unverified.
- Evaluate freshness from the locally recorded start and receipt times, using the same per-machine timeout and cadence adjustments as the view. Timestamp recovery at receipt so a new sample started shortly before the preceding sample expired can resolve the issue. Store alert transitions only for the latest machine sample and keep the freshness worker's persisted-sample guard.
- Remove the occupancy-only warning from the Linux and Windows probes. Continue emitting device state from their existing evidence, and use the requested Chinese labels in the GPU table.

## Risks / Trade-offs

Legacy machine alert keys remain visible in alert history. Legacy active rows remain until a valid sample or administrative closure. Genuine partial coverage continues to appear in machine diagnostics when usable measurements are present. The SQLite schema and storage alert rules retain their existing formats.
