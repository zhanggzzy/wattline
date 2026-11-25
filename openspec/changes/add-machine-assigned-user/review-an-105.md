# AN-105 独立复审报告

2026-11-25（Asia/Shanghai），Reviewer-Codex，Multica 配置模型 `gpt-6.2-sol`，推理档 `high`。复审依据为 AN-102、[AN-103 原审查](review-an-103.md)、AN-106 交接和 OpenSpec `add-machine-assigned-user`。

**结论为需修改。** AN-103 的两项问题在直接 API 和窄屏详情的验收路径均已修复。机器设置弹窗仍能把本应拒绝的行分隔符转成合法空值，清除已有登记。该问题影响原登记的完整性，需留在活动 change 返工。

## 被审提交

- 本地 `main` 的被审 HEAD 为 `027b796db9baef31938ea7c04051c1fde03dc6a8`。整改实现为 `63c210b168f786aac2773caaedb67aaf92230d54`，整改前基线为 `c0da8a18faded8735dc9f0256c743c4bbc6c75a6`。
- `git ls-remote origin refs/heads/main` 返回产品基线 `9b698f731b50c3eae6385cdbd23dd7a2bac1af40`（退出码 0）。全量 diff 对照该提交，整改 diff 对照整改前基线。变更仍在本地 `main`。
- 索引中的 `AGENTS.md` 仅含通用约定。复审开始时工作树已有的 `AGENTS.md` 注入差异原样保留。

## P2 · 设置弹窗可清空或覆盖应保留的登记

[monitor.js:1093](../../../wattline/static/monitor.js#L1093) 在提交前对 `assigned_user` 执行 `.trim() || null`，删除首尾 U+2028 和 U+2029。后端 [config.py:37](../../../wattline/config.py#L37) 收到的值已经失去需要拒绝的字符，按合法清空或修改写入。弹窗关闭，详情显示写入后的状态。该行为违反 [输入约束](specs/machine-registry/spec.md#requirement-assigned-user-input-constraints) 对非法值和旧登记的保护。

复现使用 Chromium `158.0.8127.18`、README 检查的合成页面与路由、停用的合成节点 `demo-3` 和临时 SQLite。将浏览器的设置 PUT 转发给内存中的 FastAPI `TestClient`，以真实 API 响应完成浏览器请求。每次先经 API 写入「初始登记」，打开机器详情的配置弹窗，清空输入控件，再用 Playwright 的 `page.keyboard.insert_text(raw)` 插入待测值。读取控件值确认字符仍在，点击保存，记录截获的请求以及写入后的快照与 SQLite。

| 输入（转义形式） | 原值直接发给 API | 弹窗实际发送的值 | 弹窗保存结果 |
| --- | --- | --- | --- |
| `\u2028` | 422，保留「初始登记」 | `null` | 200，快照为 `null`，SQLite 键被移除 |
| `\u2029` | 422，保留「初始登记」 | `null` | 200，快照为 `null`，SQLite 键被移除 |
| `next\u2028` | 422，保留「初始登记」 | `"next"` | 200，快照和 SQLite 均改为 `next` |

返工验收应从弹窗提交会被 API 拒绝的原始输入，确认显示失败、保留弹窗草稿，且快照与 SQLite 仍为原登记。普通空格修剪、空串或纯空格清空仍应通过。

## AN-103 两项复测

1. **直接 API 通过。** 在独立 Python 进程中用 `git show c0da8a1:wattline/config.py` 加载旧校验器，其他 API 路径维持被审版本。对 AN-103 的八个用例逐项重置原登记后复测，七个旧请求返回 200 并改写或清除快照与 SQLite，内部换行返回 422。被审版本用 `TestClient` 向 `PUT /api/machines/review/settings` 发送 U+0000–U+001F、U+007F–U+009F、U+2028 和 U+2029。每个字符构造首部、尾部、内部和单独四种值，合计 268 次请求均返回 422。每次均通过 `GET /api/snapshot` 并按 `history_key` 查询 SQLite 的 `machine_settings.settings`，快照与原设置行保持不变。81 字符返回 422，普通空格包裹的合法 80 字符正确修剪并接受。空串、纯空格、`null` 均正确清空，最后保存的修剪值经重启保留。仓库回归用例有 13 个非法输入，每次核对快照并在循环后核对 SQLite。独立复测覆盖每次拒绝后的数据库检查。
2. **320px 窄屏通过。** 在合成离线节点详情通过弹窗保存 `"LongUser" * 10`，再切到 320 × 900。以 `git show c0da8a1:wattline/static/monitor.css` 替换浏览器的 CSS 响应时，中英文文档宽度均为 472px。被审 CSS 下，两种语言均完整显示 80 个字符，文档宽度等于视口 320px，副标题 `scrollWidth == clientWidth == 288`，`scrollHeight == clientHeight == 90`，文本右端 303.61px。另用 `"宽" * 80` 验证两种语言，文档宽仍为 320px，文本最右端分别为 296.97px 和 298.14px，副标题无裁切。独立检查通过 DOM Range 的行内矩形核对换行和文本边界。

## 命令和结果

| 命令 | 退出码 | 实际输出 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | `36 passed, 1 warning in 0.80s`。警告来自 Starlette TestClient 的 httpx 弃用提示。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 285 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py` | 1 | 默认 Playwright Chromium headless shell 1255 未安装。 |
| `.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"` | 0 | `PASS`，Chromium `158.0.8127.18`，`page_errors: []`，`zh-CN` 和 `en`，10 次写请求、120 次历史查询。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-machine-assigned-user --strict` | 0 | `Change 'add-machine-assigned-user' is valid`。`status --change add-machine-assigned-user --json` 确认为 `spec-driven`。 |
| `git diff --check`、`git diff --cached --check`、`git diff --check 9b698f7..027b796`、`git diff --check c0da8a1..027b796` | 0 | 无输出。 |
| `.venv/bin/python - before`、`.venv/bin/python - after`（标准输入传入独立 API 探针） | 0 | 旧校验复现七次写入，被审版本 268 次 422，逐次检查快照与 SQLite，普通空格和重启复核通过。 |
| `.venv/bin/python -`（标准输入分别传入独立宽度探针和弹窗提交探针） | 0 | 复现旧样式 472px 溢出，确认修复后 320px。捕获三次弹窗改写原始输入及写库。 |

全量 pytest 与浏览器检查还覆盖旧设置读取、独立机器持久化、删除、写入失败后的 503、列表/详情显示、设置回填和清空、双语与字面渲染。GPU 进程账户与 SSH 登录仍走原数据路径。已写入非空登记的行在回退至变更前版本时会被旧版的 `extra='forbid'` 拒绝，现有设计已记录该限制。

复审使用合成路由和临时数据库。实际浏览器仅 Chromium，未核验其他浏览器、真实 SSH、GPU、用户 Docker 实例或部署级升级与回滚。复审仅补充 change 证据，代码与测试保持只读。由 Mika 协调返工并继续独立审查。
