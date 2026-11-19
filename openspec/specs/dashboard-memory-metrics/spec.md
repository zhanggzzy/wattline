# dashboard-memory-metrics Specification

## Purpose

Defines how Wattline presents machine memory usage in the overview and machine detail views, including the actual used capacity, units, container semantics and missing-data behavior.

## Requirements

### Requirement: Overview shows memory usage and used capacity

机器总览的内存列 SHALL 同时展示使用率和实际已用内存。使用率来自 `memory_percent`，已用量来自样本中的 `memory.used_bytes`，不得仅由展示层推算或伪造。

#### Scenario: Host sample with usage and used bytes
- **WHEN** 一台机器的最新样本包含 `memory_percent` 与 `memory.used_bytes`
- **THEN** 总览内存列显示百分比，并在同一单元格显示以 GiB 表示、保留一位小数的实际已用量

#### Scenario: Container without a memory limit
- **WHEN** 容器样本的 `memory.total_bytes` 为 null 且存在 `memory.used_bytes`
- **THEN** 总览内存列以已用 GiB 作为主读数，并保留既有“使用量含缓存”的语义，不重复显示同一数值

### Requirement: Detail card shows percentage and actual used amount

机器详情的内存指标卡 SHALL 以使用率作为主读数，并同时显示实际已用量与总量。宿主显示“已用 / 总量 GiB”；容器显示含缓存的已用量口径；无上限容器以已用量作为主读数。

#### Scenario: Host detail with total and used bytes
- **WHEN** 宿主样本包含 `memory.total_bytes` 与 `memory.used_bytes`
- **THEN** 内存卡主读数为使用率百分比，辅助文本显示实际已用 GiB 与总量 GiB，并标注“已用”

### Requirement: Missing memory data is not fabricated

当最新样本缺失、机器离线或过期、`memory` 为空或 `memory.used_bytes` 缺失时，界面 SHALL 显示既有占位符（如 `—` 或无当前读数文案），不得把缺失值显示为 0 或 0 GiB。

#### Scenario: Offline machine
- **WHEN** 机器没有有效样本
- **THEN** 总览内存列与详情内存卡使用占位符或既有离线/无读数文案，不显示虚构的已用量

#### Scenario: Used bytes missing from a malformed sample
- **WHEN** 样本存在百分比但没有 `memory.used_bytes`
- **THEN** 已用量位置显示占位符，百分比仍按现有规则展示或保留占位符

### Requirement: Consistent memory units and responsive presentation

已用内存 SHALL 使用项目既有的二进制容量单位 `GiB` 和本地化数字格式，容量换算采用 1024 的幂。新增的并列文本 SHALL 在现有窄屏卡片布局中可读且不造成横向溢出。

#### Scenario: Narrow viewport
- **WHEN** 操作者在窄屏查看总览或详情
- **THEN** 内存使用率与已用容量均可读取，页面不出现横向滚动

#### Scenario: Locale switch
- **WHEN** 操作者切换中文与英文
- **THEN** 内存标签、已用/总量文案和数字格式使用当前语言
