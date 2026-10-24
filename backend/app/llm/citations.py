"""Map the model's raw citations back to chunks, pages and answer offsets.

``text_start``/``text_end`` are UTF-16 code-unit offsets into the full answer (JavaScript string
indices, so the frontend can slice without conversion). ``page_char_start``/``page_char_end`` are
Python code-point offsets into the stored page text (server-side use and tests).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

from app.llm.provider import ChunkRef, FinalTextBlock

log = logging.getLogger(__name__)


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


@dataclass(frozen=True)
class CitationOut:
    n: int
    document_id: str
    filename: str
    page: int
    quote: str
    text_start: int
    text_end: int
    chunk_id: str
    page_char_start: int
    page_char_end: int


def map_citations(
    blocks: list[FinalTextBlock], flat: list[ChunkRef]
) -> tuple[str, list[CitationOut]]:
    """Return the full answer text and its citations numbered by first appearance."""
    offset = 0
    numbered: dict[tuple[int, str], int] = {}
    out: list[CitationOut] = []
    for block in blocks:
        span = (offset, offset + utf16_len(block.text))
        for raw in block.citations:
            if raw.document_index < 0 or raw.document_index >= len(flat):
                log.warning("citation document_index %d out of range", raw.document_index)
                continue
            ref = flat[raw.document_index]
            key = (raw.document_index, raw.cited_text.strip())
            n = numbered.setdefault(key, len(numbered) + 1)
            out.append(
                CitationOut(
                    n=n,
                    document_id=ref.document_id,
                    filename=ref.filename,
                    page=ref.page,
                    quote=raw.cited_text,
                    text_start=span[0],
                    text_end=span[1],
                    chunk_id=ref.chunk_id,
                    page_char_start=ref.char_start + raw.start_char_index,
                    page_char_end=ref.char_start + raw.end_char_index,
                )
            )
        offset = span[1]
    return "".join(b.text for b in blocks), out


def citation_dict(citation: CitationOut) -> dict[str, Any]:
    return asdict(citation)
