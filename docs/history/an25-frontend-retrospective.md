# AN-25 前端变更事后记录

**整理日期：2026-11-18。记录性质：事后补档。** 本文由 AN-28 的执行子任务
AN-33 在 PR #2 合并之后整理，所属 OpenSpec change 为
`enable-openspec-and-backfill-an25`。AN-25 前端实施、首轮审查及返工时**未走
OpenSpec**；本文不是当时的提案、设计规范或测试计划，也不重新实施或重新验收 AN-25。

## 需求与实际成果

AN-25 的原需求是参考 Google Modern Web Guidance 重构 Wattline 前端设计。
AN-27 执行，AN-26 Reviewer-DeepSeek 独立审查，Mika 负责审查后的 main 整合。
已合并 [PR #2](https://github.com/zhanggzzy/wattline/pull/2)，最终 head 为
`47393f8f9ec8dcea7fc3bb336386966dae5548f4`，main 合并提交为
[`fc669498dce7666e8a3c23c594e4b4ee845d24c4`](https://github.com/zhanggzzy/wattline/commit/fc669498dce7666e8a3c23c594e4b4ee845d24c4)。

前端统一总览、机器及 GPU 详情的布局、排版和状态呈现；增加窄容器机器卡片、
加载/错误/空状态、图表文字摘要与键盘读数播报。沿用原 API、采样和归属判定、
设置、排序、历史及原生对话框。第一轮返工修复列表行在重建后被同机器侧栏按钮
抢走焦点，以及 731–约760px 指标数字 `2,468` 被裁切的问题。
设计映射和当时执行者自测见 [原设计报告](../frontend-redesign.md)，
其“等待独立复审”措辞反映写作时点，最终复审与合并事实见下文。

历史 diff（初始基准 `c7d849f2c2ae104971a7ea9c2624f794b0363ea9` 至上述合并提交）
涉及 8 个文件：`.gitignore`、README、前端设计文档、`pyproject.toml`、浏览器脚本
及 3 个静态前端文件。只新增可选 `browser-test` 开发依赖，无产品运行时依赖、
配置格式、API、数据库或归档格式变化；无数据迁移。这个历史 diff 不属于 AN-33
的新产品改动。

## 真实事件时间线

下表均为 **2026-11-18 UTC**；北京时间为 UTC+8。提交时间取 Git/GitHub，
审查和交接时间取可信任务评论；不将文档整理时间倒填成实施时间。

| UTC | 事件与来源 |
| --- | --- |
| 03:37:31 | AN-25 创建，原始前端需求。 |
| 03:39:44 | AN-26/27 创建，分别承担独立审查与执行。 |
| 03:45:45 | 初始实现提交 `b01b27621195e4b1d5912b9c3970079918d5f4c0`。 |
| 03:46:12 | GitHub PR #2 创建。 |
| 03:46:54 | AN-27 初次交付、自测报告及截图，评论 `01a1ecc3-bfe3-74cf-a48d-dde6cb5383a9`。 |
| 03:59:06 | AN-26 首轮独立审查结论“需修改”，评论 `01a1ecce-ec6c-70db-aa4c-14e91112b491`：P2 焦点抢占、P3 指标裁切。 |
| 04:56:12 | 返工提交 `47393f8f9ec8dcea7fc3bb336386966dae5548f4`。 |
| 04:57:26 | AN-27 第一轮返工交付，评论 `01a1ed04-542b-72a1-9041-d4d4a6b9464a`，仍是执行者自测。 |
| 05:07:12 | AN-26 独立复审通过，评论 `01a1ed0d-45ce-7d1a-a44a-6a6e856b2826`，附非阻塞建议与未覆盖范围。 |
| 05:08:03 | GitHub 确认 PR #2 MERGED，main 合并提交 `fc669498…`。 |
| 05:08:31 | Mika 在 AN-25 评论 `01a1ed0e-7be3-711c-94bb-a8a11bff884e` 汇总 main 交付，保留 in_review 给用户验收。 |

Git 合并提交的 author/committer 时间为 05:08:02，GitHub `mergedAt` 为 05:08:03；
上表合并事件取 API 时间，两者相差一秒，不互相替代。

## 历史验证的归属

以下是对已有报告的核实和转述，不声称本次重新执行了历史操作：

- AN-27 初次自测报告：Python 回归 16 项通过，合成 API 浏览器 smoke 通过，
  页面错误 0；首轮独立审查仍发现上述两项缺陷，因此初次自测不等于通过审查。
- AN-27 返工报告：pytest 16 passed、1 条 Starlette/httpx 弃用警告；
  Chromium 158.0.8127.18 / Playwright 1.65.2 下 19 个宽度、9 组焦点重建断言通过，
  `page_errors=[]`，3 次合成写请求，10 张截图。报告记录新增断言在修复前失败，
  修复后通过；这是当时执行者记录，本次没有回退产品代码重演该对照。
- AN-26 复审报告：在最终 head 独立重跑 16 项回归、语法、browser smoke 和独立 probe，
  核实 390/731/1440px 的行/关注/侧栏共 9 组焦点及 19 个宽度；复核 731/760px
  的 `2,468` 完整显示，补验 390px 空清单和首次连接错误，结论通过。
- 当时官方来源核验使用 Modern Web Guidance v1.0.1，release 时间
  `2026-11-16T14:59:10Z`，tag 指向 `64a6d708f5a43f2cd3fde5d4d7db3905ba1bdf65`。
  本次沿用历史自测和独立复审的核验结果，未重新联网检查该指导。

历史可复现命令为 `.venv/bin/python -m pytest -q`、
`node --check wattline/static/monitor.js`、
`.venv/bin/python tools/browser_smoke.py --browser <Chromium executable>` 和
`git diff --check`；独立 probe 的调用和修复前后输出保留在来源报告附件。

## 已知限制与后续建议

AN-26 复审通过不等于没有限制，原报告明确保留：

1. 976–999px 四列布局下，六位数总功耗 `123,456 W` 可能裁约 4px；
   这超出当轮 `2,468` 的验收范围，未在 AN-33 修复或重新探测。
2. 焦点循环结束停在 1440px，故 smoke 的 `empty.png`/`error.png` 为桌面宽度；
   当时审查者另行补验了 390px。当前脚本仍保留这一截图视口限制。
3. README 当时称原设计文档包含 deployment handoff，但文档已改为审查交接；
   AN-33 本次仅将链接说明对齐为 review handoff，不补造部署步骤。
4. 若轮询后当前行因筛选或状态变化消失，原控件不存在时仍可能丢失焦点。
5. 未覆盖 Safari/Firefox 实机、真实屏幕阅读器听读、触屏拖动、Lighthouse
   或真实节点端到端采集；当时 PR 无已注册 CI checks。

## 来源与本次重验边界

可信来源为 Git/GitHub PR 元数据、版本化原设计文档、AN-25/26/27 的上述评论，
以及通过认证 Multica CLI 下载的三份报告：

| 历史附件 | Attachment ID |
| --- | --- |
| AN-27-report.md | `01a1ecc3-bfd6-7eb5-b1f9-8d3684b6144f` |
| AN-27-rework-report.md | `01a1ed04-5411-7c44-8c39-fd3fc6dd4d6e` |
| AN-26-rereview-report.md | `01a1ed0d-45bb-73c2-aed9-19aa62265247` |

这些平台内附件由具备访问权限的审查者通过 CLI 获取；本文不公开其本机路径或
内部下载地址。内容哈希、取证命令、本次执行的检查及退出码见本次 change 的
`verification.md` 和 AN-33 证据附件。历史图片不是本次截图，本文未把本次自测
写为新的独立复审。AN-33 不修改 AN-25 状态，也不表示用户已验收或实例已更新。
本次没有配置/数据迁移或部署，后续实例更新由用户另行发起的部署会话处理。
