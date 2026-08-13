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

from nestor import cli, keyring as keyring_mod  # noqa: E402
from nestor.ui import ApiError, Sessions  # noqa: E402


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
