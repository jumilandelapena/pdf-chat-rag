"""Persistent Chroma collection holding one vector per chunk. Single process only."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import chromadb
import numpy as np

from app.locks import INDEX_LOCK

BATCH = 256


class VectorStore:
    def __init__(self, path: Path) -> None:
        with INDEX_LOCK:
            self.client = chromadb.PersistentClient(
                path=str(path), settings=chromadb.Settings(anonymized_telemetry=False)
            )
            self.collection = self.client.get_or_create_collection(
                "chunks",
                embedding_function=None,
                configuration={"hnsw": {"space": "cosine"}},
            )

    def upsert(
        self,
        ids: Sequence[str],
        embeddings: np.ndarray,
        documents: Sequence[str],
        metadatas: Sequence[dict],
    ) -> None:
        with INDEX_LOCK:
            for k in range(0, len(ids), BATCH):
                self.collection.upsert(
                    ids=list(ids[k : k + BATCH]),
                    embeddings=[[float(x) for x in row] for row in embeddings[k : k + BATCH]],
                    documents=list(documents[k : k + BATCH]),
                    metadatas=list(metadatas[k : k + BATCH]),
                )

    def query(
        self, embedding: np.ndarray, document_ids: Sequence[str], k: int
    ) -> list[tuple[str, float]]:
        """Nearest chunks within ``document_ids`` as ``(chunk_id, cosine_distance)``."""
        if not document_ids or k <= 0:
            return []
        with INDEX_LOCK:
            if self.collection.count() == 0:
                return []
            result = self.collection.query(
                query_embeddings=[[float(x) for x in embedding]],
                n_results=k,
                where={"document_id": {"$in": list(document_ids)}},
                include=["distances"],
            )
        ids = result["ids"][0] if result["ids"] else []
        distances = (result.get("distances") or [[]])[0]
        return list(zip(ids, distances, strict=False))

    def delete_document(self, document_id: str) -> None:
        with INDEX_LOCK:
            self.collection.delete(where={"document_id": document_id})

    def count(self) -> int:
        with INDEX_LOCK:
            return self.collection.count()
