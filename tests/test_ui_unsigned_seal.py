"""A UI started without the signing key must not write seals that carry a
verifier's name and no signature into a store where that verifier signs.

Measured 2026-09-10: twelve rows sealed through ``nestor ui`` with an empty
``seal_sig``, found only when ``dogfood_seal_export`` refused them. The store
had signed seals by the same verifier beside them, so the evidence to refuse
was there the whole time.
"""
from __future__ import annotations

import os
import warnings

import pytest

from nestor import cascade, memory, storage, ui
from nestor.sqlite_store import SqliteStore


def _app(tmp_path):
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    return ui.App(store=store, source_lang="en", target_lang="es", db_path=":memory:")


def _post(app, path, **payload):
    return ui.dispatch(app, "POST", path, {}, payload)


def _unset_keys(monkeypatch):
    for name in ("NESTOR_SEAL_KEY", "NESTOR_KEYRING", "NESTOR_REQUIRE_SEAL_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def app_with_a_signed_seal(tmp_path, seal_key):
    """One signed seal by rita, made while the key was present."""
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    app = _app(tmp_path)
    pair = memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                           status="sealed", verifier="rita", store=app.store)
    assert pair["seal_sig"]
    return app


def test_ui_refuses_an_unsigned_seal_for_a_verifier_who_signs(app_with_a_signed_seal,
                                                                monkeypatch):
    app = app_with_a_signed_seal
    _unset_keys(monkeypatch)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        status, body = _post(app, "/api/seal", source="the monthly report",
                             target="el informe mensual", verifier="rita")
    assert status == 403
    assert body["code"] == "unsigned_seal"
    assert "Nothing was written" in body["error"]
    assert app.store.memory_find("the monthly report", "en", "es") is None
    # The signed row is untouched.
    assert app.store.memory_find("the annual invoice", "en", "es")["seal_sig"]


def test_ui_seal_draft_is_refused_the_same_way(app_with_a_signed_seal, monkeypatch):
    app = app_with_a_signed_seal
    memory.add_pair("a draft phrase", "una frase", "en", "es", store=app.store)
    draft = app.store.memory_find("a draft phrase", "en", "es")
    _unset_keys(monkeypatch)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        status, body = _post(app, "/api/seal-draft", pair_id=draft["id"], verifier="rita")
    assert status == 403, body
    assert body["code"] == "unsigned_seal"
    assert app.store.memory_get(draft["id"])["status"] != "sealed"


def test_a_store_with_no_signed_seals_keeps_the_legacy_degrade(tmp_path, monkeypatch):
    """Opt-in by evidence: a fresh store with no key still seals (and warns),
    exactly as before. This is what lets a first checkout seal anything."""
    _unset_keys(monkeypatch)
    app = _app(tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        status, body = _post(app, "/api/seal", source="the monthly report",
                             target="el informe mensual", verifier="rita")
    assert status == 200, body
    assert body["pair"]["seal_sig"] == ""


def test_a_different_verifier_is_not_gated_by_ritas_signatures(app_with_a_signed_seal,
                                                               monkeypatch):
    """The evidence is per verifier: someone the store has never seen signed
    is still on the legacy path. Whether that is right is a policy question
    (a verifier allowlist answers it); this gate only closes the forgery."""
    app = app_with_a_signed_seal
    _unset_keys(monkeypatch)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        status, body = _post(app, "/api/seal", source="the monthly report",
                             target="el informe mensual", verifier="sam")
    assert status == 200, body


def test_require_seal_key_refuses_everywhere_as_before(tmp_path, monkeypatch):
    _unset_keys(monkeypatch)
    monkeypatch.setenv("NESTOR_REQUIRE_SEAL_KEY", "1")
    app = _app(tmp_path)
    status, body = _post(app, "/api/seal", source="the monthly report",
                         target="el informe mensual", verifier="rita")
    assert status == 400
    assert "NESTOR_REQUIRE_SEAL_KEY" in body["error"]


def test_helper_is_read_only_and_evidence_based(app_with_a_signed_seal):
    store = app_with_a_signed_seal.store
    assert memory.verifier_has_signed_seals(store, "rita") is True
    assert memory.verifier_has_signed_seals(store, "sam") is False
    assert memory.verifier_has_signed_seals(store, "") is False
