"""The supersession/refutation pass — the conflict_scan payoff.

Both classifications are pinned in the two directions that matter: a same-question
duplicate becomes a ``supersedes`` pointing later->earlier, and a same-question /
opposite-answer pair becomes a ``contradicts`` (the finding a "what resembles"
pass would miss). Unrelated questions yield nothing, the output is deterministic,
and every emitted kind is a real decision-graph kind. Written during the audit —
the builder produced the module but not this test.
"""
from __future__ import annotations

import pytest

from nestor.matcher import StringMatcher
from nestor.triage import EDGE_KINDS, Decision, ProposedEdge
from nestor.triage.supersede import find_supersessions

BAR = 0.55
M = StringMatcher()


def _d(id_: str, q: str, c: str) -> Decision:
    return Decision(id=id_, file=id_.split("#")[0] + ".json",
                    question=q, commitment=c, why="", consolidated_onto=None)


def test_same_question_same_commitment_is_a_supersedes_later_over_earlier():
    ds = [_d("0001#0", "Should the gate fail closed on error?", "Yes, it fails closed."),
          _d("0002#0", "Should the gate fail closed on error?", "Yes, it fails closed.")]
    edges = find_supersessions(ds, M, BAR)
    assert len(edges) == 1
    e = edges[0]
    assert e.kind == "supersedes"
    assert (e.src_id, e.dst_id) == ("0002#0", "0001#0")   # later supersedes earlier


def test_same_question_opposite_commitment_is_a_contradicts():
    ds = [_d("0003#0", "Should the store seal a row on its own?", "yes always automatically"),
          _d("0004#0", "Should the store seal a row on its own?", "never no human required")]
    edges = find_supersessions(ds, M, BAR)
    assert len(edges) == 1
    assert edges[0].kind == "contradicts"


def test_unrelated_questions_yield_no_edge():
    ds = [_d("0005#0", "What colour is the provenance card?", "forest green"),
          _d("0006#0", "How many benches run in CI?", "five of them")]
    assert find_supersessions(ds, M, BAR) == []


def test_deterministic_and_kinds_are_graph_kinds():
    ds = [_d("0001#0", "Should the gate fail closed on error?", "yes it fails closed"),
          _d("0002#0", "Should the gate fail closed on error?", "yes it fails closed"),
          _d("0003#0", "Should the store seal a row on its own?", "yes always automatically"),
          _d("0004#0", "Should the store seal a row on its own?", "never no human required")]
    first = find_supersessions(ds, M, BAR)
    assert first == find_supersessions(ds, M, BAR)          # same in, same out
    assert all(isinstance(e, ProposedEdge) for e in first)
    assert all(e.kind in EDGE_KINDS for e in first)
    assert first == sorted(first, key=lambda e: (e.src_id, e.dst_id))


def test_moderate_question_match_with_divergent_commitments_is_not_a_contradiction():
    """Structural skeleton overlap ("Should the X?" / "Should the Y?") scores
    0.55–0.65 on difflib. With divergent commitments that was a "contradicts" —
    mostly false positives. The contradict uplift (bar + 0.15 = 0.70) filters
    them: a genuine contradiction needs stronger question evidence."""
    # These share the skeleton "Should the <noun> <verb> on <noun>?" but
    # the actual content differs. difflib scores ~0.65.
    ds = [_d("0007#0", "Should the gate fail open on timeout?",
             "yes always automatically"),
          _d("0008#0", "Should the cache warm up on startup?",
             "never no resources needed")]
    sim = M.similarity(M.normalize(ds[0].question), M.normalize(ds[1].question))
    assert BAR <= sim < BAR + 0.15, f"sim={sim:.3f} should be in the skeleton zone"
    edges = find_supersessions(ds, M, BAR)
    assert edges == [], f"skeleton overlap should not produce a contradiction: {edges}"


def test_score_is_used_when_matcher_exposes_it():
    """A matcher with score() should use it for both question and commitment
    comparison, allowing richer signals (embeddings, token-sort) to drive the
    classification."""
    class _ScoringMatcher:
        def normalize(self, v):
            return " ".join(str(v).lower().split())
        def similarity(self, a, b):
            return 0.0  # deliberately low — should not be used
        def score(self, a, b):
            if {"apples", "oranges"} <= {a.lower(), b.lower()}:
                return 0.0  # unrelated
            return 0.95

    ds = [_d("0009#0", "Alpha question", "Yes do it"),
          _d("0010#0", "Beta question", "Yes do it")]
    # similarity() returns 0.0, but score() returns 0.95 — the edge should
    # exist (supersedes, since commitments also score 0.95).
    edges = find_supersessions(ds, _ScoringMatcher(), 0.55)
    assert len(edges) == 1
    assert edges[0].kind == "supersedes"


@pytest.mark.slow
def test_smoke_over_the_real_corpus_at_the_knee():
    from nestor.triage import load_decisions
    from tests.conftest import DOGFOOD_SMOKE_DECISIONS

    edges = find_supersessions(load_decisions(DOGFOOD_SMOKE_DECISIONS), M, BAR)
    # deterministic, every kind valid, and no self-edges
    assert all(e.kind in EDGE_KINDS and e.src_id != e.dst_id for e in edges)
    assert edges == find_supersessions(load_decisions(DOGFOOD_SMOKE_DECISIONS), M, BAR)
