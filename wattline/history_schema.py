import json
import sqlite3

from .config import normalize_person_name


SCHEMA_VERSION = 8
GPU_DESCRIPTOR_FIELDS = ('index','name','bus_id','memory_total_mib')
GPU_SAMPLE_FIELDS = ('utilization_percent','memory_used_mib','temperature_c','power_w',
                     'power_kind','power_limit_w','state','process_visibility')

HOT_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS host_ticks (
           machine TEXT NOT NULL, at INTEGER NOT NULL, received_at INTEGER NOT NULL,
           source_at INTEGER, source TEXT NOT NULL, boot TEXT, epoch TEXT NOT NULL,
           status TEXT NOT NULL, metrics TEXT NOT NULL, PRIMARY KEY(machine, at))""",
    'CREATE INDEX IF NOT EXISTS host_ticks_at ON host_ticks(at)',
    """CREATE TABLE IF NOT EXISTS gpu_ticks (
           machine TEXT NOT NULL, at INTEGER NOT NULL, uuid TEXT NOT NULL, metrics TEXT NOT NULL,
           PRIMARY KEY(machine, at, uuid),
           FOREIGN KEY(machine, at) REFERENCES host_ticks(machine, at) ON DELETE CASCADE)""",
    'CREATE INDEX IF NOT EXISTS gpu_ticks_device ON gpu_ticks(machine, uuid, at)',
)

ARCHIVE_SCHEMA = (
    'CREATE TABLE history_machines (id INTEGER PRIMARY KEY, identity TEXT NOT NULL UNIQUE)',
    """CREATE TABLE history_devices (
           id INTEGER PRIMARY KEY, machine INTEGER NOT NULL REFERENCES history_machines(id), uuid TEXT NOT NULL,
           UNIQUE(machine, uuid))""",
    'CREATE TABLE gpu_descriptors (id INTEGER PRIMARY KEY, details TEXT NOT NULL UNIQUE)',
    'CREATE TABLE gpu_generations (id INTEGER PRIMARY KEY, signature TEXT NOT NULL UNIQUE)',
    """CREATE TABLE warm_host_ticks (
           machine INTEGER NOT NULL REFERENCES history_machines(id), at INTEGER NOT NULL, received_at INTEGER NOT NULL,
           source_at INTEGER, source TEXT NOT NULL, boot TEXT, epoch TEXT NOT NULL, status TEXT NOT NULL,
           generation INTEGER REFERENCES gpu_generations(id), metrics TEXT NOT NULL,
           PRIMARY KEY(machine, at)) WITHOUT ROWID""",
    'CREATE INDEX warm_host_ticks_at ON warm_host_ticks(at)',
    """CREATE TABLE warm_gpu_ticks (
           machine INTEGER NOT NULL, at INTEGER NOT NULL, device INTEGER NOT NULL REFERENCES history_devices(id),
           descriptor INTEGER NOT NULL REFERENCES gpu_descriptors(id),
           utilization_percent REAL, memory_used_mib REAL, temperature_c REAL, power_w REAL,
           power_kind TEXT, power_limit_w REAL, state TEXT, process_visibility TEXT,
           PRIMARY KEY(machine, at, device),
           FOREIGN KEY(machine, at) REFERENCES warm_host_ticks(machine, at) ON DELETE CASCADE) WITHOUT ROWID""",
    """CREATE TABLE history_maintenance (
           id INTEGER PRIMARY KEY CHECK(id=1), completed_at INTEGER, running_at INTEGER)""",
    'INSERT INTO history_maintenance(id) VALUES (1)',
    """CREATE TABLE cold_archives (
           cutoff INTEGER PRIMARY KEY, filename TEXT NOT NULL UNIQUE,
           host_count INTEGER NOT NULL, gpu_count INTEGER NOT NULL, file_bytes INTEGER NOT NULL)""",
)


def prepare_schema(db):
    version = db.execute('PRAGMA user_version').fetchone()[0]
    if version == SCHEMA_VERSION:
        return
    if version not in (0, 2, 3, 4, 5, 6, 7):
        raise sqlite3.DatabaseError('监控历史库版本不受支持')
    db.execute('BEGIN IMMEDIATE')
    if version == 0:
        tables = {name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and tables != {'host_ticks', 'gpu_ticks'}:
            raise sqlite3.DatabaseError('监控历史库结构无法识别')
        for statement in (*HOT_SCHEMA, *ARCHIVE_SCHEMA):
            db.execute(statement)
    if version < 3:
        db.execute('CREATE TABLE machine_aliases (machine TEXT PRIMARY KEY, alias TEXT NOT NULL) WITHOUT ROWID')
    if version < 4:
        db.execute("""CREATE TABLE machine_settings (
            machine TEXT PRIMARY KEY, registration TEXT, settings TEXT NOT NULL) WITHOUT ROWID""")
    if version < 5:
        db.execute("""CREATE TABLE machine_ssh_pins (
            machine TEXT PRIMARY KEY, fingerprint TEXT NOT NULL) WITHOUT ROWID""")
    if version < 6:
        db.execute("""CREATE TABLE machine_order (
            machine TEXT PRIMARY KEY, position INTEGER NOT NULL UNIQUE) WITHOUT ROWID""")
    if version < 7:
        db.execute('CREATE TABLE removed_config_machines (machine TEXT PRIMARY KEY) WITHOUT ROWID')
        db.execute('CREATE TABLE pending_machine_removals (machine TEXT PRIMARY KEY) WITHOUT ROWID')
    migrate_assignees(db)
    db.execute(f'PRAGMA user_version={SCHEMA_VERSION}')


def migrate_assignees(db):
    db.execute('CREATE TABLE people (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)')
    db.execute("""CREATE TABLE machine_assignees (
        machine TEXT NOT NULL, person INTEGER NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
        PRIMARY KEY(machine, person)) WITHOUT ROWID""")
    db.execute('CREATE INDEX machine_assignees_person ON machine_assignees(person)')
    names = {}
    rows = db.execute('SELECT machine,settings FROM machine_settings ORDER BY machine').fetchall()
    for identity, settings in rows:
        try:
            parsed = json.loads(settings)
            if not isinstance(parsed, dict):
                raise ValueError('旧版机器设置不是对象')
            if 'assigned_user' not in parsed:
                continue
            value = parsed.pop('assigned_user')
            name = normalize_person_name(value) if value is not None else ''
            if len(name) > 80:
                raise ValueError('旧版机器使用者名称过长')
        except (ValueError, TypeError) as error:
            raise sqlite3.DatabaseError('旧版机器使用者登记无法迁移') from error
        if name:
            if name not in names:
                names[name] = db.execute('INSERT INTO people(name) VALUES (?)', (name,)).lastrowid
            db.execute('INSERT INTO machine_assignees VALUES (?,?)', (identity, names[name]))
        db.execute('UPDATE machine_settings SET settings=? WHERE machine=?', (json.dumps(parsed), identity))


def pack_batch(db, cutoff, limit):
    db.execute("""CREATE TEMP TABLE batch (machine TEXT, at INTEGER, PRIMARY KEY(machine,at)) WITHOUT ROWID""")
    size = db.execute('INSERT INTO batch SELECT machine,at FROM host_ticks WHERE at<? ORDER BY at LIMIT ?',
                      (cutoff,limit)).rowcount
    if not size:
        return 0
    db.execute('INSERT OR IGNORE INTO history_machines(identity) SELECT DISTINCT machine FROM batch')
    db.execute("""
        INSERT OR IGNORE INTO gpu_generations(signature)
        SELECT DISTINCT json_extract(h.metrics,'$.gpu_generation') FROM batch b
        JOIN host_ticks h ON h.machine=b.machine AND h.at=b.at
        WHERE json_extract(h.metrics,'$.gpu_generation') IS NOT NULL
    """)
    descriptor = 'json_object(' + ','.join(
        f"'{field}',json_extract(g.metrics,'$.{field}')" for field in GPU_DESCRIPTOR_FIELDS
    ) + ')'
    gpu_rows = 'FROM batch b JOIN gpu_ticks g ON g.machine=b.machine AND g.at=b.at'
    db.execute(f'INSERT OR IGNORE INTO gpu_descriptors(details) SELECT DISTINCT {descriptor} {gpu_rows}')
    db.execute(f"""
        INSERT OR IGNORE INTO history_devices(machine,uuid)
        SELECT DISTINCT m.id,g.uuid {gpu_rows} JOIN history_machines m ON m.identity=b.machine
    """)
    hosts = db.execute("""
        INSERT INTO warm_host_ticks
        SELECT m.id,h.at,h.received_at,h.source_at,h.source,h.boot,h.epoch,h.status,k.id,
               json_remove(h.metrics,'$.gpu_generation')
        FROM batch b JOIN host_ticks h ON h.machine=b.machine AND h.at=b.at
        JOIN history_machines m ON m.identity=b.machine
        LEFT JOIN gpu_generations k ON k.signature=json_extract(h.metrics,'$.gpu_generation')
    """).rowcount
    fields = ','.join(f"json_extract(g.metrics,'$.{field}')" for field in GPU_SAMPLE_FIELDS)
    gpus = db.execute(f"""
        INSERT INTO warm_gpu_ticks
        SELECT m.id,g.at,d.id,k.id,{fields} {gpu_rows}
        JOIN history_machines m ON m.identity=b.machine
        JOIN history_devices d ON d.machine=m.id AND d.uuid=g.uuid
        JOIN gpu_descriptors k ON k.details={descriptor}
    """).rowcount
    if hosts != size or gpus != db.execute(f'SELECT COUNT(*) {gpu_rows}').fetchone()[0]:
        raise sqlite3.DatabaseError('温层整理前后记录数不符')
    db.execute('DELETE FROM host_ticks WHERE (machine,at) IN (SELECT machine,at FROM batch)')
    return hosts
