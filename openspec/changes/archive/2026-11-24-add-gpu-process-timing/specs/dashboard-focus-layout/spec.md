# Spec Delta

## ADDED Requirements

### Requirement: Current GPU process timing

The hardware list and GPU detail dialog SHALL display the start date and time and the elapsed wall-clock runtime at sampling for each visible GPU process. Both values SHALL use the same verified process and monitored endpoint sample. The display SHALL use the selected dashboard language and browser time zone and SHALL show both values as unknown when the timing pair cannot be verified.

#### Scenario: Verified host process
- **WHEN** a visible GPU PID is matched to a stable host process and timing is available
- **THEN** the current snapshot includes its start timestamp and elapsed runtime, and both views display the pair alongside existing process information

#### Scenario: PID reused or process exited during collection
- **WHEN** the PID resolves to a later process or the original identity cannot be verified throughout collection
- **THEN** both timings are unknown and the NVIDIA process record remains visible with its available device information

#### Scenario: Timing unavailable or snapshot predates process timing
- **WHEN** host timing or process identity cannot be verified, including from a GPU-only container view, or either snapshot field is missing or invalid
- **THEN** each view displays localized unknown values for both timings and retains available process and ownership information

#### Scenario: Poll refreshes a process sample
- **WHEN** the dashboard receives a new sample with updated runtime, timing availability or process rows
- **THEN** the hardware list and open GPU detail dialog use the new sample while retaining the dialog's normal dismissal and keyboard behavior
