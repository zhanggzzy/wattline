# Wattline 前端设计与验证（AN-27）

本次统一总览、机器和 GPU 详情的视觉层级及交互体验。保留现有 API、采样口径、可信归属、容器视角、设置、移除、排序和历史窗口；不迁移框架，不增加运行时依赖。页面直接读取服务数据，测试脚本中的合成响应仅用于验证。

## 官方依据

核实于 2026-11-18。Google Chrome 官方 [Modern Web Guidance](https://developer.chrome.com/docs/modern-web-guidance) 为 Web 平台工程指导集合；视觉色彩与工作台布局是本项目的设计选择。采用官方仓库 [v1.0.1](https://github.com/GoogleChrome/modern-web-guidance/releases/tag/v1.0.1)，GitHub API 的发布时间为 **2026-11-16T14:59:10Z**，tag 指向 **64a6d708f5a43f2cd3fde5d4d7db3905ba1bdf65**。本轮直接浏览官方说明并通过 gh API 读取固定 tag 的指导原文，未安装其 CLI、未启用遥测。

以下指导为 GoogleChrome/modern-web-guidance 项目作者提供的 CC-BY-4.0 文档。实现参考其建议，未复制示例代码；具体设计映射如下：

| 官方原文（固定版本） | 本次实现 |
| --- | --- |
| [Responsive design](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/guides/css/responsive-design.md) | Grid 布局、rem 与 viewport 组合的 clamp 标题；≤975px 时概览指标降为两列，为侧栏占用空间预留数字宽度；动态视口高度限制对话框，系统字体无需网络字体请求。 |
| [Responsive tables](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/guides/ui-atoms/responsive-table.md) | 机器列表按自身容器 620px 阈值变为带字段标签的卡片；保留 GPU、功耗、CPU、内存；进程表提供可键盘聚焦且具名称的横向滚动区域。 |
| [Accessibility](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/guides/accessibility/accessibility.md) | 跳到主要内容链接、明显焦点、较大点击目标；状态同时使用文字与色彩；图表增加有效时段/最近值摘要及方向键读数播报；刷新重建后在原容器按控件类型和完整 dataset 恢复焦点，必要时滚入视口。 |
| [Dialog](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/guides/ui-components/dialog.md) | 延用原生 dialog/showModal，安全的取消默认焦点与 Escape；模态期间推迟结构重建，保持调用按钮供浏览器返回焦点；滚动链约束为渐进增强。 |

未采用不适合本次工作台的新增平台 API。无容器查询时维持桌面表格和横向滚动；已有浏览器 API（如 AbortSignal.any）要求沿用原项目现代浏览器环境，未扩展旧浏览器兼容范围。

## 设计与代码入口

- `wattline/static/index.html`：品牌说明、跳转链接、初次加载状态。
- `wattline/static/monitor.css`：深蓝导航、浅色内容、统一主操作与状态语义；留白、数字层级、组件尺寸、窄屏导航和卡片重排、强制颜色与减少动态效果。
- `wattline/static/monitor.js`：总览与详情标题层级，空清单与搜索无结果的区分，首次连接错误，图表摘要和播报，刷新焦点保留。
- `tools/browser_smoke.py`：运行实际页面 JavaScript，以 Playwright 拦截 API 并注入合成数据；绝不启动后端、采集器或 SSH。
- `pyproject.toml`：仅增加可选 browser-test 依赖，不影响产品运行安装。

## 可复现验证

使用任务独立 Python 3.11 虚拟环境：

~~~sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[test,browser-test]'
node --check wattline/static/monitor.js
.venv/bin/python -m pytest -q
.venv/bin/python tools/browser_smoke.py --browser "/path/to/Chromium executable"
git diff --check
~~~

执行结果：

- JavaScript 语法检查和 diff 空白检查均成功。
- pytest（第一轮返工复测）：**16 passed, 1 warning in 1.29s**。警告来自已解析依赖 Starlette 的 TestClient/httpx 弃用提示；测试本身全部通过。
- Playwright：Chromium **158.0.8127.18**；**PASS**，页面 JavaScript 错误 **0**，记录 3 次合成写请求（排序、设置保存、新增失败）。
- 实际检查：320/390/514/515/516/640/729/730/731/732/759/760/761/974/975/976/977/1024/1440px 均无页面横向溢出；用真实格式化的“2,468”检查四张指标卡的文字边界全部位于卡片内。搜索、状态筛选、键盘排序、GPU 详情、进程与归属显示、七天窗口、图表方向键播报、配置保存、移除取消及焦点返回、新增失败提示继续通过。
- 第一轮返工的焦点断言：390/731/1440px 下分别明确定位 `#host-rows` 行按钮、需要关注按钮和 `#rail-nav` 导航按钮；改变 snapshot 的 reason 触发 shape 重建，检查旧元素确已断开、新元素保持焦点且完整位于视口内，共 9 种组合。不会用全局 `[data-host]` 的首个匹配代替行按钮。补充截图 `metrics-731.png`、`metrics-760.png`、`focus-row-390.png`，脚本共输出 10 张截图。
- 正常/离线同屏、空清单、首次服务错误、真实 pending fetch 的加载状态均截图检查。桌面及详情为整页截图；手机概览采用视口截图，机器卡片另附独立截图，避免浏览器长图合成重复。

截图由脚本生成到忽略的 artifacts 目录，作为 Multica 附件交付。所有节点、地址、GPU、账户及数据均为合成内容。脚本不依赖本机私有配置。

限制：本轮为执行者自测；独立审查交 Reviewer-DeepSeek。未进行 Safari/Firefox 实机、屏幕阅读器人工听读、真实触屏拖动、Lighthouse 性能评分或真实节点端到端采集。已有后端回归覆盖容器、未知归属、固定主机身份、单节点清理与历史归档，前端展示继续使用这些现有字段和判定。

## 第一轮返工与交接

AN-26 独立审查指出的两项问题均已复现并修复：

- 焦点：旧版全局 dataset 子集匹配把行按钮恢复到同一机器的侧栏按钮；现按原祖先容器、相同按钮 class 和完整 dataset 匹配，优先保留稳定 id。控件超出视口时按最近边缘滚入。
- 指标：731px 下四列卡片每列约 118px，“2,468”超出约 3px；现 ≤975px 使用两列，731px 下每列约 252px。保留现有手机字号及桌面四列。

新增浏览器断言在修复前分别失败于 731px 的文字边界、390px 的行按钮焦点，修复后全部通过。上述结果是执行者自测，需由 AN-26 独立复审；官方来源沿用本报告固定版本及首轮审查核验结论。

配置格式、API、数据库及归档格式均未改动，无迁移步骤。没有读取或更改用户实例，没有部署、重启、真实采集或 SSH。继续更新同一 PR #2；Mika 在独立复审通过后整合并核验远端 main。用户实例更新由另行发起的 Codex 部署会话处理，本任务不执行。
