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

浏览器实测范围为 Chromium。真实 Linux、NVIDIA 驱动、SSH 节点和用户实例属于本轮合成验证之外。独立审查待 Mika 确认交接后由 Reviewer-DeepSeek 在 AN-74 执行。规范同步、归档和远端 main 交付由 Mika 在审查通过后推进。
