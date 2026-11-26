# overview Specification

## Purpose

定义 Wattline 总览页把关注项与最近 24 小时趋势前置到机器列表之前，并按机器分别呈现整机历史指标的可见行为；同时约束总览历史接口的多机器序列契约。机器与单卡详情趋势仍由原有行为负责。

## Requirements

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

### Requirement: Overview history returns per-machine series

`GET /api/history` 在未指定机器时 SHALL 返回按机器对齐的整机历史序列，默认指标为 GPU 利用率，并 SHALL 仅接受 GPU 利用率、CPU 使用率、内存使用率、GPU 功耗以及不超过 24 小时的窗口。响应 SHALL 标识每列对应的机器，以空值表示无有效读数，并提供逐机器连续性标记。指定机器的历史与单卡历史 SHALL 保持原响应契约。

#### Scenario: Default overview request
- **WHEN** 客户端请求 `/api/history?hours=24`
- **THEN** 响应包含按机器标识的 GPU 利用率序列、对齐的时间点和每台机器的空值或数值

#### Scenario: Aligned slots and real discontinuities
- **WHEN** 对齐时间点包含某台机器的空桶或采样断点
- **THEN** 对齐空桶返回空值且连续性标记为假，实际采样缺失或序列断点由该机器的连续性标记表示

#### Scenario: Window limits
- **WHEN** 历史样本位于请求窗口边界及其两侧
- **THEN** 两个边界内含于返回窗口，窗口之外的样本不参与绘制

#### Scenario: Unsupported overview metric
- **WHEN** 客户端请求总览不支持的指标或超过 24 小时的窗口
- **THEN** 服务以 422 拒绝，不返回聚合或越界数据

#### Scenario: Machine detail contract preserved
- **WHEN** 客户端携带机器与指标请求历史
- **THEN** 响应仍按原有单机器序列返回，单卡请求仍需指定机器和 GPU

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

### Requirement: Global configuration from the overview

The overview SHALL expose a localized Global configuration entry. Operators SHALL see the global override state and effective Linux GPU tolerance with its source, and be able to save a numeric override or clear it.

#### Scenario: Revert a global override
- **WHEN** an operator clears the global setting
- **THEN** the effective global value becomes 256 MiB from the built-in default and is reflected in subsequent samples that inherit it

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
