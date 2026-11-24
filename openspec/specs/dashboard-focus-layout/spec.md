# dashboard-focus-layout Specification

## Purpose

Allow operators to recover dashboard space for resource comparisons and inspect hardware workloads while retaining machine identity, CPU information and trustworthy missing-data semantics.

## Requirements

### Requirement: Reversible compact navigation

The dashboard SHALL provide an expanded rail and a narrow machine-identity rail. Both modes SHALL retain named keyboard-operable machine selection, selected-machine indication, an independent status indicator with accessible text, and an operable expand control on desktop and narrow screens. The narrow rail SHALL show a machine-model silhouette derived from reliable observed model information, or a generic host silhouette when no reliable model is available.

#### Scenario: Compact rail selection
- **WHEN** the operator collapses navigation and selects a machine using the keyboard
- **THEN** its machine-model or generic silhouette and independent status indicator are visually shown, its instance name, status and available full model remain accessible, selection is indicated, and expansion restores names

#### Scenario: Expanded rail identity
- **WHEN** the operator expands navigation
- **THEN** each machine still shows its instance name and status, the same model or generic silhouette remains visible, and navigation, selection and keyboard behavior are unchanged

### Requirement: Focused trend comparison
Resource trends SHALL occupy a full row on machine pages. Operators SHALL be able to focus one or any nonempty subset of supported metrics in a full-page view, stacked vertically, with retained time selection, responsive plots and an explicit keyboard-operable return action.

#### Scenario: Power and utilization comparison
- **WHEN** the operator chooses a 24-hour window and GPU power plus GPU utilization in page focus mode
- **THEN** both labeled plots appear above one another with the same time window and independent units and readings

#### Scenario: Return and resize
- **WHEN** the operator resizes the focused page then returns using the return action or Escape
- **THEN** plots adapt to their containers and machine context and normal layout are restored with focus on the entry control

### Requirement: Integrated hardware and process inspection
The machine page SHALL combine GPU hardware status, utilization, memory, power and temperature with current process PID, account, ownership evidence and process memory in one table. CPU/memory and system facts SHALL remain available. GPU actions SHALL open a named dismissible detail dialog with raw evidence and keyboard focus restoration.

#### Scenario: Multiple GPUs and missing readings
- **WHEN** several GPUs include occupied, idle, partially visible or offline devices
- **THEN** each device remains individually inspectable and the table distinguishes no processes, unverifiable visibility and unavailable measurements without fabricating zeros

#### Scenario: Narrow screen inspection
- **WHEN** an operator opens a GPU on a narrow screen and dismisses its details with Escape
- **THEN** hardware and process information remain readable without document overflow and focus returns to that GPU action

### Requirement: Machine silhouette follows reliable model information

收起侧栏的机器轮廓 SHALL 依据已采集到的 GPU 产品名映射。B300 使用厚重机柜轮廓，RTX PRO 6000 使用双槽卡轮廓，GB10 或 DGX Spark 使用紧凑方盒轮廓，RTX 5090 使用双风扇卡轮廓。清单须有完整性证据、设备名齐全且符合配置的期望数量。机型信息缺失、未知、有歧义或不完整时，SHALL 使用通用主机轮廓，并在提示中保留可用的完整设备名。

#### Scenario: Known models map to distinct silhouettes
- **WHEN** 一台机器的所有已采集 GPU 产品名都识别为 B300、RTX PRO 6000、GB10/DGX Spark 或 RTX 5090 中的同一类
- **THEN** 该机器使用对应机型轮廓，且四类轮廓在实际折叠尺寸下可互相辨认

#### Scenario: Missing or unknown model
- **WHEN** 机器没有设备清单、设备名为空，或设备名不属于任何受支持机型
- **THEN** 该机器使用通用主机轮廓，不显示虚构型号

#### Scenario: Ambiguous or incomplete model set
- **WHEN** 同一机器同时出现多类受支持机型，或部分设备名无法识别
- **THEN** 该机器使用通用主机轮廓，并在悬停或键盘聚焦时仍列出可用的完整设备名

#### Scenario: Legacy configuration
- **WHEN** 旧配置的机器尚未采集设备型号或不含型号字段
- **THEN** 页面正常加载并使用通用主机轮廓，无需迁移配置

#### Scenario: Inventory confidence across polling and restart
- **WHEN** 机器从一次完整或不完整的采样转为离线或过期，或服务从历史加载设备清单
- **THEN** 机器快照 SHALL 以 `gpu_inventory_complete` 表示清单证据，即 `true` 为已确认完整、`false` 为已知不完整、`null` 为无法确认。完整可信且机型一致的清单保留轮廓，不完整或不可核实的清单显示通用轮廓，后续完整采样可恢复对应轮廓

#### Scenario: Legacy snapshot without inventory confidence
- **WHEN** 旧机器快照缺少顶层 `gpu_inventory_complete`
- **THEN** 页面 SHALL 使用当前 `metrics.gpu_inventory_complete` 中的明确证据。没有完整性证据时使用通用轮廓，提示仍显示可用设备名

#### Scenario: PRO 6000 model boundary
- **WHEN** 设备名包含合法独立型号词 `PRO 6000` 或含紧邻尾缀的未知型号 `PRO 6000X`
- **THEN** 合法型号映射到双槽卡轮廓，未知变体显示通用轮廓并保留完整型号提示

#### Scenario: Model changes during polling
- **WHEN** 一次常规轮询只更新了一台机器（包括未选中的机器）的设备型号，而状态和用于渲染签名的其他字段保持不变
- **THEN** 侧栏和总览中的轮廓、完整型号提示及同轮廓实例后缀在无需导航的情况下随之更新，选中其他机器时同样生效

### Requirement: Compact rail exposes instance and full model identity

收起侧栏的机器按钮 SHALL 在鼠标悬停和键盘聚焦时提供原始实例名、当前状态和所有可用的完整 GPU 型号。同一轮廓或同一名称的多个实例 SHALL 在收起侧栏显示可区分的简短后缀。名称相同或 Unicode 规范等价的实例 SHALL 在可访问名称及提示中包含各自的后缀。

#### Scenario: Hover and keyboard focus
- **WHEN** 操作者悬停机器按钮的任意区域（包括内部状态标记）或键盘聚焦该按钮
- **THEN** 提示一致地包含实例名、状态和可用的完整型号，且键盘用户可继续用 Enter 或 Space 打开该机器

#### Scenario: Identical instance names
- **WHEN** 两台机器的实例名相同或 Unicode 规范等价
- **THEN** 它们的可见后缀、可访问名称、悬停和键盘焦点提示仍能区分彼此，保留各自原始别名

#### Scenario: Multiple instances of one model
- **WHEN** 多台机器具有相同机型轮廓
- **THEN** 每台机器显示互不相同的简短后缀，且完整实例名仍可通过悬停、聚焦和可访问名称获得

#### Scenario: No reliable model names
- **WHEN** 多台机器都回退到通用主机轮廓且没有可用型号
- **THEN** 它们仍通过实例名派生的后缀和可访问名称区分，不显示编造的型号

### Requirement: Silhouettes preserve status and navigation semantics

机型轮廓 SHALL 使用单一继承色描边，SHALL NOT 以轮廓颜色表达在线、告警或离线状态。状态 SHALL 继续由独立标记表达；选中、导航、展开和窄屏布局 SHALL 保持可用且无横向溢出。

#### Scenario: Status remains independent
- **WHEN** 正常、告警和离线机器使用相同或不同机型轮廓
- **THEN** 每台机器仍显示其独立状态标记，轮廓本身不改变状态含义

#### Scenario: Monochrome and contrasting surfaces
- **WHEN** 轮廓在深色侧栏或浅色内容区以单色渲染
- **THEN** 四类机型轮廓仍可辨认，且不使用额外颜色区分机型

#### Scenario: Selected machine
- **WHEN** 操作者选中一台机器
- **THEN** 收起和展开侧栏都显示选中状态，轮廓和状态标记仍可见

#### Scenario: Narrow viewport
- **WHEN** 操作者在窄屏收起或展开侧栏
- **THEN** 机器轮廓、状态、后缀和展开控件保持可见，页面不出现横向溢出

### Requirement: Current GPU process timing

The hardware list and GPU detail dialog SHALL display the start date and time and the elapsed wall-clock runtime at sampling for each visible GPU process. Both values SHALL use the same verified process and monitored endpoint sample. The display SHALL use the selected dashboard language and browser time zone and SHALL show both values as unknown when the timing pair cannot be verified.

#### Scenario: Verified host process
- **WHEN** a visible GPU PID is matched to a stable host process and timing is available
- **THEN** the current snapshot includes its start timestamp and elapsed runtime, and both views display the pair alongside existing process information

#### Scenario: PID reused or process exited during collection
- **WHEN** the PID resolves to a later process or the original identity cannot be verified throughout collection
- **THEN** both timings are unknown and the NVIDIA process record remains visible with its available device information

#### Scenario: Timing unavailable or snapshot predates process timing
- **WHEN** host timing or process identity cannot be verified, including from a GPU-only container view, or either snapshot field is missing or invalid
- **THEN** each view displays localized unknown values for both timings and retains available process and ownership information

#### Scenario: Poll refreshes a process sample
- **WHEN** the dashboard receives a new sample with updated runtime, timing availability or process rows
- **THEN** the hardware list and open GPU detail dialog use the new sample while retaining the dialog's normal dismissal and keyboard behavior
