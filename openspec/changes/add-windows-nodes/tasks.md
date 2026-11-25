# Tasks

## 1. Enrollment and collection

- [x] 1.1 Implement target OS persistence, Windows SSH dispatch and host key pinning. Verify API enrollment, rejection of identity/key changes and registry reload with isolated data.
- [x] 1.2 Implement Windows host and NVIDIA probes. Verify processor group coverage, sampling after simulated reboot, system volume, partial and unavailable GPU data, UUID history and timeout handling with fixtures. Document target prerequisites and measurement semantics.

## 2. Dashboard

- [x] 2.1 Add the OS selector and bound both Windows process views. Verify deterministic order, omitted count, absent UID, partial and no-card states, and Linux behavior in the synthetic browser check.

## 3. Verification and handoff

- [ ] 3.1 Run and document local regression, browser, syntax, OpenSpec strict and Git checks, and the authorized read-only target attempt. Link the measured evidence in [verification.md](verification.md).
- [ ] 3.2 Verify the probe and processor group behavior on the authorized Windows target.
- [ ] 3.3 Complete independent review of the implementation and evidence.

## Workflow follow-up

- Mika coordinates fixes and integrates the reviewed change, synchronizes the specs, archives the change and verifies remote main.
