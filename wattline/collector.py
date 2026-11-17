import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys

from . import host_probe
from .transport import TransportError, command, ssh_command
from .config import HOST_KEY


class CollectionError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class HostIdentity:
    machine_id: str
    ssh_host_key: str | None


def handshake_key(stderr):
    # Remote stderr can only arrive after login. Read the client's handshake log.
    handshake, authenticated, _ = stderr.partition(b'Authenticated to ')
    if authenticated:
        match = re.search(rb'(?m)^debug1: Server host key: ssh-ed25519 (' + HOST_KEY.encode() + rb')\r?$', handshake)
        if match:
            return match[1].decode()
    return None


class Collector:
    """Run the same fixed, standard-library probe locally or over a configured SSH destination."""
    def __init__(self, config, run=command):
        self.config = config
        self.run = run
        self.script = Path(host_probe.__file__).read_text()

    def ssh(self, host, user, args, connect_timeout, *, inspect_key=False, canonical_key=False):
        argv = ssh_command(host, ['python3', *args], connect_timeout=connect_timeout)
        argv[1:1] = ['-oPreferredAuthentications=publickey', '-oUpdateHostKeys=no', '-oPermitLocalCommand=no']
        if user:
            argv[1:1] = ['-l', user]
        if inspect_key or canonical_key:
            argv[1:1] = ['-v', '-oFingerprintHash=sha256', '-oControlMaster=no', '-oControlPath=none']
        if canonical_key:
            argv[1:1] = ['-oHostKeyAlgorithms=ssh-ed25519']
        return argv

    async def identify(self, host, user, connect_timeout, *, canonical_key=False):
        argv = self.ssh(host, user, ['-c', self.script, '--monitor-identity'], connect_timeout,
                        inspect_key=True, canonical_key=canonical_key)
        data, stderr = await self.probe(argv, {'mode':'ssh'}, connect_timeout)
        identity = data.get('host_id')
        if not isinstance(identity, str) or not re.fullmatch(r'[a-f0-9]{32}', identity) or not data.get('boot_id'):
            raise CollectionError('unknown', '无法核实 Linux 机器身份，请检查 machine-id 和读取权限')
        return HostIdentity(identity, handshake_key(stderr))

    async def probe(self, argv, options, connect_timeout):
        try:
            code, stdout, stderr = await self.run(argv, json.dumps(options).encode(), self.config.probe_timeout(connect_timeout))
            if options['mode'] == 'ssh' and code == 255:
                raise CollectionError('offline', 'SSH 连接失败，请确认工作台所在机器能通过公钥登录，且主机密钥已受信任')
            result = json.loads(stdout)
            if code and result.get('error') == '宿主身份与固定配置不符':
                raise CollectionError('unknown', '宿主身份与固定配置不符')
            if code or not isinstance(result.get('data'), dict):
                raise CollectionError('unknown', '宿主探测未返回可用数据')
            return result['data'], stderr
        except (asyncio.TimeoutError, BrokenPipeError) as error:
            raise CollectionError('offline', '采集连接中断或超时') from error
        except (TransportError, OSError, TypeError, ValueError, AttributeError) as error:
            raise CollectionError('unknown', '无法运行探测或解析宿主响应') from error

    async def __call__(self, machine, *, ssh_host_key=None):
        options = machine.model_dump(mode='json', exclude_none=True, include={
            'mode', 'expected_host_id', 'expected_gpu_count', 'host_proc', 'host_machine_id',
            'idle_memory_tolerance_mib',
        })
        options.update(gpu_timeout=self.config.gpu_timeout_seconds, checks=machine.active_checks,
                       monitor_container_resources=True)
        args = ['-c', self.script, '--monitor']
        timeout = machine.connect_timeout
        if timeout is not None:
            argv = self.ssh(machine.ssh_alias, machine.ssh_user, args, timeout, canonical_key=ssh_host_key is not None)
        else:
            argv = [sys.executable, *args]
        data, stderr = await self.probe(argv, options, timeout)
        if ssh_host_key is not None and handshake_key(stderr) != ssh_host_key:
            raise CollectionError('unknown', 'SSH 主机密钥指纹与登记记录不一致')
        if data.get('host_id') != machine.expected_host_id or not data.get('boot_id'):
            raise CollectionError('unknown', '无法核实固定宿主或启动身份')
        return data


def cpu_percent(previous, current):
    if not previous or not current or len(previous) != 8 or len(current) != 8:
        return None
    deltas = [after - before for before, after in zip(previous, current)]
    total = sum(deltas)
    if min(deltas) < 0 or total <= 0:
        return None
    return round(100 * (total - deltas[3] - deltas[4]) / total, 2)
