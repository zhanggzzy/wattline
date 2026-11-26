from contextlib import asynccontextmanager
import base64
import binascii
from datetime import date
import hmac
from pathlib import Path
import sqlite3
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Path as PathParameter, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .collector import CollectionError
from .config import (
    AliasUpdate, MachineAssignees, MachineId, MachineOrder, MachineRegistration, MachineRemoval, MachineSettings, PersonName,
)
from .groups import ClusterSettings, ResourceLocation, ResourceOrder, RoomSettings
from .history import GPU_METRICS, HOST_METRICS, OVERVIEW_METRICS, WARM_HOURS
from .resources import StorageSettings
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
        snapshot = service.snapshot()
        try:
            snapshot['alerts'] = await service.alert_events(True, 3, 0)
        except (OSError, sqlite3.Error):
            snapshot['alerts'] = None
        return snapshot

    async def store_person(body: PersonName, person: int | None = None):
        try:
            return await service.save_person(body.name, person)
        except KeyError as error:
            raise HTTPException(404, 'person_missing') from error
        except CollectionError as error:
            raise HTTPException(409, str(error)) from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, 'people_save_failed') from error

    @app.post('/api/people', status_code=201, dependencies=[Depends(same_origin_json)])
    async def create_person(body: PersonName):
        return await store_person(body)

    @app.put('/api/people/{person}', dependencies=[Depends(same_origin_json)])
    async def rename_person(person: int, body: PersonName):
        return await store_person(body, person)

    @app.delete('/api/people/{person}', status_code=204, dependencies=[Depends(same_origin_json)])
    async def delete_person(person: int, include_references: bool = False):
        try:
            await service.delete_person(person)
        except KeyError as error:
            raise HTTPException(404, 'person_missing') from error
        except CollectionError as error:
            detail = {'code':str(error), 'references':error.references} if include_references else str(error)
            raise HTTPException(409, detail) from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, 'people_save_failed') from error

    @app.put('/api/machines/{machine}/assignees', dependencies=[Depends(same_origin_json)])
    async def configure_assignees(machine: str, body: MachineAssignees):
        try:
            return await service.configure_assignees(machine, body.person_ids, body.mode == 'shared')
        except KeyError as error:
            raise HTTPException(404, 'assignee_machine_missing') from error
        except CollectionError as error:
            raise HTTPException(409, str(error)) from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, 'people_save_failed') from error

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
        except CollectionError as error:
            raise HTTPException(409, str(error)) from error
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

    async def save_storage(body, id=None):
        try:
            return await service.configure_storage(body, id)
        except KeyError as error:
            raise HTTPException(404, 'storage_missing') from error
        except CollectionError as error:
            raise HTTPException(409, str(error)) from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, 'resource_save_failed') from error

    @app.post('/api/storage', status_code=201, dependencies=[Depends(same_origin_json)])
    async def add_storage(body: StorageSettings):
        return await save_storage(body)

    @app.put('/api/storage/{id}', dependencies=[Depends(same_origin_json)])
    async def edit_storage(id: str, body: StorageSettings):
        return await save_storage(body, id)

    @app.put('/api/storage/{id}/assignees', dependencies=[Depends(same_origin_json)])
    async def storage_assignees(id: str, body: MachineAssignees):
        try:
            return await service.configure_assignees(id, body.person_ids, body.mode == 'shared', storage=True)
        except KeyError as error:
            raise HTTPException(404, 'storage_missing') from error
        except CollectionError as error:
            raise HTTPException(409, str(error)) from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, 'resource_save_failed') from error

    @app.delete('/api/storage/{id}', dependencies=[Depends(same_origin_json)])
    async def remove_storage(id: str, body: MachineRemoval):
        try:
            return await service.remove_storage(id)
        except KeyError as error:
            raise HTTPException(404, 'storage_missing') from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, 'resource_save_failed') from error

    @app.get('/api/storage/{id}/history')
    async def storage_history(id: str, hours: int = Query(24, ge=1, le=WARM_HOURS),
                              metric: Literal['storage', 'storage_read', 'storage_write'] = 'storage'):
        if id not in service.storage:
            raise HTTPException(404, 'storage_missing')
        try:
            return await service.storage_series(id, hours, metric)
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, 'historical_metrics_unavailable') from error

    @app.get('/api/alerts')
    async def alerts(active: bool = False, limit: int = Query(200, ge=1, le=200),
                     offset: int = Query(0, ge=0, le=2**31-1)):
        try:
            return await service.alert_events(active, limit, offset)
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, 'alerts_unavailable') from error

    @app.get('/api/alerts/{id}')
    async def alert_event(id: Annotated[int, PathParameter(gt=0, le=2**53-1)]):
        try:
            return await service.alert_event(id)
        except KeyError as error:
            raise HTTPException(404, 'alert_missing') from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, 'alerts_unavailable') from error

    async def group_mutation(operation, *args):
        try:
            return await operation(*args)
        except KeyError as error:
            raise HTTPException(404, 'group_or_resource_missing') from error
        except CollectionError as error:
            raise HTTPException(409, str(error)) from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, 'group_save_failed') from error

    @app.post('/api/rooms', status_code=201, dependencies=[Depends(same_origin_json)])
    async def add_room(body: RoomSettings):
        return await group_mutation(service.save_group, 'room', body)

    @app.put('/api/rooms/{id}', dependencies=[Depends(same_origin_json)])
    async def edit_room(id: str, body: RoomSettings):
        return await group_mutation(service.save_group, 'room', body, id)

    @app.delete('/api/rooms/{id}', status_code=204, dependencies=[Depends(same_origin_json)])
    async def remove_room(id: str, body: MachineRemoval):
        await group_mutation(service.delete_group, 'room', id)

    @app.post('/api/clusters', status_code=201, dependencies=[Depends(same_origin_json)])
    async def add_cluster(body: ClusterSettings):
        return await group_mutation(service.save_group, 'cluster', body)

    @app.put('/api/clusters/{id}', dependencies=[Depends(same_origin_json)])
    async def edit_cluster(id: str, body: ClusterSettings):
        return await group_mutation(service.save_group, 'cluster', body, id)

    @app.delete('/api/clusters/{id}', status_code=204, dependencies=[Depends(same_origin_json)])
    async def remove_cluster(id: str, body: MachineRemoval):
        await group_mutation(service.delete_group, 'cluster', id)

    @app.put('/api/resources/order', dependencies=[Depends(same_origin_json)])
    async def order_resources(body: ResourceOrder):
        return await group_mutation(service.reorder_resources, body.resources)

    @app.put('/api/resources/{id}/room', dependencies=[Depends(same_origin_json)])
    async def place_resource(id: str, body: ResourceLocation):
        return await group_mutation(service.place_resource, id, body)

    @app.get('/api/group-history')
    async def group_history(kind: Literal['room','cluster'],
                            metric: Literal['cpu','memory_used','memory','gpu','power','storage'] = 'cpu',
                            group: Annotated[list[MachineId] | None, Query(max_length=6)] = None):
        selected = tuple(dict.fromkeys(group or ()))
        try:
            return await service.group_series(kind, selected, metric)
        except KeyError as error:
            raise HTTPException(404, 'group_missing') from error
        except (OSError, sqlite3.Error) as error:
            raise HTTPException(503, 'historical_metrics_unavailable') from error

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

    @app.post('/api/machines/{machine}/archive-analysis', dependencies=[Depends(same_origin_json)])
    @app.get('/api/machines/{machine}/archive-analysis')
    async def archive_analysis(machine: MachineId, request: Request):
        try:
            return service.archive_analysis(machine, start=request.method == 'POST')
        except KeyError as error:
            raise HTTPException(404, 'archive_analysis_missing') from error
        except OSError as error:
            raise HTTPException(503, 'historical_metrics_unavailable') from error

    @app.get('/api/machines/{machine}/archive-analysis/series')
    async def archive_analysis_series(machine: MachineId, start: date, end: date, metric: str = 'cpu'):
        if machine not in service.machines:
            raise HTTPException(404, 'archive_analysis_missing')
        if start > end or metric not in HOST_METRICS:
            raise HTTPException(422, 'archive_analysis_invalid_range_or_metric')
        try:
            return await service.archive_analysis_series(machine, metric, start, end)
        except KeyError as error:
            raise HTTPException(409, 'archive_analysis_missing') from error
        except (OSError, sqlite3.Error, TypeError, ValueError) as error:
            raise HTTPException(503, 'historical_metrics_unavailable') from error

    return app
