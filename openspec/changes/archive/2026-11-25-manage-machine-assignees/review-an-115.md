# AN-115 独立审查：共享人员名单与机器多人登记

2026-11-25（Asia/Shanghai），Reviewer-DeepSeek，Multica 运行时配置模型 `deepseek/deepseek-flash`。审查对象为 [AN-116](https://github.com/zhanggzzy/wattline) 的本地交付，代码与测试只读；本文件仅记录审查结论，不改实现。

## 结论

**通过，无阻塞项。** 需求、活动 change `manage-machine-assignees`、实际 diff、自动化测试和真实 Chromium 合成 API 检查一致。三项非阻塞观察列在末节，均不影响本轮通过或 `assigned_user` 升级数据的正常范围。

下一步由 Mika 按授权同步主规范、归档 change、整合并推送远端 main，核对远端实际 SHA 后完成 AN-102 交付。`tasks.md` 3.3 保持待办。

## 被审对象

- 基线（本地与远端 `main` 相同）：`04e006cfe067e56deeade6512c12003f272c142c`。
- 实现提交：`d0125d5e3d42657ca3a8d66b58f98f01642ea48b`（`AN-116: add shared people and machine assignees`）。
- 交接 HEAD：`4dfc82c4b92e344e5f06e49790d8fed81a5d4b1d`（`AN-116: record assignee implementation verification`）。
- 工作树只有既有 `AGENTS.md` 运行时注入差异；暂存区为空，未触碰被审实现。
- 实际变更：`git diff --name-status 04e006c..4dfc82c` 为 README、活动 change、`tests/test_monitor.py`、`tools/browser_smoke.py`、`wattline/{app,config,history,history_schema,service}.py`、`wattline/static/{index.html,locales.js,monitor.css,monitor.js}`，共 18 个文件、+1080/−290。

## 需求与规范核对

- **列表与详情可见**：`monitor.js` 的 `assigneeSummary()` 同时进入常规机器列表行和详情标题区，使用 `Intl.ListFormat` 本地化连接，标签来自 `assignees_value`；空名单不渲染占位。中英文、1440px 与 320px 均由真实 Chromium 断言元素可见、无 `<b>` 注入元素、无横向溢出。
- **“配置”旁入口**：详情页 `machine-settings-actions` 内依次渲染 `data-configure-machine` 与 `data-edit-assignees`；浏览器断言两者同一行、配置在前。
- **多人、移除一人、清空并保存**：`PUT /api/machines/{id}/assignees` 接收去重后的 `person_ids`，空列表清空；对话框保留草稿，取消不保存。浏览器覆盖多选、单项取消、取消编辑、清空保存。
- **共享名单复用**：人员有稳定 ID；改名只改 `people.name`，所有机器的 `assigned_users` 动态解析同一 ID。迁移把同一修剪后拼写合并为一个条目，大小写保持区分。API 测试覆盖同一人跨两台机器、改名传播、删除未用人员、删除在用人员 409。
- **名单维护**：`/api/people` 新增、改名、删除；删除在用人员返回 `person_in_use`，前端提示先解除关联；未关联人员删除后从目录和选择项消失。
- **升级**：schema 7→8 在既有启动事务内建表、导入非空 `assigned_user` 并删除旧字段；缺失、`null`、纯空白不建条目；重复启动由版本门控避免重复导入，清空关联后不会被重启恢复。
- **互不覆盖**：排队分配与普通机器设置是独立写路径；快照和 DB 验证普通设置保存后名单保留，分配保存不影响别名、间隔等设置。
- **持久化、身份隔离与删除清理**：分配键为 `history_key`；重启、`id` 改名、机器移除、同身份重新登记均有断言；移除机器只删该机器的 `machine_assignees`，保留人员和其他机器关联。
- **输入与安全**：姓名在首尾修剪前拒绝 ASCII/C1 控制字符、U+2028/U+2029 与代理项；空、纯空白、>80 字符、重复/不存在 ID 全部拒绝且保留原值；所有名称经 `escape()` 后写入 HTML，含标记字符的名称按字面显示。
- **失败保留原值**：SQLite 触发器注入写失败时 API 返回 503，对话框保留草稿，快照与数据库保持上次成功值；解除故障后用原草稿重试成功。
- **离线可改**：浏览器夹具包含离线与禁用机器，保存/清空均成功。

## 独立复跑的真实命令

| 命令 | 退出码 | 实际结果 |
| --- | ---: | --- |
| `.venv/bin/python -m pip check` | 0 | `No broken requirements found.` |
| `.venv/bin/python -m pytest -q` | 0 | `37 passed, 1 warning in 0.85s`（Starlette TestClient/httpx 弃用提示） |
| `node --check wattline/static/monitor.js` | 0 | 无输出 |
| `node --check wattline/static/locales.js` | 0 | 无输出 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 301 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"` | 0 | `result PASS`，`page_errors []`，`legacy_migration`/`offline_assignment`/`directory_rename_add_remove`/`cancel_multi_select_deselect_clear` 为真，非法名单提交 12 次均 422，关联删除 409，关联写失败 503 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate manage-machine-assignees --strict` | 0 | `Change 'manage-machine-assignees' is valid` |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 status --change manage-machine-assignees --json` | 0 | root 为该仓库，`schemaName: spec-driven`，proposal/specs/design/tasks 均存在 |
| `git diff --check` / `git diff --cached --check` / `git diff --check 04e006c..4dfc82c` | 0 / 0 / 0 | 均无输出 |

浏览器布局实测（详情 / 列表摘要的 `clientWidth`，均 `scrollWidth <= clientWidth` 且无页面横向滚动）：中文 1440px 803/230，320px 288/190；英文 1440px 737/230，320px 288/190。320px 的列表与详情截图由本次复跑写入忽略目录 `artifacts/assignees-list-{zh-CN,en}.png`、`assignees-detail-{zh-CN,en}.png`；目视确认长名称换行、字面 `<b>` 文本和相邻按钮。1440px 与窄屏的断言同时覆盖三名以下与两名人员组合。

## 独立补充探针（仓库外临时脚本，已删除）

- 版本 7 旧库写入 `'  重复  '`、`'重复'`、`None`、缺失、`'Case'`、`'case'`：升级后只生成一个「重复」条目并关联两台机器，`Case`/`case` 为两个条目，缺失/空值无分配；重启后目录与关联不变。
- 清空一台机器的关联并重启：为空的那台保持空，另一台保留；改名后重启，两台显示新名。
- 旧 API 字段 `assigned_user` 返回 422；80 字符合法名 201，81 字符 422，首尾普通空格修剪，U+2028 422，纯空白 422。
- 被其他机器关联的人员删除返回 409；未知人员分配 409，重复 ID 422，未知机器 404。
- 版本 7 旧库含不可导入的旧值（换行、超 80 字符、U+2028）时，迁移在事务内失败：`user_version` 仍为 7，`people`/`machine_assignees` 不存在，机器设置原样保留；服务以 `registry_loaded=false` 保留原数据并重试。该情形见下方观察 1。

## 非阻塞观察

1. **不可导入的旧值会让本次升级停在未迁移状态。** 仅当前已交付版本会拒绝这些值（控制字符/行分隔符/超 80 字符）并通过 API 保存前校验，因此正常交付数据不会触发；若数据库由更早未校验的版本写入过此类值，启动会保留版本 7 与旧数据，但 `registry_loaded=false`，日志只有 `监控指标库不可写 (DatabaseError)`，操作者需按 README 的回退/备份边界处理。原子失败与设计一致，不要求本轮改代码；可后续在日志或文档中补充可操作原因。
2. **只被配置文件移除、未走界面移除的机器仍会保护其人员。** 其 `machine_assignees` 行不随配置文件差异清理，人员目录中会保留该人员并返回 409；设计已记录“恢复该机器配置后再编辑关联”。符合“显式处理、不静默丢关系”的要求。
3. **孤立代理项姓名请求的 422 响应体无法序列化。** 直接提交含 `\ud800` 的 JSON 时，FastAPI 在回显校验输入时失败返回 500；后端仍拒绝写入、数据不变，界面无法产生该输入。这是框架级错误响应行为，不是本变更引入的逻辑问题，列为后续可统一处理的边界。

## 覆盖与限制

验证范围为合成节点、临时 SQLite、Chromium Headless Shell 158.0.8127.18 与 in-process API。未覆盖 Firefox/Safari、真实节点、真实历史库、用户实例部署、SSH 连接和升级后的远端安装。未审查 Mika 的主干推送与远端 SHA，`tasks.md` 3.3 仍待 Mika；主规范 `openspec/specs/machine-registry/spec.md` 尚未同步本 delta，属后续 sync/archive 步骤。
