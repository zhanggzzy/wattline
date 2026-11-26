import asyncio
from datetime import datetime
import sqlite3
from threading import Event
from zoneinfo import ZoneInfo

from httpx import ASGITransport, AsyncClient
import pytest

from wattline import service
from wattline.app import create_app
from wattline.archive_analysis import ArchiveAnalysis
from wattline.config import Config, Machine
from wattline.history import DAY_MS, WARM_MS


ZONE = ZoneInfo('America/New_York')
ARCHIVE = '/api/machines/alpha/archive-analysis'


def millis(day, hour=0):
    return int(datetime(2026, 3, day, hour, tzinfo=ZONE).timestamp()) * 1000


def tick(history, identity, at, value, boot='boot'):
    history.append(identity, 'epoch', {'observed_at':at, 'received_at':at, 'source':'ssh', 'boot':boot,
                                      'status':'normal', 'metrics':{'cpu_percent':value}})


def publish(history, cutoff):
    slot = cutoff + WARM_MS
    assert history.begin_archive(slot) == slot
    assert history.pack(cutoff)
    exported = history.export(cutoff)
    history.finish_archive(slot, cutoff, exported)
    return history.cold_directory / exported.filename


@pytest.fixture
async def analysis(tmp_path):
    machines = tuple(Machine(id=name, mode='ssh', ssh_alias=name, expected_host_id=key * 32,
                             history_id='f' * 32 if name == 'alpha' else None, enabled=False)
                     for name, key in [('alpha','a'), ('beta','b'), ('gamma','c')])
    config = Config(machines=machines, data_dir=tmp_path, archive_timezone=ZONE.key)
    monitor = service.Monitor(config, clock=lambda: millis(20))
    await monitor.load_registry()
    try:
        app = create_app(config, monitor=monitor)
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://127.0.0.1') as client:
            yield monitor, client
    finally:
        await monitor.close()


async def start(monitor, client, machine='alpha'):
    url = f'/api/machines/{machine}/archive-analysis'
    assert (await client.post(url, json={})).status_code == 200
    return monitor.archive_analyses[monitor.machines[machine].history_key]


async def series(client, first='2026-03-08', last='2026-03-08', metric='cpu', url=ARCHIVE):
    return await client.get(url+'/series', params={'start':first, 'end':last, 'metric':metric})


async def test_archive_progress_dates_and_machine_isolation(analysis, monkeypatch):
    monitor, client = analysis
    alpha, beta, _ = monitor.config.machines
    history = monitor.history
    tick(history, alpha.history_key, millis(7, 23), 13)
    tick(history, alpha.history_key, millis(8), 21)
    tick(history, beta.history_key, millis(8), 98)
    first = publish(history, millis(8, 1))
    tick(history, alpha.history_key, millis(9)-1, 24, boot='new-boot')
    tick(history, alpha.history_key, millis(9), 37)
    # The verified host identity may differ from the persisted history key.
    tick(history, alpha.expected_host_id, millis(8, 15), 95)
    second = publish(history, millis(10))
    orphan = second.with_name('before-unpublished.jsonl.gz')
    orphan.write_bytes(b'uncommitted archive')
    original = {path:path.read_bytes() for path in (first, second, orphan)}
    tick(history, alpha.history_key, millis(20)-1000, 44)

    entered, release = Event(), Event()
    read_rows = ArchiveAnalysis.rows

    def held_rows(job, files, identity, notify):
        def progress(value):
            notify(value)
            if identity == alpha.history_key and not entered.is_set():
                entered.set()
                assert release.wait(5)
        yield from read_rows(job, files, identity, progress)

    monkeypatch.setattr(ArchiveAnalysis, 'rows', held_rows)
    assert (await client.get(ARCHIVE)).status_code == 404
    assert (await client.post(ARCHIVE, json={}, headers={'sec-fetch-site':'cross-site'})).status_code == 403
    assert (await client.post('/api/machines/unknown/archive-analysis', json={})).status_code == 404
    job = await start(monitor, client)
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        pending = (await client.get(ARCHIVE)).json()
        assert pending['status'] == 'preparing'
        assert pending['progress'] == first.stat().st_size * 100 // (first.stat().st_size + second.stat().st_size)
        assert 0 < pending['progress'] < 100
        assert await start(monitor, client) is job
        assert (await series(client)).status_code == 409
        beta_job = await start(monitor, client, 'beta')
        assert beta_job.progress == 0
        assert monitor.archive_lock.locked()
    finally:
        release.set()
    await asyncio.gather(job.task, beta_job.task)
    assert (await client.get(ARCHIVE)).json() == {
        'status':'ready', 'progress':100, 'timezone':ZONE.key,
        'first_date':'2026-03-07', 'last_date':'2026-03-09'}
    assert await start(monitor, client) is job
    data = (await series(client)).json()
    assert (data['from'], data['to']) == (millis(8), millis(9))
    assert data['to'] - data['from'] == DAY_MS - 3600000
    assert [(p['time'], p['values'], p['breaks']) for p in data['points']] == [
        (millis(8), [21], [True]), (millis(9)-1, [24], [True])]
    assert (await series(client, url='/api/machines/beta/archive-analysis')).json()['points'][0]['values'] == [98]
    assert (await series(client, '2026-03-06', '2026-03-06')).json()['points'] == []
    assert (await series(client, '2026-03-09')).status_code == 422
    assert (await series(client, metric='temp')).status_code == 422
    assert (await series(client, '2026-02-30')).status_code == 422
    recent = (await client.get('/api/history', params={'machine':'alpha','metric':'cpu','hours':168})).json()
    assert [p['values'] for p in recent['points']] == [[44]]
    empty = await start(monitor, client, 'gamma')
    await empty.task
    assert empty.status == 'empty' and empty.progress == 100 and empty.workspace is None
    assert original == {path:path.read_bytes() for path in original}


async def test_failed_gzip_closes_partial_workspace_and_can_retry(analysis, monkeypatch):
    monitor, client = analysis
    alpha = monitor.config.machines[0]
    history = monitor.history
    tick(history, alpha.history_key, millis(8), 21)
    publish(history, millis(8, 1))
    tick(history, alpha.history_key, millis(8, 2), 44)
    corrupt = publish(history, millis(9))
    original = corrupt.read_bytes()
    corrupt.write_bytes(original[:-4])
    connections = []
    connect = sqlite3.connect

    def record(path, *args, **kwargs):
        db = connect(path, *args, **kwargs)
        if path == '':
            connections.append(db)
        return db

    monkeypatch.setattr(sqlite3, 'connect', record)
    failed = await start(monitor, client)
    await failed.task
    assert (await client.get(ARCHIVE)).json()['status'] == 'failed'
    assert failed.progress < 100
    assert corrupt.read_bytes() == original[:-4]
    assert (await series(client)).status_code == 409
    abandoned, = connections
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        abandoned.execute('SELECT count(*) FROM ticks')
    corrupt.write_bytes(original)
    retried = await start(monitor, client)
    await retried.task
    assert retried is not failed and retried.status == 'ready'
    assert [p['values'] for p in (await series(client)).json()['points']] == [[21], [44]]


async def test_expiry_removal_and_shutdown_release_workspaces(analysis, monkeypatch):
    monitor, client = analysis
    alpha, beta, _ = monitor.config.machines
    history = monitor.history
    for host in (alpha, beta):
        tick(history, host.history_key, millis(8), 21)
    target = publish(history, millis(9))
    original = target.read_bytes()
    job = await start(monitor, client)
    await job.task
    db = job.workspace

    entered, release = Event(), Event()
    read_series = ArchiveAnalysis.series

    def held_series(*args):
        entered.set()
        assert release.wait(5)
        return read_series(*args)

    monkeypatch.setattr(ArchiveAnalysis, 'series', held_series)
    request = asyncio.create_task(series(client))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        monitor.expire_archive_analysis(alpha.history_key, job)
        assert monitor.archive_analyses[alpha.history_key] is job
        assert job.workspace is db
        assert target.read_bytes() == original
        response = await client.request('DELETE', '/api/machines/alpha', json={'confirm':True})
        assert response.status_code == 200
        assert target.exists() and target.read_bytes() != original
        assert (await client.get(ARCHIVE)).status_code == 404
        assert job.workspace is db
    finally:
        release.set()
    assert (await request).status_code == 409
    assert job.workspace is None
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        db.execute('SELECT count(*) FROM ticks')

    expired = await start(monitor, client, 'beta')
    await expired.task
    assert expired.workspace is not None
    assert (await series(client, url='/api/machines/beta/archive-analysis')).json()['points'][0]['values'] == [21]
    with monkeypatch.context() as timer:
        timer.setattr(service, 'ARCHIVE_ANALYSIS_IDLE_SECONDS', .05)
        monitor.keep_archive_analysis(beta.history_key, expired)
    for _ in range(100):
        if expired.workspace is None:
            break
        await asyncio.sleep(.01)
    assert expired.workspace is None
    assert (await client.get('/api/machines/beta/archive-analysis')).status_code == 404
    ready = await start(monitor, client, 'beta')
    await ready.task
    assert ready.workspace is not None
    await monitor.close()
    assert ready.workspace is None and not monitor.archive_analyses


async def test_shutdown_stops_preparation_and_preserves_archives(analysis, monkeypatch):
    monitor, client = analysis
    empty = await start(monitor, client, 'gamma')
    await empty.task
    assert empty.status == 'empty' and empty.workspace is None

    alpha = monitor.config.machines[0]
    tick(monitor.history, alpha.history_key, millis(8), 21)
    target = publish(monitor.history, millis(9))
    original = target.read_bytes()
    started = Event()
    read_rows = ArchiveAnalysis.rows

    def held_rows(job, files, identity, notify):
        def progress(value):
            notify(value)
            started.set()
            assert job.stopped.wait(5)
        yield from read_rows(job, files, identity, progress)

    monkeypatch.setattr(ArchiveAnalysis, 'rows', held_rows)
    job = await start(monitor, client)
    assert await asyncio.to_thread(started.wait, 5)
    await monitor.close()
    assert job.task.cancelled() and job.workspace is None
    assert target.read_bytes() == original
