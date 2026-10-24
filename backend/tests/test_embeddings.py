import os

import numpy as np
import pytest

from app.config import Settings
from app.ingest.chunker import sub_windows
from app.ingest.embeddings import DIM, FakeEmbedder, normalise


def test_fake_embedder_is_deterministic_and_unit_norm() -> None:
    embedder = FakeEmbedder()
    a = embedder.embed_query("teapots brew coffee")
    b = FakeEmbedder().embed_query("teapots brew coffee")
    assert a.shape == (DIM,) and np.allclose(a, b)
    assert abs(float(np.linalg.norm(a)) - 1.0) < 1e-5
    passages = embedder.embed_passages(["one", "two"])
    assert passages.shape == (2, DIM)


def test_fake_embedder_ranks_lexical_overlap() -> None:
    embedder = FakeEmbedder()
    query = embedder.embed_query("which error does a teapot return when asked to brew coffee")
    docs = embedder.embed_passages(
        [
            "Any attempt to brew coffee with a teapot should result in the error code 418.",
            "The crawler-transporter carries the mobile launcher to the pad at one mile per hour.",
        ]
    )
    assert float(docs[0] @ query) > float(docs[1] @ query)


def test_long_text_is_mean_of_window_vectors() -> None:
    embedder = FakeEmbedder()
    text = " ".join(f"Sentence number {i} talks about topic {i % 7}." for i in range(500))
    windows = sub_windows(text, embedder.window_tokens, embedder.max_chars)
    assert len(windows) > 1
    expected = normalise(np.stack([FakeEmbedder._vector(w) for w in windows]).mean(axis=0))
    assert np.allclose(embedder.embed_passages([text])[0], expected, atol=1e-6)
    short = "A short passage."
    assert np.allclose(embedder.embed_passages([short])[0], FakeEmbedder._vector(short))


@pytest.mark.skipif(not os.environ.get("RUN_LOCAL_EMBEDDER"), reason="set RUN_LOCAL_EMBEDDER=1")
def test_local_embedder_smoke() -> None:
    from app.ingest.embeddings import LocalEmbedder

    embedder = LocalEmbedder(Settings(_env_file=None))
    vectors = embedder.embed_passages(["Coffee pots and teapots.", "Rocket crawler transporter."])
    query = embedder.embed_query("what is a teapot")
    assert vectors.shape == (2, DIM)
    assert float(vectors[0] @ query) > float(vectors[1] @ query)
