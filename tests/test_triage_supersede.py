"""The supersession/refutation pass — the conflict_scan payoff.

Both classifications are pinned in the two directions that matter: a same-question
duplicate becomes a ``supersedes`` pointing later->earlier, and a same-question /
opposite-answer pair becomes a ``contradicts`` (the finding a "what resembles"
pass would miss). Unrelated questions yield nothing, the output is deterministic,
and every emitted kind is a real decision-graph kind. Written during the audit —
the builder produced the module but not this test.
"""
from __future__ import annotations

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


def test_smoke_over_the_real_corpus_at_the_knee():
    from nestor.triage import load_decisions
    edges = find_supersessions(load_decisions(), M, BAR)
    # deterministic, every kind valid, and no self-edges
    assert all(e.kind in EDGE_KINDS and e.src_id != e.dst_id for e in edges)
    assert edges == find_supersessions(load_decisions(), M, BAR)
