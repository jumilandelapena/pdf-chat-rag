from app.llm.citations import citation_dict, map_citations, utf16_len
from app.llm.provider import ChunkRef, FinalTextBlock, RawCitation

A = ChunkRef("docA:00000", "docA", "a.pdf", 1, 0, 0, "alpha text")
B = ChunkRef("docB:00003", "docB", "b.pdf", 7, 3, 100, "beta text quoted text here")
FIELDS = {
    "n",
    "document_id",
    "filename",
    "page",
    "quote",
    "text_start",
    "text_end",
    "chunk_id",
    "page_char_start",
    "page_char_end",
}


def test_mapping_numbering_offsets_and_raw_quote() -> None:
    blocks = [
        FinalTextBlock("Hello \U0001f600 "),
        FinalTextBlock("cited", [RawCitation(1, "quoted text ", 10, 22)]),
        FinalTextBlock(" and again ", []),
        FinalTextBlock(
            "twice",
            [RawCitation(1, "quoted text", 10, 21), RawCitation(0, "alpha", 0, 5)],
        ),
    ]
    text, cites = map_citations(blocks, [A, B])
    assert text == "Hello \U0001f600 cited and again twice"
    assert utf16_len("Hello \U0001f600 ") == 9
    assert [c.n for c in cites] == [1, 1, 2]
    first = cites[0]
    assert (first.document_id, first.filename, first.page) == ("docB", "b.pdf", 7)
    assert first.chunk_id == "docB:00003"
    assert first.quote == "quoted text "
    assert (first.text_start, first.text_end) == (9, 14)
    assert (first.page_char_start, first.page_char_end) == (110, 122)
    assert (cites[1].text_start, cites[1].text_end) == (25, 30)
    assert cites[2].document_id == "docA" and cites[2].page == 1
    assert set(citation_dict(first)) == FIELDS


def test_out_of_range_index_is_skipped() -> None:
    blocks = [FinalTextBlock("x", [RawCitation(5, "q", 0, 1), RawCitation(-1, "q", 0, 1)])]
    text, cites = map_citations(blocks, [A])
    assert text == "x" and cites == []
