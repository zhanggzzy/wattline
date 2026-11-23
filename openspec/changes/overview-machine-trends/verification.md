# Verification

以下为 Executor-OMP 于 2026-11-23（Asia/Shanghai）完成的 AN-55 自测。随后 AN-54 独立审查给出「需修改」结论。

## Baseline

- 开发树为 Wattline 固定仓库。
- 分支：`main`，基线 `ca2469171341e259e29488ec3247203df4723536`，与 `origin/main` 一致。
- 工作树既有 `AGENTS.md` Multica runtime 注入改动保持未暂存；未读取或提交私有节点资料。
- 现有 change `overview-machine-trends` 复用，补充 `design.md`、`tasks.md` 与本记录。

## Commands and results

### Python and JS

```sh
.venv/bin/python -m pytest -q
# 17 passed, 1 warning in 0.61s

node --check wattline/static/monitor.js
# exit 0
```

新增 HTTP 覆盖：`test_overview_history_returns_aligned_machine_series_and_metrics`。
两台合成机器在同一 24 小时窗口内曲线明显不同；其中一台首个时段缺失。
断言 `machines` 顺序与值列对齐、GPU `0` 为有效值、缺失为 `null` 且 `breaks`
为真；CPU、内存、功耗切换后的单位值；不支持指标、越界窗口和总览 GPU 参数
返回 422；带机器详情的响应不含 `machines`，保持原契约。

### Synthetic browser check

```sh
.venv/bin/python tools/browser_smoke.py
# {"result":"PASS","browser":"159.0.8154.6","page_errors":[],
#  "mutations":3,"history_queries":11,"screenshots":11,...}
```

覆盖：

- 桌面和 390、320、640、1024 宽度下「需要关注」→「最近 24 小时趋势」→
  「机器列表」纵向顺序，无横向溢出。
- 默认 `data-overview-metric="gpu"` 选中，首次请求为
  `metric=gpu&hours=24`（无 `machine`），图例列出三台机器且无“平均”。
- 切换到 CPU 后请求 `metric=cpu&hours=24`；切换到功耗后图例含 `W`。
- 从机器详情选择 7 天后返回总览，最新总览请求仍为 `hours=24`。
- 同名机器图例追加地址；离线机器无历史时折线缺失，另一台中间缺失时段断开。
- 机器详情原有 7 天窗口、键盘样本播报、配置与移除交互均通过。
- 截图：`artifacts/desktop.png`、`artifacts/overview-trend.png`、
  `artifacts/mobile.png`、`artifacts/mobile-list.png` 等（`artifacts/` 被忽略，不入库）。

### OpenSpec and diff

```sh
OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate overview-machine-trends --strict
# Change 'overview-machine-trends' is valid

git diff --check && git diff --cached --check
# exit 0
```

## Commit

- 实现提交：`c489a3565452f0115e3799977e64ace1d01ef828`（parent
  `ca2469171341e259e29488ec3247203df4723536`），包含源码、测试、浏览器检查与
  本 change 的 proposal/spec/design/tasks/本记录。
- 提交后核对 `git show :AGENTS.md` 仍为 39 行通用仓库约定；工作树 255 行的
  Multica runtime 注入块保持未暂存，未进入提交。
- 未推送远端，未执行部署、实例更新或真实采集。

## Limits

- 未连接真实节点、未启动采集或归档、未改动用户实例、部署目录或私有资料。
- 浏览器检查使用合成 API 响应；真实生产历史分布、超多机器图例密度和性能未覆盖。
- AN-54 独立审查的结论与证据见该任务的 `an54-review.md`。AN-56 复审、规范同步与归档待后续阶段。

## AN-57 整改验证

Executor-Codex 于 2026-11-23（Asia/Shanghai）执行。证据对应 `tasks.md` 的 4.1–4.3，复审对应 3.3。

| 对象 | SHA |
| --- | --- |
| AN-53 整体改动基线，本地 `origin/main` 引用 | `ca2469171341e259e29488ec3247203df4723536` |
| AN-57 整改基线，AN-54 审查时的本地 HEAD | `feb29a22126b34c7f573690507aa1e138b4b875c` |
| AN-57 整改提交 | `087e33bb450dbfc7e21425802ec70bbe6e450abc` |
| 开工时 `git ls-remote origin refs/heads/main` 返回的 SHA | `a3156bf1bf244d1ab071c210a86f8bb5b25fff76` |

整改 diff 为 `git diff feb29a2 087e33b`，整体 diff 为 `git diff ca24691 087e33b`。整改提交涉及 10 个文件，新增 323 行、删除 79 行。远端主干在开工时已与本地跟踪引用不同，最终整合基线和远端提交由 Mika 核验。

### 命令与结果

| 命令 | 退出码与输出 |
| --- | --- |
| `node -v`、`npm -v`、`.venv/bin/python --version` | 均为 0。Node `v26.11.0`、npm `11.20.0`、Python `3.11.17`。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 --version` | 0，`1.14.2`。按 OpenSpec README 核验 skills 的 SHA-256，输出 `6 official skills: SHA-256 PASS`。 |
| 同版本 `list --json`、`status --change overview-machine-trends --json` 及各 artifact 的 `instructions` | 0，确认仓库内 root、`spec-driven` 和四类规划文件。规划更新后 `instructions apply --change overview-machine-trends --json` 返回 `ready`。 |
| `.venv/bin/python -m pytest -q` | 0，`18 passed, 1 warning in 0.72s`。警告来自 Starlette TestClient 对 `httpx` 的弃用提示。 |
| `node --check wattline/static/monitor.js` | 0，无输出。 |
| `.venv/bin/python tools/browser_smoke.py` | 0，`PASS`，Chromium `159.0.8154.6`，`page_errors: []`，原场景 3 次合成写请求、11 次历史查询、11 张截图。新增场景见下。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate overview-machine-trends --strict` | 0，`Change 'overview-machine-trends' is valid`。 |
| `git diff --check`、`git diff --cached --check`、`git diff --check feb29a2 087e33b`、`git diff --check ca24691 087e33b` | 均为 0，无输出。 |
| `git show :AGENTS.md`、`git show HEAD:AGENTS.md` 字节比较与工作树 `AGENTS.md` 哈希复核 | 0，Git 索引为原有 39 行通用约定，工作树注入文件哈希与开工时相同。暂存树路径及注入标识扫描返回 1，表示没有匹配项。 |

### 回归证据

- `test_overview_history_uses_each_machines_recorded_continuity` 使用临时 SQLite 与固定时钟。10 秒与 300 秒机器共用 216 秒显示桶，慢频样本按记录的时效阈值连续，覆盖对齐空位、真实空值、采样超时、重启和 0。另核对窗口两端包含、窗外样本排除，以及机器和单卡详情的请求与采样结果。
- Chromium 新场景在 `320` px 渲染 9 台合成机器。两个同名同地址的 80 字符标签按字面显示且各有机器 ID，图例和提示均检查实际换行和边界。比对 Canvas 中图例样线与实际曲线的颜色和线型。鼠标读取起始样本显示 `0%`。
- 实际笔画统计 `slow_segment_edges: [7, 1]`、`lapse_segment_edges: [3, 7]`。慢频序列的 8 个正常样本连接为 7 段，经过显式空样本后另起一段。另一台机器经过无记录的对齐空位后，由下一有效样本上的断点标记另起一段。
- 浏览器检查的前两次新增场景因测试探针未执行、笔宽精确相等过滤失效各返回 1。修正探针后，全量浏览器检查返回 0。现有冒烟场景同时覆盖卡片布局、总览指标切换、详情时间窗、导航和列表交互。

### 验证限制与复审

- 仅用合成数据与 Chromium，范围未包含 Firefox、Safari、128 台机器满载及真实历史性能。本轮无实例访问、真实采集、部署或推送。
- 整改提交与证据提交的文件快照已去除验证文档中的本机绝对路径。AN-55 的两份本地提交作为原审查证据保留，Mika 整合时须将其排除在待推送历史之外。
- 本节记录实施者自测。AN-56 独立复审、规范同步、归档与 main 整合待完成。
