# Proposal

## Why
AN-44 / AN-42 require English for Wattline while preserving Chinese. UI strings and zh-CN formatting are currently embedded in a single native JavaScript dashboard and HTML dialogs, making future language additions invasive.

## What Changes
- Add a central locale registry, resources, translation/interpolation and Intl formatting API with Chinese fallback.
- Add a discoverable persisted language selector, translate overview, node/GPU details, charts, dialogs, status and errors.
- Verify resource parity, persistence/fallback and synthetic browser flows in both languages alongside Python regression checks.

## Capabilities
### New Capabilities
- `dashboard-localization`: localized dashboard content, locale preferences and extensible translation interfaces.
### Modified Capabilities
None.

## Impact
Static HTML/JS/CSS, synthetic browser checks and documentation. No breaking HTTP API changes, backend data changes, live nodes or deployment. Acceptance requires bilingual core interactions, Chinese default, safe fallback, centralized formatting and reproducible checks. Independent review and integration remain pending for Mika.
