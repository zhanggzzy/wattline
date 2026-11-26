# AN-222 实施验证

验证日期为 2026-11-26 UTC。此记录由实现者执行，对应 [任务 1.1、2.1 和 3.1](tasks.md)。AN-221 独立审查和 Mika 的远端交付保留待办。

## 基准与被审改动

- 接手时本地 `main` 在 `0123c748d9c628902105738a7e5a080aaf3e92d4`。`git fetch --no-tags origin main`、`git merge --ff-only origin/main` 均退出 0，实际实施和运行验证基准为 `10f966f2d0da4390d3de5502b0dadcab85056642`。
- 交接的本地提交与本记录在同一个 Git 提交中。用 `git log -1 --format=%H -- openspec/changes/add-machine-archive-analysis/verification.md` 定位提交，用 `git show --stat` 和 `git show` 查看实际改动。
- 开发期间 `git ls-remote origin refs/heads/main` 观察到远端推进至 `deaa3269f158d1da33219e077d0176c1ef520ef2`。使用隔离索引对该远端快照做三方补丁检查，结果见下方。产品运行验证基于被审提交的实际基准 `10f966f`。
- Git 索引里的 `AGENTS.md` 只有通用仓库约定。本地 runtime 注入保留在工作树。

## 命令与实测结果

| 命令 | 退出码 | 输出摘要 |
| --- | ---: | --- |
| `.venv/bin/python --version`、`.venv/bin/python -m pip check` | 0 | Python 3.11.17，`No broken requirements found.` |
| `.venv/bin/python -m pytest -q tests/test_archive_analysis.py` | 0 | 4 passed |
| `.venv/bin/python -m pytest -q` | 0 | 59 passed；现有 Starlette TestClient 对 httpx 的弃用提示 1 条 |
| `.venv/bin/python -m py_compile wattline/{app,archive_analysis,history,history_cold,service}.py tests/test_archive_analysis.py tools/browser_smoke.py` | 0 | 无输出 |
| `node --check wattline/static/monitor.js` | 0 | 无输出 |
| `node tools/test_i18n.cjs` | 0 | PASS，427 个双语键，含占位符、引用和 Intl 检查 |
| `.venv/bin/python tools/browser_smoke.py` | 0 | Chromium 159.0.8154.6，PASS，页面错误 `[]`。归档场景观察到 49% 的实际中间进度，`Asia/Shanghai` 单日范围返回 2 个点，失败重试、无归档、范围无数据及入口检查均通过 |
| `.venv/bin/python tools/resource_browser_smoke.py` | 0 | PASS，资源总览、存储、告警、分组趋势、键盘交互及窄屏布局 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-machine-archive-analysis --strict` | 0 | `Change 'add-machine-archive-analysis' is valid` |
| `git diff --check`、`git diff --cached --check`、`git diff --cached --quiet -- AGENTS.md` | 0 | 无输出 |

归档浏览器用例通过 in-process API 读取临时目录中由当前 `History.export` 生成的 gzip。故意截断第二个压缩文件时，服务记录 `监控归档分析未完成 (EOFError)`，恢复原始字节后重试通过。先前执行曾发现测试样本共享状态和既有人员列表截图的 DOM 更新时序问题，最终运行通过。截图为本地忽略目录中的 `artifacts/archive-analysis.png`。

pytest 还覆盖了同一作业复用、跨机器隔离、未发布 gzip、已发布损坏 gzip、夏令时 23 小时日、结束日包含与次日排除、原始归档完整性、读取期间过期或移除以及解压过程中退出。

## 隔离索引三方检查

将本次暂存补丁应用到仅用于核验的独立 Git 索引。来源快照为上述 `deaa326`。命令退出 0，现有文件显示 `cleanly`，新文件回退为直接应用。

~~~sh
.venv/bin/python - <<'PY'
import os, subprocess, tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as folder:
    index = dict(os.environ, GIT_INDEX_FILE=str(Path(folder) / 'index'))
    patch = subprocess.check_output(['git', 'diff', '--cached', '--binary', '--full-index'])
    subprocess.run(['git', 'read-tree', 'origin/main'], env=index, check=True)
    result = subprocess.run(['git', 'apply', '--cached', '--3way'], env=index, input=patch)
    raise SystemExit(result.returncode)
PY
~~~

提交后直接用 `git merge-tree --write-tree <AN-222 本地提交 SHA> deaa3269f158d1da33219e077d0176c1ef520ef2` 复核同一组合。

## 临时文件异常退出验证

在本机 SQLite 和 macOS 上用合成数据写入一个超出缓存的临时数据库。命令退出 0，输出 `unlinked file observed: True` 与 `temporary SQLite pages: 11255 | files before and after SIGKILL: 0`。被终止的进程仅为本命令创建的测试子进程。

~~~sh
.venv/bin/python - <<'PY'
import os, shutil, signal, subprocess, sys, tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as folder:
    env = dict(os.environ, SQLITE_TMPDIR=folder)
    code = """import sqlite3
db = sqlite3.connect('')
db.execute('pragma cache_size=20')
db.execute('pragma journal_mode=OFF')
db.execute('create table ticks (data blob)')
db.executemany('insert into ticks values (zeroblob(4096))', [()] * 10000)
db.commit()
print(db.execute('pragma page_count').fetchone()[0], flush=True)
input()
"""
    worker = subprocess.Popen([sys.executable, '-c', code], env=env, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, text=True)
    try:
        pages = int(worker.stdout.readline())
        assert pages > 1000
        assert not list(Path(folder).iterdir()), 'named temp files remain during analysis'
        if shutil.which('lsof'):
            handles = subprocess.run(['lsof', '-nP', '-a', '-p', str(worker.pid), '+L1'],
                                     capture_output=True, text=True)
            print('unlinked file observed:', 'etilqs_' in handles.stdout)
        worker.send_signal(signal.SIGKILL)
        assert worker.wait() == -signal.SIGKILL
        assert not list(Path(folder).iterdir()), 'named temp files remain after SIGKILL'
        print('temporary SQLite pages:', pages, '| files before and after SIGKILL: 0')
    finally:
        if worker.poll() is None:
            worker.terminate()
            worker.wait()
PY
~~~

## 边界

归档库在空闲 15 分钟后到期。解压与压缩、节点归档移除争用现有归档锁，首次分析时需扫描已发布的共享 gzip。生产规模耗时、其他浏览器、Linux/Docker 异常退出和合入新远端基线后的运行结果未覆盖。真实节点、用户部署配置和实例数据未用于验证。

## 独立审查

2026-11-26 12:35 UTC，AN-221 的 Reviewer-DeepSeek（运行模型 `deepseek-flash`）对实现提交 `5eb022d05c99a5a72999b4be8cfd9a9a9ef71802` 给出通过结论，无需返工。审查者对照 AN-220、OpenSpec 与 Git diff，核对了机器身份和入口隔离、日期与夏令时边界、真实进度、历史图表语义、失败重试、归档完整性及并发回收。审查保持实现和规范文件只读。

审查者复跑了上表中的完整 pytest（59 项）、两套 Chromium 检查、JS 语法、双语检查（427 键）、OpenSpec 1.14.2 strict 和 Git diff 检查，均退出 0。另以 `git merge-tree --write-tree 5eb022d deaa326` 生成组合树 `bedf215c409d2c2a31e27a2bff76e11b59e6e7c3`，在该树的临时副本复跑完整 pytest，87 项通过。组合树的浏览器和双语检查留给整合验证。

审查指出共享归档扫描期间，后续分析作业和日维护需等待。生产规模耗时、其他浏览器及 Linux/Docker 异常退出未覆盖。

## 主干整合验证

2026-11-26，Mika 在固定开发目录使用 `git fetch --no-tags origin main` 和 `git -c merge.autostash=false merge --no-ff --no-edit origin/main`，均退出 0。远端基准为 `deaa3269f158d1da33219e077d0176c1ef520ef2`。合并提交 `d24df306439b327edfee176d5571731525508e78` 的树与审查者的组合树一致。以 `git diff deaa326 d24df30` 查看面向远端基准的实际改动。工作树中的本地注入块在合并前后相同，索引只含通用仓库约定。

| 命令 | 退出码 | 实测摘要 |
| --- | ---: | --- |
| `.venv/bin/python -m pytest -q` | 0 | 87 passed，1 条现有 Starlette/httpx 弃用提示 |
| `.venv/bin/python tools/browser_smoke.py` | 0 | Chromium 159.0.8154.6，PASS，页面错误为空。归档实际中间进度 49%，按 `Asia/Shanghai` 筛选的单日范围返回 2 个样本，失败重试、无归档、区间无样本和入口范围通过 |
| `.venv/bin/python tools/resource_browser_smoke.py` | 0 | PASS，覆盖资源总览、存储、告警、分组、图表、窄屏和分层配置 |
| `node --check wattline/static/monitor.js` | 0 | 无输出 |
| `node tools/test_i18n.cjs` | 0 | PASS，456 个双语键 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-machine-archive-analysis --strict` | 0 | Change is valid |
| `git diff --check`、`git diff --cached --check`、`git diff --check origin/main HEAD` | 0 | 无输出 |

验证使用合成数据。生产规模性能、非 Chromium 浏览器和 Linux/Docker 进程异常退出仍未实测。整合与归档的远端交付见 [任务 3.3](tasks.md)。
