"""Nestor#17's client-signing seam through ``nestor.ui.dispatch`` (decision 0078).

``tests/test_client_signed_seals.py`` proves ``memory.add_pair``'s ``seal_sig``
contract directly. This file proves the same contract survives the UI layer
wrapped around it: the read-only ``/api/normalize`` endpoint a browser signer
calls before it can build a message to sign, ``_verifier_for_seal`` (the
session bypass a valid signature earns — and does NOT earn where it
shouldn't), and that ``--read-only`` still refuses a client-signed seal
exactly as it refuses a server-signed one.

Simulates the browser the way ``test_client_signed_seals.py`` already does: a
real ``cryptography`` Ed25519 keypair standing in for whatever WebCrypto
produced, signing the documented wire contract directly rather than through
any Nestor helper. ``tests/test_client_signed_seals_browser.py`` is the
Playwright twin of this file — proves the same properties against an actual
browser tab instead of a Python stand-in for one.
"""
from __future__ import annotations

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat)

from nestor import cascade, keyring, memory, signing, storage, ui
from nestor.sqlite_store import SqliteStore


def _keypair():
    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_bytes = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return priv_bytes, pub_bytes


def _client_sign(priv_bytes: bytes, norm: str, target: str, verifier: str) -> str:
    """Stand in for a signer entirely outside this process: only the frozen
    wire contract (``signing._message``) and the private key -- never
    ``signing.sign_seal`` or anything else ``memory``/``ui`` expose."""
    message = signing._message(norm, target, verifier)
    return Ed25519PrivateKey.from_private_bytes(priv_bytes).sign(message).hex()


@pytest.fixture()
def ring(tmp_path):
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    r = keyring.Keyring()
    keyring.set_keyring(r)
    yield r
    keyring.set_keyring(None)


@pytest.fixture()
def app(ring):
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    return ui.App(store=store, source_lang="en", target_lang="es", db_path=":memory:")


def get(app, path, **query):
    return ui.dispatch(app, "GET", path, query)


def post(app, path, **payload):
    return ui.dispatch(app, "POST", path, {}, payload)


class TestNormalizeIsReadOnlyAndWritesNothing:
    """The one new endpoint this feature adds: read-only, and exempt from
    ``--read-only`` for exactly that reason."""

    def test_returns_the_same_norm_a_seal_would_bind_to(self, app):
        status, body = post(app, "/api/normalize", text="  Hello, World!  ",
                            source_lang="en", target_lang="es")
        assert status == 200
        assert body["source_norm"] == memory.get_matcher(None).normalize("  Hello, World!  ")

    def test_writes_nothing(self, app):
        post(app, "/api/normalize", text="a phrase nobody sealed",
            source_lang="en", target_lang="es")
        assert memory.stats(store=app.store)["total"] == 0

    def test_allowed_under_read_only(self, app):
        # This is the property the mandate calls out explicitly: a READ-ONLY
        # normalize must still work under --read-only, unlike a seal.
        app.read_only = True
        status, body = post(app, "/api/normalize", text="hello",
                            source_lang="en", target_lang="es")
        assert status == 200
        assert "source_norm" in body

    def test_nothing_to_normalize_is_refused(self, app):
        status, body = post(app, "/api/normalize", source_lang="en", target_lang="es")
        assert status == 400
        assert body["code"] == "bad_request"


class TestClientSignedSealThroughDispatch:
    """The acceptance property from decision 0077, driven through the actual
    HTTP-shaped surface a browser talks to, not the library call underneath."""

    def test_a_public_only_verifier_seals_through_the_api(self, ring, app):
        priv, pub = _keypair()
        ring.add("bob", key=pub, kind="ed25519")
        norm = memory.get_matcher(None).normalize("good evening")
        sig = _client_sign(priv, norm, "buenas noches", "bob")

        status, body = post(app, "/api/seal", source="good evening", target="buenas noches",
                            verifier="bob", seal_sig=sig)

        assert status == 200
        assert body["pair"]["status"] == "sealed"
        assert body["pair"]["verifier"] == "bob"
        assert memory.best_sealed("good evening", "en", "es", store=app.store)
        # Fails on the unfixed code: no `seal_sig` field on the route at all,
        # and `_verifier` would 401 (no session exists, and none COULD for a
        # public-only entry -- see the next test).

    def test_no_session_is_needed_when_the_signature_verifies(self, ring, app):
        """The reason _verifier_for_seal exists: bob has no server-held
        secret to sign in WITH, so /api/session is categorically unusable for
        him -- confirmed here, not assumed -- and the seal must still work."""
        priv, pub = _keypair()
        ring.add("bob", key=pub, kind="ed25519")

        status, _ = post(app, "/api/session", verifier="bob", key=pub.hex())
        # 400, not 403: `Sessions.open` calls `Keyring.signing_key`, which
        # raises `KeyringError` (not `UnknownVerifierError`/`RevokedKeyError`,
        # the only two it catches) for an entry holding no private half --
        # `dispatch`'s generic RuntimeError handler turns that into a 400.
        assert status == 400

        norm = memory.get_matcher(None).normalize("good evening")
        sig = _client_sign(priv, norm, "buenas noches", "bob")
        status, body = post(app, "/api/seal", source="good evening", target="buenas noches",
                            verifier="bob", seal_sig=sig)
        assert status == 200

    def test_a_forged_signature_is_refused_before_any_write(self, ring, app):
        _priv, pub = _keypair()
        attacker_priv, _attacker_pub = _keypair()
        ring.add("bob", key=pub, kind="ed25519")
        norm = memory.get_matcher(None).normalize("good evening")
        forged = _client_sign(attacker_priv, norm, "buenas noches", "bob")

        status, body = post(app, "/api/seal", source="good evening", target="buenas noches",
                            verifier="bob", seal_sig=forged)

        assert status == 400
        assert body["code"] == "invalid_seal_signature"
        assert app.store.memory_find(norm, "en", "es") is None

    def test_read_only_refuses_a_client_signed_seal(self, ring, app):
        priv, pub = _keypair()
        ring.add("bob", key=pub, kind="ed25519")
        norm = memory.get_matcher(None).normalize("good evening")
        sig = _client_sign(priv, norm, "buenas noches", "bob")
        app.read_only = True

        status, body = post(app, "/api/seal", source="good evening", target="buenas noches",
                            verifier="bob", seal_sig=sig)

        assert status == 403
        assert body["code"] == "read_only"
        assert app.store.memory_find(norm, "en", "es") is None

    def test_seal_draft_also_accepts_it(self, ring, app):
        priv, pub = _keypair()
        ring.add("bob", key=pub, kind="ed25519")
        draft = memory.add_pair("a draft phrase", "una frase", "en", "es", store=app.store)
        sig = _client_sign(priv, draft["source_norm"], "una frase corregida", "bob")

        status, body = post(app, "/api/seal-draft", pair_id=draft["id"],
                            target="una frase corregida", verifier="bob", seal_sig=sig)

        assert status == 200
        assert body["pair"]["status"] == "sealed"
        assert body["pair"]["verifier"] == "bob"

    def test_queue_seal_edited_branch_accepts_it(self, ring, app):
        priv, pub = _keypair()
        ring.add("bob", key=pub, kind="ed25519")
        doc = app.store.create_document("a document", "en", "es")
        seg = app.store.create_segment(doc["id"], 0, "the monthly report", "el informe", 0.8)
        norm = memory.get_matcher(None).normalize("the monthly report")
        sig = _client_sign(priv, norm, "el informe mensual corregido", "bob")

        status, body = post(app, "/api/queue/seal", segment_id=seg["id"],
                            target="el informe mensual corregido", verifier="bob", seal_sig=sig)

        assert status == 200
        assert body["edited"] is True
        assert body["pair"]["status"] == "sealed"
        assert body["pair"]["verifier"] == "bob"

    def test_queue_seal_as_drafted_still_needs_a_session_not_a_signature(self, ring, app):
        """Regression guard for an authentication-bypass bug this PR
        introduced and then found and fixed while wiring the browser signer
        into the UI.

        `graduate_segment` (the as-drafted branch) has no `seal_sig`
        parameter and never checks one -- it signs SERVER-SIDE, exactly as it
        always has. An earlier draft of `_queue_seal` resolved the verifier
        with `_verifier_for_seal` ONCE, before branching, so ANY non-empty
        `seal_sig` -- garbage, unrelated, signed by nobody with sam's key at
        all -- was enough to skip the session check entirely; the request
        then reached `graduate_segment`, which happily AUTO-SIGNED a sealed
        row as "sam" using the key this server already holds for him. Verified
        directly against that code (before the fix in this PR): a random
        Ed25519 keypair signing the literal bytes ``b"anything"`` -- nothing
        to do with sam, this segment, or the frozen wire contract -- still
        produced a 200 and a genuinely, validly sealed row attributed to sam,
        with no session ever presented. That is a full authentication bypass
        for every HMAC or private-half verifier in the keyring, reachable by
        anyone who can reach this endpoint at all. Fixed by resolving the
        verifier PER BRANCH: `_verifier_for_seal` only where the signature is
        actually forwarded and checked (see decision 0078).
        """
        ring.add("sam")  # hmac -- the server CAN and, unfixed, WOULD auto-sign for him
        doc = app.store.create_document("a document", "en", "es")
        seg = app.store.create_segment(doc["id"], 0, "the monthly report", "el informe", 0.8)
        # The attacker holds no key for sam at all -- a signature over bytes
        # with nothing to do with sam, this segment, or the wire contract.
        attacker_priv, _attacker_pub = _keypair()
        garbage_sig = Ed25519PrivateKey.from_private_bytes(attacker_priv).sign(b"anything").hex()

        status, body = post(app, "/api/queue/seal", segment_id=seg["id"], target="el informe",
                            verifier="sam", seal_sig=garbage_sig)

        assert status == 401
        assert body["code"] == "session_required"
        # And nothing was sealed under sam's name as a side effect.
        assert app.store.get_segment(seg["id"])["status"] != "verified"
        assert memory.best_sealed("the monthly report", "en", "es", store=app.store) is None

    def test_a_hmac_or_private_half_verifier_can_still_seal_the_old_way(self, ring, app):
        """seal_sig is additive: a verifier whose key lives on this server
        (HMAC, or ed25519 with the private half present) is untouched."""
        ring.add("sam")  # hmac, the default kind
        status, body = post(app, "/api/session", verifier="sam", key=ring.get("sam").key.hex())
        assert status == 200
        token = body["token"]

        status, body = post(app, "/api/seal", source="good morning", target="buenos días",
                            session=token)
        assert status == 200
        assert body["pair"]["status"] == "sealed"
        assert body["pair"]["seal_sig"]
