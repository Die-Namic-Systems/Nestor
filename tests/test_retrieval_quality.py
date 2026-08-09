"""bench/retrieval_quality.py — the recall half, and that it does not
reimplement the collision half.

Three claims, each checked by running the tool rather than by describing it:

* the verbatim floor is 100% on a corpus sealed under this run (a miss would
  mean serving itself is broken);
* shortening the query lowers recall relative to that floor (the entire point
  of measuring "asked the gist" separately from "asked verbatim");
* the collision numbers this tool reports are `nestor.calibrate.calibrate`'s
  own numbers on the same sealed store — checked two ways, so agreement is not
  a coincidence of both sides computing the same thing independently: a spy
  proves the function is actually called, and a byte-for-byte comparison
  against calling `calibrate.calibrate` directly on an identically-built store
  proves the numbers are not a second, drifted implementation.
"""
from __future__ import annotations

from bench import retrieval_quality as rq
from nestor import calibrate as calibrate_mod
from nestor.matcher import StringMatcher


def test_verbatim_floor_is_100_percent(tmp_path, seal_key):
    rows = rq.demo_corpus()
    result = rq.measure(rows, "demo", "demo", StringMatcher(),
                        keep=tmp_path / "floor")
    floor = result["verbatim_floor"]
    assert floor["n"] == len(rows)
    assert floor["served"] == len(rows), (
        "every row, queried in the exact words it was sealed under, must "
        "serve back its own answer — a miss here means serving is broken")
    assert floor["wrong"] == 0 and floor["pending"] == 0
    assert floor["rate"] == 1.0


def test_compression_lowers_recall_below_the_floor(tmp_path, seal_key):
    rows = rq.demo_corpus()
    result = rq.measure(rows, "demo", "demo", StringMatcher(),
                        compression="first-sentence", keep=tmp_path / "recall")
    floor = result["verbatim_floor"]
    recall = result["recall_under_compression"]

    assert recall["n"] > 0, (
        "the demo corpus must contain multi-sentence rows or this measures "
        "nothing — a compression sweep with n=0 is a broken fixture, not a "
        "clean result")
    assert recall["served"] < recall["n"], (
        "shortening the query must cost at least one serve, or the "
        "compression was not actually mechanical (too gentle to matter)")
    assert recall["served"] < floor["served"], (
        "recall under compression must be strictly worse than the verbatim "
        "floor — that gap is the entire thing this half of the tool measures")
    assert recall["wrong"] == 0, (
        "on this corpus compression should degrade toward pending, never "
        "toward serving the WRONG row as verified")


def test_compression_by_chars_also_degrades(tmp_path, seal_key):
    rows = rq.demo_corpus()
    result = rq.measure(rows, "demo", "demo", StringMatcher(),
                        compression="chars", chars=25, keep=tmp_path / "chars")
    recall = result["recall_under_compression"]
    assert recall["compression"] == "chars" and recall["chars"] == 25
    assert recall["n"] == len(rows), "every row is longer than 25 characters"
    assert recall["served"] < result["verbatim_floor"]["served"]


def test_a_noop_compression_is_skipped_not_miscounted(tmp_path, seal_key):
    """A cutoff longer than every source is a no-op: nothing should be queried,
    and the tool must say so via ``skipped`` rather than reporting a hollow
    100% recall over zero real probes."""
    rows = rq.demo_corpus()
    longest = max(len(r["source_text"]) for r in rows)
    result = rq.measure(rows, "demo", "demo", StringMatcher(),
                        compression="chars", chars=longest + 50,
                        keep=tmp_path / "noop")
    recall = result["recall_under_compression"]
    assert recall["n"] == 0
    assert recall["skipped"] == len(rows)
    assert recall["rate"] is None
    assert "nothing measured" in rq.summarize(result)


def test_collisions_are_calibrates_own_numbers_not_a_reimplementation(tmp_path, seal_key):
    rows = rq.demo_corpus()
    matcher = StringMatcher()

    result = rq.measure(rows, "demo", "demo", matcher,
                        calibrate_kwargs={"sample": 0},
                        keep=tmp_path / "via-measure")

    # Build an identically-sealed store by hand and call calibrate directly —
    # if retrieval_quality.py hand-rolled its own collision scan, this would
    # not need to match it exactly.
    reference_store = rq.seal_corpus(tmp_path / "reference", rows, "demo",
                                     "demo", matcher)
    try:
        reference = calibrate_mod.calibrate(reference_store, "demo", "demo",
                                            matcher=matcher, sample=0)
    finally:
        reference_store.close()

    def without_ids(examples):
        # ``id`` is a fresh UUID per seal_corpus() call (two independently
        # sealed stores, same content) — everything else must match exactly.
        return [{k: v for k, v in ex.items() if k != "id"} for ex in examples]

    assert result["collisions"]["sweep"] == reference["sweep"]
    assert without_ids(result["collisions"]["examples"]) == without_ids(reference["examples"])
    assert result["collisions"]["recommended"] == reference["recommended"]
    # calibrate's own numbers on this corpus are not vacuous — the demo
    # corpus deliberately holds a near-identical, differently-answered pair.
    assert result["collisions"]["current_rate"] > 0 or any(
        row["collisions"] > 0 for row in result["collisions"]["sweep"])


def test_measure_actually_calls_calibrate_calibrate(monkeypatch, tmp_path, seal_key):
    """A byte-for-byte match (above) could in principle happen by coincidence
    of two matching implementations. This proves the call itself happens."""
    calls = []
    original = calibrate_mod.calibrate

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(rq.calibrate, "calibrate", spy)
    rows = rq.demo_corpus()
    rq.measure(rows, "demo", "demo", StringMatcher(), keep=tmp_path / "spy")
    assert len(calls) == 1, "measure() must delegate to calibrate.calibrate exactly once"


def test_summarize_carries_calibrates_own_sentence(tmp_path, seal_key):
    """The collision section of the summary is calibrate.summarize()'s text,
    not a paraphrase of it — checked by looking for a sentence only that
    function writes."""
    rows = rq.demo_corpus()
    result = rq.measure(rows, "demo", "demo", StringMatcher(),
                        keep=tmp_path / "summary")
    assert ("This is a lower bound: it can only see collisions already in "
           "the memory." in rq.summarize(result))


def test_load_corpus_from_store_never_opens_the_original_for_write(tmp_path, seal_key):
    """The store passed to --store is copied before it is ever opened, so
    ``load_corpus_from_store`` cannot write to the caller's file."""
    source_root = tmp_path / "source"
    rows = [{"source_text": "the invoice is overdue",
            "target_text": "la factura esta vencida"}]
    store = rq.seal_corpus(source_root, rows, "en", "es", StringMatcher())
    store.close()
    db_path = source_root / "nestor.db"
    before = db_path.read_bytes()

    loaded = rq.load_corpus_from_store(db_path, "en", "es", work=tmp_path / "load")
    assert loaded == rows
    assert db_path.read_bytes() == before, "the original store must be unchanged"


def test_build_matcher_resolves_the_two_named_matchers():
    from recipes import patch_review

    assert isinstance(rq.build_matcher("string"), StringMatcher)
    assert rq.build_matcher("defect") is patch_review.MATCHER


def test_the_demo_cli_runs_clean(capsys, seal_key):
    assert rq.main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "verbatim floor" in out
    assert "collisions at the seal bar" in out


def test_the_cli_refuses_with_neither_store_nor_demo(capsys, seal_key):
    try:
        rq.main([])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("argparse should have exited on missing --store/--demo")
