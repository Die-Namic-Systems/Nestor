"""Per-verifier identity: a seal that names a person, and can be checked.

The gap this closes (TODO §1, QUESTIONS §6): everything about trust here was
rigorous except the *name*. A seal was bound to a key the store does not hold —
but one key for the whole deployment, so a valid signature proved the key was
present and nothing about who used it. `verifier="rita"` stayed a string anybody
who could reach the process could type.
"""
import json
import os
import stat

import pytest

from nestor import keyring, memory, signing
from nestor.curator import Curator
from nestor.ui import App, Sessions, dispatch


@pytest.fixture
def ring(tmp_path):
    k = keyring.Keyring(path=str(tmp_path / "keys.json"))
    k.add("rita")
    k.add("sam")
    k.save()
    keyring.set_keyring(k)
    os.environ.pop("NESTOR_SEAL_KEY", None)
    return k


# --- what a signature now proves --------------------------------------------

def test_a_seal_is_signed_by_the_verifier_it_names(ring, store):
    pair = memory.add_pair("the invoice is overdue", "la factura está vencida",
                           "en", "es", status="sealed", verifier="rita", store=store)
    assert pair["seal_sig"]
    assert memory.is_verified_seal(pair)
    # sam's key does not produce rita's signature. That is the whole feature:
    # holding *a* key is no longer the same as being *the* verifier.
    assert not signing.seal_is_valid(pair["source_norm"], pair["target_text"],
                                     "rita", pair["seal_sig"], key=ring.get("sam").key)


def test_a_name_the_keyring_does_not_know_cannot_seal(ring, store):
    with pytest.raises(keyring.UnknownVerifierError, match="not in the keyring"):
        memory.add_pair("kindly remit", "sírvase remitir", "en", "es",
                        status="sealed", verifier="mallory", store=store)
    # And nothing was written: the refusal comes from sign_seal, which add_pair
    # reaches before it touches the store.
    assert memory.stats(store=store)["total"] == 0


def test_relabelling_a_seal_as_someone_else_stops_it_serving(ring, store):
    """The forgery the keyring closes: a store-writer moving a real signature
    onto a more senior name."""
    pair = memory.add_pair("the invoice is overdue", "la factura está vencida",
                           "en", "es", status="sealed", verifier="sam", store=store)
    store.memory_seal(pair["id"], pair["target_text"], "rita", 1.0, pair["seal_sig"])
    assert memory.best_sealed("the invoice is overdue", "en", "es", store=store) is None


def test_a_draft_still_needs_no_key(ring, store):
    """Only a seal makes a claim about a person. Drafts are machine output."""
    memory.add_pair("a draft", "un borrador", "en", "es", store=store)
    assert memory.stats(store=store)["draft"] == 1


# --- revocation: the question the operator has to answer ---------------------

def test_a_rotated_key_keeps_its_past_seals(ring, store):
    """rita left. Nobody else held her key, so her verifications still stand."""
    memory.add_pair("the invoice is overdue", "la factura está vencida", "en", "es",
                    status="sealed", verifier="rita", store=store)
    ring.revoke("rita", reason="left the team")

    assert memory.best_sealed("the invoice is overdue", "en", "es", store=store)
    with pytest.raises(keyring.RevokedKeyError, match="cannot make new seals"):
        memory.add_pair("net thirty", "treinta días netos", "en", "es",
                        status="sealed", verifier="rita", store=store)


def test_a_compromised_key_loses_its_seals(ring, store):
    """The key was taken. An HMAC carries no timestamp, so nothing it signed can
    be told apart from what the thief signed — none of it serves."""
    memory.add_pair("the invoice is overdue", "la factura está vencida", "en", "es",
                    status="sealed", verifier="rita", store=store)
    memory.add_pair("net thirty", "treinta días netos", "en", "es",
                    status="sealed", verifier="sam", store=store)
    ring.revoke("sam", reason="laptop stolen", compromised=True)

    assert memory.best_sealed("the invoice is overdue", "en", "es", store=store)
    assert memory.best_sealed("net thirty", "en", "es", store=store) is None
    # Not deleted, not altered — surfaced where a human re-verifies it.
    unverifiable = Curator(store).unverifiable()
    assert [(p["source_text"], p["key_status"]) for p in unverifiable] == \
        [("net thirty", "compromised")]


def test_compromised_is_one_way(ring):
    ring.revoke("sam", compromised=True)
    ring.revoke("sam", reason="second thoughts")
    assert ring.status("sam") == "compromised"


def test_rotating_a_key_needs_saying_so(ring):
    with pytest.raises(keyring.KeyringError, match="already has a key"):
        ring.add("rita")
    old = ring.get("rita").key
    assert ring.add("rita", rotate=True).key != old


# --- migration: seals that predate the keyring -------------------------------

def test_seals_from_the_shared_key_era_can_be_adopted(tmp_path, store):
    os.environ['NESTOR_SEAL_KEY'] = 'the-old-deployment-key'
    pair = memory.add_pair("the invoice is overdue", "la factura está vencida",
                           "en", "es", status="sealed", verifier="rita", store=store)
    assert memory.is_verified_seal(pair)

    # Turn on per-verifier keys, adopting the old key so history survives.
    k = keyring.Keyring(legacy_key=b"the-old-deployment-key", path=str(tmp_path / "k.json"))
    k.add("rita")
    keyring.set_keyring(k)
    os.environ.pop("NESTOR_SEAL_KEY", None)

    assert memory.best_sealed("the invoice is overdue", "en", "es", store=store)
    row = Curator(store).get(pair["id"])
    assert row["signed_by"] == "legacy", "verified by somebody here, not by a person"
    assert row["servable"] is True
    assert Curator(store).summary()["sealed_legacy"] == 1

    # Without adopting it, the same rows are unverifiable rather than silently
    # trusted — the stricter road to the same place.
    keyring.set_keyring(keyring.Keyring([k.get("rita")], path=str(tmp_path / "k2.json")))
    assert memory.best_sealed("the invoice is overdue", "en", "es", store=store) is None


def test_without_a_keyring_nothing_changes(store):
    """The whole feature is opt-in; the shared-key deployment is untouched."""
    os.environ['NESTOR_SEAL_KEY'] = 'one-key'
    keyring.set_keyring(None)
    for who in ("rita", "mallory", ""):
        pair = memory.add_pair(f"phrase {who}", f"frase {who}", "en", "es",
                               status="sealed", verifier=who, store=store)
        assert memory.is_verified_seal(pair)
    assert Curator(store).list()[0].get("key_status") is None


# --- the file holds every key in the deployment ------------------------------

def test_a_saved_keyring_is_owner_only(ring):
    assert stat.S_IMODE(os.stat(ring.path).st_mode) == 0o600


def test_a_world_readable_keyring_is_refused(ring):
    os.chmod(ring.path, 0o644)
    with pytest.raises(keyring.KeyringError, match="readable by other users"):
        keyring.load(ring.path)


def test_a_keyring_round_trips(ring):
    ring.revoke("sam", reason="left", compromised=False)
    ring.save()
    again = keyring.load(ring.path)
    assert again.names() == ["rita", "sam"]
    assert again.status("sam") == "revoked"
    assert again.get("rita").key == ring.get("rita").key


def test_a_key_that_is_not_hex_is_refused(tmp_path):
    p = tmp_path / "k.json"
    p.write_text(json.dumps({"verifiers": [{"name": "rita", "key": "not hex"}]}))
    os.chmod(p, 0o600)
    with pytest.raises(keyring.KeyringError, match="not hex"):
        keyring.load(str(p))


# --- rejection fails the other way ------------------------------------------

def test_an_unknown_verifier_can_still_reject(ring, store):
    """A seal by an unregistered name must fail loudly. A *rejection* must not —
    refusing to record a 'no' leaves a bad answer serving."""
    pair = memory.add_pair("the invoice is overdue", "la factura está vencida",
                           "en", "es", status="sealed", verifier="rita", store=store)
    memory.reject_match("the invoice is overdue", "en", "es", pair_id=pair["id"],
                        verifier="a-contractor", reason="wrong register", store=store)
    assert memory.best_sealed("the invoice is overdue", "en", "es", store=store) is None
    report = memory.rejection_signature_report("the invoice is overdue", "en", "es",
                                               store=store)
    assert report[0]["signature_valid"] is False, "honored, and reported as unsigned"


# --- the UI session ----------------------------------------------------------

@pytest.fixture
def app(ring, store):
    return App(store=store, source_lang="en", target_lang="es")


def sign_in(app, who, key):
    return dispatch(app, "POST", "/api/session", {},
                    {"verifier": who, "key": key.hex() if isinstance(key, bytes) else key})


def test_a_decision_needs_a_session_not_a_typed_name(app, ring):
    status, out = dispatch(app, "POST", "/api/seal", {},
                           {"source": "net thirty", "target": "treinta días netos",
                            "verifier": "rita"})
    assert status == 401 and out["code"] == "session_required"
    assert memory.stats(store=app.store)["total"] == 0


def test_signing_in_needs_the_right_key(app, ring):
    assert sign_in(app, "rita", b"\x00" * 32)[0] == 403
    assert sign_in(app, "mallory", ring.get("rita").key)[0] == 403
    status, out = sign_in(app, "rita", ring.get("rita").key)
    assert status == 200 and out["verifier"] == "rita" and out["token"]


def test_a_session_seals_as_the_verifier_who_signed_in(app, ring):
    token = sign_in(app, "rita", ring.get("rita").key)[1]["token"]
    # The typed name is ignored entirely: the session is the answer to "who".
    status, out = dispatch(app, "POST", "/api/seal", {},
                           {"source": "net thirty", "target": "treinta días netos",
                            "verifier": "sam", "session": token})
    assert status == 200
    assert out["pair"]["verifier"] == "rita"
    assert out["pair"]["servable"] is True


def test_a_revoked_verifier_cannot_sign_in(app, ring):
    ring.revoke("sam", reason="left")
    status, out = sign_in(app, "sam", ring.get("sam").key)
    assert status == 403 and out["code"] == "revoked_key"


def test_a_session_ends(app, ring):
    token = sign_in(app, "rita", ring.get("rita").key)[1]["token"]
    dispatch(app, "POST", "/api/session/end", {}, {"session": token})
    status, _ = dispatch(app, "POST", "/api/seal", {},
                         {"source": "x", "target": "y", "session": token})
    assert status == 401


def test_a_session_expires(app, ring):
    app.sessions = Sessions(hours=0)
    token = app.sessions.open("rita", ring.get("rita").key.hex())["token"]
    assert app.sessions.whois(token) is None


def test_state_says_who_may_seal_and_who_is_signed_in(app, ring):
    token = sign_in(app, "rita", ring.get("rita").key)[1]["token"]
    state = dispatch(app, "GET", "/api/state", {"session": token})[1]
    assert state["identity"]["required"] is True
    assert state["identity"]["verifiers"] == ["rita", "sam"]
    assert state["identity"]["signed_in"] == "rita"
    # The names are on every seal already. The keys never leave the file.
    assert "key" not in json.dumps(state)


def test_signing_in_survives_read_only(store, ring):
    """--read-only refuses decisions. Saying who is looking is not one."""
    ro = App(store=store, read_only=True)
    assert sign_in(ro, "rita", ring.get("rita").key)[0] == 200
    assert dispatch(ro, "POST", "/api/seal", {},
                    {"source": "x", "target": "y"})[0] == 403


# --- the injection seam has to win, and the suite has to be hermetic ---------
#
# Reported by the first person to install this: `pytest -q` gave 125 failed /
# 98 errors on a machine where NESTOR_KEYRING was exported — which the README
# tells you to export. Two distinct defects behind one symptom.

def test_an_injected_keyring_wins_over_the_environment(tmp_path):
    """`set_keyring` is the injection seam; the variable is the default it
    overrides. It used to be the other way round whenever the two disagreed."""
    theirs = keyring.Keyring(path=str(tmp_path / "theirs.json"))
    theirs.add("rita")
    theirs.save()
    os.environ["NESTOR_KEYRING"] = str(theirs.path)

    mine = keyring.Keyring(path=str(tmp_path / "mine.json"))
    mine.add("bob")
    keyring.set_keyring(mine)

    assert keyring.get_keyring().names() == ["bob"]
    # And clearing the injection hands control back to the environment.
    keyring.set_keyring(None)
    assert keyring.get_keyring().names() == ["rita"]


def test_an_injected_keyring_wins_even_with_no_path_of_its_own(tmp_path):
    """A Keyring built in memory has path="" — it must not be treated as
    "nothing was injected"."""
    theirs = keyring.Keyring(path=str(tmp_path / "theirs.json"))
    theirs.add("rita")
    theirs.save()
    os.environ["NESTOR_KEYRING"] = str(theirs.path)

    inline = keyring.Keyring()
    inline.add("bob")
    keyring.set_keyring(inline)
    assert keyring.get_keyring().names() == ["bob"]


def test_the_suite_does_not_inherit_the_developers_environment():
    """conftest's isolate_globals unsets these for the duration. If this ever
    fails, every test that seals under a name starts depending on the shell
    the suite was launched from."""
    import os

    from conftest import CONFIGURED_BY_ENV

    for name in CONFIGURED_BY_ENV:
        assert name not in os.environ, f"{name} leaked into the test environment"
    # A test that wants one still sets it, and it takes effect normally.
    os.environ['NESTOR_SEAL_KEY'] = 'k'
    assert signing.signing_enabled()


# --- a configured-but-unusable keyring refuses cleanly, and early ------------
#
# Reported on first launch: NESTOR_KEYRING was exported, the file had never been
# created (the `keys add` that would have made it was the command that hit
# `command not found`), and `nestor ui` died with a raw traceback — after
# printing its banner and binding the port, so it read as "started, then
# exploded". The short-lived CLI commands refused cleanly for the same
# misconfiguration, which is the inconsistency that made it a bug rather than
# an unfriendly message.

def test_a_missing_keyring_file_says_which_variable_sent_you_there(tmp_path):
    os.environ["NESTOR_KEYRING"] = str(tmp_path / "never-made.json")
    with pytest.raises(keyring.KeyringError) as caught:
        keyring.get_keyring()
    message = str(caught.value)
    assert "never-made.json" in message
    assert "NESTOR_KEYRING" in message, "say which variable is sending them there"
    assert "unset NESTOR_KEYRING" in message, "and how to get out of it"


def test_a_configured_keyring_is_never_silently_ignored(tmp_path):
    """The refusal itself is right: identity that is switched on and unreadable
    must not degrade to off, or the operator believes seals name a person when
    they do not."""
    os.environ["NESTOR_KEYRING"] = str(tmp_path / "never-made.json")
    with pytest.raises(keyring.KeyringError):
        keyring.enabled()


def test_preflight_refuses_before_a_surface_binds_anything(tmp_path, capsys):
    os.environ["NESTOR_KEYRING"] = str(tmp_path / "never-made.json")
    from nestor import serve as serve_mod
    from nestor import ui as ui_mod

    for surface in (ui_mod, serve_mod):
        assert surface.main(["--db", str(tmp_path / "n.db")]) == 2
        out = capsys.readouterr()
        assert "refusing to start" in out.err
        assert "Nestor UI" not in out.out, "no banner: it must refuse before it binds"
        assert not (tmp_path / "n.db").exists(), "and before it opens the store"


def test_preflight_is_quiet_when_there_is_nothing_wrong(tmp_path):
    assert keyring.preflight() is None            # no keyring configured at all

    ring = keyring.Keyring(path=str(tmp_path / "k.json"))
    ring.add("rita")
    ring.save()
    os.environ["NESTOR_KEYRING"] = str(ring.path)
    assert keyring.preflight().names() == ["rita"]
