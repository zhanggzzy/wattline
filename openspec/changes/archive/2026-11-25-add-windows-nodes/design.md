# Design

## Context

Registration verifies machine identity before settings are saved. The collector already bounds SSH probes, validates identity and normalizes Linux samples for the history service.

## Goals / Non-Goals

Support native Windows targets through the existing service, history schema and localized dashboard. Supporting Wattline as a Windows service, deploying an agent and changing target privileges are outside this change.

## Decisions

- Persist `target_os` as enrollment metadata. A Windows enrollment records a canonical ED25519 fingerprint in the existing pins table even when no collision is found. An explicit OS avoids probing a target with both shells.
- Use a short encoded Windows PowerShell bootstrap and transfer the UTF-8 script through SSH stdin as Base64. This avoids shell interpolation and command-length limits while keeping the probe packaged with Wattline. SSH continues to apply strict known-host verification. Read the SMBIOS UUID with CIM and normalize valid non-sentinel GUIDs to 32 hexadecimal characters. Use the UTC last boot time as boot identity.
- Use the mean of formatted `Processor Information` per-processor instances across groups and require distinct instances to match the CIM logical processor count. This avoids relying on a single processor group's cumulative clock. Report the latest formatted sample after reboot. Obtain memory from the OS and use its SystemDrive for volume metrics. [Microsoft performance counter model](https://learn.microsoft.com/en-us/windows/win32/perfctrs/about-performance-counters)
- Read NVIDIA XML with a bounded native process. Reuse Linux's card measurement decoding and use a Windows-specific process policy. Treat enumeration as partial since the probe cannot certify coverage. Accept a process identity only when CIM creation predates the NVIDIA query and survives rechecking. Keep recorded PID and measurements if account discovery fails. [NVIDIA field availability](https://docs.nvidia.com/deploy/nvidia-smi/)
- Sort and trim only in the dashboard. The current snapshot, occupancy and overview counts retain all observed processes. Use the existing history writer for aggregate and card series.

## Risks / Trade-offs

- CIM or NVIDIA permissions and driver support vary. Report missing data with existing warning and unknown states.
- Windows inventory can explicitly report no devices. A failed or malformed query preserves prior inventory as incomplete.
- Exercise strict key failure and reboot with temporary synthetic data. Record the actual target check and coverage in verification.

## Migration Plan

Existing rows default to Linux on read, with no SQLite schema change. Register Windows targets after upgrading. An older release cannot read a Windows registration, so retain a consistent pre-upgrade data backup for binary rollback.
