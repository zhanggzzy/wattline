# Tasks

## 1. Official workflow integration

- [x] 1.1 固定 1.14.2 CLI 和 schema、原样复用六个官方 skills 并记录来源；以 CLI version/context、逐文件 SHA-256 与 byte comparison 验证。
- [x] 1.2 在 AGENTS.md 块外及 README 写开发范围、计划/验证/审查/归档约定；核验 Git index 只含通用正文且 runtime 块哈希不变。

## 2. Historical provenance

- [x] 2.1 写 AN-25 前端事后补档，关联 AN-25/26/27 和已合并 PR #2；以可信评论、报告及 Git/GitHub 时间与 SHA 逐项核对，区分历史自测、独立复审和本次重验并保留限制。

## 3. Integration verification and execution handoff

- [x] 3.1 执行 strict、已有 pytest、JS 语法、合成浏览器检查与 diff 范围检查；保存实际命令、输出、退出码和本次覆盖限制。
- [x] 3.2 写执行报告并交付完整暂存 diff 和证据附件；核对基准/前后状态及改动路径，确认没有产品文件和私有资料入库，没有提交推送。

## 4. Independent review and specification finalization

- [x] 4.1 AN-32 Reviewer-DeepSeek 独立读取 change 与实际 diff，执行必要检查并记录真实结论；如需修改，返工并复审后才可勾选。2026-11-18 审查通过，无必须修改项，来源及对象见 closeout.md。
- [x] 4.2 Mika 委派 Executor-Codex（AN-36）在独立审查通过后使用官方 sync skill 将 development-workflow delta 同步到主规范，并以 strict 检查及实际规范 diff 核验。2026-11-18 同步及两项 strict 通过，主规范保留原 Purpose 和全部五条要求，见 closeout.md。

## Workflow follow-up

- 2026-11-18，由 Mika 委派 Executor-Codex（AN-36）在上述任务完成后使用官方 archive skill 归档，并复验主规范与归档结果；本轮收尾记录入口为 closeout.md。原 verification.md 保留 AN-33 交接时点的事实与待办表述。
- Mika 按项目授权提交、推送并核验远端 main SHA，在 AN-28 汇总交付并保留 in_review 供用户验收。
- AN-25 仍待原用户验收，不重开、不改状态；代码更新不代表实例已更新。
