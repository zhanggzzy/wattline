# AN-134 independent review

Source: Multica sub-issue AN-134 (01a211ce-009c-7bfa-b50e-c64705caa51c), handoff comment 01a211de-11a6-720d-8984-30ea70e0c7b8, 2026-11-25 Asia/Shanghai. Copied into this change without private node configuration or local deployment data; the screenshots and evidence zip remain internal attachments on that comment. Reviewer model and audited HEAD are recorded below.

# AN-134 独立审查

2026-11-25（Asia/Shanghai），Reviewer-Codex。运行模型 `gpt-6.2-sol`，取自本次 Codex 运行配置。结论为 **需修改**，已完成本轮审查。

- 父任务 AN-102，本轮实现 AN-135。以 AN-102 回复 `01a211cb-89ed-7ef9-b783-2be25b96aed8` 的两张效果图和用户授权 `01a211cd-1958-7bf8-ad8f-01040a68abde` 为对照。
- 活动 change `style-machine-assignee-chips`，schema `spec-driven`。基线及审查时远端 `main` 为 `a738dabfd17d830be6fb8580cc6ea6570a63020d`，实现提交为 `f89e0668378bd8c0cd32b835175b58c02a362e1c`，审查 HEAD 为 `eae4fb43ab9b8ea9ce88282e202d260fd266c23e`。审查范围是基线到审查 HEAD 的完整 diff，共 13 个文件。
- diff 涉及静态前端、合成浏览器测试、文档和 change。登记 API、权限、SQLite 代码及配置文件从基线到审查 HEAD 无差异。`git show :AGENTS.md` 和审查 HEAD 中的版本 SHA-256 均为 `d4b440af9a08b20fec13b0ad8e546d37f4d44bc1f0548264ac2207deb034f334`，索引版本仅含通用约定。工作树原有注入保持原样。

## 需修改

1. **连续空格被折叠，两个合法的人员记录在胶囊中无法区分。** `wattline/config.py:66` 保留姓名内部空格，合成 API 确实创建了不同 ID 的 `Ada Lovelace` 和 `Ada  Lovelace`。`wattline/static/monitor.css:87` 的 `.person-chip` 和 `wattline/static/monitor.css:227` 的 `.assignee-chip-name` 都使用默认 `white-space: normal`。打开使用者弹窗后，两项在截图中显示为同一个名字；给机器选中并保存两项，列表同样如此。Chromium 分别测得两个弹窗姓名都是 84.15625 CSS px，两个列表姓名都是 77.78125 CSS px，DOM 文本仍保留原始空格。用户无法根据胶囊区分要登记的人，且完整姓名的原字面展示没有达成。可在两处姓名样式保留内部空白，同时保持长名换行，并用上述两个实际 API 记录补回归。
2. **新增列使部分原本可完整显示的列表需要横向滚动。** `wattline/static/monitor.css:80` 把表格最小宽度从 604 提到 720 CSS px，`:305` 仍只在容器不宽于 620 CSS px 时切卡片。对同一中英文产品页面，使用英文、同一份合成快照和同一 Chromium，对照两个提交的实测如下。由于还未切卡片，当前版本表格右端指标需横向滚动才可完整读取。页面本身没有横向溢出。设计文档记载了表格内部滚动退路，验收则要求窄屏带标签卡片并避免横向溢出。建议让卡片切换阈值与实际表格占用宽度匹配，或压缩表格固有宽度，并对中间宽度复验。

| 视口 CSS px | 列表可用宽度 | 基线 `scrollWidth` | 被审版 `scrollWidth` |
| ---: | ---: | ---: | ---: |
| 700 | 656 | 673 | 769 |
| 730 | 684 | 684 | 769 |
| 950 | 723 | 723 | 769 |
| 1024 | 737 | 737 | 769 |

## 独立核验

| 命令 | 退出码 | 输出或结果 |
| --- | ---: | --- |
| `.venv/bin/python -m pytest -q` | 0 | `44 passed, 1 warning in 0.89s`。既有 Starlette `TestClient` 的 httpx 弃用提示。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node --check wattline/static/locales.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 311 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py --browser ~/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell` | 0 | `result: PASS`，Chromium `158.0.8127.18`，`page_errors: []`。原始 JSON 为 `an134-browser.json`。 |
| `.venv/bin/python artifacts/an134-repro.py ~/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell` | 0 | 常规交互断言通过。实测空格碰撞和中间宽度回退记录在 `an134-repro.json`，这两项以测量值记录，不充当通过断言。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate style-machine-assignee-chips --strict` | 0 | `Change 'style-machine-assignee-chips' is valid` |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate --specs --strict` | 0 | `Totals: 7 passed, 0 failed (7 items)` |
| `git diff --check`、`git diff --cached --check`、`git diff --check a738dabfd17d830be6fb8580cc6ea6570a63020d..eae4fb43ab9b8ea9ce88282e202d260fd266c23e` | 0 / 0 / 0 | 无输出。 |
| `git ls-remote origin refs/heads/main` | 0 | `a738dabfd17d830be6fb8580cc6ea6570a63020d refs/heads/main` |

环境为 Node 26.11.0、npm 11.20.0、Python 3.11.17、Playwright 1.65.2、本机已缓存的 Chromium Headless Shell。`openspec list/status/instructions apply` 确认根目录、`spec-driven`、四份规划工件齐备，6 项任务中 4 项完成。AN-134 的审查报告证据和 Mika 整合任务保持待办。

对照效果图，桌面第三列确实紧邻状态，名称下方的重复摘要已移除，空分配显示本地化文本，详情页入口仍在配置旁。中英文 1440 与 320 CSS px 下，80 字符和含 `<b>` 的姓名均能完整换行，文本没有生成标记节点，320 px 列表切为带标签的卡片。全空及筛选为空时 `colspan=7`；鼠标拖动、方向键排序、搜索、状态筛选和下一次轮询后姓名刷新均实测通过。

弹窗中已选浅蓝底带勾，未选带加号。原生 checkbox、姓名可访问名称、44 px 点击区和 3 px 焦点环通过。补测用实际鼠标点击胶囊内缘、Tab/Shift+Tab 和 Space，四个语言与宽度组合的最小测得点击区域为 79×44 CSS px。打开、反选、清空、改名、添加及删去仅在草稿选中的人后计数与当前选项一致。暂缓保存请求时，胶囊和动作按钮禁用，Escape 无法关闭；503 后恢复可用并保留草稿与原持久值。标准浏览器回归另覆盖真实临时 SQLite 写失败、表单拒绝、已关联人员删除拒绝、旧单人登记迁移，以及保存、取消和清空。

证据包包含两次浏览器检查的原始 JSON、补充复现脚本及截图。复跑时可将 `an134-repro.py` 放入仓库的忽略目录 `artifacts/`，从审查提交根目录运行以上命令。用基线的 Git 静态资源与同一个进程内 API 获得对照数据。

仅覆盖 Chromium、合成数据、临时 SQLite 和浏览器可访问角色与焦点。Firefox、Safari、真实屏幕阅读器、真实节点、实例历史与部署未实测。本轮保持实现和仓库验证文件只读。请 Mika 安排返工并在复审后处理规范同步、归档和远端 `main` 交付。
