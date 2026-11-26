import asyncio
from datetime import date, datetime, time, timedelta
import gzip
import json
import sqlite3
from threading import Event

from .history import HOST_METRICS, MAX_POINTS, downsample
from .history_cold import read_cold_header


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
            db.execute('CREATE TABLE ticks(at INTEGER PRIMARY KEY, boot TEXT, epoch TEXT, metrics TEXT)')
            db.executemany('INSERT OR REPLACE INTO ticks VALUES (?,?,?,?)',
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
                    if row['machine'] == identity:
                        at, metrics = row['observed_at'], row['metrics']
                        if type(at) is not int or not isinstance(metrics, dict):
                            raise ValueError('无效的冷归档样本')
                        yield at, row['boot'], row['epoch'], json.dumps(metrics, allow_nan=False)
            completed += size

    def series(self, metric, start, end, stale):
        bucket = max(1, (end - start + MAX_POINTS - 1) // MAX_POINTS)
        rows = self.workspace.execute("""
            SELECT at,boot,epoch,json_extract(metrics,?),
                   CASE WHEN ? THEN json_extract(metrics,'$.gpu_generation') || ':' ||
                        COALESCE(json_extract(metrics,'$.gpu_power_kind'),'') END,
                   json_extract(metrics,'$.stale_ms')
            FROM ticks WHERE at>=? AND at<? ORDER BY at
            """, ('$.'+HOST_METRICS[metric], metric in ('gpu','power'), start, end))
        return {'from':start, 'to':end, 'bucket_ms':bucket, 'keys':[metric],
                'points':downsample(rows, start, bucket, stale), 'gap_ms':max(stale, bucket*1.5)}

    def close(self):
        if self.workspace is not None:
            self.workspace.close()
            self.workspace = None
