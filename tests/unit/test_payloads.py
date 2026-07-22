from pathlib import Path

import pytest

from skill_dna_compiler.extraction import PayloadLimitError, prepare_extraction_payload
from skill_dna_compiler.vault import parse_markdown_file, scan_vault


def _parse_notes(vault: Path, contents: dict[str, str]):
    vault.mkdir()
    for name, content in contents.items():
        (vault / name).write_text(content, encoding="utf-8")
    return [parse_markdown_file(item) for item in scan_vault(vault)]


def test_prepare_payload_contains_only_selected_notes_and_redacts(tmp_path):
    secret = "sk-proj-exampleSecretValue1234567890"
    notes = _parse_notes(
        tmp_path / "Vault",
        {
            "One.md": f"# Rule\nUse existing files.\nkey={secret}",
            "Two.md": "# Other\nNot selected",
        },
    )

    prepared = prepare_extraction_payload([notes[0]], max_characters=10_000)

    assert len(prepared.payload.documents) == 1
    assert prepared.payload.documents[0].path == "One.md"
    assert "Two.md" not in prepared.serialized_json
    assert secret not in prepared.serialized_json
    assert "[REDACTED:openai_api_key]" in prepared.serialized_json
    assert prepared.character_count == len(prepared.serialized_json)
    assert prepared.payload.redaction_count == 1


def test_prepare_payload_rejects_exact_serialized_size_over_limit(tmp_path):
    notes = _parse_notes(tmp_path / "Vault", {"Long.md": "x" * 200})

    with pytest.raises(PayloadLimitError, match="Prepared payload"):
        prepare_extraction_payload(notes, max_characters=100)


def test_prepare_payload_rejects_duplicate_selection(tmp_path):
    notes = _parse_notes(tmp_path / "Vault", {"One.md": "content"})

    with pytest.raises(ValueError, match="Duplicate"):
        prepare_extraction_payload([notes[0], notes[0]], max_characters=10_000)


def test_prepare_payload_requires_selection():
    with pytest.raises(ValueError, match="At least one"):
        prepare_extraction_payload([], max_characters=10_000)


def test_prepare_payload_redacts_sensitive_filename_metadata(tmp_path):
    email = "person@example.com"
    notes = _parse_notes(tmp_path / "Vault", {f"Contact {email}.md": "ordinary body"})

    prepared = prepare_extraction_payload(notes, max_characters=10_000)

    assert email not in prepared.serialized_json
    assert "[REDACTED:email_address]" in prepared.payload.documents[0].path
    assert {finding.location for finding in prepared.findings} == {"path", "title"}


def test_prepare_payload_uses_indexed_document_ids(tmp_path):
    notes = _parse_notes(tmp_path / "Vault", {"One.md": "content"})

    prepared = prepare_extraction_payload(
        notes,
        max_characters=10_000,
        document_ids_by_path={"One.md": "doc_indexed"},
    )

    assert prepared.payload.documents[0].document_id == "doc_indexed"


def test_prepare_payload_rejects_note_missing_from_index(tmp_path):
    notes = _parse_notes(tmp_path / "Vault", {"One.md": "content"})

    with pytest.raises(ValueError, match="not indexed"):
        prepare_extraction_payload(
            notes,
            max_characters=10_000,
            document_ids_by_path={},
        )


def test_prepare_payload_removes_structured_credentials_from_exact_json(tmp_path):
    secrets = (
        "json-secret-value-123",
        "yaml-secret-value-123",
        "bearer-token-value-123456",
    )
    notes = _parse_notes(
        tmp_path / "Vault",
        {
            "Secrets.md": (
                '# Credentials\n{"client_secret": "json-secret-value-123"}\n'
                "client_secret: 'yaml-secret-value-123'\n"
                "Authorization: Bearer bearer-token-value-123456\n"
            )
        },
    )

    prepared = prepare_extraction_payload(notes, max_characters=10_000)

    assert all(secret not in prepared.serialized_json for secret in secrets)
    assert prepared.payload.redaction_count == 3
