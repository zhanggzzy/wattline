# AN-242 实施验证

验证于 2026-11-27（Asia/Shanghai）完成，对应 [任务 1.1 与 1.2](tasks.md)。需求和合成原型来自 AN-234 与 AN-237，独立审查由 AN-241 接手。

## 基准与候选

- 本地 `main` 的 `HEAD`、`origin/main` 和开工时 `git ls-remote origin refs/heads/main` 返回的 SHA 均为 `53903d7e339697b5e7d674cb6010341e79fb5a6e`。候选保留在固定工作树，尚无候选 commit 或 PR。
- 七个前端及测试文件新增 904 行、删除 77 行。下列命令用临时 Git 索引重建代码和测试补丁，包含新建脚本。SHA-256 为 `da6fec925befc1deb33538dd79f0056069974c9e1925950a0609532a4fa9fc24`。OpenSpec 元数据、提案、设计、规范增量、任务和验证记录位于当前活动 change。
- 开工时 `AGENTS.md` 已有本地 runtime 注入。真实索引无暂存差异，`git show :AGENTS.md` 经标记检查无注入，两个候选补丁均排除该文件。

~~~sh
set -e
wattline_review_dir=$(mktemp -d artifacts/an242/diff.XXXXXX)
export GIT_INDEX_FILE="$PWD/$wattline_review_dir/index"
git read-tree 53903d7e339697b5e7d674cb6010341e79fb5a6e
git add -- tools/browser_smoke.py wattline/static/{group-trends.js,groups.js,index.html,locales.js,monitor.css,monitor.js}
git diff --cached --check
git diff --cached --stat
git diff --cached --no-color --no-ext-diff --binary > artifacts/an242/implementation.patch
shasum -a 256 artifacts/an242/implementation.patch
~~~

## 执行结果

使用项目 `.venv` 的 Python 3.11.17、pytest 8.4.2 和 Playwright 1.65.2，Node 26.11.0、npm 11.20.0，OpenSpec 1.14.2（`spec-driven`）。

| 实际命令 | 退出码 | 结果 |
| --- | ---: | --- |
| `.venv/bin/python -m pytest -q` | 0 | `93 passed, 1 warning in 2.67s`。警告来自 Starlette 对 TestClient 使用 httpx 的弃用提示。 |
| `.venv/bin/python tools/browser_smoke.py` | 0 | Chromium `159.0.8154.6`，`result: PASS`，`page_errors: []`。分组用例返回 288 桶、最多 6 组、双语、触控模拟、强制颜色及 3 张截图。旧总览验证 18 台机器。归档截断夹具产生预期 `EOFError`，修复测试夹具后重试成功，跨日 5 行、单日 3 行。 |
| `.venv/bin/python tools/resource_browser_smoke.py` | 0 | `PASS`，覆盖资源 API、图表样本与覆盖率、侧栏模式、合并成员及分组管理。 |
| `node tools/test_i18n.cjs` | 0 | `PASS: 489 message keys, placeholder parity, references, interpolation, Intl, persistence, fallback, blocked storage`。 |
| `node --check wattline/static/monitor.js`、`node --check wattline/static/group-trends.js`、`node --check wattline/static/groups.js`、`node --check wattline/static/locales.js` | 0（各项） | 无输出。 |
| `.venv/bin/python -m py_compile tools/browser_smoke.py` | 0 | 无输出。 |
| `OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate improve-group-trend-readability --strict` | 0 | `Change 'improve-group-trend-readability' is valid`。 |
| `git diff --check`、`git diff --cached --check`（真实及临时候选索引） | 0（各项） | 无空白错误。 |

定向浏览器首轮对 Canvas 的线宽使用精确浮点比较，Chromium 返回的 `2.4` 有浮点舍入，退出码为 1。改用 `0.001` 的测试容差后，定向和完整回归均退出 0。

## 覆盖与实现取舍

- 机房与集群总览可切换按组分图与叠线，单一匹配组继续使用原单图。验证同名分组、跨组共享成员、宿主和容器分列、6 组上限及筛选后显示第 7 组。共同刻度覆盖 GPU 百分比、GPU 功耗和按 GiB 转换后的已用内存。
- 合成用例观察 Canvas 的实线、像素边界、断开的路径、真实零基线、孤立点、缺测底纹和联动标尺。读取统计及数据表校验峰值和时间、有效样本均值、缺测数及成员覆盖率。分图在各绘图区所含范围全缺测时着斜纹，叠线高亮时按高亮组着斜纹并在图外标明组名。部分范围缺测仍可通过分范围线段、统计和数据表查询。覆盖率直接沿用 API 给出的分子与分母。
- 验证 1440、975、730、390、320 CSS px 下的图外读数与页面布局，覆盖键盘 5 分钟步进、一小时跳转、首尾和 Escape，模拟触控、强制颜色与浏览器存储受阻，以及浏览器刷新保留视图模式。模拟轮询替换图表 DOM 后检查独显、焦点和标尺。标尺按指标记录所选时间，滑动窗口刷新时映射到响应中最近的桶。全页 GPU 利用率与功耗可同时按组分图。
- 验证范围限于 Chromium 和临时合成数据，未实测其他浏览器、实体触屏或屏幕阅读器。六组布局纵向较长，可切换叠线。实线颜色在页面会话内按组 ID 和观测范围分配。生产实例、真实采集、配置和数据均未参与检查。

## 合成截图

截图经目视检查，保存在忽略的 `artifacts/`。SHA-256 用 `shasum -a 256 artifacts/an242-group-{split-desktop,overlay-desktop,split-mobile}.png` 计算。

| 文件 | SHA-256 |
| --- | --- |
| `an242-group-split-desktop.png` | `63b4ee5c12ba342f1de35de6f5def49ea5d9e2bfb70ae50b0de1b92709a03f4e` |
| `an242-group-overlay-desktop.png` | `4df444ff1d84ba4afd995855f654643a12e4cdc9d68356d8cacc75b5bf91f5d5` |
| `an242-group-split-mobile.png` | `2e512949d9aeefa92030a5c310eedde4775735687b72ec676d3979fdbc6eb772` |

## 交接

实施自测完成。AN-241 的 Reviewer-DeepSeek 根据实际差异、OpenSpec 和上述证据独立审查。Mika 负责审查后的主干整合、规范同步、归档和远端核验。

## 独立审查

2026-11-27，Reviewer-DeepSeek 使用 `deepseek-flash`（OMP）在 AN-241 对候选做独立只读审查，结论通过。实际复核完整补丁 SHA-256 `780fda076fc32142b895e8e6b349b58b578a9d4957d3fccf6f60ea4eb34eb0c6`、七文件代码/测试补丁和合成截图哈希，复跑表内 Python、两套 Chromium 检查、i18n、JS 语法、diff 与 OpenSpec strict，均退出 0。额外使用 320px 合成探针检查真实零参与均值且仍在基线显示，以及按观测范围计数和按全范围缺测绘制底纹。完整记录和探针见 AN-241。

窄屏单桶底纹在审查探针中约 0.69 像素，需结合断线、计数和数据表判断。仅部分范围缺测时，按范围显示断线及统计。审查另指出两个未使用的 DOM ID，本次保留已审查的实现。未实测其他浏览器、实体触屏或屏幕阅读器。

## 整合核验

2026-11-27，Mika 核对本地基准与 `git ls-remote --exit-code origin refs/heads/main` 的结果均为 `53903d7e339697b5e7d674cb6010341e79fb5a6e`。用独立临时索引重建候选，完整补丁及代码/测试补丁 SHA-256 均与 AN-241 一致。正式索引里的 `AGENTS.md` 与基准一致。

复跑 `.venv/bin/python -m pytest -q`（93 通过，1 条弃用警告）、`.venv/bin/python tools/browser_smoke.py`（Chromium 159.0.8154.6，PASS，无页面错误）、`.venv/bin/python tools/resource_browser_smoke.py`（PASS）、`node tools/test_i18n.cjs`（489 键）、四个 JS 文件的 `node --check` 及工作树和暂存差异空白检查，均退出 0。归档截断夹具产生预期 EOFError，随后恢复。已同步 `overview` 的两条新增要求并核对正文，`validate --specs --strict` 为 12 项通过。变更 strict 通过，OpenSpec 任务全部完成，按仓内归档技能移动完整 change。推送后核验的远端 SHA 记在父任务 AN-234 的交付评论。
