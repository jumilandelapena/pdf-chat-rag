from pathlib import Path

import pymupdf
import pytest

from app.errors import PdfError
from app.ingest.pdf import extract_pages, join_blocks, norm_block


def test_extracts_pages_and_flags_blank_page(tiny_pdf: Path) -> None:
    pages = extract_pages(tiny_pdf)
    assert [p.page_number for p in pages] == [1, 2, 3]
    assert "six million pounds" in pages[0].text
    assert "­" not in pages[1].text
    assert "https://example.com/a" in pages[1].text and pages[1].text.count("a") >= 290
    assert pages[2].is_scanned and pages[2].char_count == 0
    assert not pages[0].is_scanned


def test_norm_block_expands_ligatures_and_drops_soft_hyphens() -> None:
    assert norm_block("ﬁne­  \r\ntext\t x  ") == "fine\ntext  x"
    assert norm_block("  \n\n  ") == ""


def test_join_rule_blank_line_only_around_multi_line_blocks() -> None:
    assert join_blocks(["a", "b"]) == "a\nb"
    assert join_blocks(["a\nb", "c"]) == "a\nb\n\nc"
    assert join_blocks(["a", "b\nc", "d"]) == "a\n\nb\nc\n\nd"
    assert join_blocks([]) == ""


def test_password_protected_pdf_raises(tmp_path: Path) -> None:
    path = tmp_path / "locked.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "secret")
    doc.save(str(path), encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="own")
    doc.close()
    with pytest.raises(PdfError, match="password"):
        extract_pages(path)


def test_corrupt_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.4 this is not really a pdf")
    with pytest.raises(PdfError):
        extract_pages(path)


def test_sample_rfc(sample_pdf: Path) -> None:
    pages = extract_pages(sample_pdf)
    assert len(pages) == 10
    assert "418" in pages[4].text
    assert all(p.replacement_chars == 0 for p in pages)
