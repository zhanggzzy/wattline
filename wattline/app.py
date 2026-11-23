from contextlib import asynccontextmanager
import base64
import binascii
import hmac
from pathlib import Path
import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .collector import CollectionError
from .config import AliasUpdate, MachineOrder, MachineRegistration, MachineRemoval, MachineSettings
from .history import GPU_METRICS, HOST_METRICS, OVERVIEW_METRICS, WARM_HOURS
from .service import Monitor


STATIC = Path(__file__).with_name('static')


def same_origin_json(request: Request):
    if request.headers.get('sec-fetch-site') not in (None, 'same-origin'):
        raise HTTPException(403, '机器设置须从同源工作台发起')
    if request.headers.get('content-type', '').split(';',1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, '机器设置需要 JSON 请求')


def create_app(config, *, monitor=None):
    service = monitor if monitor is not None else Monitor(config)
    password = None
    if config.viewer_password_file is not None:
        password = config.viewer_password_file.read_bytes().rstrip(b'\r\n')
        if not password or b'\n' in password or b'\r' in password:
            raise ValueError('viewer_password_file 须包含一个非空密码')
        expected = config.viewer_username.encode() + b':' + password

    @asynccontextmanager
    async def lifespan(app):
        try:
            await service.start()
            yield
        finally:
            await service.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1','localhost'], www_redirect=False)
    app.mount('/static', StaticFiles(directory=STATIC), name='static')

    @app.middleware('http')
    async def access(request: Request, call_next):
        accepted = password is None
        if password is not None:
            scheme, _, credential = request.headers.get('authorization', '').partition(' ')
            if scheme.lower() == 'basic' and len(credential) <= 4096:
                try:
                    accepted = hmac.compare_digest(base64.b64decode(credential, validate=True), expected)
                except (binascii.Error, ValueError):
                    pass
        if accepted:
            response = await call_next(request)
        else:
            response = PlainTextResponse('监控访问需要认证', status_code=401,
                headers={'WWW-Authenticate':'Basic realm="Wattline", charset="UTF-8"'})
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src data:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
        )
        return response

    @app.get('/')
    async def index():
        return FileResponse(STATIC/'index.html')

    @app.get('/api/snapshot')
    async def snapshot():
        return service.snapshot()

    @app.put('/api/machines/order', dependencies=[Depends(same_origin_json)])
    async def order(body: MachineOrder):
        try:
            return await service.reorder(body.machines)
        except CollectionError as error:
            raise HTTPException(409, str(error)) from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, '机器排序暂时无法保存，请稍后重试') from error

    @app.post('/api/machines', status_code=201, dependencies=[Depends(same_origin_json)])
    async def register(body: MachineRegistration):
        try:
            return await service.register(body)
        except CollectionError as error:
            code = {'conflict':409, 'offline':502}.get(error.status, 422)
            raise HTTPException(code, str(error)) from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, '机器暂时无法保存，请稍后重试') from error

    @app.put('/api/machines/{machine}/settings', dependencies=[Depends(same_origin_json)])
    async def settings(machine: str, body: MachineSettings):
        try:
            return await service.configure(machine, body)
        except KeyError as error:
            raise HTTPException(404, '监控机器不存在') from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, '机器设置暂时无法保存，请稍后重试') from error

    @app.put('/api/machines/{machine}/alias', dependencies=[Depends(same_origin_json)])
    async def alias(machine: str, body: AliasUpdate):
        try:
            return await service.change_alias(machine, body.alias)
        except KeyError as error:
            raise HTTPException(404, '监控机器不存在') from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, '别名暂时无法保存，请稍后重试') from error

    @app.delete('/api/machines/{machine}', dependencies=[Depends(same_origin_json)])
    async def remove(machine: str, body: MachineRemoval, response: Response):
        try:
            result = await service.remove(machine)
        except KeyError as error:
            raise HTTPException(404, '监控机器不存在') from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, '机器暂时无法移除，请稍后重试') from error
        if result['cleanup_pending']:
            response.status_code = 202
        return result

    @app.get('/api/history')
    async def history(machine: str | None = Query(None, max_length=64),
                      gpu: str | None = Query(None, pattern=r'^GPU-[a-zA-Z0-9-]{1,80}$'),
                      metric: str | None = Query(None, max_length=12),
                      hours: int = Query(24, ge=1, le=WARM_HOURS)):
        key = None
        if machine is not None:
            if machine not in service.machines:
                raise HTTPException(404, '监控机器不存在')
            key = service.machines[machine].history_key
            available = GPU_METRICS if gpu else HOST_METRICS
            metric = metric or ('gpu' if gpu else 'cpu')
            if metric not in available:
                raise HTTPException(422, '此范围不支持该指标')
        else:
            if gpu:
                raise HTTPException(422, '请为设备指标指定机器')
            metric = metric or 'gpu'
            if metric not in OVERVIEW_METRICS:
                raise HTTPException(422, '总览不支持该指标')
            if hours > 24:
                raise HTTPException(422, '机器总览最多支持 24 小时，请在机器详情查看更长窗口')
        try:
            return await service.series(key, gpu, metric, hours)
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, '历史指标库暂时不可读') from error

    return app
