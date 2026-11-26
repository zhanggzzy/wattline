# AN-228 implementation verification

实施验证记录于 2026-11-26。AN-226 是产品需求，AN-228 是第一阶段实现，AN-227 负责独立审查。

## 基线与实际改动

- 开始时本地 `main`、`origin/main` 与 `git ls-remote origin refs/heads/main` 均指向 `e5a22e2e6890db9e1cd7505d7a6928017b771613`。提交前再次查询远端，SHA 相同。
- `wattline/` 包含采集身份记录、机器归属、分组和历史查询、机器详情及来源选择改动。`tests/` 和 `tools/` 使用合成观测及临时数据。`README.md` 记录指标口径和来源选择。
- 本记录随实现保存在同一本地提交。交付 SHA 见 AN-228 交接评论。用 `git show --stat <交付 SHA>` 和 `git diff e5a22e2e6890db9e1cd7505d7a6928017b771613 <交付 SHA>` 核对实际文件和代码。提交前通过索引内容核对 `AGENTS.md`，工作树的 Multica 注入块保留原样。

## 命令与结果

| 命令 | 退出码 | 实际结果 |
| --- | --- | --- |
| `node --version`、`npm --version`、`.venv/bin/python --version` | 0 | Node v26.11.0、npm 11.20.0、Python 3.11.17 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 --version` | 0 | `1.14.2` |
| `.venv/bin/python -m pytest -q` | 0 | `90 passed, 1 warning in 2.32s`。警告来自 Starlette TestClient 的 httpx 弃用提示。 |
| `node --check wattline/static/monitor.js`、`node --check wattline/static/groups.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 463 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py > artifacts/an228-browser-smoke.jsonl` | 0 | `result: PASS`，Chromium 159.0.8154.6，页面错误 0，覆盖中英文。归档故障夹具输出预期的 `EOFError`，随后验证了重试与无归档状态。 |
| `.venv/bin/python tools/resource_browser_smoke.py` | 0 | `PASS`，包含同机多来源的合成 API 和浏览器场景、GPU 去重、机房和集群视图、图表及配置。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate unify-machine-views --strict` | 0 | `Change 'unify-machine-views' is valid` |
| `git diff --check`、`git diff --cached --check` | 0 | 无输出。 |

## 场景与限制

- 原始、温层和 v1 gzip 数据测试覆盖同机宿主与容器、仅容器、多张卡重复可见、独立机器、同地址、错误固定身份、未知启动标识、暂时失败、启动标识改变、重启读取及只移除单个采集入口。冷归档分析前后校验归档字节相同。
- 只有匹配的、已通过入口身份校验的 Linux 内核启动 UUID 会合并入口。启动 UUID 被容器隔离时，同机入口可能保持分开。宿主重启期间，已观察到不同启动 UUID 的入口会暂时独立呈现，直到共同证据恢复。
- 机器视图的近期和冷归档趋势只纳入次要入口在当前已核实共同启动周期内的数据。更早样本从原入口的历史来源选择器访问。机房和集群中的 CPU 与内存使用宿主观测，覆盖分母按机器计。SQLite 从 v11 升级至 v12，原历史键和 gzip 格式可继续读取。旧版程序需使用升级前的一致备份回退。
- 检查使用合成数据、临时 SQLite 和 Playwright Chromium。未覆盖真实 SSH、物理设备、真实容器运行时、生产数据或其他浏览器的运行情况。本记录为实施自测，独立审查任务仍待 AN-227 执行。
