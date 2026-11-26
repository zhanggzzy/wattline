# Tasks

## 1. Archive analysis API

- [x] 1.1 实现机器范围的 gzip 读取、真实进度、临时存储、日期筛选和作业生命周期，以合成归档测试机器隔离、时间边界、失败重试、并发和清理。

## 2. Machine detail

- [x] 2.1 实现机器详情入口、百分比进度、日期筛选和状态反馈，复用图表交互及双语文案，使用合成 API 浏览器场景验证，并补充使用说明。

## 3. Verification and handoff

- [x] 3.1 执行仓库 pytest、JS、浏览器、OpenSpec strict 和 diff 检查，将基准、实测结果和范围写入 [verification.md](verification.md)。
- [x] 3.2 AN-221 独立核对实际提交、规范及可复现验证证据，见 [验证记录](verification.md#独立审查)。
- [ ] 3.3 Mika 在审查通过后整合并核验远端 main。

## Workflow follow-up

- 审查和必要验证通过后同步规范 delta 并归档 change。
