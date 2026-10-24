"""FastAPI application factory. Run with ``uvicorn app.main:app``."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chats, documents
from app.api.schemas import HealthOut
from app.config import MIB, Settings, get_settings
from app.db import repo
from app.errors import ProviderError
from app.ingest.pipeline import sweep_orphan_uploads
from app.services import AppServices, build_services, get_services

log = logging.getLogger(__name__)


class _BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    """Reject request bodies above ``limit`` bytes with a JSON 413, before or while reading."""

    def __init__(self, app, limit: int) -> None:  # noqa: ANN001
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.limit:
            await self._reject(scope, receive, send)
            return
        received = 0

        async def limited_receive():  # noqa: ANN202
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.limit:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await self._reject(scope, receive, send)

    async def _reject(self, scope, receive, send) -> None:  # noqa: ANN001
        response = JSONResponse(
            {"detail": f"Request body exceeds {self.limit // MIB} MiB"}, status_code=413
        )
        await response(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logging.basicConfig(level=settings.log_level.upper())
    services = build_services(settings)
    app.state.services = services
    await run_in_threadpool(services.warm_up)
    with services.session_factory() as session:
        stale = repo.mark_stale_processing_failed(
            session, "Server restarted during ingestion; upload the file again"
        )
    if stale:
        log.warning("marked %d interrupted ingestion(s) as failed", stale)
    removed = sweep_orphan_uploads(services)
    if removed:
        log.info("removed %d orphan upload(s)", removed)
    loaded = services.bm25.load_from_db(services.session_factory)
    log.info("ready: provider=%s, %d document(s) indexed", settings.llm_provider, loaded)
    try:
        yield
    finally:
        services.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="pdf-chat-rag",
        version="0.1.0",
        description="Chat with your PDFs: hybrid retrieval and Claude answers with citations.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Range", "Last-Event-ID"],
        expose_headers=["Accept-Ranges", "Content-Range", "Content-Disposition"],
    )
    app.add_middleware(BodyLimitMiddleware, limit=settings.body_limit_bytes)

    @app.exception_handler(ProviderError)
    async def _provider_error(_request: Request, exc: ProviderError) -> JSONResponse:
        return JSONResponse({"detail": exc.message, "code": exc.code}, status_code=502)

    @app.get("/health", response_model=HealthOut, tags=["meta"])
    def health(services: Annotated[AppServices, Depends(get_services)]) -> HealthOut:
        with services.session_factory() as session:
            count = repo.count_documents(session)
        return HealthOut(
            status="ok",
            llm_provider=settings.llm_provider,
            embeddings_provider=settings.embeddings_provider,
            answer_model=settings.answer_model if settings.llm_provider == "anthropic" else "mock",
            documents=count,
        )

    app.include_router(documents.router)
    app.include_router(chats.router)
    return app


app = create_app()
