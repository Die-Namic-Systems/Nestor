"""The self-grant tripwire must deny minting and allow de-escalation — and its
literal lists must stay pinned to Nestor's real seal surface.

Every forbidden act is attempted and asserted refused (the guard's can-fail
proof: neuter `_deny` and these go green→red). The pinning tests bind the guard's
env set and keys-verb knowledge to what `signing`/`keyring`/`cli` actually expose,
so a new `NESTOR_*_KEY` or a new `keys` verb cannot be added to the product and
silently escape the guard — the drift willow-mcp's group pin exists to catch.
"""
from __future__ import annotations

import pathlib
import re

from hooks import before_authority as ba
from hooks.before_authority import evaluate_authority

REPO = pathlib.Path(__file__).resolve().parent.parent


def _bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def _write(path: str, content: str = "") -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


# -- denials: minting the power to seal --------------------------------------

def test_keys_add_is_denied():
    assert evaluate_authority(_bash("nestor keys add rita"), REPO)[0] is False


def test_keys_add_rotate_is_denied():
    assert evaluate_authority(_bash("nestor keys add rita --rotate"), REPO)[0] is False


def test_setting_a_seal_key_env_is_denied():
    assert evaluate_authority(_bash("export NESTOR_SEAL_KEY=deadbeef"), REPO)[0] is False
    assert evaluate_authority(_bash("NESTOR_KEYRING=/tmp/k.json nestor keys list"), REPO)[0] is False


def test_import_apply_under_a_verifier_is_denied():
    assert evaluate_authority(_bash("nestor import b.json --apply --verifier rita"), REPO)[0] is False


def test_raw_sqlite_seal_write_is_denied():
    assert evaluate_authority(
        _bash("sqlite3 docs/dogfood/nestor.db \"UPDATE pairs SET status='sealed'\""), REPO)[0] is False


def test_writing_the_keyring_file_is_denied():
    assert evaluate_authority(_write("/home/user/.nestor/keyring.json", '{"key":"ab"}'), REPO)[0] is False


# -- allowances: de-escalation, verify-only, and reads -----------------------

def test_keys_list_and_revoke_are_allowed():
    assert evaluate_authority(_bash("nestor keys list"), REPO)[0] is True
    assert evaluate_authority(_bash("nestor keys revoke rita --reason left"), REPO)[0] is True


def test_registering_a_peers_public_key_is_allowed():
    assert evaluate_authority(_bash("nestor keys add peer --type ed25519 --public ab12cd"), REPO)[0] is True


def test_reads_and_ordinary_work_are_allowed():
    for cmd in ("cat ~/.nestor/keyring.json", "nestor stats", "echo $NESTOR_SEAL_KEY",
                "git push --force-with-lease", "pytest -q"):
        assert evaluate_authority(_bash(cmd), REPO)[0] is True, cmd
    assert evaluate_authority(_write("nestor/foo.py", "x = 1"), REPO)[0] is True


def test_a_malformed_payload_fails_open():
    assert evaluate_authority({"tool_name": "Bash", "tool_input": "garbage"}, REPO)[0] is True
    assert evaluate_authority({}, REPO)[0] is True


# -- the pins: literal lists bound to the real surface -----------------------

def test_seal_env_covers_every_key_material_env_the_modules_read():
    """Any NESTOR_*KEY / *KEYRING env read by signing/keyring must be guarded —
    except the known non-material flag. A new one fails until it's classified."""
    text = ((REPO / "nestor" / "signing.py").read_text()
            + (REPO / "nestor" / "keyring.py").read_text())
    found = set(re.findall(r"NESTOR_[A-Z_]*(?:KEY|KEYRING)[A-Z_]*", text))
    non_material = {"NESTOR_REQUIRE_SEAL_KEY"}  # a fail-closed flag, not a secret
    assert found - non_material <= set(ba.SEAL_ENV), (
        f"unguarded key-material env(s): {found - non_material - set(ba.SEAL_ENV)} "
        f"— add to SEAL_ENV or to non_material with a reason")


def test_every_keys_verb_is_classified():
    """The guard denies `keys add`; list/revoke are de-escalation/read. A new
    `keys` verb in cli.py breaks this until the guard accounts for it."""
    text = (REPO / "nestor" / "cli.py").read_text()
    m = re.search(r'"keys_command",\s*choices=\(([^)]*)\)', text)
    assert m, "could not find the keys_command choices in cli.py"
    verbs = set(re.findall(r'"(\w+)"', m.group(1)))
    assert verbs == {"list", "add", "revoke"}, (
        f"keys verbs changed to {verbs}; classify the new/removed verb in "
        f"before_authority (add mints, list/revoke do not)")
