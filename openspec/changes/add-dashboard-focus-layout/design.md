# Design

## Context

See proposal.md. The static client owns one canvas with one history request, shape-based rerendering and native configuration dialogs. GPU selection currently rebuilds the machine page with inline details. Existing CPU/memory cards and system facts contain information not represented by physical GPU inventory.

## Goals / Non-Goals

**Goals:** extend existing native controls, localized resources and synthetic browser harness; reuse plotting and API semantics for each metric; preserve CPU and container scope.

**Non-Goals:** backend changes, fullscreen browser permission, dependencies at runtime, real collection or deployment.

## Decisions

- Use CSS rail density and named/title machine controls; persist density defensively in browser storage. On narrow screens the compact rail remains a vertical strip, while expanded navigation keeps its existing horizontal layout.
- Use an in-document page focus mode (rather than browser Fullscreen API) with explicit return and Escape. Render a stack of chart instances, each with independent canvas, summary, tooltip, live announcement and ResizeObserver. Metric selection follows existing supported metrics; guard against empty selection. Shared hours and host/GPU context; fetch existing history endpoints in parallel with an abort generation so stale responses cannot overwrite a newer selection.
- Keep primary chart IDs for existing checks; additional instances get metric-suffixed IDs. Pass chart instances explicitly to draw/tooltip helpers rather than swapping a global during callbacks. Each chart also exposes a lazy native disclosure with a semantic sample table for nonvisual reading; pointer moves do not rebuild the table.
- Replace the split detail columns with a full-width trend panel followed by an integrated hardware table. One row per GPU includes live measurements and a process list; retain all CPU cards/facts. Native dialog shows existing GPU details and process evidence. A separate action inside details opens that GPU’s trends; browsing details alone does not change trend context.
- Defer structural snapshot rebuilds during modal inspection, retain the original invoker and repaint current readings. Dialog close restores focus and then allows ordinary refresh.

## Risks / Trade-offs

- Many selected metrics increase fetches → bounded by existing supported metric list; abort obsolete generations and keep errors per chart.
- Wide hardware content → container-responsive labeled rows plus a named focusable scroll fallback.
- Browser-specific modal/Canvas behavior → automated Chromium evidence; disclose Firefox/Safari and assistive-technology limits.
- Modern guidance source unavailable locally → read the official fixed v1.0.1 sources referenced by existing design notes, record actual retrieval and applicability.

## Migration Plan

No schema migration. Deliver one review branch/PR; Mika handles independent review and main integration. Reverting static files restores prior UI. Do not archive before independent review.
