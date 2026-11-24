# Tasks

## 1. Collect and publish process timing

- [x] 1.1 Derive the timing pair from the verified Linux process and source sample, project it into the current API, and verify valid, unavailable, legacy, container and PID race cases with synthetic probe and API fixtures.

## 2. Display process timing

- [x] 2.1 Render localized timings and unknown states in the hardware list and GPU detail dialog. Verify polling updates, both locales, browser-local time, and narrow-screen access with the synthetic API browser check.

## 3. Verify and review

- [ ] 3.1 Run the repository test suite, JavaScript and locale checks, the synthetic API browser check, OpenSpec strict validation and Git diff checks. Record outputs and limitations in [verification.md](verification.md).
- [ ] 3.2 Obtain independent review against the actual implementation commit and record the outcome.

## Workflow follow-up

- Mika coordinates review, syncs the delta and archives the change after the required checks pass, then verifies the remote main commit.
