from contextlib import closing, contextmanager
import fcntl
from heapq import merge
from itertools import groupby
import json
import math
import sqlite3

from .history_cold import export_cold, prune_cold, sync_directory
from .history_schema import pack_batch, prepare_schema

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
               'gpu_power_kind','gpu_generation','scope')
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

    def save_machine(self, identity, registration, settings, alias, new_pins, order=None):
        with self.connect() as db:
            db.execute("""
                INSERT INTO machine_settings(machine,registration,settings) VALUES (?,?,?)
                ON CONFLICT(machine) DO UPDATE SET settings=excluded.settings
                """, (identity, registration, settings))
            self.write_alias(db, identity, alias)
            db.executemany('INSERT INTO machine_ssh_pins VALUES (?,?)', new_pins.items())
            if order is not None:
                self.write_order(db, order)

    def removal_state(self):
        with self.connect(read=True) as db:
            static = {key for (key,) in db.execute('SELECT machine FROM removed_config_machines')}
            pending = {key for (key,) in db.execute('SELECT machine FROM pending_machine_removals')}
            return static, pending

    def begin_machine_removal(self, identity, from_config):
        with self.connect() as db:
            db.execute('PRAGMA secure_delete=ON')
            db.execute('INSERT INTO pending_machine_removals VALUES (?)', (identity,))
            if from_config:
                db.execute('INSERT OR IGNORE INTO removed_config_machines VALUES (?)', (identity,))
            for table in ('machine_settings','machine_aliases','machine_ssh_pins','machine_order','host_ticks'):
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
            db.executemany('INSERT OR IGNORE INTO gpu_ticks VALUES (?,?,?,?)', [
                (machine, snapshot['observed_at'], gpu['uuid'],
                 json.dumps({key:gpu[key] for key in GPU_FIELDS if key in gpu}, allow_nan=False))
                for gpu in devices
            ])

    def begin_archive(self, due):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
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

    def inventory(self, machine, now):
        with self.connect(read=True) as db:
            since = now-WARM_MS
            last, scope, complete = self.latest_host(db, 'host_ticks', machine, since, now)
            newest = db.execute('SELECT MAX(at) FROM gpu_ticks WHERE machine=? AND at BETWEEN ? AND ?',
                                (machine, since, now)).fetchone()[0]
            catalog = db.execute('SELECT id FROM history_machines WHERE identity=?', (machine,)).fetchone()
            if catalog:
                warm_last, warm_scope, warm_complete = self.latest_host(db, 'warm_host_ticks', *catalog, since, now)
                if warm_last is not None and (last is None or warm_last > last):
                    last, scope, complete = warm_last, warm_scope, warm_complete
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
            rows = db.execute(
                """SELECT metrics FROM gpu_ticks WHERE machine=? AND at=?
                   ORDER BY json_extract(metrics, '$.index')""", (machine, newest))
            return last, [json.loads(row[0]) for row in rows], scope, self.inventory_complete(complete, last, newest)

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

    def series(self, machines, machine, gpu, metric, hours, now, period, stale):
        window = hours * 3600000
        start = now-window
        if machine is None:
            bucket = max(period, math.ceil(window/MAX_POINTS))
            points = self.overview(machines, metric, start, now, bucket, stale)
            return {'from':start,'to':now,'bucket_ms':bucket,'keys':[metric],
                    'machines':list(machines),'points':points,'gap_ms':max(stale, bucket*1.5)}
        bucket = math.ceil(window/MAX_POINTS) if window/period >= MAX_POINTS else 0
        points = self.machine_series(machine, gpu, metric, start, now, bucket, stale, hours > 24)
        return {'from':start,'to':now,'bucket_ms':bucket,'keys':[metric],'points':points,
                'gap_ms':max(stale, bucket*1.5)}

    def overview(self, machines, metric, start, now, bucket, stale):
        if not machines:
            return []
        with self.connect(read=True) as db:
            columns = [self.machine_series_in(db, machine, None, metric, start, now, bucket, stale, False)
                       for machine in machines]
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

    def machine_series(self, machine, gpu, metric, start, now, bucket, stale, include_warm):
        with self.connect(read=True) as db:
            return self.machine_series_in(db, machine, gpu, metric, start, now, bucket, stale, include_warm)

    def machine_series_in(self, db, machine, gpu, metric, start, now, bucket, stale, include_warm):
        if gpu:
            rows = db.execute("""
                SELECT h.at, h.boot, h.epoch, json_extract(g.metrics, ?),
                       CASE WHEN ? THEN json_extract(g.metrics, '$.power_kind') END,
                       json_extract(h.metrics, '$.stale_ms')
                FROM host_ticks h LEFT JOIN gpu_ticks g
                  ON g.machine=h.machine AND g.at=h.at AND g.uuid=?
                WHERE h.machine=? AND h.at BETWEEN ? AND ? ORDER BY h.at
                """, ('$.'+GPU_METRICS[metric], metric == 'power', gpu, machine, start, now))
        else:
            rows = db.execute("""
                SELECT at, boot, epoch, json_extract(metrics, ?),
                       CASE WHEN ? THEN json_extract(metrics, '$.gpu_generation') || ':' ||
                            COALESCE(json_extract(metrics, '$.gpu_power_kind'), '') END,
                       json_extract(metrics, '$.stale_ms')
                FROM host_ticks WHERE machine=? AND at BETWEEN ? AND ? ORDER BY at
                """, ('$.'+HOST_METRICS[metric], metric in ('gpu','power'), machine, start, now))
        if include_warm:
            warm = self.warm_series(db, machine, gpu, metric, start, now)
            rows = merge(rows, warm, key=lambda row:row[0])
        return downsample(rows, start, bucket, stale)

    def warm_series(self, db, machine, gpu, metric, start, now):
        if gpu:
            column = GPU_METRICS[metric]
            return db.execute(f"""
                SELECT h.at,h.boot,h.epoch,g.{column},CASE WHEN ? THEN g.power_kind END,
                       json_extract(h.metrics,'$.stale_ms')
                FROM warm_host_ticks h JOIN history_machines m ON m.id=h.machine
                LEFT JOIN warm_gpu_ticks g ON g.machine=h.machine AND g.at=h.at AND g.device=(
                    SELECT id FROM history_devices WHERE machine=h.machine AND uuid=?
                )
                WHERE m.identity=? AND h.at BETWEEN ? AND ? ORDER BY h.at
                """, (metric=='power',gpu,machine,start,now))
        return db.execute("""
            SELECT h.at,h.boot,h.epoch,json_extract(h.metrics,?),
                   CASE WHEN ? THEN k.signature || ':' || COALESCE(json_extract(h.metrics,'$.gpu_power_kind'),'') END,
                   json_extract(h.metrics,'$.stale_ms')
            FROM warm_host_ticks h JOIN history_machines m ON m.id=h.machine
            LEFT JOIN gpu_generations k ON k.id=h.generation
            WHERE m.identity=? AND h.at BETWEEN ? AND ? ORDER BY h.at
            """, ('$.'+HOST_METRICS[metric],metric in ('gpu','power'),machine,start,now))


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
