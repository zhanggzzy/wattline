# AN-240 实施验证

2026-11-27（Asia/Shanghai）。本记录对应 AN-238 的实施子任务 AN-240 和 `show-complete-machine-history` 任务 2.1。独立审查由 AN-239 负责。

## 基线与被审内容

- 开始时本地 `HEAD` 和 `git ls-remote --exit-code origin refs/heads/main` 均为 `c0b084a85179848d221711a6af98364fc7377c85`。初始工作树仅有 `AGENTS.md` 的本地运行时注入，索引仅含通用约定。
- 本地交接提交的精确 SHA 见 AN-240 交接评论。在实施提交上可用 `git log -1 --format=%H -- openspec/changes/show-complete-machine-history/verification.md` 核对该提交，再以基线和该 SHA 做完整 diff。
- 下面的产品代码、文档和回归测试 diff 的 SHA-256 为 `6053a2066a5b8c9558a071999948c6b50372fca7aaa295d41c26d3883342195f`。

```sh
git diff --full-index --binary c0b084a85179848d221711a6af98364fc7377c85 HEAD -- \
  README.md tests/test_archive_analysis.py tests/test_machine_views.py tools/browser_smoke.py \
  wattline/archive_analysis.py wattline/history.py wattline/service.py wattline/static/locales.js | shasum -a 256
```

## 基线复现

先将下面两个回归用例加入测试文件，在产品代码仍为基线版本时执行：

```sh
.venv/bin/python -m pytest -q tests/test_archive_analysis.py -k 'local_history_without_any_archives or cross_tier_buckets_and_archive_rotation'
```

退出 1，`2 failed, 4 deselected`。库里新增本地数据后，打开仍返回原来的空作业。跨层功耗筛选只返回了冷层的一个数据点（2 条样本，70 W），而完整结果应为两个数据点（第一个纳入去重后的 4 条样本，40 W，第二个为 80 W）。

## 实施自测

环境为 Python 3.11.17（仓库 `.venv`）、pytest 8.4.2、Node v26.11.0、npm 11.20.0、Playwright 1.65.2 和 Chromium 159.0.8154.6。

| 命令 | 退出码 | 输出摘要 |
| --- | ---: | --- |
| `.venv/bin/python -m pip check` | 0 | `No broken requirements found.` |
| `.venv/bin/python -m pytest -q tests/test_archive_analysis.py tests/test_machine_views.py` | 0 | `10 passed in 0.54s`，包含上述两条回归 |
| `.venv/bin/python -m pytest -q` | 0 | `93 passed, 1 warning in 2.61s` |
| `node --check wattline/static/monitor.js` | 0 | 无输出 |
| `node --check wattline/static/locales.js` | 0 | 无输出 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 465 message keys`，占位符、引用、插值、Intl、语言偏好与回退均通过 |
| `.venv/bin/python tools/browser_smoke.py` | 0 | `result: PASS`，`page_errors: []`，历史专项摘要见下 |
| `.venv/bin/python tools/resource_browser_smoke.py` | 0 | `PASS`，概览、容器来源、存储、分组和窄窗口的合成 API 检查通过 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate show-complete-machine-history --strict` | 0 | `Change 'show-complete-machine-history' is valid` |
| `git diff --check` 和 `git diff --cached --check` | 0 / 0 | 无输出。提交前复查暂存内容 |

浏览器历史专项返回 `progress: 49`、`combined_range_rows: 5`、`single_day_rows: 3`，归档时区为 Asia/Shanghai，浏览器时区为 America/Los_Angeles。覆盖损坏 gzip 重试、同一图表跨三个存储层、仅本地样本、完全空和筛选空、退出后回到原趋势，以及 390px 下无整页溢出。本地截图为忽略目录中的 `artifacts/archive-analysis.png`。破损 gzip 的 `EOFError` 日志来自该故障夹具。pytest 和两个浏览器脚本均报告 Starlette TestClient 的 httpx 弃用警告。

API 合成测试额外覆盖无任何已发布 gzip、只有归档样本、夏令时 23 小时日期、同来源重复样本、不同机器和来源 boot 隔离、维护切换前后快照与重建结果一致、失败及删除、过期和关闭后的临时数据清理。

## 限制

仅使用临时数据和夹具。未测实际部署、真实节点、大规模归档性能或 Chromium 以外的浏览器。分析页使用准备时的快照，沿用就绪作业的闲置回收机制。AN-239 独立审查、主规范同步、归档及 Mika 的远端 main 交付仍待完成。

## AN-239 独立审查

2026-11-27，Reviewer-DeepSeek（DeepSeek 4.1 Flash，`deepseek-flash`）在独立会话审查实施提交 `b2caba92a9c2285c2bff8c8c954f953e42ee5d2b`，结论为通过。审查复跑 93 项 pytest、两套 Chromium 合成浏览器检查、JS 和双语检查、OpenSpec strict 及 Git diff 检查，并在基线复现两项回归。复算产品 diff 的 SHA-256 与上文一致。归档前已修正摘要复算命令的笔误。审查未覆盖真实部署、非 Chromium 浏览器或大规模归档性能。

## 主干整合与归档

2026-11-27，Mika 在待交付代码上复跑 `.venv/bin/python -m pytest -q`（93 项通过，1 项既有弃用警告）、两套 README 合成 Chromium 检查（均通过，历史专项跨层 5 条、单日 3 条）、两个 JS 文件的语法检查和 `node tools/test_i18n.cjs`（465 个消息键通过）。浏览器验证使用合成数据，未接触用户部署。

`machine-archive-analysis` 主规范同步了三项已审查的需求，并按交接更新 Purpose。OpenSpec 1.14.2 的 change strict 与主规范 strict（12 项通过）及 Git diff 检查通过。推送审查通过的产品提交后，`git ls-remote --exit-code origin refs/heads/main` 返回 `b2caba92a9c2285c2bff8c8c954f953e42ee5d2b`，与实施及审查提交相同。后续归档提交仅包含 OpenSpec 文档。
