"""Offline provider for tests, CI and key-less demos.

The answer wording and the number of citations are fixed, but the quoted text is taken from the
real retrieved chunks, so the citation chips, the page jump and the highlight in the viewer are
meaningful even without an API key.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator

from app.ingest.chunker import PARAGRAPH_RE, SENTENCE_RE
from app.llm.provider import (
    AnswerRequest,
    Final,
    FinalTextBlock,
    HistoryTurn,
    JudgeResult,
    RawCitation,
    TextDelta,
    Usage,
)

MOCK_NOTE = (
    "(This answer was produced by the mock provider; set LLM_PROVIDER=anthropic for real answers.)"
)
MIN_QUOTE_CHARS = 40
ENDS_SENTENCE = re.compile(r"[.!?][\"')\]]*$")
ABBREVIATION = re.compile(r"\b[A-Z]\.$")


def pick_quote(text: str) -> tuple[str, int]:
    """Return a full sentence from ``text`` and its start offset (``text[start:] startswith``)."""
    for para in PARAGRAPH_RE.finditer(text):
        base = para.start()
        for match in SENTENCE_RE.finditer(para.group(0)):
            raw = match.group(0)
            sentence = raw.strip()
            if len(sentence) < MIN_QUOTE_CHARS or "[Page" in sentence:
                continue
            if not ENDS_SENTENCE.search(sentence) or ABBREVIATION.search(sentence):
                continue
            start = base + match.start() + (len(raw) - len(raw.lstrip()))
            return sentence, start
    fallback = text[:120]
    cut = fallback.rfind(" ")
    if cut > 20:
        fallback = fallback[:cut]
    return fallback, 0


class MockProvider:
    name = "mock"

    def __init__(self, delay_s: float = 0.015) -> None:
        self.delay_s = delay_s

    async def rewrite(self, question: str, history: list[HistoryTurn]) -> str:
        return question

    def _blocks(self, request: AnswerRequest) -> list[FinalTextBlock]:
        """Quote the two best-ranked chunks; document_index follows the request block order."""
        n_history = sum(len(turn.chunks) for turn in request.history)
        ordered = sorted(request.chunks, key=lambda c: (c.filename, c.page, c.chunk_index))
        picks = request.chunks[:2]
        blocks = [FinalTextBlock("Based on the uploaded documents, ")]
        lead_ins = ["", "A related passage states: "]
        for lead_in, pick in zip(lead_ins, picks, strict=False):
            quote, start = pick_quote(pick.text)
            index = n_history + ordered.index(pick)
            if lead_in:
                blocks.append(FinalTextBlock(lead_in))
            blocks.append(
                FinalTextBlock(
                    quote.rstrip(".!?"), [RawCitation(index, quote, start, start + len(quote))]
                )
            )
            blocks.append(FinalTextBlock(". "))
        blocks.append(FinalTextBlock(MOCK_NOTE))
        return blocks

    async def stream_answer(self, request: AnswerRequest) -> AsyncIterator[TextDelta | Final]:
        if not request.chunks:
            raise ValueError("mock provider needs at least one chunk")
        blocks = self._blocks(request)
        for block in blocks:
            for piece in re.findall(r"\S+\s*|\s+", block.text):
                yield TextDelta(piece)
                if self.delay_s:
                    await asyncio.sleep(self.delay_s)
        yield Final(blocks=blocks, stop_reason="end_turn", usage=Usage(), model="mock")

    async def judge(self, question: str, reference: str, excerpts: str, answer: str) -> JudgeResult:
        score = 5 if "[" not in answer and len(answer) > 0 else 1
        return JudgeResult(score=score, explanation="mock judge", usage=Usage(), model="mock")
