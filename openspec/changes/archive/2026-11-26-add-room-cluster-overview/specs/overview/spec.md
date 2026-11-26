## MODIFIED Requirements

### Requirement: Overview prioritizes attention and recent trend

The overview SHALL show only the Online devices, Visible GPUs and GPU power summary cards, followed by the persisted alert section above Room, Cluster and Machine tabs, with Room selected by default.

#### Scenario: Desktop order
- **WHEN** the overview opens
- **THEN** three summary cards share a row. Alerts, tabs, and the selected group chart and list follow in that order.

#### Scenario: Narrow viewport order
- **WHEN** the overview is viewed at a narrow width
- **THEN** the three cards reflow without horizontal overflow or a fourth slot. Alerts and tabs remain reachable in the same order.

#### Scenario: Attention item still opens its machine
- **WHEN** an active event still has a registered device
- **THEN** the operator can reach its detail from the alert.

### Requirement: Overview trend draws one line per machine

The existing per-machine overview history API SHALL continue to return separate machine series. The user-facing overview SHALL draw separate group series on Room and Cluster tabs, and SHALL show individual device rows without a chart on the Machine tab.

#### Scenario: Duplicate and long labels
- **WHEN** group names require disambiguation or are long
- **THEN** series remain identifiable and the legend can wrap.

#### Scenario: Group and device lists
- **WHEN** an operator switches tabs with pointer or keyboard
- **THEN** the matching list appears, group trends are scoped to that tab, and device ordering and focus are preserved.

#### Scenario: Distinct machines produce distinct lines
- **WHEN** 两台合成机器的整机 GPU 利用率明显不同
- **THEN** 旧版总览历史接口仍返回机器各自的序列

#### Scenario: Same display name is disambiguated
- **WHEN** 旧版逐机总览读取到相同显示名的两台机器
- **THEN** 两者的图例标识包含各自地址，可互相区分

#### Scenario: Display name and address both match
- **WHEN** 旧版逐机总览读取到显示名与地址均相同的机器
- **THEN** 图例和提示还显示各自的机器 ID

#### Scenario: Long literal label on a narrow screen
- **WHEN** 在窄屏查看包含类似标记字符的长分组名称
- **THEN** 图例和提示按原字面显示名称，并在可用宽度内换行

#### Scenario: More machines than palette colours
- **WHEN** 同一图中的分组与观测范围序列数多于可用颜色
- **THEN** 同色曲线以线型区分，图例使用对应的颜色和线型

#### Scenario: No cross-machine average
- **WHEN** 旧版总览历史接口返回数据
- **THEN** 返回逐机器序列且不含跨机器平均序列

### Requirement: Overview trend metric switching

Group charts SHALL provide weighted CPU use, memory used, memory percent, GPU utilization, GPU power and storage percent. They SHALL include true zero, missing gaps and metric-specific coverage.

#### Scenario: 24-hour aggregate trend
- **WHEN** a group is charted
- **THEN** five-minute buckets use the latest applicable observation per device, current membership and separate host/container scopes.

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

### Requirement: Focused overview uses localized per-machine trends

The focused group history SHALL support comparing group metrics with localized controls and an accessible sample table.

#### Scenario: Focus, compare and return
- **WHEN** an operator focuses the selected group chart and selects metrics
- **THEN** at least one metric remains selected, data and coverage remain readable, and exit returns focus to the entry point.

#### Scenario: Focus and compare overview metrics
- **WHEN** 用户从总览所选指标进入聚焦视图并选择另一个指标
- **THEN** 两张图各自显示所选指标的 24 小时分组序列和对应单位，样本表按分组与范围标识数据列，返回后恢复总览的指标选择

#### Scenario: Switch overview language
- **WHEN** 用户切换总览语言并查看趋势、样本表或键盘读数
- **THEN** 图表文案及数字日期格式使用所选语言，分组标签按原字面显示

## ADDED Requirements

### Requirement: Group trend history is additive

Group history SHALL use a new API. The existing overview and machine history API contracts SHALL continue to support previous clients.

#### Scenario: Partial observations with duplicated devices
- **WHEN** members have stale, missing or overlapping observations
- **THEN** unavailable values are excluded, coverage is explicit, and GPU UUIDs and logical storage identities are deduplicated within each scope where applicable.

### Requirement: Current and rated GPU power on the overview

The GPU power card SHALL show current draw and rated power with independent coverage against unique GPU UUIDs from fresh visible observations. Rated power SHALL use only the verified GPU default power limit. A total with no qualifying values SHALL show unknown. The UI SHALL state the rated power basis.

#### Scenario: Default limit differs from operational limits
- **WHEN** a GPU reports a default power limit and different current, enforced, maximum, module or base limits
- **THEN** the rated total uses the GPU default value and the current total uses measured GPU draw.

#### Scenario: Independent coverage with overlapping visibility
- **WHEN** an identical physical GPU appears in two observations and other cards have readings for only one of the totals
- **THEN** the physical GPU contributes at most once to each total, and each coverage label reflects its own measurements.

#### Scenario: Unsupported device or old snapshot
- **WHEN** a device has no valid default power limit or the snapshot predates the field
- **THEN** its rated power contribution is unknown and no limit or zero is substituted. History and archives use the existing format.

#### Scenario: Storage detail remains available
- **WHEN** an operator looks up a registered storage resource
- **THEN** storage remains accessible in device rows, detail and group summaries.
