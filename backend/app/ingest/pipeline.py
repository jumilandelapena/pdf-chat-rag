"""Background ingestion: extract -> chunk -> embed -> index, and the matching delete."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from app.db import repo
from app.db.repo import ChunkData, PageData
from app.errors import IngestError
from app.ingest.chunker import chunk_document
from app.ingest.pdf import extract_pages
from app.locks import INDEX_LOCK, INGEST_LOCK

if TYPE_CHECKING:
    from app.services import AppServices

log = logging.getLogger(__name__)
EMBED_BATCH = 16
NO_TEXT_ERROR = "No extractable text (scanned PDF? OCR is not supported yet)"


def ingest_document(document_id: str, services: AppServices) -> None:
    """Run the full pipeline for one uploaded document. Safe to call from a worker thread."""
    settings = services.settings
    with INGEST_LOCK:
        with services.session_factory() as session:
            doc = repo.get_document(session, document_id)
            if doc is None or doc.status != "processing":
                return
            stored_path = doc.stored_path
        try:
            pages = extract_pages(stored_path)
            chunks = chunk_document(
                [(p.page_number, p.text) for p in pages],
                target_tokens=settings.chunk_tokens,
                overlap=settings.chunk_overlap,
                max_chars=settings.max_chunk_chars,
            )
            if not chunks:
                raise IngestError(NO_TEXT_ERROR)
            texts = [c.text for c in chunks]
            embedder = services.embedder
            vectors = np.concatenate(
                [
                    embedder.embed_passages(texts[k : k + EMBED_BATCH])
                    for k in range(0, len(texts), EMBED_BATCH)
                ]
            )
            with INDEX_LOCK:
                with services.session_factory() as session:
                    if repo.get_document(session, document_id) is None:
                        return  # deleted while we were working
                    ids = repo.replace_pages_and_chunks(
                        session,
                        document_id,
                        [
                            PageData(p.page_number, p.text, p.char_count, p.is_scanned)
                            for p in pages
                        ],
                        [
                            ChunkData(
                                c.page_number,
                                c.chunk_index,
                                c.char_start,
                                c.char_end,
                                c.text,
                                c.token_count,
                            )
                            for c in chunks
                        ],
                    )
                services.vector_store.upsert(
                    ids,
                    vectors,
                    texts,
                    [
                        {
                            "document_id": document_id,
                            "page": c.page_number,
                            "chunk_index": c.chunk_index,
                        }
                        for c in chunks
                    ],
                )
                services.bm25.set_document(document_id, ids, texts)
                with services.session_factory() as session:
                    repo.set_document_status(
                        session,
                        document_id,
                        "ready",
                        page_count=len(pages),
                        chunk_count=len(chunks),
                        scanned_pages=sum(1 for p in pages if p.is_scanned),
                    )
            log.info("ingested %s: %d pages, %d chunks", document_id, len(pages), len(chunks))
        except Exception as exc:  # noqa: BLE001 - any failure marks the document failed
            log.exception("ingestion failed for %s", document_id)
            message = str(exc) if isinstance(exc, IngestError) else f"{type(exc).__name__}: {exc}"
            with services.session_factory() as session:
                repo.set_document_status(session, document_id, "failed", error=message[:500])


def _unlink_with_retry(path: Path, attempts: int = 3, delay_s: float = 0.2) -> bool:
    for attempt in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return True
        except PermissionError:
            if attempt == attempts - 1:
                log.warning("could not delete %s (still open?)", path)
                return False
            time.sleep(delay_s)
    return False


def delete_document_everywhere(document_id: str, services: AppServices) -> bool:
    """Remove vectors, BM25 tokens, database rows and the stored file. False if unknown."""
    with INDEX_LOCK:
        with services.session_factory() as session:
            doc = repo.delete_document(session, document_id)
        if doc is None:
            return False
        services.vector_store.delete_document(document_id)
        services.bm25.remove_document(document_id)
    _unlink_with_retry(Path(doc.stored_path))
    return True


def sweep_orphan_uploads(services: AppServices) -> int:
    """Delete files in the uploads directory that no document row references."""
    uploads = services.settings.uploads_dir
    if not uploads.is_dir():
        return 0
    with services.session_factory() as session:
        referenced = {
            os.path.normcase(str(Path(d.stored_path).resolve()))
            for d in repo.list_documents(session)
        }
    removed = 0
    for path in uploads.iterdir():
        is_orphan = path.is_file() and os.path.normcase(str(path.resolve())) not in referenced
        if is_orphan and _unlink_with_retry(path):
            removed += 1
    return removed
