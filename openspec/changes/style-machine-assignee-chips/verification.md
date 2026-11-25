# AN-135 本地实现验证

2026-11-25（Asia/Shanghai），Executor-OMP 在 Wattline 固定开发目录，使用合成节点、临时 SQLite 和 Chromium 完成以下自测。实现提交为 `f89e0668378bd8c0cd32b835175b58c02a362e1c`，父提交为分诊基线 `a738dabfd17d830be6fb8580cc6ea6570a63020d`。

## 核对对象

- 父任务 AN-102，本轮实施 AN-135；独立审查由 AN-134 负责。
- OpenSpec change `style-machine-assignee-chips`，`spec-driven`。修改 `machine-registry` 的编辑器与展示要求；API、配置、权限和 SQLite 契约未改。
- 用户确认的效果图：AN-102 评论 `01a211c9-15c0-7134-96aa-02a99e73e213` 下回复 `01a211cb-89ed-7ef9-b783-2be25b96aed8`。开发授权：评论 `01a211cd-1958-7bf8-ad8f-01040a68abde`。
- 工作树既有的 `AGENTS.md` 运行时注入保持未暂存、未提交；提交只含通用约定之外的本次改动。

## 命令和结果

| 命令 | 退出码 | 实际结果 |
| --- | ---: | --- |
| `.venv/bin/python -m pytest -q` | 0 | `44 passed, 1 warning in 0.93s`。警告为 Starlette `TestClient` 的 httpx 弃用提示。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node --check wattline/static/locales.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 311 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"` | 0 | `result: PASS`，Chromium Headless Shell `158.0.8127.18`，`page_errors: []`。完整 JSON 在忽略目录 `artifacts/an135-browser.json`。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate style-machine-assignee-chips --strict` | 0 | `Change 'style-machine-assignee-chips' is valid` |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate --specs --strict` | 0 | 7 项主规范全部通过。 |
| `git diff --check` / `git diff --cached --check` / `git diff --check a738dab..HEAD` | 0 / 0 / 0 | 无输出。 |

环境为 Python 3.11.17、Playwright 1.65.2。Playwright 默认 Chromium build 未缓存，按 README 的 `--browser` 参数使用本机已缓存的 headless shell。

## 已覆盖的行为

- 机器列表：中英文表头前 3 项分别为「机器、状态、使用者」和「Machine、Status、Assignees」。使用者单元格仅含只读胶囊；空值显示「未登记 / Not assigned」；机器名称下不再出现旧摘要。
- 字面安全：姓名 `李工 <b>值班</b>` 在列表、详情、名单和选择器中按文本显示，未创建 `<b>` 元素。80 字符姓名在 1440px 和 320px 的中英文布局中完整换行，单元格与每个胶囊的 `right`、`scrollWidth`、`scrollHeight` 均在可用边界内。
- 窄屏：320px 时使用者列变为带本地化字段标签的整行卡片，状态也不再依赖中文 `data-label` 字符串即可占满整行，页面无横向溢出。390px 总览同样保留胶囊与标签。
- 选择器：初始、鼠标点选、取消、空格键切换、清空选择、改名和名单增删后，`#assignee-count` 的中英文选中数与勾选输入一致。选中态有勾号与浅蓝底，未选态有加号与描边。
- 无障碍：选择器保留原生 checkbox 与 label，`get_by_role("checkbox", name=姓名)` 可精确定位；装饰符号为 `aria-hidden` 生成的 CSS 内容。键盘 Tab/Shift+Tab 后焦点环可见，胶囊实测 `92×44` CSS px。保存失败时选择器和草稿保持，失败重试成功。
- 失败与兼容：原有 12 次非法姓名提交仍返回 422 并保留草稿；关联人员删除返回 409；注入关联写失败返回 503 且快照保留。取消选择不落库，保存与清空按原 API 写入。

截图在忽略目录 `artifacts/`：`assignees-list-desktop-zh-CN.png`、`assignees-list-zh-CN.png`、`assignees-list-en.png`、`assignees-detail-zh-CN.png`、`assignees-detail-en.png`、`assignee-picker-zh-CN.png`。可与用户确认的两张效果图对照。

## 兼容性与交接

快照字段 `people` 与 `machines[].assigned_users`、`PUT /api/machines/{id}/assignees`、人员名单 API、权限校验、持久化和数据库 schema 不变，无迁移。详情页原「使用者」入口和摘要保留。

验证范围为合成数据与 Chromium。Firefox、Safari、真实节点、真实历史库、用户实例和部署均未实测。AN-134 独立审查、Mika 的主干整合与远端 SHA 核对仍待进行；活动 change 与审查/整合任务保持未完成。

## AN-138 返工验证

2026-11-25（Asia/Shanghai），Executor-OMP 在 Wattline 固定开发目录完成 AN-134 审查的两项返工自测。被审基线仍为 `eae4fb43ab9b8ea9ce88282e202d260fd266c23e`（AN-134 审查 HEAD）；审查结论、实测值和证据包见 [`review-an-134.md`](review-an-134.md)。本轮只改静态前端、合成浏览器回归、文档和 change，登记 API、权限、SQLite 与配置不变，`AGENTS.md` 运行时注入继续未暂存。

### 命令和结果

| 命令 | 退出码 | 实际结果 |
| --- | ---: | --- |
| `.venv/bin/python -m pytest -q` | 0 | `44 passed, 1 warning in 0.84s`。警告仍为 Starlette `TestClient` 的 httpx 弃用提示。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node --check wattline/static/locales.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 311 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"` | 0 | `result: PASS`，Chromium `158.0.8127.18`，`page_errors: []`。新增 `assignee_responsive` 结果见下；原始 JSON 在忽略目录 `artifacts/an138-browser.json`。 |
| `.venv/bin/python artifacts/an134-repro.py <同上 Chromium>` | 0 | 沿用 AN-134 复现脚本重跑全部交互与布局断言通过；`breakpoints` 显示 700/730/950/1024 均切卡片且 `scrollWidth == clientWidth`。输出在忽略目录 `artifacts/an138-repro.json`。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate style-machine-assignee-chips --strict` | 0 | `Change 'style-machine-assignee-chips' is valid` |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate --specs --strict` | 0 | `Totals: 7 passed, 0 failed (7 items)` |
| `git diff --check`、`git diff --cached --check` | 0 / 0 | 无输出。 |

### 两项问题的闭环

1. **连续空格被折叠。** 列表 `.person-chip` 与弹窗 `.assignee-chip-name` 增加 `white-space: pre-wrap`，保留原有 `overflow-wrap: anywhere`。合成 API 建立两个 ID 不同的 `Ada Lovelace` 与 `Ada  Lovelace`；列表胶囊渲染宽度实测 `77.78125` 与 `80.96875` CSS px，弹窗为 `84.15625` 与 `87.484375`，`textContent` 分别为单空格和双空格原文，`white-space` 均为 `pre-wrap`。80 字符姓名在 1440 和 320 CSS px 下仍完整换行，没有加宽或截断（既有 `check_people_directory` 断言继续通过）。
2. **中等宽度横向滚动。** 七列表格在英文短夹具下实测固有宽度 `769` CSS px，机器名与地址取 170 px 上限时实测 `827.578125`；容器查询阈值由 620 调为 830，使表格只在完整宽度能容纳时出现。真实页面容器与视口实测：

| 视口 CSS px | 容器 CSS px | 布局 | 列表 `scrollWidth` / `clientWidth` | 四个指标字段 |
| ---: | ---: | --- | --- | --- |
| 320 | 286 | 卡片 | 286 / 286 | 可见，本地化标签 |
| 700 | 656 | 卡片 | 656 / 656 | 可见 |
| 730 | 684 | 卡片 | 684 / 684 | 可见 |
| 950 | 723 | 卡片 | 723 / 723 | 可见 |
| 1024 | 737 | 卡片 | 737 / 737 | 可见 |
| 1440 | 1138 | 表格 | 1138 / 1138 | 可见 |

中英文 320 和 1440 均无页面横向溢出（`documentElement.scrollWidth <= innerWidth`）。实际切换边界由 1024 到 1440 视口二分实测：最后一个卡片视口 1123（容器 830），第一个表格视口 1124（容器 831），两侧列表和页面都不横向滚动；表格侧容器 831 已超过长短名夹具的固有宽度上限 828。截图在忽略目录：`assignee-responsive-1024-en.png`、`assignee-responsive-320-en.png`、`assignee-responsive-boundary-en.png`、`assignee-chip-spacing.png`。

### 回归范围与限制

仓库合成 Chromium 回归新增独立 `check_assignee_responsive`，覆盖双空格姓名在列表与选择器的字面显示及渲染宽度差、320/700/730/950/1024/1440 中英文布局、卡片与表格两侧的 `scrollWidth`、页面无横向溢出、四个指标字段可见，以及二分得到的切换边界。既有人员名单回归继续覆盖列位、空值、字面安全、80 字符换行、选择计数、鼠标/空格、焦点、44 px 命中区、保存取消、失败草稿、禁用态和旧单人登记迁移。

范围为 Chromium、合成节点、临时 SQLite；Firefox、Safari、真实屏幕阅读器、真实节点、用户实例与部署未实测。AN-137 独立复审、Mika 的规范同步/归档和远端 `main` 核对仍待进行，活动 change 保持未归档。
