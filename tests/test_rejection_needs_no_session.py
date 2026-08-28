"""A rejection must never be refused for want of a session.

This exists because of a defect measured on a live instance 2026-08-28. The
keyring there held one entry — an ed25519 PUBLIC-only key. `Keyring.signing_entry`
refuses such an entry ("a keyring that can verify a peer must not be able to sign
as them"), and `Sessions.open` checks a typed secret against `Keyring.signing_key`,
which a public-only entry does not have. So no session could ever be opened.

Seals still worked: `_verifier_for_seal` accepts a browser signature, and the
browser holds the private half. Rejections went through `_verifier`, which with a
keyring installed demands a session — so the operator **could seal and could never
reject**, in the surface whose entire premise is that a human may do either.

Every layer below the UI is built the other way round:

* `signing._rejection_sign_ref` — "refusing to record a 'no' is the one direction
  rejection cannot fail in ... An unknown verifier's rejection is recorded,
  honored, and reported as unsigned."
* `signing.rejection_is_valid` — "reporting only — Nestor honors a rejection
  whether or not it verifies."
* `memory.reject_pair(pair_id, verifier: str = "")` — accepts an unnamed one.

So the UI was the only layer that could refuse a "no", and it did so silently: the
401 reads as a login prompt rather than as an impossibility.
"""
from __future__ import annotations

import pytest

from nestor import ui


class _Store:
    """Minimal store stand-in: rejection-capable, nothing else exercised."""


class _Sessions:
    """A Sessions that never recognises anybody — the live situation, where no
    session can be opened at all because the entry has no private half."""

    def whois(self, token):
        return None


class _App:
    def __init__(self):
        self.store = _Store()
        self.sessions = _Sessions()
        self.source_lang = "en"
        self.target_lang = "es"


def _payload(**kw):
    base = {"verifier": "sean campbell", "pair_id": "p-1", "reason": "wrong mapping"}
    base.update(kw)
    return base


# ── the property that was broken ───────────────────────────────────────────

def test_a_rejection_resolves_its_verifier_without_a_session(monkeypatch):
    """With a keyring enabled and no session obtainable, a rejection must still
    name its verifier rather than raising 401."""
    monkeypatch.setattr(ui.keyring, "enabled", lambda: True)
    who = ui._verifier_for_rejection(_App(), _payload())
    assert who == "sean campbell"


def test_the_old_path_would_have_refused_the_same_call(monkeypatch):
    """Prove-it-can-fail, against the real prior behaviour rather than a
    synthetic one: `_verifier` raises 401 for exactly the payload above, which
    is why rejection was unreachable."""
    monkeypatch.setattr(ui.keyring, "enabled", lambda: True)
    with pytest.raises(ui.ApiError) as e:
        ui._verifier(_App(), _payload())
    assert e.value.status == 401
    assert e.value.code == "session_required"


def test_rejection_still_needs_a_name(monkeypatch):
    """Attribution, not authentication. A name is always satisfiable by typing
    one — a session is not — so requiring it blocks nobody."""
    monkeypatch.setattr(ui.keyring, "enabled", lambda: True)
    with pytest.raises(ui.ApiError) as e:
        ui._verifier_for_rejection(_App(), _payload(verifier=""))
    assert e.value.status == 400
    assert e.value.code == "verifier_required"


def test_it_behaves_the_same_with_no_keyring(monkeypatch):
    """The whole point is that rejection does not branch on keyring state."""
    monkeypatch.setattr(ui.keyring, "enabled", lambda: False)
    assert ui._verifier_for_rejection(_App(), _payload()) == "sean campbell"


# ── the seal path must be untouched ────────────────────────────────────────

def test_seals_still_require_proof_when_no_signature_is_supplied(monkeypatch):
    """The asymmetry is the point: a seal without a signature still needs a
    session. Widening rejection must not widen sealing."""
    monkeypatch.setattr(ui.keyring, "enabled", lambda: True)
    with pytest.raises(ui.ApiError) as e:
        ui._verifier_for_seal(_App(), _payload(), sig_field="seal_sig")
    assert e.value.status == 401


def test_a_signed_seal_still_authenticates_by_signature(monkeypatch):
    monkeypatch.setattr(ui.keyring, "enabled", lambda: True)
    who = ui._verifier_for_seal(_App(), _payload(seal_sig="abc123"),
                                sig_field="seal_sig")
    assert who == "sean campbell"


# ── the endpoints actually use it ──────────────────────────────────────────

@pytest.mark.parametrize("fn", ["_reject_pair", "_reject_match", "_queue_reject"])
def test_every_rejection_endpoint_uses_the_rejection_verifier(fn):
    """Read from the source rather than a roster kept here, so a fourth
    rejection endpoint added later is covered the moment it is written."""
    import inspect
    src = inspect.getsource(getattr(ui, fn))
    assert "_verifier_for_rejection" in src, (
        f"{fn} does not resolve its verifier through _verifier_for_rejection; "
        f"a keyring-only operator cannot reach it"
    )


def test_no_seal_endpoint_uses_the_rejection_verifier():
    """The inverse guard. Sealing through the rejection path would drop the
    signature requirement entirely."""
    import inspect
    for fn in ("_seal", "_seal_draft", "_queue_seal"):
        f = getattr(ui, fn, None)
        if f is None:
            continue
        assert "_verifier_for_rejection" not in inspect.getsource(f), (
            f"{fn} resolves its verifier through the rejection path — that would "
            f"let an unauthenticated caller mint a seal"
        )
