# Design

## Context

`/api/group-history` takes up to six group IDs and emits fixed five-minute slots, with a column per group and observation scope. Overview normally requests machine view. The room or cluster detail, legacy machine overview and archive use the existing chart renderer.

## Goals

Keep the approved layout and accessibility behavior in the grouped overview, including its focused charts. Keep history queries, aggregation, membership and source selection in their existing layers.

## Decisions

- Use the eligible group ID as the panel and visibility key and the group ID plus scope as the series and color key. Use the existing requested group order and report the selection limit. Distinguish duplicate names with their group IDs. Keep summaries and readings per scope. Plot separate scope lines in the same group panel without recomputing a group aggregate.
- Put the shared controls, time, summaries, coverage, legend and table in HTML. Draw lines, grid, shared time labels, ruler and missing-slot hatch in Canvas. Use one bottom time axis and a shared scale drawn from all visible series for the metric. Use hatching where every plotted scope lacks a value. The per-scope missing count and table retain partial gaps. Use the arithmetic mean of finite bucket values and the earliest bucket for tied peaks.
- Store layout preference in browser storage when possible. Keep isolated group and explicit visibility separate so restoring isolation restores the previous selection. Keep a selected bucket timestamp per surface and metric during polling. Use native buttons and one ruler tab stop per chart. Announce keyboard and committed touch reads without reading each pointer move aloud.
- Keep the legacy renderer for group detail, machine overview, device and archive charts. Reuse the solid segment painter and data-table formatter. The alternate group renderer starts with two eligible groups, including when the operator has hidden all but one. A one-group overview continues to use the existing plot.

## Trade-offs

Six aligned plots use more vertical space than one overlay. Compact plot heights, the single time axis and the overlay option bound that cost. A view with multiple scopes may have partial gaps that cannot share one background texture. Scope-level summaries and exact table cells expose those gaps. Browser-specific accessibility rendering requires verification beyond the Chromium fixture.
