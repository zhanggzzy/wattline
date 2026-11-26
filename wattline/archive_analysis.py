import asyncio
from datetime import date, datetime, time, timedelta
import gzip
import json
import sqlite3
from threading import Event

from .history import HOST_METRICS, MAX_POINTS, combine_source_points, downsample
from .history_cold import read_cold_header
from .machine_views import SCOPED_METRICS


ARCHIVE_ANALYSIS_IDLE_SECONDS = 15 * 60


def archive_bounds(first, last, zone):
    start = datetime.combine(first, time.min, zone)
    if last == date.max:
        end = int(datetime.combine(last, time(23, 59, 59), zone).timestamp()) + 1
    else:
        end = int(datetime.combine(last + timedelta(days=1), time.min, zone).timestamp())
    return int(start.timestamp()) * 1000, end * 1000


class ArchiveAnalysis:
    def __init__(self):
        self.status = 'preparing'
        self.progress = 0
        self.task = None
        self.expiry = None
        self.read_lock = asyncio.Lock()
        self.stopped = Event()
        self.workspace = None
        self.dates = None
        self.source_count = 1

    def view(self, zone):
        dates = self.dates if self.status == 'ready' else (None, None)
        return {'status':self.status, 'progress':self.progress, 'timezone':zone.key,
                'first_date':dates[0], 'last_date':dates[1]}

    def prepare(self, history, identity, zone, notify):
        files = history.published_archives()
        if not files or self.stopped.is_set():
            return
        # SQLite owns this private temporary database and deletes its file on Unix.
        db = sqlite3.connect('', check_same_thread=False)
        try:
            db.execute('PRAGMA journal_mode=OFF')
            db.execute("""CREATE TABLE ticks(
                source INTEGER, at INTEGER, boot TEXT, epoch TEXT, metrics TEXT,
                PRIMARY KEY(source,at)) WITHOUT ROWID""")
            db.executemany('INSERT OR REPLACE INTO ticks VALUES (?,?,?,?,?)',
                           self.rows(files, identity, notify))
            if self.stopped.is_set():
                return
            first, last = db.execute('SELECT min(at),max(at) FROM ticks').fetchone()
            if first is not None:
                self.dates = tuple(datetime.fromtimestamp(at / 1000, zone).date().isoformat() for at in (first, last))
                db.commit()
                self.workspace = db
        finally:
            if self.workspace is not db:
                db.close()

    def rows(self, files, identity, notify):
        sources = identity if isinstance(identity, tuple) else ((identity,None),)
        self.source_count = len(sources)
        source_map = {key:(index,boot) for index,(key,boot) in enumerate(sources)}
        total = sum(size for _, size in files)
        completed = progress = 0
        for path, size in files:
            if self.stopped.is_set():
                return
            with path.open('rb') as raw, gzip.GzipFile(fileobj=raw) as source:
                read_cold_header(source)
                for line in source:
                    if self.stopped.is_set():
                        return
                    percent = min(99, (completed + raw.tell()) * 100 // total)
                    if percent > progress:
                        progress = percent
                        notify(progress)
                    row = json.loads(line)
                    if row['machine'] in source_map:
                        index, boot = source_map[row['machine']]
                        failed = row['boot'] is None and row.get('status') not in ('normal','warning')
                        if boot is not None and row['boot'] != boot and not failed:
                            continue
                        at, metrics = row['observed_at'], row['metrics']
                        if type(at) is not int or not isinstance(metrics, dict):
                            raise ValueError('无效的冷归档样本')
                        yield index, at, row['boot'], row['epoch'], json.dumps(metrics, allow_nan=False)
            completed += size

    def series(self, metric, start, end, stale, scope=None):
        bucket = max(1, (end - start + MAX_POINTS - 1) // MAX_POINTS)
        scope = scope if metric in SCOPED_METRICS else None
        columns = []
        for source in range(self.source_count):
            rows = self.workspace.execute("""
                SELECT at,boot,epoch,
                       CASE WHEN ? IS NULL OR COALESCE(json_extract(metrics,'$.scope'),'host') = ?
                            THEN json_extract(metrics,?) END,
                       COALESCE(json_extract(metrics,'$.scope'),'host') || ':' ||
                       CASE WHEN ? THEN COALESCE(json_extract(metrics,'$.gpu_generation'),'') || ':' ||
                            COALESCE(json_extract(metrics,'$.gpu_power_kind'),'') ELSE '' END,
                       json_extract(metrics,'$.stale_ms')
                FROM ticks WHERE source=? AND at>=? AND at<? ORDER BY at
                """, (scope,scope,'$.'+HOST_METRICS[metric],metric in ('gpu','power'),source,start,end))
            columns.append(downsample(rows, start, bucket, stale))
        points = combine_source_points(columns, start, bucket, stale) if len(columns) > 1 else columns[0]
        result = {'from':start, 'to':end, 'bucket_ms':bucket, 'keys':[metric],
                  'points':points, 'gap_ms':max(stale, bucket*1.5)}
        if scope:
            result['scope'] = scope
        return result

    def close(self):
        if self.workspace is not None:
            self.workspace.close()
            self.workspace = None
