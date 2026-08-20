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

import pytest

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


def test_a_read_only_consult_quoting_the_mint_phrase_is_allowed():
    # §6.109: the decision-store check the seat tells every agent to run before
    # proposing. The mint phrase appears only inside the quoted question, not as
    # the command's own subcommand — it must not be denied. Fails on the pre-fix
    # code, which scanned the whole command line including quoted argument text.
    consult = ('nestor --db docs/dogfood/nestor.db decision check '
               '"must cmd_keys print the signing half when a verifier is enrolled '
               'via keys add on an ed25519 keyring"')
    assert evaluate_authority(_bash(consult), REPO)[0] is True


def test_env_and_import_phrases_quoted_as_argument_text_do_not_trip():
    # Same class as above for the other two structural mints: naming them inside
    # a quoted question is not doing them.
    assert evaluate_authority(
        _bash('nestor decision check "when may we set NESTOR_SEAL_KEY at all"'), REPO)[0] is True
    assert evaluate_authority(
        _bash('nestor decision check "is import --apply --verifier ever ok"'), REPO)[0] is True


def test_the_sqlite_seal_write_guard_still_reads_quoted_sql():
    # Regression guard (passes before AND after §6.109's fix): the quote-blanking
    # that unblocks the consult above must NOT reach the sqlite check, whose
    # signal is the sealed status *inside* the SQL string.
    assert evaluate_authority(
        _bash("sqlite3 store.db \"UPDATE pairs SET status='sealed'\""), REPO)[0] is False


@pytest.mark.parametrize("command", [
    # The shell CLI, every write route to a seal. None of these may pass.
    "sqlite3 store.db \"UPDATE pairs SET status='sealed'\"",
    "sqlite3 store.db \"INSERT INTO pairs (status) VALUES ('sealed')\"",
    "sqlite3 store.db \"REPLACE INTO pairs (status) VALUES ('sealed')\"",
    "sqlite3 store.db \"INSERT OR REPLACE INTO pairs VALUES ('sealed')\"",
    "sqlite3 store.db \"UPDATE pairs SET seal_sig='x'\"",
    "sqlite3 store.db \"DELETE FROM pairs WHERE status='sealed'\"",
])
def test_every_sqlite_write_route_to_a_seal_is_still_denied(command):
    """The half of the narrowing that matters: the mint stays caught.

    Requiring a write verb alongside `sealed` is only safe if every verb that
    can reach the row is in the list. Each case here is a different route to
    the same act, and each must deny — a narrowing that let one through would
    be worse than the false positives it fixed.
    """
    assert evaluate_authority(_bash(command), REPO)[0] is False


@pytest.mark.parametrize("command", [
    # Reached through a wrapper or an env assignment, sqlite3 is still the
    # program being run. Matching the *executable* must not become a way to
    # hide behind one.
    "sudo sqlite3 store.db \"UPDATE pairs SET status='sealed'\"",
    "env FOO=bar sqlite3 store.db \"UPDATE pairs SET status='sealed'\"",
    "TZ=UTC sqlite3 store.db \"UPDATE pairs SET status='sealed'\"",
    "/usr/bin/sqlite3 store.db \"UPDATE pairs SET status='sealed'\"",
    "timeout 5 sqlite3 store.db \"UPDATE pairs SET status='sealed'\"",
    # Not the first stage of the pipeline — every stage is read, not just one.
    "echo hi | sqlite3 store.db \"UPDATE pairs SET status='sealed'\"",
    "true && sqlite3 store.db \"UPDATE pairs SET status='sealed'\"",
])
def test_a_wrapped_or_piped_sqlite_seal_write_is_still_denied(command):
    """Matching the executable must not hand back an evasion route.

    `sudo`, `env`, `timeout`, an absolute path, a leading `NAME=value`, or a
    position later in the pipeline all still run sqlite3 — the thing the guard
    is about. Each of these was denied by the old substring rule for the wrong
    reason (the word appeared); each must stay denied for the right one.
    """
    assert evaluate_authority(_bash(command), REPO)[0] is False


@pytest.mark.parametrize("command", [
    # Reads. `import sqlite3` is Python's module, not the shell CLI, and
    # counting seals is the audit #167 piece 6 asks for.
    "python3 -c \"import sqlite3; print('sealed')\"",
    "sqlite3 store.db \"SELECT status, COUNT(*) FROM pairs GROUP BY status\"",
    "sqlite3 store.db \"SELECT COUNT(*) FROM pairs WHERE status='sealed'\"",
    "python3 audit.py  # counts rows whose status is sealed but cite nothing",
    # Prose about the guard is prose. This commit message was denied by the
    # narrowed-but-still-substring rule, which is how the second false
    # positive was found: writing about sqlite3, sealed and UPDATE together.
    "git commit -m \"fix: sqlite3 UPDATE status='sealed' was denying reads\"",
    "grep -rn \"status='sealed'\" nestor/ | head",
    "echo \"sqlite3 does an UPDATE ... status='sealed' when you seal by hand\"",
])
def test_a_read_only_query_over_the_seal_column_is_allowed(command):
    """Reads are fine — the tripwire's own message says so, and now so does it.

    `\\bsqlite3\\b` matched Python's stdlib module, so a heredoc that merely
    counted sealed rows was denied, and with it every read-only audit of the
    seal column. Nothing here changes a row.
    """
    assert evaluate_authority(_bash(command), REPO)[0] is True


def test_a_real_enrol_with_a_quoted_display_name_is_still_denied():
    # Blanking quotes must not let a real mint through: the subcommand tokens are
    # unquoted, only the display name is quoted, so it still denies.
    assert evaluate_authority(_bash('nestor keys add "Rita Jones"'), REPO)[0] is False


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
