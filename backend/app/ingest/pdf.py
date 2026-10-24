"""Page text extraction with PyMuPDF.

Line-end hyphens are kept (no dehyphenation) so quotes match the pdf.js text layer in the
browser. Ligatures are expanded and soft hyphens removed for the same reason.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.errors import PdfError
from app.locks import INGEST_LOCK

FLAGS = (
    pymupdf.TEXTFLAGS_TEXT
    & ~pymupdf.TEXT_PRESERVE_LIGATURES
    & ~pymupdf.TEXT_USE_CID_FOR_UNKNOWN_UNICODE
)
SCANNED_THRESHOLD = 10


@dataclass(frozen=True)
class PageText:
    page_number: int  # 1-based
    text: str
    char_count: int
    is_scanned: bool
    replacement_chars: int = 0


def norm_block(raw: str) -> str:
    text = unicodedata.normalize("NFKC", raw).replace("­", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    lines = [re.sub(r"[  ]+$", "", line) for line in text.split("\n")]
    return "\n".join(line for line in lines if line.strip()).strip()


def join_blocks(blocks: list[str]) -> str:
    """Join normalised blocks: a blank line when either side is multi-line, else a newline."""
    out: list[str] = []
    for i, block in enumerate(blocks):
        if i:
            prev = blocks[i - 1]
            sep = "\n\n" if ("\n" in prev or "\n" in block) else "\n"
            out.append(sep)
        out.append(block)
    text = "".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _page_text(page: pymupdf.Page) -> str:
    raw_blocks = page.get_text("blocks", flags=FLAGS)
    blocks = [norm_block(b[4]) for b in raw_blocks if len(b) > 6 and b[6] == 0]
    return join_blocks([b for b in blocks if b])


def extract_pages(path: str | Path) -> list[PageText]:
    with INGEST_LOCK:
        try:
            doc = pymupdf.open(str(path))
        except (pymupdf.FileDataError, pymupdf.EmptyFileError, RuntimeError, ValueError) as exc:
            raise PdfError(f"Cannot open PDF: {exc}") from exc
        with doc:
            if doc.needs_pass:
                raise PdfError("The PDF is password protected")
            pages: list[PageText] = []
            try:
                for number, page in enumerate(doc, start=1):
                    text = _page_text(page)
                    pages.append(
                        PageText(
                            page_number=number,
                            text=text,
                            char_count=len(text),
                            is_scanned=len(text) < SCANNED_THRESHOLD,
                            replacement_chars=text.count("�"),
                        )
                    )
            except (RuntimeError, ValueError) as exc:
                raise PdfError(f"Cannot read PDF page: {exc}") from exc
        return pages


def pdf_page_count(path: str | Path) -> int:
    with INGEST_LOCK:
        try:
            with pymupdf.open(str(path)) as doc:
                return doc.page_count
        except (pymupdf.FileDataError, pymupdf.EmptyFileError, RuntimeError, ValueError) as exc:
            raise PdfError(f"Cannot open PDF: {exc}") from exc
