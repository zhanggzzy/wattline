# AN-217 问题定位

基线为 `0123c748d9c628902105738a7e5a080aaf3e92d4`（`origin/main`）。2026-11-26 在 macOS arm64、Python 3.11.17 的任务虚拟环境中，用合成探针响应和临时 SQLite 复现。

## 复现

在基线上只加入回归测试，执行 `.venv/bin/python -m pytest -q tests/test_monitor.py -k collection_alerts_are_independent_of_gpu_occupancy`。退出码 1，输出 `3 failed, 37 deselected, 1 warning`。三个用例均在首次有效样本后失败。设备表仍有 `free` 和 `unknown`，但活动告警列表多出一条证据为「部分 GPU 的利用率或实时功耗缺失」的事件。后续触发与恢复步骤尚未运行。

## 根因

- Linux 与 Windows GPU 探针会额外把占用未确认写入 `warnings`。即使有可用指标，`Monitor.observe` 仍会把有警告的快照记为 `warning`。
- `Monitor.compute_alert` 把所有 `warning` 快照当作 `collection`，并且只用 `normal` 样本清除该规则。样本是否成功和 GPU 占用能否判断由此耦合。
- 超时快照写入 `offline` 告警，过期扫描写入 `stale` 告警。两者共用同一告警中心，但都使用区别于「采集异常」的标签。
- Windows 仅采 GPU 时接受任何带 `gpu_inventory_complete` 字段的响应。现有 Windows 采样测试证实，探针失败且无 GPU 指标时也产生带空清单的 `warning` 快照。改按有效样本判断后，这类无读数响应需要与已核实的空清单明确区分。

修复沿用采样超时和每台机器的有效期，用采样结果和证据更新 `collection`。GPU 占用采用原有设备状态值。
