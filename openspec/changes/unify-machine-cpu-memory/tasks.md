# Tasks

## 1. Current machine readings and group history

- [x] 1.1 Project CPU and memory independently and use the selected readings for machine summaries and group history. Verify host and container precedence, same-source weights and pairs, zero, missing values, coverage, and scoped compatibility in `tests/test_machine_views.py`.

## 2. Recent and cold machine history

- [x] 2.1 Use per-metric selection in machine charts and preserve original source and scope queries. Verify aligned overview, raw and warm history, and cold analysis against synthetic overlapping sources in `tests/test_machine_views.py`.

## 3. Dashboard presentation

- [x] 3.1 Use neutral localized labels and bind the selected readings in the dashboard, group details and machine charts. Update the README and verify Chinese and English labels and values with the synthetic browser checks.

## 4. Integration and handoff

- [x] 4.1 Record the baseline, actual diff and local test results in `verification.md` after running pytest, the README synthetic browser checks, strict OpenSpec validation and Git diff checks.
- [ ] 4.2 Record the independent review of the actual delivery commit.

## Workflow follow-up

- Mika syncs the specs, archives the change and verifies remote main after independent review.
