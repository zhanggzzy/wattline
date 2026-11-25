# AN-109 独立复审报告

2026-11-25（Asia/Shanghai），Reviewer-DeepSeek，Multica 运行时配置模型 `deepseek/deepseek-flash`。复审依据为 AN-102、[AN-103 原审查](review-an-103.md)、[AN-105 复审](review-an-105.md)、AN-110 交接和 OpenSpec `add-machine-assigned-user`。

**结论为通过。** AN-105 的 P2 已修复：机器设置弹窗的原始输入不再在提交前被修剪或截断，真实设置 API 返回 422，弹窗保留草稿与原登记。未发现新的阻塞或 P2 问题。

## 被审提交

- 实现提交为 `3e213580cce063733f88fbfdf5efb6f0416db2aa`（`AN-110: preserve invalid assigned-user drafts for validation`），交接 HEAD 为 `0bf965277a0f3ec915d64133a59934d49a3d7d0d`。
- `git ls-remote origin refs/heads/main` 返回产品基线 `9b698f731b50c3eae6385cdbd23dd7a2bac1af40`（退出码 0）。全部改动仍在本地 `main`，未推送。
- 索引中的 `AGENTS.md` 仅含通用约定；工作树原有的运行时注入差异原样保留，未纳入复审改动。

## 独立复测方法

复测不复用 `tools/browser_smoke.py` 的实现：另写独立探针，通过 Playwright Chromium 打开仓库静态页面，把浏览器的全部请求转发到同进程 FastAPI `create_app`（`TestClient`，`base_url=http://localhost`），使用停用的合成机器 `an109-fixture` 与临时目录 SQLite。每次先经 API 写入「原登记」，再从机器详情打开设置弹窗操作。

拒绝用例逐次断言：

1. 输入控件值等于待测原始值（未在按键/粘贴阶段被改写）；
2. 捕获的 `PUT /api/machines/an109-fixture/settings` 请求体中 `assigned_user` 与控件值逐字符相等；
3. 响应 422；
4. `#machine-error` 可见，文本为「请填写不超过 80 个字符的单行使用者名称。」；
5. 弹窗仍打开，控件仍保留完整草稿；
6. `GET /api/snapshot` 的 `assigned_user` 仍为「原登记」；
7. `machine_settings.settings` 整行与操作前基线逐字节相等。

| 用例（转义形式） | 输入方式 | 实际发送值 | 状态 |
| --- | --- | --- | --- |
| `\u2028` | 键盘直接插入 | `\u2028` | 422 |
| `\u2029` | 键盘直接插入 | `\u2029` | 422 |
| `\u2028next` | 剪贴板粘贴 | 原值 | 422 |
| `next\u2028` | 剪贴板粘贴 | 原值 | 422 |
| `\u2029next` | 剪贴板粘贴 | 原值 | 422 |
| `next\u2029` | 剪贴板粘贴 | 原值 | 422 |
| `first\u2028second\u2029third` | 剪贴板粘贴 | 原值 | 422 |
| 80 个 `a` + `\u2028` | 剪贴板粘贴 | 原值 | 422 |
| 81 个 `a` | 剪贴板粘贴 | 原值 | 422 |
| `\u2028` 后按 Enter | 键盘 + 提交 | `\u2028` | 422 |

每次 422 后快照与 SQLite 均保持「原登记」，草稿、错误提示和打开的弹窗均符合验收。AN-105 报告中「`\u2029` 被转成 `null` 清空」「`next\u2028` 被改为 `next`」两种现象均不再出现。

成功路径同一弹窗复测：

- 粘贴 `"  " + 80 字符合法值 + "  "` 后按 Enter：请求体保留首尾空格，API 200，页面与快照显示修剪后的值，SQLite 存修剪值，弹窗关闭；重开设置回填该值且无错误。
- 分别以空串和纯普通空格主动清空：均 200，快照为 `null`，SQLite 移除 `assigned_user` 键，重开设置为空。
- 切到英文界面后输入 `\u2028` 保存：显示 `Enter the assigned user on one line using at most 80 characters.`，仍为 422，原值为空未被改写。

### 单行控件与文档描述复核

同一 Chromium 对比 `input[type=text]` 与一行高 `textarea` 的粘贴结果：

| 粘贴内容 | 单行 input | textarea |
| --- | --- | --- |
| `\u2028` / `\u2029` | 保留 | 保留 |
| `\r` / `\n` | 变为空 | 规范为 `\n` |
| `a\r\nb` | 变为 `a b`（静默改写） | `a\nb` |
| `\t` / `\u0085` | 保留 | 保留 |

因此 [design.md](design.md) 中「单行文本输入会在粘贴时丢弃或改写 CR/LF，一行高文本框规范为 LF 后仍被 API 拒绝」的表述与实际一致；同时移除 `maxlength` 后，浏览器不会把「80 字符合法值 + 分隔符」截断成合法值。`textarea` 是保留待拒绝字符、交由 API 裁决的必要条件，不是规避校验。

## 现有范围复核

- **422 输入覆盖**：`tests/test_monitor.py` 的拒绝集合已扩为 18 个值（首部、尾部、内部、仅拒绝字符、CR、C1、U+2028/U+2029），每值 422 后重新读取快照并按 `history_key` 校验 SQLite 仍为「张三」；`lab-02` 写入「  李四  」后修剪为「李四」。
- **机器隔离与持久化**：同一测试覆盖两机各自赋值、修改一机不影响另一机、移除一机删除其设置；`test_machine_settings_round_trip…` 覆盖重启后恢复 `assigned_user` 与 SSH 超时。
- **失败处理**：`test_assigned_user_write_failure_is_reported_without_changing_the_view` 保留 503 且快照为旧值。
- **双语与 320px**：`tools/browser_smoke.py` 的 `assigned_user_settings` 实跑 12 次 422、草稿与 SQLite 保留、Enter 修剪、空格与显式清空全部为真；`assigned_user_long` 中英文均为 `scrollWidth = clientWidth = 288`、`scrollHeight = clientHeight = 90`、右边缘 304px。
- **文档**：proposal、design、spec delta、tasks 与 README 已同步 AN-110 行为；spec 新增「弹窗内输入/粘贴非法值显示失败、保留草稿与原登记」场景，与实现一致。

## 命令和结果

| 命令 | 退出码 | 实际输出 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | `36 passed, 1 warning in 0.75s`。警告为 Starlette TestClient 的 httpx 弃用提示。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 286 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"` | 0 | `result: PASS`，Chromium `158.0.8127.18`，`page_errors: []`，`assigned_user_settings.rejected_statuses` 12 个 422，`assigned_user_long` 中英文 320px 无溢出。 |
| `.venv/bin/python /tmp/an109_probe.py <同一 Chromium>`（独立弹窗→真实 API→临时 SQLite 探针） | 0 | 10 次拒绝逐次断言通过；空格修剪、Enter 保存、空串与纯空格清空、重开回填、英文错误提示均通过；`page_errors: []`。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-machine-assigned-user --strict` | 0 | `Change 'add-machine-assigned-user' is valid` |
| `git diff --check`、`git diff --cached --check`、`git diff --check 9b698f7..HEAD` | 0 | 无输出。 |

## 未覆盖与限制

- 浏览器实测仅 Chromium 158（`158.0.8127.18`），未运行 Firefox、Safari 或移动端真实设备；单行控件语义结论以该 Chromium 和 HTML 规范的 CR/LF 值清理行为为依据。
- 全部使用合成采集、合成节点和临时 SQLite；未连接真实节点、SSH、GPU、用户数据或 Docker 实例，未验证部署级升级与回滚。
- 复审未重新审查 AN-103/AN-105 的其余结论之外的实现；上述两项按回归路径复核。
- 本报告与 `verification.md`、`tasks.md` 的复审记录由审查者补充，未提交、未推送；实现和测试保持只读。由 Mika 决定后续同步、归档与 main 交付。
