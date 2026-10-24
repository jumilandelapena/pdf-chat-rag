import re
from pathlib import Path

import pytest

from app.ingest.pdf import extract_pages
from app.llm.mock_provider import MockProvider, pick_quote
from app.llm.provider import AnswerRequest, ChunkRef, Final, HistoryTurn, TextDelta


def test_pick_quote_skips_abbreviations_and_returns_offsets(sample_pdf: Path) -> None:
    page1 = extract_pages(sample_pdf)[0].text
    quote, start = pick_quote(page1)
    assert page1[start : start + len(quote)] == quote
    assert len(quote) >= 40 and not re.search(r"\b[A-Z]\.$", quote)
    assert quote.endswith((".", "!", "?"))
    assert pick_quote("tiny text") == ("tiny text", 0)


@pytest.mark.anyio
async def test_stream_matches_final_and_offsets_history_docs() -> None:
    provider = MockProvider(delay_s=0)
    chunk_text = (
        "First sentence is short. Any attempt to brew coffee with a teapot results in error 418."
    )
    history_refs = [
        ChunkRef("h:00000", "h", "h.pdf", 1, 0, 0, "x"),
        ChunkRef("h:00001", "h", "h.pdf", 2, 1, 0, "y"),
    ]
    history = [HistoryTurn("q", history_refs, "a")]
    chunks = [
        ChunkRef("d:00001", "d", "z.pdf", 2, 1, 0, chunk_text),
        ChunkRef(
            "d:00000", "d", "a.pdf", 1, 0, 0, "Alpha sentence long enough to be a quote indeed."
        ),
    ]
    streamed, final = "", None
    async for event in provider.stream_answer(AnswerRequest("q2", history, chunks)):
        if isinstance(event, TextDelta):
            streamed += event.text
        else:
            final = event
    assert isinstance(final, Final) and final.model == "mock" and final.stop_reason == "end_turn"
    assert streamed == "".join(b.text for b in final.blocks)
    cited = [c for b in final.blocks for c in b.citations]
    assert [c.document_index for c in cited] == [3, 2]
    assert cited[1].cited_text == "Alpha sentence long enough to be a quote indeed."
    assert cited[0].cited_text.startswith("Any attempt")
    assert chunk_text[cited[0].start_char_index : cited[0].end_char_index] == cited[0].cited_text
    assert await provider.rewrite("same", history) == "same"
    assert (await provider.judge("q", "r", "e", "answer")).score == 5


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
