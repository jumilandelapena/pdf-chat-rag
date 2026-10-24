"""Chats, chat scope and the streamed answer endpoint (Server-Sent Events)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.api.schemas import ChatCreate, ChatOut, ChatPatch, ChatSummary, MessageCreate, message_out
from app.db import repo
from app.db.models import Chat, Chunk
from app.db.repo import ExchangeIds
from app.errors import ProviderError
from app.llm.citations import CitationOut, citation_dict, map_citations
from app.llm.pricing import usage_dict
from app.llm.prompts import build_request, sort_chunks
from app.llm.provider import AnswerRequest, ChunkRef, Final, HistoryTurn, TextDelta
from app.retrieval.hybrid import retrieve
from app.services import AppServices, get_services

log = logging.getLogger(__name__)
router = APIRouter(prefix="/chats", tags=["chats"])
Services = Annotated[AppServices, Depends(get_services)]

STOP_ERRORS = {
    "max_tokens": ("max_tokens", "The answer was cut off (max_tokens). Ask a narrower question."),
    "refusal": ("refusal", "The model declined to answer this request."),
    "model_context_window_exceeded": (
        "context_window",
        "The conversation is too long for the model. Start a new chat.",
    ),
}


def chat_summary(chat: Chat) -> ChatSummary:
    return ChatSummary(
        id=chat.id,
        title=chat.title,
        document_ids=chat.document_ids,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=len(chat.messages),
    )


def chat_out(chat: Chat) -> ChatOut:
    return ChatOut(
        **chat_summary(chat).model_dump(), messages=[message_out(m) for m in chat.messages]
    )


def _validate_scope(session, document_ids: list[str]) -> None:  # noqa: ANN001
    known = {d.id for d in repo.list_documents(session)}
    unknown = [doc_id for doc_id in document_ids if doc_id not in known]
    if unknown:
        raise HTTPException(422, f"Unknown document id(s): {', '.join(unknown)}")


def get_chat_or_404(chat_id: str, services: Services) -> Chat:
    with services.session_factory() as session:
        chat = repo.get_chat(session, chat_id)
    if chat is None:
        raise HTTPException(404, "Chat not found")
    return chat


ChatDep = Annotated[Chat, Depends(get_chat_or_404)]


@router.post("", status_code=201, response_model=ChatOut)
def create_chat(body: ChatCreate, services: Services) -> ChatOut:
    with services.session_factory() as session:
        _validate_scope(session, body.document_ids)
        return chat_out(repo.create_chat(session, body.title, body.document_ids))


@router.get("", response_model=list[ChatSummary])
def list_chats(services: Services) -> list[ChatSummary]:
    with services.session_factory() as session:
        return [chat_summary(c) for c in repo.list_chats(session)]


@router.get("/{chat_id}", response_model=ChatOut)
def get_chat(chat: ChatDep) -> ChatOut:
    return chat_out(chat)


@router.patch("/{chat_id}", response_model=ChatOut)
def patch_chat(body: ChatPatch, chat: ChatDep, services: Services) -> ChatOut:
    with services.session_factory() as session:
        row = repo.get_chat(session, chat.id)
        assert row is not None
        if body.document_ids is not None:
            _validate_scope(session, body.document_ids)
            row = repo.set_chat_scope(session, row, body.document_ids)
        if body.title is not None:
            repo.set_chat_title(session, row, body.title)
        return chat_out(repo.get_chat(session, chat.id))  # type: ignore[arg-type]


@router.delete("/{chat_id}", status_code=204)
def delete_chat(chat: ChatDep, services: Services) -> Response:
    with services.session_factory() as session:
        repo.delete_chat(session, chat.id)
    return Response(status_code=204)


def chunk_ref(chunk: Chunk) -> ChunkRef:
    return ChunkRef(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        filename=chunk.document.filename,
        page=chunk.page_number,
        chunk_index=chunk.chunk_index,
        char_start=chunk.char_start,
        text=chunk.text,
    )


def load_history(session, chat_id: str, history_turns: int) -> list[HistoryTurn]:  # noqa: ANN001
    """Rebuild past exchanges with the exact chunks that were sent (deleted chunks skipped)."""
    turns: list[HistoryTurn] = []
    pending = None
    for message in repo.list_messages(session, chat_id):
        if message.role == "user":
            pending = message
        elif message.role == "assistant" and pending is not None:
            ids = pending.chunk_ids or []
            rows = repo.get_chunks_by_ids(session, ids)
            refs = [chunk_ref(rows[cid]) for cid in ids if cid in rows]
            turns.append(HistoryTurn(pending.content, refs, message.content))
            pending = None
    return turns[-history_turns:]


def _persist(
    services: AppServices,
    chat_id: str,
    question: str,
    chunks: list[ChunkRef],
    rewritten_query: str | None,
    text: str,
    citations: list[CitationOut],
    usage: dict[str, Any],
    model: str,
) -> ExchangeIds:
    with services.session_factory() as session:
        return repo.append_exchange(
            session,
            chat_id,
            user={
                "content": question,
                "chunk_ids": [c.chunk_id for c in sort_chunks(chunks)],
                "rewritten_query": rewritten_query,
            },
            assistant={
                "content": text,
                "citations": [citation_dict(c) for c in citations],
                "usage": usage,
                "model": model,
            },
        )


def sse(event: str, data: Any) -> ServerSentEvent:
    return ServerSentEvent(event=event, data=data)


def sse_error(code: str, message: str) -> ServerSentEvent:
    return sse("error", {"code": code, "message": message})


@router.post("/{chat_id}/messages", response_class=EventSourceResponse)
async def send_message(
    body: MessageCreate, chat: ChatDep, services: Services
) -> AsyncIterator[ServerSentEvent]:
    """Answer a question as a stream of events: status*, token+, citations, usage, done | error."""
    settings = services.settings
    question = body.content.strip()
    with services.session_factory() as session:
        history = load_history(session, chat.id, settings.history_turns)
        document_ids = repo.scope_document_ids(session, chat)
    if not document_ids:
        yield sse_error(
            "no_documents", "Upload a PDF and wait until it is ready, or widen the chat scope."
        )
        return
    query = question
    if history:
        yield sse("status", {"stage": "rewriting"})
        query = await services.provider.rewrite(question, history)
    yield sse("status", {"stage": "retrieving"})
    hits = await run_in_threadpool(retrieve, services, query, document_ids)
    if not hits:
        yield sse_error("no_results", "No passages matched the question in the selected documents.")
        return
    chunks = [chunk_ref(h.chunk) for h in hits]
    request = AnswerRequest(question, history, chunks)
    _, flat = build_request(settings, request)
    yield sse("status", {"stage": "thinking"})
    final: Final | None = None
    try:
        async for event in services.provider.stream_answer(request):
            if isinstance(event, TextDelta):
                yield sse("token", {"text": event.text})
            elif isinstance(event, Final):
                final = event
    except ProviderError as exc:
        log.warning("provider error in chat %s: %s", chat.id, exc.message)
        yield sse_error(exc.code, exc.message)
        return
    if final is None:
        yield sse_error("provider_error", "The provider returned no final message.")
        return
    if final.stop_reason in STOP_ERRORS:
        code, message = STOP_ERRORS[final.stop_reason]
        if final.stop_reason == "refusal" and final.stop_details_category:
            message = f"{message[:-1]} (category: {final.stop_details_category})."
        yield sse_error(code, message)
        return
    text, citations = map_citations(final.blocks, flat)
    usage = usage_dict(final.usage, final.model)
    rewritten = query if history else None
    ids = await run_in_threadpool(
        _persist,
        services,
        chat.id,
        question,
        chunks,
        rewritten,
        text,
        citations,
        usage,
        final.model,
    )
    yield sse("citations", [citation_dict(c) for c in citations])
    yield sse("usage", usage)
    yield sse(
        "done",
        {
            "message_id": ids.assistant_id,
            "user_message_id": ids.user_id,
            "rewritten_query": rewritten,
        },
    )
