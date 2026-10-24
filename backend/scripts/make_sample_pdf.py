"""Render a Project Gutenberg plain-text book as a clean PDF sample.

Usage:
  uv run scripts/make_sample_pdf.py scripts/.cache/pg1952.txt ../sample-pdfs/the-yellow-wallpaper.pdf --check

The Gutenberg header, footer and licence are stripped so the sample is the public-domain text
itself and not a Project Gutenberg distribution. --check re-extracts the PDF with the app's own
extractor and prints the page of each golden anchor.
"""

from __future__ import annotations

import argparse
import html
import io
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingest.pdf import extract_pages  # noqa: E402
from app.locks import INGEST_LOCK  # noqa: E402

TITLE = "The Yellow Wallpaper"
AUTHOR = "Charlotte Perkins Gilman"
START_RE = re.compile(r"^\*\*\* START OF THE PROJECT GUTENBERG EBOOK.*$", re.M)
END_RE = re.compile(r"^\*\*\* END OF THE PROJECT GUTENBERG EBOOK.*$", re.M)
ANCHORS = [
    "John is a physician",
    "phosphates or phosphites",
    "three miles from the village",
    "nursery, at the top of the house",
    "Mary is so good with the baby",
    "Weir Mitchell",
]
CSS = """
body { font-family: sans-serif; font-size: 11pt; line-height: 1.45; }
h1 { font-size: 22pt; margin: 0 0 4pt 0; }
p.by { font-size: 12pt; margin: 0 0 18pt 0; }
p { margin: 0 0 9pt 0; text-align: left; }
"""
MAX_PAGES = 200


def body_paragraphs(raw: str) -> list[str]:
    text = raw.replace("\r\n", "\n")
    start = START_RE.search(text)
    end = END_RE.search(text)
    if not start or not end:
        raise SystemExit("Gutenberg START/END markers not found")
    body = text[start.end() : end.start()]
    body = re.sub(r"_(.+?)_", r"\1", body, flags=re.S)  # drop italic markers
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", body)]
    paragraphs = [p for p in paragraphs if p]
    # the first two paragraphs are the title and the by-line of the Gutenberg text
    if paragraphs[:2] == [TITLE, f"By {AUTHOR}"]:
        paragraphs = paragraphs[2:]
    bad = [p for p in paragraphs if "gutenberg" in p.lower()]
    if bad:
        raise SystemExit(f"Gutenberg reference survived stripping: {bad[0][:80]}")
    return paragraphs


def build_html(paragraphs: list[str]) -> str:
    parts = [f"<h1>{html.escape(TITLE)}</h1>", f'<p class="by">By {html.escape(AUTHOR)}</p>']
    parts += [f"<p>{html.escape(p)}</p>" for p in paragraphs]
    return "<html><body>" + "".join(parts) + "</body></html>"


def render(paragraphs: list[str], out: Path) -> int:
    page_rect = pymupdf.paper_rect("a4")
    where = page_rect + (56, 60, -56, -64)
    with INGEST_LOCK:
        story = pymupdf.Story(html=build_html(paragraphs), user_css=CSS)
        buffer = io.BytesIO()
        writer = pymupdf.DocumentWriter(buffer)
        pages = 0
        more = True
        while more:
            if pages >= MAX_PAGES:
                raise SystemExit("layout did not finish within 200 pages")
            device = writer.begin_page(page_rect)
            more, _ = story.place(where)
            story.draw(device)
            writer.end_page()
            pages += 1
        writer.close()
        with pymupdf.open(stream=buffer.getvalue(), filetype="pdf") as doc:
            doc.set_metadata(
                {
                    "title": TITLE,
                    "author": AUTHOR,
                    "subject": "Short story (1892), public domain",
                    "creator": "pdf-chat-rag sample generator",
                    "producer": "PyMuPDF",
                    "creationDate": "D:20260101000000Z",
                    "modDate": "D:20260101000000Z",
                }
            )
            doc.save(str(out), garbage=4, deflate=True)
    return pages


def fold(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).casefold()


def check(out: Path) -> int:
    pages = extract_pages(out)
    failures = 0
    for page in pages:
        if "gutenberg" in page.text.lower():
            print(f"FAIL: 'gutenberg' found on page {page.page_number}")
            failures += 1
    for anchor in ANCHORS:
        hits = [p.page_number for p in pages if fold(anchor) in fold(p.text)]
        print(f"{anchor!r} -> pages {hits}")
        if not hits:
            failures += 1
    print(f"{len(pages)} pages, {sum(p.char_count for p in pages)} characters")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    paragraphs = body_paragraphs(Path(args.source).read_text(encoding="utf-8"))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    pages = render(paragraphs, out)
    print(f"wrote {out} ({pages} pages, {out.stat().st_size} bytes)")
    if args.check:
        return 1 if check(out) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
