import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib
import logging
import math
import sqlite3
import time
import uuid
from zlib import error as CompressionError
from zoneinfo import ZoneInfo

from .collector import CollectionError, Collector, cpu_percent
from .config import DEFAULT_SSH_CONNECT_TIMEOUT, Machine, MachineSettings
from .history import DAY_MS, GPU_FIELDS, History, HistoryInUse, WARM_HOURS, WARM_MS


log = logging.getLogger(__name__)
DEVICE_FIELDS = ('uuid', 'index', 'name', 'bus_id')
PROCESS_FIELDS = ('pid', 'type', 'name', 'uid', 'user', 'workload', 'used_memory_mib')
ARCHIVE_ZONE = ZoneInfo('UTC')
PURGE_ERRORS = (OSError, sqlite3.Error, ValueError, KeyError, TypeError, EOFError, CompressionError)


def milliseconds():
    return time.time_ns() // 1000000


def archive_slots(now, zone=ARCHIVE_ZONE):
    local = datetime.fromtimestamp(now/1000, zone)
    slot = local.replace(hour=3, minute=0, second=0, microsecond=0)
    if slot > local:
        slot -= timedelta(days=1)
    return int(slot.timestamp()*1000), int((slot+timedelta(days=1)).timestamp()*1000)


async def wait_for_work(work):
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        await asyncio.gather(work, return_exceptions=True)
        raise


async def offload(fn, *args):
    return await wait_for_work(asyncio.create_task(asyncio.to_thread(fn,*args)))


def avg(values):
    return sum(values)/len(values) if values else None


def metrics_from(data, percent):
    memory = data.get('memory')
    if memory and 'used_bytes' not in memory:
        memory = dict(memory, used_bytes=memory['total_bytes']-memory['available_bytes'])
    devices = []
    for index, raw in enumerate(data.get('gpus', [])):
        gpu = {key:raw[key] for key in GPU_FIELDS if key in raw}
        gpu['index'] = index
        gpu['processes'] = [{key:proc[key] for key in PROCESS_FIELDS if key in proc}
                            for proc in raw.get('processes', [])]
        devices.append(gpu)
    utilization = [gpu['utilization_percent'] for gpu in devices if gpu.get('utilization_percent') is not None]
    complete = bool(data.get('gpu_inventory_complete'))
    watts = [gpu['power_w'] for gpu in devices if gpu.get('power_w') is not None]
    power_modes = {gpu.get('power_kind') for gpu in devices}
    total_power = sum(watts) if devices and complete and len(watts) == len(devices) and len(power_modes) == 1 else None
    return {'scope':'container' if data.get('scope') == 'container' else 'host',
            'cpu_percent':percent, 'cpu_count':data.get('cpu_count'), 'load_average':data.get('load_average', []),
            'memory':memory, 'memory_percent':100*memory['used_bytes']/memory['total_bytes']
            if memory and memory['total_bytes'] else None,
            'root_disk':data.get('root_disk'), 'uptime_seconds':data.get('uptime_seconds'),
            'driver_version':data.get('driver_version'), 'gpu_inventory_complete':complete,
            'gpu_percent':avg(utilization), 'gpu_util_count':len(utilization), 'gpu_power_w':total_power,
            'gpu_power_kind':next(iter(power_modes)) if total_power is not None else None,
            'gpu_generation':','.join(sorted(gpu['uuid'] for gpu in devices)),
            'gpus':devices}


class Monitor:
    def __init__(self, config, collector=None, clock=milliseconds, sleep=asyncio.sleep, monotonic=None):
        self.config = config
        self.archive_zone = ZoneInfo(config.archive_timezone)
        self.clock = clock
        self.sleep = sleep
        self.monotonic = monotonic or time.monotonic
        self.collector = collector if collector is not None else Collector(config)
        self.history = History(config.data_dir)
        self.history_ok = False
        self.archive_ok = True
        self.slots = asyncio.Semaphore(config.concurrency)
        self.writer = asyncio.Lock()
        self.readers = asyncio.Semaphore(2)
        self.epoch = uuid.uuid4().hex
        self.machines = {machine.id:machine for machine in config.machines}
        self.registry_loaded = False
        self.settings_lock = asyncio.Lock()
        self.archive_lock = asyncio.Lock()
        self.samplers = {}
        self.archive_task = None
        self.removal_task = None
        self.pending_removals = set()
        self.latest = {}
        self.aliases = {}
        self.ssh_pins = {}
        self.machine_order = {}
        self.scopes = {}
        self.inventory = {}
        self.last_seen = {}
        self.cpu_baseline = {}

    @property
    def tasks(self):
        return [*self.samplers.values(), *(task for task in (self.archive_task,self.removal_task) if task)]

    async def load_registry(self):
        aliases = await self.write(self.history.prepare)
        removed, pending = await self.write(self.history.removal_state)
        machines = {machine.id:machine for machine in self.config.machines if machine.history_key not in removed}
        identities = {machine.history_key:machine.id for machine in machines.values()}
        for identity, registration, settings in await self.write(self.history.machine_settings):
            if registration is not None:
                machine = Machine.model_validate_json(registration)
                if machine.id in machines or identity in identities or identity != machine.history_key:
                    raise ValueError('监控登记与配置文件中的机器身份冲突')
                machines[machine.id] = machine
                identities[identity] = machine.id
            if identity in identities:
                id = identities[identity]
                machines[id] = self.with_settings(machines[id], MachineSettings.model_validate_json(settings))
        pins = await self.write(self.history.ssh_pins)
        order = await self.write(self.history.machine_order)
        host_keys = defaultdict(list)
        for machine in machines.values():
            host_keys[machine.expected_host_id].append(pins.get(machine.history_key))
            last, cards, scope = await self.write(self.history.inventory, machine.history_key, self.clock())
            self.last_seen[machine.id] = last
            self.scopes[machine.id] = scope
            self.set_inventory(machine, cards)
        if any(len(keys) > 1 and (None in keys or len(set(keys)) != len(keys)) for keys in host_keys.values()):
            raise ValueError('重复的 machine-id 缺少可区分的 SSH 主机密钥')
        self.aliases = aliases
        self.ssh_pins = pins
        self.machine_order = order
        self.machines = machines
        self.pending_removals = pending
        self.schedule_removal_retry()
        self.registry_loaded = self.history_ok = True
        for machine in machines.values():
            self.start_sampler(machine)

    async def start(self):
        try:
            await self.load_registry()
        except (OSError, sqlite3.Error) as error:
            self.storage_failure(error)
        self.archive_task = asyncio.create_task(self.archive(), name='history:archive')

    def start_sampler(self, machine):
        if machine.enabled:
            self.samplers[machine.id] = asyncio.create_task(self.run(machine), name='sample:'+machine.id)

    async def stop_sampler(self, id):
        task = self.samplers.pop(id, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def restart_sampler(self, machine):
        await self.stop_sampler(machine.id)
        self.latest.pop(machine.id, None)
        self.cpu_baseline.pop(machine.id, None)
        self.start_sampler(machine)

    async def close(self):
        tasks = self.tasks
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.history.close()

    async def write(self, fn, *args):
        async with self.writer:
            return await offload(fn,*args)

    async def change_alias(self, id, alias):
        async with self.settings_lock:
            machine = self.machines[id]
            if not self.registry_loaded:
                raise OSError('机器配置暂不可读')

            async def save():
                await self.write(self.history.set_alias, machine.history_key, alias)
                self.set_alias(machine.history_key, alias)

            await wait_for_work(asyncio.create_task(save()))
        return {'id':machine.id,'alias':alias,'name':alias or self.default_name(machine)}

    async def remove(self, id):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('机器配置暂不可读')
            machine = self.machines[id]

            async def save():
                async with self.archive_lock:
                    return await self.remove_machine(machine)

            return await wait_for_work(asyncio.create_task(save()))

    async def remove_machine(self, machine):
        identity = machine.history_key
        from_config = any(node.history_key == identity for node in self.config.machines)
        await self.stop_sampler(machine.id)
        try:
            await self.write(self.history.begin_machine_removal, identity, from_config)
        except (OSError, sqlite3.Error):
            self.start_sampler(machine)
            raise
        self.pending_removals.add(identity)
        self.machines.pop(machine.id)
        for index in (self.ssh_pins,self.machine_order,self.aliases):
            index.pop(identity, None)
        for index in (self.latest,self.scopes,self.inventory,self.last_seen,self.cpu_baseline):
            index.pop(machine.id, None)
        await self.clean_removed_archives(identity)
        self.schedule_removal_retry()
        return {'id':machine.id,'cleanup_pending':identity in self.pending_removals}

    async def clean_removed_archives(self, identity):
        try:
            archives = await offload(self.history.purge_machine_archives, identity)
            await self.write(self.history.finish_machine_removal, identity, archives)
        except PURGE_ERRORS as error:
            log.warning('已移除节点的冷归档清理待重试 (%s)', type(error).__name__)
        else:
            self.pending_removals.discard(identity)

    def schedule_removal_retry(self):
        if self.pending_removals and (self.removal_task is None or self.removal_task.done()):
            self.removal_task = asyncio.create_task(self.retry_removals(), name='history:remove')

    async def retry_removals(self):
        while self.pending_removals:
            await self.sleep(30)
            async with self.archive_lock:
                for identity in tuple(self.pending_removals):
                    await self.clean_removed_archives(identity)

    async def reorder(self, ids):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('机器配置暂不可读')
            if len(ids) != len(self.machines) or set(ids) != self.machines.keys():
                raise CollectionError('conflict', '机器清单已变化，请刷新后重试排序')
            order = {self.machines[id].history_key:index for index,id in enumerate(ids)}

            async def save():
                await self.write(self.history.save_machine_order, order)
                self.machine_order = order

            await wait_for_work(asyncio.create_task(save()))
        return {'machines':ids}

    def ordered_machines(self):
        return sorted(self.machines.values(), key=lambda node:self.machine_order.get(node.history_key, math.inf))

    def set_alias(self, identity, alias):
        if alias is None:
            self.aliases.pop(identity, None)
        else:
            self.aliases[identity] = alias

    @staticmethod
    def default_name(machine):
        return machine.name or machine.id

    @staticmethod
    def with_settings(machine, settings):
        values = settings.model_dump(exclude={'alias'})
        if 'ssh_connect_timeout_seconds' not in settings.model_fields_set:
            values.pop('ssh_connect_timeout_seconds')
        return machine.model_copy(update=values)

    def interval(self, machine):
        return machine.interval_seconds or self.config.interval_seconds

    def stale_seconds(self, machine):
        return max(self.config.stale_seconds, self.interval(machine) + self.config.probe_timeout(machine.connect_timeout))

    def check_registration(self, host, user):
        if len(self.machines) >= 128:
            raise CollectionError('conflict', '机器清单已达到 128 台上限')
        if any((machine.ssh_alias, machine.ssh_user) == (host, user) for machine in self.machines.values()):
            raise CollectionError('conflict', '这台机器已经登记，可在机器详情页修改配置')

    async def verify_disambiguation_key(self, host, user, timeout, machine_id):
        try:
            async with self.slots:
                observed = await self.collector.identify(host, user, timeout, canonical_key=True)
        except CollectionError as error:
            raise CollectionError('conflict', f'{host} 的 SSH 主机密钥暂时无法复核') from error
        if observed.machine_id != machine_id or not observed.ssh_host_key:
            raise CollectionError('conflict', f'{host} 缺少可区分的机器身份和 ED25519 SSH 主机密钥证据')
        return observed.ssh_host_key

    async def resolve_collision(self, request, identity):
        matches = [node for node in self.machines.values() if node.expected_host_id == identity.machine_id]
        if not matches:
            return None, {}
        if any(node.mode != 'ssh' for node in matches):
            raise CollectionError('conflict', 'machine-id 与已登记机器重复，缺少可区分的 SSH 主机密钥证据')
        new_key = identity.ssh_host_key
        if not new_key:
            new_key = await self.verify_disambiguation_key(
                request.host, request.ssh_user, request.ssh_connect_timeout_seconds, identity.machine_id)
        pins = {}
        for node in matches:
            key = self.ssh_pins.get(node.history_key)
            if key is None:
                key = await self.verify_disambiguation_key(
                    node.ssh_alias, node.ssh_user, node.connect_timeout, identity.machine_id)
                pins[node.history_key] = key
            if key == new_key:
                raise CollectionError('conflict', f'这台机器已经登记为 {self.default_name(node)}，可在机器详情页修改配置')
        history_id = hashlib.sha256(f'{identity.machine_id}:{new_key}'.encode()).hexdigest()[:32]
        if history_id in {node.history_key for node in self.machines.values()}:
            raise CollectionError('conflict', '新机器的历史标识与已有记录冲突')
        pins[history_id] = new_key
        return history_id, pins

    async def register(self, request):
        if not self.registry_loaded:
            raise OSError('机器配置暂不可读')
        self.check_registration(request.host, request.ssh_user)
        async with self.slots:
            identity = await self.collector.identify(request.host, request.ssh_user, request.ssh_connect_timeout_seconds)
        values = request.model_dump(exclude={'host', 'ssh_user'}, exclude_unset=True)
        values.setdefault('interval_seconds', self.config.interval_seconds)
        settings = MachineSettings.model_validate(values)
        async with self.settings_lock:
            self.check_registration(request.host, request.ssh_user)
            history_id, pins = await self.resolve_collision(request, identity)
            machine = Machine(id=uuid.uuid4().hex, name=request.host[:80], mode='ssh', ssh_alias=request.host,
                              ssh_user=request.ssh_user, expected_host_id=identity.machine_id, history_id=history_id)
            if machine.history_key in self.pending_removals:
                raise CollectionError('conflict', '此节点的历史归档正在清理，完成后可重新登记')
            return await self.save_settings(machine, settings, registration=machine.model_dump_json(), pins=pins)

    async def configure(self, id, settings):
        async with self.settings_lock:
            return await self.save_settings(self.machines[id], settings)

    async def save_settings(self, machine, settings, registration=None, pins=None):
        if not self.registry_loaded:
            raise OSError('机器配置暂不可读')

        async def save():
            updated = self.with_settings(machine, settings)
            identity = machine.history_key
            order = None
            if registration:
                machines = [*self.ordered_machines(), machine]
                order = {node.history_key:index for index,node in enumerate(machines)}
            persisted = settings.model_copy(update={'ssh_connect_timeout_seconds':updated.ssh_connect_timeout_seconds})
            await self.write(self.history.save_machine, identity, registration,
                             persisted.model_dump_json(exclude={'alias'}), settings.alias, pins or {}, order)
            if pins:
                self.ssh_pins.update(pins)
                for existing in self.machines.values():
                    if existing.history_key in pins:
                        await self.restart_sampler(existing)
            self.set_alias(identity, settings.alias)
            if order is not None:
                self.machine_order = order
            self.machines[machine.id] = updated
            if registration or (machine.enabled, machine.active_checks, self.interval(machine), machine.connect_timeout) != (
                updated.enabled, updated.active_checks, self.interval(updated), updated.connect_timeout
            ):
                await self.restart_sampler(updated)
            return self.machine_view(updated, self.clock())

        return await wait_for_work(asyncio.create_task(save()))

    def storage_failure(self, error):
        if self.history_ok or not getattr(self, 'history_error_reported', False):
            log.warning('监控指标库不可写 (%s)', type(error).__name__)
        self.history_ok = False
        self.history_error_reported = True

    async def archive(self):
        while True:
            due, following = archive_slots(self.clock(), self.archive_zone)
            if not self.registry_loaded:
                await self.sleep(5)
                try:
                    await self.load_registry()
                except (OSError, sqlite3.Error) as error:
                    self.storage_failure(error)
                    continue
            if not self.history_ok:
                await self.sleep(60)
                continue
            try:
                async with self.archive_lock:
                    slot = await self.write(self.history.begin_archive, due)
                    if slot is not None:
                        while await self.write(self.history.pack, slot-DAY_MS):
                            await self.sleep(0)
                        cutoff = slot-WARM_MS
                        exported = await offload(self.history.export, cutoff)
                        await self.write(self.history.finish_archive, slot, cutoff, exported)
                        if exported:
                            log.info('冷归档完成：%s，%d 条主机样本，%d 条 GPU 样本',
                                     exported.filename, exported.hosts, exported.gpus)
                self.archive_ok = True
                if slot is not None and slot < due:
                    continue
                await self.sleep(max(1,(following-self.clock())/1000))
            except (OSError, sqlite3.Error, ValueError) as error:
                if self.archive_ok:
                    log.warning('监控历史归档未完成 (%s)', type(error).__name__)
                self.archive_ok = False
                await self.sleep(60)

    async def run(self, machine):
        interval = self.interval(machine)
        epoch = uuid.uuid4().hex if machine.interval_seconds is not None else self.epoch
        next_due = self.monotonic()
        while True:
            await self.sleep(max(0, next_due-self.monotonic()))
            async with self.slots:
                snapshot = await self.observe(machine)
            self.latest[machine.id] = snapshot
            try:
                if not self.history_ok:
                    await self.write(self.history.prepare)
                await self.write(self.history.append, machine.history_key, epoch, snapshot)
                self.history_ok = True
                self.history_error_reported = False
            except (OSError, sqlite3.Error, HistoryInUse) as error:
                self.storage_failure(error)
            # Keep the per-machine cadence and skip missed slots instead of queueing retries.
            elapsed = self.monotonic()-next_due
            next_due += interval*(1+math.floor(max(0, elapsed)/interval))

    def set_inventory(self, machine, devices, partial=False):
        if devices:
            cards = {gpu['uuid']:{key:gpu.get(key) for key in DEVICE_FIELDS} for gpu in devices}
            if partial:
                for old in self.inventory.get(machine.id, []):
                    cards.setdefault(old['uuid'], old)
            self.inventory[machine.id] = list(cards.values())

    async def observe(self, machine):
        started = self.clock()
        snapshot = {'observed_at':started, 'source':machine.mode, 'metrics':None}
        stale = round(self.stale_seconds(machine)*1000)
        if stale != round(self.config.stale_seconds*1000):
            snapshot['stale_ms'] = stale
        try:
            key = self.ssh_pins.get(machine.history_key)
            kwargs = {'ssh_host_key':key} if key is not None else {}
            data = await asyncio.wait_for(self.collector(machine, **kwargs), self.config.probe_timeout(machine.connect_timeout))
            if data.get('host_id') != machine.expected_host_id or not data.get('boot_id'):
                raise CollectionError('unknown', '宿主身份或启动身份无法核实')
            self.scopes[machine.id] = 'container' if data.get('scope') == 'container' else 'host'
            if not any(data.get(field) is not None for field in ('cpu_count','memory','uptime_seconds','root_disk')) and not (
                data.get('load_average') or data.get('gpus')
            ):
                raise CollectionError('unknown', '；'.join(data.get('warnings', [])) or '已选巡检项目暂无可读指标')
            boot, counters = data['boot_id'], data.get('cpu_ticks')
            container_cpu = data.get('container_cpu')
            cpu_identity = (self.scopes[machine.id],data.get('cpu_count'))
            if container_cpu:
                cpu_identity += (container_cpu['group'],)
                counters = container_cpu['observed_ns'], container_cpu['usage_ns']
            baseline = self.cpu_baseline.get(machine.id)
            percent = None
            if baseline:
                last_boot, last_at, last_cpu, previous = baseline
                if boot == last_boot and 0 < started-last_at <= stale and last_cpu == cpu_identity:
                    if container_cpu and previous:
                        elapsed, used = (after-before for before, after in zip(previous, counters))
                        if elapsed > 0 and used >= 0:
                            percent = 100*used/elapsed/container_cpu['capacity']
                    else:
                        percent = cpu_percent(previous, counters)
            metrics = metrics_from(data, percent)
            warnings = data.get('warnings', [])
            source_at = data.get('source_observed_at')
            snapshot.update(status='warning' if warnings else 'normal', warnings=warnings, boot=boot,
                            source_at=round(source_at*1000) if source_at is not None else None, metrics=metrics)
            self.cpu_baseline[machine.id] = boot, started, cpu_identity, counters
            self.last_seen[machine.id] = started
            self.set_inventory(machine, metrics['gpus'], partial=not metrics['gpu_inventory_complete'])
        except asyncio.TimeoutError:
            snapshot.update(status='offline', reason='采集超过单机时限')
        except CollectionError as error:
            snapshot.update(status=error.status, reason=str(error))
        except (KeyError, ValueError, TypeError, AttributeError, ArithmeticError) as error:
            log.warning('机器 %s 返回不可用的采集字段 (%s)', machine.id, type(error).__name__)
            snapshot.update(status='unknown', reason='采集字段格式不可用')
        if snapshot['metrics'] is None:
            self.cpu_baseline.pop(machine.id, None)
        snapshot['received_at'] = self.clock()
        return snapshot

    def machine_view(self, machine, now):
        result = self.latest.get(machine.id) or {}
        view = {key:result[key] for key in ('status','reason','warnings','observed_at','received_at','metrics') if key in result}
        default_name = self.default_name(machine)
        alias = self.aliases.get(machine.history_key)
        stale = round(self.stale_seconds(machine)*1000)
        view.update(id=machine.id, name=alias or default_name, alias=alias, default_name=default_name,
                    scope=self.scopes.get(machine.id), address=machine.display_address, mode=machine.mode,
                    require_gpu=machine.require_gpu or 'gpu' in machine.active_checks or bool(self.inventory.get(machine.id)),
                    expected_gpu_count=machine.expected_gpu_count,
                    last_success_at=self.last_seen.get(machine.id), devices=self.inventory.get(machine.id, []),
                    enabled=machine.enabled, checks=machine.active_checks, interval_seconds=self.interval(machine),
                    ssh_connect_timeout_seconds=machine.connect_timeout,
                    stale_ms=stale, metrics=view.get('metrics'))
        if not machine.enabled:
            view.update(status='disabled', metrics=None, reason=None, warnings=[])
        elif not result:
            view['status'] = 'waiting'
        elif result['metrics'] is not None and now-result['observed_at'] >= stale:
            view.update(status='stale', reason='有效样本超过时限，等待新采样', metrics=None, warnings=[])
        return view

    def snapshot(self):
        now = self.clock()
        return {'server_time':now, 'period_ms':round(self.config.interval_seconds*1000),
                'default_ssh_connect_timeout_seconds':DEFAULT_SSH_CONNECT_TIMEOUT,
                'stale_ms':round(self.config.stale_seconds*1000), 'history_writable':self.history_ok,
                'archive_ok':self.archive_ok, 'registry_loaded':self.registry_loaded,
                'removal_pending':len(self.pending_removals),
                'machine_history_hours':WARM_HOURS,
                'machines':[self.machine_view(machine, now) for machine in self.ordered_machines()]}

    async def series(self, machine, gpu, metric, hours):
        enabled = [item.history_key for item in self.machines.values() if item.enabled]
        configured = next((item for item in self.machines.values() if item.history_key == machine), None)
        period = min(self.interval(configured), self.config.interval_seconds) if configured else self.config.interval_seconds
        async with self.readers:
            return await asyncio.to_thread(self.history.series, enabled, machine, gpu, metric, hours, self.clock(),
                                           round(period*1000), round(self.config.stale_seconds*1000))
