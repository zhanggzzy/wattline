# Wattline repository instructions

## Development workflow

所有源码、测试、配置、依赖、构建脚本和仓库文档改动都必须使用仓库内 OpenSpec。只读调研和不改仓库的检查无需新建 change。先读取本文件、README、`openspec/config.yaml`、相关主规范和活动 change，再检查实际目录、分支、未提交修改与远端；保留已有成果，禁止强制重置、清理或覆盖。

固定使用官方 OpenSpec **1.14.2**，默认 schema 为 `spec-driven`，使用 `.agents/skills/openspec-*` 的六个官方 skills。原文来源和 SHA-256 见 `openspec/skills-lock.json`；不得自创替代 skill 或静默换版本。命令统一使用：

~~~sh
OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 <command>
~~~

先确认 Node/npm 可用；缓存缺失时明确报告，不把 CLI 不可用当作绕过流程的理由。实施前建立或复用 change，以 CLI 确认 root、schema、status 和各 artifact instructions，准备 proposal、tasks、适用 design 和规范 delta，写明问题、范围、验收条件及兼容性。无规范层行为改变时遵从官方 `skip_specs` 规则，不编造需求。

按官方 propose/apply/update skills 推进。用户已明确授权初始化或连续实施时按该授权执行，不重复请求许可；未授权的实施仍遵守 skill 的规划边界。首次已授权接入时先执行官方 init，再建立首个 change 和计划，然后实施仓库流程。历史补档必须标明事后整理时间、真实事件时间、来源及当时是否采用 OpenSpec，不能把本次检查写成当时执行。

## Verification and delivery

使用 Python >=3.11 和本仓库任务 `.venv`，按 `pyproject.toml` 安装依赖。测试用临时数据和合成夹具；保留容器视角、未知归属、固定主机身份、单节点清理和冷归档完整性等已有行为。按改动执行适当的现有测试、语法和 diff 检查，并 strict 校验 change：

~~~sh
.venv/bin/python -m pytest -q
node --check wattline/static/monitor.js
OPENSPEC_TELEMETRY=0 npx --offline @fission-ai/openspec@1.14.2 validate <change-id> --strict
git diff --check
git diff --cached --check
~~~

前端行为改动另运行 README 中的合成 API 浏览器检查。记录真实命令、输出、退出码、基准 SHA、实际 diff/commit/PR、未覆盖范围和限制，入口放在 change 并关联任务。不得将自测写成独立审查，不得将 strict 或平台 done 写成交付通过；只有完全完成的 task 才可勾选。

独立审查者对照 change、实际 diff、测试和 strict 核验，不修改自己正在审查的实现。未审查或仍有任务未完成时保持活动 change 和待办；实施、必要检查及独立审查通过后，用官方 sync/archive skills 同步适用规范并归档，保留真实审查和归档记录。

main 整合、提交、推送及远端 SHA 核验由 Mika 按项目授权负责。父任务最终保留 in_review 供用户验收；内部子任务完成不代表用户已验收或实例已更新。

## Privacy and instance boundary

只访问任务所需资料，不将私有节点配置、地址清单、历史指标、凭据、本机路径或 runtime 注入块纳入 Git。文档默认本地，不自动上传云端。无当前任务明确授权，不连接真实节点、不触发采集、不启停服务、不修改用户部署目录、实例配置或数据。实例升级由另行发起的部署会话处理。

Multica 可能在正文前注入自动管理块；该块只留本地，禁止整体暂存。审查和提交须核对 `git show :AGENTS.md` 仅含通用仓库约定，并保留工作树注入块原样。
