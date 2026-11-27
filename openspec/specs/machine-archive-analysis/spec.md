# machine-archive-analysis Specification

## Purpose

让用户从机器详情查看本地指标库和冷归档中的完整整机资源趋势，按归档时区选择日期，在保留现有近期监控行为的同时支持跨日追查历史变化。

## Requirements

### Requirement: Machine-only archive entry

整机详情 SHALL 提供打开该机器历史归档分析的按钮。总览、分组、存储、单卡详情和近期图表聚焦页 SHALL 保持各自的入口和近期数据行为。

#### Scenario: Open and return from archive analysis
- **WHEN** 用户从整机详情点击历史归档分析
- **THEN** 工作台打开该机的独立分析视图，返回后仍可使用原来的近期趋势

### Requirement: Progress reflects archive work

服务端 SHALL 在临时空间准备所选机器或来源的本地指标库样本和已发布 gzip 冷归档样本。解压时工作台 SHALL 显示由已读压缩数据量驱动的百分比，完成所有验证和暂存后才报告完成。

#### Scenario: One archive contains multiple machines
- **WHEN** 多台机器的已发布 v1 冷归档共同存放，且用户多次打开同一台机器的分析
- **THEN** 正在执行的作业被复用，进度单调增加，绘制的数据只来自所选机器

#### Scenario: History is available in only one store
- **WHEN** 所选机器只有本地指标样本或只有冷归档样本
- **THEN** 分析可用并展示已有样本

#### Scenario: Absent or unreadable archive
- **WHEN** 所选机器的各存储层均无样本，或读取和解压失败
- **THEN** 工作台分别显示无历史和可重试的失败状态，失败时不展示部分结果

### Requirement: Archive charts use inclusive calendar dates

分析页 SHALL 默认选择所选机器或来源的历史样本首末日。用户调整起止日期后，图表 SHALL 按归档时区绘制区间内的所有存储层指标。起止日 SHALL 均包含在内，图表 SHALL 保留缺失与中断的语义。

#### Scenario: Adjacent dates in the archive timezone
- **WHEN** 有记录位于所选起始日零点、结束日的最后一刻和次日零点
- **THEN** 前两份记录纳入范围，次日零点排除

#### Scenario: Date filter spans maintenance tiers
- **WHEN** 同一筛选范围覆盖冷归档、压实层和原始层
- **THEN** 图表包含三个存储层的匹配样本，同一来源同一时间只计一条，归档维护移动样本后仍呈现相同的覆盖和中断

#### Scenario: No samples in range
- **WHEN** 所选日期范围没有样本
- **THEN** 图表显示该范围无数据，用户可继续调整日期或指标

### Requirement: Temporary analysis data is reclaimed

归档分析 SHALL 使用短期临时数据，并在失败、过期、机器被移除或服务退出时释放。读取分析数据 SHALL 保持原始归档完整。

#### Scenario: Cleanup overlaps active work
- **WHEN** 正在解压或读取图表期间存在回收或归档维护操作
- **THEN** 活动作业的资源保持可用，归档发布和机器移除持续遵循既有的归档一致性要求

### Requirement: Archive analysis follows machine identity

Archive analysis SHALL resolve registered sources to the same machine as recent trends. Across all storage tiers the machine view SHALL use the same source eligibility and CPU and memory selection rules as recent trends. Existing gzip format and per-source analysis SHALL remain readable.

#### Scenario: Archive contains overlapping linked sources
- **WHEN** the combined history includes the same machine's sources, earlier unverified boots and an unrelated endpoint
- **THEN** the machine analysis selects readings from its canonical source and secondary samples from the verified common boot. Each metric shows at most one value per bucket. The source selector can still display earlier records under their original history key.
