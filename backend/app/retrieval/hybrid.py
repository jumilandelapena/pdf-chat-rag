"""Hybrid retrieval: vector top-k + BM25 top-k, fused with RRF, loaded as chunk rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.db import repo
from app.db.models import Chunk
from app.retrieval.rrf import rrf_fuse

if TYPE_CHECKING:
    from app.services import AppServices


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    rrf_score: float
    vector_rank: int | None
    bm25_rank: int | None


def retrieve(
    services: AppServices,
    query: str,
    document_ids: list[str],
    *,
    top_k_vector: int | None = None,
    top_k_bm25: int | None = None,
    top_k_final: int | None = None,
) -> list[RetrievedChunk]:
    """Blocking. Returns at most ``top_k_final`` chunks from ``document_ids``."""
    settings = services.settings
    k_vector = top_k_vector or settings.top_k_vector
    k_bm25 = top_k_bm25 or settings.top_k_bm25
    k_final = top_k_final or settings.top_k_final
    if not document_ids or not query.strip():
        return []
    query_vector = services.embedder.embed_query(query)
    vector_ids = [
        cid for cid, _ in services.vector_store.query(query_vector, document_ids, k_vector)
    ]
    bm25_ids = [cid for cid, _ in services.bm25.search(document_ids, query, k_bm25)]
    fused = rrf_fuse([vector_ids, bm25_ids])[:k_final]
    with services.session_factory() as session:
        rows = repo.get_chunks_by_ids(session, [cid for cid, _ in fused])
    vector_rank = {cid: i for i, cid in enumerate(vector_ids, start=1)}
    bm25_rank = {cid: i for i, cid in enumerate(bm25_ids, start=1)}
    return [
        RetrievedChunk(rows[cid], score, vector_rank.get(cid), bm25_rank.get(cid))
        for cid, score in fused
        if cid in rows
    ]
