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

待 AN-103 执行后补充；审查者对照本 change、实际 diff、测试结果和 strict 校验给出结论。
