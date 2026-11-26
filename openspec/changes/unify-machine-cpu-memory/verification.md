# AN-232 实施验证

2026-11-26 执行。AN-226 是父任务，AN-232 实施验收反馈，AN-231 负责独立审查。

## 基线与实际改动

- 开始时本地 `main`、`origin/main` 和 `git ls-remote origin refs/heads/main` 均为 `ba7cd507f76e9a504876ce336a41ce2b59f96a65`。提交前再次查询远端得到相同 SHA。
- `wattline/` 实现按机器和指标选择读数，覆盖实时快照、机房与集群汇总、近期和冷归档图表。`tests/test_machine_views.py` 和 `tools/` 验证合成观测与页面行为。`README.md` 记录取值及覆盖口径。
- 交付 SHA 见 AN-232 的交接评论。本文件随交付提交保存，对照 `git show --stat <交付 SHA>` 和 `git diff ba7cd507f76e9a504876ce336a41ce2b59f96a65 <交付 SHA>` 可复核实际改动。索引中的 `AGENTS.md` 与基线一致，工作树的 Multica 注入保留。

## 实际命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `node --version`、`npm --version`、`.venv/bin/python --version` | 0 | Node v26.11.0、npm 11.20.0、Python 3.11.17 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 --version` | 0 | `1.14.2` |
| `.venv/bin/python -m pytest -q tests/test_machine_views.py tests/test_groups.py` | 0 | `8 passed, 1 warning in 0.54s` |
| `.venv/bin/python -m pytest -q tests/test_machine_views.py tests/test_monitor.py tests/test_archive_analysis.py` | 0 | `76 passed, 1 warning in 1.68s` |
| `.venv/bin/python -m pytest -q` | 0 | `91 passed, 1 warning in 2.48s`。警告为 Starlette TestClient 的 httpx 弃用提示。 |
| `node --check wattline/static/monitor.js`、`node --check wattline/static/groups.js`、`node --check wattline/static/locales.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 460 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/resource_browser_smoke.py` | 0 | `PASS`。在中英文分别核对机房、集群列表和详情的 CPU 与内存标签、一次计入的真实零值、容器内存回退、图例和机器来源选择。 |
| `.venv/bin/python tools/browser_smoke.py > artifacts/an232-browser-smoke.jsonl` | 0 | `result: PASS`，Chromium 159.0.8154.6，`page_errors: []`，覆盖中英文。预期的冷归档 `EOFError` 夹具验证了重试。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate unify-machine-cpu-memory --strict` | 0 | `Change 'unify-machine-cpu-memory' is valid` |
| `git diff --check`、`git diff --cached --check` | 0 | 无输出。 |

全量浏览器脚本前两次退出码为 1，均在人员指派窄屏截图处，分别报告元素脱离 DOM 和元素不可见。相同 Chromium 在基线导出的源码副本上通过。将窄屏取证改为整页截图后，保留人员指派与布局断言，最终全量复跑通过。

## 覆盖与限制

- 合成观测覆盖宿主与容器共存、仅宿主、仅容器、同机多容器、分指标回退、真实零值和缺失。加权 CPU 统计以所选 CPU 观测提供的容量计权。无可用容量的内存观测可提供用量，百分比统计采用同源有效配对并有独立覆盖计数。
- 机器近期趋势、总览序列和冷归档依时间桶选择，核对跨来源断线和显式 `source` / `scope`。历史数据库与 gzip 格式兼容，合成归档读取前后字节一致。
- 验证范围为临时 SQLite、合成 API 与 Chromium。真实 SSH、容器运行时、生产数据和其他浏览器运行效果仍需对应环境验证。独立审查及整合由 AN-231 和 Mika 后续处理。
