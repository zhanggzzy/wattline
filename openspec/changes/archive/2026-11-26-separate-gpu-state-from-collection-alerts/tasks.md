# Tasks

## 1. Local implementation and verification

- [x] 1.1 Separate sample validity from GPU occupancy in the sampler and persisted alerts. Preserve the device labels and add regression checks for the alert lifecycle, freshness and unusable Windows GPU-only observations.
- [x] 1.2 Run the full pytest suite, the synthetic dashboard checks, strict OpenSpec validation and Git diff checks. Record commands and results in the change.

## 2. Independent review and integration

- [x] 2.1 Review the implementation independently in AN-216 and record the reviewer result and reproduced checks in [closeout.md](closeout.md).
- [x] 2.2 Integrate through Mika after review and verify the resulting main SHA. See [closeout.md](closeout.md).

## Workflow follow-up

- Sync the delta and archive the change after independent review and required checks pass.
