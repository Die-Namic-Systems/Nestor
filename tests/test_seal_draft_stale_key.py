"""Sealing a draft whose stored ``source_norm`` no longer reproduces under the
domain's matcher — the dump case §6.40's fix does not reach.

§6.40 (``test_ui_custom_matcher.py``) pinned that a draft *created with* the
domain's matcher seals in place: the draft and the seal are one row. This is its
sibling, found dogfooding a store built from bulk imports. A dump can write a
``source_norm`` that the domain's matcher does not reproduce — the raw text, or
an older normaliser's output. ``add_pair`` re-derives the key as
``matcher.normalize(source_text)`` and finds the draft by *that* key, so a stale
stored key misses: the write becomes an INSERT of a second, correctly-keyed
sealed row, and the draft the human sealed stays live in the queue.

The consequence is not an error. It is an HTTP 200, a real seal, and a draft
that "will not disappear" — and it is store-origin-dependent, because only
imported rows carry a stale key. Each test is written so it fails on the *old*
behaviour: a test that only checked the sealed row exists would have passed
throughout.
"""
from __future__ import annotations

import datetime
import os
import uuid

import pytest

from nestor import cascade, memory, storage, ui
from nestor.matcher import StringMatcher
from nestor.sqlite_store import SqliteStore

DOMAIN = "decision"
STALE = "Adopt the seat gate"  # StringMatcher lowercases: stored verbatim != key


@pytest.fixture()
def desk(tmp_path, seal_key):
    """A surface on the decision domain — no custom matcher, so it defers to the
    process-wide StringMatcher, exactly the domain the dogfood store uses."""
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(str(tmp_path / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    return ui.App(store=store, source_lang=DOMAIN, target_lang=DOMAIN,
                  db_path=str(tmp_path / "nestor.db"))


def post(app, path, **payload):
    return ui.dispatch(app, "POST", path, {}, payload)


def _dumped_draft(store, source_text, *, source_norm, target_text="pending"):
    """Insert a row the way a bulk import does — with a ``source_norm`` we
    choose, bypassing ``add_pair``'s normalisation. This is how a dump strands a
    key that the domain matcher will never recompute."""
    pair = {
        "id": str(uuid.uuid4()), "source_text": source_text,
        "source_norm": source_norm, "source_lang": DOMAIN,
        "target_text": target_text, "target_lang": DOMAIN, "status": "draft",
        "verifier": "", "weight": 1.0, "origin": "dump",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "seal_sig": "", "reason": "", "superseded_by": "",
    }
    store.memory_insert(pair)
    return pair


def _live(store):
    return store.memory_candidates(DOMAIN, DOMAIN)


def test_fixture_is_a_real_mismatch():
    assert StringMatcher().normalize(STALE) != STALE, (
        "the test's premise is a stored norm the matcher does not reproduce")


def test_sealing_a_stale_keyed_draft_upgrades_that_row(desk):
    """The core bug: the draft and the seal must be one row, even when the
    draft's stored key is stale."""
    draft = _dumped_draft(desk.store, STALE, source_norm=STALE)

    status, body = post(desk, "/api/seal-draft", pair_id=draft["id"],
                        target="the commitment", verifier="rita")
    assert status == 200
    assert body["pair"]["id"] == draft["id"], "the seal minted a second row"
    assert body["pair"]["status"] == "sealed"

    rows = _live(desk.store)
    assert len(rows) == 1, f"one source must be one live row, found {len(rows)}"
    assert not [r for r in rows if r["status"] == "draft"], (
        "the draft she sealed is still queued")
    assert rows[0]["source_norm"] == StringMatcher().normalize(STALE), (
        "the sealed row kept the stale key and would strand again")


def test_sealing_never_leaves_a_second_live_row(desk):
    """The invariant, stated as the forbidden act: sealing a stale-keyed draft
    must not create a second live row for the same source. Fails loudly on the
    old insert-a-duplicate behaviour."""
    draft = _dumped_draft(desk.store, STALE, source_norm=STALE)
    post(desk, "/api/seal-draft", pair_id=draft["id"], verifier="rita")

    live = _live(desk.store)
    assert len(live) == 1, (
        f"sealing minted a duplicate: {[(r['status'], r['source_norm']) for r in live]}")


def test_sealing_a_stale_draft_beside_its_sealed_twin_reconciles(desk):
    """The dogfooding state: an earlier click already minted the correctly-keyed
    sealed twin and the stale draft stayed behind. Sealing again must collapse to
    ONE live row (retire the redundant draft), not add a third."""
    memory.add_pair(STALE, "the commitment", DOMAIN, DOMAIN, status="sealed",
                    verifier="rita", store=desk.store)  # twin, correct key
    draft = _dumped_draft(desk.store, STALE, source_norm=STALE)  # stranded

    status, _ = post(desk, "/api/seal-draft", pair_id=draft["id"], verifier="rita")
    assert status == 200

    live = _live(desk.store)
    assert len(live) == 1, f"reconcile must collapse the twins, found {len(live)}"
    assert live[0]["status"] == "sealed"
    assert not [r for r in live if r["status"] == "draft"], (
        "the stranded draft is still live after the reconcile")


def test_a_healthy_draft_still_seals_in_place(desk):
    """The guard must not disturb the case §6.40 already fixed: a draft created
    through ``add_pair`` (consistent key) seals in place, same id, unchanged."""
    draft = memory.add_pair("a clean decision", "pending", DOMAIN, DOMAIN,
                            status="draft", store=desk.store)
    status, body = post(desk, "/api/seal-draft", pair_id=draft["id"],
                        target="its commitment", verifier="rita")
    assert status == 200
    assert body["pair"]["id"] == draft["id"]
    assert len(_live(desk.store)) == 1


# ── the offline repair for stores that already carry the damage ──────────────

def _store(tmp_path):
    store = SqliteStore(str(tmp_path / "repair.db"))
    store.init_db()
    store.memory_init()
    return store


def test_renormalize_dry_run_writes_nothing(tmp_path, seal_key):
    store = _store(tmp_path)
    draft = _dumped_draft(store, STALE, source_norm=STALE)

    report = memory.renormalize_keys(store, apply=False)
    assert [r["id"] for r in report["rekeyed"]] == [draft["id"]]
    # Nothing changed on disk.
    assert store.memory_get(draft["id"])["source_norm"] == STALE


def test_renormalize_apply_rekeys_a_stranded_draft(tmp_path, seal_key):
    store = _store(tmp_path)
    draft = _dumped_draft(store, STALE, source_norm=STALE)

    report = memory.renormalize_keys(store, apply=True)
    assert [r["id"] for r in report["rekeyed"]] == [draft["id"]]
    healed = store.memory_get(draft["id"])
    assert healed["source_norm"] == StringMatcher().normalize(STALE)
    assert healed["status"] == "draft", "re-keying must not change status"
    # And the seal that missed before now lands on this row.
    assert store.memory_find(StringMatcher().normalize(STALE), DOMAIN, DOMAIN)["id"] == draft["id"]


def test_renormalize_apply_retires_a_draft_that_duplicates_a_sealed_twin(tmp_path, seal_key):
    store = _store(tmp_path)
    twin = memory.add_pair(STALE, "the commitment", DOMAIN, DOMAIN,
                           status="sealed", verifier="rita", store=store)
    draft = _dumped_draft(store, STALE, source_norm=STALE)

    report = memory.renormalize_keys(store, apply=True)
    assert [r["id"] for r in report["retired"]] == [draft["id"]]
    live = store.memory_candidates(DOMAIN, DOMAIN)
    assert len(live) == 1 and live[0]["id"] == twin["id"], "the twin is the survivor"
    assert store.memory_get(draft["id"])["superseded_by"] == twin["id"]


def test_renormalize_never_rekeys_a_sealed_row(tmp_path, seal_key):
    """The forbidden act: re-keying a sealed row rewrites the key its signature
    covers. renormalize must report it and leave it untouched, not silently
    invalidate a human's seal."""
    store = _store(tmp_path)
    sealed = {
        "id": "11111111-1111-1111-1111-111111111111", "source_text": STALE,
        "source_norm": STALE, "source_lang": DOMAIN, "target_text": "x",
        "target_lang": DOMAIN, "status": "sealed", "verifier": "rita",
        "weight": 1.0, "origin": "dump",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "seal_sig": "sig-over-the-stale-key", "reason": "", "superseded_by": "",
    }
    store.memory_insert(sealed)

    report = memory.renormalize_keys(store, apply=True)
    assert [r["id"] for r in report["sealed_stale"]] == [sealed["id"]]
    assert not report["rekeyed"] and not report["retired"]
    after = store.memory_get(sealed["id"])
    assert after["source_norm"] == STALE, "a sealed row's key was silently moved"
    assert after["seal_sig"] == "sig-over-the-stale-key", "the seal was disturbed"


def test_cli_db_renormalize_apply_heals_the_store(tmp_path, seal_key):
    from nestor import cli

    store = _store(tmp_path)
    draft = _dumped_draft(store, STALE, source_norm=STALE)
    del store  # the CLI opens its own handle on the same file

    code = cli.main(["--db", str(tmp_path / "repair.db"),
                     "--ledger", str(tmp_path / "ledger.jsonl"),
                     "db", "renormalize", "--apply"])
    assert code == cli.EXIT_OK

    reopened = SqliteStore(str(tmp_path / "repair.db"))
    assert reopened.memory_get(draft["id"])["source_norm"] == StringMatcher().normalize(STALE)
