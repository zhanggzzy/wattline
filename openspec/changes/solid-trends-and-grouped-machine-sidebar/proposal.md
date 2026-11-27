# Proposal

## Why

AN-234 asks for color to distinguish trend series and for room and cluster placement to be visible in machine navigation. The previous eight-color overview relies on dash patterns, and the sidebar has only a flat list.

## What Changes

- Use solid lines and matching swatches in the shared trend renderer. Verify distinct, stable colors beyond eight series while retaining scope labels, gaps, values, legend controls and sample tables.
- Add a localized sidebar mode selector in both densities. Default to persisted manual order. In cluster mode, show effective room subdivisions, all valid cluster memberships and clear fallback labels.
- Support reordering in the manual sidebar through the existing saved-order mechanism. Exercise switching, live membership updates, merged machine navigation, keyboard access and narrow layouts with synthetic data.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `overview` covers distinct solid trend colors for room, cluster and legacy machine series.
- `dashboard-focus-layout` covers the shared trend rendering and the sidebar modes in both densities.

## Impact

The dashboard changes its browser UI and saves one preference in browser storage. It uses the existing snapshot projection and order endpoints, so no API contract, persistent server configuration, dependency or database migration is required.
