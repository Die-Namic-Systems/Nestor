"""Session seals (nestor.session_seal): a person's one yes to their own session.

Each guard has a test that attempts the forbidden act and asserts the refusal:
sealing a bundle that changed, a pair whose shown actions aren't the bundle's,
a session whose bundle isn't stored, and the same three through supersede and
the UI's seal-draft. Denial keeps the record readable and unserved; a sealed
session is served in its domain like any sealed pair (tagged, not excluded).
"""
from __future__ import annotations

import os

import pytest

from nestor import cascade, memory, session_seal, storage, ui
from nestor.sqlite_store import SqliteStore

BUNDLE = {
    "session": "2026-10-19-a",
    "actions": [
        {"did": "seed: replicate the meowdoku puzzle game", "came_of": ["seeded, 18 words"]},
        {"did": "forge: the same bite", "came_of": ["major: game"]},
    ],
    "pieces": [{"sha256": "ab" * 32, "where": "safe-app-store:apps/the-table"}],
    "tip": "cd" * 32,
}


@pytest.fixture()
def store(tmp_path, seal_key):
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    s.memory_init()
    storage.set_store(s)
    return s


def _seal(pair, store):
    return memory.add_pair(pair["source_text"], pair["target_text"],
                           session_seal.DOMAIN, session_seal.DOMAIN,
                           status="sealed", verifier="rita", store=store)


def _tamper(store, pair):
    sha = pair["target_text"].split(":", 1)[1]
    with store._db() as conn:
        conn.execute("UPDATE session_bundles SET bundle=? WHERE sha256=?",
                     (b'{"session":"x","actions":[{"did":"not this"}]}', sha))


def test_propose_is_one_draft_in_the_session_domain(store):
    pair = session_seal.propose(BUNDLE, origin="one-script", store=store)
    assert (pair["status"], pair["source_lang"], pair["target_lang"]) == (
        "draft", "session", "session")
    assert pair["target_text"] == session_seal.subject(session_seal.canonical(BUNDLE))
    assert pair["source_text"].splitlines() == [
        "Session 2026-10-19-a",
        "1. seed: replicate the meowdoku puzzle game",
        "   → seeded, 18 words",
        "2. forge: the same bite",
        "   → major: game",
    ]
    (w,) = [w for w in store.memory_warrants_for(pair["id"])]
    assert (w["kind"], w["expected_digest"]) == (
        "construction", pair["target_text"].split(":", 1)[1])


def test_the_view_shows_the_bundles_actions_when_verified(store):
    pair = session_seal.propose(BUNDLE, store=store)
    v = session_seal.view(pair["id"], store=store)
    assert (v["state"], v["why"], v["status"]) == ("verified", "", "draft")
    assert [a["did"] for a in v["actions"]] == [a["did"] for a in BUNDLE["actions"]]
    assert v["keys"] == ["pieces", "session", "tip"]


def test_a_verified_session_seals(store):
    pair = session_seal.propose(BUNDLE, store=store)
    sealed = _seal(pair, store)
    assert sealed["status"] == "sealed" and sealed["verifier"] == "rita"


def test_a_bundle_that_changed_is_never_sealed(store):
    pair = session_seal.propose(BUNDLE, store=store)
    _tamper(store, pair)
    assert session_seal.view(pair["id"], store=store)["state"] == "unverifiable"
    with pytest.raises(session_seal.SessionBundleError, match="doesn't hash"):
        _seal(pair, store)
    assert store.memory_get(pair["id"])["status"] == "draft"


def test_actions_that_arent_the_bundles_are_never_sealed(store):
    pair = session_seal.propose(BUNDLE, store=store)
    with pytest.raises(session_seal.SessionBundleError, match="not the bundle's"):
        memory.add_pair("Session 2026-10-19-a\n1. something else", pair["target_text"],
                        "session", "session", status="sealed", verifier="rita",
                        store=store)


def test_a_session_with_no_stored_bundle_is_never_sealed(store):
    with pytest.raises(session_seal.SessionBundleError, match="not in this store"):
        memory.add_pair("Session z\n1. made up", "session:" + "ef" * 32,
                        "session", "session", status="sealed", verifier="rita",
                        store=store)
    with pytest.raises(session_seal.SessionBundleError, match="not session:<sha256>"):
        memory.add_pair("Session z\n1. made up", "yes", "session", "session",
                        status="sealed", verifier="rita", store=store)


def test_supersede_takes_the_same_check(store):
    pair = _seal(session_seal.propose(BUNDLE, store=store), store)
    with pytest.raises(session_seal.SessionBundleError):
        memory.supersede_pair(pair["source_text"], "session:" + "01" * 32,
                              "session", "session", verifier="rita", store=store)


def test_the_uis_seal_draft_refuses_an_unverifiable_session(store, tmp_path):
    app = ui.App(store=store, source_lang="en", target_lang="es", db_path=":memory:")
    pair = session_seal.propose(BUNDLE, store=store)
    _tamper(store, pair)
    status, body = ui.dispatch(app, "POST", "/api/seal-draft", {},
                               {"pair_id": pair["id"], "verifier": "rita"})
    assert (status, body["code"]) == (409, "unverifiable_session")
    status, got = ui.dispatch(app, "GET", "/api/session-seal", {"id": pair["id"]}, {})
    assert status == 200 and got["session"]["state"] == "unverifiable"
    status, _ = ui.dispatch(app, "GET", "/api/session-seal", {"id": "nope"}, {})
    assert status == 404


def test_a_denied_session_stays_readable_and_is_never_served(store):
    pair = _seal(session_seal.propose(BUNDLE, store=store), store)
    memory.reject_pair(pair["id"], verifier="rita", reason="not my session")
    row = store.memory_get(pair["id"])
    assert row["status"] == "rejected" and row["source_text"] == pair["source_text"]
    assert session_seal.view(pair["id"], store=store)["state"] == "verified"
    assert memory.lookup(pair["source_text"], "session", "session", store=store) == []


def test_a_sealed_session_is_served_in_its_domain_not_excluded(store):
    pair = _seal(session_seal.propose(BUNDLE, store=store), store)
    hits = memory.lookup(pair["source_text"], "session", "session", store=store)
    assert [h["pair"]["id"] for h in hits] == [pair["id"]]


@pytest.mark.parametrize("bad, why", [
    ({"actions": [{"did": "x"}]}, "'session' id"),
    ({"session": "s", "actions": []}, "non-empty actions"),
    ({"session": "s", "actions": [{"did": " "}]}, "non-empty 'did'"),
    ({"session": "s", "actions": [{"did": "x", "came_of": "y"}]}, "list of strings"),
])
def test_a_malformed_bundle_is_never_proposed(store, bad, why):
    with pytest.raises(session_seal.SessionBundleError, match=why):
        session_seal.propose(bad, store=store)
    assert memory.lookup("x", "session", "session", store=store) == []


def test_other_domains_never_reach_the_session_check(store, monkeypatch):
    monkeypatch.setattr(session_seal, "require_verified",
                        lambda *a, **k: pytest.fail("checked a non-session pair"))
    got = memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                          status="sealed", verifier="rita", store=store)
    assert got["status"] == "sealed"
