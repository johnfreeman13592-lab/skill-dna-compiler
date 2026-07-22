from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from math import ceil

from skill_dna_compiler.extraction.openai_provider import EXTRACTION_INSTRUCTIONS
from skill_dna_compiler.extraction.payloads import ExtractionPayload
from skill_dna_compiler.extraction.schemas import ExtractionResult

PRICING_REVIEWED_ON = "2026-07-18"
TOKENS_PER_MILLION = Decimal(1_000_000)
LONG_CONTEXT_THRESHOLD = 272_000


@dataclass(frozen=True)
class ModelTokenPrice:
    input_per_million_usd: Decimal
    output_per_million_usd: Decimal


@dataclass(frozen=True)
class ExtractionCostEstimate:
    model: str
    input_tokens_low: int
    input_tokens_high: int
    max_output_tokens: int
    input_cost_low_usd: Decimal
    input_cost_high_usd: Decimal
    maximum_total_usd: Decimal
    long_context_pricing_possible: bool


MODEL_PRICES = {
    "gpt-5.6": ModelTokenPrice(Decimal("5"), Decimal("30")),
    "gpt-5.6-sol": ModelTokenPrice(Decimal("5"), Decimal("30")),
    "gpt-5.6-terra": ModelTokenPrice(Decimal("2.5"), Decimal("15")),
    "gpt-5.6-luna": ModelTokenPrice(Decimal("1"), Decimal("6")),
}


class PricingUnavailableError(ValueError):
    """Raised when the configured model has no reviewed local price."""


def estimate_extraction_cost(
    payload: ExtractionPayload,
    *,
    model: str,
    max_output_tokens: int,
) -> ExtractionCostEstimate:
    """Return a conservative local range without transmitting note content."""

    price = MODEL_PRICES.get(model)
    if price is None:
        raise PricingUnavailableError(f"No reviewed pricing is available for model: {model}")
    if max_output_tokens < 1:
        raise ValueError("max_output_tokens must be positive")

    schema_json = json.dumps(
        ExtractionResult.model_json_schema(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    request_text = "\n".join(
        (EXTRACTION_INSTRUCTIONS, payload.model_dump_json(), schema_json)
    )

    # A tokenizer-free range keeps estimation local and dependency-light. The lower
    # bound uses a common four-characters-per-token approximation. Since tokens are
    # composed from one or more UTF-8 bytes, byte length is a conservative upper bound.
    input_tokens_low = max(1, ceil(len(request_text) / 4))
    input_tokens_high = max(input_tokens_low, len(request_text.encode("utf-8")))
    long_context_possible = input_tokens_high > LONG_CONTEXT_THRESHOLD

    low_input_rate = price.input_per_million_usd
    high_input_rate = price.input_per_million_usd * (
        Decimal("2") if long_context_possible else Decimal("1")
    )
    high_output_rate = price.output_per_million_usd * (
        Decimal("1.5") if long_context_possible else Decimal("1")
    )

    input_cost_low = Decimal(input_tokens_low) * low_input_rate / TOKENS_PER_MILLION
    input_cost_high = Decimal(input_tokens_high) * high_input_rate / TOKENS_PER_MILLION
    maximum_total = (
        input_cost_high
        + Decimal(max_output_tokens) * high_output_rate / TOKENS_PER_MILLION
    )
    return ExtractionCostEstimate(
        model=model,
        input_tokens_low=input_tokens_low,
        input_tokens_high=input_tokens_high,
        max_output_tokens=max_output_tokens,
        input_cost_low_usd=input_cost_low,
        input_cost_high_usd=input_cost_high,
        maximum_total_usd=maximum_total,
        long_context_pricing_possible=long_context_possible,
    )


def calculate_actual_token_cost(
    *, model: str, input_tokens: int, output_tokens: int
) -> Decimal:
    price = MODEL_PRICES.get(model)
    if price is None:
        raise PricingUnavailableError(f"No reviewed pricing is available for model: {model}")
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts cannot be negative")
    long_context = input_tokens > LONG_CONTEXT_THRESHOLD
    input_rate = price.input_per_million_usd * (
        Decimal("2") if long_context else Decimal("1")
    )
    output_rate = price.output_per_million_usd * (
        Decimal("1.5") if long_context else Decimal("1")
    )
    return (
        Decimal(input_tokens) * input_rate
        + Decimal(output_tokens) * output_rate
    ) / TOKENS_PER_MILLION
