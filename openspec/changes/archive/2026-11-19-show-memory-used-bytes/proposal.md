# Proposal

## Why

Wattline 的机器总览只在内存列显示使用率，操作者需要同时知道实际已用容量才能判断是否需要处理。后端样本与历史已包含 `memory.used_bytes`，但总览界面没有显示该事实；仅凭百分比无法区分 38% 对应 48 GiB 还是 4 GiB。

## What Changes

- 机器总览的内存列在保留使用率的同时显示实际已用内存，使用现有 `GiB` 约定和一位小数。
- 机器详情的内存指标卡继续以使用率为主要读数，并把实际已用量与总量显示为明确的可读文本（宿主为 `已用 / 总量`，容器无上限时显示已用量并保留含缓存说明）。
- 无上限容器仍以已用 GiB 作为主读数，不重复显示同一数值；缺失 `used_bytes`、过期/离线或无样本时显示占位符，不把缺失值渲染为 0。
- 窄屏卡片布局保留表头和数值的可读性，新增文本不造成横向溢出。
- 中英文资源同步新增/复用文案，沿用既有本地化与数字格式约定。

## Capabilities

### New Capabilities
- `dashboard-memory-metrics`: 机器总览与详情中的内存使用率、实际已用容量、单位、缺失数据与容器口径的展示契约。

### Modified Capabilities
None.

## Impact

仅静态前端 `wattline/static/monitor.js`、`locales.js`、可能的 `monitor.css`，合成浏览器检查 `tools/browser_smoke.py`，以及本 change 的规范与证据。无后端 schema、业务 HTTP API、依赖或部署变更；现有快照中的 `memory.used_bytes` 已是服务端公开字段。
