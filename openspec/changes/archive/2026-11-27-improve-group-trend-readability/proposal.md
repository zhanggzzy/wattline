# Proposal

## Why

AN-234 feedback showed that frequent GPU utilization changes and overlapping 24-hour series obscure low readings and sampling gaps. AN-237 evaluated alternatives and the operator approved aligned group charts with optional overlay comparison.

## What Changes

- Show two to six room or cluster groups in separate aligned plots by default. Use one time window and comparable scales while retaining observation scopes, coverage and solid strokes.
- Add synchronized bucket inspection, persistent group and scope labels, and peak, mean and missing-bucket summaries. Make sampled zero and missing readings visually distinguishable.
- Offer overlay comparison with group highlighting, isolation, restoration and a matching data table. Support normal and full-page layouts, keyboard, touch, English, Chinese and narrow viewports.

## Capabilities

### Modified Capabilities

- `overview` gains a room and cluster trend comparison view and shared bucket inspection.

## Impact

The frontend and synthetic browser tests change. The existing group IDs, 24-hour history API, five-minute buckets, observation scopes, coverage and storage formats remain compatible. Legacy per-machine overview, detail charts, archive analysis and sidebar navigation retain their existing paths.
