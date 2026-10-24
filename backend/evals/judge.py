"""Faithfulness judge helpers (the model call itself lives in the provider)."""

from __future__ import annotations

from app.llm.provider import ChunkRef, JudgeResult, LLMProvider

MAX_EXCERPT_CHARS = 2500


def format_excerpts(chunks: list[ChunkRef]) -> str:
    """Plain-text excerpts for the judge (never citation document blocks)."""
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        text = chunk.text[:MAX_EXCERPT_CHARS]
        parts.append(f"[{i}] {chunk.filename}, page {chunk.page}:\n{text}")
    return "\n\n".join(parts)


async def judge_answer(
    provider: LLMProvider, question: str, reference: str, chunks: list[ChunkRef], answer: str
) -> JudgeResult:
    return await provider.judge(question, reference, format_excerpts(chunks), answer)
