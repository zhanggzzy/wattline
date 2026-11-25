# AN-116 本地实现验证

2026-11-25（Asia/Shanghai），Executor-Codex 在 Wattline 固定开发目录，使用合成节点和临时 SQLite 完成以下自测。

## 核对对象

- 父任务 AN-102，本地实施 AN-116。OpenSpec change 为 `manage-machine-assignees`，`spec-driven`。
- 实施前本地与远端 `main` 基线均为 `04e006cfe067e56deeade6512c12003f272c142c`。
- 实现提交 `d0125d5e3d42657ca3a8d66b58f98f01642ea48b`。可用 `git diff 04e006cfe067e56deeade6512c12003f272c142c d0125d5e3d42657ca3a8d66b58f98f01642ea48b` 复核实际差异。既有工作树 `AGENTS.md` 运行时差异保持原样，暂存版本仅含通用仓库约定。

## 命令和结果

| 命令 | 退出码 | 结果 |
| --- | ---: | --- |
| `.venv/bin/python -m pip check` | 0 | `No broken requirements found.` |
| `.venv/bin/python -m pytest -q` | 0 | `37 passed, 1 warning in 0.97s`。Starlette 提示 TestClient 与 httpx 的用法已弃用。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node --check wattline/static/locales.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 301 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py --browser "$WATTLINE_CHROMIUM" > artifacts/an116-browser.json` | 0 | `result: PASS`，Chromium Headless Shell 158.0.8127.18，`page_errors: []`。下方说明浏览器二进制和覆盖。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate manage-machine-assignees --strict` | 0 | `Change 'manage-machine-assignees' is valid` |
| `git diff --check` / `git diff --cached --check` | 0 / 0 | 检查工作树和实际暂存改动均无输出。 |

浏览器检查使用 Python 3.11.17、Playwright 1.65.2。Playwright 默认查找的 Chromium build 1255 未缓存，首次无参数运行退出码为 1。使用 README 的 `--browser` 参数指定本机已缓存的 Chromium Headless Shell build 1254 后通过。上表以 `WATTLINE_CHROMIUM` 表示该二进制路径。本地忽略目录 `artifacts/` 下有完整 JSON，以及中文、英文的 320px 机器列表与详情截图（`assignees-list-*.png`、`assignees-detail-*.png`）。

## 已覆盖的行为

- SQLite 7→8 导入旧值。覆盖配置节点、动态登记、无字段、空值、空白、同名合并和稳定身份。用 SQLite 触发器在导入一部分后失败，核对旧 schema 和设置原样保留。移除触发器后重启成功，后续再启动保持改名和清空结果。
- 目录与 API 覆盖同源 JSON 防护、合法及非法姓名、同名冲突、重复和失效 ID、共用人员改名、曾删除的 ID 不复用、拦截在用人员删除。机器分别保存各自名单，普通配置保留名单，登记保留普通配置，删除机器仅清理该机器关联，同身份重新登记为空。写失败用 SQLite 触发器验证数据库和快照都保留之前的值。
- 浏览器以旧版合成库启动真实应用 API，在机器列表直接看到迁移结果，从「配置」旁打开合成离线机器的使用者编辑。覆盖名单新增、改名、删除、取消、多选、单项取消和清空，附加检查禁用的机器仍显示共享姓名。12 次非法浏览器提交均返回 422，草稿和原登记保留。关联人员删除返回 409，注入关联写失败返回 503，解除故障后使用原草稿重试成功。
- 中英文分别在 1440px 和 320px 校验列表、详情的多人名称、名称分隔、80 字符长名称自动换行、字面标记字符和相邻按钮位置。通过 README 浏览器全套回归，包括原有 GPU 进程账号显示。

## 兼容性与交接

旧配置格式继续有效。API 客户端需切换到 `assigned_users` 和专用的 `/assignees` 接口。人员名按修剪后的精确拼写去重，实际同名人员可用不同的显示名称区分。升级前保留一致的数据目录备份，回退旧程序时同时恢复该备份。升级后的记录留在升级后的数据库中。

验证范围为合成环境和 Chromium。Firefox、Safari、真实节点、真实历史库及实例部署均在本轮验证范围之外。AN-115 独立审查、Mika 的主干整合与远端 SHA 核对仍待进行。活动 change 保留对应待办。

## AN-102 主干交付与归档

2026-11-25（Asia/Shanghai），Mika 核对 [AN-115 独立审查](review-an-115.md)（Reviewer-DeepSeek，`deepseek/deepseek-flash`）和被审 HEAD `4dfc82c4b92e344e5f06e49790d8fed81a5d4b1d`。审查提交 `843087d40ecbf9558a7118661e03a04ef3b8d03e` 与被审 HEAD 的差异仅为 OpenSpec 审查报告及任务勾选。交付基线为 `04e006cfe067e56deeade6512c12003f272c142c`。

| 命令 | 退出码 | 实际结果 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | 37 passed, 1 warning in 0.98s，警告为 Starlette TestClient 的 httpx 弃用提示。 |
| `node --check wattline/static/monitor.js`、`node --check wattline/static/locales.js`、`node tools/test_i18n.cjs` | 0 | 语法通过，301 个翻译键通过。 |
| `.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"` | 0 | Chromium 158.0.8127.18，`PASS`，中英文界面，`page_errors: []`。 |
| `git diff --check`、`git diff --cached --check`、`git diff --check 04e006c..HEAD` | 0 | 无空白错误。 |
| `git push origin 843087d40ecbf9558a7118661e03a04ef3b8d03e:refs/heads/main`、`git ls-remote --exit-code origin refs/heads/main` | 0 | 远端 main 快进至该被审提交，回读 SHA 相同。此为任务 3.3 的核验，验收评论记录包含归档的最终远端提交。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate --specs --strict` | 0 | 6 项规范通过。保留 machine-registry 目的，按受审 delta 修改 4 项要求并新增 2 项。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate manage-machine-assignees --strict`、`OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 archive manage-machine-assignees --yes --skip-specs` | 0 | 变更有效，6/6 任务完成。主规范已先同步，CLI 归档为 `2026-11-25-manage-machine-assignees`。 |

验证使用合成数据与 Chromium。其他浏览器、真实节点、用户实例和部署级升级或回退未实测。审查结论及非阻塞边界见 AN-115 报告。
