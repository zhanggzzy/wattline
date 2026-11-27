# AN-236 implementation verification

执行日期为 2026-11-27（Asia/Shanghai）。AN-234 为父任务，AN-235 为独立审查。对应 [tasks.md](tasks.md) 的 1.1、2.1 和 3.1。

## 基准和候选差异

- 固定开发目录的本地分支为 `main`，基准 `HEAD`、`origin/main` 和 `git ls-remote --exit-code origin refs/heads/main` 实查结果均为 `b5b77ba842b5af17b09dc566d8b18eaf54af4189`。
- 候选为该基准上的工作树差异。六个前端和测试文件合计 503 行新增、111 行删除，索引为空。活动 change 含元数据、proposal、design、tasks、两个规范 delta 和本报告。
- `AGENTS.md` 的工作树修改在本次任务开始时已存在，为本地 runtime 注入。索引中的版本经 `git show :AGENTS.md` 核对无注入标记。
- 候选代码和测试的实际 diff 可按下列命令重建，输出管道的 SHA-256 为 `f5a11ffcfc92b24b57df0c8dcc7a2e4831d42e0112142a0ff3894befd3495d9e`。省略管道即可阅读差异。OpenSpec 文件通过 `git ls-files --others --exclude-standard -- openspec/changes/solid-trends-and-grouped-machine-sidebar` 定位。

~~~sh
git diff --binary --no-ext-diff HEAD -- wattline/static/index.html wattline/static/locales.js wattline/static/monitor.css wattline/static/monitor.js tools/browser_smoke.py tools/resource_browser_smoke.py | shasum -a 256
~~~

## 已执行检查

使用现有项目 `.venv` 的 Python 3.11.17、pytest 8.4.2 和 Playwright 1.65.2。Node 为 26.11.0，npm 为 11.20.0，OpenSpec 离线 CLI 为 1.14.2，schema 为 `spec-driven`。

| 命令 | 退出码 | 实际结果 |
| --- | ---: | --- |
| `.venv/bin/python -m pytest -q` | 0 | `91 passed, 1 warning in 2.53s`。警告来自 Starlette TestClient 对 httpx 的弃用提示。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 465 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py` | 0 | Chromium `159.0.8154.6`，`result: PASS`，`page_errors: []`。320px 下验证 18 条旧版总览数据线，缺测线段长度为 `[7, 1]` 和 `[3, 7]`，每种分组总览覆盖 12 条含范围标签的合成序列。归档故障夹具产生预期的 `EOFError` 日志，随后重试成功，单日读取 3 行。 |
| `.venv/bin/python tools/resource_browser_smoke.py` | 0 | `PASS`，摘要包含 `persistent sidebar modes, projected memberships`，同时通过原有资源和分层配置检查。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node --check wattline/static/locales.js` | 0 | 无输出。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate solid-trends-and-grouped-machine-sidebar --strict` | 0 | `Change 'solid-trends-and-grouped-machine-sidebar' is valid`。 |
| `git diff --check` | 0 | 无输出。 |
| `git diff --cached --check` | 0 | 无输出。 |
| 对 change 内所有文件逐一执行 `git diff --no-index --check /dev/null "$artifact"` | 1（各文件） | 无空白错误输出。该命令以 `/dev/null` 为基准，退出码 1 表示新文件有差异。 |

## 覆盖和实现决定

- 浏览器拦截实际 Canvas 绘制调用，匹配图例和数据线的 RGB 值，检验实线、序列重排、切换指标以及轮询时的颜色稳定。房间和集群检查还覆盖图例切换、数据表和分组详情。整机、单卡、全页和归档均经过共享渲染入口。真实分组总览仍沿用每次最多六个分组的接口约束，12 条用例是六组各两种观测范围的合成响应。
- 合成资源 API 测试覆盖合并机器的有效机房、次要来源的集群归属、跨机房集群、多集群入口、缺失归属、有效归属变化时保留或恢复焦点，以及两种密度的状态和选择。手动拖拽和方向键写入同一设备顺序 API，切换到分组、导航和刷新期间的请求计数表明只有手动排序产生顺序写入。
- 320px 视口下打开合并机器时，限制趋势来源选择器所在标签的宽度，保留完整选项和值。分组窄栏将标题最多排成两行，完整名称由标题提示和机器按钮的可访问名称提供。截图位于忽略的 `artifacts/an236-sidebar-cluster-{desktop,mobile,compact}.png`。
- 颜色在当前浏览器页面会话内按序列身份保持。使用相同初始序列集合时，分配顺序与响应顺序无关。不同初始集合或不同访问顺序的新会话可能产生不同的色彩对应。密集图上相近颜色仍可能难以目视区分，图例、读数和数据表可继续用来定位。
- 浏览器验证基于合成数据、临时 SQLite 和 Chromium。覆盖桌面、320px 窄屏布局与键盘焦点。实体触屏、原生下拉弹层的跨平台按键序列以及 Safari、Firefox、Edge 未作本轮实测。实例、采集、服务器配置和数据迁移不在本轮实施范围。

## 交接

执行自测通过。AN-235 负责独立审查。Mika 在审查通过后办理规范同步、归档、提交、推送和远端核验。执行候选留在本地工作树。

## 独立审查

2026-11-27，Reviewer-DeepSeek 在 AN-235 使用 `deepseek/deepseek-flash` 独立审查，结论为通过。审查复核同一六文件差异及基准，复跑 Python 91 项、两套合成 Chromium 检查、465 条 i18n 键校验、JS 语法、OpenSpec strict 和空白检查，均退出 0。另用临时夹具验证 64 像素折叠栏中的键盘排序写入，以及 320 像素手动模式的页面布局。审查截图与完整复跑记录见 AN-235。审查过程为只读。

审查指出两项非阻塞清理建议：纵向侧栏手柄仍接受左右方向键并可能保存顺序，以及未使用的 `data-rail-cluster` 标记。本次发布保留已审查的实现。64 像素窄栏可能断开长名称，完整名称仍可通过提示和可访问名称读取。图表颜色对应在页面会话内保持。

## Mika 整合复查

2026-11-27，重新计算六文件工作树差异哈希，与执行和独立审查记录一致。复跑 `.venv/bin/python -m pytest -q`（91 通过，1 条既有弃用警告）、`.venv/bin/python tools/browser_smoke.py`（PASS，Chromium 159.0.8154.6，脚本报告页面错误为空）、`.venv/bin/python tools/resource_browser_smoke.py`（PASS）、`node tools/test_i18n.cjs`（465 条）、`node --check`（monitor.js 和 locales.js）、`git diff --check` 和 `git diff --cached --check`。命令均退出 0。实际同步 `overview` 既有颜色情景与 `dashboard-focus-layout` 两条新增要求，逐项比对主规范与 delta。OpenSpec 1.14.2 的变更 strict 和 `validate --specs --strict` 分别通过，主规范 12 项。

## 主干核验与归档

2026-11-27，`git push origin HEAD:refs/heads/main` 退出 0，远端从基准 `b5b77ba842b5af17b09dc566d8b18eaf54af4189` 更新到功能及规范提交 `c711b911ae871687cf13f586b884056b82116f34`。`git ls-remote --exit-code origin refs/heads/main` 退出 0 并返回该 SHA。核验后勾选 4.2，OpenSpec 列表确认 5/5，严格校验再次通过，按仓内官方归档技能把完整 change 移入 `openspec/changes/archive/2026-11-27-solid-trends-and-grouped-machine-sidebar/`。归档提交只整理 OpenSpec 记录。
