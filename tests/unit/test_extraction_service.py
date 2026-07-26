import pytest
from sqlalchemy import select

from skill_dna_compiler.extraction.mock_provider import StaticMockExtractionProvider
from skill_dna_compiler.extraction.payloads import ExtractionPayload, PayloadDocument
from skill_dna_compiler.extraction.provider import ExtractionProviderError
from skill_dna_compiler.extraction.schemas import ExtractionResult
from skill_dna_compiler.extraction.service import ExtractionService
from skill_dna_compiler.storage.database import Database, ExtractionRunRecord
from skill_dna_compiler.storage.repositories import ExtractionRepository


def _setup(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    assert database.session_factory is not None
    service = ExtractionService(ExtractionRepository(database.session_factory))
    return service, database.session_factory


def _payload():
    return ExtractionPayload(
        documents=[
            PayloadDocument(
                document_id="doc_1",
                title="Note",
                path="Note.md",
                content_hash="a" * 64,
                content="Reusable rule",
            )
        ],
        redaction_count=0,
    )


def test_service_records_success(tmp_path):
    service, sessions = _setup(tmp_path)

    result = service.run(
        payload=_payload(),
        provider=StaticMockExtractionProvider(ExtractionResult(candidates=[])),
        model="mock",
        prompt_version="test-v1",
    )

    assert result.candidates == []
    with sessions() as session:
        assert session.scalars(select(ExtractionRunRecord)).one().status == "completed"


def test_service_can_return_exact_run_identity_without_changing_run_api(tmp_path):
    service, sessions = _setup(tmp_path)

    run_id, result = service.run_with_id(
        payload=_payload(),
        provider=StaticMockExtractionProvider(ExtractionResult(candidates=[])),
        model="mock",
        prompt_version="test-v1",
    )

    assert result.candidates == []
    with sessions() as session:
        persisted = session.get(ExtractionRunRecord, run_id)
        assert persisted is not None
        assert persisted.status == "completed"


def test_service_records_safe_failure_and_allows_retry(tmp_path):
    class FailingProvider:
        def extract(self, payload):
            raise RuntimeError("secret raw failure")

    service, sessions = _setup(tmp_path)

    with pytest.raises(ExtractionProviderError) as raised:
        service.run(
            payload=_payload(),
            provider=FailingProvider(),
            model="mock",
            prompt_version="test-v1",
        )

    assert raised.value.retryable is True
    with sessions() as session:
        run = session.scalars(select(ExtractionRunRecord)).one()
        assert run.status == "failed"
        assert "secret raw failure" not in (run.error_message or "")
