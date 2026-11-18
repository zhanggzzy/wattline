# OpenSpec maintenance workflow

本仓库于 2026-11-18 经 AN-28 授权接入，首个 change 为
`enable-openspec-and-backfill-an25`。开发约定见根目录 `AGENTS.md`。
源码、测试、配置、依赖、构建脚本和仓库文档修改均适用；只读检查无需新建 change。

使用官方 CLI **1.14.2** 与默认 `spec-driven` schema：

~~~sh
OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 --version
OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 context --json
OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 list --json
OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 schemas --json
~~~

需要 Node/npm 和对应版本的 npm 缓存；离线命令若提示没有缓存，报告缺口，
按当前任务授权获取固定版本，不静默升级或跳过流程。已有 `openspec/` 时勿重新初始化。
此次初始化真实命令为 `init --tools none --no-animation --no-copilot-cloud`，
CLI 提示未选择 GitHub Copilot，故忽略最后一个 flag。随后按授权原样复制六个 skills，
没有安装自创 skill 或增加产品运行时依赖。

## Official skills

`.agents/skills/` 下的 propose、apply-change、update-change、sync-specs、
archive-change 和 explore 均为工作区已授权的官方 `openspec-*` 原文，
其 metadata `generatedBy` 为 1.14.2。来源链由 AN-28 指定：先前从
AlayaJet-MaaS 的 Codex `.agents/skills` 原样复用到工作区，再复制至本仓。
本次与工作区来源逐字节比较；不声称额外做了上游独立下载核验。
`skills-lock.json` 记录所有文件的 SHA-256 与固定 CLI 版本；该文件是来源清单，
不是 CLI 自动强制执行的版本锁。

从仓库根核验原文哈希：

~~~sh
python3 - <<'PY'
from pathlib import Path
import hashlib, json
lock = json.loads(Path('openspec/skills-lock.json').read_text())
for file, expected in lock['sha256'].items():
    assert hashlib.sha256(Path(file).read_bytes()).hexdigest() == expected, file
print('6 official skills: SHA-256 PASS')
PY
~~~

## Change lifecycle

先读取上下文、主规范与活动 change，以 CLI instructions 确定 artifact 依赖；
先写问题、范围、验收、proposal/tasks 和适用 design/delta，再按 apply 实施。
无规范层行为改变时遵从 schema 的 `skip_specs` 规则，不杜撰产品需求。
本次 `development-workflow` delta 规范用户明确引入的维护行为，历史前端补档
不视为当时的实施计划。

change 内保存验证与证据入口，关联任务、基准和实际 diff/commit/PR；记录真实命令、
输出、退出码、限制和独立审查结论。自测、独立审查与用户验收分别记录，
未完成的 task 不勾选。`status` 的 artifacts done 只表示规划文件存在；
实际实施进度以 `instructions apply --json` 的 tasks 为准。

实施、必要验证及独立审查通过后，同步适用 delta 到 `openspec/specs/` 并归档；
使用官方 sync/archive skills，不跳过审查提前归档。AN-33 交接时保留活动 change，
随后 AN-32 独立审查通过。Mika 委派 Executor-Codex 在 AN-36 同步
[`development-workflow` 主规范](specs/development-workflow/spec.md) 并归档；
真实审查摘要与收尾检查见
[归档收尾记录](changes/archive/2026-11-18-enable-openspec-and-backfill-an25/closeout.md)。
Mika 继续负责最终核验、提交、推送及远端 main SHA 核验，AN-28 最终保留待用户验收。
本流程不会升级用户实例或触发部署。
