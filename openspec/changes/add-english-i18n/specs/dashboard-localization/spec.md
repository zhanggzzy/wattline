## Purpose
Allow Wattline operators to use the complete monitoring dashboard in Chinese or English, with a consistent and extensible language preference and formatting contract.

## ADDED Requirements

### Requirement: Bilingual dashboard
The dashboard SHALL present navigation, overview, machine/GPU details, charts, forms, statuses, errors and empty states in Chinese or English. User names, machine identities and raw diagnostic evidence SHALL remain unchanged. Business HTTP APIs SHALL remain compatible.

#### Scenario: English core interactions
- **WHEN** an operator chooses English and opens machine/GPU details or configuration/removal dialogs
- **THEN** dashboard labels, chart descriptions and application validation messages use English while identifiers remain intact

#### Scenario: Switch language after a machine mutation
- **WHEN** an operator saves or removes a machine successfully or unsuccessfully, closes the dialog, switches between Chinese and English, and reopens without reloading
- **THEN** action buttons use the selected language in visible text and accessible names, and show the proper busy/restored labels during submissions

### Requirement: Stable language preference
The dashboard SHALL default to Chinese, offer an accessible language selector, persist supported preferences in browser storage, and fall back to Chinese for unsupported preferences or unavailable storage. Selected language SHALL apply before dashboard content becomes visible and update document language.

#### Scenario: Preference restoration
- **WHEN** an operator selects English and reloads
- **THEN** English is restored without exposing initial Chinese content

#### Scenario: Storage failure
- **WHEN** preference storage throws or contains an unsupported locale
- **THEN** the dashboard remains usable in Chinese and allows a session language change

### Requirement: Extensible localization contract
Translations SHALL be centralized, support named interpolation and locale-aware numbers/dates, and fall back to Chinese for missing translations then the key for unknown keys. Adding a language SHALL use resource and registry changes without page-level locale branches. Translated values SHALL not execute HTML from interpolation.

#### Scenario: Missing translation
- **WHEN** a locale lacks a message present in Chinese
- **THEN** the Chinese message is displayed with supplied parameters

#### Scenario: Resource verification
- **WHEN** supported resources are checked
- **THEN** English and Chinese keys and interpolation placeholders match
