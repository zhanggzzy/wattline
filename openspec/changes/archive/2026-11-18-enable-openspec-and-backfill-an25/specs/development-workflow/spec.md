# Spec Delta

## Purpose

为 Wattline 维护者提供可复核的仓库变更契约，使实施前意图、实际改动、真实验证和独立审查能够关联；同时保留历史补档的真实时间和证据边界，避免以流程状态代替交付事实。

## ADDED Requirements

### Requirement: Official reproducible workflow tooling

仓库 MUST 固定 OpenSpec CLI 版本，并保留获授权的官方 skills 原文及可验证来源；执行者 SHALL 优先使用仓库内 skills，不以自造流程替代官方工具。

#### Scenario: A maintainer starts a change
- **WHEN** 维护者在新环境开始仓库维护
- **THEN** 能从版本化约定确定 CLI 版本、官方 skills 位置和来源，并复现 OpenSpec 检查

### Requirement: Planning precedes implementation

源码、测试、配置、依赖、构建脚本和仓库文档的变更 MUST 在实施前建立或复用 OpenSpec change，并按实际 schema 准备问题、范围、验收、tasks 和适用的设计及规范 delta。只读检查 SHALL 不创建 change。

#### Scenario: A maintainer changes repository documentation
- **WHEN** 维护者准备修改 README 或其他版本化文档
- **THEN** 先读取仓库上下文与现有 change，以 CLI 确认 schema 和所需 artifacts，规划就绪后才实施

#### Scenario: A maintainer performs a read-only review
- **WHEN** 工作仅核验现有代码、提交或证据而不改仓库
- **THEN** 可以引用原 change 审查，无需为只读检查新建 change

### Requirement: Verification and acceptance are distinct

交付记录 MUST 关联 change ID 与基准及实际 diff、commit 或 PR，记录真实命令、结果、范围和限制；自测 SHALL 与独立审查区分。未完成的审查或交付任务 MUST 保持待办，不以平台 done 或 strict 通过代替审查通过。

#### Scenario: Implementation is ready for independent review
- **WHEN** 执行者完成本地实施和适当检查
- **THEN** 交付明确被审对象和可复现证据，独立审查与 main 交付保持未完成，不将用户实例描述为已更新

### Requirement: Retrospective records preserve provenance

历史补档 MUST 标明整理时间、真实事件时间、来源和已知限制，并明确是否当时使用 OpenSpec。历史自测、历史独立审查和本次重验 SHALL 分别归属，不补造实施前计划或未经执行的测试。

#### Scenario: An already merged frontend change is documented
- **WHEN** 补记 AN-25 及 PR #2
- **THEN** 明确这是事后整理，记录 AN-25/26/27、实际提交与审查时间，说明当时未走 OpenSpec，并保留审查报告的未覆盖范围和非阻塞限制

### Requirement: Review gates specification finalization

维护者 MUST 在实施、必要验证和独立审查通过后同步适用的规范并归档 change。未审查或尚有未完成任务时 SHALL 保持活动 change；正式 main 交付由项目指定负责人完成并核验远端 SHA。

#### Scenario: Independent review is still pending
- **WHEN** 执行阶段已经交接而独立审查尚未完成
- **THEN** change 保留在活动目录，规范 delta 保留待同步，不提前标记审查、整合或归档完成
