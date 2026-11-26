from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
from itertools import chain
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .history_schema import GPU_SAMPLE_FIELDS


@dataclass(frozen=True)
class ColdArchive:
    filename: str
    hosts: int
    gpus: int
    size: int


def encode(file, value):
    file.write(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode() + b'\n')


def sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_cold_header(source):
    header = source.readline()
    fields = json.loads(header)
    if not isinstance(fields, dict) or fields.get('format') != 'compute-monitor-history' or fields.get('version') != 1:
        raise ValueError('无法识别冷归档格式')
    return header


def export_cold(db, cutoff, directory):
    column_list = ','.join('g.'+field for field in GPU_SAMPLE_FIELDS)
    hosts = db.execute("""
        SELECT h.machine,h.at,m.identity,h.received_at,h.source_at,h.source,h.boot,h.epoch,h.status,h.metrics,k.signature
        FROM warm_host_ticks h JOIN history_machines m ON m.id=h.machine
        LEFT JOIN gpu_generations k ON k.id=h.generation
        WHERE h.at<? ORDER BY h.machine,h.at
        """, (cutoff,))
    gpus = iter(db.execute(f"""
        SELECT g.machine,g.at,d.uuid,k.details,{column_list} FROM warm_gpu_ticks g
        JOIN history_devices d ON d.id=g.device JOIN gpu_descriptors k ON k.id=g.descriptor
        WHERE g.at<? ORDER BY g.machine,g.at,g.device
        """, (cutoff,)))
    first = hosts.fetchone()
    if first is None:
        return None
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    timestamp = datetime.fromtimestamp(cutoff/1000, timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    filename = 'before-'+timestamp+'.jsonl.gz'
    target = directory/filename
    host_count = gpu_count = 0
    current = next(gpus, None)
    temporary = None
    try:
        with NamedTemporaryFile(dir=directory, prefix='.archive-', delete=False) as stage:
            temporary = Path(stage.name)
            with gzip.GzipFile(filename='', fileobj=stage, mode='wb', compresslevel=3, mtime=0) as output:
                encode(output, {'format':'compute-monitor-history','version':1,'before_ms':cutoff})
                for machine, at, identity, received, source_at, source, boot, epoch, status, raw, generation in chain((first,), hosts):
                    metrics = json.loads(raw)
                    if generation is not None:
                        metrics['gpu_generation'] = generation
                    cards = []
                    while current is not None and current[:2] == (machine, at):
                        card = {'uuid':current[2], **json.loads(current[3]),
                                **dict(zip(GPU_SAMPLE_FIELDS, current[4:], strict=True))}
                        cards.append(card)
                        current = next(gpus, None)
                    encode(output, {'machine':identity,'observed_at':at,'received_at':received,'source_at':source_at,
                                    'source':source,'boot':boot,'epoch':epoch,'status':status,'metrics':metrics,'gpus':cards})
                    host_count += 1
                    gpu_count += len(cards)
                if current is not None:
                    raise ValueError('冷归档存在未归属的 GPU 样本')
            stage.flush()
            os.fsync(stage.fileno())
        os.replace(temporary, target)
        sync_directory(directory)
        return ColdArchive(filename, host_count, gpu_count, target.stat().st_size)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prune_cold(target, identity):
    if not target.exists():
        return None
    temporary = None
    hosts = gpus = 0
    removed = False
    try:
        with gzip.open(target, 'rb') as source, NamedTemporaryFile(
            dir=target.parent, prefix='.purge-', delete=False
        ) as stage:
            temporary = Path(stage.name)
            header = read_cold_header(source)
            with gzip.GzipFile(filename='', fileobj=stage, mode='wb', compresslevel=3, mtime=0) as output:
                output.write(header)
                for line in source:
                    row = json.loads(line)
                    if row['machine'] == identity:
                        removed = True
                        continue
                    hosts += 1
                    gpus += len(row['gpus'])
                    output.write(line)
            if removed and hosts:
                stage.flush()
                os.fsync(stage.fileno())
        if removed:
            if hosts:
                os.replace(temporary, target)
            else:
                target.unlink()
            sync_directory(target.parent)
        return ColdArchive(target.name, hosts, gpus, target.stat().st_size) if target.exists() else None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
