"""cluster.group — the grouping is a mechanism, so every claim has a test that
can go red.

The four things proved here are the four the contract names: near-duplicates
land together while unrelated questions stay apart ({3},{1},{1}); the pass is
deterministic (same input twice, identical output); the bar is the N1 knee — a
re-worded pair joins at 0.45 and splits at 0.92; and on the real 316-decision
queue every decision lands in exactly one cluster, quickly. Each of the first
three fails if the graph cut is broken in the direction it guards.
"""
from __future__ import annotations

import os
import sys
import time

import pytest

from nestor.matcher import StringMatcher
from nestor.triage import Decision, load_decisions
from nestor.triage.cluster import group


def _timing_distorted() -> bool:
    """Whether tracing or parallel contention invalidates wall-clock now.

    Coverage detection is by its own ``Coverage.current()`` API, which is robust
    across coverage's Python, C, and ``sys.monitoring`` tracers — ``sys.gettrace``
    alone returns ``None`` under the C tracer, so it is only a fallback. When
    coverage is not installed at all (the local ``.venv``), neither fires and the
    timing assertion runs as before. An xdist worker also shares finite CPU with
    other workers, so elapsed time there measures scheduling rather than this
    function; the dedicated ``performance`` lane runs serially.
    """
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return True
    if sys.gettrace() is not None:
        return True
    cov = sys.modules.get("coverage")
    if cov is not None:
        try:
            return cov.Coverage.current() is not None
        except Exception:                     # noqa: BLE001 — present but API shifted: assume so
            return True
    return False


def _mk(idx: int, question: str) -> Decision:
    return Decision(id=f"{idx:04d}#0", file="t.json", question=question,
                    commitment="c", why="w", consolidated_onto=None)


# Three near-duplicate questions (~0.9 to each other) and two unrelated ones
# (~0.4 at most to anything). At bar=0.6 the trio is one clique and the other
# two are islands.
_TRIO = [
    "How is the deny rule enforced by the harness?",
    "How is the deny rule enforced in the harness?",
    "How is the deny rule enforced by our harness?",
]
_UNRELATED = [
    "What color should the submit button be on mobile?",
    "When does the fiscal reporting year begin exactly?",
]


def _fixture() -> list[Decision]:
    qs = _TRIO + _UNRELATED
    return [_mk(i, q) for i, q in enumerate(qs)]


def test_an_xdist_worker_does_not_claim_a_wall_clock_measurement(monkeypatch):
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
    assert _timing_distorted() is True


def test_three_near_dupes_one_cluster_two_singletons():
    clusters = group(_fixture(), StringMatcher(), 0.6)
    sizes = sorted(len(c.member_ids) for c in clusters)
    assert sizes == [1, 1, 3]

    # The size-3 cluster is exactly the trio (ids 0000#0..0002#0), and each
    # unrelated question is alone.
    by_size = sorted(clusters, key=lambda c: -len(c.member_ids))
    assert set(by_size[0].member_ids) == {"0000#0", "0001#0", "0002#0"}
    singleton_ids = {c.member_ids[0] for c in by_size[1:]}
    assert singleton_ids == {"0003#0", "0004#0"}

    # Every decision appears in exactly one cluster.
    seen = [mid for c in clusters for mid in c.member_ids]
    assert sorted(seen) == ["0000#0", "0001#0", "0002#0", "0003#0", "0004#0"]


def test_representative_and_label_are_shaped():
    clusters = group(_fixture(), StringMatcher(), 0.6)
    trio = max(clusters, key=lambda c: len(c.member_ids))
    # Representative is a real member.
    assert trio.representative_id in trio.member_ids
    # Label is drawn from the shared tokens ("deny", "rule", "enforced",
    # "harness") and drops the "how/is/the/by" stopwords.
    assert trio.label
    assert set(trio.label.split()) <= {"deny", "rule", "enforced", "harness"}


def test_deterministic_same_input_same_output():
    fx = _fixture()
    m = StringMatcher()
    a = group(fx, m, 0.6)
    b = group(fx, m, 0.6)
    assert a == b
    # And a fresh matcher / fresh decision objects give the identical result —
    # nothing rides on object identity or call order.
    c = group(_fixture(), StringMatcher(), 0.6)
    assert a == c


def test_n1_knee_reworded_pair_joins_low_splits_high():
    # Same decision, re-worded: char-similarity ~0.66 — above the 0.45 triage
    # knee, below the 0.92 seal bar. So it is one cluster for a human to judge at
    # 0.45 and two separate rows at 0.92. This is the whole reason triage keys off
    # 0.45 and not SEAL_THRESHOLD.
    pair = [
        _mk(0, "Should the deny rule be proven by attempting a Drive read?"),
        _mk(1, "Must the deny rule be verified by trying an actual read?"),
    ]
    m = StringMatcher()

    low = group(pair, m, 0.45)
    assert len(low) == 1
    assert set(low[0].member_ids) == {"0000#0", "0001#0"}

    high = group(pair, m, 0.92)
    assert len(high) == 2
    assert sorted(len(c.member_ids) for c in high) == [1, 1]


def test_singletons_are_surfaced_not_dropped():
    # Five mutually-unrelated questions at a high bar: five one-member clusters,
    # none dropped.
    qs = [
        "What color should the submit button be on mobile?",
        "When does the fiscal reporting year begin exactly?",
        "Where is the parking garage located downtown?",
        "Who signed the maintenance contract last spring?",
        "Which vendor supplies the cafeteria napkins now?",
    ]
    decs = [_mk(i, q) for i, q in enumerate(qs)]
    clusters = group(decs, StringMatcher(), 0.9)
    assert len(clusters) == 5
    assert all(len(c.member_ids) == 1 for c in clusters)
    seen = sorted(mid for c in clusters for mid in c.member_ids)
    assert seen == [f"{i:04d}#0" for i in range(5)]


def test_empty_input():
    assert group([], StringMatcher(), 0.45) == []


@pytest.mark.performance
@pytest.mark.slow
def test_smoke_real_corpus_partitions_every_decision_quickly():
    decisions = load_decisions()
    assert len(decisions) > 100  # the real queue, not an empty tree

    start = time.monotonic()
    clusters = group(decisions, StringMatcher(), 0.45)
    elapsed = time.monotonic() - start
    # The clustering always runs (the partition check below needs it); the
    # *timing* claim only means something uninstrumented. CI runs the suite under
    # `coverage run`, whose tracing inflates wall-clock several-fold — this smoke
    # clocked ~69s there against a 60s bar it clears in ~19s without coverage, a
    # false red on a test whose real job is the partition invariant, growing
    # worse as the corpus grows. Measure only when not instrumented.
    if not _timing_distorted():
        assert elapsed < 60.0, f"clustering took {elapsed:.1f}s"

    # Partition: every decision in exactly one cluster, no dupes, no drops.
    all_ids = sorted(d.id for d in decisions)
    clustered = sorted(mid for c in clusters for mid in c.member_ids)
    assert clustered == all_ids

    # Every cluster is well-formed.
    for c in clusters:
        assert c.member_ids
        assert c.representative_id in c.member_ids
        assert isinstance(c.label, str)


def test_score_is_used_for_graph_edges_when_matcher_exposes_it():
    """A matcher with score() should build the similarity graph with it, not
    with similarity(). This is the fix that makes SemanticMatcher actually
    drive clustering via embeddings — before this, its internal StringMatcher's
    difflib ratio was used, ignoring the embedding signal entirely."""
    from nestor.triage import Decision
    from nestor.triage.cluster import group

    class _ScoreMatcher:
        """similarity() sees nothing alike; score() knows two questions are
        semantically identical. If _build_graph uses similarity(), these stay
        apart; if it uses score(), they cluster."""
        def normalize(self, v):
            return " ".join(str(v).lower().split())
        def similarity(self, a, b):
            return 0.0
        def score(self, a, b):
            pair = {a.lower().strip(), b.lower().strip()}
            target = {"what is the default threshold?",
                      "what should the fuzzy_bar be set to?"}
            return 0.92 if pair == target else 0.0

    ds = [Decision(id="0001#0", file="a.json",
                   question="What is the default threshold?",
                   commitment="", why="", consolidated_onto=None),
          Decision(id="0002#0", file="b.json",
                   question="What should the fuzzy_bar be set to?",
                   commitment="", why="", consolidated_onto=None),
          Decision(id="0003#0", file="c.json",
                   question="An unrelated question entirely.",
                   commitment="", why="", consolidated_onto=None)]
    clusters = group(ds, _ScoreMatcher(), bar=0.55)
    members = {tuple(sorted(c.member_ids)) for c in clusters}
    assert ("0001#0", "0002#0") in members, (
        f"score()-based paraphrase must cluster together: {members}")


def test_no_length_prune_for_a_matcher_without_similarity_bound():
    """The audit fix: the char length-ratio prune is valid only for difflib. A
    semantic-style matcher (no similarity_bound) must score every pair, so a
    short question that a length prune would drop still clusters with a long one.

    A fake matcher scores this exact long/short pair high and everything else
    low. If cluster.py length-pruned it (2*min/(la+lb) is ~0.28 here, well under
    the bar), the two would land in separate clusters — this asserts they don't.
    """
    from nestor.triage import Decision
    from nestor.triage.cluster import group

    long_q = "Should the store, under concurrent writers over the pooled connection, fail closed?"
    short_q = "fail closed?"

    class _FakeSemantic:
        """Has similarity() and normalize() but NO similarity_bound — like the
        embedding matchers."""
        def normalize(self, v):
            return " ".join(str(v).lower().split())
        def similarity(self, a, b):
            pair = {a, b}
            return 0.9 if pair == {self.normalize(long_q), self.normalize(short_q)} else 0.0

    ds = [Decision(id="0001#0", file="0001.json", question=long_q, commitment="", why="", consolidated_onto=None),
          Decision(id="0002#0", file="0002.json", question=short_q, commitment="", why="", consolidated_onto=None),
          Decision(id="0003#0", file="0003.json", question="An unrelated question entirely.", commitment="", why="", consolidated_onto=None)]
    clusters = group(ds, _FakeSemantic(), bar=0.55)
    # the long/short paraphrase must be one cluster; the unrelated one its own
    members = {tuple(sorted(c.member_ids)) for c in clusters}
    assert ("0001#0", "0002#0") in members, members
