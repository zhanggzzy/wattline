# AN-168 独立审查报告 · 阶段 1、2 与 11-26 首页卡片修订

结论：**通过（无需返工）**。未发现阻塞合并的缺陷；下列 P3 观察不影响本轮验收，可作为后续改进。

审查方式：Reviewer-DeepSeek 独立会话，只读核验。未修改被审查源码或 OpenSpec，未提交、未推送、未部署。

## 1. 审查对象

- 基准：`bede7a15e1a14cbf36c3d8a8f3a5da467d4f4b64`（工作树 HEAD、`origin/main`、`git ls-remote origin refs/heads/main` 三者一致）。
- 实际工作树：15 个已跟踪文件修改 + 20 个新增文件，共 35 项，与累计补丁文件清单一致；不含两个 `verification.md` 与运行时注入的 `AGENTS.md` 块。
- 累计补丁 `artifacts/an-164-design/2026-11-26-power/implementation.patch`：SHA-256 `1a50263b7d5f93b9e882fb148b084fce4eecad03b381053451ace91d36dacd54`，35 个 `diff --git`。
- 卡片增量 `overview-power.patch`：SHA-256 `e90c80e84cbff6823d2c40f25f7e9550c1c23464b0d7ae01b12faae7a0a76bdc`。
- 两份补丁对实际工作树 `git apply --reverse --check` 均退出 0。
- 暂存区为空；`git show :AGENTS.md` 39 行，不含 `MULTICA-RUNTIME`；工作树 `AGENTS.md` 仅有未暂存的运行时注入块。
- 两个活动 change：`add-compute-resource-registry`、`add-room-cluster-overview`。`tasks.md` 的 2.2（独立审查与整合）保持未勾选，未同步、未归档。

## 2. 独立运行结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 0 | `51 passed, 1 warning in 1.33s`（仅既有 Starlette TestClient 弃用警告） |
| `node --check wattline/static/monitor.js` | 0 | 无输出 |
| `node --check wattline/static/groups.js` | 0 | 无输出 |
| `node tools/test_i18n.cjs` | 0 | PASS，415 个消息键、占位符与本地化检查 |
| `.venv/bin/python -m compileall -q wattline tests tools` | 0 | 无编译错误 |
| `.venv/bin/python tools/resource_browser_smoke.py` | 0 | PASS：三张首页卡、当前/额定功率去重与独立覆盖、存储登记与合成容量、持久告警、机房/集群管理互跳、24 小时趋势与覆盖、键盘页签与排序、过滤、窄屏 |
| `.venv/bin/python tools/browser_smoke.py` | 0 | PASS：Chromium 159.0.8154.6、双语、122 次历史请求、28 张截图、零页面错误；焦点布局 PASS；Windows 七条观测显示五行加两条省略 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-room-cluster-overview --strict` | 0 | Change is valid |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-compute-resource-registry --strict` | 0 | Change is valid |
| `git diff --check` / `git diff --cached --check` | 0 / 0 | 无空白错误 |

附加只读探针：

- 单节点清理：删除机器后 `resource_rooms`、`cluster_resources`、`resource_order`、`shared_users` 中该资源链接被移除；删除存储后四表对应行均为 0，房间/集群成员与排序同步更新。
- 机器过期告警：构造过期样本后 `check_freshness` 生成一条 `stale` 活动事件；新正常样本写入后同一事件转为 `resolved`，`recovered_at` 等于新观测时间。
- 旧库/旧 API：pytest 的 v7/v8 升级、旧多人归属、固定主机身份、历史与冷归档用例通过；浏览器用例对剥除 `storage`/`groups`/`assignment_mode` 的旧快照仍能工作。

## 3. 规范与需求核对

- 首页三卡、告警、三页签顺序与默认机房：符合 `overview` 修改后需求；窄屏无溢出、无第四槽位。
- 机房/集群汇总与机器个体列表、24 小时分组趋势、主机/容器分列、五项覆盖与断线：符合。分组历史使用当前成员、5 分钟桶内最新样本，旧总览与逐机历史契约保持不变。
- 机房/集群互跳、责任人/使用人/共享、删除分组仅解除链接并保留设备与历史、目录引用阻止删除人员：符合。
- CPU/GPU/NAS/共享存储登记与详情、待接入状态、只读适配器与逻辑池去重、成员容量不重复累加：符合。
- 告警持久化、出现/最近/恢复/关闭时间、每资源每规则至多一个活动事件、重启保持、缺数据不视为恢复、停用/移除关闭：符合。
- GPU 功率卡：当前与额定分别覆盖；额定仅用 GPU 级默认功率上限，忽略模块/系统与当前/强制/最大上限；缺数为未知不填 0；同一 UUID 跨主机/容器至多计一次；旧快照/旧采样无额定字段时未知；历史与归档格式未变。符合。
- 内存：已用/总量/占比同显，容器无上限时单列已用，不借用主机上限。符合。
- 固定主机身份、旧 ID/设置保留、单节点清理与冷归档完整性：现有用例通过。

## 4. 非阻塞观察（P3，不要求本轮返工）

1. **设备详情告警仅来自快照前 3 条活动事件。** `wattline/app.py:88` 让 `/api/snapshot` 只取 3 条活动事件，`wattline/static/monitor.js:1950-1952` 的 `deviceAlerts` 再从中按资源过滤。复现：4 台设备各 1 条活动告警时，快照 `total=4`、`events` 仅为 `m3,m2,m1`，`by_resource` 含 `m0:1`，但 `m0` 详情页不会显示告警入口。告警中心与总览总数仍正确。建议后续在设备详情按资源拉取活动事件，或在快照附每资源活动事件。
2. **分组趋势静默只绘前 6 个组。** `wattline/static/groups.js:70` 与 `wattline/app.py:295` 将图表组限制为 6；超过 6 个机房/集群且未过滤时，其余组无提示地不进入图例。汇总表仍列出全部组，可用筛选查看任意组。建议提示“仅显示前 6 组”或提供选择。
3. **GPU 功率覆盖分母在服务端与卡片间口径不同。** `wattline/groups.py:215` 的 `summary.gpu_power.total` 含预期未观测卡数，`groups.py:218` 的额定与 `monitor.js:840-843` 的卡片覆盖使用可见卡数。卡片界面符合规范；但房间/集群汇总表引用 `summary.gpu_power.total`，同一指标在不同视图可能显示不同分母。建议统一或注明口径。
4. **存储删除对话框复用机器文案。** `wattline/static/index.html:132-134` 的标题/说明为“移除节点……包括冷归档”，用于 NAS/共享存储时不准确（存储无冷归档）。仅文案问题。

## 5. 未覆盖范围

- 真实厂商 NAS/共享存储适配器、真实 NVIDIA GPU、真实 Windows 主机与部署实例均未接入；仅合成适配器、合成样本与 Chromium。
- SSH 长连接复用、飞书、数据库换库不在本轮实现/审查范围。
- >3 活动告警的设备详情入口、>6 分组趋势展示为上述已知限制。
- 未执行远端 CI、部署或用户实例验证；本次仅本地只读审查。

## 6. 审查结论

**通过。** 变更满足本轮阶段 1、2 与 11-26 三卡/功率修订的规范与用户要求；实际工作树与累计补丁一致，独立测试、浏览器、strict 与兼容性检查通过。上述 P3 不构成返工条件，交由 Mika 决定整合与后续跟进。
