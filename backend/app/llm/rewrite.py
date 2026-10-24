"""Pure helpers for the follow-up query rewrite (used for retrieval only)."""

from __future__ import annotations

from typing import Any

from app.llm.prompts import REWRITE_USER_TEMPLATE
from app.llm.provider import HistoryTurn

MAX_ASSISTANT_CHARS = 600
MAX_QUERY_CHARS = 500


def build_rewrite_messages(
    question: str, history: list[HistoryTurn], history_turns: int
) -> list[dict[str, Any]]:
    turns = [
        f"User: {turn.user_text}\nAssistant: {turn.assistant_text[:MAX_ASSISTANT_CHARS]}"
        for turn in history[-history_turns:]
    ]
    content = REWRITE_USER_TEMPLATE.format(turns="\n".join(turns) or "(none)", question=question)
    return [{"role": "user", "content": content}]


def clean_rewrite_output(text: str | None, question: str) -> str:
    """First line of the model output, or the original question when the output is unusable."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(lines) != 1:
        return question
    query = lines[0].strip().strip("\"'").strip()
    if not query or len(query) > MAX_QUERY_CHARS:
        return question
    return query
