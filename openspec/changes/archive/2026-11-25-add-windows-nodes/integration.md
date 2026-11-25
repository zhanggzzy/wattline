# AN-126 独立审查与主干整合

2026-11-25，Mika 汇总 AN-128 实施、AN-127 独立审查及本轮整合。关联 [实施验证](verification.md) 与 [任务 3.3](tasks.md)。

- 基线为 `a99d317134c36582b5b6ae2c1fe3f8d9eb670c1e`。审查范围为该基线至本地交接提交 `6246e26bf9c2e20f717ca1ec5e1df8ba9f032e54`，含实施提交 `c7ebc1f1429c308260f4322ae3c00eecbbd05abd`。
- Reviewer-DeepSeek（`deepseek-flash`）于 07:25:08 UTC 在 Multica AN-127 发布通过结论。审查对照实际提交差异、规范和脱敏实机证据，独立复跑 pytest（44 项通过）、JS 语法、i18n、合成浏览器、OpenSpec strict、Git diff 检查与 wheel 内容检查。审查阶段使用本地夹具和实施阶段的脱敏实机记录。
- 独立检查还确认 API 拒绝经设置接口修改节点 OS，Windows 节点及确认空的 GPU 清单重启后仍可恢复。文件配置的 Windows 节点依赖配置中的预期机器身份和严格 known_hosts 校验，登记走持久化密钥绑定。极端大清单可能触及 XML 输出上限并显示未核实。GPU 详情的「可见记录」指探针观察总数，预览仍显示省略数。
- 实机范围为单处理器组和单张 WDDM 卡，逐进程显存为未知。更广的系统与驱动覆盖范围见实施验证。

## 整合检查

- `git ls-remote --exit-code origin refs/heads/main` 退出 0，整合前远端为上述基线。
- `.venv/bin/python -m pytest -q` 退出 0，44 项通过，有一条既有 Starlette/httpx 弃用提示。 `node --check wattline/static/monitor.js` 与 `node tools/test_i18n.cjs` 均退出 0，308 个翻译键通过。
- `.venv/bin/python tools/browser_smoke.py --browser "$CHROME_EXECUTABLE"` 使用本机 Chrome 158.0.8127.37 复跑，退出 0，合成 API 浏览器结果为 `PASS`，两种语言均无页面错误。
- `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-windows-nodes --strict` 退出 0。同步后的 `validate --specs --strict` 退出 0，7 份规范通过。 `list --json` 确认 6/6 项任务完成。
- 三份规范同步后按仓库归档技能移至 `openspec/changes/archive/2026-11-25-add-windows-nodes`。保留实施与审查对应的代码。
- `git diff --check`、`git diff --cached --check` 与从基线起的 `git diff --check a99d317...HEAD` 用于检查工作区、索引及完整交付差异。最终整合提交和远端核验结果见 AN-126 交付评论。
