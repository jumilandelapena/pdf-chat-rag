"""Verify that every golden anchor appears on exactly the expected pages.

Usage: uv run evals/check_golden.py [--golden evals/golden.jsonl] [--samples ../sample-pdfs]
Exit status 1 when any anchor is missing or found on an unexpected page.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingest.pdf import extract_pages  # noqa: E402

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_GOLDEN = EVALS_DIR / "golden.jsonl"
DEFAULT_SAMPLES = EVALS_DIR.parents[1] / "sample-pdfs"


def fold(text: str) -> str:
    """NFKC, straight quotes, single spaces, casefold: the comparison form for anchors."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[‘’‚‛]", "'", text)
    text = re.sub(r"[“”„‟]", '"', text)
    return re.sub(r"\s+", " ", text).casefold().strip()


@dataclass(frozen=True)
class AnchorResult:
    row_id: str
    file: str
    anchor: str
    expected_pages: tuple[int, ...]
    found_pages: tuple[int, ...]

    @property
    def ok(self) -> bool:
        return bool(self.found_pages) and set(self.found_pages) <= set(self.expected_pages)


def load_golden(path: Path = DEFAULT_GOLDEN) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def check(
    golden_path: Path = DEFAULT_GOLDEN, samples_dir: Path = DEFAULT_SAMPLES
) -> list[AnchorResult]:
    rows = load_golden(golden_path)
    folded_pages: dict[str, dict[int, str]] = {}
    results: list[AnchorResult] = []
    for row in rows:
        name = row["file"]
        if name not in folded_pages:
            folded_pages[name] = {
                p.page_number: fold(p.text) for p in extract_pages(samples_dir / name)
            }
        checks = [(row["anchors"], row["expected_pages"])]
        follow_up = row.get("follow_up")
        if follow_up and follow_up.get("anchors"):
            checks.append((follow_up["anchors"], follow_up["expected_pages"]))
        for anchors, expected in checks:
            for anchor in anchors:
                needle = fold(anchor)
                found = tuple(n for n, text in folded_pages[name].items() if needle in text)
                results.append(AnchorResult(row["id"], name, anchor, tuple(expected), found))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES)
    args = parser.parse_args(argv)
    results = check(args.golden, args.samples)
    failures = 0
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        failures += not r.ok
        print(
            f"{status} {r.row_id:8} expected {list(r.expected_pages)} found {list(r.found_pages)}  {r.anchor[:60]!r}"
        )
    print(f"{len(results)} anchors, {failures} failing")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
