from app.llm.pricing import cost_usd, usage_dict
from app.llm.provider import Usage


def test_opus_arithmetic() -> None:
    usage = Usage(1000, 500, 2000, 3000)
    assert cost_usd("claude-opus-5-5", usage) == round((4000 + 15000 + 400 + 10000) / 1e6, 6)


def test_haiku_standard_and_long_tier() -> None:
    assert cost_usd("claude-haiku-5-5", Usage(10_000, 1_000, 0, 0)) == round(0.001 + 0.0005, 6)
    long_usage = Usage(150_000, 1_000, 0, 0)
    expected = round(150_000 * 0.5 / 1e6 + 1_000 * 2.5 / 1e6, 6)
    assert cost_usd("claude-haiku-5-5", long_usage) == expected
    assert cost_usd("claude-haiku-5-5-20260301", Usage(10_000, 0, 0, 0)) == 0.001


def test_unknown_and_mock_models_cost_nothing() -> None:
    assert cost_usd("mock", Usage(1000, 1000, 0, 0)) == 0.0
    assert usage_dict(Usage(), "mock") == {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "thinking_tokens": 0,
        "model": "mock",
        "cost_usd": 0.0,
    }
