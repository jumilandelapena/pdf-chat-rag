"""Long-lived application services (database, embedder, indexes, LLM provider)."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.engine import make_engine, make_session_factory
from app.db.models import Base
from app.ingest.embeddings import Embedder, make_embedder
from app.llm.provider import LLMProvider, make_provider
from app.locks import MODEL_LOCK
from app.retrieval.bm25 import BM25Registry
from app.retrieval.vector_store import VectorStore


@dataclass
class AppServices:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    vector_store: VectorStore
    bm25: BM25Registry
    provider: LLMProvider
    _embedder: Embedder | None = field(default=None, repr=False)

    @property
    def embedder(self) -> Embedder:
        with MODEL_LOCK:
            if self._embedder is None:
                self._embedder = make_embedder(self.settings)
            return self._embedder

    def warm_up(self) -> None:
        """Load the embedding model (slow the first time: downloads ~130 MB)."""
        _ = self.embedder

    def close(self) -> None:
        self.engine.dispose()


def build_services(settings: Settings) -> AppServices:
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.sqlite_url)
    Base.metadata.create_all(engine)
    return AppServices(
        settings=settings,
        engine=engine,
        session_factory=make_session_factory(engine),
        vector_store=VectorStore(settings.chroma_dir),
        bm25=BM25Registry(),
        provider=make_provider(settings),
    )


def get_services(request: Request) -> AppServices:
    return request.app.state.services
