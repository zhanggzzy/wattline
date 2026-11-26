## ADDED Requirements

### Requirement: Global configuration from the overview

The overview SHALL expose a localized Global configuration entry. Operators SHALL see the global override state and effective Linux GPU tolerance with its source, and be able to save a numeric override or clear it.

#### Scenario: Revert a global override
- **WHEN** an operator clears the global setting
- **THEN** the effective global value becomes 256 MiB from the built-in default and is reflected in subsequent samples that inherit it
