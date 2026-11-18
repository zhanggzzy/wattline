# Wattline 前端设计与验证（AN-27）

本次统一总览、机器和 GPU 详情的视觉层级及交互体验。保留现有 API、采样口径、可信归属、容器视角、设置、移除、排序和历史窗口；不迁移框架，不增加运行时依赖。页面直接读取服务数据，测试脚本中的合成响应仅用于验证。

## 官方依据

核实于 2026-11-18。Google Chrome 官方 [Modern Web Guidance](https://developer.chrome.com/docs/modern-web-guidance) 为 Web 平台工程指导集合；视觉色彩与工作台布局是本项目的设计选择。采用官方仓库 [v1.0.1](https://github.com/GoogleChrome/modern-web-guidance/releases/tag/v1.0.1)，GitHub API 的发布时间为 **2026-11-16T14:59:10Z**，tag 指向 **64a6d708f5a43f2cd3fde5d4d7db3905ba1bdf65**。本轮直接浏览官方说明并通过 gh API 读取固定 tag 的指导原文，未安装其 CLI、未启用遥测。

以下指导为 GoogleChrome/modern-web-guidance 项目作者提供的 CC-BY-4.0 文档。实现参考其建议，未复制示例代码；具体设计映射如下：

| 官方原文（固定版本） | 本次实现 |
| --- | --- |
| [Responsive design](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/guides/css/responsive-design.md) | Grid 布局、rem 与 viewport 组合的 clamp 标题；动态视口高度限制对话框，系统字体无需网络字体请求。 |
| [Responsive tables](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/guides/ui-atoms/responsive-table.md) | 机器列表按自身容器 620px 阈值变为带字段标签的卡片；保留 GPU、功耗、CPU、内存；进程表提供可键盘聚焦且具名称的横向滚动区域。 |
| [Accessibility](https://github.com/GoogleChrome/modern-web-guidance/blob/v1.0.1/skills/modern-web-guidance/guides/accessibility/accessibility.md) | 跳到主要内容链接、明显焦点、较大点击目标；状态同时使用文字与色彩；图表增加有效时段/最近值摘要及方向键读数播报；刷新重建后恢复操作焦点。 |
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
- pytest：**16 passed, 1 warning in 1.00s**。警告来自已解析依赖 Starlette 的 TestClient/httpx 弃用提示；测试本身全部通过。
- Playwright：Chromium **158.0.8127.18**；**PASS**，页面 JavaScript 错误 **0**，记录 3 次合成写请求（排序、设置保存、新增失败）。
- 实际检查：桌面 1440px、390px 手机、320/640/1024px 无页面横向溢出；搜索、状态筛选、键盘排序、GPU 详情、进程与归属显示、七天窗口、图表方向键播报、配置保存、移除取消及焦点返回、新增失败提示、刷新后焦点保留。
- 正常/离线同屏、空清单、首次服务错误、真实 pending fetch 的加载状态均截图检查。桌面及详情为整页截图；手机概览采用视口截图，机器卡片另附独立截图，避免浏览器长图合成重复。

截图由脚本生成到忽略的 artifacts 目录，作为 Multica 附件交付。所有节点、地址、GPU、账户及数据均为合成内容。脚本不依赖本机私有配置。

限制：本轮为执行者自测；独立审查交 Reviewer-DeepSeek。未进行 Safari/Firefox 实机、屏幕阅读器人工听读、真实触屏拖动、Lighthouse 性能评分或真实节点端到端采集。已有后端回归覆盖容器、未知归属、固定主机身份、单节点清理与历史归档，前端展示继续使用这些现有字段和判定。

## 配置、部署与回滚交接

配置格式、API、数据库及归档格式均未改动，无迁移步骤。没有读取或更改用户实例；没有部署、重启、真实采集、SSH、合并 PR。

用户授权上线后由管理部署实例的 Codex 实施：

1. 保存当前代码版本、运行方式和静态资产；按既有流程备份私有配置、注册表与数据。继续保留实例原有 archive_timezone 等设置。
2. 从 PR 的明确 head 提交构建安装 Wattline；不要直接用 main 代替待验收版本。旧实例入口原为 compute_monitor，迁移到 Wattline 的安装/模块入口属于独立部署步骤，不能只把新静态文件覆盖进旧 AlayaDeck。
3. 以独立停用节点配置启动待验证版本，确认页面可加载、各状态、设置、排序、GPU/进程及历史窗口；核验 API/静态资源响应，之后依实例授权流程切换并刷新浏览器缓存。
4. 回滚至部署前记录的代码/包与启动方式；本次未改数据结构，通常无需恢复数据。仅在数据本身被后续部署操作更改且需要恢复时使用备份，避免覆盖新采样。验证原入口与资产版本一致。

本次 PR 只交付产品前端变更与证据，不代表用户部署已更新。
