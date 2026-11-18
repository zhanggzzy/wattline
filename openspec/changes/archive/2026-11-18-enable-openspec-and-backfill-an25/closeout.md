# AN-36 specification sync and archive closeout

记录日期：2026-11-18。change：`enable-openspec-and-backfill-an25`；schema：
`spec-driven`。执行者为 Executor-Codex，受 Mika 在 AN-36 的明确委派完成
规范同步、审查摘要和归档。Mika 保留最终核验、提交、推送与远端 SHA 核验职责。
本记录补充 AN-33 的 [verification.md](verification.md)，不回写其历史时间或结论。

## Independent review source and scope

AN-32 的 Reviewer-DeepSeek 在独立会话审查，模型记录为 DeepSeek；来源报告
未单列精确模型版本，本文不推断。审查通过，无阻塞项、无必须修改项。
来源为 AN-32 于 **2026-11-18T05:35:52Z** 的评论
`01a1ed27-84c8-7050-b8f1-a03b940ed56d`，附件
`01a1ed27-84c1-74ea-a08c-3ac84e16cb4f`（`review-report.md`）。
本地原件 SHA-256 为
`f5df735c5934388a6f527989a461a0ac27fab74d944540a99e1414661c787e25`。
原件含本机路径，仅在本地忽略目录保留，公开仓库与本轮证据附件只存本摘要和来源标识。

审查对象是基准 `fc669498dce7666e8a3c23c594e4b4ee845d24c4` 上的
20 个暂存文件，index tree 为
`4ca157d614e681f230cb93b2b8998b32dc885ade`，暂存补丁 SHA-256 为
`06daa0e62de9c7bc142aaf976ecf2cbbffdcca8f3ca6bf86e8a1a29c27c34164`。
本轮于 **2026-11-18T05:38:22Z** 复算二者一致后才开始改动。

独立审查核对了官方 skills 来源、AGENTS 索引、实施前计划快照、历史补档、
实际 diff 和 strict，并独立重跑 pytest（16 passed，1 个既有弃用警告）、
JS 语法与 whitespace 检查。审查未重跑浏览器脚本，未重演历史实验；
初始化顺序没有外部不可篡改时间戳。审查结论针对上述 tree，
不冒称该审查也覆盖本轮新增收尾 diff；本轮由 Mika 最终核验。
据此完成 tasks 4.1。

## Sync and archive actually performed

先以固定 CLI 确认 nearest repo root、`spec-driven`、活动 change 5/7，
从 status 的 `artifactPaths.specs.existingOutputPaths` 取唯一 delta，
并读取一次 specs instructions（无额外 artifact rules）。按仓库内官方
`openspec-sync-specs` skill 创建
[development-workflow 主规范](../../../specs/development-workflow/spec.md)：
只将标题改为主规范标题、`ADDED Requirements` 改为 `Requirements`，
Purpose 与五个 requirement blocks 原文保留，无 TBD 或 delta 操作标题残留。
主规范与活动 change 的 strict 均通过，核对实际新文件 diff 后完成 tasks 4.2。

再读取 archive instructions、status 和 list：四个 artifacts 均 done，
tracked tasks 为 7/7、complete。归档 guidance 要求的实施、验证和独立审查已满足，
无冲突或需忽略的建议。逐字节比较主规范与规范化 delta，确认唯一 capability
已同步，无剩余操作。依据 AN-36 的明确归档授权继续，不以重复确认代替已获授权。

按官方 `openspec-archive-change` skill 的目录移动步骤，于
**2026-11-18T05:39:40Z**（北京时间 13:39:40）执行归档：

~~~sh
test ! -e openspec/changes/archive/2026-11-18-enable-openspec-and-backfill-an25
mv openspec/changes/enable-openspec-and-backfill-an25 openspec/changes/archive/2026-11-18-enable-openspec-and-backfill-an25
~~~

目标此前不存在，移动 exit 0，无 stdout/stderr。
`.openspec.yaml` 随目录保留；proposal、design、delta、verification 原文迁移，
tasks 仅更新真实完成状态与 Mika 委派关系。`openspec/README.md` 更新到归档入口。
原 verification.md 中的活动路径和待审措辞属于 AN-33 交接历史，当前事实以本记录为准。

## Reproducible commands and results

下表 OpenSpec 命令均带前缀
`OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2`。
完整 argv、开始时间、stdout、stderr、退出码和收尾 diff 放在 AN-36 证据附件，
本地入口 `artifacts/an36/`；本机路径归一化为 `$REPO` / `$HOME`。

| 实际命令 | 实际输出或核验结果 | exit |
| --- | --- | --- |
| `list --json`（开始） | nearest repo，5/7 | 0 |
| `status --change enable-openspec-and-backfill-an25 --json` | spec-driven，四个 artifacts done，唯一 delta | 0 |
| `instructions specs --change enable-openspec-and-backfill-an25 --json` | specs artifact instruction JSON，无 rules | 0 |
| `validate --specs --strict`（同步后） | spec/development-workflow，1 passed，0 failed | 0 |
| `validate enable-openspec-and-backfill-an25 --strict`（归档前） | Change is valid | 0 |
| `git diff --no-index /dev/null openspec/specs/development-workflow/spec.md` | 新主规范 51 行；exit 1 表示有差异 | 1 |
| `instructions archive --change enable-openspec-and-backfill-an25 --json` | context 与一条 archive guidance，已采纳 | 0 |
| `list --json`（归档前） | complete，7/7 | 0 |
| `validate --archived --strict`（归档后） | change/2026-11-18-enable-openspec-and-backfill-an25，1 passed，0 failed | 0 |
| `validate --specs --strict`（归档后） | spec/development-workflow，1 passed，0 failed | 0 |
| `validate --all --strict`（归档后） | spec/development-workflow，1 passed，0 failed | 0 |
| `list --json`（归档后） | changes: []，root 仍为当前仓库 | 0 |
| `git diff HEAD -- wattline tests tools pyproject.toml config.example.json .gitignore docs/frontend-redesign.md` | 无输出 | 0 |
| `git ls-remote origin refs/heads/main`（本轮开始） | fc669498dce7666e8a3c23c594e4b4ee845d24c4 | 0 |
| `git diff --check`、`git diff --cached --check`（最终暂存后） | 均无输出 | 0 |
| `.venv/bin/python artifacts/an36/verify.py` | 全部未涉及 blob 保持一致，五个归档原件不变，7/7、主规范/delta 一致、skills lock、AGENTS 39 行及工作树哈希、无产品 diff 和索引隐私检查全部 PASS | 0 |

`--archived` 是官方 CLI 的归档任务完成性检查，不重新应用历史 delta；
`--all` 不包含归档 delta。因此同时保留归档前 delta strict、
归档后主规范 strict、归档任务检查及主规范一致性比较，不将这些检查夸大为新独立审查。

## Final delivery boundary and evidence

本轮只增加主规范、收尾记录，更新 tasks 和流程入口，并移动 change。
六份官方 skills、历史补档、AGENTS 索引正文及本轮开始时的工作树 runtime 块
保持原样；产品、测试、依赖和用户实例未改动。最终索引安全、逐文件 blob 比较、
whitespace 检查及归档文件清单见 AN-36 附件 `AN-36-evidence.zip`，
其中 `delivery-manifest.json` 记录收尾前后 tree、基准、完整和增量补丁 SHA-256，
避免在补丁内容中循环引用自身哈希。增量补丁直接比较原审查 tree 与最终 index。

本轮未再次运行产品测试或浏览器脚本：只做已审流程的机械收尾，产品文件逐字节未变，
AN-33 执行与 AN-32 独立测试记录保留。本轮检查均为执行者自检，
Mika 仍需对新增收尾 diff 最终核验后再提交、推送并核验远端 main；
当前 HEAD 仍是基准，无本轮 commit/PR/push。继续保留 `AM AGENTS.md`：
index 仅 39 行通用正文，禁止 `git add -A`、`git add AGENTS.md` 或 `git commit -a`。
AN-28 最终保留 in_review 由用户验收；AN-25 状态不变，实例未升级。
