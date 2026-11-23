# Proposal

## Why

总览页把「需要关注」和 24 小时趋势放在机器列表右侧，窄屏时排到列表之后，跨机器平均值也掩盖了单机趋势（AN-53、AN-55）。首轮独立审查发现标签渲染、采样连续性和窄屏辨识问题，由 AN-57 整改。

AN-59 将已复审的总览改动整合到包含中英本地化、内存容量和聚焦布局的主干。

## What Changes

- 总览页在机器列表之前依次显示「需要关注」和「最近 24 小时趋势」，两个卡片各占一整行；桌面与窄屏保持同一顺序和既有交互。
- 总览趋势固定最近 24 小时，默认按机器绘制整机 GPU 利用率折线，取消跨机器平均曲线。
- 趋势支持切换 GPU 利用率、CPU 使用率、内存使用率和 GPU 功耗。机器标签按纯文本显示，长标签在窄屏换行。同名用地址区分，同名同地址时附加机器 ID。图例使用与曲线一致的颜色和线型。
- `GET /api/history` 在未指定机器时改为返回按机器对齐的多序列数据，`metric` 限定为上述整机指标。
- 按各机器的采样连续性连接折线。正常的慢频样本连续绘制，实际缺失或序列身份变化时断开，`0` 为有效值。
- 总览及其聚焦视图使用同一逐机历史和中英文文案。聚焦视图保留多图比较、样本表、键盘读数和返回动作。

## Capabilities

### New Capabilities

- `overview`: 总览页的信息顺序、关注项与按机器趋势的可见行为，以及总览历史接口的多机器序列契约。

### Modified Capabilities

<!-- 无。现有 development-workflow 与本变更无关。 -->

## Impact

- 代码：`wattline/history.py`（多机器整机序列）、`wattline/service.py`（总览序列按机器 id 映射）、`wattline/app.py`（总览指标校验）、`wattline/static/monitor.js`、`wattline/static/monitor.css`、`wattline/static/locales.js`。
- 测试与验证：`tests/test_monitor.py`、`tools/browser_smoke.py`、README 中的合成 API 浏览器检查、OpenSpec strict。
- 兼容性：总览历史响应由 `keys`+平均值改为 `machines`+按机器值列，仅影响未指定 `machine` 的调用；这是**BREAKING**的内部 API 变更，工作台前端同步迁移，无外部消费者。机器/单卡历史接口、数据库 schema、采集与归档均不变。
- 不涉及部署、真实节点、真实采集或用户实例数据。
