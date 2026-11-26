"""Identity evidence and observation selection for the machine view."""
from dataclasses import dataclass
import math
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
    """Choose the observation for status, GPU details and system facts."""
    return max(rows, key=lambda row: (
        row.get('metrics') is not None, row.get('enabled', True), row.get('scope') == 'host',
        row.get('observed_at') or 0,
    ))


def observation_priority(row):
    return row.get('scope') != 'container', row.get('observed_at') or 0


def known(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def memory_reading(metrics):
    memory = metrics.get('memory') or {}
    used, total = memory.get('used_bytes'), memory.get('total_bytes')
    percent = metrics.get('memory_percent')
    if known(used):
        if known(total) and total > 0 and used <= total:
            return memory, percent if known(percent) else 100 * used / total
        return {'used_bytes':used, 'total_bytes':None}, None
    # Older samples can have a usage percentage without measured bytes.
    return None, percent if known(percent) and not (memory and total is None) else None


def machine_resource_metrics(rows):
    measured = [dict(row, scope=row['metrics'].get('scope') or 'host')
                for row in rows if row.get('metrics') is not None]
    ordered = sorted(measured, key=observation_priority, reverse=True)
    cpu_row = next((row for row in ordered if known(row['metrics'].get('cpu_percent'))),
                   ordered[0] if ordered else {})
    cpu = cpu_row.get('metrics', {})
    cpu_percent = cpu['cpu_percent'] if known(cpu.get('cpu_percent')) else None
    result = {'cpu_scope':cpu_row.get('scope'), 'cpu_count':cpu.get('cpu_count'),
              'load_average':cpu.get('load_average'), 'cpu_percent':cpu_percent,
              'cpu_source_id':cpu_row.get('id') if cpu_percent is not None else None,
              'memory_scope':None, 'memory_source_id':None, 'memory':None, 'memory_percent':None}
    for row in ordered:
        memory, percent = memory_reading(row['metrics'])
        if memory is not None or percent is not None:
            result.update(memory_scope=row['scope'], memory_source_id=row.get('id'), memory=memory, memory_percent=percent)
            break
    return result
