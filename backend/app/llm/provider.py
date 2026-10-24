"""Provider-neutral request and response types, and the provider factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

from app.config import Settings


@dataclass(frozen=True)
class ChunkRef:
    """A retrieved chunk as sent to the model (one document block)."""

    chunk_id: str
    document_id: str
    filename: str
    page: int
    chunk_index: int
    char_start: int
    text: str


@dataclass(frozen=True)
class HistoryTurn:
    user_text: str
    chunks: list[ChunkRef]
    assistant_text: str


@dataclass(frozen=True)
class AnswerRequest:
    question: str
    history: list[HistoryTurn]
    chunks: list[ChunkRef]


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class RawCitation:
    document_index: int
    cited_text: str
    start_char_index: int
    end_char_index: int


@dataclass(frozen=True)
class FinalTextBlock:
    text: str
    citations: list[RawCitation] = field(default_factory=list)


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    thinking_tokens: int = 0


@dataclass(frozen=True)
class Final:
    blocks: list[FinalTextBlock]
    stop_reason: str | None
    usage: Usage
    model: str
    stop_details_category: str | None = None
    request_id: str | None = None


@dataclass(frozen=True)
class JudgeResult:
    score: int | None
    explanation: str
    usage: Usage
    model: str


class LLMProvider(Protocol):
    name: str

    async def rewrite(self, question: str, history: list[HistoryTurn]) -> str: ...

    def stream_answer(self, request: AnswerRequest) -> AsyncIterator[TextDelta | Final]: ...

    async def judge(
        self, question: str, reference: str, excerpts: str, answer: str
    ) -> JudgeResult: ...


def make_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings)
    from app.llm.mock_provider import MockProvider

    return MockProvider()
