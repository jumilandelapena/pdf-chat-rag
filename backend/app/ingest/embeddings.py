"""Embedding providers: local bge-small-en-v1.5 via sentence-transformers, or a fake for tests.

Chunks can be longer than the 512-token input window of bge-small. Each chunk is therefore
embedded as the normalised mean of the embeddings of its <= ``embed_window_tokens`` sub-windows.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import Protocol

import numpy as np

from app.config import Settings
from app.ingest.chunker import sub_windows
from app.locks import MODEL_LOCK

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DIM = 384
TOKEN_RE = re.compile(r"(?u)\b\w\w+\b")


class Embedder(Protocol):
    dim: int

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


def normalise(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 0 else vector


def mean_of_windows(
    texts: list[str],
    encode: Callable[[list[str]], np.ndarray],
    window_tokens: int,
    max_chars: int,
) -> np.ndarray:
    """Embed every sub-window in one call and average the windows of each text."""
    if not texts:
        return np.zeros((0, DIM), dtype=np.float32)
    windows_per_text = [sub_windows(text, window_tokens, max_chars) for text in texts]
    flat = [w for windows in windows_per_text for w in windows]
    vectors = np.asarray(encode(flat), dtype=np.float32)
    out = np.zeros((len(texts), DIM), dtype=np.float32)
    pos = 0
    for i, windows in enumerate(windows_per_text):
        n = len(windows)
        out[i] = normalise(vectors[pos : pos + n].mean(axis=0))
        pos += n
    return out


class LocalEmbedder:
    """bge-small-en-v1.5 on CPU. Loads from ``EMBEDDING_MODEL_PATH`` when it is a directory."""

    dim = DIM

    def __init__(self, settings: Settings) -> None:
        from sentence_transformers import SentenceTransformer

        path = settings.embedding_model_path
        if path is not None and path.is_dir():
            self.source, kwargs = str(path), {}
        else:
            self.source, kwargs = (
                settings.embedding_model,
                {"revision": settings.embedding_revision},
            )
        self.window_tokens = settings.embed_window_tokens
        self.max_chars = settings.max_chunk_chars
        with MODEL_LOCK:
            self.model = SentenceTransformer(self.source, device="cpu", **kwargs)

    def _encode(self, texts: list[str]) -> np.ndarray:
        with MODEL_LOCK:
            return np.asarray(
                self.model.encode(texts, batch_size=16, normalize_embeddings=True),
                dtype=np.float32,
            )

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return mean_of_windows(texts, self._encode, self.window_tokens, self.max_chars)

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode([QUERY_PREFIX + text])[0]


class FakeEmbedder:
    """Deterministic feature-hashed vectors: lexical overlap gives a sensible cosine ranking."""

    dim = DIM

    def __init__(self, settings: Settings | None = None) -> None:
        self.window_tokens = settings.embed_window_tokens if settings else 480
        self.max_chars = settings.max_chunk_chars if settings else 4800

    @staticmethod
    def _vector(text: str) -> np.ndarray:
        vector = np.zeros(DIM, dtype=np.float32)
        for token in TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % DIM
            vector[bucket] += 1.0 if digest[4] & 1 else -1.0
        noise_bytes = hashlib.shake_256(text.encode("utf-8")).digest(DIM)
        noise = (np.frombuffer(noise_bytes, dtype=np.uint8).astype(np.float32) / 255.0) - 0.5
        vector += noise * 1e-3
        if not np.any(vector):
            vector[0] = 1.0
        return normalise(vector)

    def _encode(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vector(t) for t in texts]) if texts else np.zeros((0, DIM))

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return mean_of_windows(texts, self._encode, self.window_tokens, self.max_chars)

    def embed_query(self, text: str) -> np.ndarray:
        return self._vector(text)


def make_embedder(settings: Settings) -> Embedder:
    if settings.embeddings_provider == "fake":
        return FakeEmbedder(settings)
    return LocalEmbedder(settings)
