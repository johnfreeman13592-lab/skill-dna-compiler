from sqlalchemy import select

from skill_dna_compiler.storage.database import Database, DocumentRecord
from skill_dna_compiler.storage.repositories import VaultRepository
from skill_dna_compiler.vault import scan_vault


def test_save_scan_updates_documents_and_marks_missing(tmp_path):
    vault = tmp_path / "Vault"
    vault.mkdir()
    first = vault / "First.md"
    second = vault / "Second.md"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    database = Database(tmp_path / "app.db")
    database.initialize()
    assert database.session_factory is not None
    repository = VaultRepository(database.session_factory)

    vault_id = repository.save_scan(vault, (".obsidian",), scan_vault(vault))
    second.unlink()
    first.write_text("changed", encoding="utf-8")
    repository.save_scan(vault, (".obsidian",), scan_vault(vault))

    assert repository.latest() is not None
    assert repository.latest().id == vault_id
    with database.session_factory() as session:
        documents = {
            item.relative_path: item
            for item in session.scalars(select(DocumentRecord)).all()
        }
    assert documents["First.md"].status == "active"
    assert documents["Second.md"].status == "missing"
    assert repository.document_ids_for_paths(vault_id, ["First.md"]) == {
        "First.md": documents["First.md"].id
    }


def test_document_ids_reject_missing_or_inactive_notes(tmp_path):
    vault = tmp_path / "Vault"
    vault.mkdir()
    note = vault / "First.md"
    note.write_text("first", encoding="utf-8")
    database = Database(tmp_path / "app.db")
    database.initialize()
    assert database.session_factory is not None
    repository = VaultRepository(database.session_factory)
    vault_id = repository.save_scan(vault, (), scan_vault(vault))
    note.unlink()
    repository.save_scan(vault, (), scan_vault(vault))

    try:
        repository.document_ids_for_paths(vault_id, ["First.md"])
    except ValueError as exc:
        assert "not active" in str(exc)
    else:
        raise AssertionError("Expected an inactive document to be rejected")
