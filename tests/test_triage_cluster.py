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

import time

from nestor.matcher import StringMatcher
from nestor.triage import Decision, load_decisions
from nestor.triage.cluster import group


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


def test_smoke_real_corpus_partitions_every_decision_quickly():
    decisions = load_decisions()
    assert len(decisions) > 100  # the real queue, not an empty tree

    start = time.monotonic()
    clusters = group(decisions, StringMatcher(), 0.45)
    elapsed = time.monotonic() - start
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
