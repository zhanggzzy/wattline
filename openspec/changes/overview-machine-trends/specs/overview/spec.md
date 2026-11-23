# Spec Delta

## Purpose

定义 Wattline 总览页把关注项与最近 24 小时趋势前置到机器列表之前，并按机器分别呈现整机历史指标的可见行为；同时约束总览历史接口的多机器序列契约。机器与单卡详情趋势仍由原有行为负责。

## ADDED Requirements

### Requirement: Overview prioritizes attention and recent trend

总览页 SHALL 在机器列表之前依次显示「需要关注」和「最近 24 小时趋势」，两个卡片各自独占一整行。桌面与窄屏 SHALL 保持该顺序，并保留关注项跳转和机器列表筛选、搜索、排序交互。

#### Scenario: Desktop order
- **WHEN** 用户在桌面宽度打开总览页
- **THEN** 页面依次呈现「需要关注」整行、「最近 24 小时趋势」整行，然后才是机器列表

#### Scenario: Narrow viewport order
- **WHEN** 用户在窄屏打开总览页
- **THEN** 两个卡片仍按「需要关注」、趋势、机器列表的顺序各占一行，没有横向溢出

#### Scenario: Attention item still opens its machine
- **WHEN** 用户点击「需要关注」中的机器
- **THEN** 工作台打开该机器详情，原有列表交互不受顺序调整影响

### Requirement: Overview trend draws one line per machine

总览趋势 SHALL 固定最近 24 小时，默认按机器绘制整机 GPU 利用率折线。图例与提示 SHALL 以纯文本标识机器，图例和曲线 SHALL 使用一致且可区分的颜色和线型。长标签 SHALL 在窄屏保持可读。

#### Scenario: Distinct machines produce distinct lines
- **WHEN** 两台合成机器的整机 GPU 利用率明显不同
- **THEN** 趋势图按机器分别绘制两条折线，图例各标出对应机器

#### Scenario: Same display name is disambiguated
- **WHEN** 两台参与绘图的有效机器显示名称相同
- **THEN** 两者的图例标识包含各自地址，可互相区分

#### Scenario: Display name and address both match
- **WHEN** 多台机器具有相同的显示名称和地址
- **THEN** 图例和提示还显示各自的机器 ID

#### Scenario: Long literal label on a narrow screen
- **WHEN** 在窄屏查看包含类似标记字符的长机器名称
- **THEN** 图例和提示按原字面显示名称，并在可用宽度内换行

#### Scenario: More machines than palette colours
- **WHEN** 同一图中的机器数量多于可用颜色
- **THEN** 同色曲线以线型区分，图例使用对应的颜色和线型

#### Scenario: No cross-machine average
- **WHEN** 总览趋势完成加载
- **THEN** 图中不存在跨机器平均序列，只有逐机器的整机指标序列

### Requirement: Overview trend metric switching

总览趋势 SHALL 支持切换 GPU 利用率、CPU 使用率、内存使用率和 GPU 功耗。切换后 SHALL 显示所选按钮的选中状态，百分比指标固定 0–100 轴，功耗按瓦特取值。`0` SHALL 视为有效样本，折线 SHALL 按各机器的采样连续性连接。

#### Scenario: Switch to CPU usage
- **WHEN** 用户从默认 GPU 利用率切换到 CPU 使用率
- **THEN** CPU 按钮呈选中状态，图例和提示使用百分比单位，数据按 CPU 使用率绘制

#### Scenario: Switch to GPU power
- **WHEN** 用户切换到 GPU 功耗
- **THEN** 图例、坐标轴和提示按瓦特展示功耗，且不再显示百分比单位

#### Scenario: Zero utilization is valid
- **WHEN** 某台机器的整机 GPU 利用率为 `0`
- **THEN** 该样本作为有效值参与折线，不被当作缺失

#### Scenario: Missing samples break the line
- **WHEN** 某台机器缺少指标值，或采样间隔超过该机器在历史采样时的时效阈值
- **THEN** 该机器的折线在缺失区间断开，其他机器的折线继续显示

#### Scenario: Different normal sampling intervals
- **WHEN** 两台机器正常采样，慢频机器的有效样本之间跨过共享时间桶
- **THEN** 慢频机器的有效样本仍保持连续

#### Scenario: Machine detail trend is unchanged
- **WHEN** 用户进入机器或单卡详情查看趋势
- **THEN** 原有指标集合、时间窗选择和单卡趋势行为保持不变

### Requirement: Focused overview uses localized per-machine trends

总览及其聚焦视图 SHALL 使用当前语言显示控件、状态、辅助技术文案和数字日期格式。聚焦总览 SHALL 支持同时比较任意非空的总览指标组合，每张图均使用固定的 24 小时逐机历史，样本表和键盘读数 SHALL 保留机器的原始标识。

#### Scenario: Focus and compare overview metrics
- **WHEN** 用户从总览所选指标进入聚焦视图并选择另一个指标
- **THEN** 两张图各自显示所选指标的 24 小时逐机序列和对应单位，样本表按机器标识数据列，返回后恢复总览的指标选择

#### Scenario: Switch overview language
- **WHEN** 用户切换总览语言并查看趋势、样本表或键盘读数
- **THEN** 图表文案及数字日期格式使用所选语言，机器标签按原字面显示

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
