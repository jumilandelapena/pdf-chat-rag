"""BM25 keyword search.

Token corpora are kept per document (loaded at startup, replaced on ingestion). A BM25 index is
built lazily per chat scope (the set of searched documents) and cached until any member document
changes, so IDF statistics are comparable across the files being searched.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session, sessionmaker

from app.db import repo
from app.locks import INDEX_LOCK

TOKEN_RE = re.compile(r"(?u)\b\w\w+\b")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


class BM25(BM25Okapi):
    """BM25Okapi with the Lucene idf ``log(1 + (N - n + 0.5) / (n + 0.5))``.

    The classic Okapi idf is zero or negative for terms that occur in half or more of the
    chunks, which happens constantly in small corpora (one short PDF). The Lucene variant is
    always positive, so a matching chunk always outscores a non-matching one.
    """

    def _calc_idf(self, nd: dict[str, int]) -> None:
        for word, freq in nd.items():
            self.idf[word] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))


@dataclass
class _DocCorpus:
    chunk_ids: list[str]
    tokens: list[list[str]]


@dataclass
class _ScopeIndex:
    bm25: BM25
    chunk_ids: list[str]


class BM25Registry:
    def __init__(self) -> None:
        self._docs: dict[str, _DocCorpus] = {}
        self._scopes: dict[frozenset[str], _ScopeIndex] = {}

    def load_from_db(self, session_factory: sessionmaker[Session]) -> int:
        with INDEX_LOCK, session_factory() as session:
            self._docs.clear()
            self._scopes.clear()
            for doc_id in repo.ready_document_ids(session):
                chunks = repo.list_chunks_for_documents(session, [doc_id])
                self._docs[doc_id] = _DocCorpus(
                    [c.id for c in chunks], [tokenize(c.text) for c in chunks]
                )
            return len(self._docs)

    def set_document(
        self, document_id: str, chunk_ids: Sequence[str], texts: Sequence[str]
    ) -> None:
        with INDEX_LOCK:
            self._docs[document_id] = _DocCorpus(list(chunk_ids), [tokenize(t) for t in texts])
            self._drop_scopes_with(document_id)

    def remove_document(self, document_id: str) -> None:
        with INDEX_LOCK:
            self._docs.pop(document_id, None)
            self._drop_scopes_with(document_id)

    def has_document(self, document_id: str) -> bool:
        with INDEX_LOCK:
            return document_id in self._docs

    def _drop_scopes_with(self, document_id: str) -> None:
        self._scopes = {k: v for k, v in self._scopes.items() if document_id not in k}

    def search(self, document_ids: Sequence[str], query: str, k: int) -> list[tuple[str, float]]:
        tokens = tokenize(query)
        if not tokens or k <= 0:
            return []
        with INDEX_LOCK:
            key = frozenset(document_ids) & set(self._docs)
            if not key:
                return []
            index = self._scopes.get(key)
            if index is None:
                chunk_ids: list[str] = []
                corpus: list[list[str]] = []
                for doc_id in sorted(key):
                    chunk_ids.extend(self._docs[doc_id].chunk_ids)
                    corpus.extend(self._docs[doc_id].tokens)
                if not any(corpus):
                    return []
                index = _ScopeIndex(BM25(corpus), chunk_ids)
                self._scopes[key] = index
            scores = np.asarray(index.bm25.get_scores(tokens), dtype=np.float64)
            order = np.argsort(-scores, kind="stable")
            out: list[tuple[str, float]] = []
            for idx in order[:k]:
                if scores[idx] <= 0:
                    break
                out.append((index.chunk_ids[int(idx)], float(scores[idx])))
            return out
