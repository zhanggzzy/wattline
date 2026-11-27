## ADDED Requirements

### Requirement: Aligned room and cluster trend comparison

The room and cluster overview SHALL default to one aligned plot per group when two to six groups are selected for charting. Plots SHALL share the 24-hour time axis and metric scale. Operators SHALL be able to switch to a solid-line overlay, highlight a group, and isolate it with an action that restores the previous visible groups.

#### Scenario: Compare related groups with multiple scopes
- **WHEN** charted groups share members or names, or a group has separate observation scopes
- **THEN** each group has a distinguishable label and all returned scopes retain their own solid strokes, values and coverage inside the corresponding group. The display uses one scale across groups, including 0–100% for utilization.

#### Scenario: Chart request is limited to six groups
- **WHEN** more than six groups match the current overview filters
- **THEN** the trend identifies how many matching groups it charts, and filtering can bring other groups into range.

#### Scenario: Compare in overlay or full-page focus
- **WHEN** the operator hides, highlights, isolates or restores a group, including in full-page multi-metric focus
- **THEN** the visible series, readings, table columns and labels agree. Highlighting leaves other visible groups available. Visibility, mode and valid control focus survive polling.

### Requirement: Synchronized group bucket readings

Group comparison SHALL allow mouse, touch and keyboard users to inspect the same five-minute bucket across visible groups. Readings and coverage SHALL appear outside the plots. Each observation scope SHALL show its peak with time, mean across valid buckets, and missing-bucket count. Charts SHALL preserve sampled zero, gaps and isolated samples.

#### Scenario: Inspect a missing bucket next to observed zero
- **WHEN** a group has observed zero, missing readings or a discontinuous sample
- **THEN** zero appears at the baseline and contributes to the mean, missing data breaks the line and has a visible texture where the plotted scopes are all missing, and isolated observations remain visible. The semantic table preserves the same values and coverage.

#### Scenario: Navigate a 24-hour chart on a narrow viewport
- **WHEN** the operator reads the chart at 320 CSS pixels, uses forced colors, or moves the ruler with touch or a keyboard
- **THEN** labels and controls remain usable without page overflow or plot occlusion. Keyboard interaction includes hourly jumps, endpoints and clearing the current ruler with Escape before exiting full-page mode.
