# Spec Delta

## MODIFIED Requirements

### Requirement: Reversible compact navigation

The dashboard SHALL provide an expanded rail and a narrow machine-identity rail. Both modes SHALL retain named keyboard-operable machine selection, selected-machine indication, an independent status indicator with accessible text, and an operable expand control on desktop and narrow screens. The narrow rail SHALL show a machine-model silhouette derived from reliable observed model information, or a generic host silhouette when no reliable model is available.

#### Scenario: Compact rail selection
- **WHEN** the operator collapses navigation and selects a machine using the keyboard
- **THEN** its machine-model or generic silhouette and independent status indicator are visually shown, its instance name, status and available full model remain accessible, selection is indicated, and expansion restores names

#### Scenario: Expanded rail identity
- **WHEN** the operator expands navigation
- **THEN** each machine still shows its instance name and status, the same model or generic silhouette remains visible, and navigation, selection and keyboard behavior are unchanged

## ADDED Requirements

### Requirement: Machine silhouette follows reliable model information

收起侧栏的机器轮廓 SHALL 依据该机器已采集到的 GPU 产品名映射：B300 使用厚重机柜轮廓，RTX PRO 6000 使用双槽卡轮廓，GB10 或 DGX Spark 使用紧凑方盒轮廓，RTX 5090 使用双风扇卡轮廓。机型信息缺失、未知、有歧义或不完整时，SHALL 使用通用主机轮廓，不得按机器名、地址或外形猜测型号。

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

### Requirement: Compact rail exposes instance and full model identity

收起侧栏的机器按钮 SHALL 在鼠标悬停和键盘聚焦时提供实例名、当前状态和所有可用的完整 GPU 型号。同一轮廓下存在多台机器时，SHALL 在收起侧栏显示由实例名派生的简短后缀，使这些实例可直接区分；后缀在不同机器间不得重复。

#### Scenario: Hover and keyboard focus
- **WHEN** 操作者悬停或键盘聚焦收起侧栏的机器按钮
- **THEN** 提示包含实例名、状态和可用的完整型号，且键盘用户可继续用 Enter 或 Space 打开该机器

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
