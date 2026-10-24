"""Thin data-access functions. Every function takes an open Session and commits when it writes."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Chat, ChatDocument, Chunk, Document, Message, Page, utcnow


@dataclass(frozen=True)
class PageData:
    page_number: int
    text: str
    char_count: int
    is_scanned: bool


@dataclass(frozen=True)
class ChunkData:
    page_number: int
    chunk_index: int
    char_start: int
    char_end: int
    text: str
    token_count: int


@dataclass(frozen=True)
class ExchangeIds:
    user_id: str
    assistant_id: str


def chunk_row_id(document_id: str, chunk_index: int) -> str:
    return f"{document_id}:{chunk_index:05d}"


# --- documents -----------------------------------------------------------------------------


def create_document(
    session: Session, *, document_id: str, filename: str, stored_path: str, size_bytes: int
) -> Document:
    doc = Document(
        id=document_id,
        filename=filename,
        stored_path=stored_path,
        size_bytes=size_bytes,
        status="processing",
    )
    session.add(doc)
    session.commit()
    return doc


def get_document(session: Session, document_id: str) -> Document | None:
    return session.get(Document, document_id)


def list_documents(session: Session) -> list[Document]:
    stmt = select(Document).order_by(Document.created_at, Document.id)
    return list(session.scalars(stmt))


def count_documents(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Document)) or 0


def ready_document_ids(session: Session) -> list[str]:
    stmt = (
        select(Document.id)
        .where(Document.status == "ready")
        .order_by(Document.created_at, Document.id)
    )
    return list(session.scalars(stmt))


def set_document_status(
    session: Session,
    document_id: str,
    status: str,
    *,
    error: str | None = None,
    page_count: int | None = None,
    chunk_count: int | None = None,
    scanned_pages: int | None = None,
) -> Document | None:
    doc = session.get(Document, document_id)
    if doc is None:
        return None
    doc.status = status
    doc.error = error
    if page_count is not None:
        doc.page_count = page_count
    if chunk_count is not None:
        doc.chunk_count = chunk_count
    if scanned_pages is not None:
        doc.scanned_pages = scanned_pages
    doc.updated_at = utcnow()
    session.commit()
    return doc


def delete_document(session: Session, document_id: str) -> Document | None:
    doc = session.get(Document, document_id)
    if doc is None:
        return None
    session.delete(doc)
    session.commit()
    return doc


def mark_stale_processing_failed(session: Session, error: str) -> int:
    docs = list(session.scalars(select(Document).where(Document.status == "processing")))
    for doc in docs:
        doc.status = "failed"
        doc.error = error
        doc.updated_at = utcnow()
    session.commit()
    return len(docs)


def replace_pages_and_chunks(
    session: Session, document_id: str, pages: Sequence[PageData], chunks: Sequence[ChunkData]
) -> list[str]:
    session.execute(delete(Page).where(Page.document_id == document_id))
    session.execute(delete(Chunk).where(Chunk.document_id == document_id))
    session.add_all(
        Page(
            document_id=document_id,
            page_number=p.page_number,
            text=p.text,
            char_count=p.char_count,
            is_scanned=p.is_scanned,
        )
        for p in pages
    )
    ids: list[str] = []
    for c in chunks:
        cid = chunk_row_id(document_id, c.chunk_index)
        ids.append(cid)
        session.add(
            Chunk(
                id=cid,
                document_id=document_id,
                page_number=c.page_number,
                chunk_index=c.chunk_index,
                char_start=c.char_start,
                char_end=c.char_end,
                text=c.text,
                token_count=c.token_count,
            )
        )
    session.commit()
    return ids


def get_page_text(session: Session, document_id: str, page_number: int) -> str | None:
    stmt = select(Page.text).where(Page.document_id == document_id, Page.page_number == page_number)
    return session.scalar(stmt)


def get_chunks_by_ids(session: Session, ids: Iterable[str]) -> dict[str, Chunk]:
    wanted = list(dict.fromkeys(ids))
    if not wanted:
        return {}
    stmt = select(Chunk).options(selectinload(Chunk.document)).where(Chunk.id.in_(wanted))
    return {c.id: c for c in session.scalars(stmt)}


def list_chunks_for_documents(session: Session, document_ids: Iterable[str]) -> list[Chunk]:
    wanted = list(dict.fromkeys(document_ids))
    if not wanted:
        return []
    stmt = (
        select(Chunk)
        .where(Chunk.document_id.in_(wanted))
        .order_by(Chunk.document_id, Chunk.chunk_index)
    )
    return list(session.scalars(stmt))


# --- chats ---------------------------------------------------------------------------------


def _chat_stmt():
    return select(Chat).options(selectinload(Chat.document_links), selectinload(Chat.messages))


def create_chat(session: Session, title: str | None, document_ids: Sequence[str]) -> Chat:
    chat = Chat(title=(title or "").strip()[:120])
    chat.document_links = [
        ChatDocument(document_id=doc_id, position=i)
        for i, doc_id in enumerate(dict.fromkeys(document_ids))
    ]
    session.add(chat)
    session.commit()
    return get_chat(session, chat.id)  # type: ignore[return-value]


def get_chat(session: Session, chat_id: str) -> Chat | None:
    return session.scalar(_chat_stmt().where(Chat.id == chat_id))


def list_chats(session: Session) -> list[Chat]:
    return list(session.scalars(_chat_stmt().order_by(Chat.updated_at.desc(), Chat.id)))


def set_chat_scope(session: Session, chat: Chat, document_ids: Sequence[str]) -> Chat:
    chat.document_links = [
        ChatDocument(document_id=doc_id, position=i)
        for i, doc_id in enumerate(dict.fromkeys(document_ids))
    ]
    chat.updated_at = utcnow()
    session.commit()
    return get_chat(session, chat.id)  # type: ignore[return-value]


def set_chat_title(session: Session, chat: Chat, title: str) -> Chat:
    chat.title = title.strip()[:120]
    chat.updated_at = utcnow()
    session.commit()
    return chat


def delete_chat(session: Session, chat_id: str) -> bool:
    chat = session.get(Chat, chat_id)
    if chat is None:
        return False
    session.delete(chat)
    session.commit()
    return True


def scope_document_ids(session: Session, chat: Chat) -> list[str]:
    """Ready documents the chat may search: its explicit scope, or every ready document."""
    explicit = chat.document_ids
    if not explicit:
        return ready_document_ids(session)
    stmt = select(Document.id).where(Document.id.in_(explicit), Document.status == "ready")
    ready = set(session.scalars(stmt))
    return [doc_id for doc_id in explicit if doc_id in ready]


def list_messages(session: Session, chat_id: str) -> list[Message]:
    stmt = select(Message).where(Message.chat_id == chat_id).order_by(Message.seq)
    return list(session.scalars(stmt))


def append_exchange(
    session: Session, chat_id: str, user: dict[str, Any], assistant: dict[str, Any]
) -> ExchangeIds:
    """Persist a user turn and its answer atomically."""
    chat = session.get(Chat, chat_id)
    if chat is None:
        raise LookupError(f"chat {chat_id} not found")
    last_seq = session.scalar(select(func.max(Message.seq)).where(Message.chat_id == chat_id)) or 0
    user_row = Message(
        chat_id=chat_id,
        seq=last_seq + 1,
        role="user",
        content=user["content"],
        chunk_ids=user.get("chunk_ids"),
        rewritten_query=user.get("rewritten_query"),
    )
    assistant_row = Message(
        chat_id=chat_id,
        seq=last_seq + 2,
        role="assistant",
        content=assistant["content"],
        citations=assistant.get("citations") or [],
        usage=assistant.get("usage"),
        model=assistant.get("model"),
    )
    session.add_all([user_row, assistant_row])
    if not chat.title:
        chat.title = user["content"].strip().replace("\n", " ")[:60]
    chat.updated_at = utcnow()
    session.commit()
    return ExchangeIds(user_id=user_row.id, assistant_id=assistant_row.id)
