"""`nestor keys add <name> --type ed25519` must print the key that signs in.

Nestor#99: :func:`nestor.cli.cmd_keys` printed ``entry.key`` unconditionally —
the PUBLIC half for an ed25519 entry — labelled "the only time it is printed,
{name} needs it to sign in to the UI". But :meth:`nestor.ui.Sessions.open`
authenticates against :meth:`nestor.keyring.Keyring.signing_key`, which is the
PRIVATE half for ed25519. So the enrolled verifier was handed the non-signing
key, told it was their sign-in key, and got a 403.

These tests attempt the forbidden outcome — sign in with exactly what the CLI
printed — and assert it now succeeds. Before the fix ``Sessions.open`` raises
``ApiError(403, code="bad_key")`` (the printed public key is not the signing
half); after the fix the printed key opens a session.
"""
from __future__ import annotations

import json

import pytest

# The [keys] extra: an ed25519 keypair cannot be generated without it, and this
# whole bug only exists for ed25519. Skip cleanly where it is absent rather than
# fail on an unrelated import.
pytest.importorskip("cryptography")

from nestor import cli
from nestor import keyring as keyring_mod
from nestor.ui import ApiError, Sessions


def _add_ed25519(name: str, path, capsys, *, as_json: bool = True) -> str:
    """Run `nestor keys add <name> --type ed25519` and return what it PRINTED as
    the sign-in key — the JSON ``key`` field, or the lone 64-hex token in the
    human block."""
    # `--json` is a global flag, so it precedes the subcommand.
    argv = (["--json"] if as_json else []) + [
        "keys", "add", name, "--type", "ed25519", "--keyring", str(path)]
    rc = cli.main(argv)
    out = capsys.readouterr().out
    assert rc == 0, out
    if as_json:
        payload = json.loads(out)
        # The field the CLI presents as the thing the verifier signs in with.
        printed = payload.get("key")
        assert printed, f"no sign-in 'key' in add output: {payload!r}"
        return printed
    hexes = [tok for tok in out.replace("\n", " ").split() if _is_key_hex(tok)]
    assert len(hexes) == 1, f"expected exactly one 32-byte hex key, got {hexes}"
    return hexes[0]


def _is_key_hex(tok: str) -> bool:
    if len(tok) != 64:
        return False
    try:
        bytes.fromhex(tok)
    except ValueError:
        return False
    return True


@pytest.fixture(autouse=True)
def _no_ambient_keyring(monkeypatch):
    """Neither NESTOR_KEYRING nor a cached injection may decide who can seal."""
    monkeypatch.delenv("NESTOR_KEYRING", raising=False)
    keyring_mod.set_keyring(None)
    yield
    keyring_mod.set_keyring(None)


def _open_session(name: str, path, key_hex: str) -> dict:
    """Open a session exactly as `POST /api/session` does — Sessions.open over
    the keyring on disk. Raises ApiError(403) when ``key_hex`` is not the half
    the server checks."""
    keyring_mod.set_keyring(keyring_mod.load(str(path)))
    try:
        return Sessions().open(name, key_hex)
    finally:
        keyring_mod.set_keyring(None)


def test_printed_ed25519_key_opens_a_session(tmp_path, capsys):
    """The key `keys add` prints must authenticate a session for that verifier.

    Red before the fix: the printed public half yields
    ``ApiError(403, code="bad_key")``. Green after: it is the private half and
    opens a session.
    """
    path = tmp_path / "ring.json"
    printed = _add_ed25519("eydis", path, capsys)

    result = _open_session("eydis", path, printed)
    assert result["verifier"] == "eydis"
    assert result["token"]


def test_the_public_half_still_does_not_open_a_session(tmp_path, capsys):
    """Guard the invariant, not just the happy path: the PUBLIC half must still
    be refused, so the fix prints the private half rather than weakening the
    check."""
    path = tmp_path / "ring.json"
    _add_ed25519("eydis", path, capsys)

    public_hex = keyring_mod.load(str(path)).get("eydis").key.hex()
    with pytest.raises(ApiError) as exc:
        _open_session("eydis", path, public_hex)
    assert exc.value.status == 403
    assert exc.value.code == "bad_key"


def test_printed_key_is_the_private_signing_half(tmp_path, capsys):
    """Lower-layer proof of the same fact: the printed key is what
    ``Keyring.signing_key`` returns (the private half), not the public one."""
    path = tmp_path / "ring.json"
    printed = _add_ed25519("eydis", path, capsys)

    ring = keyring_mod.load(str(path))
    entry = ring.get("eydis")
    assert entry.kind == "ed25519"
    assert printed == entry.private.hex()      # the signing half
    assert printed != entry.key.hex()          # not the public half
    assert printed == ring.signing_key("eydis").hex()


def test_human_output_prints_the_signing_half_too(tmp_path, capsys):
    """The default (non-JSON) block a human reads must carry the working key,
    not only the ``--json`` field."""
    path = tmp_path / "ring.json"
    printed = _add_ed25519("eydis", path, capsys, as_json=False)

    result = _open_session("eydis", path, printed)
    assert result["verifier"] == "eydis"


# --- the other two claims in the same sentence (§6.36 / Nestor#99) ---------
#
# The generate case above is one of three ways to add a verifier. The pre-fix
# message ("This is the only time it is printed. {name} needs it to sign in")
# was reused verbatim for all three, and the other two are wrong in a
# different way each: `--public HEX` types the key on the command line before
# the command ever runs (not "the only time"), and the peer never signs in
# with it at all (they sign client-side with their own private half — the
# entry's `can_sign` is False by construction). These tests hold that fix down
# the same way: red against the pre-fix code (parent of the fix commit),
# green after.


def _add_ed25519_peer(name: str, public_hex: str, path, capsys, *,
                       as_json: bool = True) -> str:
    """Run `nestor keys add <name> --type ed25519 --public <hex>` and return
    stdout."""
    argv = (["--json"] if as_json else []) + [
        "keys", "add", name, "--type", "ed25519", "--public", public_hex,
        "--keyring", str(path)]
    rc = cli.main(argv)
    out = capsys.readouterr().out
    assert rc == 0, out
    return out


def test_peer_public_key_message_does_not_claim_only_time_printed(tmp_path, capsys):
    """Registering a peer's PUBLIC key (`--public HEX`) must not say "this is
    the only time it is printed" — it was already typed on the command line,
    in shell history, before this process ever ran.

    Red before the fix: `cmd_keys` reused the generate-case sentence
    unconditionally, so it printed that claim here too.
    """
    path = tmp_path / "ring.json"
    public_hex = "ab" * 32
    out = _add_ed25519_peer("gunnar", public_hex, path, capsys, as_json=False)
    assert "only time it is printed" not in out


def test_peer_public_key_message_does_not_claim_it_signs_in(tmp_path, capsys):
    """Registering a peer must not claim they need this key to sign in — a
    peer entry holds no private half, so `Sessions.open` can never
    authenticate against it (`Keyring.signing_entry` refuses by construction).
    The peer signs in on their own instance, with their own private half.

    Red before the fix: the reused sentence said "{name} needs it to sign in
    to the UI" for the peer case too, which is backwards.
    """
    path = tmp_path / "ring.json"
    public_hex = "cd" * 32
    out = _add_ed25519_peer("halla", public_hex, path, capsys, as_json=False)
    assert "needs it to sign in" not in out
    assert "cannot open a session" in out


def test_peer_entry_has_no_signing_material(tmp_path, capsys):
    """The mechanism the message now describes: a `--public`-registered entry
    holds no private half on this instance, so there is nothing here for
    `Keyring.signing_key`/`signing_entry` to authenticate a sign-in against —
    ``bool(entry.private)`` is what `scripts/two_instances.py` calls
    "can_sign" for a peer (not `Entry.can_sign`, which tracks revocation, a
    different axis)."""
    path = tmp_path / "ring.json"
    public_hex = "ef" * 32
    _add_ed25519_peer("ingrid", public_hex, path, capsys, as_json=False)

    entry = keyring_mod.load(str(path)).get("ingrid")
    assert entry.kind == "ed25519"
    assert entry.private == b""
    with pytest.raises(keyring_mod.KeyringError):
        keyring_mod.load(str(path)).signing_entry("ingrid")


def test_peer_json_has_no_signing_key_field(tmp_path, capsys):
    """`--json` must not hand a script a `"key"` it could pipe to a new
    verifier as their sign-in credential — a peer entry has no signing
    material on this instance at all. The public half is still surfaced,
    under a name that says what it is.

    Red before the fix: `--json` emitted `"key": entry.key.hex()` — the
    PUBLIC half — indistinguishable in shape from the generate case's
    (correct) `"key"` field, which IS the signing half there.
    """
    path = tmp_path / "ring.json"
    public_hex = "12" * 32
    out = _add_ed25519_peer("jon", public_hex, path, capsys, as_json=True)
    payload = json.loads(out)
    assert "key" not in payload
    assert payload["public_key"] == public_hex


def test_hmac_add_is_unaffected_by_the_ed25519_fix(tmp_path, capsys):
    """Regression guard: the hmac path (the default, and the only kind where
    the original sentence held for every claim it made) must still print the
    signing secret, still say it is the only time, and it must still open a
    session — the fix must not have narrowed the branch that was already
    correct.
    """
    path = tmp_path / "ring.json"
    argv = ["--json", "keys", "add", "klara", "--keyring", str(path)]
    rc = cli.main(argv)
    out = capsys.readouterr().out
    assert rc == 0, out
    payload = json.loads(out)
    assert payload["kind"] == "hmac"
    printed = payload["key"]

    entry = keyring_mod.load(str(path)).get("klara")
    assert printed == entry.key.hex()

    keyring_mod.set_keyring(keyring_mod.load(str(path)))
    try:
        result = Sessions().open("klara", printed)
    finally:
        keyring_mod.set_keyring(None)
    assert result["verifier"] == "klara"


def _fresh_public_hex() -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    return Ed25519PrivateKey.generate().public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw).hex()


def test_peer_add_prints_the_public_half_and_says_it_cannot_sign_in(tmp_path, capsys):
    """§6.36's third case, the sentence read across the value it takes: a peer
    registered with ``--public`` gets the PUBLIC key printed, and the message
    says plainly it verifies seals but cannot open a session — never "the only
    time it is printed" or "needs it to sign in", which are false for a peer
    (the public half was typed on the command line, and the peer signs on their
    own instance with the private half this instance never holds)."""
    pub_hex = _fresh_public_hex()
    path = tmp_path / "keys.json"
    rc = cli.main(["keys", "add", "bob", "--type", "ed25519",
                   "--public", pub_hex, "--keyring", str(path)])
    out = capsys.readouterr().out.lower()
    assert rc == 0, out
    assert pub_hex in out
    assert "cannot open a session" in out
    assert "only time it is printed" not in out
    assert "needs it to sign in" not in out


def test_peer_add_json_carries_the_public_half_not_a_sign_in_key(tmp_path, capsys):
    """The machine-readable half of the same case: a peer entry emits
    ``public_key`` and no ``key`` — so a script cannot pipe a sign-in credential
    that does not exist for a peer to a new verifier."""
    pub_hex = _fresh_public_hex()
    path = tmp_path / "keys.json"
    rc = cli.main(["--json", "keys", "add", "bob", "--type", "ed25519",
                   "--public", pub_hex, "--keyring", str(path)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload.get("public_key") == pub_hex
    assert "key" not in payload
