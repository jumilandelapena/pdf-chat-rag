"""Process-wide locks.

PyMuPDF is not thread-safe, Chroma is single-process, and the embedding model should not run
concurrently on a small host. Three re-entrant locks serialise those resources:

- ``INGEST_LOCK``: one ingestion job at a time; every PyMuPDF call runs inside it.
- ``MODEL_LOCK``: every ``SentenceTransformer.encode`` call.
- ``INDEX_LOCK``: every Chroma call, every BM25 registry mutation or search, and the
  status-commit / delete critical sections.
"""

import threading

INGEST_LOCK = threading.RLock()
MODEL_LOCK = threading.RLock()
INDEX_LOCK = threading.RLock()
