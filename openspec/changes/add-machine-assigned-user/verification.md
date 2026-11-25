# AN-104 执行验证

2026-11-25 在 Wattline 固定工作区使用合成夹具验证「每台环境手动登记使用者」。任务为 AN-104，父任务为 AN-102，独立审查任务为 AN-103。本记录对应 [tasks.md](tasks.md) 的 1.1、1.2、2.1、2.2、3.1。

## Git 基准与实现

- 执行前本地 `main` 与 `git ls-remote origin refs/heads/main` 均为 `9b698f731b50c3eae6385cdbd23dd7a2bac1af40`。
- 本地实现提交为 `f6a66244ce7158cdf644c1a20e9683538d3d59e4`，提交信息 `AN-104: record per-machine assigned user`。
- 提交涉及 13 个文件，新增 280 行、删除 9 行。工作树原有的 `AGENTS.md` 运行时注入块未纳入提交；`git show :AGENTS.md` 仍仅含通用仓库约定。

## 命令与结果

| 命令 | 退出码 | 实际结果 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | `36 passed, 1 warning in 0.77s`。警告为 Starlette TestClient 的 httpx 弃用提示。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 285 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-machine-assigned-user --strict` | 0 | `Change 'add-machine-assigned-user' is valid` |
| `git diff --check` | 0 | 无输出。 |
| `git show --check f6a66244ce7158cdf644c1a20e9683538d3d59e4` | 0 | 无空白错误（只打印提交信息）。 |

README 的合成 API 浏览器检查使用现有 Chromium 缓存：

```sh
.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"
```

退出码为 0。输出摘录如下。

```json
{
  "result": "PASS",
  "browser": "158.0.8127.18",
  "page_errors": [],
  "locales": ["zh-CN", "en"],
  "mutations": 8,
  "history_queries": 120
}
```

脚本在总览与机器详情核对中文「使用者：张工」和英文 `Assigned user: 张工`，只对已登记机器显示；打开设置时字段回填登记值；修改为含 `<b>` 的文本后列表与详情按字面显示且不产生元素；再次打开设置并清空后详情与列表不再显示该标签。桌面、320 像素窄屏、无页面错误均通过。`artifacts/detail.png` 保留本轮截图，显示转义后的字面文本。

## 覆盖范围

- API 与持久化：登记、修改、清空；两台机器互不影响；服务重启后保留；旧设置 JSON（无该键）可读；移除机器后其设置记录被删除；清空后存储 JSON 不再包含该键。
- 输入与访问防护：跨源 403、非 JSON 415、多行与超长 422；底层写入抛错时返回 503 且快照保留旧值，不误报成功。
- 界面：中文与英文标签、列表与详情显示、设置回填、修改、清空、HTML 转义、窄屏布局；进程账户与 SSH 用户显示路径未改动。
- 兼容性：未新增数据库 schema 或配置字段。既有 `machine_settings.settings` 行可直接读取。

## 未覆盖范围与限制

- 浏览器实测仅 Chromium 158；未在真实 Firefox 或 Safari 运行。
- 未连接真实节点、NVIDIA 驱动、SSH 端点或用户 Docker 实例；验证全部使用合成采集与合成 API 响应。
- 回滚到本变更前的版本时，已写入 `assigned_user` 的设置行会因旧版 `extra='forbid'` 被拒绝；未登记的数据库保持可读。需要回滚时应先在当前版本清空相关登记值。
- 使用者是人工备注，不校验其真实性，也不与自动采集的进程账户或 SSH 用户比对。

## AN-103 独立审查

2026-11-25，Reviewer-Codex 独立审查结论为**需修改**。任务 1.2 的输入校验允许部分控制字符和换行符覆盖登记值。任务 2.1 的机器详情在窄屏上会被合法长值撑出视口。复跑结果、复现步骤和被审提交见 [AN-103 独立审查报告](review-an-103.md)。

## AN-106 返工验证

2026-11-25，为 AN-102 第一轮返工（AN-106）在 Wattline 固定工作区复跑。基线为 AN-103 审查时的 `HEAD` `c0da8a18faded8735dc9f0256c743c4bbc6c75a6`，实现提交为 `63c210b168f786aac2773caaedb67aaf92230d54`（`AN-106: reject raw control characters and wrap long assigned users`）。AN-103 留在工作树的 `verification.md` 更新和未跟踪审查报告 `review-an-103.md` 均保留，并随本次记录提交。

### 修复内容

- `wattline/config.py`：`assigned_user` 增加 `mode='before'` 校验器，在 Pydantic 去除首尾空白之前检查原始值。拒绝 U+0000–U+001F、U+007F、U+0080–U+009F 以及 U+2028、U+2029，任意位置包括首尾和仅由这些字符构成的值都会返回 422。普通空格修剪、合法值、空值或纯空格清空语义由原有校验和新增归一化保持。
- `wattline/static/monitor.css`：详情副标题允许任意位置换行，标题容器限制在可用宽度内，消除窄屏横向溢出。
- `tests/test_monitor.py`：真实 API 回归覆盖 13 个拒绝值（首部、尾部、内部换行；NUL、DEL；U+0085、U+009B；U+2028、U+2029；以及仅由换行、U+0085、U+2028、U+2029 构成的值），每次 422 后核对快照仍为原值，并在两机保存后直接读取 SQLite 确认持久化仍为 `张三`；仍覆盖普通空格修剪、空串与纯空格清空。
- `tools/browser_smoke.py`：在真实设置弹窗保存合法 80 字符连续值 `'LongUser'*10`，于 320 × 900 视口分别用中文和英文打开详情，断言文档无横向滚动、副标题右边缘在视口内、文本无横向或纵向裁切，并保留原有转义、回填和清空检查。

### 命令与结果

| 命令 | 退出码 | 实际结果 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | `36 passed, 1 warning in 0.73s`。警告仍为 Starlette TestClient 的 httpx 弃用提示。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 285 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"` | 0 | `PASS`，Chromium `158.0.8127.18`，`page_errors: []`，`locales: ["zh-CN", "en"]`，10 次写请求、120 次历史查询。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-machine-assigned-user --strict` | 0 | `Change 'add-machine-assigned-user' is valid` |
| `git diff --check`、`git diff --cached --check` | 0 | 无输出。 |

浏览器长值断言的实际量测（两个语言一致）：

```json
[{"locale":"zh-CN","width":320,"subtitle":{"right":304,"height":89.5625,"scrollWidth":288,"clientWidth":288,"scrollHeight":90,"clientHeight":90}},
 {"locale":"en","width":320,"subtitle":{"right":304,"height":89.5625,"scrollWidth":288,"clientWidth":288,"scrollHeight":90,"clientHeight":90}}]
```

副标题在 320 像素视口内换行为多行（高度约 90 像素），右边缘 304 像素，内容宽度等于可视宽度。截图保留在 `artifacts/assigned-user-long-zh-CN.png` 和 `artifacts/assigned-user-long-en.png`（未提交，仓库原有行为）。

### 覆盖与限制

- 覆盖：上述 13 类拒绝输入的首部、尾部、内部和仅拒绝字符位置；每次拒绝后的快照与数据库原值；普通空格修剪；合法值；空串与纯空格清空；80 字符合法值的窄屏中英文详情和转义、回填、清空回归。
- 未覆盖：真实节点、SSH、GPU、用户 Docker 实例；Firefox、Safari 和移动端真实设备；实例升级或回滚。浏览器仍仅使用 Chromium 158 与合成 API。
- 未推送远端，也未归档 change；由 Mika 核对后交 Reviewer-Codex 复审。

## AN-105 独立复审

2026-11-25，Reviewer-Codex 复审 `027b796db9baef31938ea7c04051c1fde03dc6a8`。原两项问题的直接 API 与 320px 中英文详情检查均通过。整体结论为**需修改**。机器设置弹窗会在提交前修剪 U+2028/U+2029，导致本应拒绝的输入清空或覆盖已有登记。完整复现、退出码和覆盖范围见 [AN-105 独立复审报告](review-an-105.md)，涉及 [任务](tasks.md) 1.2、2.1 和 3.1。

- [ ] 机器设置弹窗提交非法分隔符时保留已有登记，验收见 AN-105 报告，待 Mika 协调返工与复审。

## AN-110 第二轮返工验证

2026-11-25（Asia/Shanghai），Executor-Codex 执行自测。返工基线为 AN-105 被审本地 `main` 的 `027b796db9baef31938ea7c04051c1fde03dc6a8`。`git ls-remote origin refs/heads/main` 退出 0，开始时的远端基线为 `9b698f731b50c3eae6385cdbd23dd7a2bac1af40`。实现提交为 `3e213580cce063733f88fbfdf5efb6f0416db2aa`。可用 `git diff 027b796..3e21358` 查看本轮实现、测试与规划。保留 [AN-103](review-an-103.md) 和 [AN-105](review-an-105.md) 两次独立审查，后者及其上方结论随实现提交纳入 Git。

### 表单与持久化

- 在 Chromium 中通过 `navigator.clipboard.writeText` 写入合成测试文本，再用粘贴快捷键分别粘贴到原单行控件和一行高的文本框。两个控件均保留 U+2028/U+2029。原控件将单独 CR 或 LF 粘贴为空，将 `one\r\ntwo` 粘贴为 `one two`。文本框将 CR 和 CRLF 规范为 LF，API 仍能拒绝。
- 使用 `.venv/bin/python - <Chromium 路径>` 通过标准输入运行回归探针，调用 `git show 027b796:wattline/static/index.html` 和 `git show 027b796:wattline/static/monitor.js` 替换测试路由中的两个响应，运行当前 `tools/browser_smoke.py`。旧单行控件收到 U+2028，旧脚本发送 `null` 并收到 200。测试按预期退出 1，断言对比实际 `None / 200` 和期望 `U+2028 / 422`。
- 修复后的浏览器回归把弹窗 PUT 转发至同进程 FastAPI，使用停用的合成机器与临时 SQLite。直接插入单独的 U+2028 和 U+2029，粘贴首尾或内部含分隔符的文本、CR/LF、制表符、C1 字符、80 字符后的分隔符和 81 个合法字符。12 次请求均收到 422，每次逐项核对发送值、可见的使用者错误、仍打开的弹窗、完整草稿、快照及完整原 SQLite 设置行。
- 用 Enter 保存粘贴的带首尾普通空格的 80 字符合法值，核对页面、浏览器快照、API 快照、SQLite 与重开弹窗均使用实际持久化值。分别从已有登记用纯普通空格和空串清空，再重开核对为空。直接 API 的 pytest 用例扩展为 18 个控制字符或分隔符输入，每次均核对快照和 SQLite 原登记。
- 结论覆盖 [任务](tasks.md) 1.2、2.1、3.1。生产 API 校验及持久化代码沿用当前实现。浏览器范围为 Chromium 158 的无头检查，其他浏览器、系统输入法与移动设备实测留在覆盖范围外。验证使用合成路由和临时数据，部署级升级和回滚未验证。OpenSpec change 保持活动，AN-109 独立复审待执行。

### 命令与结果

| 命令 | 退出码 | 实际输出 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | `36 passed, 1 warning in 0.83s`。警告来自 Starlette TestClient 对 httpx 的弃用提示。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 286 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage`。 |
| `.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell" > artifacts/an-110-browser.json` | 0 | `PASS`，Chromium `158.0.8127.18`，`page_errors: []`，12 次 422，10 次原合成路由写请求、120 次历史查询。中英文 320px 详情副标题的 `scrollWidth = clientWidth = 288`，`scrollHeight = clientHeight = 90`。标准错误有同一 Starlette 弃用提示。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-machine-assigned-user --strict` | 0 | `Change 'add-machine-assigned-user' is valid`。 |
| `git diff --check`、`git diff --cached --check`、`git diff --check 027b796..3e21358`、`git diff --check 9b698f7..3e21358` | 0 | 无输出。索引中的 `AGENTS.md` 无运行时标记，工作树注入保留。 |
