from app.retrieval.bm25 import BM25Registry, tokenize


def _registry() -> BM25Registry:
    registry = BM25Registry()
    registry.set_document(
        "d1",
        ["d1:00000", "d1:00001"],
        ["The teapot brews coffee for everyone.", "The crawler transporter carries rockets."],
    )
    registry.set_document("d2", ["d2:00000"], ["Coffee pots and more coffee pots."])
    return registry


def test_tokenize_lowercases_and_drops_single_chars() -> None:
    assert tokenize("A Teapot, 418 I'm.") == ["teapot", "418"]


def test_rare_term_ranks_first_and_scope_is_respected() -> None:
    registry = _registry()
    hits = registry.search(["d1", "d2"], "teapot", 5)
    assert hits[0][0] == "d1:00000" and hits[0][1] > 0
    assert registry.search(["d1"], "pots", 5) == []
    assert [cid for cid, _ in registry.search(["d2"], "coffee", 5)] == ["d2:00000"]


def test_empty_query_scope_or_unknown_document() -> None:
    registry = _registry()
    assert registry.search(["d1"], "", 5) == []
    assert registry.search([], "coffee", 5) == []
    assert registry.search(["nope"], "coffee", 5) == []
    assert registry.search(["d1"], "zebra", 5) == []


def test_changes_invalidate_cached_scope_index() -> None:
    registry = _registry()
    assert len(registry.search(["d1", "d2"], "coffee", 5)) == 2
    registry.remove_document("d2")
    assert [cid for cid, _ in registry.search(["d1", "d2"], "coffee", 5)] == ["d1:00000"]
    registry.set_document("d1", ["d1:00000"], ["Nothing relevant at all."])
    assert registry.search(["d1", "d2"], "coffee", 5) == []
    assert not registry.has_document("d2") and registry.has_document("d1")
