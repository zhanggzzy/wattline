## MODIFIED Requirements

### Requirement: Overview trend metric switching

Group charts SHALL provide weighted CPU use, memory used, memory percent, GPU utilization, GPU power and storage percent. They SHALL include true zero, missing gaps and metric-specific coverage.

#### Scenario: 24-hour aggregate trend
- **WHEN** a group is charted
- **THEN** five-minute buckets use the latest applicable observation per verified machine and current membership. The machine view uses host CPU and memory and deduplicated visible GPU readings. The API also retains scope-specific group queries.

#### Scenario: Machine detail trend is unchanged
- **WHEN** an operator opens a compute machine detail
- **THEN** its existing trend API, windows and GPU behavior remain available.

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

## ADDED Requirements


### Requirement: One monitoring unit per machine

The overview SHALL count and list each verified machine once, and all machine-based trends SHALL resolve the same current machine membership. A single source observation supplies CPU and memory in machine details, preferring fresh host observations, with the measured scope labeled.

#### Scenario: A host and its containers expose overlapping devices
- **WHEN** multiple sources on the same machine report overlapping GPU UUIDs and resource values
- **THEN** the online count and machine list include the machine once, and each visible GPU contributes at most once to summary values and coverage

#### Scenario: Only containers can be observed
- **WHEN** the machine has no fresh host readings and one or more containers report their own CPU and memory
- **THEN** the machine counts once, the details name the selected container scope, and the group host CPU and memory coverage omit those readings

#### Scenario: Linked source has prior history
- **WHEN** recent history is requested for a grouped machine
- **THEN** one series is returned per machine or selected GPU, secondary data is attributed only for the verified boot, and older per-source history remains readable from the machine details
