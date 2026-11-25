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
