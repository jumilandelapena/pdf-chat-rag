"""Pydantic schemas shared with the frontend (mirrored in ``frontend/src/api/types.ts``)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field, field_validator


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


class DocumentOut(BaseModel):
    id: str
    filename: str
    status: Literal["processing", "ready", "failed"]
    error: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    scanned_pages: int = 0
    size_bytes: int
    created_at: UtcDatetime


class ChatCreate(BaseModel):
    document_ids: list[str] = Field(default_factory=list)  # [] = all ready documents
    title: str | None = None


class ChatPatch(BaseModel):
    document_ids: list[str] | None = None  # None = unchanged, [] = all ready documents
    title: str | None = None


class CitationOut(BaseModel):
    n: int
    document_id: str
    filename: str
    page: int
    quote: str
    text_start: int
    text_end: int
    chunk_id: str
    page_char_start: int
    page_char_end: int


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    thinking_tokens: int
    model: str
    cost_usd: float


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    citations: list[CitationOut] = Field(default_factory=list)
    usage: UsageOut | None = None
    rewritten_query: str | None = None
    created_at: UtcDatetime


class ChatSummary(BaseModel):
    id: str
    title: str
    document_ids: list[str]
    created_at: UtcDatetime
    updated_at: UtcDatetime
    message_count: int


class ChatOut(ChatSummary):
    messages: list[MessageOut]


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be blank")
        return value


class HealthOut(BaseModel):
    status: str
    llm_provider: str
    embeddings_provider: str
    answer_model: str
    documents: int


def message_out(row: Any) -> MessageOut:
    return MessageOut(
        id=row.id,
        role=row.role,
        content=row.content,
        citations=[CitationOut(**c) for c in (row.citations or [])],
        usage=UsageOut(**row.usage) if row.usage else None,
        rewritten_query=row.rewritten_query,
        created_at=row.created_at,
    )
