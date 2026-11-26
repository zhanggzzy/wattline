# Wattline

A standalone workbench for monitoring Linux and Windows machines and their NVIDIA GPUs over SSH. The web interface supports Simplified Chinese (default) and English, with a persistent language selector in the top bar. See [localization](docs/localization.md) for preferences, fallback rules and adding languages.

- The background sampler collects machine health, CPU and memory, GPU utilization, VRAM, temperature and power. The GPU process view shows the account, workload evidence, start time and elapsed runtime at sampling when available.
- Enroll machines from the overview, set per-machine checks and polling intervals, drag to reorder, and remove nodes with their monitoring data.
- Assign people from a shared directory. The machine list shows each machine's assignees as wrapping chips in a dedicated column beside Status, with a localized unassigned value and literal spacing; details repeat the names. When the list container is too narrow for all seven columns, the list becomes labelled cards instead of scrolling horizontally.
- The dashboard reads 24 hours of raw history. Machine and GPU details show up to 7 days. Older samples are kept in local gzip archives.
- Verified Linux endpoints that share the same kernel boot appear once as a machine. Its details list the monitoring sources, including container identifiers when available. Container SSH endpoints can report their own cgroup v2 CPU and memory usage alongside visible GPU metrics.

## Quick start

Run Wattline on macOS or Linux with Python 3.11 or newer and OpenSSH. Linux targets require Python 3. Windows targets require OpenSSH Server, Windows PowerShell and read access to CIM. NVIDIA metrics require a working nvidia-smi on the target.

~~~sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
cp config.example.json config.json
wattline --config config.json
~~~

Open [the local workbench](http://127.0.0.1:8090/) and choose **新增机器**. Enter an IP, hostname or SSH alias and select the target operating system. Use the account that runs Wattline to set up public-key login and verify the server host key before enrollment. Windows enrollment requires a trusted ED25519 server key and pins its fingerprint.

The example configuration starts with an empty machine list. Machine settings and monitoring samples are stored under the configured data directory. Relative paths are resolved from the JSON configuration file. The service binds to loopback. An optional viewer_password_file enables HTTP Basic authentication for the dashboard and its API.

The registration API and file configuration accept `target_os: "linux"` or
`target_os: "windows"`. Omitted values default to Linux, including in older
registrations. A file-configured Windows SSH target uses its SMBIOS UUID in
32-character lowercase hexadecimal form without hyphens for `expected_host_id`.
To roll back to a binary released before Windows support, use a consistent
pre-upgrade data backup if Windows registrations were created.

Daily history maintenance runs at 03:00 in the configured archive_timezone (UTC by default). The [example configuration](config.example.json) can be copied and customized locally.

## Tests

~~~sh
python -m pip install -e '.[test]'
python -m pytest -q
~~~

The frontend uses native HTML controls, CSS Grid and container queries. Current
Chrome, Edge, Firefox and Safari are the intended browser targets; without
container query support, the machine table remains horizontally scrollable.

Run the isolated browser checks with synthetic fixtures. The people directory
and assignees check also uses the in-process API and temporary SQLite. No HTTP
server, collection, or SSH connection is started:

~~~sh
python -m pip install -e '.[test,browser-test]'
python -m playwright install chromium
node tools/test_i18n.cjs
python tools/browser_smoke.py
python tools/resource_browser_smoke.py
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

Choose **新增设备 / Add device** to register a CPU or GPU machine, a NAS, or a
shared storage cluster. Storage may be registered before an adapter is
available. Pending records show unavailable readings. Storage adapters are
read-only collectors that report a stable logical identity, sample time,
observation scope, capacity and health. An adapter may also report throughput,
pools, members and verified logical children. The browser check injects a
synthetic adapter. Vendor integrations require a separate adapter.

Use **分组与人员 / Groups and people** to maintain rooms, clusters and the
directory. A device can belong to one room and multiple clusters. Room and
cluster pages link to each other and list their devices. Removing a group
detaches its links and preserves device records and history.

The overview shows online devices, visible GPUs and GPU power above persisted
alerts. The power card reports current draw and rated power with separate
coverage of visible GPUs. Rated power uses the GPU default power limit reported
by NVIDIA and appears when the live sample includes it. Rooms and
clusters offer a 24-hour chart based on current machine membership. Group CPU
and memory use host readings and report machine coverage. GPU totals use unique
visible devices. A machine with only fresh container readings shows the
container scope in its details. Use the history source selector in a machine
with several endpoints to see an original endpoint's recent or archived
readings. The alert center shows first and most
recent observations, verified recovery and administrative closure.

A room can name one owner. A device or cluster can specify one directory
person, Shared, or no assignment. Existing multiple-assignee records remain
visible and persist through unrelated edits. The machine assignment API still
accepts `person_ids`. Clients using the new modes can also send `mode` with
`person`, `shared`, or `unset`. Assignments are operator notes independent of
GPU process ownership and SSH configuration.

Startup applies the SQLite schema upgrade and retains existing registry, people,
SSH identity and history keys. Keep a consistent pre-upgrade data backup.
Restoring that backup is required for rollback to a binary using the previous
schema version.

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

From machine details, choose **历史归档分析 / Archive analysis** to see older
samples already stored in gzip archives. The workbench shows decompression
progress, then opens the archived trend. Choose a metric and inclusive start
and end dates, then apply the filters. Dates and chart times follow
`archive_timezone`. The temporary analysis expires after 15 minutes of
inactivity. Open it again to rebuild it.

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

Windows CPU usage uses the current formatted Windows processor counters when
they account for every reported logical processor. This also applies to the
first sample after reboot. System volume readings follow the volume hosting
Windows. Load average is unavailable on Windows. Host history stays with the
SMBIOS identity and GPU history uses the card UUID.

Windows GPU process views show up to five rows per card. Rows with reported
VRAM sort by descending VRAM, followed by unknown values. Ties use ascending
PID. Both views show how many observed rows were omitted. The dashboard uses
all observed records for occupancy and totals. Windows NVIDIA process
enumeration is treated as partial, so an empty list leaves occupancy unknown.
WDDM can leave per-process VRAM unavailable even when card-level VRAM and
other measurements are available.
