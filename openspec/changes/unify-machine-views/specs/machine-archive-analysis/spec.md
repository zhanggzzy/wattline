## ADDED Requirements

### Requirement: Archive analysis follows machine identity

Archive analysis SHALL resolve registered sources to the same machine as recent trends. Existing gzip format and per-source archive analysis SHALL remain readable.

#### Scenario: Archive contains overlapping linked sources
- **WHEN** archived records include the same machine's sources, earlier unverified boots and an unrelated endpoint
- **THEN** the machine analysis selects readings from its canonical source and secondary samples from the verified common boot, shows one plotted value per bucket, and the source selector can still display earlier records under their original history key
