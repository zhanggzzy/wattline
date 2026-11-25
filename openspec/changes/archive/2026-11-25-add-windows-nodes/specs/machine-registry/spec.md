# Spec Delta

## ADDED Requirements

### Requirement: Target operating system of SSH registration

The enrollment UI, API, and machine configuration SHALL support Linux and Windows SSH targets. Omitted OS values SHALL resolve to Linux for existing configuration and stored registration. The selected OS SHALL survive reload and appear in the snapshot. Windows enrollment SHALL require public-key login, strict known-host verification, a stable machine identity and an ED25519 host key pinned for future sampling.

#### Scenario: Registration and reload
- **WHEN** an operator enrolls a verified Windows SSH target and restarts Wattline
- **THEN** the reloaded registration uses the Windows probe and the original pinned identity and key

#### Scenario: Identity collision or change
- **WHEN** two aliases identify the same machine and key, or a sampled identity or key differs from the enrolled evidence
- **THEN** duplicate enrollment or the mismatched sample is rejected, preserving existing history
