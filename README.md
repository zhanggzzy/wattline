# Wattline

A standalone workbench for monitoring Linux machines and NVIDIA GPUs over SSH. The web interface supports Simplified Chinese (default) and English, with a persistent language selector in the top bar. See [localization](docs/localization.md) for preferences, fallback rules and adding languages.

- The background sampler collects machine health, CPU and memory, GPU utilization, VRAM, temperature and power. The GPU process view shows Linux user, workload evidence, start time and elapsed runtime at sampling when available.
- Enroll machines from the overview, set per-machine checks and polling intervals, drag to reorder, and remove nodes with their monitoring data.
- The dashboard reads 24 hours of raw history. Machine and GPU details show up to 7 days. Older samples are kept in local gzip archives.
- Container SSH endpoints can report their own cgroup v2 CPU and memory usage alongside visible GPU metrics.

## Quick start

Run Wattline on macOS or Linux with Python 3.11 or newer and OpenSSH. Targets run Linux with Python 3. NVIDIA metrics require a working nvidia-smi on the target.

~~~sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
cp config.example.json config.json
wattline --config config.json
~~~

Open [the local workbench](http://127.0.0.1:8090/) and choose **新增机器**. Enter an IP, hostname or SSH alias. Use the account that runs Wattline to set up public-key login and verify the server host key before enrollment.

The example configuration starts with an empty machine list. Machine settings and monitoring samples are stored under the configured data directory. Relative paths are resolved from the JSON configuration file. The service binds to loopback. An optional viewer_password_file enables HTTP Basic authentication for the dashboard and its API.

Daily history maintenance runs at 03:00 in the configured archive_timezone (UTC by default). The [example configuration](config.example.json) can be copied and customized locally.

## Tests

~~~sh
python -m pip install -e '.[test]'
python -m pytest -q
~~~

The frontend uses native HTML controls, CSS Grid and container queries. Current
Chrome, Edge, Firefox and Safari are the intended browser targets; without
container query support, the machine table remains horizontally scrollable.

Run the isolated browser checks with synthetic API responses (no monitoring
service or SSH connection is started):

~~~sh
python -m pip install -e '.[test,browser-test]'
python -m playwright install chromium
node tools/test_i18n.cjs
python tools/browser_smoke.py
~~~

Screenshots are written to the ignored `artifacts/` directory. An existing
Chromium binary can be supplied with `--browser /path/to/chromium`.
See [design and verification notes](docs/frontend-redesign.md) for guidance
sources, coverage, compatibility, and review handoff.

## Development changes

All source, tests, configuration, dependency, build script, and repository
documentation changes follow the versioned [repository instructions](AGENTS.md)
and [OpenSpec workflow](openspec/README.md). Use the six unchanged official
skills in `.agents/skills/` and the pinned OpenSpec CLI **1.14.2**.

The [AN-25 retrospective](docs/history/an25-frontend-retrospective.md) records
the frontend work merged in PR #2, its independent review and known limitations.
It was written after implementation; that frontend change did not use OpenSpec.
Product maintenance delivers reviewed main commits. Instance updates remain a
separate deployment session requested by the user.

## Dashboard workspace

Use the arrow beside Wattline to collapse navigation into a narrow
machine-identity rail. Each machine keeps a monochrome model silhouette: B300 as
a heavy rack, RTX PRO 6000 as a dual-slot card, GB10 / DGX Spark as a compact
box, RTX 5090 as a dual-fan card, and a generic host when the observed device
model is missing, blank, unknown, ambiguous or the inventory is incomplete.
Offline machines keep the last known silhouette when their retained inventory is
complete and trusted. The status light stays independent. Machines that share a
silhouette show a short instance suffix, and identical instance names also differ
in their accessible names and tooltips; hover or keyboard focus reveals the
instance name and every available full model name. Model changes seen by a normal
poll refresh the rail and overview without navigating. Select a
machine to open it, or expand to restore names. The density preference is saved
locally when browser storage is available.

Machine trends use the full content width. Choose a metric and **全页展示 / Focus
charts** for a single large plot, then toggle additional metrics to compare them
vertically. For example, choose **GPU 功耗 / GPU power**, **24 小时 / 24 hours**,
enter focus mode and select **GPU 利用率 / GPU utilization**. At least one plot
stays selected. Use **返回工作台 / Return to dashboard** or Escape to return;
Escape first clears an active chart reading. Each chart also offers a sample
table under **查看图表数据 / View chart data**.

The hardware table below trends combines each GPU’s status and measurements
with current process PID, account, ownership evidence, VRAM, start time and
elapsed runtime at sampling. Start times use the browser's time zone. Both
timing values show **Unknown** when they cannot be verified or are absent
from an older snapshot. On small containers the table becomes labeled device
cards. Its named region can also be
scrolled with the keyboard. Select a GPU to open details, close with the visible
button or Escape, or use **查看此 GPU 趋势 / View this GPU’s trends** to inspect
that device’s history. CPU, memory, logical CPU count/load and system facts
remain above trends. See the [archived dashboard layout change](openspec/changes/archive/2026-11-20-add-dashboard-focus-layout/closeout.md)
for implementation verification, independent review and integration status.
