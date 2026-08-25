"""Nestor#17, the server-side half: an HMAC proves possession, not attribution.

The acceptance property, from the issue verbatim: **an instance that can
verify B's seals must not be able to produce one.** A symmetric key cannot
have that property — the verifying party holds the forging key by
construction. An ed25519 entry holding only the public half has it
structurally, and these tests prove both directions.

The [keys] extra is optional, so: tests that exercise real ed25519 skip
without ``cryptography``; the refusal-without-the-extra test simulates the
missing dependency instead of requiring a second environment.

Out of scope here, as in the issue's own "not in scope": browser/client-side
signing (the positioning decision), timestamping, transparency logs.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("cryptography")

from nestor import cascade, keyring, memory, portable, signing, storage
from nestor.curator import Curator
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def ring(tmp_path, monkeypatch):
    monkeypatch.delenv("NESTOR_SEAL_KEY", raising=False)
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    r = keyring.Keyring()
    keyring.set_keyring(r)
    yield r
    keyring.set_keyring(None)


@pytest.fixture()
def store(ring):
    s = SqliteStore(":memory:")
    s.init_db()
    s.memory_init()
    storage.set_store(s)
    yield s
    s.close()


class TestSignAndVerify:
    def test_ed25519_seal_roundtrip(self, ring, store):
        ring.add("rita", kind="ed25519")
        pair = memory.add_pair("hello", "hola", "en", "es", status="sealed",
                               verifier="rita", store=store)
        assert pair["seal_sig"]                      # 64-byte sig, hex
        assert len(bytes.fromhex(pair["seal_sig"])) == 64
        assert signing.seal_is_valid(pair["source_norm"], "hola", "rita",
                                     pair["seal_sig"])
        assert signing.seal_attribution(pair["source_norm"], "hola", "rita",
                                        pair["seal_sig"]) == "verifier"

    def test_tampered_target_does_not_verify(self, ring, store):
        ring.add("rita", kind="ed25519")
        pair = memory.add_pair("hello", "hola", "en", "es", status="sealed",
                               verifier="rita", store=store)
        assert not signing.seal_is_valid(pair["source_norm"], "adios", "rita",
                                         pair["seal_sig"])

    def test_curator_reports_key_type(self, ring, store):
        ring.add("rita", kind="ed25519")
        ring.add("sam")                              # hmac, the default
        for src, who in (("hello", "rita"), ("goodbye", "sam")):
            memory.add_pair(src, "x", "en", "es", status="sealed",
                            verifier=who, store=store)
        rows = {r["verifier"]: r for r in Curator(store).browse()}
        assert rows["rita"]["key_type"] == "ed25519"
        assert rows["sam"]["key_type"] == "hmac"


class TestTheAcceptanceProperty:
    """Verify-without-forge, in both directions, across two instances."""

    def test_public_only_instance_verifies_but_cannot_sign(self, tmp_path,
                                                           monkeypatch):
        monkeypatch.delenv("NESTOR_SEAL_KEY", raising=False)
        cascade.set_ledger_path(tmp_path / "ledger.jsonl")

        # Instance B: holds its own private key, seals, exports.
        ring_b = keyring.Keyring()
        entry = ring_b.add("bob", kind="ed25519")
        keyring.set_keyring(ring_b)
        store_b = SqliteStore(":memory:")
        store_b.init_db()
        store_b.memory_init()
        memory.add_pair("hello", "hola", "en", "es", status="sealed",
                        verifier="bob", store=store_b)
        bundle = portable.export_bundle(store=store_b)
        store_b.close()

        # Instance A: holds ONLY bob's public key.
        ring_a = keyring.Keyring()
        ring_a.add("bob", key=entry.key, kind="ed25519")
        keyring.set_keyring(ring_a)
        try:
            store_a = SqliteStore(":memory:")
            store_a.init_db()
            store_a.memory_init()
            # Direction 1: A verifies B's work — the seal imports AS sealed.
            report = portable.import_bundle(bundle, store=store_a,
                                            dry_run=False, verifier="alice")
            assert report["sealed"] == 1
            row = store_a.memory_find("hello", "en", "es")
            assert row["status"] == "sealed"
            assert signing.seal_is_valid("hello", "hola", "bob",
                                         row["seal_sig"])
            # Direction 2: A cannot produce a seal as bob. This is the cell
            # in the issue's table that HMAC could never clear.
            with pytest.raises(keyring.KeyringError, match="PUBLIC"):
                memory.add_pair("goodbye", "adios", "en", "es",
                                status="sealed", verifier="bob",
                                store=store_a)
            assert store_a.memory_find("goodbye", "en", "es") is None
            store_a.close()
        finally:
            keyring.set_keyring(None)

    def test_public_only_keyring_is_distributable(self, tmp_path):
        # The permission refusal follows the key MATERIAL: a public-only
        # keyring is world-readable on purpose (commit it, mirror it); one
        # holding any secret still refuses.
        ring = keyring.Keyring()
        entry = ring.add("bob", kind="ed25519")
        pub_only = keyring.Keyring()
        pub_only.add("bob", key=entry.key, kind="ed25519")
        path = tmp_path / "public.keyring"
        pub_only.save(str(path))
        path.chmod(0o644)
        loaded = keyring.load(str(path))
        assert loaded.get("bob").kind == "ed25519"
        assert not loaded.get("bob").private

        secret = tmp_path / "secret.keyring"
        ring.save(str(secret))                      # holds the private half
        secret.chmod(0o644)
        with pytest.raises(keyring.KeyringError, match="readable by other"):
            keyring.load(str(secret))

    def test_private_half_stays_out_of_public_export(self, tmp_path):
        ring = keyring.Keyring()
        entry = ring.add("bob", kind="ed25519")
        raw = json.dumps(entry.to_json())
        assert entry.private.hex() in raw           # its own file: private
        pub = keyring.VerifierKey(name="bob", key=entry.key, kind="ed25519")
        assert "private" not in pub.to_json()       # the distributed shape


class TestRejectionNeverRefuses:
    def test_public_only_verifier_rejection_recorded_unsigned(self, ring,
                                                              store):
        # Refusing to record a "no" is the one direction rejection must not
        # fail in: an ed25519 entry without its private half records the
        # rejection unsigned rather than raising.
        priv = keyring.Keyring()
        entry = priv.add("bob", kind="ed25519")
        ring.add("bob", key=entry.key, kind="ed25519")   # public only
        ring.add("rita", kind="ed25519")                 # can seal here
        pair = memory.add_pair("hello", "hola", "en", "es", status="sealed",
                               verifier="rita", store=store)
        rejection = memory.reject_match("hello", "en", "es",
                                        pair_id=pair["id"], verifier="bob",
                                        reason="wrong register", store=store)
        assert rejection["reject_sig"] == ""             # unsigned, honored
        got = memory.lookup("hello", "en", "es", store=store)
        assert all(m["pair"]["id"] != pair["id"] for m in got)

    def test_private_holder_rejection_signs_and_verifies(self, ring, store):
        ring.add("rita", kind="ed25519")
        pair = memory.add_pair("hello", "hola", "en", "es", status="sealed",
                               verifier="rita", store=store)
        rejection = memory.reject_match("hello", "en", "es",
                                        pair_id=pair["id"], verifier="rita",
                                        reason="self-correction", store=store)
        assert rejection["reject_sig"]
        assert signing.rejection_is_valid("hello", pair["id"], "", "rita",
                                          rejection["reject_sig"])


class TestWithoutTheExtra:
    def test_missing_dependency_refuses_loudly(self, ring, store,
                                               monkeypatch):
        ring.add("rita", kind="ed25519")

        def _no_extra():
            raise signing.SigningRequiredError(
                "this keyring holds ed25519 keys, which need the [keys] "
                "extra: pip install 'nestor-meaning[keys]'.")
        monkeypatch.setattr(signing, "_load_ed25519", _no_extra)
        with pytest.raises(signing.SigningRequiredError, match=r"\[keys\]"):
            memory.add_pair("hello", "hola", "en", "es", status="sealed",
                            verifier="rita", store=store)
        # Refused BEFORE the store write — no unsigned row left behind.
        assert store.memory_find("hello", "en", "es") is None
