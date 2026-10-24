from app.retrieval.rrf import rrf_fuse


def test_hand_computed_scores_and_order() -> None:
    fused = rrf_fuse([["a", "b"], ["b", "c"]], k=60)
    scores = dict(fused)
    assert abs(scores["b"] - (1 / 62 + 1 / 61)) < 1e-12
    assert abs(scores["a"] - 1 / 61) < 1e-12
    assert abs(scores["c"] - 1 / 62) < 1e-12
    assert [cid for cid, _ in fused] == ["b", "a", "c"]


def test_item_in_both_lists_beats_single_list_item() -> None:
    fused = rrf_fuse([["x", "y"], ["z", "y"]])
    assert fused[0][0] == "y"


def test_duplicates_within_a_list_count_once() -> None:
    fused = rrf_fuse([["a", "a", "b"]])
    assert [cid for cid, _ in fused] == ["a", "b"]
    assert abs(fused[0][1] - 1 / 61) < 1e-12


def test_ties_break_on_best_rank_then_id() -> None:
    fused = rrf_fuse([["b"], ["a"]])
    assert [cid for cid, _ in fused] == ["a", "b"]
    assert rrf_fuse([]) == []
