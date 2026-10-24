"""Cost estimates per request (USD per million tokens, October 2026 list prices)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.llm.provider import Usage

LONG_PROMPT_TOKENS = 100_000


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_write: float
    cache_read: float


PRICES: dict[str, Price] = {
    "claude-opus-5-5": Price(4.00, 20.00, 5.00, 0.20),
    "claude-haiku-5-5": Price(0.10, 0.50, 0.125, 0.01),
    "claude-haiku-5-5:long": Price(0.50, 2.50, 0.625, 0.05),
}


def price_for(model: str, usage: Usage) -> Price | None:
    base = model.split("@")[0]
    if base.startswith("claude-haiku-5-5"):
        prompt = (
            usage.input_tokens + usage.cache_read_input_tokens + usage.cache_creation_input_tokens
        )
        return PRICES[
            "claude-haiku-5-5:long" if prompt > LONG_PROMPT_TOKENS else "claude-haiku-5-5"
        ]
    for key, price in PRICES.items():
        if base.startswith(key):
            return price
    return None


def cost_usd(model: str, usage: Usage) -> float:
    price = price_for(model, usage)
    if price is None:
        return 0.0
    total = (
        usage.input_tokens * price.input
        + usage.cache_creation_input_tokens * price.cache_write
        + usage.cache_read_input_tokens * price.cache_read
        + usage.output_tokens * price.output
    )
    return round(total / 1_000_000, 6)


def usage_dict(usage: Usage, model: str) -> dict[str, Any]:
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_input_tokens": usage.cache_read_input_tokens,
        "cache_creation_input_tokens": usage.cache_creation_input_tokens,
        "thinking_tokens": usage.thinking_tokens,
        "model": model,
        "cost_usd": cost_usd(model, usage),
    }
