## MODIFIED Requirements

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

### Requirement: Archive analysis follows machine identity

Archive analysis SHALL resolve registered sources to the same machine as recent trends. Across all storage tiers the machine view SHALL use the same source eligibility and CPU and memory selection rules as recent trends. Existing gzip format and per-source analysis SHALL remain readable.

#### Scenario: Archive contains overlapping linked sources
- **WHEN** the combined history includes the same machine's sources, earlier unverified boots and an unrelated endpoint
- **THEN** the machine analysis selects readings from its canonical source and secondary samples from the verified common boot. Each metric shows at most one value per bucket. The source selector can still display earlier records under their original history key.
