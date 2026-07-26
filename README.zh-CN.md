<h1 align="center">🧬 Skill DNA Compiler</h1>

<p align="center"><strong>将笔记转化为有来源依据、可供 AI 真正复用的 Skill。</strong></p>

<p align="center">
  一款本地优先的 Windows 应用，可将用户明确选择的 Obsidian 和 Markdown 笔记
  转化为经过人工审核的 Codex Skill。
</p>

<p align="center">
  <a href="https://github.com/johnfreeman13592-lab/skill-dna-compiler/releases/tag/v0.1.0-beta.6"><img alt="版本" src="https://img.shields.io/github/v/release/johnfreeman13592-lab/skill-dna-compiler?include_prereleases&label=beta&color=7c3aed"></a>
  <img alt="平台" src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078d4">
  <a href="LICENSE"><img alt="许可证" src="https://img.shields.io/badge/license-MPL--2.0-2563eb"></a>
  <img alt="本地优先" src="https://img.shields.io/badge/data-local--first-059669">
  <img alt="无遥测" src="https://img.shields.io/badge/telemetry-none-475569">
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.ja.md">日本語</a> ·
  <strong>简体中文</strong>
</p>

> [!NOTE]
> 👋 **感谢你发现 Skill DNA Compiler！**
> 这个项目才刚刚起步。欢迎试用 Beta 版，并告诉我们哪些地方对你有帮助、
> 哪些地方不够清楚。希望能和你一起塑造 Skill DNA Compiler 的未来。

---

## 下载 Windows 版本

> [!IMPORTANT]
> **[下载 Skill DNA Compiler v0.1.0-beta.6 Windows 版](https://github.com/johnfreeman13592-lab/skill-dna-compiler/releases/download/v0.1.0-beta.6/skill-dna-compiler-0.1.0-beta.6-windows-x64.zip)**

1. 右键单击下载的 ZIP 文件，然后选择 **全部解压缩（Extract All）**。
2. 打开解压后的文件夹。请勿直接从 ZIP 文件内部运行应用。
3. 双击 `Skill DNA Compiler.exe`。

建议先使用内置的 `Sample Vault` 和**模拟提取（mock extraction）**。此流程不需要 API Key，
不会向外部 AI 发送任何内容，也不会产生费用。SmartScreen 提示和完整操作顺序请参阅
[Beta 快速入门](docs/beta-quick-start.md)。

## 它带来了什么变化

| 使用前 | 使用 Skill DNA Compiler 后 |
|---|---|
| 有价值的经验分散在多篇笔记中。 | 可以从选定笔记中生成可复用的 Skill 候选。 |
| AI 补充了原文中没有的内容时，很难察觉。 | 可以将最终指令与精确的来源证据逐项核对。 |
| 生成后的 Skill 难以信任和维护。 | 由人工审核后，再保存版本、证据并导出。 |
| 在其他项目中可能需要重复解释同一经验。 | 可以通过已批准的 Codex `SKILL.md` 复用流程。 |

## Skill DNA Compiler 的特点

### 🔬 证据优先于 AI 的自信

DNA Trace 会把最终指令连接到用户所选笔记中的精确证据。缺乏直接证据或未经人工批准的指令，
无法通过严格的编译和导出门禁。

### 🧑 必须经过人工批准

提取、候选批准、创建 Skill DNA 和文件导出是相互独立的操作。应用不会自动批准候选，
也不会在未经确认的情况下覆盖现有 `SKILL.md`。

### 🔒 默认本地优先

Vault 始终以只读方式使用。笔记、候选、Skill DNA、版本历史、备份和生成文件均保存在用户电脑上。
当前版本不需要账户、运营方服务器、订阅、许可证激活，也不会自动发送遥测数据。

## 工作流程

```text
1. 选择笔记
       ↓
2. 检查经过脱敏的准确 JSON 和可能的 API 费用上限
       ↓
3. 提取带有来源依据的 Skill 候选
       ↓
4. 审核证据，只批准可信内容
       ↓
5. 保存带版本的 Skill DNA，并导出 Codex SKILL.md
```

真实的 OpenAI 提取流程使用用户自己的 API Key，因此可能产生 API 费用。在任何付费请求之前，
应用会分别要求确认准确的发送 JSON 和保守估算的费用上限。未选择的笔记不会被发送。

## 公开 Beta 状态

当前版本是仅支持 Windows 的公开 Beta。现已实现从 Obsidian／Markdown 到 Codex Skill 的完整流程、
指令级证据审核、本地数据保护、Windows Credential Manager，以及内置 Python 的便携式 ZIP。

项目已使用三组真实笔记完成提取，并对四个经过人工审核的 Skill 进行了虚构场景前向测试。
公开的 Windows 候选包通过了 checksum、ZIP 安全、packaged import、HTTP health，以及目标进程
仅监听 `127.0.0.1` 的检查。这些是 Beta 阶段的技术证据，并不代表已经证明了广泛的用户价值，
也不保证兼容所有电脑。

准确证据和已知限制请参阅
[公开 Beta 就绪审计](docs/public-beta-readiness-audit-2026-07-22.md)。

## 当前支持范围

| 项目 | 当前支持 | 根据真实需求逐步增加 |
|---|---|---|
| 输入 | 用户明确选择的 Obsidian／Markdown 笔记 | 其他笔记应用、文本格式、对话、操作和 Git 历史 |
| 输出 | Codex 兼容的 `SKILL.md` | 其他 AI Agent 和面向人的格式 |
| 操作系统 | Windows 10/11 x64 | 其他桌面操作系统 |
| 存储 | 本地 SQLite、本地文件、经过验证的备份 | 当前阶段不计划构建大型云平台 |

首个产品版本有意保持较小范围。同时，UI、领域逻辑、存储、安全、操作系统相关行为和 OpenAI
集成彼此分离，以便未来增加适配器时无需重写安全规则。

## 安全与隐私

- 只有用户明确选择的笔记才可以进入外发 payload。
- 标题、相对路径和正文会在本地扫描并脱敏。
- “未检测到问题”不等于绝对安全，发送前仍需人工检查准确 JSON。
- OpenAI 请求使用 Structured Outputs，并设置 `store=False`。
- 打包版只会将 API Key 保存到 Windows Credential Manager，并且不会再次显示。
- API Key 和笔记正文不会写入 SQLite 或常规日志。
- 导出范围限制在用户批准的现有目标目录内，并使用原子替换。
- 数据库备份与恢复会执行 SQLite 完整性检查。

完整边界请参阅[隐私与 API 发送说明](docs/privacy.md)。

## 开发

<details>
<summary><strong>本地开发命令</strong></summary>

需要 Windows 10/11 和 Python 3.11 或更高版本。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,package]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m streamlit run app.py
```

开发用秘密信息应保存在 Git 忽略的 `.env.local` 中。请勿将 API Key 写入源代码、
GitHub Issue、日志或生成的 Skill。

</details>

<details>
<summary><strong>构建并验证 Windows 包</strong></summary>

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\build_windows_beta.ps1

.\.venv\Scripts\python.exe .\tools\verify_windows_candidate.py `
  .\dist\skill-dna-compiler-0.1.0-beta.6-windows-x64.zip `
  --report-dir .\build\verification\beta.6
```

验证工具会检查 checksum、压缩包限制和安全路径、必需与禁止文件、依赖来源和许可证、
packaged import、HTTP health、进程所有权以及仅限 loopback 的监听地址。退出码：
通过为 `0`，验证失败为 `1`，验证工具本身无法运行为 `2`。

</details>

## 文档

- [Beta 快速入门](docs/beta-quick-start.md)
- [隐私与 API 发送说明](docs/privacy.md)
- [架构与安全边界](docs/architecture.md)
- [实施计划](docs/implementation-plan.md)
- [Beta 测试清单](docs/beta-test-checklist.md)

## 反馈与贡献

- 问题和建议请使用 [Discussions](https://github.com/johnfreeman13592-lab/skill-dna-compiler/discussions)
- 可复现的缺陷请使用 [Issues](https://github.com/johnfreeman13592-lab/skill-dna-compiler/issues)
- 安全问题请使用 GitHub 私密漏洞报告
- 提交修改前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)

## 许可证

Skill DNA Compiler 使用 [Mozilla Public License 2.0](LICENSE) 发布。第三方许可证和通知请参阅
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
