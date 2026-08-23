"""The edge-confirmation ceremony (``nestor ui``) — ``POST /api/edge/seal``,
the Triage tab's Confirm affordance (docs/decision-memory.md N6/N9).

Today the Triage and Graph tabs show *proposed* edges, read-only. This is the
human's ratification: a signed-in human confirms a proposed edge by signing it
in the browser, and only a valid signature writes it. This is a WRITE path
sitting next to the trust root, so — same discipline as
``tests/test_decision_edges.py`` and ``tests/test_client_signed_seals_ui.py``,
which this mirrors one layer up (through ``ui.dispatch`` rather than
``DecisionMemory`` directly) — every test here is an adversarial guard: a
forbidden act, attempted, and the refusal it must produce.

Nothing here forges a human's signature. Every valid signature is produced by
a TEST keyring entry signing its own test key (``bob``, public-only in the
keyring — this instance can verify him and structurally cannot sign for him),
the same fixture shape ``test_decision_edges.py``'s ``sean`` already uses.
"""
from __future__ import annotations

import inspect
import json
import threading
import urllib.error
import urllib.request

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from nestor import cascade, keyring, ledger, signing, storage, ui
from nestor.decision import DecisionMemory
from nestor.sqlite_store import SqliteStore


def get(app, path, **query):
    return ui.dispatch(app, "GET", path, query)


def post(app, path, **payload):
    return ui.dispatch(app, "POST", path, {}, payload)


def _keypair():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return priv, pub


def _sign_edge(priv, src_id, dst_id, kind):
    """Stand in for the browser: only the frozen wire contract
    (``signing._edge_message``) and the private key — never
    ``signing.sign_edge`` or anything else ``ui``/``decision`` expose,
    exactly as ``test_decision_edges.py``'s ``_sign_edge`` and
    ``test_client_signed_seals_ui.py``'s ``_client_sign`` do it."""
    return priv.sign(signing._edge_message(src_id, dst_id, kind)).hex()


@pytest.fixture()
def ring(tmp_path, monkeypatch):
    monkeypatch.delenv("NESTOR_SEAL_KEY", raising=False)
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


@pytest.fixture()
def bob(ring):
    """A public-only ed25519 verifier — this instance can verify bob's
    signatures and can never produce one for him."""
    priv, pub = _keypair()
    ring.add("bob", key=pub, kind="ed25519")
    return priv


@pytest.fixture()
def two_decisions(app):
    dm = DecisionMemory(app.store)
    a = dm.propose("should draft decisions expire after 90 days?",
                   "no — a human seals them by hand, eventually")
    b = dm.propose("should the ledger be compacted on a schedule?",
                   "no — append-only, never rewritten")
    return a["id"], b["id"]


# --- the route exists, and never signs on its own ----------------------------

def test_edge_seal_route_is_registered():
    assert ("POST", "/api/edge/seal") in ui._ROUTES


def test_nothing_in_ui_ever_signs_an_edge():
    """The structural half of 'the machine cannot seal an edge by any route
    reachable from the UI': unlike a decision seal (``memory.add_pair``
    signs SERVER-SIDE when ``seal_sig=""`` and a key is configured),
    ``DecisionMemory.seal_edge`` never calls ``signing.sign_edge`` — it only
    verifies. This asserts ``nestor.ui`` never calls it either, so there is
    no path through this server that manufactures an ``edge_sig`` on a
    caller's behalf; a browser's (or a test's) own private key is the only
    thing that can ever produce one.
    """
    src = inspect.getsource(ui)
    assert "sign_edge(" not in src


# --- the covenant: a valid signature, and only a valid signature, writes -----

class TestAValidSignatureSealsIt:

    def test_seals_it_ledgers_it_and_it_becomes_a_constraint(self, ring, app, bob, two_decisions):
        a, b = two_decisions
        sig = _sign_edge(bob, b, a, "depends_on")

        status, body = post(app, "/api/edge/seal", src_id=b, dst_id=a, kind="depends_on",
                            verifier="bob", edge_sig=sig)

        assert status == 200
        assert body["edge"]["src_id"] == b and body["edge"]["dst_id"] == a
        assert body["edge"]["kind"] == "depends_on"
        assert body["edge"]["verifier"] == "bob"

        # ledgered (N7)
        assert ledger.entries(kind="edge_seal")
        ok, detail = ledger.verify()
        assert ok, detail

        # a fact now: edge_is_valid accepts it, and constraints_on traverses it
        assert signing.edge_is_valid(b, a, "depends_on", "bob", sig)
        on_b = DecisionMemory(app.store).constraints_on(
            "should the ledger be compacted on a schedule?")
        assert on_b["proposed"] == []
        assert len(on_b["constraints"]) == 1
        assert on_b["constraints"][0]["kind"] == "depends_on"
        assert on_b["constraints"][0]["verifier"] == "bob"

    def test_confirmed_over_the_real_socket_with_the_csrf_header(self, ring, app, bob, two_decisions):
        """Drives the actual HTTP-shaped surface a browser talks to, not
        ``dispatch`` directly — same discipline as
        ``test_ui_triage.py::test_csp_and_page_are_unchanged_by_the_triage_view``."""
        a, b = two_decisions
        sig = _sign_edge(bob, b, a, "supersedes")
        httpd = ui.serve(app, "127.0.0.1", 0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            body = json.dumps({"src_id": b, "dst_id": a, "kind": "supersedes",
                               "verifier": "bob", "edge_sig": sig}).encode()
            req = urllib.request.Request(
                base + "/api/edge/seal", data=body,
                headers={"Content-Type": "application/json", "X-Nestor-UI": "1"})
            with urllib.request.urlopen(req) as res:
                out = json.loads(res.read())
            assert out["edge"]["kind"] == "supersedes"
            assert out["edge"]["verifier"] == "bob"
        finally:
            httpd.shutdown()
            httpd.server_close()
        assert ledger.entries(kind="edge_seal")
        ok, detail = ledger.verify()
        assert ok, detail


# --- the forbidden acts, attempted --------------------------------------------

class TestEmptySignatureIsRefused:
    """An edge with no signature is a proposal, never a fact — refused even
    with a perfectly valid, signed-in session naming the verifier."""

    def test_empty_edge_sig_is_refused_even_with_a_valid_session(self, ring, app, two_decisions):
        ring.add("rita")  # hmac — a key this server legitimately HOLDS for rita
        status, body = post(app, "/api/session", verifier="rita",
                            key=ring.get("rita").key.hex())
        assert status == 200
        token = body["token"]
        a, b = two_decisions

        status, body = post(app, "/api/edge/seal", src_id=b, dst_id=a, kind="depends_on",
                            session=token, edge_sig="")

        assert status == 403
        assert body["code"] == "invalid_edge_signature"
        assert app.store.memory_edges_from(b) == []
        assert app.store.memory_edges_to(a) == []
        assert not ledger.entries(kind="edge_seal")

    def test_omitted_edge_sig_is_refused_the_same_way(self, ring, app, bob, two_decisions):
        a, b = two_decisions
        # bob is a real, valid verifier -- but no signature at all was sent.
        status, body = post(app, "/api/edge/seal", src_id=b, dst_id=a, kind="depends_on",
                            verifier="bob")
        # no keyring session and no edge_sig -> _verifier_for_seal falls back
        # to _verifier(), which under a keyring requires a session
        assert status == 401
        assert body["code"] == "session_required"
        assert app.store.memory_edges_from(b) == []


class TestForgedOrWrongFieldSignatureIsRefused:

    def test_signed_by_the_wrong_key_is_refused(self, ring, app, bob, two_decisions):
        a, b = two_decisions
        attacker_priv, _attacker_pub = _keypair()
        forged = attacker_priv.sign(signing._edge_message(b, a, "depends_on")).hex()

        status, body = post(app, "/api/edge/seal", src_id=b, dst_id=a, kind="depends_on",
                            verifier="bob", edge_sig=forged)

        assert status == 403
        assert body["code"] == "invalid_edge_signature"
        assert app.store.memory_edges_from(b) == []
        assert app.store.memory_edges_to(a) == []
        assert not ledger.entries(kind="edge_seal")

    def test_signed_over_different_fields_is_refused(self, ring, app, bob, two_decisions):
        """bob's own, real signature -- but over a different kind. Domain
        separation inside the message, not just key ownership, has to hold."""
        a, b = two_decisions
        wrong_kind_sig = _sign_edge(bob, b, a, "contradicts")

        status, body = post(app, "/api/edge/seal", src_id=b, dst_id=a, kind="depends_on",
                            verifier="bob", edge_sig=wrong_kind_sig)

        assert status == 403
        assert body["code"] == "invalid_edge_signature"
        assert app.store.memory_edges_from(b) == []

    def test_a_seal_signature_cannot_be_replayed_as_an_edge_signature(self, ring, app, bob, two_decisions):
        a, b = two_decisions
        seal_sig = bob.sign(signing._message(
            "should the ledger be compacted on a schedule?",
            "no — append-only, never rewritten", "bob")).hex()

        status, body = post(app, "/api/edge/seal", src_id=b, dst_id=a, kind="depends_on",
                            verifier="bob", edge_sig=seal_sig)

        assert status == 403
        assert body["code"] == "invalid_edge_signature"
        assert app.store.memory_edges_from(b) == []


class TestIdentityResolvesFromTheSessionNeverFromTheTypedName:
    """With a keyring installed, ``_verifier_for_seal`` resolves the verifier
    from the SESSION whenever no signature is offered, and trusts a
    payload-named verifier only on the strength of a signature that is about
    to be checked cryptographically — so a typed name alone, session or not,
    can never seal as somebody else (mirrors ``_seal``'s discipline, decision
    0078, now shared by this endpoint via ``sig_field='edge_sig'``)."""

    def test_verifier_for_seal_resolves_from_the_session_not_the_payload(self, ring, app):
        """Direct unit check of the identity-resolution rule this endpoint
        reuses: with no ``edge_sig`` in the payload, a signed-in session's
        own verifier wins even when the payload names somebody else."""
        ring.add("rita")
        opened = app.sessions.open("rita", ring.get("rita").key.hex())
        resolved = ui._verifier_for_seal(
            app, {"session": opened["token"], "verifier": "mallory"},
            sig_field="edge_sig")
        assert resolved == "rita"

    def test_attribution_follows_the_real_signature_not_whoever_is_signed_in(
            self, ring, app, bob, two_decisions):
        """rita is signed in; the payload carries bob's OWN valid signature
        and claims verifier=bob. The seal is correctly attributed to bob (the
        signature's owner) — rita's session is simply irrelevant here,
        proving the payload's claimed name is trusted only on the strength of
        a signature that verifies for it, never on the session it happens to
        ride alongside."""
        ring.add("rita")
        session = app.sessions.open("rita", ring.get("rita").key.hex())
        a, b = two_decisions
        sig = _sign_edge(bob, b, a, "depends_on")

        status, body = post(app, "/api/edge/seal", src_id=b, dst_id=a, kind="depends_on",
                            session=session["token"], verifier="bob", edge_sig=sig)

        assert status == 200
        assert body["edge"]["verifier"] == "bob"          # attributed to the signer, not rita

    def test_a_spoofed_verifier_with_no_matching_signature_is_refused(
            self, ring, app, bob, two_decisions):
        """The negative case: claiming to be bob (payload verifier='bob')
        while signing with a DIFFERENT, unregistered key is refused — a
        signature that does not verify for the name it claims is exactly
        what edge_is_valid exists to catch, session or no session."""
        ring.add("rita")
        session = app.sessions.open("rita", ring.get("rita").key.hex())
        a, b = two_decisions
        impostor_priv, _pub = _keypair()
        fake_sig = impostor_priv.sign(signing._edge_message(b, a, "depends_on")).hex()

        status, body = post(app, "/api/edge/seal", src_id=b, dst_id=a, kind="depends_on",
                            session=session["token"], verifier="bob", edge_sig=fake_sig)

        assert status == 403
        assert body["code"] == "invalid_edge_signature"
        assert app.store.memory_edges_from(b) == []


class TestReadOnlyRefuses:

    def test_read_only_refuses_a_valid_signed_confirm(self, ring, app, bob, two_decisions):
        app.read_only = True
        a, b = two_decisions
        sig = _sign_edge(bob, b, a, "depends_on")

        status, body = post(app, "/api/edge/seal", src_id=b, dst_id=a, kind="depends_on",
                            verifier="bob", edge_sig=sig)

        assert status == 403
        assert body["code"] == "read_only"
        assert app.store.memory_edges_from(b) == []
        assert not ledger.entries(kind="edge_seal")


class TestCsrfIsEnforced:

    def test_post_without_the_csrf_header_is_refused_over_the_real_socket(
            self, ring, app, bob, two_decisions):
        a, b = two_decisions
        sig = _sign_edge(bob, b, a, "depends_on")
        httpd = ui.serve(app, "127.0.0.1", 0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            body = json.dumps({"src_id": b, "dst_id": a, "kind": "depends_on",
                               "verifier": "bob", "edge_sig": sig}).encode()
            req = urllib.request.Request(
                base + "/api/edge/seal", data=body,
                headers={"Content-Type": "application/json"})   # no X-Nestor-UI
            try:
                urllib.request.urlopen(req)
                assert False, "should have been refused"
            except urllib.error.HTTPError as exc:
                assert exc.code == 403
                assert json.loads(exc.read())["code"] == "csrf"
        finally:
            httpd.shutdown()
            httpd.server_close()
        assert app.store.memory_edges_from(b) == []
        assert not ledger.entries(kind="edge_seal")


class TestMalformedRequestsAreRefused:

    def test_missing_ids_is_a_400(self, app):
        status, body = post(app, "/api/edge/seal", kind="depends_on")
        assert status == 400
        assert body["code"] == "bad_request"

    def test_unknown_kind_is_a_400_bad_request_not_a_signature_refusal(
            self, ring, app, bob, two_decisions):
        a, b = two_decisions
        # bob's real signature, but over a kind outside EDGE_KINDS -- the
        # request is malformed before a signature is even worth checking.
        sig = bob.sign(signing._edge_message(b, a, "grounds")).hex()

        status, body = post(app, "/api/edge/seal", src_id=b, dst_id=a, kind="grounds",
                            verifier="bob", edge_sig=sig)

        assert status == 400
        assert body["code"] == "bad_request"
        assert app.store.memory_edges_from(b) == []


# --- the read-only tabs beside this one are untouched -------------------------

def test_triage_and_graph_endpoints_are_still_read_only(ring, app, two_decisions):
    """The two GET endpoints this PR was told not to touch: no route exists
    from either to a write, however the request is shaped -- same assertion
    ``test_ui_triage.py``/``test_ui_graph.py`` already make, re-run here so a
    regression introduced alongside this endpoint is caught in the same file
    that introduces the risk."""
    status, _out = post(app, "/api/triage")
    assert status == 404
    status, _out = post(app, "/api/graph")
    assert status == 404
    status, _out = get(app, "/api/triage")
    assert status == 200
    status, _out = get(app, "/api/graph")
    assert status == 200
