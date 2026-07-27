"""A conflicting seal must not pass unnoticed.

``add_pair`` used to let a second SEALED row for the same source silently
clobber the first via ``store.memory_seal`` — same pair id, old target simply
gone, nothing raised. ``RejectedPairError`` already refuses that moment when a
rejection is on record; these tests pin the same refusal one step earlier, for
two humans who never went through rejection at all but simply asserted
different answers for the same source text.

The signal that tells a *correction* (one reviewer fixing their own earlier
seal — proceed) from a *conflict* (two reviewers disagreeing — raise) is
verifier identity: same non-empty verifier is a correction, everything else
(including an empty verifier on either side) is treated as unknown and
therefore conflicting.
"""
from __future__ import annotations

import pytest

from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NESTOR_SEAL_KEY", "test-key")
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    storage.set_store(s)
    return s


def test_different_verifier_different_target_raises(store):
    """The reproduction from the bug report: rita seals one answer, sam seals
    a different one for the same source — this is a conflict, not an upgrade."""
    memory.add_pair("routing_decisions", "defA", "en", "es",
                    status="sealed", verifier="rita", store=store)

    with pytest.raises(memory.ConflictingSealError, match="rita"):
        memory.add_pair("routing_decisions", "defB", "en", "es",
                        status="sealed", verifier="sam", store=store)

    # defA must survive untouched — the whole point of raising early.
    hit = memory.best_sealed("routing_decisions", "en", "es", store=store)
    assert hit is not None
    assert hit["pair"]["target_text"] == "defA"
    assert hit["pair"]["verifier"] == "rita"


def test_same_verifier_reseal_is_a_correction_not_a_conflict(store):
    """A reviewer fixing their OWN earlier seal must not need an override —
    that is the routine case option C exists to keep silent."""
    pair = memory.add_pair("routing_decisions", "defA", "en", "es",
                           status="sealed", verifier="rita", store=store)

    corrected = memory.add_pair("routing_decisions", "defB", "en", "es",
                                status="sealed", verifier="rita", store=store)

    assert corrected["id"] == pair["id"], "a correction upgrades the same pair"
    hit = memory.best_sealed("routing_decisions", "en", "es", store=store)
    assert hit["pair"]["target_text"] == "defB"


def test_empty_verifier_does_not_count_as_a_self_correction(store):
    """``verifier`` defaults to "" and is the single most common value an
    unauthenticated or scripted caller supplies. Treating "" == "" as "the
    same reviewer correcting themselves" would silently wave through every
    anonymous re-seal — exactly the leak this guard exists to close. An
    absent verifier asserts no identity, so two of them must not be assumed
    to be the same actor."""
    memory.add_pair("anon_key", "defA", "en", "es", status="sealed", store=store)

    with pytest.raises(memory.ConflictingSealError):
        memory.add_pair("anon_key", "defB", "en", "es", status="sealed", store=store)

    assert memory.best_sealed("anon_key", "en", "es", store=store)["pair"]["target_text"] == "defA"


def test_override_conflict_is_available_but_explicit(store):
    """Mirrors ``override_rejection`` — a deliberate escape hatch, not a
    silent default."""
    memory.add_pair("routing_decisions", "defA", "en", "es",
                    status="sealed", verifier="rita", store=store)

    overwritten = memory.add_pair("routing_decisions", "defB", "en", "es",
                                  status="sealed", verifier="sam", store=store,
                                  override_conflict=True)

    assert overwritten["target_text"] == "defB"
    hit = memory.best_sealed("routing_decisions", "en", "es", store=store)
    assert hit["pair"]["target_text"] == "defB"
    assert hit["pair"]["verifier"] == "sam"


def test_conflict_guard_does_not_block_a_draft_graduating_to_sealed(store):
    """The guard is scoped to an existing SEALED row on purpose. A machine
    draft (tier 2/3, never verified by anyone) getting sealed for the first
    time by a human is the normal graduation path, not a conflict, even
    though its target differs from the unverified draft's."""
    memory.add_pair("gap_15", "draft-guess", "en", "es",
                    status="draft", store=store)

    sealed = memory.add_pair("gap_15", "human-verified-answer", "en", "es",
                             status="sealed", verifier="rita", store=store)

    assert sealed["status"] == "sealed"
    assert sealed["target_text"] == "human-verified-answer"


def test_same_target_reseal_never_conflicts_regardless_of_verifier(store):
    """Re-affirming the SAME answer is not a conflict under any verifier
    combination — the guard only fires when the target actually differs,
    matching the pre-existing overwrite condition it sits in front of."""
    memory.add_pair("stable_fact", "the answer", "en", "es",
                    status="sealed", verifier="rita", store=store)
    # A different verifier re-sealing the identical target must go through.
    again = memory.add_pair("stable_fact", "the answer", "en", "es",
                            status="sealed", verifier="sam", store=store)
    assert again["target_text"] == "the answer"


def test_conflicting_seal_propagates_through_graduate_segment(store):
    """``cascade.graduate_segment`` is a thin wrapper over ``add_pair`` with
    no guard of its own — the conflict must surface at that call site too,
    since that is how a normal review queue would trigger this in practice."""
    memory.add_pair("See you soon", "Hasta pronto", "en", "es",
                    status="sealed", verifier="rita", store=store)

    doc = store.create_document("d", "en", "es")
    seg = store.create_segment(doc["id"], 0, "See you soon", "Nos vemos", 0.6)

    with pytest.raises(memory.ConflictingSealError):
        cascade.graduate_segment(seg["id"], verifier="sam", store=store)

    # rita's seal must still be what serves.
    hit = memory.best_sealed("See you soon", "en", "es", store=store)
    assert hit["pair"]["target_text"] == "Hasta pronto"


def test_seed_from_corpus_skips_conflicts_instead_of_aborting(store, tmp_path):
    """A human's seal beats a curated corpus — but a collision must not halt the
    import. Found by inspection after the guard landed: seeding uses the fixed
    verifier "corpus", which never matches a person, so a single overlap used to
    abort mid-load and leave a half-seeded memory."""
    import json
    memory.add_pair("hola", "hi there", "es", "en", status="sealed",
                    verifier="rita", store=store)
    # Pass the loader explicitly rather than via set_bilingual_loader — that
    # setter mutates module-level state and would leak into every later test
    # in the session (it did, on the first run of this test).
    def loader():
        return [
            {"front": "hola", "back": "hello", "lang_front": "es",
             "lang_back": "en", "lesson": "L1"},
            {"front": "adios", "back": "bye", "lang_front": "es",
             "lang_back": "en", "lesson": "L1"},
        ]

    with pytest.warns(RuntimeWarning, match="skipped"):
        written = memory.seed_from_corpus(loader=loader, store=store)

    # The non-conflicting pair still landed, both directions.
    assert memory.best_sealed("adios", "es", "en", store=store) is not None
    assert memory.best_sealed("bye", "en", "es", store=store) is not None
    # rita's seal survives untouched.
    assert memory.best_sealed("hola", "es", "en", store=store)["pair"]["target_text"] == "hi there"
    assert written == 3, "3 of 4 directions written, 1 skipped"

    kinds = [json.loads(x)["kind"]
             for x in (tmp_path / "ledger.jsonl").read_text().strip().split("\n")]
    assert "seed_conflict" in kinds, "a skipped row must not vanish silently"
