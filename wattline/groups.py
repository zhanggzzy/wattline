"""Physical rooms, clusters, and aggregate resource measurements."""

from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import IdleMemoryTolerance, MachineId, PersonId, normalize_person_name
from .machine_views import known, machine_resource_metrics, preferred_observation

GROUP_SCHEMA = (
    """CREATE TABLE rooms (
       id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, location TEXT,
       owner INTEGER REFERENCES people(id) ON DELETE RESTRICT) WITHOUT ROWID""",
    """CREATE TABLE clusters (
       id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
       person INTEGER REFERENCES people(id) ON DELETE RESTRICT, shared INTEGER NOT NULL) WITHOUT ROWID""",
    """CREATE TABLE resource_rooms (
       resource TEXT PRIMARY KEY, room TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE) WITHOUT ROWID""",
    'CREATE INDEX resource_rooms_room ON resource_rooms(room)',
    """CREATE TABLE cluster_resources (
       cluster TEXT NOT NULL REFERENCES clusters(id) ON DELETE CASCADE, resource TEXT NOT NULL,
       PRIMARY KEY(cluster, resource)) WITHOUT ROWID""",
    'CREATE INDEX cluster_resources_resource ON cluster_resources(resource)',
    'CREATE TABLE resource_order (resource TEXT PRIMARY KEY, position INTEGER NOT NULL UNIQUE) WITHOUT ROWID',
)
GROUP_BUCKET_MS = 5 * 60 * 1000


class GroupName(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=80)
    idle_memory_tolerance_mib: IdleMemoryTolerance | None = None

    @model_validator(mode='after')
    def valid_name(self):
        self.name = normalize_person_name(self.name)
        if not self.name:
            raise ValueError('group_name_required')
        return self


class RoomSettings(GroupName):
    location: str | None = Field(default=None, max_length=128)
    owner_id: PersonId | None = None

    @model_validator(mode='after')
    def valid_location(self):
        if self.location is not None:
            self.location = normalize_person_name(self.location) or None
        return self


class ClusterSettings(GroupName):
    person_id: PersonId | None = None
    shared: bool = False
    members: tuple[MachineId, ...] = Field(default=(), max_length=1024)

    @model_validator(mode='after')
    def valid_cluster(self):
        if (self.person_id is not None and self.shared) or len(set(self.members)) != len(self.members):
            raise ValueError('invalid_cluster')
        return self


class ResourceOrder(BaseModel):
    model_config = ConfigDict(extra='forbid')
    resources: tuple[MachineId, ...] = Field(max_length=1024)


class ResourceLocation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    room_id: MachineId | None


def unlink_resource(db, key):
    for table in ('resource_rooms','cluster_resources','resource_order'):
        db.execute(f'DELETE FROM {table} WHERE resource=?', (key,))


def write_room_link(db, key, assignment):
    if assignment.room_id is None:
        db.execute('DELETE FROM resource_rooms WHERE resource=?', (key,))
    else:
        db.execute("""INSERT INTO resource_rooms VALUES (?,?)
                      ON CONFLICT(resource) DO UPDATE SET room=excluded.room""", (key, assignment.room_id))


def compute_key(identity):
    return 'compute:'+identity


def storage_key(id):
    return 'storage:'+id


def metric(value, valid, total):
    return {'value':value,'valid':valid,'total':total}


def capacity(used, total, valid, eligible, *, unbounded_used=None):
    return {'used_bytes':used,'total_bytes':total,
            'percent':100*used/total if total and used is not None else None,
            'valid':valid,'total':eligible,'unbounded_used_bytes':unbounded_used}


def visible_gpu_readings(rows):
    gpus = {}
    for row in sorted(rows, key=lambda item:item.get('observed_at') or 0, reverse=True):
        for gpu in (row.get('metrics') or {}).get('gpus', ()):
            uuid = gpu.get('uuid')
            if not isinstance(uuid, str) or not uuid.startswith('GPU-') or len(uuid) <= 4:
                continue
            readings = gpus.setdefault(uuid.lower(), {})
            for field in ('utilization_percent','power_w'):
                if field not in readings and known(gpu.get(field)):
                    readings[field] = gpu[field]
            limit = gpu.get('default_power_limit_w')
            if 'default_power_limit_w' not in readings and known(limit) and limit > 0:
                readings['default_power_limit_w'] = limit
    return gpus


def expected_unseen_gpus(rows):
    return sum(max(0, (row.get('expected_gpu_count') or 0)-len((row.get('metrics') or {}).get('gpus', ())))
               for row in rows)


def machine_gpu_readings(rows):
    sources = [source for row in rows for source in row.get('_gpu_sources', (row,))]
    gpus = visible_gpu_readings(sources)
    unseen = sum(max(0, row['expected_gpu_count'] - len(visible_gpu_readings(row.get('_gpu_sources', (row,)))))
                 for row in rows if row.get('expected_gpu_count'))
    return gpus, len(gpus)+unseen


def gpu_power_total(gpus, field, total):
    watts = [gpu[field] for gpu in gpus.values() if field in gpu]
    return metric(sum(watts) if watts else None,len(watts),total)


def aggregate_scope(rows, scope):
    eligible = [row for row in rows if row.get('scope') == scope]
    seen = sorted((row for row in eligible if row.get('metrics') is not None),
                  key=lambda row:row.get('observed_at') or 0, reverse=True)
    gpus = visible_gpu_readings(seen)
    gpu_values = [gpu['utilization_percent'] for gpu in gpus.values() if 'utilization_percent' in gpu]
    # For GPU metrics, coverage is cards with readings out of visible or expected cards.
    gpu_total = len(gpus)+expected_unseen_gpus(eligible)
    return {
        'devices': len(eligible),
        **aggregate_cpu_memory((row['metrics'] for row in seen), len(eligible)),
        'gpu':metric(sum(gpu_values)/len(gpu_values) if gpu_values else None,len(gpu_values),gpu_total),
        'power':gpu_power_total(gpus,'power_w',gpu_total),
    }


def aggregate_cpu_memory(measurements, eligible):
    cpu = []
    used_values = []
    pairs = []
    unknown_limits = []
    for metrics in measurements:
        usage, cores = metrics.get('cpu_percent'), metrics.get('cpu_count')
        if known(usage) and known(cores) and cores:
            cpu.append((usage,cores))
        memory = metrics.get('memory') or {}
        used, total = memory.get('used_bytes'), memory.get('total_bytes')
        if known(used):
            used_values.append(used)
            if known(total) and total and used <= total:
                pairs.append((used,total))
            elif total is None:
                unknown_limits.append(used)
    used_total = sum(item[0] for item in pairs) if pairs else None
    total_bytes = sum(item[1] for item in pairs) if pairs else None
    return {
        'cpu':metric(sum(use*cores for use,cores in cpu)/sum(cores for _,cores in cpu) if cpu else None,
                     len(cpu),eligible),
        'memory_used':metric(sum(used_values) if used_values else None,len(used_values),eligible),
        'memory':capacity(used_total,total_bytes,len(pairs),eligible,
                          unbounded_used=sum(unknown_limits) if unknown_limits else None),
    }


def aggregate_storage(rows):
    logical = {}
    unverified = 0
    for row in sorted(rows, key=lambda item:item.get('observed_at') or 0, reverse=True):
        sample = row.get('storage_observation') or {}
        pair = sample.get('capacity')
        if not pair or not pair['total_bytes']:
            continue
        if sample.get('scope') == 'logical' and sample.get('identity'):
            identity = sample['identity']
            _, covered = logical.setdefault(identity, (pair, set()))
            if row.get('storage_kind') == 'storage_cluster':
                covered.update(sample.get('covered_identities', ()))
        else:
            unverified += 1
    # Only an explicit claim from a verified shared-storage observation suppresses a child.
    # Reciprocal claims are ambiguous, so use a stable tie break when their sets coincide.
    selected = []
    claimed = set()
    for identity, (pair, covered) in sorted(logical.items(), key=lambda item:(-len(item[1][1]),item[0])):
        if identity in claimed:
            continue
        if covered & claimed:
            unverified += 1
            continue
        selected.append(pair)
        claimed.add(identity)
        claimed.update(covered)
    pairs = selected
    return {**capacity(sum(pair['used_bytes'] for pair in pairs) if pairs else None,
                       sum(pair['total_bytes'] for pair in pairs) if pairs else None,
                       len(pairs),len(rows)), 'unverified':unverified}


def summarize_resources(rows, *, overview=False):
    storage = [row for row in rows if row.get('storage_kind')]
    compute = [dict(row,scope=row.get('scope') or 'host') for row in rows if not row.get('storage_kind')]
    scopes = {scope:aggregate_scope(compute,scope) for scope in ('host','container')}
    gpus, gpu_total = machine_gpu_readings(compute)
    gpu_values = [gpu['utilization_percent'] for gpu in gpus.values() if 'utilization_percent' in gpu]
    power = gpu_power_total(gpus,'power_w',gpu_total)
    machine = dict(aggregate_cpu_memory((row['machine_metrics'] for row in compute), len(compute)),
                   devices=len(compute), power=power,
                   gpu=metric(sum(gpu_values)/len(gpu_values) if gpu_values else None,len(gpu_values),gpu_total))
    result = {**scopes, 'machine':machine, 'storage':aggregate_storage(storage), 'visible_gpu':len(gpus),
              'gpu_power':power,
              'online':sum(row.get('status') in ('normal','warning') for row in rows), 'registered':len(rows)}
    if overview:
        result['gpu_rated_power'] = gpu_power_total(gpus,'default_power_limit_w',len(gpus))
    return result


def group_history_data(groups, defaults, ticks, start, now, selected_metric, sources, *, machine_view=False):
    """Build fixed slots using the latest stored observation in each slot."""
    slots = (now-start)//GROUP_BUCKET_MS
    series = []
    groups_by_resource = defaultdict(set)
    for index, group in enumerate(groups):
        scopes = ('storage',) if selected_metric == 'storage' else ('machine',) if machine_view else ('host','container')
        for scope in scopes:
            if scope == 'container' and not any(
                defaults[source].get('scope') == scope or
                any(row.get('scope') == scope for row in ticks.get(source, {}).values())
                for key in group['keys']
                for source in sources[key]
            ):
                continue
            series.append({'group':group['id'],'name':group['name'],'scope':scope,'index':index})
        for key in group['keys']:
            groups_by_resource[key].add(index)
    points = []
    for slot in range(slots):
        point_at = start+(slot+1)*GROUP_BUCKET_MS
        rows = [[] for _ in groups]
        for key, memberships in groups_by_resource.items():
            candidates = [{**defaults[source], **ticks.get(source, {}).get(slot, {})} for source in sources[key]]
            row = dict(preferred_observation(candidates))
            if not row.get('storage_kind'):
                row['machine_metrics'] = machine_resource_metrics(candidates)
            if len(candidates) > 1:
                row['_gpu_sources'] = candidates
                row['expected_gpu_count'] = max(item.get('expected_gpu_count') or 0 for item in candidates)
            # Do not use an already stale value from an adapter response.
            if row.get('storage_observation') and row['observed_at']-row['storage_observation']['observed_at'] >= row['stale_ms']:
                row['storage_observation'] = None
            for index in memberships:
                rows[index].append(row)
        summaries = [summarize_resources(group) for group in rows]
        values, coverage = [], []
        for item in series:
            scope = item['scope']
            summary = summaries[item['index']][scope]
            reading = summary if scope == 'storage' else summary[selected_metric]
            values.append(reading.get('value',reading.get('percent')))
            coverage.append([reading['valid'],reading['total']])
        points.append({'time':point_at,'values':values,'coverage':coverage,
                       'breaks':[value is None for value in values]})
    return {'from':start,'to':now,'bucket_ms':GROUP_BUCKET_MS,'keys':[selected_metric]*len(series),
            'series':[{key:value for key,value in item.items() if key != 'index'} for item in series],
            'membership':'current','points':points}
