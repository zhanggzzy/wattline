# Design

## Context

动机和范围见 proposal.md。干净工作树最初在已合并的 AN-27 分支 `47393f8`；已安全切换 main 并快进到 `fc669498dce7666e8a3c23c594e4b4ee845d24c4`。此前没有 OpenSpec 根，已获明确授权执行官方 1.14.2 初始化。现有 README、前端设计文档和 Multica 历史报告可供核实。

## Goals / Non-Goals

**Goals:** 形成跨会话可复核的维护约定与历史来源链；将通用版本化说明和本机 runtime 注入信息分开；在不改变官方 skills 原文的前提下固定使用方式。

**Non-Goals:** 本次不重新设计前端、不修复历史非阻塞建议、不做实例验证，不建立监控产品功能的事后假规范。

## Decisions

1. 使用本地 `openspec/` 与默认 `spec-driven` schema。CLI `init --tools none` 只完成官方初始化；六个已授权 1.14.2 skills 逐字节复制到 `.agents/skills/`，记录 SHA-256，不另写替代 skill。相较让 CLI 生成默认工具子集，这能保持工作区已批准的六个技能原文和范围。CLI 调用固定为 `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2`；缺少缓存时明确报错，不静默升级。
2. `development-workflow` 只规范维护者和下游审查者依赖的开发行为。它承载本次用户明确引入的开发契约，不把历史前端功能包装成当时已规划的产品规范。AN-25 历史另存 `docs/history/an25-frontend-retrospective.md`，原设计报告保持原样。
3. `AGENTS.md` 自动注入块保持字节不变，在块外添加通用项目约定。因该路径原被 `.git/info/exclude` 忽略，只将块外正文作为 Git index 的新文件；工作树中的 runtime 块仍只在本地。采用 `git hash-object -w --stdin` 与 `git update-index --add --cacheinfo` 写入正文索引，审查使用 `git diff --cached`。避免直接 force-add 整份文件带入本机资料；交接必须说明该文件预期为 AM，Mika 不得用 `git add AGENTS.md` 或 `git add -A` 覆盖干净索引。
4. 计划 artifacts 在实施前写入、strict 校验并保存只读内容哈希及 CLI apply 初始输出；不为记录顺序修改历史提交。配置、README、历史及验证文档在 apply 后实施。独立审查及 main 交付由后续阶段记录，因此本阶段不勾选、不同步、不归档。
5. 本次只运行已有离线回归、JS 语法和合成 API 浏览器检查，另检查 skills 原样性、流程文件范围及 strict。无需新增镜像实现的测试；历史原始报告通过认证 CLI 下载，保留在忽略的 artifacts 中，不将含机器路径的原件公开入库。

## Risks / Trade-offs

- 官方 propose skill 默认在提案后等待新指令 → 本任务明确授权初始化、提案、实施、验证和交付，因此连续推进；不更改官方 skill 文本。
- `AGENTS.md` 的本地 runtime 与待提交正文不同 → 在报告提供正文 blob、暂存 diff 和排除规则，验证注入块哈希未改变；保留原 runtime，不使用跳过工作树检查的隐藏标志。
- 历史报告和 PR 正文停留在当时状态 → 用事件时间表区分初始、自测、复审与合并，不把旧“等待复审”当作最终结论。
- strict 能检查 artifact 格式，不能证明执行顺序或语义正确 → 留真实命令和结果，并由 AN-32 独立核对 actual diff；未审查时 change 继续活动。

## Migration Plan

无产品、配置或数据迁移。本阶段不提交推送；保留完整可审查改动。AN-32 审查通过后，Mika 补真实审查记录、核验必要检查，用官方 sync/archive skills 同步规范并归档，再按项目授权提交并推送 main、核验远端 SHA。若审查需修改则继续当前 change，不能提前归档。撤销本流程需另立变更，不能回写历史前端提交。
