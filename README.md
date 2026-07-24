<h1 align="center">🧬 Skill DNA Compiler</h1>

<p align="center"><strong>Turn your notes into source-backed Skills your AI can actually reuse.</strong></p>

<p align="center">
  A local-first Windows app that transforms selected Obsidian and Markdown notes into
  human-approved Codex Skills.
</p>

<p align="center">
  <a href="https://github.com/johnfreeman13592-lab/skill-dna-compiler/releases/tag/v0.1.0-beta.3"><img alt="Release" src="https://img.shields.io/github/v/release/johnfreeman13592-lab/skill-dna-compiler?include_prereleases&label=beta&color=7c3aed"></a>
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078d4">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MPL--2.0-2563eb"></a>
  <img alt="Local first" src="https://img.shields.io/badge/data-local--first-059669">
  <img alt="Telemetry" src="https://img.shields.io/badge/telemetry-none-475569">
</p>

<p align="center">
  <strong>English</strong> · <a href="README.ja.md">日本語</a> ·
  <a href="README.zh-CN.md">简体中文</a>
</p>

> [!NOTE]
> 👋 **Thanks for visiting Skill DNA Compiler!** This project is still in its early stages.
> Try the Beta, share what worked or felt confusing, and help us shape what it becomes next.

---

## Download for Windows

> [!IMPORTANT]
> **[Download Skill DNA Compiler v0.1.0-beta.3 for Windows](https://github.com/johnfreeman13592-lab/skill-dna-compiler/releases/download/v0.1.0-beta.3/skill-dna-compiler-0.1.0-beta.3-windows-x64.zip)**

1. Right-click the downloaded ZIP and select **Extract All**.
2. Open the extracted folder. Do not run the app from inside the ZIP.
3. Double-click `Skill DNA Compiler.exe`.

Start with the bundled `Sample Vault` and **mock extraction**. This path needs no API key, sends
nothing to an external AI, and costs nothing. See the
[Beta quick start](docs/beta-quick-start.md) for SmartScreen help and the complete screen flow.

## What changes

| Before | With Skill DNA Compiler |
|---|---|
| Useful lessons stay scattered across notes. | Selected notes become reusable Skill candidates. |
| AI may fill missing details without showing where they came from. | Instructions are reviewed against exact source evidence. |
| A generated Skill can be difficult to trust or maintain. | Humans approve the candidate, preserve its version and evidence, then export it. |
| The same lesson may need to be explained again in another project. | An approved Codex `SKILL.md` can carry the procedure into later work. |

## What makes it different

### 🔬 Evidence before confidence

DNA Trace links final instructions to exact evidence from notes you selected. Unsupported or
unapproved instructions cannot pass the strict compile and export gates.

### 🧑 Human approval is mandatory

Extraction, candidate approval, Skill DNA creation, and file export are separate actions. The app
never silently approves a candidate or overwrites an existing `SKILL.md`.

### 🔒 Local-first by default

Your Vault stays read-only. Notes, candidates, Skill DNA, history, backups, and generated files stay
on your PC. There is no account, operator server, subscription, license activation, or automatic
telemetry.

## How it works

```text
1. Select notes
       ↓
2. Review the exact sanitized JSON and possible API cost
       ↓
3. Extract source-backed Skill candidates
       ↓
4. Review evidence and approve only what is trustworthy
       ↓
5. Save versioned Skill DNA and export Codex SKILL.md
```

The live OpenAI path uses your own API key and may incur API charges. Before any paid request, the
app separately asks you to confirm the exact outbound JSON and a conservative cost ceiling.
Unselected notes are not included.

## Public Beta status

The current release is a Windows-only public Beta. The complete
Obsidian/Markdown-to-Codex flow, instruction-level evidence review, local data protection, Windows
Credential Manager integration, and a Python-bundled portable ZIP are implemented.

Three real-note trial groups produced four human-reviewed Skills that were forward-tested on
fictional cases. The published Windows candidate passed checksum, ZIP safety, packaged imports,
HTTP health, and owned-process `127.0.0.1`-only listener checks. This is technical Beta evidence,
not proof of broad user value or compatibility with every PC.

See the [public Beta readiness audit](docs/public-beta-readiness-audit-2026-07-22.md) for the exact
evidence and limitations.

## Current scope

| Area | Supported now | Later, based on real demand |
|---|---|---|
| Input | Explicitly selected Obsidian / Markdown notes | Other note apps, text formats, chats, activity and Git history |
| Output | Codex-compatible `SKILL.md` | Other agents and human-readable formats |
| OS | Windows 10/11 x64 | Additional desktop operating systems |
| Storage | Local SQLite, local files, validated backups | No large cloud platform planned for the current stage |

The first product stays intentionally narrow. Internal boundaries keep UI, domain logic, storage,
security, platform-specific behavior, and OpenAI integration separate so future adapters do not
require rewriting the safety rules.

## Safety and privacy

- Only explicitly selected notes can enter an outbound payload.
- Titles, relative paths, and content are scanned and redacted locally.
- A zero-finding scan is not treated as a guarantee; the exact JSON still requires human review.
- OpenAI requests use Structured Outputs and `store=False`.
- The packaged app stores the API key only in Windows Credential Manager and never redisplays it.
- API keys and note bodies are not written to SQLite or normal logs.
- Export is restricted to a user-approved existing destination and uses atomic replacement.
- Database backup and restore include SQLite integrity checks.

Read [Privacy and API transmission](docs/privacy.md) for the full boundary.

## Development

<details>
<summary><strong>Local development commands</strong></summary>

Requirements: Windows 10/11 and Python 3.11 or later.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,package]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Development secrets belong in ignored `.env.local`. Never put an API key in source code, GitHub
Issues, logs, or generated Skills.

</details>

<details>
<summary><strong>Build and verify the Windows package</strong></summary>

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\build_windows_beta.ps1

.\.venv\Scripts\python.exe .\tools\verify_windows_candidate.py `
  .\dist\skill-dna-compiler-0.1.0-beta.3-windows-x64.zip `
  --report-dir .\build\verification\beta.3
```

The verifier checks the checksum, archive limits and safe paths, required and forbidden files,
dependency provenance and licenses, packaged imports, HTTP health, process ownership, and
loopback-only listeners. Exit codes are `0` for pass, `1` for a validation failure, and `2` when
the verifier itself cannot run.

</details>

## Documentation

- [Beta quick start](docs/beta-quick-start.md)
- [Privacy and API transmission](docs/privacy.md)
- [Architecture and safety boundaries](docs/architecture.md)
- [Implementation plan](docs/implementation-plan.md)
- [Beta test checklist](docs/beta-test-checklist.md)

## Feedback and contributions

- Use [Discussions](https://github.com/johnfreeman13592-lab/skill-dna-compiler/discussions) for
  questions and ideas.
- Use [Issues](https://github.com/johnfreeman13592-lab/skill-dna-compiler/issues) for reproducible
  bugs.
- Use GitHub private vulnerability reporting for security issues.
- Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a change.

## License

Skill DNA Compiler is available under the [Mozilla Public License 2.0](LICENSE). Third-party
licenses and notices are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
