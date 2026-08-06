"""Nestor#32 — the ledger's ``kind`` set: writers closed, readers permissive.

``kind`` is the one field in a row that records why a boundary was crossed.
Before this, twenty-one kinds had grown one call site at a time with nothing
pinning them, and an unknown kind was not an error but a new event type —
which propagated into the FRANK mirror and silently vanished from every
``entries(kind=...)`` review surface. The homestead precedent (its R-7 and
I-13): a control nothing can check is a label.

Three claims, each with the counter-case proven:

  * the set is pinned EXACTLY — a twenty-second kind is a deliberate,
    reviewed act (this file changes in the same diff as its first writer);
  * a writer with an unpinned kind is refused before the file is touched;
  * a READER never refuses a historical kind — an audit trail must not
    refuse to show what it already recorded.
"""
from __future__ import annotations

import json

import pytest

from nestor import cascade, ledger

#: Mirror, not import: the point is that CHANGING the set requires touching
#: two files in one reviewed diff. Importing cascade.LEDGER_KINDS here would
#: make this test true by construction and therefore vacuous.
PINNED = {
    "baseline_replaced", "baseline_seal", "bundle_import", "corpus_seed",
    "countersign", "entity_resolve", "entity_seal", "passage", "proposal",
    "reconcile",
    "reject_match", "reject_pair", "reject_segment", "restore", "seal",
    "seal_override", "seal_replaced", "seed_conflict", "seed_rejected",
    "segment_sealed", "supersede", "unseal",
}


def test_the_set_is_pinned_exactly():
    assert cascade.LEDGER_KINDS == PINNED, (
        "cascade.LEDGER_KINDS changed without updating the pinning test — "
        "a new kind must arrive deliberately: set + test + first writer in "
        "one diff (Nestor#32)")


def test_every_source_literal_kind_is_pinned():
    # The inventory check the issue performed by hand, kept mechanical: any
    # `"kind": "x"` literal in nestor/ must be in the set, so a new writer
    # cannot land without the set (and therefore this file) changing.
    import pathlib
    import re
    src = pathlib.Path(cascade.__file__).parent
    found = set()
    for py in src.glob("*.py"):
        found |= set(re.findall(r'"kind": "([a-z_]+)"', py.read_text()))
    assert found <= cascade.LEDGER_KINDS, (
        f"unpinned kind literals in source: {sorted(found - cascade.LEDGER_KINDS)}")


def test_writer_refuses_unknown_kind(tmp_path):
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError, match="unknown ledger kind"):
        cascade.ledger_append({"kind": "sealx"})   # the typo the issue fears
    with pytest.raises(ValueError, match="unknown ledger kind"):
        cascade.ledger_append({"detail": "no kind at all"})
    # Refused before the file was touched: no half-written chain.
    assert not (tmp_path / "ledger.jsonl").exists()


def test_reader_stays_permissive_for_historical_kinds(tmp_path):
    # A ledger written before the set existed (or by a newer Nestor with a
    # newer set) contains kinds this build does not know. verify() must
    # still verify it and entries() must still return them — an audit trail
    # that refuses to show its own past is the one failure worse than free
    # text.
    lp = tmp_path / "ledger.jsonl"
    cascade.set_ledger_path(lp)
    cascade.ledger_append({"kind": "seal", "verifier": "rita"})
    # Forge history the honest way: rewrite the file with an unknown kind,
    # re-chaining it correctly, as an old build would have written it.
    rows = [json.loads(ln) for ln in lp.read_text().splitlines()]
    old = {"ts": rows[0]["ts"], "prev": rows[0]["prev"],
           "kind": "a_kind_from_2025", "detail": "predates the set"}
    import hashlib
    line0 = json.dumps(old, ensure_ascii=False)
    row1 = {"ts": rows[0]["ts"], "prev": hashlib.sha256(line0.encode()).hexdigest(),
            "kind": "seal", "verifier": "rita"}
    lp.write_text(line0 + "\n" + json.dumps(row1, ensure_ascii=False) + "\n")

    ok, detail = ledger.verify(str(lp))
    assert ok, detail
    kinds = {e["kind"] for e in ledger.entries(path=str(lp), limit=10)}
    assert "a_kind_from_2025" in kinds


def test_appending_after_historical_unknown_kind_still_works(tmp_path):
    # Writer-closed must not make an old ledger unappendable: the check is
    # on the NEW entry's kind, never on the tail it extends. Build the
    # historical file from scratch — this process never appended to it, so
    # the per-process tail checkpoint has nothing to dispute.
    lp = tmp_path / "old-ledger.jsonl"
    old = {"ts": "2025-01-01T00:00:00+00:00", "prev": "genesis",
           "kind": "prehistoric", "detail": "predates the set"}
    lp.write_text(json.dumps(old, ensure_ascii=False) + "\n")
    cascade.set_ledger_path(lp)
    cascade.ledger_append({"kind": "restore", "pair_id": "x"})
    ok, detail = ledger.verify(str(lp))
    assert ok, detail
    kinds = [e["kind"] for e in ledger.entries(path=str(lp), limit=10)]
    assert kinds == ["prehistoric", "restore"]
