"""Print the text the app extracts from one or more PDFs, page by page.

Usage: uv run scripts/dump_pages.py ../sample-pdfs/*.pdf [--find "needle"]
With --find, only pages containing the needle (case-insensitive, whitespace-folded) are listed.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingest.pdf import extract_pages  # noqa: E402


def fold(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).casefold().strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="+")
    parser.add_argument("--find", default=None, help="only list pages containing this text")
    args = parser.parse_args(argv)
    needle = fold(args.find) if args.find else None
    for pdf in args.pdfs:
        for page in extract_pages(pdf):
            if needle is not None:
                if needle in fold(page.text):
                    print(f"{Path(pdf).name} | page {page.page_number}: found")
                continue
            print(
                f"===== {Path(pdf).name} | page {page.page_number} | {page.char_count} chars ====="
            )
            print(page.text)
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
