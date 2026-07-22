# Privacy and API transmission

## Current behavior

Skill DNA Compiler is local-first. Vault settings, document indexes, selected notes, candidate data, and generated skills stay on the user's PC. The application does not send telemetry to the operator.

Payload preparation and cost estimation do not call the OpenAI API. The app displays the exact outbound JSON and a conservative local USD cost ceiling. A live call is possible only after the user separately confirms both the sanitized content and the possibility of API charges, then presses a button explicitly labeled as a charged OpenAI extraction.

The live adapter uses the Responses API with `store=False`. Local SQLite does not retain the outbound note payload, raw API response, raw exception text, or API key; it stores only execution metadata, safe error messages, and candidates that pass exact source-quote validation.

## Local database backups

Database backups stay on the user's PC beside the application database. They contain the same local candidate, citation, index, and history data as SQLite, but do not add the API key, raw outbound note payload, or raw API response. Backup creation and restore do not send telemetry or make an OpenAI request. Users should protect or delete backup files with the same care as the main local database.

Restore requires an explicit UI confirmation. The app validates the selected backup, restricts it to the application backup directory, and creates a safety backup of the current database before replacement.

## Before any future API call

1. The user explicitly selects one or more notes.
2. The app scans the selected source text, title, and relative path locally.
3. Detected values are replaced in the outbound JSON.
4. The app shows finding locations, exact serialized JSON, document count, character count, and redaction count.
5. The user must confirm the preview before extraction can run.

Unselected notes are not included in the payload.

## Detected patterns

The initial scanner covers common OpenAI and GitHub tokens, AWS access keys, JWTs, private-key blocks, assigned API keys/passwords/secrets, email addresses, formatted phone numbers, and absolute Windows drive or UNC paths that can expose local usernames or private server names. Findings store only type, severity, line, and replacement marker; they do not store the matched secret.

Detection is best-effort. It can produce false positives and cannot guarantee that every possible secret or piece of personal data will be recognized. The exact outbound preview remains mandatory even when the scanner reports no findings.

## Local source preview versus outbound preview

The ordinary note preview shows the original local note so the user can compare evidence. The separate outbound JSON preview contains the sanitized version. The UI labels these surfaces separately to avoid confusing local display with external transmission.

## Credentials

During development, `OPENAI_API_KEY` is read from the ignored `.env.local`. In the packaged
Windows Beta, the key is stored in Windows Credential Manager through `keyring`; the packaged
launcher removes any inherited `OPENAI_API_KEY` and does not read `.env.local`. The UI may report
whether a key exists but never displays it. If the credential backend fails, the app fails closed
and does not fall back to plaintext. The key must never be logged, stored in SQLite, copied into a
generated Skill, or placed in process arguments.

## Cost

No API charge occurs during payload preparation, backup operations, or mock extraction. When live extraction is used, the user uses their own OpenAI API account and pays its API charges. The model, input limit, and estimated usage are visible before sending.
