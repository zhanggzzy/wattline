# AN-103 独立审查报告

2026-11-25（Asia/Shanghai），Reviewer-Codex，Multica 配置模型 `gpt-6.2-sol`，推理档 `high`。独立对照 AN-102、AN-104 验收条件、OpenSpec `add-machine-assigned-user` 规范与实际 diff。

**结论为需修改。** 两项问题分别对应 change 任务 1.2 和 2.1。由 Mika 协调返工与复审，change 保持活动。

## 审查范围

- 远端 `main` 与基线 `9b698f731b50c3eae6385cdbd23dd7a2bac1af40` 一致。实际实现为 `f6a66244ce7158cdf644c1a20e9683538d3d59e4`，被审工作树 `HEAD` 为 `c0da8a18faded8735dc9f0256c743c4bbc6c75a6`。两者之间的 diff 仅涉及 change 的任务和验证记录。
- 独立复跑前，跟踪文件仅有既存的 `AGENTS.md` 工作树差异。索引版 `AGENTS.md` 仅含通用仓库约定。

## 需修改项

1. **P2 · 部分多行或含控制字符的值会覆盖已保存的登记。** [config.py:37](../../../wattline/config.py#L37) 在 Pydantic 去除首尾空白之后校验，并只拦截内部的 ASCII 控制字符。用 `TemporaryDirectory` 和 `TestClient` 在合成 SSH 节点上请求 `PUT /api/machines/review/settings`，请求体为 `{"assigned_user": value, "interval_seconds": 1}`。先保存 `初始值`，逐个试下列输入，并请求 `/api/snapshot` 读取该节点的 `assigned_user`。

   | 输入（转义表示） | HTTP | 快照值 |
   | --- | --- | --- |
   | `first\nsecond` | 422 | `初始值` |
   | `\nnext` | 200 | `next` |
   | `next\t` | 200 | `next` |
   | `first\u0085second`、`first\u009bsecond` | 200 | 保留相应 C1 控制字符 |
   | `first\u2028second`、`first\u2029second` | 200 | 保留分隔符 |
   | `\n` | 200 | `null`，清空已有值 |

   规范要求拒绝这些值并保留已有登记。返工应在去除空白前校验控制字符和行分隔符，并验证非法值不会写入。现有 pytest 只覆盖了字符串中间的 ASCII 换行和超长输入。

2. **P2 · 80 字符连续文本会让窄屏详情横向溢出。** [monitor.js:461](../../../wattline/static/monitor.js#L461) 把使用者插入详情副标题。[monitor.css:189](../../../wattline/static/monitor.css#L189) 只给主标题设置了 `overflow-wrap: anywhere`。使用 `tools/browser_smoke.py` 的合成路由，在 Chromium 中将视口设为 320 × 900，打开 `demo-3` 离线节点详情。在配置中保存 `'LongUser'.repeat(10)`，比较 `document.documentElement.scrollWidth`。中英文界面的文档宽均由 320 增至 472 像素，副标题文本右边缘也到 472 像素。返工应让副标题中的合法长值在窄屏完整换行，并补充详情页回归断言。原浏览器用例只用短使用者文本跑通了显示。

## 独立执行结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | `36 passed, 1 warning in 0.74s`。警告来自 Starlette TestClient 的 httpx 弃用提示。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 285 message keys`，占位符、引用、插值、Intl、持久化、回退和受限存储均通过。 |
| `.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"` | 0 | `PASS`，Chromium `158.0.8127.18`，`zh-CN` 和 `en`，`page_errors: []`，8 次写请求、120 次历史查询。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-machine-assigned-user --strict` | 0 | `Change 'add-machine-assigned-user' is valid`。`status` 确认 `spec-driven`，`instructions apply` 读到实现者已勾选 5/5。 |
| `git diff --check`、`git diff --cached --check`、`git diff --check 9b698f731b50c3eae6385cdbd23dd7a2bac1af40 c0da8a18faded8735dc9f0256c743c4bbc6c75a6` | 0 | 无空白错误。 |
| `git ls-remote origin refs/heads/main` | 0 | 远端返回 `9b698f731b50c3eae6385cdbd23dd7a2bac1af40`。 |

- pytest 独立复跑覆盖停用节点、登记和替换、重启、清空后移除 JSON 键、已有设置无新键、同源与 JSON 防护，以及模拟存储失败后的 503 和原值保留。代码审查确认设置仍按 `history_key` 写入原 SQLite 事务，删除会清理同一身份的持久记录和缓存。额外用同一 machine-id、两枚合成 SSH 主机密钥验证隔离、重启及同身份删除后重新登记，原登记值没有迁入新节点。运行中的合成离线节点可以保存，SSH 登录显示地址保持 `observer@review.invalid`。
- 浏览器复跑确认设置回填、列表与详情显示、修改和清空、普通标记字符按字面显示，合成进程账户 `demo-user` 仍来自 GPU 进程数据。额外对 `demo-3` 的合成设置请求先返回 503 再成功，确认失败时弹窗保留草稿、详情保留原显示，重试才显示登记，清空后列表和详情移除该字段，另一机器的登记仍在。
- 新版本读取旧设置和旧配置的路径已核对。已写入非空 `assigned_user` 的行会被旧版 `extra='forbid'` 拒绝，此回滚限制已记入设计和执行验证。

数据库和 API 使用临时数据，浏览器使用合成 API。实测浏览器为 Chromium。真实 SSH、GPU、其他浏览器、用户 Docker 和实例级升级或回滚均未运行。审查仅补充 OpenSpec 证据，未改实现或测试，未提交、归档或推送。
