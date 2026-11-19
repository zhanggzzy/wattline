# Verification

## Baseline and scope

- Task: AN-47 / parent AN-45, memory used capacity alongside usage percentage.
- Repository base: `5dc41ba` (`AN-42: record independent review and archive English localization`).
- Implementation branch: `agent/executor-omp/838e9045f08d`.
- Implementation commit: `5a9687d` (`AN-47: show used memory capacity alongside usage`); this evidence update is a follow-up commit on the same branch.
- Changed implementation: `wattline/static/monitor.js`, `wattline/static/monitor.css`.
- Changed synthetic check: `tools/browser_smoke.py`.
- No backend, API schema, history schema, dependency, configuration or deployment changes.

## Commands and results

Environment: Python 3.11.17 in the task `.venv`, Node 26.11.0, Playwright Chromium 159.0.8154.6, OpenSpec 1.14.2.

| Command | Exit | Output |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | `16 passed, 1 warning in 0.63s` (existing Starlette/httpx deprecation warning) |
| `node --check wattline/static/monitor.js` | 0 | no output |
| `node tools/test_i18n.cjs` | 0 | `PASS: 261 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py` | 0 | `result: PASS`, `page_errors: []`, 7 synthetic mutations, 19 screenshots, both locales, `unlimited_container.used_text: 1.0 GiB`, `duplicate_hidden: true` |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate show-memory-used-bytes --strict` | 0 | `Change 'show-memory-used-bytes' is valid` |
| `git diff --check` | 0 | no whitespace errors |

Setup commands actually used:

~~~sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[test,browser-test]'
.venv/bin/python -m playwright install chromium
~~~

## Browser evidence

Synthetic API responses only; no Wattline service, SSH connection or real node was started.

- `artifacts/desktop.png` — 总览内存列显示 `38%`、百分比条与 `· 48.0 GiB 已用`；离线节点仅显示 `—`。
- `artifacts/detail.png` — 详情内存卡主读数 `38%`，辅助文本 `48.0 GiB / 128.0 GiB 已用`。
- `artifacts/mobile-list.png` — 390 px 卡片布局同样显示已用量，无横向溢出。
- `artifacts/english-overview.png` — 英文显示 `38%` 与 `· 48.0 GiB used`。
- `artifacts/container-unlimited.png` — 无 cgroup 上限容器以 `1.0 GiB` 为主读数，不重复已用量，并保留“无 cgroup 内存上限，使用量含缓存”。

Assertions added to `tools/browser_smoke.py` cover:

- Chinese overview percentage + `48.0 GiB 已用`; English `48.0 GiB used`.
- Detail-card `48.0 GiB / 128.0 GiB 已用` / `48.0 GiB / 128.0 GiB used`.
- Offline machine hides the used-capacity line and never renders `0.0 GiB`.
- A sample with `memory` but without `used_bytes` keeps `38%` and hides the used line.
- Unlimited container shows used GiB once, hides the duplicate line, and retains the cache/no-limit note.
- All existing responsive widths (320–1440 px), focus behavior, dialogs and locale switching continue to pass without page errors.

## Limits

- Verification is synthetic and single-browser; no real host, container runtime or mobile device was used.
- The host fixture uses the service-normalized `memory.used_bytes`; the no-limit container case injects the snapshot shape already produced by the backend.
- Screenshots live in the ignored `artifacts/` directory and are attached to the issue comment, not committed.
- This is implementer self-verification, not independent review. Independent review and main integration remain open in `tasks.md`, and Mika owns them.

## Independent review and specification sync (2026-11-19)

Reviewer-Codex / gpt-6.1-sol independently reviewed Executor-OMP / DeepSeek 4.1 Flash commit `49280e38719bfb8451f485a15820c2abeb8b097c` in AN-46 and returned **PASS, no blocking findings**. The earlier paragraph describes the implementer's original handoff state; this section records the subsequent review.

The reviewer independently passed pytest (16 tests), JavaScript syntax, i18n (261 keys), browser smoke, wheel build and OpenSpec 1.14.2 strict validation. Additional synthetic checks passed 26 locale/state groups, 8 in-place updates and 76 width/view combinations without page errors. Coverage includes real zero vs missing values, stale/offline samples, capped/uncapped containers and responsive layouts. Limit: synthetic APIs and Chromium only; no live collection, real node/container, other browser engines or deployed-instance verification.

Evidence: Multica AN-46 final comment `01a1f1a6-79aa-7dbd-897e-8246acf7e332`; report attachment `01a1f1a6-799b-79c8-be45-59c59bd46d69` (AN-46-review.md); reproducible scripts/results/screenshots attachment `01a1f1a6-79a5-7809-a0b2-ab3fc2320081` (AN-46-review-evidence.zip). The source bundle exports HEAD rather than the branch name; import with `git fetch <bundle> HEAD:an47-review` when using the attached bundle.

Mika integrated the exact reviewed commits by fast-forward in a dedicated task checkout and synchronized all four ADDED requirements into the new `dashboard-memory-metrics` main spec, preserving the delta Purpose verbatim. No implementation code changed after independent review. Integration checks: OpenSpec 1.14.2 `validate --specs --strict` (3 specs), `validate show-memory-used-bytes --strict`, `node --check wattline/static/monitor.js`, `node tools/test_i18n.cjs` (261 keys), and `git diff --check` all exited 0. No redundant application test run was needed because the reviewed implementation is unchanged.
