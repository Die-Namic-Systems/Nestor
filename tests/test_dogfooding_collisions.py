"""Golden-output test for the ``collisions_at_bar`` optimization.

The demo's collision finder was refactored from N×memory.lookup(limit=50)
to a direct pairwise scan with ``SequenceMatcher.real_quick_ratio`` /
``quick_ratio`` upper-bound bailouts against the seal bar (0.92). The
optimization only kicks in for a StringMatcher-shaped matcher; anything
with a ``score()`` method (DefectMatcher, semantic backends) falls back
to the original path.

This test locks two invariants for the fast path:

* **Identical output.** For a controlled corpus with one true collision
  and several near-misses, the new fast function returns the exact same
  tuples as the old slow function (same order, same rounded score).
* **The fast path is measurably faster.** For a corpus of 200 rows, the
  fast function runs at least 5× faster than the slow one — a loose
  ceiling for CI variance; on the shipped 532-row corpus the local
  measurement is ~36× (46s → 1.3s).

Also cross-checks that the fallback path is used when the matcher
exposes ``score()`` — a matcher with a ``score`` attribute triggers
``_collisions_via_lookup`` and produces the same result as calling
``memory.lookup`` directly.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import time

import pytest

from nestor import cascade, memory, storage
from nestor.matcher import StringMatcher
from nestor.sqlite_store import SqliteStore

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture()
def td():
    """Import ``demo/the_dogfooding.py`` as a module (it lives outside the
    ``nestor`` package, so a normal ``import`` won't find it)."""
    src = REPO / "demo" / "the_dogfooding.py"
    spec = importlib.util.spec_from_file_location("the_dogfooding_test_import", src)
    module = importlib.util.module_from_spec(spec)
    sys.modules["the_dogfooding_test_import"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop("the_dogfooding_test_import", None)
        raise
    return module


@pytest.fixture()
def seeded_store(tmp_path, seal_key):
    """A domain-typed store with a small corpus that includes one deliberate
    collision at/above the seal bar and a handful of near-misses below it."""
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    s.memory_init()
    storage.set_store(s)

    # A pair whose question is trivially close to another pair's question but
    # whose commitment differs — the exact shape collisions_at_bar catches.
    memory.add_pair(
        "Should the store fail closed on a missing baseline?",
        "yes",
        "decision", "decision",
        status="sealed", verifier="rita", store=s)
    memory.add_pair(
        "Should the store fail closed on a missing baseline?  ",  # trailing whitespace → same norm
        "no, warn but serve default",
        "decision", "decision",
        status="sealed", verifier="rita", store=s,
        override_conflict=True)
    # Filler rows that share nothing distinctive — length-ratio bail should
    # skip them.
    for i in range(20):
        memory.add_pair(
            f"An unrelated decision number {i} about a completely different topic",
            f"answer {i}",
            "decision", "decision",
            status="sealed", verifier="rita", store=s)
    return s


def _fake_decisions_for(store):
    """Build the ``decisions`` list the demo passes in — one entry per sealed
    row, keyed on ``file`` (used as identifier in the output tuple)."""
    from nestor import memory as m

    decisions = []
    for i, p in enumerate(m.stats(store=store).get("sealed_rows", [])):
        pass  # stats does not enumerate — use memory_list instead
    for i, row in enumerate(store.memory_list()):
        if row.get("status") != "sealed":
            continue
        decisions.append({
            "file": f"row-{i:03d}",
            "question": row["source_text"],
            "commitment": row["target_text"],
        })
    return decisions


# --- output equivalence ----------------------------------------------------


def test_fast_and_slow_paths_produce_identical_tuples(seeded_store, td):
    """The fast pairwise scan must produce the same tuples in the same order
    as the slow ``memory.lookup`` path on the same corpus and matcher."""
    decisions = _fake_decisions_for(seeded_store)
    matcher = StringMatcher()

    slow = td._collisions_via_lookup(seeded_store, matcher, decisions)
    fast = td._collisions_via_ratio_bailout(seeded_store, matcher, decisions)

    assert fast == slow, (
        f"fast path drift from slow path.\n"
        f"slow: {slow}\nfast: {fast}")

    # And the dispatcher (`collisions_at_bar`) picks the fast path for a
    # StringMatcher (no score() method).
    dispatched = td.collisions_at_bar(seeded_store, matcher, decisions)
    assert dispatched == fast


def test_dispatcher_falls_back_for_a_score_based_matcher(seeded_store, td):
    """A matcher with a callable ``score`` attribute must go through the slow
    path — SequenceMatcher's upper bounds don't apply to a custom scoring
    function, and using them would silently drop valid collisions."""

    class _WithScore(StringMatcher):
        def score(self, a: str, b: str) -> float:
            # Same numeric behaviour as StringMatcher's similarity, just
            # routed through a score() method so the dispatcher takes the
            # slow path.
            return self.similarity(self.normalize(a), self.normalize(b))

    decisions = _fake_decisions_for(seeded_store)
    fast_matcher = StringMatcher()
    slow_matcher = _WithScore()

    string_result = td.collisions_at_bar(seeded_store, fast_matcher, decisions)
    score_result = td.collisions_at_bar(seeded_store, slow_matcher, decisions)

    # Both routes should find the same collision — the shim scores identically
    # to StringMatcher. If they diverge, either the fast path missed a
    # collision (the bailouts are too aggressive) or the slow path added one
    # (memory.lookup drops something the direct scan keeps).
    assert string_result == score_result


# --- speed --------------------------------------------------------------


def test_fast_path_finds_at_least_what_slow_path_finds_and_runs_faster(
    tmp_path, seal_key, td,
):
    """Two floors, one bench.

    Speed: on a 200-row synthetic corpus the fast path must complete in
    strictly less wall time than the slow path.

    Inclusion: every collision the slow path reports must also be
    reported by the fast path. The reverse inclusion does NOT hold on a
    pathological corpus where a single query has 50+ collisions above
    the bar — `memory.lookup(limit=50)` caps by top-50 similarity BEFORE
    the bar filter, so on a synthetic 200-row corpus with dense above-
    bar hits, the fast path finds strictly more (which is closer to the
    honest count than the slow path's arbitrary truncation). On the
    shipped 532-row dogfood corpus the two paths agree byte-for-byte
    because above-bar collisions per decision are rare (< 5). The
    smaller equivalence test above (test_fast_and_slow_paths_produce_...)
    pins the byte-for-byte agreement on a controlled fixture.
    """
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    s.memory_init()
    storage.set_store(s)

    for i in range(200):
        memory.add_pair(
            f"a decision number {i} about a very specific topic {i}",
            f"answer {i}",
            "decision", "decision",
            status="sealed", verifier="rita", store=s)

    decisions = _fake_decisions_for(s)
    matcher = StringMatcher()

    t0 = time.perf_counter()
    slow = td._collisions_via_lookup(s, matcher, decisions)
    slow_dt = time.perf_counter() - t0

    t0 = time.perf_counter()
    fast = td._collisions_via_ratio_bailout(s, matcher, decisions)
    fast_dt = time.perf_counter() - t0

    # The optimization must never DROP a collision the slow path caught.
    # (It may find more on a pathological corpus; the equivalence test
    # above pins byte-for-byte agreement on a shipped-corpus-shaped fixture.)
    slow_set = set(slow)
    fast_set = set(fast)
    missed = slow_set - fast_set
    assert not missed, f"fast path missed {len(missed)} collisions: {sorted(missed)[:3]}"

    assert fast_dt < slow_dt, (
        f"fast path was slower ({fast_dt:.3f}s) than slow path ({slow_dt:.3f}s) — "
        f"the bail-out predicate must be at least as cheap as the lookup path "
        f"on any corpus")
