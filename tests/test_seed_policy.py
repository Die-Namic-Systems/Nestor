"""``nestor.seed_policy`` — the policy-shaped demo store.

Mirrors the shape of ``tests/test_seed.py`` — same three-recipe coverage,
same cold-start / no-duplicates rules — with two extras that speak to what
the policy fixture is FOR:

* **The covenant is demonstrable.** The one draft row (`_DRAFTS`) must
  land as ``draft`` (not sealed) — the row a walk-through ends on to teach
  what Nestor refuses to do.
* **The verifier name is not shared with the default fixture.** The default
  seeds under ``rita``; the policy seed uses ``elena``. A reviewer looking
  at a store must be able to tell which fixture it was seeded from at a
  glance.
"""
from __future__ import annotations

from nestor import cascade, memory, seed_policy
from nestor.sqlite_store import SqliteStore


def _fresh_store(tmp_path, ledger="ledger.jsonl"):
    cascade.set_ledger_path(str(tmp_path / ledger))
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    return store


def test_policy_seed_counts_and_all_three_recipes(tmp_path):
    store = _fresh_store(tmp_path)
    counts = seed_policy.seed_store(store)

    # Load-bearing counts — the fixture claims 5 sealed + 1 draft translations,
    # 4 aliases, 2 baselines, and a review queue.
    assert counts["sealed"] == 5
    assert counts["draft"] == 1
    assert counts["aliases"] == 4
    assert counts["baselines"] == 2
    assert counts["queued"] >= 1
    assert counts["forged"] == 0  # signing off in tests → forged row is not seeded

    # All three recipes present under the same lang-pair scheme as the default
    # seed: translation (en → es), entity (entity → entity), value (value → value).
    stats = memory.stats(store=store)
    pairs = {(sl, tl) for sl, tl, _ in stats["lang_pairs"]}
    targets = {tl for _, tl, _ in stats["lang_pairs"]}
    assert ("en", "es") in pairs
    assert ("entity", "entity") in pairs
    assert "value" in targets


def test_the_draft_row_is_the_covenant_demonstration(tmp_path):
    """The one draft row (`_DRAFTS`) must land unsigned — the covenant tour
    ends at this row: the machine proposed a translation, the store keeps
    it, and no ``verified`` result comes back until a human seals it.
    """
    store = _fresh_store(tmp_path)
    seed_policy.seed_store(store)

    drafts = [p for p in store.memory_list() if p.get("status") == "draft"]
    assert len(drafts) >= 1
    for d in drafts:
        # A draft has no verifier attribution and no signature. Both
        # invariants must hold for `ask` to correctly return `pending`
        # when the row is retrieved.
        assert not d.get("verifier"), (
            f"a draft row must carry no verifier attribution — got "
            f"{d.get('verifier')!r} on {d.get('source_text')!r}")
        assert not d.get("seal_sig"), (
            "a draft row must carry no seal signature; if this row were "
            "later mistaken for a sealed one, the covenant would silently "
            "serve unverified content")


def test_policy_seed_verifier_is_distinct_from_the_default_seed(tmp_path):
    """A reviewer opening a store should be able to tell whether it was
    seeded from the default fixture (``rita``) or the policy fixture
    (``elena``) without reading the source text.
    """
    store = _fresh_store(tmp_path)
    seed_policy.seed_store(store)

    verifiers = {p.get("verifier") for p in store.memory_list()
                 if p.get("verifier")}
    assert seed_policy.DEMO_VERIFIER in verifiers
    # The default seed's verifier must not be present, so the two fixtures
    # remain distinguishable even in a mixed store (which shouldn't happen
    # but the invariant makes it obvious if it does).
    from nestor import seed as default_seed
    assert default_seed.DEMO_VERIFIER != seed_policy.DEMO_VERIFIER
    assert default_seed.DEMO_VERIFIER not in verifiers


def test_policy_seed_origin_tag_is_distinct_from_the_default(tmp_path):
    """The ``origin`` column carries which fixture wrote each row — same
    reason as the verifier: a reviewer needs to tell them apart. Default
    uses ``demo``; policy uses ``demo-policy``.
    """
    store = _fresh_store(tmp_path)
    seed_policy.seed_store(store)

    origins = {p.get("origin") for p in store.memory_list()}
    assert "demo-policy" in origins
    assert "demo" not in origins
