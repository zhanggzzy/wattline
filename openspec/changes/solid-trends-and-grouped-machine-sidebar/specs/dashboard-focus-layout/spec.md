## ADDED Requirements

### Requirement: Solid trend series and legends

The dashboard SHALL draw trend data with solid strokes and matching solid legend swatches. Series drawn together SHALL use distinct colors. Charts SHALL retain existing scope labels, readings, gaps, legend interactions and sample tables.

#### Scenario: Inspect trends across the dashboard
- **WHEN** an operator views an overview, room, cluster, machine, GPU, focused or archived trend
- **THEN** each plotted series and its swatch use the same solid color, and missing observations still break the plotted path

### Requirement: Switchable machine sidebar organization

The expanded and compact machine sidebar SHALL offer localized manual and cluster modes in both languages. Manual mode SHALL be the default and support drag and keyboard reordering through the saved device order. The sidebar SHALL preserve the mode in browser storage when available.

#### Scenario: Switch between cluster and manual modes
- **WHEN** an operator switches to cluster mode, navigates, and returns to manual mode
- **THEN** cluster mode has no sidebar reorder actions, the saved manual order is unaffected by grouped navigation, and manual mode restores that order

#### Scenario: Observe effective placement
- **WHEN** a machine is represented by several verified sources, belongs to multiple clusters, or lacks a valid placement
- **THEN** the sidebar uses the canonical machine and shows it once per effective cluster under its effective room, with localized no-cluster and no-room labels where appropriate

#### Scenario: Navigate during live updates
- **WHEN** an operator uses either sidebar density on a desktop or narrow screen while membership, names or status are refreshed
- **THEN** grouping updates without a reload, machine buttons remain keyboard accessible with identity, status and selection available, and the layout has no document-level horizontal overflow
