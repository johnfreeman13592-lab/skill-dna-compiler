from decimal import Decimal

import pytest

from skill_dna_compiler.extraction.costs import (
    PricingUnavailableError,
    calculate_actual_token_cost,
    estimate_extraction_cost,
)
from skill_dna_compiler.extraction.payloads import ExtractionPayload, PayloadDocument


def _payload(content: str = "再利用できる開発ルール") -> ExtractionPayload:
    return ExtractionPayload(
        documents=[
            PayloadDocument(
                document_id="doc_1",
                title="Rule",
                path="Rule.md",
                content_hash="a" * 64,
                content=content,
            )
        ],
        redaction_count=0,
    )


def test_estimate_extraction_cost_returns_conservative_local_range():
    estimate = estimate_extraction_cost(
        _payload(), model="gpt-5.6-terra", max_output_tokens=6_000
    )

    assert estimate.input_tokens_low > 0
    assert estimate.input_tokens_high >= estimate.input_tokens_low
    assert estimate.input_cost_high_usd >= estimate.input_cost_low_usd
    assert estimate.maximum_total_usd > estimate.input_cost_high_usd
    assert estimate.long_context_pricing_possible is False


def test_terra_cost_is_lower_than_sol_alias_for_same_payload():
    terra = estimate_extraction_cost(
        _payload(), model="gpt-5.6-terra", max_output_tokens=6_000
    )
    sol = estimate_extraction_cost(
        _payload(), model="gpt-5.6", max_output_tokens=6_000
    )

    assert terra.maximum_total_usd < sol.maximum_total_usd
    assert terra.maximum_total_usd == sol.maximum_total_usd / Decimal("2")


def test_unknown_model_blocks_cost_estimate():
    with pytest.raises(PricingUnavailableError, match="No reviewed pricing"):
        estimate_extraction_cost(_payload(), model="unknown", max_output_tokens=6_000)


def test_long_context_ceiling_applies_documented_price_multipliers():
    estimate = estimate_extraction_cost(
        _payload("日" * 100_000),
        model="gpt-5.6-terra",
        max_output_tokens=6_000,
    )

    assert estimate.input_tokens_high > 272_000
    assert estimate.long_context_pricing_possible is True
    regular_input_ceiling = (
        Decimal(estimate.input_tokens_high) * Decimal("2.5") / Decimal(1_000_000)
    )
    assert estimate.input_cost_high_usd == regular_input_ceiling * Decimal("2")


def test_max_output_tokens_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        estimate_extraction_cost(
            _payload(), model="gpt-5.6-terra", max_output_tokens=0
        )


def test_actual_token_cost_uses_reviewed_terra_rates():
    cost = calculate_actual_token_cost(
        model="gpt-5.6-terra", input_tokens=1_000, output_tokens=2_000
    )

    assert cost == Decimal("0.0325")


def test_actual_token_cost_rejects_negative_counts():
    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_actual_token_cost(
            model="gpt-5.6-terra", input_tokens=-1, output_tokens=0
        )
