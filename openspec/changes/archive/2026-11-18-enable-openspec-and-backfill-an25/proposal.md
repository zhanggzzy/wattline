# Proposal

## Why

Wattline 尚无版本化的 OpenSpec 流程，AN-25 前端改动已合并但当时未走 OpenSpec。AN-28 授权引入可审查的变更与验证记录，并按真实时间补记历史，避免把事后资料误认为实施前计划。

## What Changes

- 使用官方 CLI 1.14.2 初始化仓库内 OpenSpec，原样复用工作区已授权的六个官方 `openspec-*` skills。
- 版本化仓库 `AGENTS.md` 的开发约定，覆盖源码、测试、配置、依赖、构建脚本及仓库文档；自动注入的 Multica runtime 块仅留本地。
- 新增开发流程规范，规定变更前计划、真实验证、独立审查、同步及归档时点。
- 对 AN-25/26/27 与已合并 PR #2 做明确标注的事后补档，区分历史自测、独立复审及本次重验，保留已知限制。
- 在本 change 记录基准、实际 diff、命令、输出及交接；未完成的独立审查和 main 交付保持待办。

## Capabilities

### New Capabilities

- `development-workflow`: 仓库维护者使用固定官方工具、实施前变更计划、可核验验证和历史来源记录的开发流程。这是本次明确引入的维护行为契约，不是监控产品功能规范。

### Modified Capabilities

无。初始化前 `openspec/specs/` 不存在，CLI inventory 为空。

## Impact

仅影响 `AGENTS.md`、`.agents/skills/openspec-*`、`openspec/`、README 和仓库文档。基准为 PR #2 合并后的 main `fc669498dce7666e8a3c23c594e4b4ee845d24c4`。不改应用、测试代码、配置格式、依赖声明、API、数据库或归档格式；不接触私有配置或部署。AN-25 保持原待验收状态。本阶段不推送；AN-32 独立审查后由 Mika 同步适用规范、归档，再整合提交并核验远端 main。
