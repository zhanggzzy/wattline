"""Validation and persistent data for storage resources and resource alerts."""

import json
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import MachineId, PersonId, normalize_person_name


class StorageSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=80)
    storage_kind: Literal['nas', 'storage_cluster']
    adapter: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]{1,40}$')
    enabled: bool = True
    person_id: PersonId | None = None
    shared: bool = False
    room_id: MachineId | None = None

    @model_validator(mode='after')
    def validate_settings(self):
        self.name = normalize_person_name(self.name)
        if not self.name or (self.shared and self.person_id is not None):
            raise ValueError('invalid_storage_settings')
        return self


Bytes = Annotated[int, Field(strict=True, ge=0, le=2**63-1)]
Rate = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class StorageCapacity(BaseModel):
    used_bytes: Bytes
    total_bytes: Bytes

    @model_validator(mode='after')
    def valid_capacity(self):
        if self.used_bytes > self.total_bytes:
            raise ValueError('used capacity exceeds total')
        return self


class StoragePool(StorageCapacity):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    health: Literal['healthy', 'degraded', 'failed', 'unknown'] = 'unknown'


class StorageMember(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    role: str | None = Field(default=None, max_length=128)
    health: Literal['healthy', 'degraded', 'failed', 'unknown'] = 'unknown'
    capacity_bytes: Bytes | None = None


LogicalId = Annotated[str, Field(min_length=1, max_length=128)]


class StorageObservation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    identity: LogicalId
    covered_identities: tuple[LogicalId, ...] = Field(default=(), max_length=256)
    observed_at: Annotated[int, Field(strict=True, ge=0, le=2**63-1)]
    scope: Literal['logical', 'unverified']
    capacity: StorageCapacity | None = None
    health: Literal['healthy', 'degraded', 'failed', 'unknown']
    read_bytes_per_second: Rate | None = None
    write_bytes_per_second: Rate | None = None
    pools: tuple[StoragePool, ...] = Field(default=(), max_length=256)
    members: tuple[StorageMember, ...] = Field(default=(), max_length=256)

    @model_validator(mode='after')
    def unique_pools(self):
        pools = {}
        for pool in self.pools:
            existing = pools.setdefault(pool.id, pool)
            if (existing.used_bytes, existing.total_bytes, existing.health) != (
                pool.used_bytes, pool.total_bytes, pool.health
            ):
                raise ValueError('conflicting observations for one pool')
        self.pools = tuple(pools.values())
        self.covered_identities = tuple(dict.fromkeys(key for key in self.covered_identities if key != self.identity))
        return self


class StorageAdapter(Protocol):
    async def __call__(self, resource_id: str, settings: StorageSettings) -> StorageObservation: ...


RESOURCE_SCHEMA = (
    'CREATE TABLE shared_users (resource TEXT PRIMARY KEY) WITHOUT ROWID',
    'CREATE TABLE storage_resources (id TEXT PRIMARY KEY, settings TEXT NOT NULL) WITHOUT ROWID',
    """CREATE TABLE storage_ticks (
        resource TEXT NOT NULL REFERENCES storage_resources(id) ON DELETE CASCADE,
        at INTEGER NOT NULL, status TEXT NOT NULL, observation TEXT,
        PRIMARY KEY(resource,at)) WITHOUT ROWID""",
    'CREATE INDEX storage_ticks_at ON storage_ticks(at)',
    """CREATE TABLE alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, resource TEXT NOT NULL, kind TEXT NOT NULL,
        name TEXT NOT NULL, rule TEXT NOT NULL, severity TEXT NOT NULL,
        first_at INTEGER NOT NULL, last_at INTEGER NOT NULL, evidence TEXT,
        last_success_at INTEGER, recovered_at INTEGER, recovery_evidence TEXT,
        closed_at INTEGER, closure_reason TEXT)""",
    'CREATE UNIQUE INDEX active_resource_alert ON alerts(resource,rule) WHERE recovered_at IS NULL AND closed_at IS NULL',
    'CREATE INDEX alerts_last_at ON alerts(last_at DESC,id DESC)',
)

ACTIVE = 'recovered_at IS NULL AND closed_at IS NULL'
RETENTION_MS = 90 * 24 * 60 * 60 * 1000


def write_resource_users(db, key, people, shared):
    db.execute('DELETE FROM machine_assignees WHERE machine=?', (key,))
    db.execute('DELETE FROM shared_users WHERE resource=?', (key,))
    if shared:
        db.execute('INSERT INTO shared_users VALUES (?)', (key,))
    else:
        db.executemany('INSERT INTO machine_assignees VALUES (?,?)', ((key, person) for person in people))


def update_alerts(db, resource, kind, name, at, triggered, cleared, last_success_at):
    for rule, (severity, evidence) in triggered.items():
        db.execute(f"""
            INSERT INTO alerts(resource,kind,name,rule,severity,first_at,last_at,evidence,last_success_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(resource,rule) WHERE {ACTIVE} DO UPDATE SET
              last_at=excluded.last_at, evidence=excluded.evidence, name=excluded.name,
              kind=excluded.kind, severity=excluded.severity,
              last_success_at=coalesce(excluded.last_success_at,alerts.last_success_at)
            WHERE excluded.last_at >= alerts.last_at
        """, (resource, kind, name, rule, severity, at, at, evidence, last_success_at))
    for rule, evidence in cleared.items():
        db.execute(f"""UPDATE alerts SET recovered_at=?, recovery_evidence=?, last_success_at=?
                      WHERE {ACTIVE} AND resource=? AND rule=? AND last_at<=?""",
                   (at, evidence, last_success_at, resource, rule, at))


def close_alerts(db, resource, at, reason):
    db.execute(f"""UPDATE alerts SET closed_at=max(?,last_at), closure_reason=?
                  WHERE {ACTIVE} AND resource=?""", (at, reason, resource))


def alert_view(row):
    result = dict(row)
    result['status'] = 'resolved' if row['recovered_at'] is not None else (
        'closed' if row['closed_at'] is not None else 'active')
    return result


def storage_tick(rows):
    return [
        {'observed_at': at, 'status': status, 'observation': json.loads(data) if data else None}
        for at, status, data in rows
    ]
