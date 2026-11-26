# Spec Delta

## MODIFIED Requirements

### Requirement: Overview trend metric switching

Group charts SHALL provide weighted CPU use, memory used, memory percent, GPU utilization, GPU power and storage percent. They SHALL include true zero, missing gaps and metric-specific coverage.

#### Scenario: 24-hour aggregate trend
- **WHEN** a group is charted
- **THEN** five-minute buckets use the latest applicable observation per verified machine and current membership. The machine view selects CPU and memory independently, preferring valid host readings and falling back to valid container readings. It deduplicates visible GPU readings. The API also retains scope-specific group queries.

#### Scenario: Machine detail trend is unchanged
- **WHEN** an operator opens a compute machine detail
- **THEN** its existing trend API, windows and GPU behavior remain available.

#### Scenario: Machine detail plots available CPU and memory readings
- **WHEN** an operator charts CPU or memory and an associated container provided the only valid reading for that metric
- **THEN** the machine view plots that reading, and an explicit source or scope query still returns its original series.

#### Scenario: Switch to CPU usage
- **WHEN** 用户从另一项分组指标切换到 CPU 使用率
- **THEN** CPU 按钮呈选中状态，图例和提示使用百分比单位，数据按 CPU 使用率绘制

#### Scenario: Switch to GPU power
- **WHEN** 用户切换到 GPU 功耗
- **THEN** 图例、坐标轴和提示按瓦特展示功耗，且不再显示百分比单位

#### Scenario: Zero utilization is valid
- **WHEN** 某台机器的整机 GPU 利用率为 `0`
- **THEN** 该样本作为有效值参与折线，不被当作缺失

#### Scenario: Missing samples break the line
- **WHEN** 某个分组在时间桶内缺少该指标的有效输入
- **THEN** 该分组的折线在缺失区间断开，其他分组的折线继续显示

#### Scenario: Different normal sampling intervals
- **WHEN** 旧版逐机总览历史查询包含不同采样间隔的机器
- **THEN** 保持既有历史时效与断线语义

### Requirement: Focused overview uses localized per-machine trends

The focused group history SHALL support comparing group metrics with localized controls and an accessible sample table.

#### Scenario: Focus, compare and return
- **WHEN** an operator focuses the selected group chart and selects metrics
- **THEN** at least one metric remains selected, data and coverage remain readable, and exit returns focus to the entry point.

#### Scenario: Focus and compare overview metrics
- **WHEN** 用户从总览所选指标进入聚焦视图并选择另一个指标
- **THEN** 两张图各自显示所选指标的 24 小时分组序列和对应单位，机器视图的样本表按分组标识数据列，返回后恢复总览的指标选择

#### Scenario: Switch overview language
- **WHEN** 用户切换总览语言并查看趋势、样本表或键盘读数
- **THEN** 图表文案及数字日期格式使用所选语言，分组标签按原字面显示

### Requirement: One monitoring unit per machine

The overview SHALL count and list each verified machine once, and all machine-based trends SHALL resolve the same current machine membership. Current machine views SHALL select CPU and memory independently from fresh observations. Each metric SHALL prefer the host, then the most recent valid container reading, with stable ordering for ties. Capacity and usage for a metric SHALL come from the same observation.

#### Scenario: A host and its containers expose overlapping devices
- **WHEN** multiple sources on the same machine report overlapping GPU UUIDs and resource values
- **THEN** the online count and machine list include the machine once, and each visible GPU contributes at most once to summary values and coverage

#### Scenario: Only containers can be observed
- **WHEN** the machine has no fresh host readings and one or more containers report their own CPU and memory
- **THEN** the machine counts once, each available reading contributes once to the machine summary and coverage, and the machine details identify the container sources

#### Scenario: Linked source has prior history
- **WHEN** recent history is requested for a grouped machine
- **THEN** one series is returned per machine or selected GPU, secondary data is attributed only for the verified boot, and older per-source history remains readable from the machine details

#### Scenario: Metrics have different valid sources
- **WHEN** a host reports valid CPU but unavailable memory and an associated container reports both
- **THEN** the machine uses the host CPU with its own weight and the container memory with its own capacity and used bytes. A reported zero remains valid.

#### Scenario: Labels follow the current locale
- **WHEN** an operator opens the room or cluster table or its detail page in Chinese or English
- **THEN** the statistics are headed CPU and 内存 / Memory. The machine-view group chart identifies the group without a host or container suffix.

#### Scenario: No valid source
- **WHEN** no source has a valid observation for a metric
- **THEN** the metric is missing in the machine view and contributes no valid coverage to the group.
