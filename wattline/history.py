from contextlib import closing, contextmanager
import fcntl
from heapq import merge
from itertools import groupby
import json
import math
import sqlite3

from .groups import GROUP_BUCKET_MS, compute_key, storage_key, unlink_resource, write_room_link
from .history_cold import export_cold, prune_cold, sync_directory
from .history_schema import pack_batch, prepare_schema
from .machine_views import SCOPED_METRICS, SourceObservation
from .resources import (
    ACTIVE, RETENTION_MS, StorageSettings, alert_view, close_alerts, storage_tick,
    update_alerts, write_resource_users,
)

DAY_MS = 24 * 60 * 60 * 1000
WARM_HOURS = 7 * 24
WARM_MS = 7 * DAY_MS
MAX_POINTS = 400
HOST_METRICS = {'cpu':'cpu_percent', 'memory':'memory_percent', 'memory_used':'memory.used_bytes',
                'gpu':'gpu_percent', 'power':'gpu_power_w'}
OVERVIEW_METRICS = ('gpu', 'cpu', 'memory', 'power')
GPU_METRICS = {'gpu':'utilization_percent', 'power':'power_w', 'vram':'memory_used_mib', 'temp':'temperature_c'}
HOST_FIELDS = ('cpu_count','cpu_percent','load_average','memory','memory_percent','root_disk',
               'uptime_seconds','gpu_percent','gpu_util_count','gpu_power_w','gpu_inventory_complete','driver_version',
               'gpu_power_kind','gpu_generation','scope','gpu_inventory_empty')
GPU_FIELDS = ('uuid','index','name','bus_id','utilization_percent','memory_used_mib','memory_total_mib',
              'temperature_c','power_w','power_kind','power_limit_w','state','process_visibility')


class HistoryInUse(RuntimeError):
    pass


class History:
    def __init__(self, directory):
        self.directory = directory
        self.path = directory/'metrics.sqlite3'
        self.cold_directory = directory/'cold'
        self.lock = None

    @contextmanager
    def connect(self, read=False):
        target = self.path.resolve().as_uri() + '?mode=ro' if read else self.path
        with closing(sqlite3.connect(target, uri=read, timeout=2)) as connection:
            if not read:
                connection.execute('PRAGMA foreign_keys=ON')
            with connection:
                if read:
                    connection.execute('BEGIN')
                yield connection

    def prepare(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.lock is None:
            handle = (self.directory/'monitor.lock').open('a+')
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                handle.close()
                raise HistoryInUse('此数据目录已有监控服务写入') from error
            except OSError:
                handle.close()
                raise
            self.lock = handle
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            prepare_schema(db)
            return dict(db.execute('SELECT machine,alias FROM machine_aliases'))

    def set_alias(self, machine, alias):
        with self.connect() as db:
            self.write_alias(db, machine, alias)

    @staticmethod
    def write_alias(db, machine, alias):
        if alias is None:
            db.execute('DELETE FROM machine_aliases WHERE machine=?', (machine,))
        else:
            db.execute("""
                INSERT INTO machine_aliases(machine,alias) VALUES (?,?)
                ON CONFLICT(machine) DO UPDATE SET alias=excluded.alias
                """, (machine, alias))

    def machine_settings(self):
        with self.connect(read=True) as db:
            return db.execute('SELECT machine,registration,settings FROM machine_settings').fetchall()

    def people_and_assignees(self):
        with self.connect(read=True) as db:
            people = dict(db.execute('SELECT id,name FROM people'))
            rows = db.execute('SELECT machine,person FROM machine_assignees ORDER BY machine,person')
            assignees = {machine: tuple(person for _, person in entries)
                         for machine, entries in groupby(rows, key=lambda row: row[0])}
            return people, assignees

    def save_person(self, person, name):
        with self.connect() as db:
            if person is None:
                return db.execute('INSERT INTO people(name) VALUES (?)', (name,)).lastrowid
            db.execute('UPDATE people SET name=? WHERE id=?', (name, person))
            return person

    def delete_person(self, person):
        with self.connect() as db:
            db.execute('DELETE FROM people WHERE id=?', (person,))

    def save_assignees(self, identity, people, shared=False):
        with self.connect() as db:
            write_resource_users(db, identity, people, shared)

    def load_resources(self):
        with self.connect(read=True) as db:
            shared = {key for (key,) in db.execute('SELECT resource FROM shared_users')}
            storage = {key: StorageSettings.model_validate_json(settings)
                       for key, settings in db.execute('SELECT id,settings FROM storage_resources ORDER BY id')}
        return shared, storage

    def save_storage(self, id, settings, assignment, closure=None, location=None):
        with self.connect() as db:
            db.execute("""INSERT INTO storage_resources VALUES (?,?)
                          ON CONFLICT(id) DO UPDATE SET settings=excluded.settings""",
                       (id, settings.model_dump_json(exclude={'person_id', 'shared', 'room_id'})))
            if assignment is not None:
                write_resource_users(db, id, *assignment)
            if closure:
                close_alerts(db, id, *closure)
            if location is not None:
                write_room_link(db, storage_key(id), location)

    def remove_storage(self, id, at):
        with self.connect() as db:
            write_resource_users(db, id, (), False)
            unlink_resource(db, storage_key(id))
            db.execute('DELETE FROM storage_resources WHERE id=?', (id,))
            close_alerts(db, id, at, 'removed')

    def append_storage(self, id, at, status, observation, event=None):
        with self.connect() as db:
            inserted = db.execute('INSERT OR IGNORE INTO storage_ticks VALUES (?,?,?,?)',
                                  (id, at, status, observation.model_dump_json() if observation else None)).rowcount
            if inserted and event:
                update_alerts(db, *event)

    def storage_success_times(self, now):
        with self.connect(read=True) as db:
            return dict(db.execute("""
                SELECT s.id,(SELECT json_extract(t.observation,'$.observed_at')
                    FROM storage_ticks t WHERE t.resource=s.id AND t.at<=? AND t.observation IS NOT NULL
                    ORDER BY t.at DESC LIMIT 1)
                FROM storage_resources s
            """, (now,)))

    def storage_history(self, id, start, now):
        with self.connect(read=True) as db:
            return storage_tick(db.execute("""SELECT at,status,observation FROM storage_ticks
                WHERE resource=? AND at BETWEEN ? AND ? ORDER BY at""", (id, start, now)))

    def alert_events(self, active=False, limit=200, offset=0):
        with self.connect(read=True) as db:
            db.row_factory = sqlite3.Row
            where = f'WHERE {ACTIVE}' if active else ''
            count = db.execute(f'SELECT count(*) FROM alerts {where}').fetchone()[0]
            priority = "CASE severity WHEN 'critical' THEN 0 ELSE 1 END," if active else ''
            rows = db.execute(f'SELECT * FROM alerts {where} ORDER BY {priority}last_at DESC,id DESC LIMIT ? OFFSET ?',
                              (limit, offset))
            result = {'total':count,'events':[alert_view(row) for row in rows]}
            if active:
                result['by_resource'] = dict(db.execute(f'SELECT resource,count(*) FROM alerts WHERE {ACTIVE} GROUP BY resource'))
            return result

    def alert_event(self, id):
        with self.connect(read=True) as db:
            db.row_factory = sqlite3.Row
            row = db.execute('SELECT * FROM alerts WHERE id=?', (id,)).fetchone()
            if row is None:
                raise KeyError(id)
            return alert_view(row)

    def record_stale_alert(self, key, storage, observed_at, event):
        with self.connect() as db:
            if storage:
                latest = db.execute('SELECT max(at) FROM storage_ticks WHERE resource=?', (key,)).fetchone()[0]
            else:
                latest = db.execute('SELECT max(at) FROM host_ticks WHERE machine=?', (key,)).fetchone()[0]
            if latest is not None and latest <= observed_at:
                update_alerts(db, *event)

    def close_inactive_alerts(self, active_ids, registered_ids, at):
        with self.connect() as db:
            for (id,) in db.execute(f'SELECT DISTINCT resource FROM alerts WHERE {ACTIVE}').fetchall():
                if id not in active_ids:
                    close_alerts(db, id, at, 'disabled' if id in registered_ids else 'removed')

    def ssh_pins(self):
        with self.connect(read=True) as db:
            return dict(db.execute('SELECT machine,fingerprint FROM machine_ssh_pins'))

    def machine_order(self):
        with self.connect(read=True) as db:
            return dict(db.execute('SELECT machine,position FROM machine_order'))

    def save_machine_order(self, order):
        with self.connect() as db:
            self.write_order(db, order)

    @staticmethod
    def write_order(db, order):
        db.execute('DELETE FROM machine_order')
        db.executemany('INSERT INTO machine_order VALUES (?,?)', order.items())

    def save_machine(self, identity, registration, settings, alias, new_pins, order=None,
                     assignment=None, closure=None, location=None):
        with self.connect() as db:
            values = json.loads(settings)
            omitted = {'idle_memory_tolerance_mib', 'configuration_cluster_id'} - values.keys()
            if omitted:
                # Preserve omitted settings, including an explicitly stored null.
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT settings FROM machine_settings WHERE machine=?', (identity,)).fetchone()
                previous = json.loads(row[0]) if row else {}
                values.update({field:previous[field] for field in omitted if field in previous})
                settings = json.dumps(values)
            db.execute("""
                INSERT INTO machine_settings(machine,registration,settings) VALUES (?,?,?)
                ON CONFLICT(machine) DO UPDATE SET settings=excluded.settings
                """, (identity, registration, settings))
            self.write_alias(db, identity, alias)
            db.executemany('INSERT INTO machine_ssh_pins VALUES (?,?)', new_pins.items())
            if order is not None:
                self.write_order(db, order)
            if assignment is not None:
                write_resource_users(db, identity, *assignment)
            if closure:
                close_alerts(db, *closure)
            if location is not None:
                write_room_link(db, compute_key(identity), location)

    def load_groups(self):
        with self.connect(read=True) as db:
            db.row_factory = sqlite3.Row
            rooms = {row['id']:dict(row) for row in db.execute(
                'SELECT id,name,location,owner AS owner_id,idle_memory_tolerance_mib FROM rooms ORDER BY name')}
            clusters = {row['id']:dict(row, keys=()) for row in db.execute(
                'SELECT id,name,person AS person_id,shared,idle_memory_tolerance_mib FROM clusters ORDER BY name')}
            members = db.execute('SELECT cluster,resource FROM cluster_resources ORDER BY cluster,resource')
            for id, resources in groupby(members, key=lambda row:row['cluster']):
                clusters[id]['keys'] = tuple(row['resource'] for row in resources)
            locations = dict(db.execute('SELECT resource,room FROM resource_rooms'))
            order = dict(db.execute('SELECT resource,position FROM resource_order'))
        return rooms, clusters, locations, order

    def save_room(self, id, room):
        with self.connect() as db:
            db.execute("""INSERT INTO rooms(id,name,location,owner,idle_memory_tolerance_mib)
                          VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                          name=excluded.name,location=excluded.location,owner=excluded.owner,
                          idle_memory_tolerance_mib=CASE WHEN ? THEN excluded.idle_memory_tolerance_mib
                                                        ELSE rooms.idle_memory_tolerance_mib END""",
                       (id,room.name,room.location,room.owner_id,room.idle_memory_tolerance_mib,
                        'idle_memory_tolerance_mib' in room.model_fields_set))

    def save_cluster(self, id, cluster, keys):
        with self.connect() as db:
            db.execute("""INSERT INTO clusters(id,name,person,shared,idle_memory_tolerance_mib)
                          VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                          name=excluded.name,person=excluded.person,shared=excluded.shared,
                          idle_memory_tolerance_mib=CASE WHEN ? THEN excluded.idle_memory_tolerance_mib
                                                        ELSE clusters.idle_memory_tolerance_mib END""",
                       (id,cluster.name,cluster.person_id,cluster.shared,cluster.idle_memory_tolerance_mib,
                        'idle_memory_tolerance_mib' in cluster.model_fields_set))
            db.execute('DELETE FROM cluster_resources WHERE cluster=?', (id,))
            db.executemany('INSERT INTO cluster_resources VALUES (?,?)', ((id,key) for key in keys))

    def global_idle_tolerance(self):
        with self.connect(read=True) as db:
            return db.execute('SELECT idle_memory_tolerance_mib FROM global_configuration WHERE id=1').fetchone()[0]

    def save_global_idle_tolerance(self, value):
        with self.connect() as db:
            db.execute('UPDATE global_configuration SET idle_memory_tolerance_mib=? WHERE id=1', (value,))

    def delete_group(self, kind, id):
        table = 'rooms' if kind == 'room' else 'clusters'
        with self.connect() as db:
            db.execute(f'DELETE FROM {table} WHERE id=?', (id,))

    def save_resource_location(self, key, assignment):
        with self.connect() as db:
            write_room_link(db, key, assignment)

    def save_resource_order(self, order, machines):
        with self.connect() as db:
            db.execute('DELETE FROM resource_order')
            db.executemany('INSERT INTO resource_order VALUES (?,?)', order.items())
            self.write_order(db, machines)

    def removal_state(self):
        with self.connect(read=True) as db:
            static = {key for (key,) in db.execute('SELECT machine FROM removed_config_machines')}
            pending = {key for (key,) in db.execute('SELECT machine FROM pending_machine_removals')}
            return static, pending

    def begin_machine_removal(self, identity, from_config, resource=None, at=None):
        with self.connect() as db:
            db.execute('PRAGMA secure_delete=ON')
            db.execute('DELETE FROM shared_users WHERE resource=?', (identity,))
            unlink_resource(db, compute_key(identity))
            if resource is not None:
                close_alerts(db, resource, at, 'removed')
            db.execute('INSERT INTO pending_machine_removals VALUES (?)', (identity,))
            if from_config:
                db.execute('INSERT OR IGNORE INTO removed_config_machines VALUES (?)', (identity,))
            for table in ('machine_settings','machine_aliases','machine_ssh_pins','machine_order',
                          'machine_assignees','machine_observations','host_ticks'):
                db.execute(f'DELETE FROM {table} WHERE machine=?', (identity,))
            catalog = db.execute('SELECT id FROM history_machines WHERE identity=?',(identity,)).fetchone()
            if catalog:
                db.execute('DELETE FROM warm_host_ticks WHERE machine=?', catalog)
                db.execute('DELETE FROM history_devices WHERE machine=?', catalog)
                db.execute('DELETE FROM history_machines WHERE id=?', catalog)
                db.execute('DELETE FROM gpu_descriptors WHERE id NOT IN (SELECT DISTINCT descriptor FROM warm_gpu_ticks)')
                db.execute('DELETE FROM gpu_generations WHERE id NOT IN '
                           '(SELECT DISTINCT generation FROM warm_host_ticks WHERE generation IS NOT NULL)')

    def purge_machine_archives(self, identity):
        with self.connect(read=True) as db:
            indexed = {key for (key,) in db.execute('SELECT filename FROM cold_archives')}
        # Archive export and removal are serialized, so these are abandoned staging files.
        for pattern in ('.archive-*', '.purge-*'):
            for stage in self.cold_directory.glob(pattern):
                stage.unlink()
        files = indexed | {path.name for path in self.cold_directory.glob('before-*.jsonl.gz')}
        result = {}
        for name in sorted(files):
            if not name.startswith('before-') or '/' in name or not name.endswith('.jsonl.gz'):
                raise ValueError('无效的冷归档文件名')
            archive = prune_cold(self.cold_directory/name, identity)
            if name in indexed:
                result[name] = archive
        if self.cold_directory.is_dir():
            sync_directory(self.cold_directory)
        return result

    def finish_machine_removal(self, identity, archives):
        with self.connect() as db:
            for filename, archive in archives.items():
                if archive is None:
                    db.execute('DELETE FROM cold_archives WHERE filename=?', (filename,))
                else:
                    db.execute('UPDATE cold_archives SET host_count=?,gpu_count=?,file_bytes=? WHERE filename=?',
                               (archive.hosts, archive.gpus, archive.size, filename))
            db.execute('DELETE FROM pending_machine_removals WHERE machine=?', (identity,))

    def close(self):
        if self.lock:
            self.lock.close()
            self.lock = None

    def source_observations(self, machines, now):
        observations = {}
        seeded = []
        with self.connect() as db:
            persisted = {key:(boot, scope, container, at) for key, boot, scope, container, at in
                         db.execute('SELECT machine,boot,scope,container_id,at FROM machine_observations')}
            for key in machines:
                row = persisted.get(key)
                if row is None:
                    # Older databases already recorded accepted boot and scope with their samples.
                    row = db.execute("""
                        SELECT boot,scope,NULL,at FROM (
                            SELECT boot,json_extract(metrics,'$.scope') AS scope,at FROM host_ticks
                            WHERE machine=? AND status IN ('normal','warning') AND at BETWEEN ? AND ?
                            UNION ALL
                            SELECT h.boot,json_extract(h.metrics,'$.scope'),h.at FROM warm_host_ticks h
                            JOIN history_machines m ON m.id=h.machine
                            WHERE m.identity=? AND h.status IN ('normal','warning') AND h.at BETWEEN ? AND ?
                        ) WHERE boot IS NOT NULL ORDER BY at DESC LIMIT 1
                        """, (key,now-WARM_MS,now,key,now-WARM_MS,now)).fetchone()
                if row is not None and row[3] <= now:
                    observation = observations[key] = SourceObservation.from_sample(*row)
                    if key not in persisted:
                        seeded.append((key,observation.boot,observation.scope,observation.container_id,observation.at))
            db.executemany('INSERT OR IGNORE INTO machine_observations VALUES (?,?,?,?,?)', seeded)
        return observations

    def append(self, machine, epoch, snapshot):
        metrics = snapshot.get('metrics') or {}
        devices = metrics.get('gpus', [])
        fields = {key:metrics[key] for key in HOST_FIELDS if key in metrics}
        if 'stale_ms' in snapshot:
            fields['stale_ms'] = snapshot['stale_ms']
        packed = json.dumps(fields, allow_nan=False)
        with self.connect() as db:
            inserted = db.execute('INSERT OR IGNORE INTO host_ticks VALUES (?,?,?,?,?,?,?,?,?)', (
                machine, snapshot['observed_at'], snapshot['received_at'], snapshot.get('source_at'),
                snapshot['source'], snapshot.get('boot'), epoch, snapshot['status'], packed,
            )).rowcount
            if not inserted:
                return
            if observation := snapshot.get('source_observation'):
                db.execute("""
                    INSERT INTO machine_observations VALUES (?,?,?,?,?)
                    ON CONFLICT(machine) DO UPDATE SET boot=excluded.boot,scope=excluded.scope,
                      container_id=excluded.container_id,at=excluded.at
                    WHERE excluded.at > machine_observations.at
                    """, (machine,observation.boot,observation.scope,observation.container_id,observation.at))
            db.executemany('INSERT OR IGNORE INTO gpu_ticks VALUES (?,?,?,?)', [
                (machine, snapshot['observed_at'], gpu['uuid'],
                 json.dumps({key:gpu[key] for key in GPU_FIELDS if key in gpu}, allow_nan=False))
                for gpu in devices
            ])
            if event := snapshot.get('alert_event'):
                latest = db.execute('SELECT max(at) FROM host_ticks WHERE machine=?', (machine,)).fetchone()[0]
                if latest == snapshot['observed_at']:
                    update_alerts(db, *event)

    def begin_archive(self, due):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM alerts WHERE coalesce(recovered_at,closed_at)<?', (due-RETENTION_MS,))
            db.execute('DELETE FROM storage_ticks WHERE at<?', (due-WARM_MS,))
            completed, running = db.execute(
                'SELECT completed_at,running_at FROM history_maintenance WHERE id=1').fetchone()
            if running is not None:
                return running
            if completed is not None and completed >= due:
                return None
            db.execute('UPDATE history_maintenance SET running_at=? WHERE id=1', (due,))
            return due

    def pack(self, cutoff, limit=512):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            return pack_batch(db, cutoff, limit)

    def export(self, cutoff):
        with self.connect(read=True) as db:
            return export_cold(db, cutoff, self.cold_directory)

    def published_archives(self):
        with self.connect(read=True) as db:
            names = [name for (name,) in db.execute('SELECT filename FROM cold_archives ORDER BY cutoff')]
        files = []
        for name in names:
            if not name.startswith('before-') or '/' in name or not name.endswith('.jsonl.gz'):
                raise ValueError('无效的冷归档文件名')
            path = self.cold_directory/name
            files.append((path, path.stat().st_size))
        return files

    def finish_archive(self, slot, cutoff, exported):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            running, = db.execute('SELECT running_at FROM history_maintenance WHERE id=1').fetchone()
            if running != slot:
                raise sqlite3.DatabaseError('冷归档任务标记变化')
            host_count = db.execute('SELECT COUNT(*) FROM warm_host_ticks WHERE at<?', (cutoff,)).fetchone()[0]
            if exported:
                if (self.cold_directory/exported.filename).stat().st_size != exported.size:
                    raise OSError('冷归档文件大小变化')
                gpu_count = db.execute("""
                    SELECT COUNT(*) FROM warm_host_ticks h JOIN warm_gpu_ticks g
                    ON h.machine=g.machine AND h.at=g.at WHERE h.at<?
                    """, (cutoff,)).fetchone()[0]
                if (host_count,gpu_count) != (exported.hosts,exported.gpus):
                    raise sqlite3.DatabaseError('冷归档记录数与待删除数据不符')
                db.execute('INSERT INTO cold_archives VALUES (?,?,?,?,?)',
                           (cutoff,exported.filename,exported.hosts,exported.gpus,exported.size))
                db.execute('DELETE FROM warm_host_ticks WHERE at<?', (cutoff,))
            elif host_count:
                raise sqlite3.DatabaseError('未生成冷归档文件')
            db.execute('UPDATE history_maintenance SET completed_at=?,running_at=NULL WHERE id=1', (slot,))

    def inventory(self, machine, now, track_empty=False):
        with self.connect(read=True) as db:
            since = now-WARM_MS
            last, scope, complete = self.latest_host(db, 'host_ticks', machine, since, now)
            catalog = db.execute('SELECT id FROM history_machines WHERE identity=?', (machine,)).fetchone()
            if track_empty:
                empty_at = self.latest_empty(db, 'host_ticks', machine, since, now)
                if catalog:
                    empty_at = max(empty_at, self.latest_empty(db, 'warm_host_ticks', *catalog, since, now))
                since = max(since, empty_at)
            newest = db.execute('SELECT MAX(at) FROM gpu_ticks WHERE machine=? AND at BETWEEN ? AND ?',
                                (machine, since, now)).fetchone()[0]
            if catalog:
                warm_last, warm_scope, warm_complete = self.latest_host(db, 'warm_host_ticks', *catalog, since, now)
                if warm_last is not None and (last is None or warm_last > last):
                    last, scope, complete = warm_last, warm_scope, warm_complete
                if track_empty and last == empty_at:
                    return last, [], scope, True
                warm_newest = db.execute('SELECT MAX(at) FROM warm_gpu_ticks WHERE machine=? AND at BETWEEN ? AND ?',
                                         (*catalog,since,now)).fetchone()[0]
                if warm_newest is not None and (newest is None or warm_newest > newest):
                    rows = db.execute("""
                        SELECT d.uuid,k.details FROM warm_gpu_ticks g JOIN history_devices d ON d.id=g.device
                        JOIN gpu_descriptors k ON k.id=g.descriptor WHERE g.machine=? AND g.at=?
                        ORDER BY json_extract(k.details,'$.index')
                        """, (*catalog,warm_newest))
                    devices = [{'uuid':uuid,**json.loads(details)} for uuid,details in rows]
                    return last, devices, scope, self.inventory_complete(complete, last, warm_newest)
            if track_empty and last == empty_at:
                return last, [], scope, True
            rows = db.execute(
                """SELECT metrics FROM gpu_ticks WHERE machine=? AND at=?
                   ORDER BY json_extract(metrics, '$.index')""", (machine, newest))
            return last, [json.loads(row[0]) for row in rows], scope, self.inventory_complete(complete, last, newest)

    @staticmethod
    def latest_empty(db, table, machine, since, now):
        return db.execute(f"""
            SELECT MAX(at) FROM {table} WHERE machine=? AND at BETWEEN ? AND ?
            AND json_type(metrics,'$.gpu_inventory_empty')='true'
            """, (machine,since,now)).fetchone()[0] or since-1

    @staticmethod
    def inventory_complete(complete, sample_at, devices_at):
        # A positive result only certifies the device list from the same sample.
        if complete == 'false':
            return False
        if complete == 'true' and sample_at == devices_at:
            return True
        return None

    @staticmethod
    def latest_host(db, table, machine, since, now):
        return db.execute(f"""
            SELECT at,json_extract(metrics,'$.scope'),json_type(metrics,'$.gpu_inventory_complete') FROM {table}
            WHERE machine=? AND at BETWEEN ? AND ? AND boot IS NOT NULL ORDER BY at DESC LIMIT 1
            """, (machine,since,now)).fetchone() or (None, None, None)

    def series(self, machines, machine, gpu, metric, hours, now, period, stale, *, projections=None, scope=None):
        window = hours * 3600000
        start = now-window
        projections = projections or {}
        if machine is None:
            bucket = max(period, math.ceil(window/MAX_POINTS))
            points = self.overview(machines, metric, start, now, bucket, stale, projections)
            return {'from':start,'to':now,'bucket_ms':bucket,'keys':[metric],
                    'machines':list(machines),'points':points,'gap_ms':max(stale, bucket*1.5)}
        bucket = math.ceil(window/MAX_POINTS) if window/period >= MAX_POINTS else 0
        sources, scope = projections.get(machine, (((machine,None),),scope))
        if len(sources) > 1:
            bucket = max(period, math.ceil(window/MAX_POINTS))
        with self.connect(read=True) as db:
            points = self.projected_series(db, sources, gpu, metric, start, now, bucket, stale, hours > 24, scope)
        result = {'from':start,'to':now,'bucket_ms':bucket,'keys':[metric],'points':points,
                  'gap_ms':max(stale, bucket*1.5)}
        if scope:
            result['scope'] = scope
        return result

    def overview(self, machines, metric, start, now, bucket, stale, projections):
        if not machines:
            return []
        with self.connect(read=True) as db:
            columns = []
            for machine in machines:
                sources, scope = projections.get(machine, (((machine,None),),None))
                columns.append(self.projected_series(db, sources, None, metric, start, now, bucket, stale, False, scope))
        indexed = []
        for points in columns:
            indexed.append({(point['time']-start)//bucket:point for point in points})
        populated = [index for column in indexed for index in column]
        if not populated:
            return []
        result = []
        for index in range(min(populated), max(populated)+1):
            values, breaks, valid = [], [], []
            samples = 0
            for column in indexed:
                point = column.get(index)
                values.append(point['values'][0] if point else None)
                # An alignment slot has no observation. Continuity is decided by the machine series.
                breaks.append(point['breaks'][0] if point else False)
                valid.append(point['valid'][0] if point else 0)
                samples += point['samples'] if point else 0
            result.append({'time':start+index*bucket,'values':values,'breaks':breaks,
                           'valid':valid,'samples':samples})
        return result

    def group_ticks(self, keys, start, now, boots=None):
        ticks = {}
        boots = boots or {}
        slots = (now-start)//GROUP_BUCKET_MS
        with self.connect(read=True) as db:
            for key in keys:
                kind, _, identity = key.partition(':')
                by_slot = {}
                if kind == 'storage':
                    rows = db.execute("""
                        SELECT at,status,observation FROM storage_ticks
                        WHERE resource=? AND at IN (
                            SELECT max(at) FROM storage_ticks WHERE resource=? AND at BETWEEN ? AND ?
                            GROUP BY min((at-?)/?,?))
                        ORDER BY at
                        """, (identity,identity,start,now,start,GROUP_BUCKET_MS,slots-1))
                    for row in storage_tick(rows):
                        at = row['observed_at']
                        by_slot[min((at-start)//GROUP_BUCKET_MS,slots-1)] = {
                            'observed_at':at,'status':row['status'],'storage_observation':row['observation'],
                        }
                else:
                    for warm in (True,False):
                        for at, status, metrics, gpus in self.group_compute_ticks(
                            db, identity, start, now, slots, warm, boots.get(key),
                        ):
                            slot = min((at-start)//GROUP_BUCKET_MS,slots-1)
                            if at < by_slot.get(slot, {}).get('observed_at', -1):
                                continue
                            parsed = json.loads(metrics)
                            parsed['gpus'] = json.loads(gpus)
                            by_slot[slot] = {'observed_at':at,'status':status,
                                             'metrics':parsed if status in ('warning','normal') else None}
                            if parsed.get('scope') in ('host','container'):
                                by_slot[slot]['scope'] = parsed['scope']
                ticks[key] = by_slot
        return ticks

    @staticmethod
    def group_compute_ticks(db, identity, start, now, slots, warm, boot):
        # Select one host tick per slot before reading card observations.
        if warm:
            machine = db.execute('SELECT id FROM history_machines WHERE identity=?', (identity,)).fetchone()
            if not machine:
                return ()
            identity = machine[0]
            table = 'warm_host_ticks'
            gpu_query = """SELECT json_group_array(json_object('uuid',d.uuid,'utilization_percent',g.utilization_percent,
                               'power_w',g.power_w)) FROM warm_gpu_ticks g JOIN history_devices d ON d.id=g.device
                           WHERE g.machine=h.machine AND g.at=h.at"""
        else:
            table = 'host_ticks'
            gpu_query = """SELECT json_group_array(json(metrics)) FROM gpu_ticks g
                           WHERE g.machine=h.machine AND g.at=h.at"""
        return db.execute(f"""
            SELECT h.at,h.status,h.metrics,({gpu_query})
            FROM {table} h WHERE h.machine=? AND h.at IN (
                SELECT max(at) FROM {table} WHERE machine=? AND at BETWEEN ? AND ?
                AND (? IS NULL OR boot=? OR (boot IS NULL AND status NOT IN ('normal','warning')))
                GROUP BY min((at-?)/?,?))
            ORDER BY h.at
        """, (identity,identity,start,now,boot,boot,start,GROUP_BUCKET_MS,slots-1))

    def projected_series(self, db, sources, gpu, metric, start, now, bucket, stale, include_warm, scope):
        columns = [self.machine_series_in(db, machine, gpu, metric, start, now, bucket, stale,
                                          include_warm, boot=boot, scope=scope)
                   for machine,boot in sources]
        return combine_source_points(columns, start, bucket, stale) if len(columns) > 1 else columns[0]

    def machine_series_in(self, db, machine, gpu, metric, start, now, bucket, stale, include_warm, *, boot, scope):
        measure_scope = scope if not gpu and metric in SCOPED_METRICS else None
        if gpu:
            rows = db.execute("""
                SELECT h.at, h.boot, h.epoch, json_extract(g.metrics, ?),
                       CASE WHEN ? THEN json_extract(g.metrics, '$.power_kind') END,
                       json_extract(h.metrics, '$.stale_ms')
                FROM host_ticks h LEFT JOIN gpu_ticks g
                  ON g.machine=h.machine AND g.at=h.at AND g.uuid=?
                WHERE h.machine=? AND h.at BETWEEN ? AND ?
                AND (? IS NULL OR h.boot=? OR (h.boot IS NULL AND h.status NOT IN ('normal','warning')))
                ORDER BY h.at
                """, ('$.'+GPU_METRICS[metric], metric == 'power', gpu, machine, start, now, boot, boot))
        else:
            rows = db.execute("""
                SELECT at, boot, epoch,
                       CASE WHEN ? IS NULL OR COALESCE(json_extract(metrics,'$.scope'),'host') = ?
                            THEN json_extract(metrics, ?) END,
                       COALESCE(json_extract(metrics,'$.scope'),'host') || ':' ||
                       CASE WHEN ? THEN COALESCE(json_extract(metrics, '$.gpu_generation'), '') || ':' ||
                            COALESCE(json_extract(metrics, '$.gpu_power_kind'), '') ELSE '' END,
                       json_extract(metrics, '$.stale_ms')
                FROM host_ticks WHERE machine=? AND at BETWEEN ? AND ?
                AND (? IS NULL OR boot=? OR (boot IS NULL AND status NOT IN ('normal','warning')))
                ORDER BY at
                """, (measure_scope,measure_scope,'$.'+HOST_METRICS[metric],metric in ('gpu','power'),
                      machine,start,now,boot,boot))
        if include_warm:
            warm = self.warm_series(db, machine, gpu, metric, start, now, boot, measure_scope)
            rows = merge(rows, warm, key=lambda row:row[0])
        return downsample(rows, start, bucket, stale)

    def warm_series(self, db, machine, gpu, metric, start, now, boot, scope):
        if gpu:
            column = GPU_METRICS[metric]
            return db.execute(f"""
                SELECT h.at,h.boot,h.epoch,g.{column},CASE WHEN ? THEN g.power_kind END,
                       json_extract(h.metrics,'$.stale_ms')
                FROM warm_host_ticks h JOIN history_machines m ON m.id=h.machine
                LEFT JOIN warm_gpu_ticks g ON g.machine=h.machine AND g.at=h.at AND g.device=(
                    SELECT id FROM history_devices WHERE machine=h.machine AND uuid=?
                )
                WHERE m.identity=? AND h.at BETWEEN ? AND ?
                AND (? IS NULL OR h.boot=? OR (h.boot IS NULL AND h.status NOT IN ('normal','warning')))
                ORDER BY h.at
                """, (metric=='power',gpu,machine,start,now,boot,boot))
        return db.execute("""
            SELECT h.at,h.boot,h.epoch,
                   CASE WHEN ? IS NULL OR COALESCE(json_extract(h.metrics,'$.scope'),'host') = ?
                        THEN json_extract(h.metrics,?) END,
                   COALESCE(json_extract(h.metrics,'$.scope'),'host') || ':' ||
                   CASE WHEN ? THEN COALESCE(k.signature,'') || ':' ||
                        COALESCE(json_extract(h.metrics,'$.gpu_power_kind'),'') ELSE '' END,
                   json_extract(h.metrics,'$.stale_ms')
            FROM warm_host_ticks h JOIN history_machines m ON m.id=h.machine
            LEFT JOIN gpu_generations k ON k.id=h.generation
            WHERE m.identity=? AND h.at BETWEEN ? AND ?
            AND (? IS NULL OR h.boot=? OR (h.boot IS NULL AND h.status NOT IN ('normal','warning')))
            ORDER BY h.at
            """, (scope,scope,'$.'+HOST_METRICS[metric],metric in ('gpu','power'),machine,start,now,boot,boot))


def combine_source_points(columns, start, bucket, stale):
    by_slot = {}
    for source, points in enumerate(columns):
        for point in points:
            slot = (point['time']-start)//bucket
            previous = by_slot.get(slot)
            # Sources are in preference order. A missing reading can yield to a valid one.
            if previous is None or (previous[1]['values'][0] is None and point['values'][0] is not None):
                by_slot[slot] = source, point
    result = []
    previous_source, previous_at = None, None
    for slot in sorted(by_slot):
        source, point = by_slot[slot]
        broken = source != previous_source or point['time']-previous_at > max(stale, bucket*1.5)
        result.append(dict(point, breaks=[point['breaks'][0] or broken]))
        previous_source = source if point['values'][0] is not None else None
        previous_at = point['time']
    return result


def downsample(rows, start, bucket, stale):
    points = []
    previous = None
    group_key = (lambda row:(row[0]-start)//bucket) if bucket else (lambda row:row[0])
    for _, rows_in_bucket in groupby(rows, group_key):
        values = []
        identities = set()
        total = 0
        gap = False
        for at, boot, epoch, value, kind, sample_stale in rows_in_bucket:
            identity = (boot, epoch, kind)
            if previous is None or previous[1] != identity or at-previous[0] > previous[2]:
                gap = True
            total += 1
            if value is not None:
                identities.add(identity)
                values.append(value)
                previous = (at, identity, sample_stale or stale)
            else:
                gap = True
                previous = None
        # A bucket crossing a boot, collector restart, or measured power mode stays a gap.
        compatible = len(identities) == 1
        points.append({'time':at, 'values':[sum(values)/len(values) if compatible else None],
                       'breaks':[gap], 'valid':[len(values) if compatible else 0], 'samples':total})
        if gap and (total != len(values) or not compatible):
            previous = None
    return points
