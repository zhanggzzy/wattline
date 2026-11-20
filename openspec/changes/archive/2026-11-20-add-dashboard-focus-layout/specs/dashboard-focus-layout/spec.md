# Spec Delta

## Purpose

Allow operators to recover dashboard space for resource comparisons and inspect hardware workloads while retaining machine identity, CPU information and trustworthy missing-data semantics.

## ADDED Requirements

### Requirement: Reversible compact navigation
The dashboard SHALL provide an expanded rail and a narrow status-only machine rail. Both modes SHALL retain named keyboard-operable machine selection, selected-machine indication, readable status through accessible text, and an operable expand control on desktop and narrow screens.

#### Scenario: Compact rail selection
- **WHEN** the operator collapses navigation and selects a machine using the keyboard
- **THEN** only its status indicator is visually shown in the machine button, its name/status remain accessible, selection is indicated and expansion restores names

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
