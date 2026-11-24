# Verification

以下为 Executor-OMP 于 2026-11-24（Asia/Shanghai）在 Wattline 固定开发目录完成的 AN-64 自测。该记录不是独立审查；独立审查由 AN-63 执行。

## Baseline and change

- 仓库：固定开发目录，分支 `main`。
- 基线：`f31ed8ddc0a92bd94469546970433e8a8f4b5c56`，与 `origin/main` 一致。
- 工作树既有 `AGENTS.md` Multica runtime 注入块保持未暂存；索引中的 `AGENTS.md` 仍为 39 行通用仓库约定。
- OpenSpec change：`add-rail-machine-silhouettes`（`spec-driven`，1.14.2）。
- 设计依据：AN-60 已验收方案 A「机型轮廓」。

## Implementation

- `wattline/static/monitor.js`
  - 以快照 `devices[].name` 为唯一型号来源；所有非空设备名必须识别为同一类，否则回退 `generic`。
  - 四类轮廓与通用主机的内联 SVG，使用 `currentColor` 单色描边。
  - 收起侧栏的同轮廓实例后缀、完整型号 `aria-label`/`title`，并让展开侧栏和概览行复用同一轮廓。
- `wattline/static/monitor.css`
  - 64px 收起侧栏中 24px 轮廓、绝对定位状态点和 9px 实例后缀；展开侧栏保持 18px 轮廓与名称布局。
- `tools/browser_smoke.py`
  - 新增 AN-64 合成检查；AN-48 收起侧栏断言由“通用图标隐藏”更新为“机型轮廓可见且可访问名称含完整型号”。
- `README.md`
  - 收起侧栏说明更新为机型轮廓、回退、状态独立和同型号后缀。

未新增后端字段、配置字段、数据库迁移或 HTTP 契约变更。

## Commands and results

### Python, JavaScript and localization

```sh
.venv/bin/python -m pytest -q
# 18 passed, 1 warning in 0.70s

node --check wattline/static/monitor.js
# exit 0

node tools/test_i18n.cjs
# PASS: 274 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage
```

### Synthetic Chromium check

```sh
.venv/bin/python tools/browser_smoke.py
# exit 0; result PASS; Chromium 159.0.8154.6; page_errors []
```

新检查的合成机器与结果：

| 实例 | 设备名 | 期望/实际轮廓 | 收起侧栏可见后缀 |
| --- | --- | --- | --- |
| 机柜 B300 甲 | `NVIDIA B300 SXM6 AC` | `b300` / `b300` | `0甲` |
| 机柜 B300 乙 | `NVIDIA B300 SXM6 AC` | `b300` / `b300` | `0乙` |
| 工作站 PRO 6000 | `NVIDIA RTX PRO 6000 Blackwell Workstation Edition` | `pro6000` / `pro6000` | 无（单实例） |
| Spark 方盒 | `NVIDIA GB10` | `spark` / `spark` | 无（单实例） |
| 桌面 5090 | `NVIDIA GeForce RTX 5090` | `rtx5090` / `rtx5090` | 无（单实例） |
| 未知机型 | `NVIDIA Synthetic GPU` | `generic` / `generic` | `知机型` |
| 混合机型 | B300 + RTX 5090 | `generic` / `generic` | `合机型` |
| 旧配置无型号 | 无 `devices` 字段 | `generic` / `generic` | `无型号` |

额外分类矩阵全部通过：

- `NVIDIA RTX PRO 6000 Blackwell Max-Q` → `pro6000`；`NVIDIA RTX 6000 Ada Generation` → `generic`，不误判为 PRO 6000。
- `NVIDIA DGX Spark` → `spark`；`NVIDIA GeForce RTX 5090 D` → `rtx5090`。
- 同一设备名重复 → `b300`；B300 + 未知设备名 → `generic`；`null` 设备名、空设备清单 → `generic`。

实际 64px 收起侧栏断言：

- `.rail` 宽 `64px`，每个轮廓边界约 `24×24px`。
- 四类轮廓与通用主机的元素截图 SHA-256 全部不同：`b300`、`pro6000`、`spark`、`rtx5090`、`generic` 共 5 个唯一值。
- 正常/需关注/连接失败状态点实际颜色分别为 `rgb(107, 212, 173)`、`rgb(255, 198, 111)`、`rgb(250, 155, 139)`，且全部可见。
- 同轮廓 B300 实例后缀为 `0甲`/`0乙`，通用回退实例为 `知机型`/`合机型`/`无型号`，组内均不重复；单实例无后缀。
- 每个机器按钮的 `aria-label` 与 `title` 包含实例名、状态和完整型号；混合机型包含两组完整设备名，旧配置无型号时不追加型号。示例：`混合机型 · 正常 · NVIDIA B300 SXM6 AC · NVIDIA GeForce RTX 5090`。
- 键盘 Enter 打开对应机器并聚焦页面标题；选中按钮出现 `aria-current="page"` 且背景与未选中不同；Spark 与总览导航可往返。
- 轮廓颜色唯一为 `rgb(195, 206, 224)`；所有 SVG 子元素的 `fill`/`stroke` 仅使用 `currentColor`（小面积指示点 `fill=currentColor`、`stroke=none`），无额外颜色。
- 实际深色侧栏背景 `rgb(16, 31, 53)`、浅色机器面板背景 `rgb(255, 255, 255)`；侧栏轮廓色 `rgb(195, 206, 224)`，浅色列表轮廓色 `rgb(69, 101, 150)`，两侧均可见。
- 展开后实例名、轮廓和状态同时可见，后缀隐藏，可访问名称不变。
- 收起与展开状态在 320、390、640、731、1440px 均无横向溢出；390px 另存收起和展开截图。

### OpenSpec and diff

```sh
OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-rail-machine-silhouettes --strict
# Change 'add-rail-machine-silhouettes' is valid

git diff --check && git diff --cached --check
# exit 0
```

## Screenshots

脚本写入被忽略的 `artifacts/`，作为本任务附件交付：

| 文件 | 内容 |
| --- | --- |
| `an64-rail-collapsed.png` | 64px 收起侧栏，8 台合成机器、状态点与后缀 |
| `an64-collapsed-desktop.png` | 收起侧栏与总览同屏 |
| `an64-rail-expanded.png` | 展开侧栏，轮廓 + 实例名 + 状态 |
| `an64-overview-light.png` | 浅色机器列表中的同轮廓 |
| `an64-glyph-b300.png` | B300 厚重机柜，实际 24px |
| `an64-glyph-pro6000.png` | RTX PRO 6000 双槽卡，实际 24px |
| `an64-glyph-spark.png` | GB10 紧凑方盒，实际 24px |
| `an64-glyph-rtx5090.png` | RTX 5090 双风扇卡，实际 24px |
| `an64-glyph-generic.png` | 通用主机，实际 24px |
| `an64-collapsed-390.png` | 390px 收起侧栏 |
| `an64-expanded-390.png` | 390px 展开侧栏 |

## Commit

- 实现提交：`a156289bc66c1c65423875b68c6367f19cd48e6f`（parent `f31ed8ddc0a92bd94469546970433e8a8f4b5c56`），包含源码、测试、README 与本 change 的 proposal/spec/design/tasks/verification。
- 提交未包含工作树中的 `AGENTS.md` Multica runtime 注入块；`git show a156289:AGENTS.md` 仍为 39 行通用仓库约定。
- 未推送远端；Mika 在 AN-63 独立审查通过后负责整合、推送并核验远端 `main`。
- 未部署、未更新用户实例、未连接真实节点、未触发真实采集，未读取私有节点配置。

## Limits

- 应用当前只有浅色内容区和深色侧栏，没有独立的应用级深色主题；本变体验证的是这两种实际表面，并确认轮廓使用可继承单色，不声称存在未实现的主题切换。
- 仅在 Chromium 159 合成 API 环境验证；未做 Safari/Firefox、屏幕阅读器人工听读、真实触屏或生产 GPU 型号抽样。
- 型号映射基于 `nvidia-smi` 产品名 token；新的命名变体会安全回退为通用轮廓并在提示中保留真实设备名。
- 本记录为执行者自测，不代表独立审查或用户验收。
