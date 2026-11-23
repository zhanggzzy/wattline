# AN-59 主干整合验证

Executor-Codex（GPT-6）于 2026-11-23（Asia/Shanghai）完成整合和实施者自测，对应 [任务 5.1 和 5.2](tasks.md)。AN-56 的审查对象是整合前的 `a5cbee2`。整合候选由 AN-58 独立复审。

## 交付范围

- 候选分支为 `an-59/overview-machine-trends`。基准为远端 `main` 的 `a3156bf1bf244d1ab071c210a86f8bb5b25fff76`，由 `git ls-remote origin refs/heads/main` 核实。Multica AN-59 交接评论记录具体候选 SHA。
- 源变更为共同基准 `ca2469171341e259e29488ec3247203df4723536` 到已审树 `a5cbee214848a991c3ab5efcf2d94cdca359b477` 的净差异。候选以远端基准为唯一父提交。原本地 `main` 保留在 `a5cbee2`。
- 执行 `git diff a3156bf an-59/overview-machine-trends` 可查阅实际 diff。按 `git diff a3156bf an-59/overview-machine-trends -- tests tools wattline | git hash-object --stdin` 核对实现和测试差异的指纹 `ada409e8eff9a11e5c8dd012cc88e35013ac08c6`。
- 后端和 pytest 文件的快照与已审树一致。前端在主干的多图与本地化结构中接入逐机序列。总览及聚焦总览固定查询 24 小时，每张聚焦图按所选指标独立请求。沿用样本表和键盘读数，在样本表对机器标签做转义，图例和提示按字面文本渲染。整合时修正了 AN-56 记录的提示框阴影单位。
- 合并了两侧 Browser smoke 的行为检查。聚焦图断言选择绘图 canvas，图例 canvas 由逐机样线断言覆盖。

## 命令与输出

| 命令 | 退出码与输出 |
| --- | --- |
| `node -v`、`npm -v`、`.venv/bin/python --version` | 均为 0，Node `v26.11.0`、npm `11.20.0`、Python `3.11.17`。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 --version` 及 OpenSpec README 的 skills SHA-256 检查 | 均为 0，`1.14.2`、`6 official skills: SHA-256 PASS`。 |
| 同版本 `list --json`、`status --change overview-machine-trends --json`、`instructions {proposal,specs,design,tasks,apply} --change overview-machine-trends --json` | 均为 0，确认仓库 root、`spec-driven`、四类产物和实施状态 `ready`。 |
| `.venv/bin/python -m pytest -q` | 首次与浏览器并行运行返回 1，`1 failed, 17 passed, 1 warning in 3.51s`。既有 `test_background_scheduling_timeout_disk_fault_boot_and_shutdown` 等待第二次采样超时。调度逻辑与该测试无差异。两次单独复跑均返回 0，`18 passed, 1 warning in 0.62s`。警告来自 Starlette TestClient 对 `httpx` 的弃用提示。 |
| `node --check wattline/static/monitor.js`、`node --check wattline/static/locales.js` | 均为 0，无输出。 |
| `node tools/test_i18n.cjs` | 0，`PASS: 274 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage`。 |
| `.venv/bin/python tools/browser_smoke.py` | 0，`PASS`，Chromium `159.0.8154.6`，`page_errors: []`，合成历史请求 108 次，合成写请求 7 次，报告 26 张截图。12 个中英文对话框组合、19 个指标布局宽度、9 次焦点恢复场景通过。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate overview-machine-trends --strict` | 0，`Change 'overview-machine-trends' is valid`。 |
| `git diff --check`、`git diff --cached --check`、`git diff --check a3156bf HEAD` | 均为 0，无输出。 |
| `git show :AGENTS.md`、`git diff --cached --exit-code -- AGENTS.md`、`git hash-object AGENTS.md` | 索引为基准的 39 行通用约定，暂存差异为空，工作树注入文件与开工哈希相同。 |
| `git rev-list --parents a3156bf..HEAD`、`git merge-base --is-ancestor {c489a35,feb29a2,a5cbee2} HEAD`（逐一执行） | 候选范围只有一份提交，唯一父提交为基准。三个旧本地提交的祖先查询各返回 1。候选范围逐提交核对文件清单、提交信息和新增行，机器本地路径、运行时块和私有实例资料扫描均无匹配。 |

## 浏览器覆盖

- 验证关注、趋势、机器列表依次全宽排列。验证默认 GPU 利用率、CPU、内存和功耗四个总览指标均请求 24 小时，机器或单卡详情仍可选择 7 天，返回总览仍为 24 小时。
- 320 px 下验证 9 台合成机器的配色和线型、同名同地址的机器 ID、图例与提示换行、样本表按字面呈现标签，以及起点 `0%`。实测慢频样线分段边数为 `[7, 1]`，超时样线为 `[3, 7]`。
- 聚焦布局在 320–1440 px 的六个宽度保持独立绘图，覆盖多指标、单指标失败、3 个过期请求的竞争处理及键盘退出。英文聚焦总览验证逐机 W 读数、样本表和辅助技术读数，并验证从总览继承所选指标。
- 保留紧凑导航、GPU 详情、实际内存用量、无上限容器、列表交互、中英文持久化和对话框的主干冒烟覆盖。

验证使用合成 API、临时 SQLite 和 Chromium。Firefox、Safari、128 台满载与实际历史性能超出本轮覆盖。复审、规范同步、归档及 Mika 的远端交付见 [剩余任务](tasks.md)。
