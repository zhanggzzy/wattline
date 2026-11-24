# AN-75 执行验证

2026-11-24 在 Wattline 固定工作区使用合成夹具验证。任务为 AN-75，父任务为 AN-73，独立审查任务为 AN-74。本记录对应 [tasks.md](tasks.md) 的 1.1、2.1、3.1。

## Git 基准与实现

- 执行前的本地 `main` 及 `git ls-remote origin refs/heads/main` 均为 `95c403cf5ccd37b722da66c2fecffd1c5aa115ea`。
- 本地实现提交为 `f79214b9ef649eff577a116c33b0925997782afe`。用 `git diff 95c403cf5ccd37b722da66c2fecffd1c5aa115ea f79214b9ef649eff577a116c33b0925997782afe` 查看实现与规划差异。
- 提交前 `git diff --cached --stat` 显示 12 个文件、398 行新增、34 行删除。`git diff --cached --exit-code -- AGENTS.md` 退出 0；`git show :AGENTS.md` 经检查仅含通用仓库约定。工作树中的原有运行时块保持原样。

## 命令与结果

| 命令 | 退出码 | 实际结果 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | `34 passed, 1 warning in 0.78s`。警告来自 Starlette TestClient 对 httpx 的弃用提示。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 281 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-gpu-process-timing --strict` | 0 | `Change 'add-gpu-process-timing' is valid` |
| `git diff --check` | 0 | 无输出。 |
| `git diff --cached --check` | 0 | 暂存实现后运行，无输出。 |

README 的浏览器检查使用其 `--browser` 参数和现有 Chromium 二进制。

```sh
.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"
```

退出码为 0。输出摘录如下。

```json
{
  "result": "PASS",
  "browser": "158.0.8127.18",
  "page_errors": [],
  "gpu_process_timing": {
    "locales": ["zh-CN", "en"],
    "timezone": "America/Los_Angeles",
    "narrow_width": 320,
    "timing_only_poll": true,
    "missing_pair_poll": true,
    "departed_processes_poll": true,
    "page_errors": []
  }
}
```

直接运行 `.venv/bin/python tools/browser_smoke.py` 退出 1，因为当前 Playwright 默认查找的 Chromium headless shell 1255 未缓存。首次指定缓存中的 1254 运行时，320 像素宽度的断言发现进程表的滚动区域超宽，退出 1。将详情网格列约束到容器宽度后，全套检查通过。之后补充了关闭弹窗时立即刷新机器页的行为，重新运行全套检查仍通过。

## 覆盖范围与交接

合成 Linux proc 和 NVIDIA 输出覆盖采样前的已验证 PID、零整秒、采样边界、PID 复用、进程退出、缺少 cgroup、时间源和 tick 频率不可用、GPU-only 容器及旧快照。API 测试核对新增字段和原有进程字段，合成浏览器验证两个视图、两种语言、跨日时区转换、未知值、轮询更新、滚动和焦点。运行时长由采样时的 uptime 计算。启动时间受内核计时粒度和受监控端时钟准确度影响。

浏览器实测范围为 Chromium。真实 Linux、NVIDIA 驱动、SSH 节点和用户实例属于本轮合成验证之外。执行交接时，独立审查尚待 AN-74 执行。

## AN-74 独立审查

2026-11-24，Reviewer-DeepSeek（`deepseek/deepseek-flash`）在独立会话中只读审查基线 `95c403cf5ccd37b722da66c2fecffd1c5aa115ea` 至审查 HEAD `c61c656c1dcbae4aac9abbe1fe1617e4e46e03a8` 的实际差异。结论为通过。完整命令和边界探针见 Multica AN-74 的附件 `AN-74-review-report.md`。

- 独立执行的 pytest、JavaScript 语法、本地化、OpenSpec strict、提交范围 diff 和合成 API 浏览器检查均退出 0。pytest 报告 34 项通过及一项 Starlette TestClient 弃用警告，本地化覆盖 281 个键。
- 两个视图在 Chromium 158 下通过中英文、浏览器时区、320 像素宽度和轮询检查，无页面错误。审查还核对了 PID 复用和退出、容器边界、采样边界以及旧快照的未知值。
- 真实 Linux/NVIDIA/SSH 节点、用户实例、其他浏览器、宿主时钟跳变和长期挂起未实测。
- 唯一非阻塞建议是补充 README 的时间字段说明。Mika 在收尾时采纳，审查过的产品和测试代码保持原样。

## AN-73 同步与归档

2026-11-24，Mika 在同一基线和审查 HEAD 上复查，补充 README，使用 OpenSpec 1.14.2 的 sync 与 archive 工作流。将 “Current GPU process timing” 及四个场景同步到 `dashboard-focus-layout` 主规范，逐字比较确认只增加该需求。change 为 `spec-driven`，归档前四个任务全部完成。

| 命令 | 退出码 | 实际结果 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | `34 passed, 1 warning in 0.78s`，同一 Starlette TestClient 弃用警告。 |
| `node --check wattline/static/monitor.js` | 0 | 无输出。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 281 message keys`。 |
| `.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"` | 0 | Chromium 158.0.8127.18，`result: PASS`，无页面错误。中英文、320 像素和 America/Los_Angeles 时区均覆盖，三项进程轮询断言为真。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate --specs --strict` | 0 | 5 个主规范通过，0 个失败。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-gpu-process-timing --strict` | 0 | 归档前 change 校验有效。 |
| `git diff --check` | 0 | 无输出。 |

按 archive 技能将 change 移入 `openspec/changes/archive/2026-11-24-add-gpu-process-timing/`。移动后确认元数据仍存在，OpenSpec `list --json` 的活动列表已无该 change。
