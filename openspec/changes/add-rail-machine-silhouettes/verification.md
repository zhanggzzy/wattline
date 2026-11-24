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

## AN-68 整改验证（2026-11-24）

以下为 Executor-OMP 针对 AN-63 五项审查发现的整改自测，仍不是独立复审；复审由 AN-67 执行。

### 基线与范围

- 审查基线：`bdfb908c901851eac1868e77dbabad8f45376365`。
- 沿用活动 change `add-rail-machine-silhouettes`（`spec-driven`，CLI 1.14.2），只修改前端、合成浏览器检查、多语言文案和本 change 记录。
- 工作树原有 `AGENTS.md` Multica runtime 注入块保持未暂存，未纳入整改提交。
- 未改采集、快照、历史、配置或 HTTP 契约。

### 整改对应

| AN-63 发现 | 整改 |
| --- | --- |
| P1 未选中机器轮询只更新型号后仍显示旧图标和提示 | 渲染签名对每台机器加入机型识别结果与完整设备名；合成检查在总览和选中其他机器时各轮询一次并断言侧栏、总览、提示和后缀分组更新 |
| P1 已知机型加空名称、部分清单仍标 B300 | 任一空设备名、期望数量不一致或在线样本 `gpu_inventory_complete=false` 均回退 `generic`；仍保留已知非空名称；离线且完整可信的历史清单继续显示 B300 |
| P2 单条多机型词与 `PRO 60000` 误判 | 每个设备名必须恰好命中一个机型；`PRO 6000` 增加数字边界 |
| P2 Unicode 后缀截断、同名实例身份重复 | 后缀按 grapheme 截取；身份文本完全相同时追加 `实例 {后缀}`，可见后缀、`aria-label` 和 `title` 均可区分 |
| P3 状态点自己的提示只含状态 | 状态点去掉独立 `title`，悬停按钮任意位置命中按钮的完整身份提示 |

### 命令与结果

```sh
.venv/bin/python -m pytest -q
# 18 passed, 1 warning in 0.67s

node --check wattline/static/monitor.js
node --check wattline/static/locales.js
node tools/test_i18n.cjs
# PASS: 275 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage

.venv/bin/python tools/browser_smoke.py --browser "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"
# exit 0; result PASS; Chromium 158.0.8127.18; page_errors []
```

合成 Chromium 整改结果：

- 轮询总览：`更新节点` 从空清单变为 B300 后，侧栏与总览 `data-model` 均为 `b300`，提示为 `更新节点 · 正常 · NVIDIA B300 SXM6 AC`，后缀进入 B300 分组。
- 选中 `Spark 方盒` 时再次轮询：`更新节点` 变为 `pro6000`，提示含完整 PRO 6000 名称，同型后缀由 `1` 变为 `节点`；页面仍停留在 Spark，`aria-current` 未变。
- 分类矩阵：`[B300, null]`、期望 2 张但保留 1 张、在线 `gpu_inventory_complete=false`、`NVIDIA B300 / GeForce RTX 5090`、`NVIDIA PRO 60000` 均为 `generic`；完整可信的离线 B300 与在线 B300 仍为 `b300`。
- 同名实例：可见后缀 `3` / `4`，可访问名称与提示分别为 `相同别名 · 正常 · NVIDIA B300 SXM6 AC · 实例 3` 和 `… 实例 4`。
- Unicode：可见后缀为 `🚀🚀` 与 `🛸🚀`，无替换字符，实际渲染截图 SHA-256 分别为 `baa0aa87…38dc6` 和 `c490fb4b…dc8c3d8`，互不相同。
- 悬停：`.machine-icon` 与 `.status-dot` 命中的最近 `title` 都是 `混合机型 · 正常 · NVIDIA B300 SXM6 AC · NVIDIA GeForce RTX 5090`。
- 原有浅色/深色、单色、24px/18px、状态点、选中、Tab、Space、折叠/展开和 320/390/640/731/1440px 无横向溢出检查继续通过。

AN-63 复现脚本（附件 `review_browser.py`，原 SHA-256 `647bc7db52993451e4206f69d23f89808ea27f65930d2f891cf87ce6393c319d`；仅将输出目录改为 `artifacts/an68-an63-rerun`）复跑：

```sh
.venv/bin/python artifacts/an68-an63-rerun/review_browser.py "$chromium" > artifacts/an68-an63-rerun/results.json
# exit 0; failures []
```

关键复跑值：`model_after_poll=b300`、`overview_model_after_poll=b300`、`tooltip_after_poll=更新节点 · 正常 · NVIDIA B300 SXM6 AC`；`missing/partial/ambiguous/near` 均为 `generic` 且提示保留已知完整名称；同名实例身份分别带 `实例 2` / `实例 3`；Unicode 后缀渲染哈希不同；状态点悬停返回按钮完整提示。

### OpenSpec 与 diff

```sh
OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 status --change add-rail-machine-silhouettes
# Schema: spec-driven; progress 4/4 artifacts complete

OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-rail-machine-silhouettes --strict
# Change 'add-rail-machine-silhouettes' is valid

git diff --check
git diff --cached --check
# exit 0
```

### 证据与限制

- 整改截图仍写入被忽略的 `artifacts/`：`an64-*` 系列，以及整改新增的 `an64-suffix-unicode-a.png`、`an64-suffix-unicode-b.png`。
- 浅色折叠侧栏证据使用测试临时注入的浅色背景与继承色；应用根节点仍固定 `color-scheme: light`，侧栏实际使用深色背景。
- 仅在 macOS Chromium 158 合成 API 环境验证；未运行 Safari/Firefox、屏幕阅读器人工听读、真实触屏或真实 GPU 型号抽样。
- 未推送远端、未部署、未连接真实节点、未读取私有节点配置。整改交付 SHA 记录在本子任务评论；以该 SHA 的实际 `git show` 为准。

## AN-70 第二轮整改验证（2026-11-24）

本节记录执行者自测。OpenSpec `add-rail-machine-silhouettes` 保持活动，由 AN-69 独立复审。

- 本地审查基线为 `6a1b5c878a2fc2608a780cdb80122ded31e4e691`，核对时远端 `main` 为 `f31ed8ddc0a92bd94469546970433e8a8f4b5c56`。整改通过本地提交交付，完整 SHA 与实际 diff 见 AN-70 交接。
- 机器快照新增 `gpu_inventory_complete`。`true` 表示采样已确认清单完整，`false` 表示不完整，`null` 表示无证据。热层和温层使用已有采样指标恢复可信度。旧前端可忽略新增字段。新前端读取旧快照时从当前指标取明确证据，旧离线清单无证据时显示通用轮廓并保留完整名称。配置和持久化格式无需迁移。
- 相同或 NFC 等价的别名显示独立后缀，焦点提示和可访问名称保留原始别名并包含该后缀。合成 Chromium 返回 `Café` 和 `Café` 的后缀 5、6，跨轮廓的第三个相同别名使用 7。
- 完整 B300 在正常、离线和过期时均保持机型。部分 B300 在在线和离线时均为 `generic`，恢复完整后回到 `b300`，再变部分清单时回退。两种状态均可读取完整的 `NVIDIA B300 SXM6 AC`。旧在线快照显式完整时仍为 `b300`，旧离线快照无证据时为 `generic`。
- 标准工作站版和 Max-Q 版均识别为 `pro6000`。检测到紧邻字母、数字、连接符号或汉字的未知型号时回退。`NVIDIA PRO 6000X` 在合成 XML 到实际侧栏的复跑中显示完整原名和通用轮廓。

### 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | 21 passed，1 条既有 Starlette/httpx 弃用告警。新增合成 XML 的完整、部分、合并保留、空清单、离线、过期、恢复，以及热层和温层历史恢复测试。 |
| `node --check wattline/static/monitor.js` 和 `node --check wattline/static/locales.js` | 0 | 两项语法检查通过。 |
| `node tools/test_i18n.cjs` | 0 | PASS，275 个文案键，检查占位符、引用、插值、Intl、持久化及回退。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-rail-machine-silhouettes --strict` | 0 | `Change 'add-rail-machine-silhouettes' is valid`。CLI `--version` 返回 `1.14.2`。 |
| `git diff --check` 和 `git diff --cached --check` | 0 | 工作树及待提交 diff 均通过。索引中的 `AGENTS.md` 仅含仓库约定。 |
| 下方合成 Chromium 命令 | 0 | Chromium 158.0.8127.18，仓库 smoke 为 `PASS`，两份审查复跑均为 `failures: []`，三份结果均为 `page_errors: []`。 |

```sh
rail_chromium="$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1254/chrome-headless-shell-mac-arm64/chrome-headless-shell"
.venv/bin/python tools/browser_smoke.py --browser "$rail_chromium" > artifacts/an70/repo-smoke.json
.venv/bin/python artifacts/an70/an63/review_browser.py "$rail_chromium" > artifacts/an70/an63/results.json
.venv/bin/python artifacts/an70/an67/review_edges.py "$rail_chromium" > artifacts/an70/an67/results.json
```

- AN-63 的 `review_browser.py` 原附件 SHA-256 为 `647bc7db52993451e4206f69d23f89808ea27f65930d2f891cf87ce6393c319d`。原脚本在由基线 `git archive` 提取的静态资源上运行，退出码 0，`failures: []`。在整改代码上复跑时，除输出目录外，仅在原脚本预期为可信离线 B300 的 `rack-a` 夹具新增 `gpu_inventory_complete: true`。原夹具缺少此证据的情形已由仓库 smoke 单独断言通用轮廓和完整提示。
- AN-67 的 `review_edges.py` 原附件 SHA-256 为 `dfe3ccce8a2b0566bae9330354954e866257521cbba91e332c2dae3e30d268d5`，复跑脚本与附件内容一致。其 JSON 的离线快照字段取自旧的 `metrics`，因此该打印值为 `null`。新增顶层字段由后端用例直接断言。
- 首次运行仓库 smoke 发现原断言要求轮询后更新节点的后缀文本必须变化。修正后断言 PRO 6000 从单实例变为同轮廓双实例，检查两个后缀都出现且彼此不同，更新节点可保留仍然唯一的名称后缀。再次运行通过，合计 24 项型号分类检查。

### 覆盖限制

- 使用 macOS Chromium 158、合成 API、合成 NVIDIA XML 和临时历史库。浅色折叠侧栏证据来自审查脚本注入的测试配色。覆盖实际 64px 折叠尺寸、键盘焦点和单色轮廓，Safari、Firefox、人工屏幕阅读器和真实 GPU 抽样仍待验证。
- 独立复审、同步规范、归档和远端 main 整合待 Mika 按项目流程推进。本轮只涉及本地开发，没有实例更新。
