# AN-128 验证记录

2026-11-25 UTC，Executor-Codex 实施自测。关联 [任务 3.1 和 3.2](tasks.md)，独立审查对应任务 3.3。

- 开工基线 `a99d317134c36582b5b6ae2c1fe3f8d9eb670c1e`。开工时本地 HEAD、`origin/main` 和 `git ls-remote origin refs/heads/main` 一致。
- 本地实施提交 `c7ebc1f1429c308260f4322ae3c00eecbbd05abd`。用 `git diff a99d317 c7ebc1f` 核对实际改动。本记录随后提交，最终交接引用该记录提交。
- 执行环境为 macOS arm64、Python 3.11.17、Node 26.11.0、npm 11.20.0、OpenSpec 1.14.2。保留开工时的 `AGENTS.md` 本地差异，索引中的文件只含通用约定。

## 合成及本地检查

| 命令 | 退出码与结果 |
| --- | --- |
| `.venv/bin/python -m pytest -q` | 0。44 项通过，1 条既有 Starlette/httpx 弃用提示。Windows 测试覆盖配置、登记和重载、重复身份键、密钥或机器身份变化、处理器组数量不完整、重启历史间断、GPU 按 UUID 跨索引查询、空清单在原始和温存储中的恢复、缺少探针及超时。 |
| `node --check wattline/static/monitor.js` | 0。 |
| `node tools/test_i18n.cjs` | 0。308 个翻译键，通过占位符和引用校验。 |
| `.venv/bin/python tools/browser_smoke.py --browser "$CHROME_EXECUTABLE"` | 0。Chrome 158.0.8127.37，两种语言，无页面错误。Windows 用例宽 390px，验证两处显示 5/7 条及省略 2 条、已知显存同分排序、未知显存、无 UID 账号、无卡与探针不可用。总览保留全量计数。Linux 对照保留 7 条。首次未指定浏览器时 Playwright 目标版本本地缺失，退出 1，复跑使用现有 Chrome。 |
| `.venv/bin/python -m pip wheel . --no-build-isolation --no-deps -w "$WHEEL_DIRECTORY"` | 0。用 Python `zipfile.ZipFile` 核对 wheel 含 `wattline/windows.py` 和 `wattline/windows_probe.ps1`。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate add-windows-nodes --strict` | 0。输出 `Change 'add-windows-nodes' is valid`。 |
| `git diff --check`、`git diff --cached --check`、`git diff a99d317 c7ebc1f --check` | 均为 0，无输出。 |

## Windows 只读实机

早期严格 SSH 预检曾退出 255，返回 `No route to host`。随后同一授权别名连接恢复。2026-11-25 07:15:03 UTC 在实施提交上复跑 [实机验证脚本](verify-windows-target.py) 并退出 0。目标通过本地已有别名传入。脚本通过进程内 API 登记，使用临时 SQLite 目录和 5 秒间隔，通过非交互公钥 SSH 执行实际 PowerShell/CIM 与 NVIDIA 探针。

```sh
PYTHONPATH=. .venv/bin/python openspec/changes/add-windows-nodes/verify-windows-target.py "$WINDOWS_TEST_TARGET"
```

- 登记返回 HTTP 201，OS 为 Windows。实际采样确认 1 个处理器组、32 个逻辑处理器、32 条唯一计数记录。CPU、内存、系统卷及运行时长可读，load average 为空。
- 保存两轮机器样本和两轮 GPU 样本。CPU、内存、GPU 利用率及显存的历史查询各返回 HTTP 200 和 1 个有效时间桶，两轮样本落在同一桶。
- 一张 WDDM NVIDIA 卡提供利用率、总及已用显存、温度、功耗和功耗上限。快照标记已占用、枚举部分可见。该轮 16 条进程均有经核实的账号与时间，逐进程显存可用数为 0。
- 实机覆盖单处理器组、单张 WDDM 卡和当前 SSH 账户。多处理器组、模拟重启、密钥更换、无卡、驱动缺失和超时由合成夹具覆盖。其他驱动模式、真实重启或密钥轮换、不同 Windows 版本和账户权限仍需对应环境验证。独立审查在 AN-127。

实机结果只保留计数和可用性。验证使用临时数据目录与现有主机密钥信任，远端操作限于只读探测。
