# Spec Delta

## ADDED Requirements

### Requirement: Bounded Windows GPU process display

The integrated hardware table and GPU detail dialog SHALL show at most five observed processes per Windows GPU by descending known VRAM, with unknown values last and PID ascending for ties. Both views SHALL report the number of observed rows omitted. Occupancy and visible process totals SHALL use all collected records. Verified Windows account names SHALL render without a UID label when none exists.

#### Scenario: More than five records per card
- **WHEN** a GPU has more than five observed processes, including tied or unavailable VRAM
- **THEN** both views show the same ordered subset and omitted count while the snapshot retains each record
