from types import SimpleNamespace

import pytest

from skill_dna_compiler.extraction.openai_provider import OpenAIExtractionProvider
from skill_dna_compiler.extraction.payloads import ExtractionPayload, PayloadDocument
from skill_dna_compiler.extraction.provider import ExtractionProviderError
from skill_dna_compiler.extraction.schemas import ExtractionResult


class FakeResponses:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return self.response


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


def test_openai_provider_uses_structured_stateless_request_without_network():
    expected = ExtractionResult(candidates=[])
    item = SimpleNamespace(type="output_text", parsed=expected)
    response = SimpleNamespace(
        output=[SimpleNamespace(type="message", content=[item])],
        usage=SimpleNamespace(input_tokens=120, output_tokens=45, total_tokens=165),
    )
    responses = FakeResponses(response)
    provider = OpenAIExtractionProvider(
        model="test-model",
        reasoning_effort="medium",
        client=SimpleNamespace(responses=responses),
    )

    result = provider.extract(_payload())

    assert result == expected
    assert responses.kwargs["text_format"] is ExtractionResult
    assert responses.kwargs["store"] is False
    assert responses.kwargs["reasoning"] == {"effort": "medium"}
    assert "Reusable rule" in responses.kwargs["input"]
    assert provider.last_usage is not None
    assert provider.last_usage.input_tokens == 120
    assert provider.last_usage.output_tokens == 45
    assert provider.last_usage.total_tokens == 165


def test_openai_provider_maps_refusal_to_safe_non_retryable_error():
    refusal = SimpleNamespace(type="refusal", refusal="raw provider refusal", parsed=None)
    response = SimpleNamespace(
        output=[SimpleNamespace(type="message", content=[refusal])]
    )
    provider = OpenAIExtractionProvider(
        model="test-model",
        reasoning_effort="medium",
        client=SimpleNamespace(responses=FakeResponses(response)),
    )

    with pytest.raises(ExtractionProviderError) as raised:
        provider.extract(_payload())

    assert raised.value.retryable is False
    assert "raw provider refusal" not in str(raised.value)


def test_openai_provider_rejects_missing_parsed_output():
    response = SimpleNamespace(
        output=[SimpleNamespace(type="message", content=[])]
    )
    provider = OpenAIExtractionProvider(
        model="test-model",
        reasoning_effort="medium",
        client=SimpleNamespace(responses=FakeResponses(response)),
    )

    with pytest.raises(ExtractionProviderError) as raised:
        provider.extract(_payload())

    assert raised.value.retryable is True


def test_openai_provider_blocks_unredacted_high_risk_data_before_network():
    payload = _payload().model_copy(
        update={
            "documents": [
                _payload().documents[0].model_copy(
                    update={"content": '{"client_secret": "json-secret-value-123"}'}
                )
            ]
        }
    )
    responses = FakeResponses(SimpleNamespace(output=[]))
    provider = OpenAIExtractionProvider(
        model="test-model",
        reasoning_effort="medium",
        client=SimpleNamespace(responses=responses),
    )

    with pytest.raises(ExtractionProviderError) as raised:
        provider.extract(payload)

    assert raised.value.retryable is False
    assert "json-secret-value-123" not in str(raised.value)
    assert responses.kwargs is None
