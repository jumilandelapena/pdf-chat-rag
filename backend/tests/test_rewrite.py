from app.llm.provider import HistoryTurn
from app.llm.rewrite import build_rewrite_messages, clean_rewrite_output


def test_messages_include_recent_turns_only() -> None:
    history = [HistoryTurn(f"q{i}", [], f"a{i}" * 400) for i in range(4)]
    messages = build_rewrite_messages("how heavy is it?", history, history_turns=2)
    assert len(messages) == 1 and messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert "User: q2" in content and "User: q3" in content and "User: q1" not in content
    assert "Latest message: how heavy is it?" in content
    assert content.rstrip().endswith("Standalone query:")
    assert len(content) < 2 * 650 + 200
    assert "(none)" in build_rewrite_messages("hi", [], 6)[0]["content"]


def test_clean_output_fallbacks() -> None:
    assert (
        clean_rewrite_output('"crawler transporter weight"\n', "q") == "crawler transporter weight"
    )
    assert clean_rewrite_output("", "q") == "q"
    assert clean_rewrite_output(None, "q") == "q"
    assert clean_rewrite_output("line one\nline two", "q") == "q"
    assert clean_rewrite_output("x" * 501, "q") == "q"
    assert clean_rewrite_output("  plain query  ", "q") == "plain query"
