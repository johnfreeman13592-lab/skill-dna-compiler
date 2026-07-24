# Skill DNA Compiler Beta Quick Start

## What to try in your first 10 minutes

You do not need an API key or real Obsidian notes for your first run. Start with this free,
local-only path:

```text
Extract the ZIP
  → Launch the EXE
  → Choose the bundled Sample Vault
  → Run mock extraction (free)
  → Review the source evidence
  → Export an approved candidate as SKILL.md
```

Mock extraction does not call an external API and cannot incur an API charge. A paid action is
possible only if you later select real notes, review the exact outbound JSON and cost ceiling,
confirm both the content and possible charge, and press the live-extraction button that displays
the estimate.

These terms may help while you explore:

- `Vault`: a folder containing Obsidian Markdown notes
- `Candidate`: a reusable instruction or rule found in selected notes
- `Evidence review`: checking that a candidate is actually supported by the source note
- `Skill DNA`: an approved candidate saved with a version and its evidence
- `SKILL.md`: the final file that Codex can use

日本語版は[Betaクイックスタート](beta-quick-start.ja.md)を参照してください。

## 1. Launch

1. Right-click the ZIP and select **Extract All**.
2. Open the extracted `Skill DNA Compiler` folder.
3. Double-click `Skill DNA Compiler.exe`.
4. Keep the black launcher window open and use the page that appears in your browser.
5. Close the black launcher window when you want to stop the app.

Python is not required. The app binds its page only to `127.0.0.1`, not to an external network
interface.

Because this early Beta is unsigned, Windows SmartScreen may show a warning. Continue only when
the ZIP came from the official Release page and its SHA-256 matches the published `.sha256` file.
Do not disable a security product or add an antivirus exclusion just to run the Beta.

## 2. Free Sample Vault flow

1. Press **Use bundled Sample Vault**.
2. Press **Load Vault**.
3. Select the sample notes and press **Prepare outbound content**.
4. Review the redacted JSON and confirm that you reviewed it.
5. Press **Run mock extraction**. Do not press a live-extraction button.
6. Open a candidate and review whether each instruction is supported by the shown evidence.
7. Approve only the candidate and instruction traces you actually reviewed.
8. Save the approved candidate as Skill DNA.
9. Choose an empty test folder, preview the complete output, and export `SKILL.md`.

The mock path makes no OpenAI API request and costs nothing. For the first run, prioritize
checking whether the evidence supports each instruction instead of trying to perfect every word.
If the evidence is insufficient, leave the instruction pending or reject it.

## 3. Optional OpenAI API key for a later live extraction

Skip this section during the free Sample Vault flow.

1. Open **OpenAI API key settings**.
2. Enter the key in the password field.
3. Press **Save to Windows Credential Manager**.

Saving a key does not make an API request or create a charge. The packaged app stores it in
Windows Credential Manager, not in Skill DNA Compiler's SQLite database, logs, or generated
Skills. Never paste an API key into a note, Issue, chat, or screenshot.

To remove it, select the deletion confirmation and press the delete button. If the credential
backend is unavailable, the app fails closed and does not fall back to plaintext storage.

## 4. Optional real-note flow

Do not use this section in the first-use Sample Vault study.

1. Enter and load your Obsidian Vault path.
2. Explicitly select only notes that may be sent to the external AI.
3. Review the redacted outbound JSON, character count, and cost ceiling.
4. Select both confirmation boxes and press the live-extraction button showing the estimate.
5. Review the source and content, then approve only the candidates you want.

Unselected notes are not sent. Sensitive-data detection is not a guarantee, so never skip the
exact outbound JSON review.

## 5. Data and uninstall

- App files: the extracted ZIP folder
- Local database:
  `%LOCALAPPDATA%\SkillDNACompiler\SkillDNACompiler\skill-dna.db`
- Database backups: the `skill-dna.db.backups` folder beside the database
- API key, if saved: Windows Credential Manager

Deleting only the extracted app folder does not remove the database or a saved API key. For a
complete removal, first delete the API key from the app, preserve any backup you need, and then
remove the extracted app folder and the user-data folder above.

## 6. Known limitations

- Windows 10/11 x64 only
- No code signature or installer
- Early Beta software; keep separate backups of important data
- Closing only the browser tab does not stop the local process
- No automatic telemetry or cloud synchronization

## 7. Troubleshooting

- Browser did not open: keep the black launcher window open and enter its `127.0.0.1` URL in your
  browser.
- A second launch does not open: use the already-running launcher window and browser page.
- No API key: the Sample Vault and mock extraction work without one.
- Concerned about charges: use only **Run mock extraction**. Do not press a live-extraction button.
- Unsure which notes to use: stay with the bundled Sample Vault for the first run.
- SmartScreen or antivirus stopped the app: do not rush to bypass it. Recheck the official source
  and SHA-256, and stop if you remain uncertain.
