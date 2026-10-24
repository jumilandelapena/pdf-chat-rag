from pathlib import Path

from app.ingest.chunker import chunk_document, chunk_page, sub_windows
from app.ingest.pdf import extract_pages
from app.ingest.tokens import count_tokens
from tests.conftest import SAMPLE_PDFS

TARGET, OVERLAP_TOKENS, MAX_CHARS = 800, 120, 4800


def _check_invariants(page_text: str, chunks) -> None:
    for chunk in chunks:
        assert chunk.text == page_text[chunk.char_start : chunk.char_end]
        assert chunk.text == chunk.text.strip()
        assert count_tokens(chunk.text) <= TARGET
        assert chunk.token_count == count_tokens(chunk.text)
        assert len(chunk.text) <= MAX_CHARS


def test_real_pages_respect_limits_offsets_and_overlap() -> None:
    for name in ("rfc2324-htcpcp.pdf", "the-yellow-wallpaper.pdf", "nasa-crawler-transporters.pdf"):
        pages = extract_pages(SAMPLE_PDFS / name)
        chunks = chunk_document([(p.page_number, p.text) for p in pages])
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
        texts = {p.page_number: p.text for p in pages}
        for page_number, page_text in texts.items():
            page_chunks = [c for c in chunks if c.page_number == page_number]
            _check_invariants(page_text, page_chunks)
            for prev, nxt in zip(page_chunks, page_chunks[1:], strict=False):
                assert nxt.char_start > prev.char_start and nxt.char_end > prev.char_end
                overlap = page_text[nxt.char_start : prev.char_end]
                assert count_tokens(overlap) <= OVERLAP_TOKENS + 80
            if page_text.strip():
                assert page_chunks and page_chunks[0].char_start <= page_text.index(
                    page_text.strip()[0]
                )


def test_never_crosses_pages_and_indexes_sequentially() -> None:
    pages = [(1, "First page sentence one. Sentence two."), (2, ""), (3, "Third page text here.")]
    chunks = chunk_document(pages)
    assert [(c.page_number, c.chunk_index) for c in chunks] == [(1, 0), (3, 1)]


def test_empty_page_yields_nothing() -> None:
    assert chunk_page("   \n\n  ", 1) == []


def test_giant_unpunctuated_paragraph_is_split_and_fully_covered() -> None:
    text = " ".join(f"word{i}" for i in range(6000))
    chunks = chunk_page(text, 1)
    assert len(chunks) > 3
    _check_invariants(text, chunks)
    covered = set()
    for c in chunks:
        covered.update(range(c.char_start, c.char_end))
    assert all(i in covered for i, ch in enumerate(text) if not ch.isspace())


def test_unknown_token_run_is_bounded_by_characters() -> None:
    text = "a" * 5000
    chunks = chunk_page(text, 1)
    assert len(chunks) == 2
    _check_invariants(text, chunks)
    assert "".join(c.text for c in chunks) == text


def test_long_url_stays_inside_one_chunk() -> None:
    url = "https://example.com/" + "x" * 280
    text = "See the link " + url + " for details. " + "More text follows here. " * 50
    chunks = chunk_page(text, 1)
    assert any(url in c.text for c in chunks)
    _check_invariants(text, chunks)


def test_exactly_target_tokens_is_one_chunk() -> None:
    text = " ".join(["alpha"] * TARGET)
    assert count_tokens(text) == TARGET
    assert len(chunk_page(text, 1)) == 1
    assert len(chunk_page(text + " alpha", 1)) == 2


def test_tiny_tail_is_merged_into_previous_chunk() -> None:
    body = " ".join(f"Sentence number {i} is here." for i in range(130))
    text = body + " End."
    chunks = chunk_page(text, 1)
    assert chunks[-1].text.endswith("End.")
    assert count_tokens(chunks[-1].text) > 0.1 * TARGET


def test_sub_windows_cover_text_within_limit() -> None:
    text = " ".join(f"Short sentence number {i}." for i in range(400))
    assert count_tokens(text) > 1500
    windows = sub_windows(text, 480, MAX_CHARS)
    assert len(windows) >= 3
    assert all(count_tokens(w) <= 480 for w in windows)
    assert "".join(windows).replace(" ", "") == text.replace(" ", "")
    assert sub_windows("tiny", 480, MAX_CHARS) == ["tiny"]
    assert sub_windows("", 480, MAX_CHARS) == [""]


def test_offsets_invariant_on_tiny_pdf(tiny_pdf: Path) -> None:
    pages = extract_pages(tiny_pdf)
    chunks = chunk_document([(p.page_number, p.text) for p in pages])
    assert {c.page_number for c in chunks} == {1, 2}
    for c in chunks:
        assert c.text == pages[c.page_number - 1].text[c.char_start : c.char_end]
