from app.config import Settings
from app.llm.prompts import SYSTEM_PROMPT, build_request, document_title
from app.llm.provider import AnswerRequest, ChunkRef, HistoryTurn


def ref(i: int, filename: str = "a.pdf", page: int = 1) -> ChunkRef:
    return ChunkRef(f"doc{i}:{i:05d}", f"doc{i}", filename, page, i, i * 10, f"text {i}")


def test_block_order_cache_control_and_flat_list(settings: Settings) -> None:
    history = [HistoryTurn("q1", [ref(1, "b.pdf", 2)], "a1")]
    current = [ref(3, "b.pdf", 1), ref(2, "a.pdf", 5)]
    params, flat = build_request(settings, AnswerRequest("q2", history, current))

    assert params["model"] == settings.answer_model
    assert params["max_tokens"] == settings.answer_max_tokens
    assert params["output_config"] == {"effort": "low"}
    assert "thinking" not in params and "temperature" not in params and "top_p" not in params
    assert params["system"] == [
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
    ]

    messages = params["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    first = messages[0]["content"]
    assert first[0]["type"] == "document" and "cache_control" not in first[0]
    assert first[0]["title"] == "b.pdf - page 2"
    assert first[-1] == {"type": "text", "text": "q1"}
    assert messages[1]["content"] == "a1"

    last = messages[2]["content"]
    docs, question = last[:-1], last[-1]
    assert question == {"type": "text", "text": "q2"}
    assert [d["title"] for d in docs] == ["a.pdf - page 5", "b.pdf - page 1"]
    assert docs[-1]["cache_control"] == {"type": "ephemeral"} and "cache_control" not in docs[0]
    for d in docs:
        assert d["citations"] == {"enabled": True}
        assert d["context"].startswith("document_id=")
        assert d["source"]["type"] == "text" and d["source"]["media_type"] == "text/plain"
    assert flat == [history[0].chunks[0], current[1], current[0]]
    assert docs[0]["source"]["data"] == "text 2"


def test_history_is_trimmed_to_history_turns(settings: Settings) -> None:
    history = [HistoryTurn(f"q{i}", [ref(i)], f"a{i}") for i in range(8)]
    params, flat = build_request(settings, AnswerRequest("now", history, [ref(99)]))
    assert len(params["messages"]) == settings.history_turns * 2 + 1
    assert params["messages"][0]["content"][-1]["text"] == "q2"
    assert [c.chunk_id for c in flat] == [f"doc{i}:{i:05d}" for i in range(2, 8)] + ["doc99:00099"]


def test_no_chunks_and_long_titles(settings: Settings) -> None:
    params, flat = build_request(settings, AnswerRequest("q", [], []))
    assert params["messages"] == [{"role": "user", "content": [{"type": "text", "text": "q"}]}]
    assert flat == []
    assert len(document_title("x" * 600, 12)) == 500
