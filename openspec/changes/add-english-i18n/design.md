# Design

## Context
See proposal.md. FastAPI serves static HTML and a native monitor.js with string templates and canvas charts; no bundler or frontend framework exists. Existing browser smoke checks mock every API.

## Goals / Non-Goals
Provide a small native localization boundary and bilingual UX. Preserve monitoring semantics, collection, raw evidence and HTTP responses. No service/deployment changes.

## Decisions
- Use an i18n.js browser global plus locales.js resources, loaded before monitor.js, rather than introducing a framework/build chain. Stable message keys separate copy from page logic.
- Resolve localStorage preference with guarded access, Chinese default, explicit supported-locale registry. Hide content until synchronous bootstrap has localized static text/attributes; no SSR hydration is present.
- Translate static HTML via data attributes; dynamic render functions use t(), named interpolation and Intl wrappers. Rebuild derived status dictionaries on locale changes and rerender current view without resetting filters/history.
- Keep arbitrary backend diagnostics untouched as evidence. Provide localized operation error context for unrecognized server details. Known application messages use centralized translations; no HTTP response schema change.
- Offer selector outside dialogs; modal focus prevents mid-form switches. Preserve form contents and avoid DOM mutation translation observers.

## Risks / Trade-offs
- Longer English text → responsive synthetic browser checks and screenshots.
- Unknown diagnostics can be Chinese → retain original evidence under localized operation context; do not fabricate translations.
- Storage can be blocked → guard reads/writes and retain session preference.
- Resource drift → key/placeholder parity and untranslated UI checks.

## Migration Plan
Static assets ship together through normal package data. No database migration. Revert the commit to roll back. Mika owns review, main integration and any separately authorized deployment.
