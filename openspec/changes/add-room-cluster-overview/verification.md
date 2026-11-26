# AN-164 implementation verification

## Review input

The fixed checkout was on `main` at `bede7a15e1a14cbf36c3d8a8f3a5da467d4f4b64`. The local tracking ref and `git ls-remote origin refs/heads/main` matched that baseline. Reviewed integration and its commit are pending with Mika.

The combined implementation and OpenSpec planning diff is in `artifacts/an-164-design/implementation.patch` in the local checkout. Its SHA-256 is `85632400ff4cd5c93db9c047933cf33d05213dd7d157b03de10fcf9127ad4d97`. It contains 33 files and excludes the two verification reports and the local AGENTS.md runtime block. `git apply --reverse --check --whitespace=error-all artifacts/an-164-design/implementation.patch` exited 0 against the actual working tree. The earlier phase 1 patch is described in [phase 1 verification](../add-compute-resource-registry/verification.md).

## Baseline checks on 2026-11-25

| Command | Exit | Observed result |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | 50 passed, one Starlette TestClient deprecation warning. |
| `node --check wattline/static/monitor.js` and `node --check wattline/static/groups.js` | 0 | Both syntax checks returned no output. |
| `.venv/bin/python -m compileall -q wattline` | 0 | No compilation errors. |
| `node tools/test_i18n.cjs` | 0 | PASS, 416 message keys with locale and placeholder parity. |
| `.venv/bin/python tools/browser_smoke.py` | 0 | PASS, Playwright Chromium 159.0.8154.6, both locales, 122 intercepted history queries, 28 screenshots, zero page errors. |
| `.venv/bin/python tools/resource_browser_smoke.py` | 0 | PASS, isolated API and browser journeys for pending storage registration and synthetic capacity, persisted alert navigation, room and cluster management, 24-hour chart and coverage, keyboard tabs and ordering, filtering, and narrow layouts. |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-compute-resource-registry --strict` | 0 | Change is valid. |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-room-cluster-overview --strict` | 0 | Change is valid. |
| `git diff --check` and `git diff --cached --check` | 0 | No whitespace errors. New files were also checked with `git diff --no-index --check -- /dev/null <file>`. The index copy of AGENTS.md contains the generic repository instructions. |

Full local logs use the `artifacts/an-164-design/final-*.log` pattern. Browser screenshots `artifacts/an164-cluster-desktop.png` and `artifacts/an164-cluster-320.png` captured the baseline layout. The 2026-11-26 browser rerun regenerated them with the revised three-card layout. They use synthetic data.

## Compatibility and limits

- The schema upgrade retains host history keys, SSH identity and fingerprints, people IDs and prior multi-user assignments. Current group membership drives 24-hour summaries. Separate host and container inputs retain their observation scope. Storage and GPU totals use verified identities, and group series expose metric coverage.
- Old machine and overview history API shapes and the machine-only ordering and assignment mutation paths still work. Browser smoke covers the older API shapes and both Windows process displays, including five visible rows and two omitted rows for seven synthetic observations.
- Storage adapter acceptance uses an injected synthetic collector. Real vendor endpoints, live machines, deployed data and SSH reuse were outside the verification. Browser execution used Chromium. The local results are ready for the separate AN-168 independent review.

## 2026-11-26 follow-up on overview cards

AN-154 requested three overview cards and a GPU power card with current and rated totals. This revision updates the existing `add-room-cluster-overview` change. The checkout baseline is still `bede7a15e1a14cbf36c3d8a8f3a5da467d4f4b64`. The remote main read returned the same SHA. The two-stage working tree remains the integration input for Mika.

- Focused patch `artifacts/an-164-design/2026-11-26-power/overview-power.patch` against the verified 2026-11-25 implementation patch. SHA-256 `e90c80e84cbff6823d2c40f25f7e9550c1c23464b0d7ae01b12faae7a0a76bdc`.
- Combined patch `artifacts/an-164-design/2026-11-26-power/implementation.patch` against the main baseline. SHA-256 `1a50263b7d5f93b9e882fb148b084fce4eecad03b381053451ace91d36dacd54`.
- Both patches passed `git apply --reverse --check --whitespace=error-all` against the actual working tree. The focused patch also passed `git apply --check` against the previous patch applied to temporary files from `git archive HEAD`. The patches exclude verification reports and the runtime-managed AGENTS.md block.

| Command | Exit | Observed result |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | 51 passed, one existing Starlette TestClient deprecation warning. |
| `node --check wattline/static/monitor.js`, `node --check wattline/static/groups.js`, `.venv/bin/python -m compileall -q wattline tests tools` | 0 | No syntax or compilation errors. |
| `node tools/test_i18n.cjs` | 0 | PASS, 415 message keys, placeholder parity and locale checks. |
| `.venv/bin/python tools/resource_browser_smoke.py` | 0 | PASS, current 200 W with 3/4 coverage, rated 800 W with 2/4 coverage, and unknown rated value with 0/4 coverage when removed from the sample. English and Chinese at 1440, 976, 975, 730, 390 and 320 px. Storage still appears in device details and group summaries. |
| `.venv/bin/python tools/browser_smoke.py` | 0 | PASS with Chromium 159.0.8154.6, both locales, 122 history requests, 28 screenshots and zero page errors. Windows showed five rows and two omitted while retaining seven observed records. |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-room-cluster-overview --strict` | 0 | Change is valid. |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-compute-resource-registry --strict` | 0 | Change is valid. |
| `git diff --check` and `git diff --cached --check` | 0 | No whitespace errors. The index copy of AGENTS.md contains the generic repository instructions. |

An initial run of each browser script exited 1 on an assertion for the removed fourth card. One subsequent legacy browser run exited 1 while capturing a screenshot of a DOM element replaced during polling. The recorded PASS comes from the full rerun. Logs are under `artifacts/an-164-design/2026-11-26-power/`. The new synthetic power screenshots are `artifacts/an164-power-desktop.png` and `artifacts/an164-power-320.png`.

Rated power adds a live snapshot field and uses the GPU default limit from the existing Linux and Windows probe sample. The snapshot test checks overlapping GPU visibility, stale samples, valid zero draw, independently missing values and the existing hot GPU sample field set. The database schema, history API and archive formats remain compatible. Verification used synthetic Linux and Windows payloads and Chromium. Real GPUs and the deployed instance were outside local verification. AN-168 independent review and integration remain open.
