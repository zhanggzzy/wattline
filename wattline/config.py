from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .transport import DEFAULT_SSH_CONNECT_TIMEOUT, valid_ssh_destination


Check = Literal['gpu', 'processes', 'cpu', 'memory', 'system']
DEFAULT_CHECKS = ('gpu', 'processes', 'cpu', 'memory', 'system')
SSH_USER = r'^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,63}$'
HOST_KEY = r'SHA256:[A-Za-z0-9+/]{43}'
MachineId = Annotated[str, Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$')]


class AliasUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    alias: str | None = Field(max_length=80)

    @field_validator('alias')
    @classmethod
    def validate_alias(cls, value):
        if value and any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('别名须为单行文字')
        return value or None


class MachineSettings(AliasUpdate):
    alias: str | None = Field(default=None, max_length=80)
    assigned_user: str | None = Field(default=None, max_length=80)
    enabled: bool = True
    checks: tuple[Check, ...] = Field(default=DEFAULT_CHECKS, max_length=len(DEFAULT_CHECKS))
    interval_seconds: float = Field(default=10, ge=1, le=300)
    ssh_connect_timeout_seconds: int = Field(default=DEFAULT_SSH_CONNECT_TIMEOUT, ge=1, le=60)

    @field_validator('assigned_user')
    @classmethod
    def validate_assigned_user(cls, value):
        if value and any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('使用者须为单行文字')
        return value or None

    @field_validator('checks')
    @classmethod
    def validate_checks(cls, checks):
        if len(set(checks)) != len(checks):
            raise ValueError('巡检项目不能重复')
        if 'processes' in checks and 'gpu' not in checks:
            raise ValueError('巡检 GPU 进程需要启用 GPU 指标')
        return checks

    @model_validator(mode='after')
    def validate_enabled_checks(self):
        if self.enabled and not self.checks:
            raise ValueError('启用巡检时至少选择一个巡检项目')
        return self


class MachineRegistration(MachineSettings):
    host: str = Field(min_length=1, max_length=128)
    ssh_user: str | None = Field(default=None, pattern=SSH_USER)

    @field_validator('host')
    @classmethod
    def validate_host(cls, value):
        if not valid_ssh_destination(value):
            raise ValueError('请输入 IP、主机名或已有 SSH 别名')
        return value


class MachineOrder(BaseModel):
    model_config = ConfigDict(extra='forbid')
    machines: tuple[MachineId, ...] = Field(max_length=128)

    @field_validator('machines')
    @classmethod
    def unique_ids(cls, ids):
        if len(set(ids)) != len(ids):
            raise ValueError('机器排序不能包含重复的 ID')
        return ids


class MachineRemoval(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirm: Literal[True]


class Machine(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, str_strip_whitespace=True)

    id: MachineId
    name: str | None = Field(default=None, min_length=1, max_length=80)
    address: str | None = Field(default=None, min_length=1, max_length=128)
    mode: Literal['local', 'ssh']
    ssh_alias: str | None = None
    ssh_user: str | None = Field(default=None, pattern=SSH_USER)
    expected_host_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    history_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    enabled: bool = True
    checks: tuple[Check, ...] | None = None
    interval_seconds: float | None = Field(default=None, ge=1, le=300)
    ssh_connect_timeout_seconds: int = Field(default=DEFAULT_SSH_CONNECT_TIMEOUT, ge=1, le=60)
    require_gpu: bool = True
    expected_gpu_count: int | None = Field(default=None, ge=1, le=256)
    idle_memory_tolerance_mib: float = Field(default=0, ge=0, allow_inf_nan=False)
    host_proc: Path | None = None
    host_machine_id: Path | None = None

    @model_validator(mode='after')
    def validate_transport(self):
        if self.mode == 'ssh' and not valid_ssh_destination(self.ssh_alias):
            raise ValueError('SSH 节点需要现有 ssh_alias')
        if self.mode == 'local' and (self.ssh_alias or self.ssh_user):
            raise ValueError('本机节点不能配置 SSH 连接参数')
        if any(path and not path.is_absolute() for path in (self.host_proc, self.host_machine_id)):
            raise ValueError('宿主路径需要使用绝对路径')
        if not self.require_gpu and self.expected_gpu_count:
            raise ValueError('纯 CPU 节点不配置预期卡数')
        if self.checks is not None:
            MachineSettings(enabled=self.enabled, checks=self.checks)
        return self

    @property
    def active_checks(self):
        if self.checks is not None:
            return self.checks
        return DEFAULT_CHECKS if self.require_gpu else ('cpu', 'memory', 'system')

    @property
    def display_address(self):
        if self.address:
            return self.address
        if self.ssh_user:
            return f'{self.ssh_user}@{self.ssh_alias}'
        return self.ssh_alias or '本机'

    @property
    def connect_timeout(self):
        return self.ssh_connect_timeout_seconds if self.mode == 'ssh' else None

    @property
    def history_key(self):
        return self.history_id or self.expected_host_id


class Config(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    data_dir: Path
    machines: tuple[Machine, ...] = Field(default=(), max_length=128)
    port: int = Field(default=8090, ge=1024, le=65535)
    archive_timezone: str = 'UTC'
    interval_seconds: float = Field(default=10, ge=1, le=300)
    stale_seconds: float = Field(default=30, ge=2, le=900)
    timeout_seconds: float = Field(default=12, gt=0, le=120)
    gpu_timeout_seconds: float = Field(default=6, gt=0, le=60)
    concurrency: int = Field(default=4, ge=1, le=32)
    viewer_username: str = Field(default='monitor', pattern=r'^[a-zA-Z0-9_.-]{1,80}$')
    viewer_password_file: Path | None = None

    @field_validator('archive_timezone')
    @classmethod
    def validate_archive_timezone(cls, name):
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError('归档时区须为有效的 IANA 时区名') from error
        return name

    def probe_timeout(self, connect_timeout):
        extra = max(0, (connect_timeout or DEFAULT_SSH_CONNECT_TIMEOUT) - DEFAULT_SSH_CONNECT_TIMEOUT)
        return self.timeout_seconds + extra

    @model_validator(mode='after')
    def validate_monitor(self):
        if len({m.id for m in self.machines}) != len(self.machines):
            raise ValueError('机器 ID 不能重复')
        if len({m.history_key for m in self.machines}) != len(self.machines):
            raise ValueError('机器历史 ID 不能重复')
        if len({m.expected_host_id for m in self.machines}) != len(self.machines):
            raise ValueError('同一宿主只能登记一次')
        if self.stale_seconds <= max(self.interval_seconds, self.timeout_seconds):
            raise ValueError('过期时长须大于采集周期和单次超时')
        if self.gpu_timeout_seconds >= self.timeout_seconds:
            raise ValueError('GPU 查询超时须小于整机采集超时')
        return self

    @classmethod
    def read(cls, path):
        path = Path(path).resolve()
        value = cls.model_validate_json(path.read_text())
        paths = {'data_dir':path.parent/value.data_dir}
        if value.viewer_password_file:
            paths['viewer_password_file'] = path.parent/value.viewer_password_file
        return value.model_copy(update=paths)
