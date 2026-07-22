# Architecture

## Principles

- Local-first and single-user for the MVP.
- The Obsidian Vault is read-only input.
- Nothing is sent to AI until the user selects notes and confirms the exact payload.
- Human approval is a mandatory state transition before Skill DNA creation.
- OpenAI integration is behind a provider interface.
- File writes are restricted to explicit, validated destinations.

## Data flow

```text
Obsidian Vault (read only)
  -> Vault scanner and document parser
  -> Sensitive-data scan
  -> User payload preview and confirmation
  -> AI provider / structured extraction
  -> Candidate validation and source verification
  -> Human review (edit / approve / reject / hold)
  -> Skill DNA repository
  -> Codex exporter preview
  -> User-confirmed SKILL.md destination
```

## Runtime boundaries

```text
Streamlit UI
  -> application services (future phases)
     -> domain models
     -> storage repositories -> local SQLite
     -> AI provider interface -> OpenAI Responses API
     -> filesystem adapters -> Vault and generated Skill folders
```

FastAPI is intentionally absent from the MVP. The application remains modular so an API adapter can be added later without moving business rules into the UI.

## Storage

The default SQLite path is resolved with `platformdirs` under the current user's application-data directory. It must not be placed inside the source repository, application installation directory, or Obsidian Vault by default.

The initial schema mirrors the product plan:

- `vaults`
- `documents`
- `extraction_runs`
- `skill_candidates`
- `source_references`
- `candidate_merge_sources`
- `schema_migrations`
- `skill_dna`
- `export_records`
- `skill_feedback`

SQLite `PRAGMA user_version` and `schema_migrations` track schema versions v1 through v3. An existing database is copied with SQLite's online backup API before each required migration. A database from a newer application version is rejected without modification.

Validated backups live beside the database in a dedicated `<database-name>.backups` directory. Creation and restore use SQLite's backup API and `PRAGMA quick_check`. Restore accepts only `.sqlite3` files resolved inside that directory, creates a safety backup of the current database first, disposes application connections, restores through a temporary database, and atomically replaces the live file. If reinitialization fails, the safety backup is restored automatically. Backups are not deleted automatically in the MVP.

## Credentials

`OPENAI_API_KEY` is a secret. During development, Pydantic reads it from the ignored `.env.local`.
The packaged Beta forces the production environment, removes an inherited conventional OpenAI
environment variable, and uses a `CredentialStore` boundary backed by Windows Credential Manager.
The UI can save, delete, and report whether a key exists but never redisplays it. Backend failures
are converted to fixed safe messages and never fall back to plaintext, SQLite, or logs.

## Windows Beta runtime

PyInstaller creates an unsigned x64 `onedir` bundle with UPX disabled. A console launcher owns a
Windows named mutex, selects a free loopback port, and starts the bundled Streamlit module without
calling an external Python or Streamlit executable. It binds only to `127.0.0.1`, disables usage
statistics and file watching, and releases the mutex when the console closes. The application DB
continues to live under the OS user-data directory rather than the extracted bundle.

## Cross-platform boundary

Windows is the only implemented and packaged target for the first release. Broader desktop-OS
support is a future goal; Linux distributions and macOS are examples, not fixed next targets or
current compatibility claims.

The domain models, extraction validation, SQLite repositories, Vault/Markdown parsing, Skill DNA
versioning, Codex rendering, and `platformdirs` data-location policy remain platform-neutral. The
replaceable platform layer consists of credential storage, single-instance locking, launcher
behavior, browser opening, packaging, code-signing/notarization, and OS-specific acceptance tests.

The existing `CredentialStore` protocol is the credential port; its current implementation
intentionally accepts only the Windows keyring backend. Future platform implementations must fail
closed unless they can verify an approved OS credential backend. They must never fall back to a
plaintext file. The current launcher uses a Windows named mutex; a future launcher boundary may
provide a platform-specific lock while reusing loopback-only Streamlit arguments and packaged
import smoke tests.

Do not add speculative non-Windows implementations to the Windows MVP. First keep the shared core
executable under platform-independent tests. When a platform is approved, add one credential
adapter, launcher, package recipe, and clean-environment acceptance workflow for that platform
without branching domain or safety behavior.

## Outbound payload boundary

The local note preview may show original content for evidence comparison. The outbound payload is a separate immutable model produced only from explicitly selected notes. Its title, relative path, and full source text are scanned and redacted before deterministic JSON serialization. Input limits apply to that exact serialized JSON, not an estimate. Security findings retained by the preview never include the matched value.

The provider interface accepts only the prepared payload model. It does not receive a Vault path or filesystem adapter, preventing a provider from expanding the selected scope.

## Model policy

The model and reasoning effort are runtime settings. The development baseline is the public Responses API model `gpt-5.6-terra` with `medium` effort because Terra is documented as balancing intelligence and cost. The `gpt-5.6` alias routes to the more capable and more expensive `gpt-5.6-sol`. Model changes require representative structured-extraction tests; model strings alone are not proof of compatibility.

## Validated extraction boundary

The Responses API adapter uses Pydantic Structured Outputs and sets `store=False`. The SDK is configured with a finite timeout and two automatic retries. Raw provider exceptions, request content, and API responses are not written to SQLite.

Every returned source reference must name a document in the exact prepared payload and quote a verbatim substring of its sanitized content. Only after this local validation succeeds does the extraction run become `completed` and its candidates become eligible for human review. Failed runs retain only a safe user-facing error message.

## Local cost gate

Before a live request, the app estimates a local input-token range from the complete payload, extraction instructions, and Structured Outputs schema. It displays the reviewed model price, maximum output-token limit, and a conservative USD ceiling. The estimate sends nothing externally and intentionally favors overestimating rather than hiding possible cost. Unknown or stale-unreviewed model identifiers cannot run live extraction until a price entry is added or refreshed.

## Human review boundary

Prepared payload documents use the stable IDs assigned by the local `documents` index. Validated candidate citations are stored both in the candidate JSON and as relational `source_references`; SQLite foreign-key enforcement rejects citations to unknown documents.

The review UI reloads candidates from SQLite. A reviewer may edit candidate guidance but not its validated source references or extraction confidence. Any edit resets the candidate to `pending`. Approve, reject, and hold actions update only `skill_candidates.status`; they do not create `skill_dna` or export records. Skill generation remains a separate Phase 5 boundary.

Duplicate detection is deterministic and local. It compares normalized character pairs across names, descriptions, reusable guidance, and source-document overlap, which avoids relying on English-only tokenization. A score is only a review suggestion and never changes state automatically. An explicit manual merge preserves the primary candidate's descriptive fields, unions reusable guidance and validated citations, uses the lower confidence, creates a new `pending` candidate, and moves both originals to `on_hold`. `candidate_merge_sources` preserves the two source candidate IDs; no original candidate is deleted.

## Skill DNA boundary

Candidate approval changes only `skill_candidates.status`. A separate explicit action may convert an `approved` candidate into Skill DNA; the service and repository both reject every other status. The UI shows the source candidate and proposed Skill DNA JSON side by side before saving.

The current snapshot is stored in `skill_dna.skill_data`. Every explicit create or update also appends an immutable JSON snapshot to `skill_dna_versions`; initial version is `0.1.0` and later approved updates increment the patch version. Name, description, triggers, exclusions, principles, workflow, constraints, and validated sources are preserved. This boundary creates no files; `SKILL.md` output remains a separate confirmed export phase.

## Codex export boundary

The renderer deterministically emits UTF-8 Markdown with only `name` and `description` in YAML frontmatter. Skill names are safe hyphen-case strings no longer than 64 characters. The body retains the approved principles, ordered workflow, constraints, exclusions, and sanitized validated source references.

The user supplies an existing parent directory. Preview resolves the parent and proposed `<slug>/SKILL.md`, rejects symbolic-link Skill targets and paths outside the approved root, and performs no write. Export requires a separate content-and-path confirmation; an existing file requires an additional overwrite confirmation. Writes use a same-directory temporary file, flush and `fsync`, then atomically replace the target. Each successful write appends a local `export_records` row.

## Local feedback boundary

The user may append a structured usage result for a saved Skill DNA version: not used,
used once, or reused; and not evaluated, helpful, partly helpful, or not helpful. Optional
good-point and improvement text is limited to 2,000 characters per field. The UI warns the
user not to enter API keys, note bodies, passwords, or personal data. Feedback is stored only
in local SQLite, is never sent automatically, and never changes or approves a Skill.

## Product scope and future adapter boundaries

The first complete public-product candidate intentionally has one narrow path:

```text
explicitly selected Obsidian / Markdown notes -> human-approved Codex SKILL.md
```

Additional note applications, text and structured-data formats, document imports, and non-Codex
export targets are out of the initial scope. Notion and JSON are examples, not fixed next targets or
special cases in the architecture. Domain and safety rules must nevertheless remain independent of
Streamlit, Markdown path scanning, OpenAI, and the Codex renderer so later adapters do not require a
rewrite.

A future input adapter may produce the same selected `SourceDocument` boundary with an origin kind,
stable locator, title, sanitized content, content hash, and optional line map. It must never gain
authority to enumerate or transmit an entire source account. A future output adapter may render a
saved, approved Skill DNA for one named target while reusing the existing preview, path-validation,
overwrite-confirmation, and export-record boundaries. The MVP implements only the existing
Obsidian/Markdown reader and Codex exporter; adapter abstractions should be introduced only when a
second real input or output target is selected from actual user demand and approved.

## DNA Trace differentiation hypothesis

The proposed public differentiator is not generic AI Skill generation. It is a local, enforceable
trace gate: every normative instruction that will reach the final Skill can be mapped to exact,
validated evidence from explicitly selected notes, reviewed by a person, and blocked from Skill
DNA creation or export when the trace is missing or unapproved.

The saved `v0.1.0-beta.2` artifact stores validated source references at candidate level and must
not be described as enforcing instruction-level links. The current development branch implements
the minimal gate in existing candidate/Skill JSON snapshots without a database migration. Exact
source-reference fingerprints bind a trace to document ID, quote, and reason without depending on
array order. Instruction keys plus policy-versioned hashes invalidate approval after edits or
reordering. Candidate approval, Skill DNA persistence, and export all fail closed when any final
instruction is missing strict human-approved evidence. Real-note dogfood is still required before
this is treated as a validated public differentiator.

The approved privacy default is to keep complete instruction-level trace evidence inside the local
application. Codex `SKILL.md` output contains the approved instructions without full note evidence
unless the user explicitly enables a separately previewed evidence-inclusion option. This option
must never bypass redaction, path confirmation, or export preview.
