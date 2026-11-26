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

from .archive_analysis import ARCHIVE_ANALYSIS_IDLE_SECONDS, ArchiveAnalysis, archive_bounds
from .collector import CollectionError, Collector, cpu_percent
from .config import DEFAULT_IDLE_MEMORY_TOLERANCE_MIB, DEFAULT_SSH_CONNECT_TIMEOUT, Machine, MachineSettings
from .groups import compute_key, group_history_data, storage_key, summarize_resources
from .history import DAY_MS, GPU_FIELDS, History, HistoryInUse, MAX_POINTS, WARM_HOURS, WARM_MS, downsample
from .resources import StorageAdapter, StorageObservation


log = logging.getLogger(__name__)
DEVICE_FIELDS = ('uuid', 'index', 'name', 'bus_id')
PROCESS_FIELDS = ('pid', 'type', 'name', 'uid', 'user', 'workload', 'used_memory_mib', 'started_at', 'elapsed_seconds')
ARCHIVE_ZONE = ZoneInfo('UTC')
PURGE_ERRORS = (OSError, sqlite3.Error, ValueError, KeyError, TypeError, EOFError, CompressionError)
INHERITABLE_MACHINE_FIELDS = {'idle_memory_tolerance_mib', 'configuration_cluster_id'}


def configuration_layer(override, scope, ids=(), *, inherited=None):
    if override is not None:
        return {'override':override, 'effective':override, 'source':{'scope':scope, 'ids':ids}}
    return {'override':None, 'effective':inherited['effective'] if inherited else None,
            'source':inherited['source'] if inherited else None}


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
        # This hardware setting is used by the live overview. History keeps its existing field set.
        default_limit = raw.get('default_power_limit_w')
        if type(default_limit) in (int, float) and default_limit > 0 and math.isfinite(default_limit):
            gpu['default_power_limit_w'] = default_limit
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
            **({'gpu_inventory_empty':True} if data.get('gpu_inventory_empty') else {}),
            'gpu_percent':avg(utilization), 'gpu_util_count':len(utilization), 'gpu_power_w':total_power,
            'gpu_power_kind':next(iter(power_modes)) if total_power is not None else None,
            'gpu_generation':','.join(sorted(gpu['uuid'] for gpu in devices)),
            'gpus':devices}


class Monitor:
    def __init__(self, config, collector=None, clock=milliseconds, sleep=asyncio.sleep, monotonic=None,
                 *, storage_adapters: dict[str, StorageAdapter] | None = None):
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
        self.archive_analyses = {}
        self.samplers = {}
        self.archive_task = None
        self.removal_task = None
        self.pending_removals = set()
        self.latest = {}
        self.aliases = {}
        self.people = {}
        self.machine_assignees = {}
        self.shared_users = set()
        self.storage = {}
        self.rooms = {}
        self.clusters = {}
        self.locations = {}
        self.global_idle_override = None
        self.resource_order = {}
        self.storage_adapters = dict(storage_adapters or {})
        self.storage_latest = {}
        self.storage_last_seen = {}
        self.storage_samplers = {}
        self.freshness_task = None
        self.ssh_pins = {}
        self.machine_order = {}
        self.scopes = {}
        self.inventory = {}
        self.inventory_complete = {}
        self.last_seen = {}
        self.cpu_baseline = {}

    @property
    def tasks(self):
        return [*self.samplers.values(), *self.storage_samplers.values(),
                *(task for task in (self.archive_task,self.removal_task,self.freshness_task) if task)]

    async def load_registry(self):
        aliases = await self.write(self.history.prepare)
        removed, pending = await self.write(self.history.removal_state)
        machines = {machine.id:machine for machine in self.config.machines if machine.history_key not in removed}
        identities = {machine.history_key:machine.id for machine in machines.values()}
        for identity, registration, settings in await self.write(self.history.machine_settings):
            if registration is not None:
                machine = Machine.model_validate_json(registration)
                # The old registration API serialized its implicit zero and had no tolerance input.
                if machine.idle_memory_tolerance_mib == 0:
                    machine = Machine.model_validate(machine.model_dump(
                        exclude_unset=True, exclude={'idle_memory_tolerance_mib'}))
                if machine.id in machines or identity in identities or identity != machine.history_key:
                    raise ValueError('监控登记与配置文件中的机器身份冲突')
                machines[machine.id] = machine
                identities[identity] = machine.id
            if identity in identities:
                id = identities[identity]
                parsed = MachineSettings.model_validate_json(settings)
                machines[id] = self.with_settings(machines[id], parsed)
        people, assignees = await self.write(self.history.people_and_assignees)
        pins = await self.write(self.history.ssh_pins)
        order = await self.write(self.history.machine_order)
        host_keys = defaultdict(list)
        for machine in machines.values():
            host_keys[machine.expected_host_id].append(pins.get(machine.history_key))
            last, cards, scope, complete = await self.write(
                self.history.inventory, machine.history_key, self.clock(), machine.target_os == 'windows')
            self.last_seen[machine.id] = last
            self.scopes[machine.id] = scope
            self.set_inventory(machine, cards, complete=complete)
        if any(len(keys) > 1 and (None in keys or len(set(keys)) != len(keys)) for keys in host_keys.values()):
            raise ValueError('重复的 machine-id 缺少可区分的 SSH 主机密钥')
        self.aliases = aliases
        self.people = people
        self.machine_assignees = assignees
        self.shared_users, self.storage = await self.write(self.history.load_resources)
        self.storage_last_seen = await self.write(self.history.storage_success_times, self.clock())
        self.rooms, self.clusters, self.locations, self.resource_order = await self.write(self.history.load_groups)
        self.global_idle_override = await self.write(self.history.global_idle_tolerance)
        self.ssh_pins = pins
        self.machine_order = order
        self.machines = machines
        await self.reconcile_alerts()
        self.pending_removals = pending
        self.schedule_removal_retry()
        self.registry_loaded = self.history_ok = True
        for machine in machines.values():
            self.start_sampler(machine)
        for id in self.storage:
            self.start_storage_sampler(id)

    async def start(self):
        try:
            await self.load_registry()
        except (OSError, sqlite3.Error) as error:
            self.storage_failure(error)
        self.archive_task = asyncio.create_task(self.archive(), name='history:archive')
        self.freshness_task = asyncio.create_task(self.check_freshness(), name='alerts:freshness')

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
        jobs = tuple(self.archive_analyses.values())
        tasks = [*self.tasks, *(job.task for job in jobs)]
        for identity in tuple(self.archive_analyses):
            self.discard_archive_analysis(identity)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for job in jobs:
            async with job.read_lock:
                job.close()
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
            await self.write(self.history.begin_machine_removal, identity, from_config, machine.id, self.clock())
        except (OSError, sqlite3.Error):
            self.start_sampler(machine)
            raise
        self.pending_removals.add(identity)
        self.machines.pop(machine.id)
        self.discard_archive_analysis(identity)
        self.forget_resource(compute_key(identity))
        self.shared_users.discard(identity)
        for index in (self.ssh_pins,self.machine_order,self.aliases,self.machine_assignees):
            index.pop(identity, None)
        for index in (self.latest,self.scopes,self.inventory,self.inventory_complete,self.last_seen,self.cpu_baseline):
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
            if self.resource_order:
                replacements = iter(ids)
                combined = [next(replacements) if id in self.machines else id for id in self.ordered_resource_ids()]
                await self.persist_resource_order(combined, self.resource_keys())
                return {'machines':ids}
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

    def person_views(self, people):
        return [{'id': person, 'name': self.people[person]}
                for person in sorted(people, key=lambda person: self.people[person])]

    async def save_person(self, name, person=None):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('机器配置暂不可读')
            if person is not None and person not in self.people:
                raise KeyError(person)
            if any(other != person and name == existing for other, existing in self.people.items()):
                raise CollectionError('conflict', 'person_name_taken')

            async def save():
                saved = await self.write(self.history.save_person, person, name)
                self.people[saved] = name
                return {'id': saved, 'name': name}

            return await wait_for_work(asyncio.create_task(save()))

    async def delete_person(self, person):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('机器配置暂不可读')
            if person not in self.people:
                raise KeyError(person)
            references = self.person_references(person)
            if any(references.values()) or any(person in ids for ids in self.machine_assignees.values()):
                error = CollectionError('conflict', 'person_in_use')
                error.references = references
                raise error

            async def save():
                await self.write(self.history.delete_person, person)
                del self.people[person]

            await wait_for_work(asyncio.create_task(save()))

    def user_view(self, key):
        users = self.person_views(self.machine_assignees.get(key, ()))
        return {'assigned_users': users, 'assignment_mode': 'shared' if key in self.shared_users else
                'legacy' if len(users) > 1 else 'person' if users else 'unset'}

    def validate_people(self, people):
        if any(person not in self.people for person in people):
            raise CollectionError('conflict', 'person_missing')

    def set_users(self, key, people, shared):
        if people:
            self.machine_assignees[key] = people
        else:
            self.machine_assignees.pop(key, None)
        if shared:
            self.shared_users.add(key)
        else:
            self.shared_users.discard(key)

    async def configure_assignees(self, id, people, shared=False, *, storage=False):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('机器配置暂不可读')
            target = self.storage[id] if storage else self.machines[id]
            key = id if storage else target.history_key
            self.validate_people(people)

            async def save():
                await self.write(self.history.save_assignees, key, people, shared)
                self.set_users(key, people, shared)
                return self.storage_view(id, self.clock()) if storage else self.machine_view(target, self.clock())

            return await wait_for_work(asyncio.create_task(save()))

    async def configure_storage(self, settings, id=None):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('机器配置暂不可读')
            previous = self.storage[id] if id is not None else None
            id = id or 'storage-' + uuid.uuid4().hex
            if settings.adapter is not None and settings.adapter not in self.storage_adapters and (
                previous is None or settings.adapter != previous.adapter
            ):
                raise CollectionError('conflict', 'storage_adapter_unavailable')
            people = () if settings.person_id is None else (settings.person_id,)
            assignment = (people, settings.shared) if previous is None or {
                'person_id','shared'
            } & settings.model_fields_set else None
            self.validate_people(people)
            location = self.check_location(settings)
            restart = previous is None or (previous.enabled, previous.adapter, previous.storage_kind) != (
                settings.enabled, settings.adapter, settings.storage_kind)

            async def save():
                if restart:
                    await self.stop_storage_sampler(id)
                closure = None
                if not settings.enabled or settings.adapter is None:
                    closure = (self.clock(), 'disabled' if not settings.enabled else 'adapter_removed')
                try:
                    await self.write(self.history.save_storage, id, settings, assignment, closure, location)
                except (OSError, sqlite3.Error):
                    if restart and previous:
                        self.start_storage_sampler(id)
                    raise
                self.storage[id] = settings
                if location is not None:
                    self.set_location(storage_key(id), location)
                if assignment is not None:
                    self.set_users(id, *assignment)
                if restart:
                    self.storage_latest.pop(id, None)
                    self.start_storage_sampler(id)
                return self.storage_view(id, self.clock())

            return await wait_for_work(asyncio.create_task(save()))

    async def remove_storage(self, id):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('机器配置暂不可读')
            self.storage[id]

            async def remove():
                await self.stop_storage_sampler(id)
                try:
                    await self.write(self.history.remove_storage, id, self.clock())
                except (OSError, sqlite3.Error):
                    self.start_storage_sampler(id)
                    raise
                del self.storage[id]
                self.forget_resource(storage_key(id))
                self.set_users(id, (), False)
                self.storage_latest.pop(id, None)
                self.storage_last_seen.pop(id, None)
                return {'id':id,'cleanup_pending':False}

            return await wait_for_work(asyncio.create_task(remove()))

    def start_storage_sampler(self, id):
        settings = self.storage[id]
        if settings.enabled and settings.adapter in self.storage_adapters:
            self.storage_samplers[id] = asyncio.create_task(self.sample_storage(id), name='storage:'+id)

    async def stop_storage_sampler(self, id):
        task = self.storage_samplers.pop(id, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def sample_storage(self, id):
        interval = self.config.interval_seconds
        while True:
            settings = self.storage[id]
            at = self.clock()
            observation = None
            evidence = None
            try:
                async with self.slots:
                    result = await asyncio.wait_for(self.storage_adapters[settings.adapter](id, settings),
                                                    self.config.stale_seconds)
                observation = StorageObservation.model_validate(result)
                if not 0 <= self.clock()-observation.observed_at < self.config.stale_seconds*1000:
                    observation = None
                    raise ValueError('storage timestamp outside the collection interval')
                if observation.health in ('failed','degraded') or any(
                    pool.health in ('failed','degraded') for pool in observation.pools
                ):
                    evidence = 'storage_health'
                status = 'warning' if evidence else 'normal'
            except asyncio.TimeoutError:
                status, evidence = 'offline', 'storage_timeout'
            except (OSError, ValueError, TypeError):
                status, evidence = 'unknown', 'storage_observation_unavailable'
            if observation:
                self.storage_last_seen[id] = observation.observed_at
            cleared = {}
            if observation:
                cleared = {'offline': 'collection_resumed', 'collection': 'collection_resumed', 'stale': 'collection_resumed'}
                if observation.health == 'healthy' and all(pool.health == 'healthy' for pool in observation.pools):
                    cleared['storage_health'] = 'storage_health_confirmed'
            rule = {'offline':'offline', 'unknown':'collection', 'warning':'storage_health'}.get(status)
            event = (id, settings.storage_kind, settings.name, at,
                     {rule: ('warning', evidence)} if rule else {}, cleared, self.storage_last_seen.get(id))
            try:
                await self.write(self.history.append_storage, id, at, status, observation, event)
            except (OSError, sqlite3.Error) as error:
                self.storage_failure(error)
            self.storage_latest[id] = {'observed_at': observation.observed_at if observation else at, 'sample_at':at,
                                       'status': status, 'reason': evidence,
                                       'storage_observation': observation.model_dump() if observation else None}
            await self.sleep(max(0, interval-(self.clock()-at)/1000))

    def storage_view(self, id, now):
        settings = self.storage[id]
        result = dict(self.storage_latest.get(id, {}))
        status = ('disabled' if not settings.enabled else
                  'pending' if settings.adapter not in self.storage_adapters else result.get('status', 'waiting'))
        stale = round(self.config.stale_seconds*1000)
        if result.get('storage_observation') and now-result['observed_at'] >= stale:
            status = 'stale' if status in ('normal', 'warning') else status
        return {**result, **self.user_view(id), **self.group_links(storage_key(id)), 'id':id, 'name':settings.name, 'address':'',
                'hardware_kind':settings.storage_kind, 'storage_kind':settings.storage_kind,
                'enabled':settings.enabled, 'adapter':settings.adapter, 'status':status,
                'last_success_at':self.storage_last_seen.get(id), 'metrics':None, 'devices':[],
                'storage_observation':result.get('storage_observation') if status in ('normal','warning') else None}

    async def reconcile_alerts(self):
        active = {machine.id for machine in self.machines.values() if machine.enabled}
        active.update(id for id, settings in self.storage.items() if settings.enabled and settings.adapter is not None)
        await self.write(self.history.close_inactive_alerts, active, self.machines.keys() | self.storage.keys(), self.clock())

    def hardware_kind(self, machine):
        if machine.hardware_kind:
            return machine.hardware_kind
        if self.inventory.get(machine.id):
            return 'gpu'
        if not machine.require_gpu and 'gpu' not in machine.active_checks:
            return 'cpu'
        return 'unconfirmed'

    def compute_alert(self, machine, snapshot):
        kind = self.hardware_kind(machine)
        name = self.aliases.get(machine.history_key) or self.default_name(machine)
        at = snapshot['received_at']
        expires_at = snapshot['observed_at'] + snapshot.get('stale_ms', round(self.config.stale_seconds*1000))
        triggered = {}
        cleared = {}
        if snapshot['metrics'] is None:
            severity = 'critical' if snapshot['status'] == 'offline' else 'warning'
            triggered['collection'] = (severity, snapshot['reason'])
        elif at >= expires_at:
            at = expires_at
            triggered['collection'] = ('warning', 'sample_stale')
        else:
            cleared = dict.fromkeys(('collection', 'offline', 'stale'), 'collection_resumed')
        return machine.id, kind, name, at, triggered, cleared, self.last_seen.get(machine.id)

    async def check_freshness(self):
        while True:
            await self.sleep(min(5, self.config.stale_seconds))
            if not self.registry_loaded or not self.history_ok:
                continue
            async with self.settings_lock:
                now = self.clock()
                stale_targets = [self.machine_view(machine, now) for machine in self.machines.values()]
                stale_targets.extend(self.storage_view(id, now) for id in self.storage)
                try:
                    for target in stale_targets:
                        if target['status'] != 'stale':
                            continue
                        # The first stale observation is the time at which freshness expired.
                        started = target['observed_at'] + target.get('stale_ms', round(self.config.stale_seconds*1000))
                        id = target['id']
                        storage = id in self.storage
                        key = id if storage else self.machines[id].history_key
                        rule = 'stale' if storage else 'collection'
                        event = (id, target['hardware_kind'], target['name'], started,
                                 {rule: ('warning','sample_stale')}, {}, target['last_success_at'])
                        await self.write(self.history.record_stale_alert, key, storage,
                                         target.get('sample_at', target['observed_at']), event)
                except (OSError, sqlite3.Error) as error:
                    self.storage_failure(error)

    @staticmethod
    def default_name(machine):
        return machine.name or machine.id

    @staticmethod
    def with_settings(machine, settings):
        values = settings.model_dump(exclude={'alias','room_id'})
        for field in {'ssh_connect_timeout_seconds', 'hardware_kind'} | INHERITABLE_MACHINE_FIELDS:
            if field not in settings.model_fields_set:
                values.pop(field)
        if values.get('hardware_kind', machine.hardware_kind) == 'cpu':
            values['checks'] = tuple(check for check in values['checks'] if check not in ('gpu','processes'))
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

    async def verify_disambiguation_key(self, host, user, timeout, machine_id, target_os):
        try:
            async with self.slots:
                observed = await self.collector.identify(host, user, timeout, canonical_key=True, target_os=target_os)
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
                request.host, request.ssh_user, request.ssh_connect_timeout_seconds, identity.machine_id, request.target_os)
        pins = {}
        for node in matches:
            key = self.ssh_pins.get(node.history_key)
            if key is None:
                key = await self.verify_disambiguation_key(
                    node.ssh_alias, node.ssh_user, node.connect_timeout, identity.machine_id, node.target_os)
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
            options = {'target_os':request.target_os} if request.target_os != 'linux' else {}
            identity = await self.collector.identify(
                request.host, request.ssh_user, request.ssh_connect_timeout_seconds, **options)
        if request.target_os == 'windows' and not identity.ssh_host_key:
            raise CollectionError('unknown', '无法核实 Windows 节点的 ED25519 SSH 主机密钥')
        values = request.model_dump(exclude={'host', 'ssh_user', 'target_os', 'shared', 'person_id'}, exclude_unset=True)
        values.setdefault('interval_seconds', self.config.interval_seconds)
        settings = MachineSettings.model_validate(values)
        async with self.settings_lock:
            self.check_registration(request.host, request.ssh_user)
            people = () if request.person_id is None else (request.person_id,)
            self.validate_people(people)
            self.check_location(settings)
            history_id, pins = await self.resolve_collision(request, identity)
            machine = Machine(id=uuid.uuid4().hex, name=request.host[:80], mode='ssh', ssh_alias=request.host,
                              ssh_user=request.ssh_user, target_os=request.target_os,
                              expected_host_id=identity.machine_id, history_id=history_id)
            if machine.history_key in self.pending_removals:
                raise CollectionError('conflict', '此节点的历史归档正在清理，完成后可重新登记')
            if request.target_os == 'windows':
                pins[machine.history_key] = identity.ssh_host_key
            excluded = INHERITABLE_MACHINE_FIELDS.copy()
            if machine.target_os == 'linux':
                excluded.add('target_os')
            registration = machine.model_dump_json(exclude=excluded)
            return await self.save_settings(machine, settings, registration=registration, pins=pins,
                                            assignment=(people, request.shared))

    async def configure(self, id, settings):
        async with self.settings_lock:
            return await self.save_settings(self.machines[id], settings)

    async def save_settings(self, machine, settings, registration=None, pins=None, assignment=None):
        if not self.registry_loaded:
            raise OSError('机器配置暂不可读')
        selected = settings.configuration_cluster_id
        if selected is not None and selected not in self.cluster_overrides(compute_key(machine.history_key)):
            raise CollectionError('conflict', 'configuration_cluster_ineligible')

        async def save():
            updated = self.with_settings(machine, settings)
            identity = machine.history_key
            order = None
            if registration:
                machines = [*self.ordered_machines(), machine]
                order = {node.history_key:index for index,node in enumerate(machines)}
            persisted = settings.model_copy(update={'ssh_connect_timeout_seconds':updated.ssh_connect_timeout_seconds,
                                                    'hardware_kind':updated.hardware_kind})
            excluded = {'alias', 'room_id'} | (INHERITABLE_MACHINE_FIELDS - settings.model_fields_set)
            stored = persisted.model_dump_json(exclude=excluded)
            location = self.check_location(settings)
            restart = registration or (machine.enabled, machine.active_checks, self.interval(machine), machine.connect_timeout) != (
                updated.enabled, updated.active_checks, self.interval(updated), updated.connect_timeout
            )
            if restart and not registration:
                await self.stop_sampler(machine.id)
            closure = (machine.id, self.clock(), 'disabled') if not updated.enabled else None
            try:
                await self.write(self.history.save_machine, identity, registration, stored, settings.alias,
                                 pins or {}, order, assignment, closure, location)
            except (OSError, sqlite3.Error):
                if restart and not registration:
                    self.start_sampler(machine)
                raise
            if assignment is not None:
                self.set_users(identity, *assignment)
            if location is not None:
                self.set_location(compute_key(identity), location)
            if pins:
                self.ssh_pins.update(pins)
                for existing in self.machines.values():
                    if existing.history_key in pins:
                        await self.restart_sampler(existing)
            self.set_alias(identity, settings.alias)
            if order is not None:
                self.machine_order = order
            self.machines[machine.id] = updated
            if restart:
                await self.restart_sampler(updated)
            return self.machine_view(updated, self.clock())

        return await wait_for_work(asyncio.create_task(save()))

    def storage_failure(self, error):
        if self.history_ok or not getattr(self, 'history_error_reported', False):
            log.warning('监控指标库不可写 (%s)', type(error).__name__)
        self.history_ok = False
        self.history_error_reported = True

    def archive_analysis(self, machine, *, start=False):
        identity = self.machines[machine].history_key
        if not self.registry_loaded:
            raise OSError('指标库暂不可读')
        job = self.archive_analyses.get(identity)
        if start and (job is None or job.status == 'failed'):
            self.discard_archive_analysis(identity)
            job = self.archive_analyses[identity] = ArchiveAnalysis()
            job.task = asyncio.create_task(self.prepare_archive_analysis(identity, job))
        if job is None:
            raise KeyError(machine)
        if start and job.status != 'preparing':
            self.keep_archive_analysis(identity, job)
        return job.view(self.archive_zone)

    async def prepare_archive_analysis(self, identity, job):
        loop = asyncio.get_running_loop()

        def progress(percent):
            loop.call_soon_threadsafe(setattr, job, 'progress', percent)

        try:
            async with self.archive_lock:
                if job.stopped.is_set():
                    return
                await offload(job.prepare, self.history, identity, self.archive_zone, progress)
                job.status = 'ready' if job.workspace is not None else 'empty'
                job.progress = 100
        except asyncio.CancelledError:
            job.close()
            raise
        except (*PURGE_ERRORS, OverflowError) as error:
            job.status = 'failed'
            log.warning('监控归档分析未完成 (%s)', type(error).__name__)
        self.keep_archive_analysis(identity, job)

    def keep_archive_analysis(self, identity, job):
        if job.expiry is not None:
            job.expiry.cancel()
        job.expiry = asyncio.get_running_loop().call_later(
            ARCHIVE_ANALYSIS_IDLE_SECONDS, self.expire_archive_analysis, identity, job)

    def expire_archive_analysis(self, identity, job):
        if self.archive_analyses.get(identity) is job and not job.read_lock.locked():
            self.discard_archive_analysis(identity)

    def discard_archive_analysis(self, identity):
        job = self.archive_analyses.pop(identity, None)
        if job is not None:
            job.stopped.set()
            if job.expiry is not None:
                job.expiry.cancel()
            if not job.read_lock.locked():
                job.close()

    async def archive_analysis_series(self, machine, metric, first, last):
        identity = self.machines[machine].history_key
        job = self.archive_analyses.get(identity)
        if job is None or job.status != 'ready':
            raise KeyError(machine)
        start, end = archive_bounds(first, last, self.archive_zone)
        stale = round(self.config.stale_seconds * 1000)
        async with job.read_lock:
            if self.archive_analyses.get(identity) is not job:
                raise KeyError(machine)
            try:
                result = await offload(job.series, metric, start, end, stale)
                if self.archive_analyses.get(identity) is not job:
                    raise KeyError(machine)
                return result
            finally:
                if self.archive_analyses.get(identity) is job:
                    self.keep_archive_analysis(identity, job)
                else:
                    job.close()

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
                machine = self.machines[machine.id]
                snapshot = await self.observe(machine)
            self.latest[machine.id] = snapshot
            try:
                if not self.history_ok:
                    await self.write(self.history.prepare)
                await self.write(self.history.append, machine.history_key, epoch,
                                 dict(snapshot, alert_event=self.compute_alert(machine, snapshot)))
                self.history_ok = True
                self.history_error_reported = False
            except (OSError, sqlite3.Error, HistoryInUse) as error:
                self.storage_failure(error)
            # Keep the per-machine cadence and skip missed slots instead of queueing retries.
            elapsed = self.monotonic()-next_due
            next_due += interval*(1+math.floor(max(0, elapsed)/interval))

    def set_inventory(self, machine, devices, *, complete):
        if devices or complete is True:
            cards = {gpu['uuid']:{key:gpu.get(key) for key in DEVICE_FIELDS} for gpu in devices}
            if complete is False:
                for old in self.inventory.get(machine.id, []):
                    cards.setdefault(old['uuid'], old)
            self.inventory[machine.id] = list(cards.values())
        self.inventory_complete[machine.id] = complete

    async def observe(self, machine):
        started = self.clock()
        snapshot = {'observed_at':started, 'source':machine.mode, 'metrics':None}
        configuration = self.machine_idle_configuration(machine)
        snapshot['sample_idle_memory_configuration'] = configuration
        machine = machine.model_copy(update={'idle_memory_tolerance_mib':configuration['effective']})
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
                data.get('load_average') or data.get('gpus') or data.get('gpu_inventory_empty')
            ):
                if machine.target_os == 'windows' and 'gpu_inventory_complete' in data:
                    self.set_inventory(machine, [], complete=False)
                raise CollectionError('unknown', '；'.join(data.get('warnings', [])) or '已选巡检项目暂无可读指标')
            boot, counters = data['boot_id'], data.get('cpu_ticks')
            container_cpu = data.get('container_cpu')
            cpu_identity = (self.scopes[machine.id],data.get('cpu_count'))
            if container_cpu:
                cpu_identity += (container_cpu['group'],)
                counters = container_cpu['observed_ns'], container_cpu['usage_ns']
            baseline = self.cpu_baseline.get(machine.id)
            percent = None
            if machine.target_os == 'windows':
                percent = data.get('cpu_percent')
            elif baseline:
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
            self.set_inventory(machine, metrics['gpus'], complete=metrics['gpu_inventory_complete'])
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
        view = {key:result[key] for key in ('status','reason','warnings','observed_at','received_at','metrics',
                                           'sample_idle_memory_configuration') if key in result}
        configuration = self.machine_idle_configuration(machine)
        default_name = self.default_name(machine)
        alias = self.aliases.get(machine.history_key)
        stale = round(self.stale_seconds(machine)*1000)
        view.update(id=machine.id, name=alias or default_name, alias=alias, default_name=default_name,
                    **self.user_view(machine.history_key), **self.group_links(compute_key(machine.history_key)), hardware_kind=self.hardware_kind(machine),
                    configured_hardware_kind=machine.hardware_kind,
                    scope=self.scopes.get(machine.id), address=machine.display_address,
                    mode=machine.mode, target_os=machine.target_os,
                    require_gpu=machine.hardware_kind != 'cpu' and
                    (machine.require_gpu or 'gpu' in machine.active_checks or bool(self.inventory.get(machine.id))),
                    expected_gpu_count=machine.expected_gpu_count if machine.hardware_kind != 'cpu' else None, gpu_inventory_complete=self.inventory_complete.get(machine.id),
                    last_success_at=self.last_seen.get(machine.id), devices=self.inventory.get(machine.id, []),
                    enabled=machine.enabled, checks=machine.active_checks, interval_seconds=self.interval(machine),
                    ssh_connect_timeout_seconds=machine.connect_timeout,
                    idle_memory_tolerance_mib=configuration['effective'], idle_memory_configuration=configuration,
                    stale_ms=stale, metrics=view.get('metrics'))
        if not machine.enabled:
            view.update(status='disabled', metrics=None, reason=None, warnings=[])
        elif not result:
            view['status'] = 'waiting'
        elif result['metrics'] is not None and now-result['observed_at'] >= stale:
            view.update(status='stale', reason='有效样本超过时限，等待新采样', metrics=None, warnings=[])
        return view

    def resource_keys(self):
        return {**{machine.id:compute_key(machine.history_key) for machine in self.ordered_machines()},
                **{id:storage_key(id) for id in self.storage}}

    def ordered_resource_ids(self):
        keys = self.resource_keys()
        return sorted(keys, key=lambda id:self.resource_order.get(keys[id], math.inf))

    def group_links(self, key):
        return {'room_id':self.locations.get(key),
                'cluster_ids':[id for id, cluster in self.clusters.items() if key in cluster['keys']]}

    def global_idle_configuration(self):
        fallback = configuration_layer(DEFAULT_IDLE_MEMORY_TOLERANCE_MIB, 'default')
        return configuration_layer(self.global_idle_override, 'global', inherited=fallback)

    def room_idle_configuration(self, id):
        override = self.rooms[id]['idle_memory_tolerance_mib'] if id else None
        return configuration_layer(override, 'room', (id,), inherited=self.global_idle_configuration())

    def cluster_overrides(self, key):
        return {id:cluster['idle_memory_tolerance_mib'] for id, cluster in self.clusters.items()
                if key in cluster['keys'] and cluster['idle_memory_tolerance_mib'] is not None}

    def machine_idle_configuration(self, machine):
        key = compute_key(machine.history_key)
        candidates = self.cluster_overrides(key)
        ids = tuple(sorted(candidates))
        values = set(candidates.values())
        selected = machine.configuration_cluster_id
        conflict = len(values) > 1 and selected not in candidates
        inherited = self.room_idle_configuration(self.locations.get(key))
        if len(values) == 1:
            inherited = configuration_layer(next(iter(values)), 'cluster', ids)
        elif len(values) > 1 and not conflict:
            inherited = configuration_layer(candidates[selected], 'cluster', (selected,))
        override = machine.idle_memory_tolerance_mib if 'idle_memory_tolerance_mib' in machine.model_fields_set else None
        return dict(configuration_layer(override, 'machine', (machine.id,), inherited=inherited),
                    cluster_candidates=[{'id':id, 'value':candidates[id]} for id in ids],
                    selected_cluster_id=selected, cluster_conflict=conflict,
                    invalid_cluster_selection=selected is not None and selected not in candidates)

    async def configure_global_idle(self, settings):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('registry_unavailable')

            async def save():
                await self.write(self.history.save_global_idle_tolerance, settings.idle_memory_tolerance_mib)
                self.global_idle_override = settings.idle_memory_tolerance_mib
                return self.global_idle_configuration()

            return await wait_for_work(asyncio.create_task(save()))

    def forget_resource(self, key):
        self.locations.pop(key, None)
        self.resource_order.pop(key, None)
        for cluster in self.clusters.values():
            cluster['keys'] = tuple(member for member in cluster['keys'] if member != key)

    def check_location(self, settings):
        if 'room_id' not in settings.model_fields_set:
            return None
        if settings.room_id is not None and settings.room_id not in self.rooms:
            raise CollectionError('conflict', 'room_missing')
        return settings

    def set_location(self, key, location):
        if location.room_id is None:
            self.locations.pop(key, None)
        else:
            self.locations[key] = location.room_id

    def group_views(self, views):
        by_key = {key:views[id] for id,key in self.resource_keys().items() if id in views}
        grouped = defaultdict(list)
        for key, view in by_key.items():
            if room := self.locations.get(key):
                grouped[room].append(view)
        rooms = []
        for id, room in self.rooms.items():
            members = grouped[id]
            owner = self.people.get(room['owner_id'])
            rooms.append({**room, 'owner':owner,'members':[node['id'] for node in members],
                          'idle_memory_configuration':self.room_idle_configuration(id),
                          'summary':summarize_resources(members)})
        clusters = []
        for id, cluster in self.clusters.items():
            members = [by_key[key] for key in cluster['keys'] if key in by_key]
            room_counts = defaultdict(int)
            for node in members:
                room_counts[node['room_id']] += 1
            cluster_fields = {key:value for key,value in cluster.items() if key != 'keys'}
            clusters.append({**cluster_fields,'shared':bool(cluster['shared']),'person':self.people.get(cluster['person_id']),
                             'idle_memory_configuration':configuration_layer(cluster['idle_memory_tolerance_mib'],
                                                                             'cluster', (id,)),
                             'members':[node['id'] for node in members], 'summary':summarize_resources(members),
                             'rooms':[{'id':room,'count':count} for room,count in room_counts.items()]})
        return {'rooms':sorted(rooms,key=lambda group:group['name']),
                'clusters':sorted(clusters,key=lambda group:group['name'])}

    async def save_group(self, kind, body, id=None):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('registry_unavailable')
            groups = self.rooms if kind == 'room' else self.clusters
            if id is not None and id not in groups:
                raise KeyError(id)
            if any(other != id and group['name'] == body.name for other, group in groups.items()):
                raise CollectionError('conflict','group_name_taken')
            person = body.owner_id if kind == 'room' else body.person_id
            if person is not None:
                self.validate_people((person,))
            id = id or uuid.uuid4().hex
            override = body.idle_memory_tolerance_mib
            if 'idle_memory_tolerance_mib' not in body.model_fields_set and id in groups:
                override = groups[id]['idle_memory_tolerance_mib']
            if kind == 'room':
                record = dict(id=id,name=body.name,location=body.location,owner_id=body.owner_id)
                operation = self.history.save_room
                args = (id,body)
            else:
                resources = self.resource_keys()
                if any(member not in resources for member in body.members):
                    raise CollectionError('conflict','group_member_missing')
                members = tuple(resources[member] for member in body.members)
                record = dict(id=id,name=body.name,person_id=body.person_id,shared=body.shared,keys=members)
                operation = self.history.save_cluster
                args = (id,body,members)
            record['idle_memory_tolerance_mib'] = override

            async def save():
                await self.write(operation,*args)
                groups[id] = record
                return {'id':id}

            return await wait_for_work(asyncio.create_task(save()))

    async def delete_group(self, kind, id):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('registry_unavailable')
            groups = self.rooms if kind == 'room' else self.clusters
            if id not in groups:
                raise KeyError(id)

            async def delete():
                await self.write(self.history.delete_group, kind, id)
                del groups[id]
                if kind == 'room':
                    self.locations = {key:room for key,room in self.locations.items() if room != id}

            await wait_for_work(asyncio.create_task(delete()))

    async def place_resource(self, id, location):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('registry_unavailable')
            self.check_location(location)
            key = self.resource_keys()[id]

            async def save():
                await self.write(self.history.save_resource_location, key, location)
                self.set_location(key,location)
                return {'id':id,'room_id':location.room_id}

            return await wait_for_work(asyncio.create_task(save()))

    def person_references(self, person):
        views = {machine.history_key:self.aliases.get(machine.history_key) or self.default_name(machine)
                 for machine in self.machines.values()}
        views.update({id:settings.name for id,settings in self.storage.items()})
        return {'devices':[views[key] for key,ids in self.machine_assignees.items() if person in ids and key in views],
                'rooms':[room['name'] for room in self.rooms.values() if room['owner_id'] == person],
                'clusters':[cluster['name'] for cluster in self.clusters.values() if cluster['person_id'] == person]}

    async def reorder_resources(self, ids):
        async with self.settings_lock:
            if not self.registry_loaded:
                raise OSError('registry_unavailable')
            keys = self.resource_keys()
            if len(ids) != len(keys) or set(ids) != keys.keys():
                raise CollectionError('conflict','resource_list_changed')
            return await self.persist_resource_order(ids, keys)

    async def persist_resource_order(self, ids, keys):
        order = {keys[id]:index for index,id in enumerate(ids)}
        machines = {self.machines[id].history_key:index
                    for index,id in enumerate(id for id in ids if id in self.machines)}

        async def save():
            await self.write(self.history.save_resource_order, order, machines)
            self.resource_order = order
            self.machine_order = machines

        await wait_for_work(asyncio.create_task(save()))
        return {'resources':ids}

    def snapshot(self):
        now = self.clock()
        machines = [self.machine_view(machine, now) for machine in self.ordered_machines()]
        storage = [self.storage_view(id, now) for id in self.storage]
        views = {node['id']:node for node in (*machines,*storage)}
        return {'server_time':now, 'period_ms':round(self.config.interval_seconds*1000),
                'default_ssh_connect_timeout_seconds':DEFAULT_SSH_CONNECT_TIMEOUT,
                'stale_ms':round(self.config.stale_seconds*1000), 'history_writable':self.history_ok,
                'archive_ok':self.archive_ok, 'registry_loaded':self.registry_loaded,
                'removal_pending':len(self.pending_removals),
                'machine_history_hours':WARM_HOURS,
                'people':self.person_views(self.people),
                'storage':storage, 'groups':self.group_views(views),
                'resource_order':self.ordered_resource_ids(), 'summary':summarize_resources(views.values(), overview=True),
                'storage_adapters':sorted(self.storage_adapters),
                'idle_memory_configuration':self.global_idle_configuration(),
                'machines':machines}

    async def group_series(self, kind, selected, metric):
        roster = self.rooms if kind == 'room' else self.clusters
        if any(id not in roster for id in selected):
            raise KeyError('group_missing')
        ids = selected or tuple(sorted(roster, key=lambda id:roster[id]['name'])[:6])
        now = self.clock()
        start = now-DAY_MS
        defaults = {
            compute_key(machine.history_key):{'scope':self.scopes.get(machine.id) or 'host',
                                              'expected_gpu_count':machine.expected_gpu_count if machine.hardware_kind != 'cpu' else None}
            for machine in self.machines.values()
        }
        defaults.update({storage_key(id):{'storage_kind':settings.storage_kind,
                                         'stale_ms':round(self.config.stale_seconds*1000)}
                         for id,settings in self.storage.items()})
        groups = []
        keys = set()
        for id in ids:
            members = (key for key, room in self.locations.items() if room == id) if kind == 'room' else roster[id]['keys']
            current = [key for key in members if key in defaults]
            groups.append({'id':id,'name':roster[id]['name'],'keys':current})
            keys.update(current)
        async with self.readers:
            def series():
                ticks = self.history.group_ticks(keys, start, now) if keys else {}
                return group_history_data(groups, defaults, ticks, start, now, metric)

            return await asyncio.to_thread(series)

    async def alert_events(self, active, limit, offset):
        async with self.readers:
            return await asyncio.to_thread(self.history.alert_events, active, limit, offset)

    async def alert_event(self, id):
        async with self.readers:
            return await asyncio.to_thread(self.history.alert_event, id)

    async def storage_series(self, id, hours, metric):
        now = self.clock()
        start = now-hours*3_600_000
        bucket = max(round(self.config.interval_seconds*1000), math.ceil((now-start)/MAX_POINTS))
        async with self.readers:
            ticks = await asyncio.to_thread(self.history.storage_history, id, start, now)
        stale = round(self.config.stale_seconds*1000)
        rows = []
        for tick in ticks:
            observation = tick['observation'] or {}
            capacity = observation.get('capacity')
            if metric == 'storage':
                value = 100*capacity['used_bytes']/capacity['total_bytes'] if capacity and capacity['total_bytes'] else None
            else:
                rate = observation.get(f"{metric.removeprefix('storage_')}_bytes_per_second")
                value = rate/(1024**2) if rate is not None else None
            rows.append((tick['observed_at'], observation.get('identity'), 'storage', value, None, stale))
        return {'from':start,'to':now,'bucket_ms':bucket,'keys':[metric],
                'points':downsample(rows, start, bucket, stale)}

    async def series(self, machine, gpu, metric, hours):
        enabled = [item for item in self.machines.values() if item.enabled]
        if machine is None:
            period = self.config.interval_seconds
        else:
            configured = next((item for item in self.machines.values() if item.history_key == machine), None)
            period = min(self.interval(configured), self.config.interval_seconds) if configured else self.config.interval_seconds
        async with self.readers:
            result = await asyncio.to_thread(self.history.series, [item.history_key for item in enabled],
                                             machine, gpu, metric, hours, self.clock(),
                                             round(period*1000), round(self.config.stale_seconds*1000))
        if machine is None:
            result['machines'] = [item.id for item in enabled]
        return result
