# AN-137 独立复审记录

2026-11-25（Asia/Shanghai）由 AN-141 从 AN-137 当日的原始记录摘录。原审查由 Reviewer-Codex 执行，Multica 配置模型为 `gpt-6.2-sol`，结论为 **需修改**。当时已使用活动 OpenSpec change `style-machine-assignee-chips`，schema 为 `spec-driven`。来源为 AN-137（`01a211df-413a-707b-b6a7-4b29d523c875`）交接评论 `01a211ed-b4e9-7efd-9a7a-628720357195`。原报告、截图、测量 JSON 和证据包保存在原评论与本地忽略目录 `artifacts/an137-review/`。第一轮独立审查记录见 [AN-134](review-an-134.md)。

- 被审 HEAD 为 `592f19fabfca4d844406691cb7f2ba0e35822001`。返工范围为 `eae4fb43ab9b8ea9ce88282e202d260fd266c23e..592f19fabfca4d844406691cb7f2ba0e35822001`，整组变更的远端跟踪基线为 `a738dabfd17d830be6fb8580cc6ea6570a63020d`。
- 英文展开导航 1155 CSS px 时为卡片，列表宽度和滚动宽度都是 860。到 1156 CSS px 时切为七列表格，列表宽 861，表格宽约 901，内存用量尾部被裁。折叠导航 986 和 1024 CSS px 同样复现。夹具通过合成 API 配置人员，活动行包含警告状态、长 SSH 别名、10000 W 和 1800.0 GiB 内存用量。
- 在同一窄表格中，`Ada Lovelace` 与 `Ada  Lovelace` 均在 `Ada` 后换行。DOM 文本各自正确，非空格字形的相对位置完全相同。中英文 320、1440 CSS px 的列表及弹窗单行样例可区分两名人员。
- 补充记录显示，英文折叠导航 320 CSS px 时，页面滚动宽度为 346，卡片内存说明跨出单元格。这两项早于新增使用者列。
- AN-137 的 pytest、JS/i18n、README Chromium、OpenSpec 1.14.2 strict、Git diff 检查和 AN-134 原夹具复测均通过。补充布局脚本 `layout.py` 因上述可见性和字形断言返回 1。对照使用相同的合成 API、临时 SQLite 和 Chromium Headless Shell，仅替换 Git 静态资源。Firefox、Safari、真实屏幕阅读器和用户实例未实测。

AN-141 的实现自测见 [verification.md](verification.md)。AN-140 独立复审仍记录在该 change 的待办中。
