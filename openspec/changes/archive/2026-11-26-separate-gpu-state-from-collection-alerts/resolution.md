# AN-217 验证报告

- 父任务 AN-215。独立审查任务 AN-216。
- 基线 `0123c748d9c628902105738a7e5a080aaf3e92d4`（`origin/main`）。
- OpenSpec change `separate-gpu-state-from-collection-alerts`，官方 CLI 1.14.2。
- 执行者 Executor-Codex。Multica 任务配置模型 `gpt-6.2-sol`。
- 2026-11-26 本地验证。macOS 26.6 arm64、Python 3.11.17、Node 26.11.0、Playwright 1.65.2、Chromium 159.0.8154.6。
- 源码与测试的稳定 patch ID 为 `45e60f37c5759af5310099a1100345a3131d69b8`。可用 `git diff HEAD^ HEAD -- wattline tests tools | git patch-id --stable` 复核首列。

## 修复与覆盖

| 场景 | 实测结果 |
| --- | --- |
| 有效样本包含空闲和占用未确认设备 | GPU 状态仍为 `free` 和 `unknown`。中文设备表显示「空闲」和「占用未确认」。即使存在其他采集覆盖诊断，活动告警为空。 |
| 采样失败 | 固定宿主身份无法核实，机器状态为 `unknown`，告警中心记录 `collection` 和对应原因。 |
| 采样超时 | 合成采样协程超过实际 `wait_for` 时限，机器状态为 `offline`，记录 `collection` 和超时原因。 |
| 有效数据过期 | 使用机器级有效期。截止前 1 ms 无告警，到达截止时记录 `collection`，证据为 `sample_stale`。 |
| 恢复 | 三个触发场景均收到占用仍未确认且带诊断的有效样本。原事件记录 `collection_resumed` 和恢复时间，活动告警为空。 |
| 过期边界和写入顺序 | 在上一份样本过期前开始、过期后收到的有效新样本按接收时刻恢复。迟写的已被取代样本和到达时已过期的样本均未误清告警。 |
| Windows 仅采 GPU | 不可用探针触发 `collection` 且保留上一有效样本时间。已核实的空清单算作有效样本。 |

## 复跑

从 Wattline 仓库根目录运行。

~~~sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[test,browser-test]'
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -q tests/test_monitor.py -k 'collection_alerts_are_independent_of_gpu_occupancy or collection_recovery_respects_sample_timing'
.venv/bin/python -m pytest -q tests/test_windows.py
.venv/bin/python -m pytest -q
node --check wattline/static/monitor.js
node --check wattline/static/locales.js
node tools/test_i18n.cjs
.venv/bin/python tools/browser_smoke.py
.venv/bin/python tools/resource_browser_smoke.py
OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate separate-gpu-state-from-collection-alerts --strict
git diff --check
git diff --cached --check
~~~

| 检查 | 输出摘要 | 退出码 |
| --- | --- | --- |
| 告警和时序回归 | `4 passed, 37 deselected, 1 warning` | 0 |
| Windows 采样 | `7 passed, 1 warning` | 0 |
| 全量 pytest | `55 passed, 1 warning` | 0 |
| JS 语法及 i18n | 语法检查无输出。i18n 输出 `PASS: 415 message keys`，涵盖插值、消息一致性和回退。 | 0 |
| 合成仪表盘浏览器检查 | `"result": "PASS"`，`"page_errors": []`，覆盖两种设备状态的中文文案。 | 0 |
| 合成资源浏览器检查 | `PASS`，涵盖持久化告警、存储、分组和导航。 | 0 |
| OpenSpec strict | `Change 'separate-gpu-state-from-collection-alerts' is valid` | 0 |
| Git diff 检查 | 工作树与暂存区检查均无输出。 | 0 |

pytest 的警告来自 Starlette 对使用 httpx 的 TestClient 的弃用提示。基线复现也出现同一警告。基线证据见 [问题定位](diagnosis.md)。

## 验证边界

验证使用合成探针数据、注入时钟、临时 SQLite 和 Chromium。本次自测未覆盖真实 SSH、GPU 驱动、共享环境及其他浏览器引擎。样本有效期依服务端记录的采样开始与收到时间判定，远端时钟用于历史信息。已有机器 `offline` 和 `stale` 事件保留 OpenSpec 描述的恢复路径，当前代码使用 `collection` 记录新机器告警。独立审查由 AN-216 执行，整合与归档待审查。
