from collections import Counter

from evals.check_golden import DEFAULT_SAMPLES, check, load_golden


def test_golden_set_shape() -> None:
    rows = load_golden()
    assert len(rows) == 20
    assert len({r["id"] for r in rows}) == 20
    assert Counter(r["file"] for r in rows) == {
        "nasa-crawler-transporters.pdf": 7,
        "rfc2324-htcpcp.pdf": 7,
        "the-yellow-wallpaper.pdf": 6,
    }
    for row in rows:
        assert (DEFAULT_SAMPLES / row["file"]).is_file()
        assert row["question"] and row["reference_answer"] and row["anchors"]
        assert row["expected_pages"] and all(isinstance(p, int) for p in row["expected_pages"])
    assert sum(1 for r in rows if r.get("follow_up")) == 3


def test_every_anchor_is_on_the_expected_pages() -> None:
    results = check()
    failing = [r for r in results if not r.ok]
    assert not failing, [(r.row_id, r.anchor, r.found_pages) for r in failing]
