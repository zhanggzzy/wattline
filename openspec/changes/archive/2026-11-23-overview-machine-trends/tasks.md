# Tasks

## 1. Contract and backend

- [x] 1.1 Define the overview history contract: per-machine columns, allowed metrics, 24-hour cap.
- [x] 1.2 Implement aligned per-machine whole-machine series in `wattline/history.py`.
- [x] 1.3 Map internal history identities to public machine ids and validate overview metrics in `wattline/service.py` and `wattline/app.py`.
- [x] 1.4 Add HTTP coverage for two distinct machines, metric units, zero values and missing samples.

## 2. Overview layout and trend

- [x] 2.1 Stack attention and trend panels before the machine list, full width at all breakpoints.
- [x] 2.2 Draw one labelled line per machine, with duplicate-name addresses and no cross-machine average.
- [x] 2.3 Add overview metric switching and keep the overview window fixed at 24 hours.
- [x] 2.4 Extend the synthetic browser check for order, default metric, switching, units and missing data.

## 3. Verification and handoff

- [x] 3.1 Run pytest, JS syntax, OpenSpec strict, diff checks and the synthetic browser check; record real output in `verification.md`.
- [x] 3.2 Commit implementation and evidence on the fixed development tree without touching the runtime injection block.
- [x] 3.3 Obtain independent follow-up on the AN-54 findings. AN-56 passed the pre-integration candidate `a5cbee2`.

## 4. AN-57 review fixes

- [x] 4.1 Preserve each machine's sample continuity through alignment and plotting. Verify slow cadence, actual gaps, zero, window edges and detail history with synthetic tests.
- [x] 4.2 Render chart labels as wrapping text and distinguish repeated names, addresses and colours. Verify legend, tooltip and matching strokes in the Chromium smoke check.
- [x] 4.3 Remove local paths from verification, run all required checks and record results and the implementation SHA in `verification.md`. Verify the Git index excludes the runtime block.

## 5. AN-59 mainline integration

- [x] 5.1 Integrate the reviewed net changes with mainline, preserving localized controls and readings, focused comparisons and time ranges, memory readings, compact navigation, GPU inspection and list interactions. Combine both synthetic browser suites and verify the localized per-machine overview, including in focus mode.
- [x] 5.2 Run pytest, JS syntax, i18n, Chromium smoke, OpenSpec strict and diff checks. Record commands and results in `integration.md` and audit candidate ancestry and the AGENTS.md index entry.
- [x] 5.3 AN-58 independently reviewed and passed candidate `2651bc7`. See `integration.md`.

## Workflow follow-up

- After AN-58 passes, sync the overview spec and archive this change. Mika verifies each commit to be pushed excludes machine-local paths and delivers main.
