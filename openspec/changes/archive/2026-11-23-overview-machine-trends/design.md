# Design

## Overview API

`GET /api/history` without `machine` becomes the overview contract:

- `metric` defaults to `gpu`; allowed values are `gpu`, `cpu`, `memory`, `power`.
- `hours` stays capped at 24. The `gpu` query parameter requires a machine.
- Response keeps `from`, `to`, `bucket_ms`, `gap_ms`, `keys` and `points`, and adds
  `machines`: the public machine ids in the same order as each point's `values`
  columns. The service maps internal history identities to public ids.
- `points` are aligned on a shared bucket grid for enabled machines. An
  unpopulated slot has a `null` value and `breaks: false` in its machine column.
  It has no plotted value. A populated bucket carries the continuity flag from
  that machine's downsampled series. `0` remains a real value.

Machine detail responses (`machine=...`) and GPU series stay unchanged.

## History layer

`History.overview` runs the existing whole-machine series query per machine and
merges the bucketed points by bucket index using one read connection. The
downsampler checks continuity using the timestamps of actual observations and
each previous sample's recorded staleness threshold, with the existing default
for records without an override. Explicit missing values and changes to boot,
collector epoch, GPU generation or power mode participate in that check. A gap
can be recorded on the next observed bucket after a lapse. The shared bucket
grid positions samples on the chart, while each machine column carries its own
continuity flags.

## Frontend

- Overview markup becomes a single stacked column: attention panel, trend panel,
  machine list panel, each full width. Existing filter/search/sort/drag and
  attention-button behaviour are unchanged.
- Overview trend always requests 24 hours, independent of the machine detail
  window that may have been selected earlier.
- The chart builds one series per `machines` entry in response order. Legend
  and tooltip labels are text nodes. Duplicate names append the machine address
  and any remaining duplicate labels append the machine ID. The legend and
  tooltip let long labels wrap within their available widths.
- The chart pairs its eight colours with sixteen dash patterns to give the 128
  supported machines distinct combinations. Canvas swatches use the same colours
  and dash patterns as the plotted lines.
- Overview metric buttons (`data-overview-metric`) switch the request and the
  pressed state without rebuilding the page. Fan-out/legend/tooltip use that
  metric's unit, so power renders in W and percentages use %.
- The overview skips alignment slots and splits at the history continuity flags.
  Machine and GPU detail keep their existing handling of missing values.
- Use the mainline chart instances and per-metric request state for both the
  overview and focused overview. Each focused plot requests its own metric at
  24 hours, starting with the metric selected on the overview. The detail
  plots keep their existing metric and range controls and request parameters.
- Use the existing locale resources and formatters for visible and accessible
  chart text. Render machine labels as text in legends and tooltips and escape
  them in the on-demand sample table. Cache chart output against each instance's
  series and relevant locale and history data, including label changes.

## Compatibility

The unqualified history response changes shape; the bundled workbench is its
only consumer. Database schema, sampling, archiving, machine detail and GPU
detail contracts are unchanged. No deployment or node access is involved.
