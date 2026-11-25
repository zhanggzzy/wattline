# AN-140 独立复审（AN-141 返工）

2026-11-25（Asia/Shanghai），Reviewer-DeepSeek，Multica 配置模型 `deepseek/deepseek-flash`，macOS arm64。结论 **需修改**。

- 活动 change `style-machine-assignee-chips`（`spec-driven`）；交接 HEAD `d9820cd3655efd70a4a02b39fac38723c17ce2bb`，实现提交 `c6e59a7e0e2d4d475aa820de489c6efb68bc07e5`；返工范围 `592f19fabfca4d844406691cb7f2ba0e35822001..d9820cd`。
- 对照基线为 AN-137 被审提交 `592f19fabfca4d844406691cb7f2ba0e35822001` 和本地 `origin/main` 跟踪基线 `a738dabfd17d830be6fb8580cc6ea6570a63020d`；本轮未推送远端。
- 独立复现使用新写的 `artifacts/an140-review/probe.py`、`identity.py`、`sweep.py`，不依赖执行者断言；对照浏览器只替换相应提交的 `index.html`、`monitor.css`、`monitor.js`、`locales.js`。合成节点、临时 SQLite，Chromium Headless Shell 158.0.8127.18。

## AN-137 两项结论已修复

1. **临界宽度横向裁切。** 同一英文夹具下，`592f19f` 在展开导航 1156（容器 861）与折叠导航 986/1024（容器 861/897）列表 `scrollWidth` 为 901，表格实际宽 901.06，Memory 表头与指标落在可视区外；`d9820cd` 对应测量为 861/861、861/861、897/897，表格宽 860.66，七列表头、状态、使用者、GPU、功耗、CPU、Memory 及 `1800.0 GiB used` 均在列内。页面在 1156 时 `scrollWidth=1156`。卡片/表格切换点如实为展开 1155/1156、折叠 985/986；两导航、两语言逐像素往返 168 次采样，切换点两侧与过程中列表和页面都无横向滚动，指标文字与卡片标签都在可用区域内。
2. **折行后姓名不可区分。** 基线在展开 1156 时两颗 Ada 胶囊均为 72 px、两行，逐字坐标完全相同（`L` 都在 `(9, 23.19)`）；`d9820cd` 同宽度为单行 96.09/99.28 px，本身可区分。约束到 80/70/60 px 后两颗胶囊仍折行，`L` 分别为 `12.19/15.38`；弹窗约束 65 px 为 `3.33/6.66`。列表宽度 30–180 px 逐像素扫描除 25–28 px 外都可区分；25–28 px 时字形已被挤出胶囊、在现有布局不可达（表格使用者列内容宽 122 px）。DOM 文本保留单/双空格原文，未生成 `<b>` 等元素，checkbox 的 `aria-label` 与实际姓名一致。

补充：基线在 320 px 卡片下页面滚动宽度 346、内存说明跨出单元格；`d9820cd` 为 320，内存说明在卡片内换行，属改善。

## 需修改

**P2｜表格机器标识内容超出本列，压到状态徽章下并在徽章边缘硬截断。** 新增的固定列宽把第一列压到 24%，但 `.row-open`（`wattline/static/monitor.js:352` 一带，样式在 `monitor.css:107`）仍是 170 px 名称/地址加图标和间距的收缩宽度，没有随 147.55 px 的 `.machine-identity` 收窄，`min-width:0` 只作用在内部 `span`，不足以让按钮收缩：

- 展开导航 1156 / 折叠导航 986（容器 861）：第一列 `td` 宽 206.55，内容右边界 454.22，`.row-open` 宽 196、右边界 502.67，超出 `td` 36.45 px；`strong`/`small` 仍为 170 px。逐字测量有 6 个地址字形落在 `td` 右边界之外，并与状态徽章所在行相交。
- 折叠导航 1024（容器 897）超出 27.8 px，展开导航 1200（容器 902）超出 26.5 px；表格容器约 1012 px 以上才完全收回，即展开导航约 1156–1307、折叠导航约 986–1137 CSS px 的常见窗口宽度都受影响。
- 可见结果为：长机器名在状态徽章左缘被直接截断（`…` 画在 170 px 盒右端，被徽章遮住），长 SSH 别名同样延伸到徽章下方；`identity-overflow-long.png` 中「长机器名 长机器名 长机」「uuuuuu…」都止于「Needs attention」徽章边缘。基线 `592f19f` 的自动列宽下第一列为 255 px，无此溢出，说明是本轮固定列宽引入的回归。
- 与 change 记载矛盾：`design.md` 声称对「machine identity」做了约束，`verification.md` 声称长机器名与地址均在可用区域内；但 `tools/browser_smoke.py` 的边界扫描用 `wraps = card || !cell.querySelector('.row-open')` 在表格模式明确跳过了第一列，因此既有回归覆盖不到此路径。
- 建议方向（供返工参考，不代为实现）：给 `.row-open` 明确 `width:100%`/`max-width:100%` 或在 `.machine-identity` 上截断，使名称/地址在列内省略；返工后把机器标识列纳入 861–约 1012 px 容器的边界断言，并用长机器名、长别名复查两种导航与两种语言。

## 通过项与命令

| 命令 | 退出码 | 实际结果 |
| --- | ---: | --- |
| `.venv/bin/python -m pytest -q` | 0 | `44 passed, 1 warning`（既有 Starlette/httpx 弃用） |
| `node --check wattline/static/monitor.js`；`node --check wattline/static/locales.js` | 0；0 | 无输出 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 311 message keys, …` |
| `.venv/bin/python tools/browser_smoke.py --browser "$sr_bin"` | 0 | `result: PASS`，`page_errors: []`，28 张截图，两语言对话框 |
| `.venv/bin/python artifacts/an140-review/probe.py "$sr_bin"` | 0 | 现实现 0 失败；`probe.json`，含 30 布局、16 压力、168 连续缩放、16 折行、4 弹窗记录 |
| 同上 `--static-ref 592f19f…` | 1（预期） | 复现 AN-137：1156/986/1024 `scrollWidth` 901、Memory 在可视区外、两 Ada 字形一致；`probe-base.json` |
| `.venv/bin/python artifacts/an140-review/identity.py "$sr_bin"` | 0 | 标识列 206.55 / `.row-open` 502.67 / `td` 右界 466.22，6 个字形越界 |
| `.venv/bin/python artifacts/an140-review/sweep.py "$sr_bin"` | 0 | 列表 30–180 px、弹窗 20–140 px 均可在折行时区分；仅列表 25–28 px 相同且字形出框 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate style-machine-assignee-chips --strict` | 0 | `Change 'style-machine-assignee-chips' is valid` |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate --specs --strict` | 0 | `Totals: 7 passed, 0 failed` |
| `git diff --check`；`git diff --cached --check`；`git diff --check 592f19f..d9820cd` | 0；0；0 | 无输出 |

工作树只保留原有 `AGENTS.md` 运行时注入（220 行新增，索引中无该标记），审查未改代码或测试。

## 覆盖与限制

Chromium Headless Shell、合成节点、临时 SQLite、Playwright 可访问名称与焦点断言。未实测 Firefox、Safari、真实屏幕阅读器、真实节点、用户实例或部署；保存失败、旧名单迁移等既有路径沿用 `tools/browser_smoke.py` 的通过记录，本轮未另建夹具。未操作实例、未推送远端。复审结论为需修改，Mika 安排返工后需重新复审；活动 change 保持，3.3/3.4 仍未完成。
