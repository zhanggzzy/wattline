## MODIFIED Requirements

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
- **WHEN** 机房、集群或旧版逐机总览同时显示超过八条序列
- **THEN** 各序列使用颜色不同的实线与对应图例，轮询、序列重排及切换指标时保留同一序列的颜色

#### Scenario: No cross-machine average
- **WHEN** 旧版总览历史接口返回数据
- **THEN** 返回逐机器序列且不含跨机器平均序列
