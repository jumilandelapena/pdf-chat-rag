"""Frozen prompts and the pure request builder for the answer model."""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.llm.provider import AnswerRequest, ChunkRef

SYSTEM_PROMPT = """You answer questions about PDF documents that the user uploaded. The documents are provided as excerpts attached to the conversation; each excerpt is labelled with its file name and page number.

Rules:
1. Answer only from the excerpts. Do not use outside knowledge, even for well-known facts.
2. If the excerpts do not contain the information, say so plainly in one sentence, for example: "The uploaded documents do not mention X." Do not guess and do not answer partially from memory.
3. Keep answers short: one to three sentences, or a short list when the question asks for several items. Quote numbers, names and dates exactly as they appear in the excerpts.
4. Never write page numbers, file names or phrases like "page 3 says" in your answer. Citations are attached automatically to the sentences you write; the reader sees them as numbered references.
5. Excerpts attached to earlier turns remain valid context for follow-up questions. When excerpts conflict, prefer the ones attached to the latest question and mention the discrepancy briefly.
6. Describe what the documents state; do not present the content as an official statement of the organisation that published them (for example, do not write "according to NASA").
7. Use plain prose. No headings, no markdown tables, no emoji."""

REWRITE_SYSTEM = (
    "Rewrite the user's latest message as one standalone search query for a document search "
    "engine. Use the earlier conversation only to resolve references such as it, that, they, "
    "the second one, or the same page. Keep every specific name, number and term from the latest "
    "message. If the message is already standalone, return it unchanged. Output only the query: "
    "no quotes, no explanation, no preamble."
)

REWRITE_USER_TEMPLATE = (
    "Conversation so far:\n{turns}\n\nLatest message: {question}\n\nStandalone query:"
)


def document_title(filename: str, page: int) -> str:
    return f"{filename} - page {page}"[:500]


def document_context(ref: ChunkRef) -> str:
    return f"document_id={ref.document_id}; chunk={ref.chunk_id}"


def document_block(ref: ChunkRef) -> dict[str, Any]:
    return {
        "type": "document",
        "source": {"type": "text", "media_type": "text/plain", "data": ref.text},
        "title": document_title(ref.filename, ref.page),
        "context": document_context(ref),
        "citations": {"enabled": True},
    }


def sort_chunks(chunks: list[ChunkRef]) -> list[ChunkRef]:
    return sorted(chunks, key=lambda c: (c.filename, c.page, c.chunk_index))


def build_request(
    settings: Settings, request: AnswerRequest
) -> tuple[dict[str, Any], list[ChunkRef]]:
    """Build the Messages API parameters and the flat list of document blocks in request order.

    ``citation.document_index`` indexes the returned flat list directly (history blocks first,
    then the current turn's sorted blocks). History turns are re-sent byte-identically so the
    prompt cache can serve them.
    """
    system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
    messages: list[dict[str, Any]] = []
    flat: list[ChunkRef] = []
    for turn in request.history[-settings.history_turns :]:
        blocks = [document_block(c) for c in turn.chunks]
        flat.extend(turn.chunks)
        messages.append(
            {"role": "user", "content": blocks + [{"type": "text", "text": turn.user_text}]}
        )
        messages.append({"role": "assistant", "content": turn.assistant_text})
    current = sort_chunks(request.chunks)
    blocks = [document_block(c) for c in current]
    if blocks:
        blocks[-1]["cache_control"] = {"type": "ephemeral"}
    flat.extend(current)
    messages.append(
        {"role": "user", "content": blocks + [{"type": "text", "text": request.question}]}
    )
    params = {
        "model": settings.answer_model,
        "max_tokens": settings.answer_max_tokens,
        "system": system,
        "messages": messages,
        "output_config": {"effort": settings.answer_effort},
    }
    return params, flat


JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "description": "1 (unfaithful) to 5 (fully supported)"},
        "explanation": {"type": "string"},
    },
    "required": ["score", "explanation"],
    "additionalProperties": False,
}

JUDGE_PROMPT = """You are grading whether an answer to a question is faithful to the source excerpts. Faithful means every factual claim in the answer is supported by the excerpts. The reference answer tells you what a correct answer contains; use it to spot wrong or invented details, but score faithfulness to the excerpts, not style. Scale: 5 every claim supported and the question is answered; 4 supported with a trivial omission; 3 mostly supported, one unsupported or vague detail; 2 a central claim is unsupported or wrong; 1 contradicts the excerpts or is fabricated. If the excerpts truly lack the answer and the answer says so, score 5.

Question: {question}
Reference answer: {reference}
Excerpts:
{excerpts}
Answer: {answer}

Return JSON with score and explanation (one sentence)."""
