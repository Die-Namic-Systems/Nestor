"""Token bench matchers use the score() seam."""

from __future__ import annotations

from bench.token_matchers import TokenJaccard, TokenOverlap
from nestor import memory
from nestor.matcher import match_similarity


def test_jaccard_and_overlap_score_differ():
    j, o = TokenJaccard(), TokenOverlap()
    raw_a, raw_b = "the sensitivity ladder", "sensitivity"
    assert j.score(raw_a, raw_b) != o.score(raw_a, raw_b)


def test_best_match_uses_score_for_token_matchers():
    from bench.bench_accuracy import best_match

    rows = [{
        "source_text": "Amazon Web Services",
        "source_norm": "amazon services web",
        "target_text": "aws",
        "id": "1",
    }]
    probe = "AWS cloud"
    j = TokenJaccard()
    sim_via_best = best_match(probe, rows, j)[0]
    assert sim_via_best == round(j.score(probe, rows[0]["source_text"]), 3)


def test_norm_only_similarity_can_differ_from_score():
    """``best_match`` uses ``score``; comparing norms alone is not the same path."""
    j = TokenJaccard()
    probe = "Amazon Web Services"
    stored_norm = "amazon web"  # stale or partial norm key
    norm_only = j.similarity(j.normalize(probe), stored_norm)
    via_score = j.score(probe, "Amazon Web Services")
    assert round(norm_only, 3) != round(via_score, 3)


def test_match_similarity_prefers_score_on_token_matcher():
    j = TokenJaccard()
    assert match_similarity(
        j, "foo bar", j.normalize("foo bar"),
        "bar foo", j.normalize("bar foo"),
    ) == j.score("foo bar", "bar foo")


def test_best_sealed_agrees_with_bench_best_match_token_overlap(store):
    """bench_accuracy and memory.best_sealed must not drift on token matchers."""
    from bench.bench_accuracy import best_match

    m = TokenOverlap()
    memory.add_pair("Amazon Web Services", "TARGET_AWS", "en", "es",
                    status="sealed", verifier="rita", store=store, matcher=m)
    memory.add_pair("the sensitivity ladder", "TARGET_SENS", "en", "es",
                    status="sealed", verifier="rita", store=store, matcher=m)
    rows = store.memory_candidates("en", "es")

    for probe in ("amazon web services", "the sensitivity ladder", "sensitivity"):
        hit = memory.best_sealed(
            probe, "en", "es", store=store, matcher=m,
            seal_threshold=0.0, context_threshold=0.0,
        )
        bench_sim, bench_tgt, _ = best_match(probe, rows, m)
        assert hit is not None, probe
        assert hit["similarity"] == bench_sim, probe
        assert hit["pair"]["target_text"] == bench_tgt, probe
