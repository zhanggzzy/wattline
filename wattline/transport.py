"""Bounded subprocess and SSH transport for the monitoring probes."""
import asyncio
from ipaddress import IPv6Address
import os
import re
import shlex
import signal


DEFAULT_SSH_CONNECT_TIMEOUT = 5


class TransportError(Exception):
    pass


async def command(argv, payload=b'', timeout=15, limit=1024*1024):
    process = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True,
        env={key:value for key,value in os.environ.items() if key in ('PATH','HOME','LANG','LC_ALL','SSH_AUTH_SOCK')})
    async def read(stream):
        result = bytearray()
        while chunk := await stream.read(16384):
            result.extend(chunk)
            if len(result)>limit:
                raise TransportError('节点检查输出超过上限')
        return bytes(result)
    async def io():
        process.stdin.write(payload)
        await process.stdin.drain()
        process.stdin.close()
        output, error = await asyncio.gather(read(process.stdout),read(process.stderr))
        return await process.wait(), output, error
    try:
        return await asyncio.wait_for(io(),timeout)
    finally:
        if process.returncode is None:
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            await process.wait()


def valid_ssh_destination(value):
    if not isinstance(value, str) or len(value) > 128:
        return False
    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',value):
        return True
    if ':' in value and '%' not in value:
        try:
            IPv6Address(value)
            return True
        except ValueError:
            pass
    return False


def ssh_command(alias, argv, *, connect_timeout=DEFAULT_SSH_CONNECT_TIMEOUT):
    if not valid_ssh_destination(alias):
        raise TransportError('SSH 别名格式无效')
    prefix = ['ssh','-T','-oBatchMode=yes','-oStrictHostKeyChecking=yes','-oPasswordAuthentication=no',
              '-oKbdInteractiveAuthentication=no','-oForwardAgent=no','-oClearAllForwardings=yes',
              f'-oConnectTimeout={connect_timeout}']
    return prefix + [alias,shlex.join(argv)]
