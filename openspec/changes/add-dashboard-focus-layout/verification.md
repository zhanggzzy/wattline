# AN-48 / AN-50 implementation verification

Recorded 2026-11-20 by Executor-Codex. These are implementation self-checks; independent review remains pending in AN-49. Change: add-dashboard-focus-layout. Base: d6e6597617dec7447aac4b3d845d2f11e223a238 (main at checkout). One review branch contains the complete feature.

Review entry: [PR #3](https://github.com/zhanggzzy/wattline/pull/3), targeting main from agent/executor-codex/7ba1c8520c19. Implementation commit: 8d5c79fdc29254fe4c14601197909810cd43a080; subsequent handoff changes only update this record and task progress. Obtain the exact current review head with gh pr view 3 --json headRefOid,baseRefOid. The PR was OPEN and draft; no checks were registered at the delivery snapshot.

## Reproduce

Use Python 3.11+ and Node/npm; the OpenSpec cache must contain the pinned official version. From the review checkout:

    python3.11 -m venv .venv
    .venv/bin/python -m pip install -e '.[test,browser-test]'
    # Only if a compatible browser is not already installed:
    .venv/bin/python -m playwright install chromium
    .venv/bin/python -m pytest -q
    node --check wattline/static/monitor.js
    node tools/test_i18n.cjs
    .venv/bin/python tools/browser_smoke.py
    .venv/bin/python -m pip wheel --no-deps . --wheel-dir artifacts/dist
    OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-dashboard-focus-layout --strict
    git diff --check
    git diff --cached --check

The actual static files execute against intercepted synthetic APIs. Browser checks start no backend, SSH connection or collector. Screenshots go to ignored artifacts/; logs/screenshots are attached to AN-50 for independent sessions. No frontend bundler exists; wheel packaging verifies static asset delivery.

## Observed results

| Check | Result |
| --- | --- |
| pytest | Exit 0: 16 passed, 1 warning in 0.96s. Existing Starlette/httpx TestClient deprecation warning. |
| JS syntax | Exit 0, no output. |
| i18n | Exit 0: 272 keys, placeholder parity, references, interpolation, Intl, persistence, fallback and blocked storage pass. |
| Browser | Exit 0, PASS, Chromium 159.0.8154.6, zero page errors; both locales and 12 mutation-dialog/language cases pass. Seven synthetic writes intercepted locally. |
| Feature acceptance | Status-only rail, keyboard selection/expansion, persisted collapse and blocked storage; full-row trends; one/two/three metric focus; 24-hour power/utilization stack; 7-day/3-day ranges; independent failures/recovery; three held obsolete requests cannot overwrite the 24-hour result. |
| Layout | Overview passes 19 widths from 320–1440px. Focus plots resize at 1440/975/731/640/390/320px with correct backing sizes and no document overflow. |
| GPU inspection | Two GPUs, occupied + idle, partial visibility, offline placeholders, empty inventory and CPU-only host; PID/account/ownership/VRAM retained. Dialog naming, close/Escape, deferred refresh and focus return pass. Inspecting GPU 1 does not overwrite GPU 0's metric card. |
| Accessible charts | Independent summaries, arrow-key announcements/tooltips; lazy semantic sample table contains all 11 synthetic periods. Return/Escape restore focus. |
| Build | Exit 0: wattline-0.1.0-py3-none-any.whl produced with static assets. |
| OpenSpec | Exit 0: strict validation passes. Review/integration remain open. |
| Diff | Working-tree and staged whitespace checks exit 0. |

## Guidance provenance

The installed/repository search found no local Modern Web Guidance skill. Existing docs/frontend-redesign.md supplied the official fixed source. This session read the actual [v1.0.1 skill](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/SKILL.md) via GitHub CLI and used its search/retrieve workflow. CLI version returned 1.0.1. The four retrieved guides total 953 lines and were read in full; captured text SHA-256: f7282ae02cb0011baedd5ea5dbe38595c2c632cd75c0e6805e0db6fc652f83c8.

Actual retrieval commands:

    gh api 'repos/GoogleChrome/modern-web-guidance/contents/skills/modern-web-guidance/SKILL.md?ref=v1.0.1' --jq .content | base64 -d
    npx -y modern-web-guidance@latest search "responsive data table" --skill-version 2026_11_10-47b4c80e
    npx -y modern-web-guidance@latest search "modal dialog focus" --skill-version 2026_11_10-47b4c80e
    npx -y modern-web-guidance@latest search "collapsible navigation sidebar" --skill-version 2026_11_10-47b4c80e
    npx -y modern-web-guidance@latest retrieve "responsive-table,dialog,responsive-design,accessibility"
    npx --offline modern-web-guidance@latest --version

For repeatable future retrieval, use modern-web-guidance@1.0.1; latest resolved to 1.0.1 during these commands. No legacy scan or runtime dependency was added. Guidance is CC-BY-4.0, authored by GoogleChrome/modern-web-guidance contributors. Color/layout decisions remain project choices.

### Modern Web Guidance

- **[responsive-table](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/guides/ui-atoms/responsive-table.md)**: I used container-stacked rows, labeled cells and a named keyboard-scrollable region ("Use standard" table elements). Sticky headers retain context in the scrolling fallback; narrow rows label every data cell.
- **[dialog](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/guides/ui-components/dialog.md)**: I used showModal(), a native close form, safe autofocus and existing scroll-containment CSS ("Use the native"). The invoker stays attached for native focus return; overscroll containment degrades gracefully without locking the root scrollbar.
- **[responsive-design](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/guides/css/responsive-design.md)**: I used dynamic viewport bounds ("Use dynamic viewport units") and per-Canvas ResizeObservers. Table layout follows its container; horizontal scrolling remains available without container queries.
- **[accessibility](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/guides/accessibility/accessibility.md)**: I preserved named status controls and added lazy sample tables ("Provide semantic data tables as alternatives"). Native buttons, selected states, outlines, focus restoration and independent chart announcements were exercised with keyboard interactions.

## Screenshot review

The implementation session visually inspected six representative actual-page captures, all using synthetic data:

- an48-desktop.png: compact rail, retained CPU/memory/system facts, full-row chart, integrated two-GPU table.
- an48-narrow.png: 390px compact rail and stacked hardware rows; the hardware region scrolls internally.
- an48-dialog-narrow.png: GPU details at 390×844; close, evidence and per-GPU trends remain available.
- an48-single-power.png: one chart fills the focus page.
- an48-power-utilization-24h.png: 1440px two-chart stack with shared 24-hour selection and independent units.
- an48-two-charts-narrow.png: narrow stacked comparison with controls and readable plot sizes.

The harness produces 25 screenshots; these six are the review attachments. Modal captures use the viewport to avoid full-page compositing artifacts with top-layer dialogs.

## Limits and next owner

GPU inventory and current processes are integrated. CPU usage, logical CPU count/load, memory and system facts remain above trends. The source contains no separate physical CPU inventory; no CPU model/topology information was invented or removed. Business APIs, configuration, database and collectors are unchanged.

This session tested Chromium only: no Safari/Firefox run, physical touch device, screen-reader listening, axe/Lighthouse certification, private instance or real-node sampling. Narrow focus pages can scroll vertically to preserve readable plots. Storage failure reduces the rail preference to the current session.

Reviewer-DeepSeek must independently review the actual code/spec/evidence. Mika owns reviewed main integration and remote SHA verification. Keep the change active and review/integration unchecked until their owners supply evidence. User deployment is a separate session.
