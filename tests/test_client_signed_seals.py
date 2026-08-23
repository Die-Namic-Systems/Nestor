"""Nestor#17, the last cell: the server VERIFIES a seal it did not sign.

Server-side ed25519 (``test_asymmetric_seals.py``) closed the cross-instance
cell: an instance holding only a peer's public key can verify that peer's
seals and is structurally unable to produce one. It left one operator-facing
cell open, named explicitly in
``docs/dogfood/decisions/0074-where-an-asymmetric-seal-is-signed.json``: the
instance that SIGNS still holds every verifier's private key, so its operator
can forge as anyone whose key lives there.

This module proves the seam that closes it without touching where the key
lives: ``memory.add_pair(..., seal_sig=...)`` lets a caller who already holds
a signature — produced by a client, entirely outside this process, exactly as
a browser's WebCrypto page or an agent-side signer would — hand it to the
server for VERIFICATION ONLY. The server never calls ``signing.sign_seal`` on
this path and, for a public-only ed25519 keyring entry, never could.

The acceptance property, extended from the issue's own bar:

* a public-only verifier CAN seal — given a valid client-produced signature;
* a public-only verifier STILL CANNOT seal with no signature supplied — the
  original property, unbroken;
* an INVALID or forged supplied signature is refused, and writes NOTHING —
  no row at all, sealed or otherwise;
* every existing signing path (private-half ed25519, hmac keyring entry,
  shared ``NESTOR_SEAL_KEY``) is byte-for-byte unchanged when ``seal_sig`` is
  omitted.

The browser/agent-side signing UI itself now ships too (`nestor/ui_page.py`,
decision `0078`) — the end-to-end proof that its JavaScript reproduces the
frozen contract against a REAL browser lives in
``tests/test_client_signed_seals_browser.py`` (Playwright), because nothing
in this file can prove a JS encoder agrees with `_message` byte-for-byte; it
can only prove what the server does once handed bytes that already agree.
What this file adds beyond the acceptance property above is the wire-contract
vector a client signer must reproduce: a hardcoded byte string for a
non-ASCII, quote-bearing input (`TestMessageWireContractIsFrozen`), and a
proof that signing exactly THOSE hardcoded bytes — not `_message`'s return
value, which would make the test circular — verifies through
``memory.add_pair`` end to end (`TestNonAsciiQuoteVectorEndToEnd`).
"""
from __future__ import annotations

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from nestor import cascade, keyring, memory, signing, storage
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


def _client_sign(private_bytes: bytes, norm: str, target: str, verifier: str) -> str:
    """Stand in for a signer that lives entirely outside this process: it
    only needs the wire contract (``signing._message``) and the private key —
    never anything memory.py or signing.sign_seal exposes."""
    priv = Ed25519PrivateKey.from_private_bytes(private_bytes)
    message = signing._message(norm, target, verifier)
    return priv.sign(message).hex()


class TestPublicOnlyVerifierSealsWithAClientSignature:
    """(a) A public-only verifier seals via a valid client-produced signature."""

    def test_lands_sealed_and_verifies(self, ring, store):
        # "bob" signs entirely on his own device: nothing here is the server's
        # sign_seal, and the private key below never gets near `ring`.
        private = Ed25519PrivateKey.generate()
        from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
        priv_bytes = private.private_bytes(Encoding.Raw, PrivateFormat.Raw,
                                           NoEncryption())
        pub_bytes = private.public_key().public_bytes(Encoding.Raw,
                                                       PublicFormat.Raw)

        # The server only ever sees bob's PUBLIC key.
        ring.add("bob", key=pub_bytes, kind="ed25519")
        entry = ring.get("bob")
        assert entry.kind == "ed25519" and not entry.private

        norm = "hello"                          # StringMatcher.normalize is
                                                  # the identity for this text
        client_sig = _client_sign(priv_bytes, norm, "hola", "bob")

        pair = memory.add_pair("hello", "hola", "en", "es", status="sealed",
                               verifier="bob", store=store, seal_sig=client_sig)

        assert pair["status"] == "sealed"
        assert pair["seal_sig"] == client_sig
        row = store.memory_find("hello", "en", "es")
        assert row is not None and row["status"] == "sealed"
        assert signing.seal_is_valid("hello", "hola", "bob", row["seal_sig"])
        # Fails on the unfixed code: `add_pair` had no `seal_sig` parameter at
        # all, so this call raised TypeError before ever reaching the store,
        # and even patched in by hand it hit `Keyring.signing_entry`'s public-
        # only refusal (see test_asymmetric_seals.py) because the old code
        # path always calls `sign_seal`, never a verify-only path.


class TestInvalidProvidedSignatureRefusesAndWritesNothing:
    """(b) A forged/invalid supplied signature is refused; nothing lands."""

    def test_forged_signature_refused_no_row(self, ring, store):
        from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
        real = Ed25519PrivateKey.generate()
        real_pub = real.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ring.add("bob", key=real_pub, kind="ed25519")

        # An attacker signs with a DIFFERENT key and hands over that signature
        # claiming it is bob's.
        attacker = Ed25519PrivateKey.generate()
        attacker_priv = attacker.private_bytes(Encoding.Raw, PrivateFormat.Raw,
                                               NoEncryption())
        forged_sig = _client_sign(attacker_priv, "hello", "hola", "bob")

        with pytest.raises(memory.InvalidSealSignatureError):
            memory.add_pair("hello", "hola", "en", "es", status="sealed",
                            verifier="bob", store=store, seal_sig=forged_sig)
        # The load-bearing assertion: no row at all, not a draft, not
        # anything — the refusal happens before any store write.
        assert store.memory_find("hello", "en", "es") is None
        # Fails on the unfixed code in the most direct way possible: the
        # unfixed `add_pair` has no `seal_sig` parameter, so passing it is a
        # TypeError, not an `InvalidSealSignatureError` — this test could not
        # even be phrased against the old signature.

    def test_garbage_signature_refused_no_row(self, ring, store):
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        real = Ed25519PrivateKey.generate()
        real_pub = real.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ring.add("bob", key=real_pub, kind="ed25519")

        with pytest.raises(memory.InvalidSealSignatureError):
            memory.add_pair("hello", "hola", "en", "es", status="sealed",
                            verifier="bob", store=store,
                            seal_sig="00" * 64)          # well-formed hex, wrong sig
        assert store.memory_find("hello", "en", "es") is None

    def test_signature_for_different_target_refused(self, ring, store):
        """A valid signature over the WRONG fields must not verify — proves
        the message is actually bound to (source_norm, target_text, verifier)
        on this path, not just checked for well-formedness."""
        from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
        private = Ed25519PrivateKey.generate()
        priv_bytes = private.private_bytes(Encoding.Raw, PrivateFormat.Raw,
                                           NoEncryption())
        pub_bytes = private.public_key().public_bytes(Encoding.Raw,
                                                       PublicFormat.Raw)
        ring.add("bob", key=pub_bytes, kind="ed25519")

        # bob really did sign "adios", not "hola".
        sig_for_adios = _client_sign(priv_bytes, "hello", "adios", "bob")

        with pytest.raises(memory.InvalidSealSignatureError):
            memory.add_pair("hello", "hola", "en", "es", status="sealed",
                            verifier="bob", store=store, seal_sig=sig_for_adios)
        assert store.memory_find("hello", "en", "es") is None


class TestNoSignatureSuppliedStillRefusesForPublicOnly:
    """(c) The original acceptance property, unbroken by this seam."""

    def test_public_only_verifier_cannot_auto_sign(self, ring, store):
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        private = Ed25519PrivateKey.generate()
        pub_bytes = private.public_key().public_bytes(Encoding.Raw,
                                                       PublicFormat.Raw)
        ring.add("bob", key=pub_bytes, kind="ed25519")

        # No seal_sig supplied -> falls to the old auto-sign path, which must
        # still refuse exactly as it did before this feature existed.
        with pytest.raises(keyring.KeyringError, match="PUBLIC"):
            memory.add_pair("hello", "hola", "en", "es", status="sealed",
                            verifier="bob", store=store)
        assert store.memory_find("hello", "en", "es") is None

    def test_public_only_bypass_requires_a_verifying_signature(self, ring, store):
        """The public-only refusal is bypassed ONLY when a valid signature is
        actually provided -- never merely because seal_sig="" was passed
        explicitly (the empty string must behave exactly like omitting it)."""
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        private = Ed25519PrivateKey.generate()
        pub_bytes = private.public_key().public_bytes(Encoding.Raw,
                                                       PublicFormat.Raw)
        ring.add("bob", key=pub_bytes, kind="ed25519")

        with pytest.raises(keyring.KeyringError, match="PUBLIC"):
            memory.add_pair("hello", "hola", "en", "es", status="sealed",
                            verifier="bob", store=store, seal_sig="")
        assert store.memory_find("hello", "en", "es") is None


class TestAutoSignPathUnchanged:
    """(d) Nothing about the default (no seal_sig) path moves."""

    def test_private_half_present_signs_as_before(self, ring, store):
        ring.add("rita", kind="ed25519")             # generates a keypair here
        pair = memory.add_pair("hello", "hola", "en", "es", status="sealed",
                               verifier="rita", store=store)
        assert pair["seal_sig"]
        assert signing.seal_is_valid(pair["source_norm"], "hola", "rita",
                                     pair["seal_sig"])

    def test_hmac_keyring_entry_signs_as_before(self, ring, store):
        ring.add("sam")                                # hmac, the default kind
        pair = memory.add_pair("hello", "hola", "en", "es", status="sealed",
                               verifier="sam", store=store)
        assert pair["seal_sig"]
        assert signing.seal_is_valid(pair["source_norm"], "hola", "sam",
                                     pair["seal_sig"])

    def test_shared_key_deployment_signs_as_before(self, tmp_path, monkeypatch):
        # No keyring at all -- the original, pre-#17 deployment shape.
        keyring.set_keyring(None)
        monkeypatch.setenv("NESTOR_SEAL_KEY", "a shared deployment secret")
        cascade.set_ledger_path(tmp_path / "ledger.jsonl")
        s = SqliteStore(":memory:")
        s.init_db()
        s.memory_init()
        try:
            pair = memory.add_pair("hello", "hola", "en", "es", status="sealed",
                                   verifier="whoever", store=s)
            assert pair["seal_sig"]
            assert signing.seal_is_valid(pair["source_norm"], "hola", "whoever",
                                         pair["seal_sig"])
        finally:
            s.close()


class TestMessageWireContractIsFrozen:
    """(e) `signing._message`'s exact bytes, pinned for a known input.

    Mirrored here rather than derived from the function under test -- the
    whole point of freezing the encoding is that an independent client
    reproduces it from the *documented* shape, not by importing
    ``nestor.signing``. Recomputing the expected bytes with ``json.dumps``
    the same way `_message` does would make the pin true by construction.
    """

    def test_known_input_byte_for_byte(self):
        assert (signing._message("hello", "hola", "rita")
               == b'["hello","hola","rita"]')

    def test_field_order_is_source_target_verifier(self):
        # A message built with the fields in a different order must NOT match
        # -- the pin is on the order, not just the byte count/shape.
        assert signing._message("a", "b", "c") == b'["a","b","c"]'
        assert signing._message("a", "b", "c") != signing._message("c", "b", "a")

    def test_no_whitespace_and_non_ascii_kept_literal(self):
        # separators=(",", ":") -- no space after either; ensure_ascii=False --
        # a non-ASCII character is emitted as itself (UTF-8 bytes), not
        # escaped as \\u00e9. Hardcoded, not derived from json.dumps here --
        # that would just re-run the implementation against itself.
        msg = signing._message("héllo", 'quo"te', "rita")
        assert msg == b'["h\xc3\xa9llo","quo\\"te","rita"]'
        assert b", " not in msg and b": " not in msg   # no separator whitespace
        assert b"\\u00e9" not in msg                    # utf-8 bytes, not \\uXXXX


class TestNonAsciiQuoteVectorEndToEnd:
    """(f) The exact non-ASCII + quote wire-contract vector, SIGNED and
    VERIFIED through ``memory.add_pair`` -- the shape a real client signer
    must meet, one level past the byte-string pin above (Nestor#17's browser
    signer, decision 0078). ``ui_page.py``'s JS reproduces this identical
    table (``pyJsonString``); this is the Python side of proving it, all the
    way through the store rather than only at the byte level.
    """

    def test_hardcoded_bytes_sign_and_verify_through_add_pair(self, ring, store):
        # The exact bytes pinned above -- hardcoded AGAIN here rather than
        # imported from the other test, so this test does not depend on
        # `_message` to describe its own input; it stands on its own if that
        # test is ever deleted or reworded.
        expected = b'["h\xc3\xa9llo","quo\\"te","rita"]'
        assert signing._message("héllo", 'quo"te', "rita") == expected

        from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
        private = Ed25519PrivateKey.generate()
        priv_bytes = private.private_bytes(Encoding.Raw, PrivateFormat.Raw,
                                           NoEncryption())
        pub_bytes = private.public_key().public_bytes(Encoding.Raw,
                                                       PublicFormat.Raw)
        ring.add("rita", key=pub_bytes, kind="ed25519")   # public-only, as an
                                                            # enrolled browser
                                                            # key would be

        # Sign the HARDCODED bytes directly, not `_message(...)`'s return
        # value -- this is exactly what an independent encoder (JS or
        # otherwise) that reproduced the table by hand, without importing
        # this module, would sign.
        sig = Ed25519PrivateKey.from_private_bytes(priv_bytes).sign(expected).hex()

        pair = memory.add_pair("héllo", 'quo"te', "en", "es", status="sealed",
                               verifier="rita", store=store, seal_sig=sig)
        assert pair["status"] == "sealed"
        assert pair["seal_sig"] == sig
        row = store.memory_find("héllo", "en", "es")
        assert row is not None and row["status"] == "sealed"
        assert signing.seal_is_valid("héllo", 'quo"te', "rita", row["seal_sig"])
        # Fails on the unfixed code exactly as (a) does: no `seal_sig`
        # parameter on `add_pair` at all before this feature existed.

    def test_a_signature_over_the_message_minus_one_byte_is_refused(self, ring, store):
        """The hardcoded vector is load-bearing, not decorative -- a
        signature over almost-the-same bytes (one byte short) must not
        verify. Guards against a JS encoder that is byte-for-byte correct
        except for, say, dropping the closing bracket."""
        from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
        private = Ed25519PrivateKey.generate()
        priv_bytes = private.private_bytes(Encoding.Raw, PrivateFormat.Raw,
                                           NoEncryption())
        pub_bytes = private.public_key().public_bytes(Encoding.Raw,
                                                       PublicFormat.Raw)
        ring.add("rita", key=pub_bytes, kind="ed25519")

        truncated = b'["h\xc3\xa9llo","quo\\"te","rita"]'[:-1]
        sig = Ed25519PrivateKey.from_private_bytes(priv_bytes).sign(truncated).hex()

        with pytest.raises(memory.InvalidSealSignatureError):
            memory.add_pair("héllo", 'quo"te', "en", "es", status="sealed",
                            verifier="rita", store=store, seal_sig=sig)
        assert store.memory_find("héllo", "en", "es") is None
