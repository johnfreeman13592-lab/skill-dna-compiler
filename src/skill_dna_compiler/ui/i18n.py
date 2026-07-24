"""Small, presentation-only translation catalog for the Streamlit UI."""

# ruff: noqa: E501

from __future__ import annotations

from typing import Literal

Language = Literal["en", "ja", "zh-CN"]

DEFAULT_LANGUAGE: Language = "en"
LANGUAGE_LABELS: dict[Language, str] = {
    "en": "English",
    "ja": "日本語",
    "zh-CN": "简体中文",
}


def _entry(en: str, ja: str, zh_cn: str) -> dict[Language, str]:
    return {"en": en, "ja": ja, "zh-CN": zh_cn}


TEXT: dict[str, dict[Language, str]] = {
    "language.label": _entry(
        "Language",
        "表示言語",
        "界面语言",
    ),
    "hero.copy": _entry(
        "Compile reusable, source-backed Skills from the experience stored in Obsidian.",
        "Obsidianに蓄積した経験から、出典を保った再利用可能なSkillを編成する。",
        "将 Obsidian 中积累的经验编译为可复用、可追溯来源的 Skill。",
    ),
    "hero.safety_aria": _entry(
        "Product safety features",
        "製品の安全特性",
        "产品安全特性",
    ),
    "hero.selected_only": _entry(
        "Selected notes only",
        "選択メモだけを解析",
        "仅分析已选择的笔记",
    ),
    "hero.human_approval": _entry(
        "Human approval",
        "人間が承認",
        "人工批准",
    ),
    "hero.local_storage": _entry(
        "Local storage",
        "ローカル保存",
        "本地存储",
    ),
    "workflow.aria": _entry(
        "Five-step Skill workflow",
        "Skill生成の5工程",
        "Skill 生成的五个步骤",
    ),
    "workflow.select": _entry("Select notes", "メモを選ぶ", "选择笔记"),
    "workflow.payload": _entry(
        "Review payload",
        "送信内容を確認",
        "检查发送内容",
    ),
    "workflow.review": _entry(
        "Review candidates",
        "候補をレビュー",
        "审核候选项",
    ),
    "workflow.compile": _entry(
        "Compile Skill DNA",
        "Skill DNA化",
        "编译 Skill DNA",
    ),
    "workflow.export": _entry(
        "Export to Codex",
        "Codexへ出力",
        "导出到 Codex",
    ),
    "sidebar.title": _entry(
        "LOCAL SAFETY STATUS",
        "ローカル安全状態",
        "本地安全状态",
    ),
    "sidebar.vault": _entry(
        "Source notes are read-only",
        "元メモは読み取り専用",
        "源笔记为只读",
    ),
    "sidebar.gates": _entry(
        "Approval, compilation, and export are separate",
        "承認・変換・出力を分離",
        "批准、编译和导出相互独立",
    ),
    "sidebar.key_configured": _entry("Configured", "設定済み", "已配置"),
    "sidebar.key_missing": _entry("Not configured", "未設定", "未配置"),
    "sidebar.key_hidden": _entry(
        "{state}; value hidden",
        "{state}・値は非表示",
        "{state}；不显示密钥值",
    ),
    "sidebar.network": _entry(
        "Selected and confirmed payload only",
        "選択・確認済みPayloadのみ",
        "仅发送已选择并确认的 Payload",
    ),
    "beta.notice": _entry(
        "Public Beta. Review local data and any AI payload before you continue.",
        "一般公開Betaです。データとAI送信内容をローカルで確認してから実行してください。",
        "公开测试版。继续前请在本地检查数据和任何发送给 AI 的内容。",
    ),
    "quick.title": _entry(
        "Fastest first-use path",
        "はじめての最短ルート",
        "首次使用的最短流程",
    ),
    "quick.three_steps": _entry(
        """
1. **Select notes** — Review exactly what may be sent and the maximum estimated cost.
2. **Review discovered rules** — Compare each rule with its source and approve only what you trust.
3. **Save for Codex** — Review the complete Skill and destination before export.

You can safely leave any uncertain candidate on hold and stop.
""",
        """
1. **メモを選ぶ** — AIへ送る内容と料金上限を確認します。
2. **見つかったルールを確認する** — 元メモの根拠を見て、使うものだけ承認します。
3. **Codexへ保存する** — Skillの全文と保存先を確認して出力します。

途中で分からなくなった候補は、保留のままで安全に終了できます。
""",
        """
1. **选择笔记** — 检查可能发送的确切内容和最高预计费用。
2. **审核发现的规则** — 将每条规则与来源对照，只批准可信内容。
3. **保存到 Codex** — 导出前检查完整 Skill 和保存位置。

不确定的候选项可以保留，随时安全停止。
""",
    ),
    "quick.details_label": _entry(
        "Show the detailed five steps",
        "詳しい5ステップを見る",
        "查看详细的五个步骤",
    ),
    "quick.five_steps": _entry(
        """
1. Load a Vault folder and select only the notes you may send to AI.
2. Review the redacted JSON and maximum estimated cost before extraction.
3. Edit candidates against their sources and approve only the ones you will use.
4. Review the conversion and save an approved candidate as Skill DNA.
5. Review the complete `SKILL.md` and destination, then export the Codex Skill.
""",
        """
1. Vaultフォルダを読み込み、AIへ送るメモだけを選びます。
2. 伏字済みの送信JSONと料金上限を確認してから抽出します。
3. 出典を見ながら候補を編集し、使う候補だけを承認します。
4. 承認済み候補の変換前後を確認してSkill DNAへ保存します。
5. `SKILL.md`全文と出力先を確認し、Codex Skillとして出力します。
""",
        """
1. 加载 Vault 文件夹，只选择允许发送给 AI 的笔记。
2. 提取前检查脱敏后的 JSON 和最高预计费用。
3. 对照来源编辑候选项，只批准要使用的内容。
4. 检查转换前后，将已批准候选项保存为 Skill DNA。
5. 检查完整的 `SKILL.md` 和保存位置，然后导出 Codex Skill。
""",
    ),
    "local_first.title": _entry("Local-first", "ローカルファースト", "本地优先"),
    "local_first.body": _entry(
        """
- Notes and generated Skills stay on this PC.
- Notes you did not select are not sent to AI.
- A Skill candidate is never exported before human approval.
""",
        """
- メモや生成SkillはこのPCに保存します。
- 選択していないメモをAIへ送りません。
- Skill候補は人間が承認するまで出力しません。
""",
        """
- 笔记和生成的 Skill 保存在此电脑上。
- 未选择的笔记不会发送给 AI。
- Skill 候选项未经人工批准不会导出。
""",
    ),
    "credentials.title": _entry(
        "OpenAI API key settings",
        "OpenAI APIキー設定",
        "OpenAI API 密钥设置",
    ),
    "credentials.status": _entry(
        "OpenAI API key: **{state}**",
        "OpenAI APIキー: **{state}**",
        "OpenAI API 密钥：**{state}**",
    ),
    "credentials.model": _entry(
        "AI model: `{model}`",
        "AIモデル: `{model}`",
        "AI 模型：`{model}`",
    ),
    "credentials.database": _entry(
        "Local database: `{path}`",
        "ローカルDB: `{path}`",
        "本地数据库：`{path}`",
    ),
    "credentials.dev_caption": _entry(
        "Development mode reads the API key from the ignored `.env.local` file.",
        "開発版ではGit管理外の`.env.local`からAPIキーを読み込みます。",
        "开发模式从不受 Git 管理的 `.env.local` 文件读取 API 密钥。",
    ),
    "credentials.dev_missing": _entry(
        "To use live extraction, set `OPENAI_API_KEY=...` in the ignored `.env.local` beside the app and restart.",
        "実APIを使うには、アプリと同じフォルダのGit管理外`.env.local`へ`OPENAI_API_KEY=...`を設定してから再起動してください。",
        "如需使用实时提取，请在应用旁不受 Git 管理的 `.env.local` 中设置 `OPENAI_API_KEY=...`，然后重新启动。",
    ),
    "credentials.production_caption": _entry(
        "The API key is stored in Windows Credential Manager, not in the database, generated Skills, or logs.",
        "APIキーはWindows Credential Managerへ保存します。DB、生成Skill、ログには保存しません。",
        "API 密钥保存在 Windows 凭据管理器中，不会写入数据库、生成的 Skill 或日志。",
    ),
    "credentials.no_plaintext": _entry(
        "For safety, the app will not fall back to plaintext storage.",
        "安全のため、平文ファイルへの代替保存は行いません。",
        "为确保安全，应用不会回退到明文存储。",
    ),
    "credentials.input": _entry("OpenAI API key", "OpenAI APIキー", "OpenAI API 密钥"),
    "credentials.placeholder": _entry(
        "The entered value will not be shown again",
        "入力内容は画面に再表示されません",
        "输入内容不会再次显示",
    ),
    "credentials.save": _entry(
        "Save to Windows Credential Manager",
        "Windows資格情報ストアへ保存",
        "保存到 Windows 凭据管理器",
    ),
    "credentials.saved": _entry(
        "Saved the API key to Windows Credential Manager. No API request was made.",
        "APIキーをWindows資格情報ストアへ保存しました。API通信は行っていません。",
        "已将 API 密钥保存到 Windows 凭据管理器。未发起 API 请求。",
    ),
    "credentials.confirm_delete": _entry(
        "I confirm that I want to delete the saved API key",
        "保存済みAPIキーを削除することを確認しました",
        "我确认要删除已保存的 API 密钥",
    ),
    "credentials.delete": _entry(
        "Delete from Windows Credential Manager",
        "Windows資格情報ストアから削除",
        "从 Windows 凭据管理器中删除",
    ),
    "credentials.deleted": _entry(
        "Deleted the saved API key.",
        "保存済みAPIキーを削除しました。",
        "已删除保存的 API 密钥。",
    ),
    "credentials.none_saved": _entry(
        "No saved API key was found.",
        "保存済みAPIキーはありません。",
        "未找到已保存的 API 密钥。",
    ),
    "vault.title": _entry(
        "1. Select Obsidian notes",
        "1. Obsidianメモを選ぶ",
        "1. 选择 Obsidian 笔记",
    ),
    "vault.caption": _entry(
        "Paste the absolute path of the Vault folder. The source files remain read-only.",
        "Vaultフォルダの絶対パスを貼り付けてください。元ファイルは読み取り専用です。",
        "粘贴 Vault 文件夹的绝对路径。源文件保持只读。",
    ),
    "vault.path": _entry("Vault folder", "Vaultフォルダ", "Vault 文件夹"),
    "vault.exclusions": _entry(
        "Excluded folders (comma-separated)",
        "除外フォルダ（カンマ区切り）",
        "排除的文件夹（以逗号分隔）",
    ),
    "vault.use_sample": _entry(
        "Use bundled Sample Vault",
        "同梱Sample Vaultを使う",
        "使用随附的 Sample Vault",
    ),
    "vault.sample_ready": _entry(
        "Filled the bundled Sample Vault path. Press **Load Vault** to scan it.",
        "同梱Sample Vaultのパスを入力しました。**Vaultを読み込む**を押して読み込んでください。",
        "已填入随附 Sample Vault 的路径。请按 **加载 Vault** 进行扫描。",
    ),
    "vault.load": _entry("Load Vault", "Vaultを読み込む", "加载 Vault"),
    "vault.path_required": _entry(
        "Enter the absolute path of a Vault folder.",
        "Vaultフォルダの絶対パスを入力してください。",
        "请输入 Vault 文件夹的绝对路径。",
    ),
    "vault.loaded": _entry(
        "Loaded {count} Markdown note(s). The source files were not changed.",
        "Markdownメモを{count}件読み込みました。元ファイルは変更していません。",
        "已加载 {count} 条 Markdown 笔记。未修改源文件。",
    ),
    "vault.folder_filter": _entry(
        "Filter by folder",
        "フォルダで絞り込み",
        "按文件夹筛选",
    ),
    "vault.all": _entry("All", "すべて", "全部"),
    "vault.search": _entry(
        "Search file names and paths",
        "ファイル名・パスで検索",
        "搜索文件名和路径",
    ),
    "vault.table_file": _entry("File", "ファイル", "文件"),
    "vault.table_path": _entry("Path", "パス", "路径"),
    "vault.table_size": _entry("Size", "サイズ", "大小"),
    "vault.table_modified": _entry("Modified", "更新日時", "修改时间"),
    "vault.no_matches": _entry(
        "No notes match the current filters.",
        "検索条件に一致するメモはありません。",
        "没有符合当前筛选条件的笔记。",
    ),
    "vault.analysis_selection": _entry(
        "Notes to analyze (not sent yet)",
        "AI分析対象候補（まだ送信されません）",
        "要分析的笔记（尚未发送）",
    ),
    "vault.preview": _entry(
        "Note to preview",
        "プレビューするメモ",
        "预览笔记",
    ),
    "payload.title": _entry(
        "2. Review AI payload and extract",
        "2. AI送信内容の安全確認と抽出",
        "2. 检查 AI 发送内容并提取",
    ),
    "payload.caption": _entry(
        "Preparing does not send anything. A live OpenAI request occurs only after you review the redacted JSON and separately confirm both content and possible charges.",
        "準備しただけでは送信しません。伏字後のJSONを確認し、内容と料金を別々に確認した場合だけOpenAIへ送信します。",
        "仅准备内容不会发送任何数据。只有检查脱敏后的 JSON，并分别确认内容和可能费用后，才会向 OpenAI 发起实时请求。",
    ),
    "payload.select_note": _entry(
        "Select at least one note for analysis.",
        "AI分析対象候補から1件以上のメモを選択してください。",
        "请至少选择一条要分析的笔记。",
    ),
    "payload.prepare": _entry(
        "Prepare outbound content",
        "送信内容を準備する",
        "准备发送内容",
    ),
    "payload.summary": _entry(
        "Planned payload: **{documents} document(s)** / **{characters:,} characters** / **{redactions} redaction(s)**",
        "送信予定: **{documents}件** / **{characters:,}文字** / 伏字 **{redactions}件**",
        "计划发送：**{documents} 个文档** / **{characters:,} 个字符** / **{redactions} 处脱敏**",
    ),
    "payload.redacted_warning": _entry(
        "Possible secrets or personal information were automatically redacted.",
        "秘密情報または個人情報の可能性がある箇所を自動で伏字にしました。",
        "可能包含密钥或个人信息的内容已自动脱敏。",
    ),
    "payload.no_findings": _entry(
        "No known secret or contact-information patterns were detected.",
        "既知の秘密情報・連絡先パターンは検出されませんでした。",
        "未检测到已知的密钥或联系信息模式。",
    ),
    "payload.table_location": _entry("Location", "場所", "位置"),
    "payload.table_line": _entry("Line", "行", "行"),
    "payload.table_kind": _entry("Type", "種類", "类型"),
    "payload.table_severity": _entry("Severity", "重要度", "严重程度"),
    "payload.table_replacement": _entry("Replacement", "置換", "替换内容"),
    "payload.json_title": _entry(
        "#### Exact outbound JSON",
        "#### 実際に送信されるJSON",
        "#### 实际发送的 JSON",
    ),
    "cost.unavailable": _entry(
        "Live extraction is disabled because pricing for the configured model has not been reviewed.",
        "設定中のモデルは料金情報を確認できていないため、実API抽出を無効にしました。",
        "由于尚未审核当前模型的价格信息，实时提取已被禁用。",
    ),
    "cost.title": _entry(
        "#### Live API size and cost estimate",
        "#### 実APIの入力規模・料金目安",
        "#### 实时 API 输入规模和费用估算",
    ),
    "cost.model": _entry(
        "Model: `{model}` / reasoning effort: `{effort}`",
        "モデル: `{model}` / reasoning effort: `{effort}`",
        "模型：`{model}` / 推理强度：`{effort}`",
    ),
    "cost.tokens": _entry(
        "Estimated input: **{low:,}–{high:,} tokens** / Maximum output: **{maximum:,} tokens**",
        "入力推定: **{low:,}～{high:,} tokens** / 最大出力: **{maximum:,} tokens**",
        "预计输入：**{low:,}–{high:,} tokens** / 最大输出：**{maximum:,} tokens**",
    ),
    "cost.amount": _entry(
        "Estimated input cost: **${low:.4f}–${high:.4f}** / Conservative maximum total: **${maximum:.4f}**",
        "入力料金目安: **${low:.4f}～${high:.4f}** / 最大出力まで使った場合の上限目安: **${maximum:.4f}**",
        "预计输入费用：**${low:.4f}–${high:.4f}** / 保守的最高总费用：**${maximum:.4f}**",
    ),
    "cost.review_date": _entry(
        "Pricing reviewed on {date}. This local estimate may differ from the final bill.",
        "料金確認日: {date}。ローカル推定のため実請求額とは異なる場合があります。",
        "价格审核日期：{date}。本地估算可能与最终账单不同。",
    ),
    "cost.official_link": _entry(
        "Check official OpenAI pricing",
        "OpenAI公式料金を確認する",
        "查看 OpenAI 官方价格",
    ),
    "cost.long_context": _entry(
        "The conservative maximum includes possible long-context pricing.",
        "長い入力向けの割増料金に入る可能性があるため、上限目安へ割増を反映しました。",
        "保守的最高费用已包含可能适用的长上下文加价。",
    ),
    "payload.confirm": _entry(
        "I reviewed the redacted outbound content",
        "伏字済みの送信内容を確認しました",
        "我已检查脱敏后的发送内容",
    ),
    "extract.mock": _entry(
        "Run mock extraction",
        "モック抽出を実行する",
        "运行模拟提取",
    ),
    "extract.retry_mock": _entry(
        "You can retry with the same button without changing the content.",
        "内容を変更せず、同じボタンから再試行できます。",
        "无需更改内容，可使用同一按钮重试。",
    ),
    "extract.mock_label": _entry("Mock extraction", "モック抽出", "模拟提取"),
    "extract.api_missing": _entry(
        "Live extraction is unavailable because no OpenAI API key is configured.",
        "OpenAI APIキーが未設定のため、実API抽出は利用できません。",
        "由于未配置 OpenAI API 密钥，无法使用实时提取。",
    ),
    "extract.cost_confirm": _entry(
        "I reviewed the displayed estimate and agree to possible API charges",
        "表示された料金目安を確認し、API料金の発生に同意します",
        "我已检查显示的费用估算，并同意可能产生 API 费用",
    ),
    "extract.live": _entry(
        "Extract with OpenAI (API charges may apply)",
        "OpenAIで実抽出する（API料金が発生します）",
        "使用 OpenAI 实时提取（可能产生 API 费用）",
    ),
    "extract.spinner": _entry(
        "Extracting Skill candidates with OpenAI…",
        "OpenAIでSkill候補を抽出しています…",
        "正在使用 OpenAI 提取 Skill 候选项…",
    ),
    "extract.retry_live": _entry(
        "Review the content and cost estimate again before retrying.",
        "送信内容と料金目安を再確認してから再試行できます。",
        "重试前请再次检查发送内容和费用估算。",
    ),
    "extract.live_label": _entry("OpenAI extraction", "OpenAI実抽出", "OpenAI 实时提取"),
    "extract.generic_label": _entry("Extraction", "抽出", "提取"),
    "extract.completed": _entry(
        "{provider} completed. Candidates: {count}",
        "{provider}が完了しました。候補数: {count}",
        "{provider}已完成。候选项数量：{count}",
    ),
    "extract.no_candidates": _entry(
        "No reusable Skill candidates were found. This is a valid result.",
        "再利用可能なSkill候補は見つかりませんでした。これは正常な結果です。",
        "未发现可复用的 Skill 候选项。这是正常结果。",
    ),
    "extract.verified_candidates": _entry(
        "### Verified Skill candidates",
        "### 検証済みSkill候補",
        "### 已验证的 Skill 候选项",
    ),
    "extract.not_approved": _entry(
        "These candidates are not approved or compiled yet.",
        "まだ承認・Skill化されていません。",
        "这些候选项尚未批准或编译。",
    ),
    "extract.confidence": _entry(
        "{index}. {name} (confidence {confidence:.0%})",
        "{index}. {name}（信頼度 {confidence:.0%}）",
        "{index}. {name}（置信度 {confidence:.0%}）",
    ),
    "extract.category": _entry(
        "Category: `{category}` / Generality: `{generality}`",
        "カテゴリ: `{category}` / 一般性: `{generality}`",
        "类别：`{category}` / 通用性：`{generality}`",
    ),
    "extract.confidence_reason": _entry(
        "Confidence reason: {reason}",
        "信頼度の理由: {reason}",
        "置信度理由：{reason}",
    ),
    "extract.triggers": _entry("**Use when**", "**利用場面**", "**适用场景**"),
    "extract.workflow": _entry("**Workflow**", "**手順**", "**步骤**"),
    "extract.sources": _entry(
        "**Verified citations**",
        "**検証済み引用**",
        "**已验证引用**",
    ),
    "extract.actual_usage": _entry(
        "Live API usage: input {input:,} / output {output:,} / total {total:,} tokens / estimated cost ${cost}",
        "実API使用量: 入力 {input:,} / 出力 {output:,} / 合計 {total:,} tokens / 料金推定 ${cost}",
        "实时 API 用量：输入 {input:,} / 输出 {output:,} / 合计 {total:,} tokens / 预计费用 ${cost}",
    ),
    "extract.mock_free": _entry(
        "No network request or API charge occurred.",
        "ネットワーク通信とAPI料金は発生していません。",
        "未发生网络请求或 API 费用。",
    ),
    "candidate.title": _entry(
        "3. Review Skill candidates",
        "3. Skill候補をレビューする",
        "3. 审核 Skill 候选项",
    ),
    "candidate.caption": _entry(
        "Candidates are stored locally. Approval at this step does not create Skill DNA or export a file.",
        "候補はローカルDBに保存されています。この段階で承認してもSkill DNAやファイルは作成されません。",
        "候选项保存在本地。此步骤的批准不会创建 Skill DNA 或导出文件。",
    ),
    "candidate.filter": _entry("Status to show", "表示する状態", "显示状态"),
    "status.all": _entry("All", "すべて", "全部"),
    "status.pending": _entry("Pending", "未確認", "待审核"),
    "status.approved": _entry("Approved", "承認済み", "已批准"),
    "status.hold": _entry("On hold", "保留", "保留"),
    "status.rejected": _entry("Rejected", "却下", "已拒绝"),
    "candidate.none": _entry(
        "No Skill candidates are available yet.",
        "表示できるSkill候補はまだありません。",
        "目前没有可显示的 Skill 候选项。",
    ),
    "candidate.select": _entry(
        "Candidate to review",
        "レビューする候補",
        "要审核的候选项",
    ),
    "candidate.state": _entry(
        "Current status: `{status}` / Confidence: `{confidence:.0%}`",
        "現在の状態: `{status}` / 信頼度: `{confidence:.0%}`",
        "当前状态：`{status}` / 置信度：`{confidence:.0%}`",
    ),
    "candidate.sources_locked": _entry(
        "Validated sources (not editable)",
        "変更できない引用元",
        "已验证来源（不可编辑）",
    ),
    "candidate.document_id": _entry(
        "Document ID: {document_id}",
        "文書ID: {document_id}",
        "文档 ID：{document_id}",
    ),
    "candidate.name": _entry("Candidate name", "候補名", "候选项名称"),
    "candidate.description": _entry("Description", "説明", "说明"),
    "candidate.category": _entry("Category", "カテゴリ", "类别"),
    "candidate.generality": _entry("Generality", "汎用性", "通用性"),
    "candidate.triggers": _entry(
        "Use when (one per line)",
        "利用場面（1行に1件）",
        "适用场景（每行一项）",
    ),
    "candidate.exclusions": _entry(
        "Do not use when (one per line)",
        "利用しない場面（1行に1件）",
        "不适用场景（每行一项）",
    ),
    "candidate.principles": _entry(
        "Principles (one per line)",
        "原則（1行に1件）",
        "原则（每行一项）",
    ),
    "candidate.steps": _entry(
        "Workflow (one step per line)",
        "手順（1行に1件）",
        "步骤（每行一步）",
    ),
    "candidate.constraints": _entry(
        "Constraints (one per line)",
        "制約（1行に1件）",
        "约束（每行一项）",
    ),
    "candidate.warnings": _entry(
        "Warnings (one per line)",
        "注意事項（1行に1件）",
        "警告（每行一项）",
    ),
    "candidate.save_edit": _entry("Save edits", "編集内容を保存", "保存编辑"),
    "candidate.edit_failed": _entry(
        "Could not save edits: {error}",
        "編集内容を保存できません: {error}",
        "无法保存编辑：{error}",
    ),
    "candidate.edited": _entry(
        "Saved the edits and returned the candidate to Pending.",
        "編集内容を保存し、状態を未確認へ戻しました。",
        "已保存编辑，并将候选项恢复为待审核状态。",
    ),
    "candidate.old_trace": _entry(
        "This candidate was approved by an older version, but its current DNA Trace review is incomplete. It cannot be compiled or exported until it is reviewed again.",
        "この候補は以前の版で承認済みですが、現行のDNA Trace確認は未完了です。再確認が終わるまでSkill DNA化と出力はできません。",
        "此候选项曾由旧版本批准，但当前 DNA Trace 审核尚未完成。重新审核前无法编译或导出。",
    ),
    "candidate.status_only": _entry(
        "Changing status updates only the candidate record; it does not create a Skill file.",
        "状態の変更は候補データだけに保存され、Skillファイルは作成されません。",
        "更改状态只会更新候选项记录，不会创建 Skill 文件。",
    ),
    "candidate.reset": _entry("Return to Pending", "未確認に戻す", "恢复为待审核"),
    "candidate.approve": _entry("Approve", "承認する", "批准"),
    "candidate.hold": _entry("Put on hold", "保留にする", "设为保留"),
    "candidate.reject": _entry("Reject", "却下する", "拒绝"),
    "trace.title": _entry(
        "#### Evidence review (DNA Trace)",
        "#### 根拠の確認（DNA Trace）",
        "#### 证据审核（DNA Trace）",
    ),
    "trace.summary": _entry(
        "Passed {approved}/{total}. Compare every rule that may enter the Skill with the source note.",
        "根拠確認を通過 {approved}/{total}。Skillへ入れる各ルールを元メモと照合します。",
        "已通过 {approved}/{total}。请将每条可能进入 Skill 的规则与源笔记对照。",
    ),
    "trace.progress": _entry(
        "Rules eligible for the Skill: {approved}/{total}",
        "Skillへ入れられるルール: {approved}/{total}",
        "可进入 Skill 的规则：{approved}/{total}",
    ),
    "trace.instructions_label": _entry(
        "What to do on this screen",
        "この画面でやること",
        "此页面的操作方法",
    ),
    "trace.instructions": _entry(
        """
1. Select the citations that directly support this rule.
2. Check whether the citation means the same thing and whether the rule is high-impact.
3. Approve, hold, or reject the rule, then save the review.

If you are unsure, leave it **on hold**. Unreviewed rules are not exported.
""",
        """
1. このルールを直接支える引用を選びます。
2. 引用とルールの意味が同じか、危険な操作を含むか確認します。
3. 承認・保留・却下を選び、確認結果を保存します。

分からない場合は**保留**のままで大丈夫です。未確認のルールはSkillへ出力されません。
""",
        """
1. 选择直接支持此规则的引用。
2. 检查引用与规则含义是否一致，以及规则是否影响较大。
3. 批准、保留或拒绝该规则，然后保存审核结果。

如不确定，请保持**保留**。未审核的规则不会导出。
""",
    ),
    "trace.select_instruction": _entry(
        "Instruction to review",
        "確認する指示",
        "要审核的指令",
    ),
    "trace.direct_sources": _entry(
        "Citations that directly support this instruction",
        "この指示を直接支える引用",
        "直接支持此指令的引用",
    ),
    "trace.no_evidence": _entry(
        "No, there is no supporting evidence",
        "いいえ（根拠がない）",
        "否，没有支持证据",
    ),
    "trace.related_evidence": _entry(
        "Related content exists",
        "関連する内容はある",
        "存在相关内容",
    ),
    "trace.direct_evidence": _entry(
        "Yes, it is stated directly",
        "はい（直接書かれている）",
        "是，来源中有直接说明",
    ),
    "trace.traceability_help": _entry(
        "DNA Trace calls this traceability. Approval requires direct evidence.",
        "DNA Traceの詳細評価名では「追跡可能性」です。承認には直接根拠が必要です。",
        "DNA Trace 将此项称为可追溯性。批准需要直接证据。",
    ),
    "trace.traceability": _entry(
        "Does the source note directly support this rule?",
        "元メモに、このルールを直接支える内容がありますか？",
        "源笔记是否直接支持此规则？",
    ),
    "trace.fidelity": _entry(
        "Do the citation and rule have the same meaning and conditions?",
        "引用とルールの意味・条件は一致していますか？",
        "引用与规则的含义和条件是否一致？",
    ),
    "trace.fidelity_none": _entry(
        "The meaning does not match or unsupported meaning was added",
        "一致しない、または書かれていない意味が増えている",
        "含义不一致，或增加了来源中没有的含义",
    ),
    "trace.fidelity_partial": _entry(
        "Partly matches, but conditions are missing",
        "一部一致するが、条件が足りない",
        "部分一致，但缺少条件",
    ),
    "trace.fidelity_full": _entry(
        "Meaning and conditions match",
        "意味と条件が一致している",
        "含义和条件一致",
    ),
    "trace.fidelity_help": _entry(
        "DNA Trace calls this fidelity. Approval requires a complete match.",
        "DNA Traceの詳細評価名では「意味の一致」です。承認には完全な一致が必要です。",
        "DNA Trace 将此项称为保真度。批准需要完全一致。",
    ),
    "trace.impact": _entry(
        "Could this rule materially affect money, deletion, publication, or similar actions?",
        "お金・削除・公開などに大きく影響するルールですか？",
        "此规则是否会对付款、删除、发布等操作产生重大影响？",
    ),
    "trace.impact_unknown": _entry(
        "Not decided yet (cannot approve)",
        "まだ判断していない（承認不可）",
        "尚未判断（无法批准）",
    ),
    "trace.impact_normal": _entry(
        "No, this is a normal rule",
        "いいえ、通常のルール",
        "否，这是普通规则",
    ),
    "trace.impact_high": _entry(
        "Yes, the impact is high",
        "はい、影響が大きい",
        "是，影响较大",
    ),
    "trace.impact_help": _entry(
        "Check whether failure could materially affect deletion, payment, publication, or external transmission.",
        "削除、支払い、公開、外部送信など、失敗時の影響が大きい指示かを確認します。",
        "检查失败是否会对删除、付款、发布或外部发送产生重大影响。",
    ),
    "trace.boundary": _entry(
        "Are important use conditions and prohibitions sufficient?",
        "重要な使用条件や、してはいけないことは十分ですか？",
        "重要使用条件和禁止事项是否充分？",
    ),
    "trace.boundary_unknown": _entry(
        "Not reviewed yet / not applicable unless high-impact",
        "まだ確認していない／高影響でなければ対象外",
        "尚未审核／非高影响规则时不适用",
    ),
    "trace.boundary_missing": _entry(
        "Missing",
        "不足している",
        "不足",
    ),
    "trace.boundary_partial": _entry(
        "Present but insufficient",
        "一部あるが不十分",
        "已有部分内容，但不充分",
    ),
    "trace.boundary_full": _entry(
        "Sufficient",
        "十分に書かれている",
        "充分",
    ),
    "trace.boundary_help": _entry(
        "High-impact rules require sufficient conditions and prohibitions before approval.",
        "影響が大きいルールを承認する場合だけ、十分な条件と禁止事項が必要です。",
        "高影响规则必须具备充分的条件和禁止事项后才能批准。",
    ),
    "trace.decision": _entry(
        "What should happen to this rule?",
        "このルールをどうしますか？",
        "如何处理此规则？",
    ),
    "trace.note": _entry(
        "Review note (optional; do not store secrets or note bodies)",
        "確認メモ（任意・秘密やメモ本文は記録しない）",
        "审核备注（可选；请勿保存密钥或笔记正文）",
    ),
    "trace.save": _entry(
        "Save this rule review",
        "このルールの確認結果を保存",
        "保存此规则的审核结果",
    ),
    "trace.terms_label": _entry(
        "Show DNA Trace terms",
        "DNA Traceの評価用語を見る",
        "查看 DNA Trace 术语",
    ),
    "trace.terms": _entry(
        """
- **Traceability**: Does the source note directly support the rule?
- **Fidelity**: Did the rule add meaning or conditions absent from the citation?
- **Impact**: Could the rule materially affect payment, deletion, publication, or transmission?
- **Conditions and prohibitions**: Are the boundaries sufficient for a high-impact rule?
""",
        """
- **追跡可能性**: 元メモがルールを直接支えているか
- **意味の一致**: 引用にない条件や命令が増えていないか
- **影響度**: お金・削除・公開・外部送信などへの影響が大きいか
- **使用条件・禁則**: 高影響なルールを安全に使う境界が十分か
""",
        """
- **可追溯性**：源笔记是否直接支持规则
- **保真度**：规则是否增加了引用中没有的含义或条件
- **影响程度**：规则是否会对付款、删除、发布或发送产生重大影响
- **条件和禁止事项**：高影响规则的边界是否充分
""",
    ),
    "trace.saved": _entry(
        "Saved the DNA Trace review and returned the candidate to Pending.",
        "DNA Traceを保存しました。候補全体は未確認へ戻ります。",
        "已保存 DNA Trace 审核，并将候选项恢复为待审核状态。",
    ),
    "trace.save_failed": _entry(
        "Could not save the DNA Trace review: {error}",
        "DNA Traceを保存できません: {error}",
        "无法保存 DNA Trace 审核：{error}",
    ),
    "trace.incomplete": _entry(
        "Cannot approve while {count} review item(s) remain incomplete.",
        "未完了のため承認できません（{count}件）。",
        "仍有 {count} 项审核未完成，无法批准。",
    ),
    "trace.incomplete_label": _entry(
        "Show incomplete items",
        "未完了項目を確認",
        "查看未完成项目",
    ),
    "trace.passed": _entry(
        "Every instruction passes the DNA Trace gate.",
        "すべての指示がDNA Trace gateを満たしています。",
        "所有指令均通过 DNA Trace 门控。",
    ),
    "duplicate.title": _entry(
        "Optional: Review possible duplicates",
        "任意: 重複候補を確認する",
        "可选：审核可能的重复候选项",
    ),
    "duplicate.caption": _entry(
        "Similarity is a local review aid. Nothing is merged automatically.",
        "類似度はローカルで計算する参考情報です。自動統合は行いません。",
        "相似度仅用于本地审核参考，不会自动合并。",
    ),
    "duplicate.none": _entry(
        "No similar pairs are currently suggested.",
        "現在、統合候補として提示する類似ペアはありません。",
        "目前没有建议合并的相似候选项。",
    ),
    "duplicate.select": _entry(
        "Similar pair to review",
        "確認する類似ペア",
        "要审核的相似候选项",
    ),
    "duplicate.primary_select": _entry(
        "Primary candidate (basis for name, description, and category)",
        "主候補（名前・説明・カテゴリの基準）",
        "主候选项（名称、说明和类别的基础）",
    ),
    "duplicate.reasons": _entry(
        "Similarity reasons: {reasons}",
        "類似理由: {reasons}",
        "相似原因：{reasons}",
    ),
    "duplicate.primary": _entry("Primary", "主候補", "主候选项"),
    "duplicate.secondary": _entry(
        "Candidate to merge",
        "統合する候補",
        "要合并的候选项",
    ),
    "duplicate.state_sources": _entry(
        "Status: {status} / Sources: {sources}",
        "状態: {status} / 引用元: {sources}件",
        "状态：{status} / 来源：{sources}",
    ),
    "duplicate.preview": _entry(
        "Review merged content",
        "統合後の内容を確認",
        "检查合并后的内容",
    ),
    "duplicate.merged_name": _entry(
        "Candidate name: {name}",
        "候補名: {name}",
        "候选项名称：{name}",
    ),
    "duplicate.merged_description": _entry(
        "Description: {description}",
        "説明: {description}",
        "说明：{description}",
    ),
    "duplicate.merged_sources": _entry(
        "Sources: {count}",
        "引用元: {count}件",
        "来源：{count}",
    ),
    "duplicate.merged_steps": _entry(
        "Workflow steps: {steps} / Principles: {principles}",
        "手順: {steps}件 / 原則: {principles}件",
        "步骤：{steps} / 原则：{principles}",
    ),
    "duplicate.after_caption": _entry(
        "You can edit the merged candidate in the normal review screen before approval.",
        "統合後は通常の候補レビュー画面で編集してから承認できます。",
        "合并后可在普通审核页面中编辑，再进行批准。",
    ),
    "duplicate.confirm": _entry(
        "Put both source candidates on hold and save the merge as a new Pending candidate",
        "元の2候補を保留にし、統合結果を新しい未確認候補として保存します",
        "将两个来源候选项设为保留，并将合并结果保存为新的待审核候选项",
    ),
    "duplicate.merge": _entry(
        "Merge as a Pending candidate",
        "未確認候補として統合",
        "合并为待审核候选项",
    ),
    "duplicate.failed": _entry(
        "Could not merge candidates: {error}",
        "候補を統合できません: {error}",
        "无法合并候选项：{error}",
    ),
    "duplicate.saved": _entry(
        "Saved the merged candidate and put both source candidates on hold.",
        "統合候補を保存し、元の2候補を保留にしました。",
        "已保存合并候选项，并将两个来源候选项设为保留。",
    ),
    "skill_dna.title": _entry(
        "4. Compile an approved candidate as Skill DNA",
        "4. 承認済み候補をSkill DNA化する",
        "4. 将已批准候选项编译为 Skill DNA",
    ),
    "skill_dna.caption": _entry(
        "A separate action saves an approved candidate to the local database. No file is exported at this step.",
        "承認済み候補だけを別操作でローカルDBへ保存します。この段階ではファイルを出力しません。",
        "通过单独操作将已批准候选项保存到本地数据库。此步骤不会导出文件。",
    ),
    "skill_dna.none": _entry(
        "No candidate currently passes DNA Trace and is eligible for Skill DNA.",
        "DNA Trace確認済みで、Skill DNAへ変換できる候補はありません。",
        "目前没有通过 DNA Trace 且可编译为 Skill DNA 的候选项。",
    ),
    "skill_dna.blocked": _entry(
        "Excluded {count} Approved candidate(s) because DNA Trace is incomplete. Review the evidence in step 3.",
        "承認済み表示の候補{count}件はDNA Trace未完了のため除外しました。ステップ3で根拠を再確認してください。",
        "已排除 {count} 个已批准候选项，因为 DNA Trace 尚未完成。请在步骤 3 中重新审核证据。",
    ),
    "skill_dna.select": _entry(
        "Approved candidate to compile",
        "Skill DNA化する承認済み候補",
        "要编译的已批准候选项",
    ),
    "skill_dna.prepare_failed": _entry(
        "Could not prepare Skill DNA: {error}",
        "Skill DNAを準備できません: {error}",
        "无法准备 Skill DNA：{error}",
    ),
    "skill_dna.before": _entry(
        "**Before: approved candidate**",
        "**変換前：承認済み候補**",
        "**转换前：已批准候选项**",
    ),
    "skill_dna.after": _entry(
        "**After: Skill DNA v{version}**",
        "**変換後：Skill DNA v{version}**",
        "**转换后：Skill DNA v{version}**",
    ),
    "skill_dna.save": _entry(
        "Save as Skill DNA",
        "Skill DNAとして保存",
        "保存为 Skill DNA",
    ),
    "skill_dna.update": _entry(
        "Update Skill DNA and save a new version",
        "Skill DNAを更新して新しい版を保存",
        "更新 Skill DNA 并保存新版本",
    ),
    "skill_dna.confirm": _entry(
        "I reviewed the before-and-after content and will save it to the local database",
        "変換前後を確認し、ローカルDBへ保存します",
        "我已检查转换前后的内容，并将其保存到本地数据库",
    ),
    "skill_dna.failed": _entry(
        "Could not save Skill DNA: {error}",
        "Skill DNAを保存できません: {error}",
        "无法保存 Skill DNA：{error}",
    ),
    "skill_dna.saved": _entry(
        "Saved {name} as Skill DNA v{version}.",
        "{name}をSkill DNA v{version}として保存しました。",
        "已将 {name} 保存为 Skill DNA v{version}。",
    ),
    "skill_dna.history": _entry(
        "Current version: {current} / Saved history: {versions}",
        "現在版: {current} / 保存済み履歴: {versions}",
        "当前版本：{current} / 已保存历史：{versions}",
    ),
    "export.title": _entry(
        "5. Export a Codex Skill",
        "5. Codex Skillを出力する",
        "5. 导出 Codex Skill",
    ),
    "export.caption": _entry(
        "Preview `SKILL.md` from saved Skill DNA and export only inside the destination you specify.",
        "保存済みSkill DNAから`SKILL.md`をプレビューし、指定したフォルダの内側だけへ出力します。",
        "从已保存的 Skill DNA 预览 `SKILL.md`，并仅导出到指定文件夹内。",
    ),
    "export.none": _entry(
        "No current Skill DNA is eligible for export.",
        "現行DNA Traceで確認済みの、出力できるSkill DNAはまだありません。",
        "目前没有符合导出条件的 Skill DNA。",
    ),
    "export.blocked": _entry(
        "Excluded {count} saved Skill DNA record(s) because DNA Trace is incomplete or the candidate changed. Review steps 3 and 4.",
        "保存済みSkill DNA {count}件はDNA Trace未確認または候補更新後のため除外しました。ステップ3と4で再確認してください。",
        "已排除 {count} 个已保存的 Skill DNA，因为 DNA Trace 未完成或候选项已更改。请重新检查步骤 3 和 4。",
    ),
    "export.select": _entry(
        "Skill DNA to export",
        "出力するSkill DNA",
        "要导出的 Skill DNA",
    ),
    "export.destination": _entry(
        "Parent destination folder",
        "出力先の親フォルダ",
        "目标父文件夹",
    ),
    "export.placeholder": _entry(
        r"Example: C:\Users\name\.codex\skills",
        r"例: C:\Users\ユーザー名\.codex\skills",
        r"示例：C:\Users\用户名\.codex\skills",
    ),
    "export.destination_info": _entry(
        "Enter an existing destination folder to preview before saving.",
        "既に存在する出力先フォルダを入力すると、保存前プレビューを表示します。",
        "请输入已存在的目标文件夹，以便在保存前预览。",
    ),
    "export.prepare_failed": _entry(
        "Could not prepare the destination: {error}",
        "出力先を準備できません: {error}",
        "无法准备目标位置：{error}",
    ),
    "export.planned": _entry(
        "Planned output: `{path}`",
        "出力予定: `{path}`",
        "计划输出：`{path}`",
    ),
    "export.overwrite_warning": _entry(
        "A `SKILL.md` already exists there. Replacing it requires an additional confirmation.",
        "同じ場所に`SKILL.md`が存在します。内容を置き換えるには追加確認が必要です。",
        "该位置已存在 `SKILL.md`。替换它需要额外确认。",
    ),
    "export.confirm": _entry(
        "I reviewed the complete content and destination",
        "出力内容と出力先を確認しました",
        "我已检查完整内容和目标位置",
    ),
    "export.confirm_overwrite": _entry(
        "Replace the existing `SKILL.md`",
        "既存の`SKILL.md`を上書きします",
        "替换现有的 `SKILL.md`",
    ),
    "export.button": _entry("Export `SKILL.md`", "`SKILL.md`を出力", "导出 `SKILL.md`"),
    "export.failed": _entry(
        "Could not export `SKILL.md`: {error}",
        "`SKILL.md`を出力できません: {error}",
        "无法导出 `SKILL.md`：{error}",
    ),
    "export.saved": _entry(
        "Exported `SKILL.md`: {path}",
        "`SKILL.md`を出力しました: {path}",
        "已导出 `SKILL.md`：{path}",
    ),
    "export.history": _entry(
        "Export history: {history}",
        "出力履歴: {history}",
        "导出历史：{history}",
    ),
    "feedback.title": _entry(
        "Optional: Record how a generated Skill performed",
        "任意: 生成Skillの使用結果を記録する",
        "可选：记录生成 Skill 的使用结果",
    ),
    "feedback.caption": _entry(
        "Feedback stays in the local database and never changes a Skill automatically.",
        "記録はこのPCのローカルDBだけに保存され、Skillを自動変更しません。",
        "反馈仅保存在本地数据库中，不会自动修改 Skill。",
    ),
    "feedback.none": _entry(
        "No Skill DNA is available for feedback yet.",
        "使用結果を記録できるSkill DNAはまだありません。",
        "目前没有可记录反馈的 Skill DNA。",
    ),
    "feedback.select": _entry(
        "Skill to evaluate",
        "使用結果を記録するSkill",
        "要评价的 Skill",
    ),
    "feedback.not_used": _entry("Not used yet", "まだ使っていない", "尚未使用"),
    "feedback.used_once": _entry("Used once", "1回使った", "使用过一次"),
    "feedback.reused": _entry(
        "Reused multiple times",
        "複数回再利用した",
        "已多次复用",
    ),
    "feedback.not_evaluated": _entry(
        "Not evaluated yet",
        "まだ評価しない",
        "尚未评价",
    ),
    "feedback.helpful": _entry("Helpful", "役立った", "有帮助"),
    "feedback.partly": _entry("Partly helpful", "一部役立った", "部分有帮助"),
    "feedback.not_helpful": _entry("Not helpful", "役立たなかった", "没有帮助"),
    "feedback.usage": _entry("Usage", "利用状況", "使用情况"),
    "feedback.usefulness": _entry("Usefulness", "役立ち度", "帮助程度"),
    "feedback.worked": _entry(
        "What worked well (optional)",
        "良かった点（任意）",
        "效果良好的方面（可选）",
    ),
    "feedback.improve": _entry(
        "What should improve (optional)",
        "改善したい点（任意）",
        "需要改进的方面（可选）",
    ),
    "feedback.safety": _entry(
        "Do not enter API keys, note bodies, passwords, or personal information.",
        "APIキー、メモ本文、パスワード、個人情報は入力しないでください。",
        "请勿输入 API 密钥、笔记正文、密码或个人信息。",
    ),
    "feedback.save": _entry(
        "Save feedback locally",
        "使用結果をローカル保存",
        "在本地保存反馈",
    ),
    "feedback.failed": _entry(
        "Could not save feedback: {error}",
        "使用結果を保存できません: {error}",
        "无法保存反馈：{error}",
    ),
    "feedback.saved": _entry(
        "Saved local feedback for {name} v{version}.",
        "{name} v{version}の使用結果をローカル保存しました。",
        "已在本地保存 {name} v{version} 的反馈。",
    ),
    "feedback.date": _entry("Date", "日時", "日期"),
    "feedback.version": _entry("Skill version", "Skill版", "Skill 版本"),
    "feedback.good": _entry("Worked well", "良かった点", "效果良好"),
    "feedback.improvement": _entry("Improvement", "改善点", "改进点"),
    "database.title": _entry(
        "Local data protection",
        "ローカルデータ保護",
        "本地数据保护",
    ),
    "database.schema": _entry(
        "Database schema version: `{version}`",
        "DBスキーマバージョン: `{version}`",
        "数据库架构版本：`{version}`",
    ),
    "database.directory": _entry(
        "Backup directory: `{path}`",
        "バックアップ保存先: `{path}`",
        "备份目录：`{path}`",
    ),
    "database.create": _entry(
        "Create database backup now",
        "今すぐDBバックアップを作成",
        "立即创建数据库备份",
    ),
    "database.created": _entry(
        "Created a validated backup: {name}",
        "検証済みバックアップを作成しました: {name}",
        "已创建通过验证的备份：{name}",
    ),
    "database.none": _entry(
        "No backups exist yet.",
        "バックアップはまだありません。",
        "目前没有备份。",
    ),
    "database.create_failed": _entry(
        "Could not create a backup: {error}",
        "バックアップを作成できません: {error}",
        "无法创建备份：{error}",
    ),
    "database.skipped": _entry(
        "Excluded backups that could not be inspected. No files were changed: {names}",
        "検査できないバックアップを復元候補から除外しました。ファイルは変更していません: {names}",
        "已排除无法检查的备份。未修改任何文件：{names}",
    ),
    "database.created_at": _entry("Created", "作成日時", "创建时间"),
    "database.integrity": _entry("Integrity", "整合性", "完整性"),
    "database.schema_column": _entry("Schema", "スキーマ", "架构"),
    "database.ok": _entry("Valid", "正常", "正常"),
    "database.corrupt": _entry(
        "Corrupt or unreadable",
        "破損または読取不能",
        "损坏或无法读取",
    ),
    "database.no_valid": _entry(
        "No valid compatible backup can be restored.",
        "復元可能な正常バックアップがありません。",
        "没有可恢复的有效兼容备份。",
    ),
    "database.restore_select": _entry(
        "Backup to restore",
        "復元するバックアップ",
        "要恢复的备份",
    ),
    "database.restore_warning": _entry(
        "Restoring returns the current database to the selected point. A separate safety backup is created immediately before restore.",
        "復元すると現在のDB内容が選択した時点へ戻ります。復元直前のDBは別の安全バックアップへ自動退避します。",
        "恢复操作会将当前数据库回退到所选时间点。恢复前会自动创建单独的安全备份。",
    ),
    "database.restore_confirm": _entry(
        "I confirm restoration after creating a safety backup of the current database",
        "現在のDBを安全バックアップした上で復元することを確認しました",
        "我确认在为当前数据库创建安全备份后进行恢复",
    ),
    "database.restore": _entry(
        "Restore selected database backup",
        "選択したDBバックアップを復元",
        "恢复所选数据库备份",
    ),
    "database.restore_failed": _entry(
        "Could not restore the database: {error}",
        "DBを復元できません: {error}",
        "无法恢复数据库：{error}",
    ),
    "database.restored": _entry(
        "Restored the database. Pre-restore safety backup: {name}",
        "DBを復元しました。復元前の安全バックアップ: {name}",
        "已恢复数据库。恢复前安全备份：{name}",
    ),
}


def text(language: Language, key: str, **values: object) -> str:
    """Return one translated UI string and interpolate named values."""

    try:
        template = TEXT[key][language]
    except KeyError as exc:
        raise KeyError(f"Unknown UI translation: {key!r} ({language!r})") from exc
    return template.format(**values)
