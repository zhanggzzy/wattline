# AN-143 独立复验记录

2026-11-25（Asia/Shanghai），Reviewer-DeepSeek，Multica 配置模型 `deepseek/deepseek-flash`，macOS arm64。结论 **通过**。

- 活动 change `style-machine-assignee-chips`（`spec-driven`）。被审实现提交 `a0dc9dfff981b2e141bb0af5e41e2de51ea851a3`（`git diff d9820cd..a0dc9df`），验收证据 HEAD `4179daef0634c3a58f899860989a865a4affe41e`；AN-140 被审基线 `d9820cd3655efd70a4a02b39fac38723c17ce2bb`；本地 `origin/main` 跟踪基线 `a738dabfd17d830be6fb8580cc6ea6570a63020d`。本轮未推送远端。
- 范围仅为 AN-140 报告的表格首列越界。代码与测试只读；未改 `review-an-140.md` 或 `artifacts/an140-review/`，仅新增本记录和忽略目录 `artifacts/an143-review/` 下的独立脚本、JSON 与截图。工作树只保留原有 `AGENTS.md` 运行时注入（220 行新增，索引中无该标记）。

## 独立复现（基线 `d9820cd`）

新写 `artifacts/an143-review/verify_an143.py`，不调用执行者的 `verify_an144.py`，只按 AN-140 夹具重建合成节点、临时 SQLite 与人员，并在对照时仅从 Git 取旧提交的 `index.html`、`monitor.css`、`monitor.js`、`locales.js`。

- 基线失败 20/124 条布局记录（Alpha / Long）。英文展开 1156（容器 861）：`td` 内容右界 454.22，`.row-open` 306.67→502.67，相邻状态单元左界 466.22，长名/别名有 12 个已绘制字形越界，其中长名字形侵入徽章行；折叠 986 同样为 289.17 对 301.17。展开 1310（容器 1008）仍为 506 对 504.91，仍有 1.09 px 越界，说明该现象略超出 AN-140 约 1012 px 的估计。
- 卡片宽度 320/985/1155 未复现该越界；可见结果为 `alpha-d9820cd-expanded-1156.png` 中 SSH 别名伸到 “Healthy” 徽章下方。
- 独立断言按字形 Range 裁剪后再与状态徽章、状态单元求交，并用 `document.elementFromPoint` 采样可见字形中心；未复用 `tools/browser_smoke.py` 的新增断言。

## 修复后结果

修复为 `.machine-identity { flex: 1 1 auto; min-width: 0; }`、`.row-open { max-width: 100%; }`、`strong/small { max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }`，卡片容器继续整段换行。

- 64 条固定布局（2 夹具 × 2 导航 × 2 语言 × 8 视口）与 208 条切换边界往返布局全部 0 失败、0 页面错误。列表与页面都无横向滚动；七列表头和四个指标均落在列表内，指标值与内存说明完整；可访问名称保持 `View/查看 + 完整机器名`；活动行四个只读胶囊文本原样、空行显示本地化“未登记 / Not assigned”。
- 关键测量（英文，活动行）：

| 视口 | 容器 | 模式 | `td` 内容右界 | `.row-open` 宽/右界 | 状态单元左界 | 截断 |
| --- | ---: | --- | ---: | --- | ---: | --- |
| 展开 1156 | 861 | 表格 | 454.22 | 147.55 / 454.22 | 466.22 | 别名省略 |
| 展开 1200 | 902 | 表格 | 465.47 | 157.47 / 465.47 | 477.47 | 别名省略 |
| 折叠 986 | 861 | 表格 | 289.17 | 147.59 / 289.17 | 301.17 | 别名省略 |
| 折叠 1024 | 897 | 表格 | 298.89 | 156.17 / 298.89 | 310.89 | 别名省略 |
| 展开 1440 | 1138 | 表格 | 524.11 | 214.11 / 524.11 | 536.11 | 长名与别名省略 |
| 展开 320 | 286 | 卡片 | 274.00 | 190 / 274.00 | 卡片堆叠 | 完整换行 |

- Long 夹具在 1156/1200/986/1024/1440 的机器名与 SSH 别名都按列内省略显示；320 卡片内完整换行。中文与英文测量一致。
- 边界在两种语言、两种导航下均为展开 1155 卡片/1156 表格、折叠 985 卡片/986 表格；切换点上下各 12 px 往返无溢出。逐字形检查中每行 26–33 个可见字形采样均能命中自身，没有命中状态单元或徽章，证明不是仅靠几何外套判断。
- 交互保持：键盘 Enter 进入详情 → “使用者”编辑器；4 项初始选中，Space 后计数 4→3；保存移除一人后列表剩 3 个胶囊，再次修改并取消后仍为 3；焦点环 `outline: solid 2px`、`:focus-visible` 为真；方向键重排与指针拖动重排均成功。

## 命令与结果

环境：Python 3.11.17、Node 26.11.0、Playwright 1.65.2、Chromium Headless Shell `158.0.8127.18`、OpenSpec `1.14.2`。

| 命令 | 退出码 | 实际结果 |
| --- | ---: | --- |
| `.venv/bin/python -m pytest -q` | 0 | `44 passed, 1 warning`（既有 Starlette/httpx 弃用） |
| `node --check wattline/static/monitor.js`；`node --check wattline/static/locales.js` | 0；0 | 无输出 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 311 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage` |
| `.venv/bin/python tools/browser_smoke.py --browser "$sr_bin"` | 0 | `result: PASS`，`page_errors: []`，52 组布局，切换边界展开 1155/1156、折叠 985/986，含新增首列边界与省略断言 |
| `.venv/bin/python artifacts/an143-review/verify_an143.py "$sr_bin"` | 0 | 64 固定布局 + 208 边界布局，0 失败、0 页面错误；`verify-an143-fixed.json` |
| 同上 `--static-ref d9820cd3655efd70a4a02b39fac38723c17ce2bb` | 0（断言基线必须有失败） | 复现首列越界 20/124 条；`verify-an143-d9820cd.json` |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate style-machine-assignee-chips --strict` | 0 | `Change 'style-machine-assignee-chips' is valid` |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate --specs --strict` | 0 | `Totals: 7 passed, 0 failed (7 items)` |
| `git diff --check`；`git diff --cached --check`；`git diff --check d9820cd..a0dc9df` | 0；0；0 | 无输出；`git show :AGENTS.md` 不含运行时注入 |

证据哈希：`verify-an143-fixed.json` `286bb48b…`，`verify-an143-d9820cd.json` `6624221b…`，`browser-smoke.json` `8fa7ffa8…`，`verify_an143.py` `214b0a9a…`。截图共 28 张，覆盖两夹具 × 两导航 × 320/986/1024/1156/1200/1440 的修复前/修复后。

## 观察（非缺陷）

固定 24% 首列减去拖动柄与图标后，容器 861 时文字宽 121.55 px；因此 “Synthetic unassigned” 这类约 20 字符的名称在 861–约 1012 px 容器也会显示省略号。完整名称保留在按钮 `aria-label` 与可访问名称中，不重叠状态徽章，符合本轮批准的固定列宽方案；若产品希望此宽度显示更多名称，需要另行决策，不构成本轮返工项。

## 覆盖与限制

Chromium Headless Shell、合成节点、临时 SQLite、900 px 视口高度、Playwright 可访问名称与焦点断言。未实测 Firefox、Safari、真实屏幕阅读器、真实节点、用户实例或部署；未触发采集、未改 API/配置/SQLite/归档格式。复审只验证 AN-140 的首列越界及既有七列、指标、胶囊与多选回归，不代替 Mika 的 main 整合、规范同步/归档或用户验收。`tasks.md` 3.3 待 Mika 收录本记录后勾选，3.4 仍待远端核验。
