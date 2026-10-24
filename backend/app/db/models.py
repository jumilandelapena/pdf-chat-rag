"""ORM models. Timestamps are naive UTC; the API layer attaches the UTC zone."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="processing")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scanned_pages: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    pages: Mapped[list[Page]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped[Document] = relationship(back_populates="pages")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index("ix_chunks_document_page", "document_id", "page_number"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    document_links: Mapped[list[ChatDocument]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatDocument.position",
    )
    messages: Mapped[list[Message]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.seq",
    )

    @property
    def document_ids(self) -> list[str]:
        return [link.document_id for link in self.document_links]


class ChatDocument(Base):
    """Explicit chat scope. No rows for a chat means "all ready documents"."""

    __tablename__ = "chat_documents"

    chat_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    chat: Mapped[Chat] = relationship(back_populates="document_links")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("chat_id", "seq"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    chat_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("chats.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # user rows: ordered chunk ids sent as document blocks, and the retrieval query used
    chunk_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    rewritten_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    # assistant rows
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    chat: Mapped[Chat] = relationship(back_populates="messages")
