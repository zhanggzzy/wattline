# Tasks

## 1. Registry and API

- [x] 1.1 Add the directory, machine associations and atomic upgrade. Verify legacy rows, repeated startup, and forced migration rollback/retry with temporary SQLite.
- [x] 1.2 Add guarded directory and assignment operations. Verify validation, failed persistence, same-person reuse, restart, settings isolation and machine removal through the API.

## 2. Dashboard

- [x] 2.1 Show all names on cards and in machine details, add the dedicated editor and shared directory, and document the operator flow and compatibility boundary. Verify the bilingual flow, cancellation, failure, literal names and long-name layout using the synthetic API browser check.

## 3. Handoff

- [x] 3.1 Run the complete local checks and link reproducible evidence in [`verification.md`](verification.md) for AN-116.
- [ ] 3.2 Record the independent review of the implementation under AN-115 and resolve any findings.
- [ ] 3.3 Mika integrates the reviewed result and records the verified remote SHA.

## Workflow follow-up

- Sync the applicable spec and archive after implementation, verification and independent review pass.
