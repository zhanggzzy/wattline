"""Identity evidence and observation selection for the machine view."""
from dataclasses import dataclass
import re


LINUX_BOOT = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}')
CONTAINER_ID = re.compile(r'[a-f0-9]{64}')
SCOPED_METRICS = ('cpu', 'memory', 'memory_used')


@dataclass(frozen=True)
class SourceObservation:
    boot: str | None
    scope: str
    container_id: str | None
    at: int

    @classmethod
    def from_sample(cls, boot, scope, container_id, at):
        return cls(boot if isinstance(boot, str) and LINUX_BOOT.fullmatch(boot) else None,
                   'container' if scope == 'container' else 'host',
                   container_id if isinstance(container_id, str) and CONTAINER_ID.fullmatch(container_id) else None,
                   at)


def preferred_observation(rows):
    """Use one fresh source for CPU and memory, with deterministic ties."""
    return max(rows, key=lambda row: (
        row.get('metrics') is not None, row.get('enabled', True), row.get('scope') == 'host',
        row.get('observed_at') or 0,
    ))
