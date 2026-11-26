# Proposal

## Why

AN-217 implements AN-215. A usable GPU sample can carry a warning about unconfirmed occupancy. Today the alert center treats that warning as a collection issue and leaves it active until a warning-free sample arrives. Timeouts and expired samples use separate alert names.

## What Changes

- Show 空闲 and 占用未确认 in the GPU device status, using the existing occupancy evidence and state values.
- Raise a machine collection issue when sampling fails, times out or the last usable sample expires.
- Resolve the issue when a new usable sample arrives within the existing validity period, including samples with unconfirmed GPU occupancy.

## Capabilities

### New Capabilities

### Modified Capabilities

- `in-app-alerts` — Define machine collection issue triggers and verified recovery.

## Impact

Machine health, persisted alerts and GPU status labels are affected. The alert API and SQLite schema are compatible with historical offline/stale records. New machine collection incidents use the existing `collection` rule. Storage adapters retain their existing alert policies.
