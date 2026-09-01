"""What a signature is evidence *of* — reported, not collapsed into a bit.

``signing_enabled()`` answers "are seals signed at all". That is one bit over
three situations which do not mean the same thing, and every deployment-wide
surface reported the bit: ``nestor stats`` printed ``on``/``OFF``, and the
portable export header carried ``enabled``. All three states make
``memory.is_verified_seal`` return ``True`` — correctly, because that answers
"may I serve this row", which really is binary — so nothing downstream told
them apart either.

The same collapse sat one level down. ``nestor keys add --type ed25519`` and
``... --type ed25519 --public <hex>`` are one flag apart and land on opposite
sides of decision ``0074``: the first leaves the private half in this
instance's keyring, so its operator can sign as that verifier; the second
never receives it. Afterwards the only trace was a ``private`` field present
or absent in the keyring file, and ``verifier_key_type`` returned
``"ed25519"`` for both.

These lock the reported states. The rule lives on
:attr:`nestor.keyring.VerifierKey.key_type` so the surfaces agree by reading
it rather than by each reimplementing it — the shape ``TODO.md`` names as the
defect four separate bugs shared.
"""
from __future__ import annotations

import json

import pytest

from nestor import cli, keyring, memory, portable, signing
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def no_keyring(monkeypatch):
    monkeypatch.delenv("NESTOR_SEAL_KEY", raising=False)
    monkeypatch.delenv("NESTOR_REQUIRE_SEAL_KEY", raising=False)
    keyring.set_keyring(None)
    yield
    keyring.set_keyring(None)


class TestSealTrustNamesTheState:
    """Three configurations, three answers — not one boolean."""

    def test_nothing_configured_is_unsigned(self, no_keyring):
        assert signing.seal_trust() == "unsigned"
        assert signing.signing_enabled() is False

    def test_a_shared_key_alone_is_shared_not_keyring(self, no_keyring, monkeypatch):
        """The state decision 0074 named: signed, and the name unchecked."""
        monkeypatch.setenv("NESTOR_SEAL_KEY", "one-shared-secret")
        assert signing.seal_trust() == "shared"

    def test_a_keyring_is_keyring(self, no_keyring):
        ring = keyring.Keyring()
        ring.add("rita")
        keyring.set_keyring(ring)
        assert signing.seal_trust() == "keyring"

    def test_the_boolean_cannot_tell_the_last_two_apart(self, no_keyring, monkeypatch):
        """The reason this function exists, asserted rather than described."""
        monkeypatch.setenv("NESTOR_SEAL_KEY", "one-shared-secret")
        shared_bit, shared_state = signing.signing_enabled(), signing.seal_trust()
        monkeypatch.delenv("NESTOR_SEAL_KEY")
        ring = keyring.Keyring()
        ring.add("rita")
        keyring.set_keyring(ring)
        assert shared_bit is signing.signing_enabled() is True
        assert shared_state != signing.seal_trust()


class TestKeyTypeSplitsTheTwoSidesOf0074:
    """`--type ed25519` and `--type ed25519 --public` must not report alike."""

    def test_a_locally_generated_pair_reports_ed25519(self, no_keyring):
        pytest.importorskip("cryptography")
        ring = keyring.Keyring()
        entry = ring.add("rita", kind="ed25519")
        assert entry.private, "generated here: the private half is retained"
        assert entry.key_type == "ed25519"

    def test_a_public_only_entry_reports_ed25519_public(self, no_keyring):
        pytest.importorskip("cryptography")
        source = keyring.Keyring()
        peer = source.add("phone", kind="ed25519")
        ring = keyring.Keyring()
        entry = ring.add("phone", key=peer.key, kind="ed25519")
        assert not entry.private, "registered by public half: nothing to sign with"
        assert entry.key_type == "ed25519-public"

    def test_hmac_is_unchanged(self, no_keyring):
        assert keyring.Keyring().add("sam").key_type == "hmac"

    def test_the_signing_surface_reads_the_same_rule(self, no_keyring):
        """One place, not two — verifier_key_type must not reimplement it."""
        pytest.importorskip("cryptography")
        source = keyring.Keyring()
        peer = source.add("phone", kind="ed25519")
        ring = keyring.Keyring()
        ring.add("phone", key=peer.key, kind="ed25519")
        ring.add("rita", kind="ed25519")
        ring.add("sam")
        keyring.set_keyring(ring)
        assert signing.verifier_key_type("phone") == "ed25519-public"
        assert signing.verifier_key_type("rita") == "ed25519"
        assert signing.verifier_key_type("sam") == "hmac"
        assert signing.verifier_key_type("nobody") == "unknown"

    def test_no_keyring_still_reports_the_deployment_state(self, no_keyring, monkeypatch):
        monkeypatch.setenv("NESTOR_SEAL_KEY", "shared")
        assert signing.verifier_key_type("anyone") == "shared"
        monkeypatch.delenv("NESTOR_SEAL_KEY")
        assert signing.verifier_key_type("anyone") == "unsigned"


class TestTheReportingSurfacesCarryIt:

    def test_the_export_header_states_the_trust(self, no_keyring, tmp_path, monkeypatch):
        monkeypatch.setenv("NESTOR_SEAL_KEY", "one-shared-secret")
        store = SqliteStore(str(tmp_path / "s.db"))
        memory.add_pair("hello", "hola", "en", "es", store=store,
                        status="sealed", verifier="rita")
        bundle = portable.export_bundle(store=store)
        assert bundle["signing"]["trust"] == "shared"
        assert bundle["signing"]["enabled"] is True

    def test_adding_trust_did_not_move_any_digest(self, no_keyring, tmp_path):
        """Header only: the digest is taken over the rows, so an existing
        bundle's digest must still verify against a bundle exported now."""
        store = SqliteStore(str(tmp_path / "s.db"))
        memory.add_pair("hello", "hola", "en", "es", store=store,
                        status="sealed", verifier="rita")
        bundle = portable.export_bundle(store=store)
        stripped = json.loads(json.dumps(bundle))
        stripped["signing"].pop("trust")
        ok, _ = portable.verify_bundle(stripped)
        assert ok, "the digest must not depend on the signing header"

    def test_stats_names_every_state_it_can_report(self):
        """A state with no line would print a KeyError, not a posture."""
        from nestor.cli import _SEAL_TRUST_LINE
        assert set(_SEAL_TRUST_LINE) == {"keyring", "shared", "unsigned"}


class TestTheCliRendersTheStateAPersonReads:
    """The JSON is for programs; these are the lines a person actually sees.

    Built in-process on ``test_asymmetric_seals.py``'s fixture pattern — a
    throwaway keyring under ``tmp_path``, discarded with the test. The seat's
    self-grant tripwire refuses to mint signing keys from the shell, which is
    correct and is why these assert on rendering rather than on a keyring this
    session created and kept.
    """

    def _keyring(self, tmp_path):
        pytest.importorskip("cryptography")
        source = keyring.Keyring()
        peer = source.add("phone", kind="ed25519")
        path = tmp_path / "kr.json"
        ring = keyring.Keyring(path=path)
        ring.add("rita", kind="ed25519")
        ring.add("phone", key=peer.key, kind="ed25519")
        ring.add("sam")
        ring.save(path)
        return path

    def test_keys_list_shows_which_side_of_0074_each_entry_is_on(
            self, no_keyring, tmp_path, capsys):
        path = self._keyring(tmp_path)
        assert cli.main(["keys", "list", "--keyring", str(path)]) == cli.EXIT_OK
        out = capsys.readouterr().out
        assert "ed25519-public  " in out and "phone" in out
        assert "ed25519 " in out and "rita" in out
        assert "hmac" in out and "sam" in out
        assert "can sign as them" in out, (
            "a listing that shows the two ed25519 values without saying what "
            "they mean has moved the collapse rather than fixed it")

    def test_keys_list_stays_quiet_when_nothing_holds_a_private_half(
            self, no_keyring, tmp_path, capsys):
        """The explanation is earned by an entry that needs it, not printed always."""
        path = tmp_path / "kr.json"
        ring = keyring.Keyring(path=path)
        ring.add("sam")
        ring.save(path)
        assert cli.main(["keys", "list", "--keyring", str(path)]) == cli.EXIT_OK
        assert "can sign as them" not in capsys.readouterr().out

    @pytest.mark.parametrize("env,expected", [
        ({}, "OFF — stored status is trusted"),
        ({"NESTOR_SEAL_KEY": "shhh"}, "anyone holding it signs as anyone"),
    ])
    def test_stats_names_the_posture_not_a_bit(
            self, no_keyring, tmp_path, capsys, monkeypatch, env, expected):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        code = cli.main(["--db", str(tmp_path / "s.db"),
                         "--ledger", str(tmp_path / "l.jsonl"), "stats"])
        assert code == cli.EXIT_OK
        line = [ln for ln in capsys.readouterr().out.splitlines()
                if "seal signatures:" in ln]
        assert line and expected in line[0], line

    def test_stats_json_keeps_the_old_bit_and_adds_the_state(
            self, no_keyring, tmp_path, capsys, monkeypatch):
        """An existing reader parsing `signing_enabled` must not be broken."""
        monkeypatch.setenv("NESTOR_SEAL_KEY", "shhh")
        cli.main(["--db", str(tmp_path / "s.db"),
                  "--ledger", str(tmp_path / "l.jsonl"), "stats", "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["signing_enabled"] is True
        assert payload["seal_trust"] == "shared"
