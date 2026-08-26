"""Gate the strings in ``docs/walk-through-covenant.md`` against the store.

The walk-through doc is a beat-by-beat tour of the policy seed that ends at
the moment a machine's draft becomes a human's decision. It quotes literal
strings for beats 1, 2, 3, and 5. If any of those strings drifts out of what
``nestor demo --seed policy`` actually produces, the doc becomes an
asserted-not-verified claim — the exact anti-pattern the seat rule about
saying-what-you-read forbids.

The doc's beat 4 is a human sealing in the UI. No agent can execute that
step, so the test emulates it the same way ``demo/sixty_seconds.py`` beat 2
does — call ``memory.add_pair(..., status="sealed", verifier="elena")``
directly — and then asserts beat 5's *retype-and-serve-as-verified* holds.

Beat 6 (the ledger holds it, one edit breaks the chain) is covered by
``tests/test_review_ledger.py`` — this file does not re-litigate it.
"""
from __future__ import annotations

import pathlib

from nestor import answer, cascade, memory, seed_policy
from nestor.sqlite_store import SqliteStore

DOC = pathlib.Path(__file__).resolve().parents[1] / "docs" / "walk-through-covenant.md"


def _seeded_store(tmp_path):
    cascade.set_ledger_path(str(tmp_path / "ledger.jsonl"))
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    seed_policy.seed_store(store)
    return store


def _ask(store, text: str) -> dict:
    return answer.ask(store, text, "en", "es", engine_name="offline")


def test_doc_exists():
    """A missing doc would make every claim below vacuously true."""
    assert DOC.is_file(), f"walk-through doc must live at {DOC}"


def test_beat_1_sealed_serve(tmp_path):
    """*"The agreement enters into force on ratification."* — one of the
    five sealed translations. Must serve as verified, by ``elena``, with
    similarity 1.0. This is the shape of every green ``✓ sealed`` line in
    the doc.
    """
    store = _seeded_store(tmp_path)
    src = "The agreement enters into force on ratification."
    tgt = "El acuerdo entra en vigor tras la ratificación."

    result = _ask(store, src)
    assert result["verified"], (
        "beat 1's sealed sentence must serve as verified — if it does not, "
        "the whole walk-through's opening claim is false")
    assert result["passage"]["target"] == tgt, (
        f"beat 1's target string drifted: doc quotes {tgt!r}, "
        f"got {result['passage']['target']!r}")
    assert result["passage"]["meta"].get("verifier") == seed_policy.DEMO_VERIFIER

    # The doc quotes both the source and the target verbatim.
    doc_text = DOC.read_text(encoding="utf-8")
    assert src in doc_text, "beat 1's source string is not in the walk-through"
    assert tgt in doc_text, "beat 1's target string is not in the walk-through"


def test_beat_2_the_draft_row_is_pending(tmp_path):
    """*"The measure takes effect immediately."* — the one draft row the
    policy seed leaves for a human. Must come back as ``draft``, never as
    verified. This is the row the ninety seconds turn on.
    """
    store = _seeded_store(tmp_path)
    src = "The measure takes effect immediately."
    tgt = "La medida entra en vigor de inmediato."

    result = _ask(store, src)
    assert not result["verified"], (
        "beat 2's draft row must never serve as verified — if it does, the "
        "covenant demonstration is broken and the walk-through lies")
    # The machine's guess is offered (marked draft), so a reader who accepts
    # it in the UI can seal it in one click. The doc quotes it explicitly.
    assert result["passage"]["target"] == tgt

    doc_text = DOC.read_text(encoding="utf-8")
    assert src in doc_text
    assert tgt in doc_text


def test_beat_3_rewrite_is_below_the_bar(tmp_path):
    """*"The agreement is in force after ratification."* — a rewrite that
    means the same thing as beat 1's sentence. Must return the beat-1
    target as a draft (the closest sealed row's answer), not serve it as
    verified. A character-ratio matcher does not read; the walk-through
    names this out loud.
    """
    store = _seeded_store(tmp_path)
    rewrite = "The agreement is in force after ratification."
    beat_1_target = "El acuerdo entra en vigor tras la ratificación."

    result = _ask(store, rewrite)
    assert not result["verified"], (
        "beat 3's rewrite must not serve as verified — if it does, the "
        "seal bar is set below what the walk-through claims and the "
        "'the machine may propose, it may not confirm' shape is broken")
    assert result["passage"]["target"] == beat_1_target, (
        "beat 3 claims the machine offers beat-1's exact sealed answer as "
        "the draft — if the closest-sealed-row logic changes, the doc "
        "needs to change with it")

    doc_text = DOC.read_text(encoding="utf-8")
    assert rewrite in doc_text


def test_beat_5_seal_then_retype_serves_as_verified(tmp_path):
    """After a human seals beat 2's drafted row in the UI, the same
    ``ask`` command comes back green. This is the punchline of the tour:
    the amber ``~ draft`` from beat 2 becomes the green ``✓ sealed`` of
    beat 1, one human action between them.

    The test emulates the UI seal the way ``demo/sixty_seconds.py`` beat 2
    does — ``memory.add_pair`` with the demo verifier — since no agent can
    actually perform the UI-side signing action.
    """
    store = _seeded_store(tmp_path)
    src = "The measure takes effect immediately."
    tgt = "La medida entra en vigor de inmediato."

    # Beat 4 — the human seal. In the doc this is a click in the UI; here
    # it is the same call the UI makes internally.
    memory.add_pair(src, tgt, "en", "es", status="sealed",
                    verifier=seed_policy.DEMO_VERIFIER, origin="demo-policy",
                    store=store)

    # Beat 5 — the same command as beat 2, now green.
    result = _ask(store, src)
    assert result["verified"], (
        "beat 5's re-ask must serve as verified once the drafted row is "
        "sealed — this is the whole 'one human, one time' argument")
    assert result["passage"]["target"] == tgt
    assert result["passage"]["meta"].get("verifier") == seed_policy.DEMO_VERIFIER


def test_doc_names_the_bench_that_gates_it():
    """A doc that promises a test as its anchor must name this file. If the
    doc drifts to point somewhere else, this assertion catches the drift
    the same way the beat-string assertions catch a string drift.
    """
    text = DOC.read_text(encoding="utf-8")
    assert "test_walk_through_covenant.py" in text, (
        "walk-through doc must name the bench that gates it — otherwise "
        "the reader has no way to check what actually holds")
