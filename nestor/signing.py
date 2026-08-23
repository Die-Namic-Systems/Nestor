"""nestor.signing — bind a seal to a key the store does not hold.

Red-team finding (Nestor#2): ``status="sealed"`` and ``verifier`` are just
columns, so any caller that can write ``tm_pairs`` forges a human seal and it
serves as tier-1. This binds a seal to an HMAC over its load-bearing fields
``(source_norm, target_text, verifier)``, keyed by a secret held OUTSIDE the
store (``NESTOR_SEAL_KEY`` or injected). A store-writer without the key cannot
produce a signature ``best_sealed`` will accept — so a forged sealed row is not
served.

Stdlib only, so the dependency-light core is preserved. The default is the
symmetric (HMAC) form; the asymmetric upgrade — an Ed25519 signature checked
with a public key the signer alone could have produced — lives behind the
``[keys]`` extra, as ``kind == "ed25519"`` keyring entries (see Nestor#2).

Opt-in and backward-compatible: with no key configured, signing is OFF and every
seal is accepted, exactly as before.

One key or one per verifier
---------------------------
A single ``NESTOR_SEAL_KEY`` proves *the key was present*. It does not prove
who: every verifier signs with it, so the name on a seal is still a string
somebody typed. :mod:`nestor.keyring` closes that — install a keyring and each
verifier signs with their own key, so a valid signature over
``(source_norm, target_text, "rita")`` is evidence about rita.

Every function here resolves its key the same way, in this order:

1. an explicit ``key=`` argument (tests, and any caller that wants to be exact);
2. the installed keyring's entry for ``verifier``, if a keyring is in force;
3. ``NESTOR_SEAL_KEY``.

So the shared-key deployment is unchanged, the keyring deployment attributes
seals to people, and the two are the same code path.

Three protocols, three domains
------------------------------
Seals, rejections and cached embeddings are each MAC'd here, and each message is
tagged so a signature from one can never verify in another. The third arrived
with the embedding cache (IDEAS §6.4) and is worth stating plainly: a seal binds
*what a human approved*, but under :class:`~nestor.semantic_matcher.SemanticMatcher`
the serve decision is taken over embedding vectors, and a vector read back out
of the store is an input to that decision. Signing the seal and not the vector
would leave a store-writer able to change what a sealed row matches without
forging anything — the same shape as Nestor#2, one object over.

Client-produced signatures (Nestor#17)
---------------------------------------
Every signature above was, until now, both produced and checked inside this
process. ``memory.add_pair(..., seal_sig=...)`` adds a path where a CLIENT —
a browser doing WebCrypto ed25519, or any other out-of-process signer —
produces the signature and this module only VERIFIES it via
:func:`seal_is_valid`, never signs it. That is what lets an ed25519 keyring
entry holding only the verifier's PUBLIC key seal a pair: the private key
never has to be on this instance at all. See :func:`_message` for the exact,
now-FROZEN, byte encoding a client signer must reproduce.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import warnings

from . import config
from . import keyring as keyring_mod
from .errors import NestorError


class SigningRequiredError(NestorError):
    """``NESTOR_REQUIRE_SEAL_KEY`` is set but no ``NESTOR_SEAL_KEY`` is
    configured — strict mode refuses to serve seals it cannot verify."""


_warned_unsigned = False


def _load_ed25519():
    """The [keys] extra, or a loud refusal. Never a silent degrade: a seal
    that silently fell back to unsigned would be the Nestor#2 forgery with a
    dependency error as its accomplice."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
        return Ed25519PrivateKey, Ed25519PublicKey, InvalidSignature
    except ImportError as exc:
        raise SigningRequiredError(
            "this keyring holds ed25519 keys, which need the [keys] extra: "
            "pip install 'nestor-meaning[keys]'. HMAC keyrings remain the "
            "dependency-free default.") from exc


def _sign_with(entry_kind: str, secret: bytes, message: bytes) -> str:
    if entry_kind == "ed25519":
        Ed25519PrivateKey, _, _ = _load_ed25519()
        return Ed25519PrivateKey.from_private_bytes(secret).sign(message).hex()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _verifies_with(entry_kind: str, key_bytes: bytes, message: bytes,
                   sig: str) -> bool:
    if not sig:
        return False
    if entry_kind == "ed25519":
        _, Ed25519PublicKey, InvalidSignature = _load_ed25519()
        try:
            Ed25519PublicKey.from_public_bytes(key_bytes).verify(
                bytes.fromhex(sig), message)
            return True
        except (InvalidSignature, ValueError):
            return False
    return hmac.compare_digest(
        hmac.new(key_bytes, message, hashlib.sha256).hexdigest(), sig)


def _key(key: bytes | None = None) -> bytes | None:
    if key is not None:
        return key
    env = config.get_secret("NESTOR_SEAL_KEY")
    return env.encode() if env else None


def _signing_ref(verifier: str,
                 key: bytes | None = None) -> tuple[str, bytes] | None:
    """``(kind, secret)`` ``verifier`` signs with. Raises if a keyring refuses
    them — including an ed25519 entry holding only the public half, because
    an instance that can verify a peer must not be able to sign as them.

    The refusal is the feature: with per-verifier keys, an unregistered or
    revoked name has no key, and the alternative to raising is putting a name on
    a verification that nothing backs.
    """
    if key is not None:
        return ("hmac", key)
    ring = keyring_mod.get_keyring()
    if ring is not None:
        entry = ring.signing_entry(verifier)
        secret = entry.private if entry.kind == "ed25519" else entry.key
        return (entry.kind, secret)
    shared = _key(None)
    return ("hmac", shared) if shared else None


def _verifying_refs(verifier: str,
                    key: bytes | None = None) -> list[tuple[str, bytes]]:
    """Every key a seal by ``verifier`` may legitimately have been signed with.

    Usually one. Two only during migration: a keyring with a ``legacy_key`` also
    accepts signatures made under the old single deployment key, which is what
    every seal predating the keyring carries. Those are reported as ``legacy``
    by the curator rather than attributed to a person, because that is what they
    are.
    """
    if key is not None:
        return [("hmac", key)]
    ring = keyring_mod.get_keyring()
    if ring is not None:
        refs = []
        own = ring.verifying_entry(verifier)
        if own is not None:
            refs.append((own.kind, own.key))
        if ring.legacy_key:
            refs.append(("hmac", ring.legacy_key))
        return refs
    shared = _key(None)
    return [("hmac", shared)] if shared else []


def seal_attribution(source_norm: str, target_text: str, verifier: str,
                     seal_sig: str) -> str:
    """*Whose* key signed this seal — for surfaces, never for serving.

    ``"unsigned"`` (signing is off entirely), ``"verifier"`` (their own key —
    the only value that attributes a seal to a person), ``"legacy"`` (the
    deployment-wide key from before the keyring, so: verified by somebody here),
    or ``"none"`` (nothing this instance holds produced that signature).

    :func:`seal_is_valid` is the serve decision and stays a bool; a curator
    needs the distinction between "a person signed this" and "this deployment
    signed this", which a bool cannot carry.
    """
    ring = keyring_mod.get_keyring()
    if ring is None:
        return "verifier" if _key(None) and seal_is_valid(
            source_norm, target_text, verifier, seal_sig) else (
            "unsigned" if not _key(None) else "none")
    if not seal_sig:
        return "none"
    message = _message(source_norm, target_text, verifier)

    own = ring.verifying_entry(verifier)
    if own is not None and _verifies_with(own.kind, own.key, message, seal_sig):
        return "verifier"
    if ring.legacy_key and _verifies_with("hmac", ring.legacy_key, message,
                                          seal_sig):
        return "legacy"
    return "none"


def verifier_key_type(verifier: str) -> str:
    """The key type behind a verifier's name — for surfaces (Nestor#17).

    ``"hmac"`` / ``"ed25519"`` (their keyring entry), ``"shared"`` (no
    keyring, deployment-wide NESTOR_SEAL_KEY), ``"unsigned"`` (signing off),
    ``"unknown"`` (keyring installed, name not in it). "Signed by rita's
    HMAC" and "signed by rita's key" are different claims, and a curator
    migrating between them needs to see which one each seal makes.
    """
    ring = keyring_mod.get_keyring()
    if ring is None:
        return "shared" if _key(None) else "unsigned"
    entry = ring.get(verifier)
    return entry.kind if entry is not None else "unknown"


def _strict() -> bool:
    return config.get_bool_loose("NESTOR_REQUIRE_SEAL_KEY", False,
                                 frozenset({"1", "true", "yes", "on"}))


def signing_enabled(key: bytes | None = None) -> bool:
    """True iff seals are signed at all — a keyring, or a shared key."""
    return _key(key) is not None or keyring_mod.enabled()


def _message(source_norm: str, target_text: str, verifier: str) -> bytes:
    """The bytes a seal signature is taken over. JSON-encoded array — a
    *structured* encoding so no combination of field values can collide by
    shifting a delimiter. (The old ``"\\x1f".join(...)`` form was forgeable:
    ``target_text`` and ``verifier`` are not normalized and could contain the
    separator, so ``("ok\\x1fadmin", "alice")`` and ``("ok", "admin\\x1falice")``
    signed the same bytes — Nestor#2 follow-up. Matches willow-mcp/session_binder's
    canonical encoding.)

    FROZEN — a wire contract, not an implementation detail (Nestor#17).
    While every seal signature was produced *and* checked inside this module,
    the exact encoding was free to change: any two calls in the same process
    agreed with each other by construction. That stopped being true the
    moment a signature can arrive from OUTSIDE this process — a browser doing
    WebCrypto ed25519, or any other client-side signer — because that signer
    reproduces these bytes independently, without importing this function.
    ``memory.add_pair(..., seal_sig=...)`` is the server-side seam that
    accepts such a signature and checks it with :func:`seal_is_valid`; the two
    sides only agree if they compute *identical* bytes. So, pinned exactly,
    for every field of the encoding:

    * a JSON array, field order ``[source_norm, target_text, verifier]`` —
      not an object (no key-name ambiguity), not the legacy ``\\x1f``-joined
      string;
    * ``json.dumps(..., separators=(",", ":"), ensure_ascii=False)`` — no
      whitespace after ``,``/``:``, and non-ASCII characters are emitted
      literally rather than as ``\\uXXXX`` escapes;
    * ``.encode("utf-8")`` — the signature is over UTF-8 bytes, not ``str``;
    * ``source_norm`` is the ALREADY-NORMALIZED source (whatever the domain's
      ``Matcher.normalize`` produced), not the raw ``source_text``.

    Do not change this encoding — a client signer that reproduces it
    byte-for-byte is the entire contract. If it must ever change, that is a
    protocol version bump communicated to every signer, not a refactor.
    ``tests/test_client_signed_seals.py`` pins the exact output for a known
    input for this reason.
    """
    return json.dumps([source_norm, target_text, verifier],
                      separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _embedding_message(pair_id: str, model_name: str, source_sha: str,
                       blob: bytes) -> bytes:
    """The bytes an embedding-cache HMAC is taken over.

    Tagged ``"embedding"`` as element 0 for the same reason a rejection is: a
    signature from one protocol must not verify in another. The vector itself
    enters as a digest of its packed bytes rather than a list of floats, so the
    message is a fixed size and does not depend on ``repr`` of a float.

    ``pair_id`` and ``model_name`` are inside the message, not just the lookup
    key — otherwise a valid entry could be moved onto a different row, which is
    the same attack with an extra step.
    """
    return json.dumps(["embedding", pair_id, model_name, source_sha,
                       hashlib.sha256(blob).hexdigest()],
                      separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def cache_key(key: bytes | None = None) -> bytes | None:
    """The key a cached embedding is MAC'd with — deployment-wide, not per-person.

    A seal names a verifier and so is signed with *their* key. Nothing about a
    cached vector belongs to a person: it is a machine's arithmetic over text
    already in the row. What it needs is a key the store does not hold, which is
    the only property that makes the MAC worth taking.

    ``NESTOR_CACHE_KEY`` first, so a deployment can separate the two secrets;
    then ``NESTOR_SEAL_KEY``; then a keyring's ``legacy_key``, which is the one
    deployment-wide secret a keyring carries. A keyring with no legacy key has
    no deployment-wide secret at all, and inventing one out of per-verifier keys
    would mean every ``keys add`` silently invalidated the whole cache.
    """
    if key is not None:
        return key
    env = config.get_secret("NESTOR_CACHE_KEY")
    if env:
        return env.encode()
    shared = _key(None)
    if shared:
        return shared
    ring = keyring_mod.get_keyring()
    if ring is not None and ring.legacy_key:
        return ring.legacy_key
    return None


def cache_trust(key: bytes | None = None) -> str:
    """How far a stored embedding may be trusted: the cache's serve policy.

    * ``"signed"`` — a key is available; a cached vector is used iff it verifies.
    * ``"unsigned"`` — signing is off entirely. The store is already fully
      trusted (any row in it can claim ``status="sealed"``), so requiring a MAC
      on the cache would protect nothing while costing every deployment that
      never turned signing on. Accept, exactly as :func:`seal_is_valid` does.
    * ``"unavailable"`` — signing is ON but no deployment-wide key exists. The
      store is *not* trusted and the cache cannot be checked, so it is not read.
      Embeddings are recomputed: slower, never wrong.
    """
    if cache_key(key) is not None:
        return "signed"
    return "unavailable" if signing_enabled() else "unsigned"


def sign_embedding(pair_id: str, model_name: str, source_sha: str, blob: bytes,
                   key: bytes | None = None) -> str:
    """HMAC-SHA256 over a cached embedding. ``""`` when no cache key exists."""
    k = cache_key(key)
    if not k:
        return ""
    return hmac.new(k, _embedding_message(pair_id, model_name, source_sha, blob),
                    hashlib.sha256).hexdigest()


def embedding_is_valid(pair_id: str, model_name: str, source_sha: str,
                       blob: bytes, sig: str, key: bytes | None = None) -> bool:
    """Whether a cached vector may be used instead of recomputing it.

    Unlike :func:`seal_is_valid` this never raises and never warns: a cache miss
    is not a refusal to serve, it is an embed call. Failing here costs latency,
    so the safe answer is always available and there is no reason to degrade.
    """
    trust = cache_trust(key)
    if trust == "unsigned":
        return True
    if trust == "unavailable":
        return False
    expected = sign_embedding(pair_id, model_name, source_sha, blob, key)
    return bool(sig) and hmac.compare_digest(expected, sig)


def _rejection_message(query_norm: str, pair_id: str, target_text: str,
                       verifier: str) -> bytes:
    """The bytes a rejection HMAC is taken over.

    Tagged with a literal ``"rejection"`` as element 0 so a rejection signature
    and a seal signature can never be each other. Seal messages are 3-element
    arrays of field values; a rejection is a 4-element array whose first element
    is a constant no ``source_norm`` can produce ambiguity with. Without that
    domain separation a signature captured from one protocol could be replayed
    into the other.
    """
    return json.dumps(["rejection", query_norm, pair_id, target_text, verifier],
                      separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _rejection_sign_ref(verifier: str, key: bytes | None = None
                        ) -> tuple[str, bytes] | None:
    """``(kind, secret)`` a rejection by ``verifier`` is signed with — and never a refusal.

    Deliberately not :func:`_signing_key`. A seal by an unregistered verifier
    must fail loudly; a *rejection* by one must not, because refusing to record
    a "no" is the one direction rejection cannot fail in — it would leave a bad
    answer serving because the reviewer's name was not on a list. An unknown
    verifier's rejection is recorded, honored, and reported as unsigned.
    """
    if key is not None:
        return ("hmac", key)
    ring = keyring_mod.get_keyring()
    if ring is not None:
        own = ring.verifying_entry(verifier)
        if own is not None:
            if own.kind == "ed25519":
                # Only the private half can sign; without it the rejection is
                # recorded UNSIGNED rather than refused — refusing to record
                # a "no" is the one direction rejection must not fail in.
                return ("ed25519", own.private) if own.private else None
            return ("hmac", own.key)
        return ("hmac", ring.legacy_key) if ring.legacy_key else None
    shared = _key(None)
    return ("hmac", shared) if shared else None


def sign_rejection(query_norm: str, pair_id: str, target_text: str,
                   verifier: str, key: bytes | None = None) -> str:
    """HMAC-SHA256 over a rejection's bound fields. ``""`` when signing is off."""
    ref = _rejection_sign_ref(verifier, key)
    if ref is None or not ref[1]:
        return ""
    return _sign_with(ref[0], ref[1],
                      _rejection_message(query_norm, pair_id, target_text,
                                         verifier))


def rejection_is_valid(query_norm: str, pair_id: str, target_text: str,
                       verifier: str, reject_sig: str,
                       key: bytes | None = None) -> bool:
    """Whether ``reject_sig`` is a valid rejection signature.

    NOTE: unlike :func:`seal_is_valid`, this is *reporting only* — Nestor honors
    a rejection whether or not it verifies. See ``memory.rejected_ids`` for why
    suppression fails safe in a way that serving does not.
    """
    refs = _verifying_refs(verifier, key) if key is None else [("hmac", key)]
    if not refs:
        # Nothing to check against: with signing off every rejection is as good
        # as any other, and saying "invalid" would be a report about the
        # deployment dressed up as a report about the reviewer.
        return not keyring_mod.enabled()
    message = _rejection_message(query_norm, pair_id, target_text, verifier)
    return bool(reject_sig) and any(
        _verifies_with(kind, k, message, reject_sig) for kind, k in refs)


def sign_seal(source_norm: str, target_text: str, verifier: str,
              key: bytes | None = None) -> str:
    """HMAC-SHA256 over the seal's bound fields. Returns ``""`` when no key is
    configured (unsigned — signing disabled).

    With a keyring installed this signs with ``verifier``'s own key, and raises
    :class:`~nestor.keyring.UnknownVerifierError` or
    :class:`~nestor.keyring.RevokedKeyError` if they have none. Callers reach
    here through ``memory.add_pair``, before the store write, so a refusal
    leaves nothing behind.
    """
    ref = _signing_ref(verifier, key)
    if ref is None:
        return ""
    kind, secret = ref
    return _sign_with(kind, secret, _message(source_norm, target_text, verifier))


def seal_is_valid(source_norm: str, target_text: str, verifier: str,
                  seal_sig: str, key: bytes | None = None) -> bool:
    """Whether ``seal_sig`` is a valid seal signature.

    With nothing configured, signing is OFF and every seal is accepted (the
    legacy default) — but that silently reopens the Nestor#2 forgery, so it
    warns once, and ``NESTOR_REQUIRE_SEAL_KEY=1`` turns the degrade into a hard
    refusal.

    With a keyring, a seal is valid only under the key belonging to the verifier
    *named on it*. So a signature is evidence about a person, and three cases
    that used to be indistinguishable now differ:

    * a verifier the keyring never knew — no key, never valid;
    * a key revoked because it was rotated — still verifies its own past seals;
    * a key revoked because it was **stolen** — verifies nothing, because an
      HMAC carries no timestamp and its seals cannot be told apart from the
      thief's. See :meth:`nestor.keyring.Keyring.revoke`.
    """
    refs = _verifying_refs(verifier, key)
    if not refs and not keyring_mod.enabled():
        if _strict():
            raise SigningRequiredError(
                "NESTOR_REQUIRE_SEAL_KEY is set but no NESTOR_SEAL_KEY is "
                "configured — refusing to serve unverifiable seals")
        global _warned_unsigned
        if not _warned_unsigned:
            _warned_unsigned = True
            warnings.warn(
                "NESTOR_SEAL_KEY not set — seal signatures are NOT verified; "
                "any 'sealed' row is trusted (Nestor#2). Set NESTOR_SEAL_KEY, "
                "or NESTOR_REQUIRE_SEAL_KEY=1 to fail closed.",
                RuntimeWarning, stacklevel=2)
        return True  # signing disabled — preserve legacy behavior
    if not seal_sig:
        return False
    message = _message(source_norm, target_text, verifier)
    return any(_verifies_with(kind, k, message, seal_sig) for kind, k in refs)


def _edge_message(src_id: str, dst_id: str, kind: str) -> bytes:
    """The bytes a decision-edge signature is taken over (docs/decision-memory.md
    N6).

    Tagged with a literal ``"edge"`` as element 0 so an edge signature can never
    be a seal or a rejection. A seal message is a 3-element array of field
    values; a rejection is a 5-element array led by ``"rejection"``; an edge is a
    4-element array led by ``"edge"`` — a constant no ``src_id`` produces. Same
    ``json.dumps(separators=(",",":"), ensure_ascii=False)`` FROZEN encoding as
    :func:`_message`, so an out-of-process signer (the openssl / WebCrypto flow a
    human seals an edge with) reproduces it byte-for-byte.
    """
    return json.dumps(["edge", src_id, dst_id, kind],
                      separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_edge(src_id: str, dst_id: str, kind: str, verifier: str,
              key: bytes | None = None) -> str:
    """Signature over an edge's bound fields. ``""`` when signing is off.

    An edge — "this decision supersedes / refines / depends_on / contradicts
    that one" — is a human judgment of the same weight as a seal, so it resolves
    keys the seal way (:func:`_signing_ref`) and an unregistered verifier is
    *refused*, not recorded unsigned as a rejection would be. The covenant reason
    is the same as the seal's: a name on a ratification that nothing backs is the
    forgery the signature exists to stop.
    """
    ref = _signing_ref(verifier, key)
    if ref is None:
        return ""
    key_kind, secret = ref
    return _sign_with(key_kind, secret, _edge_message(src_id, dst_id, kind))


def edge_is_valid(src_id: str, dst_id: str, kind: str, verifier: str,
                  edge_sig: str, key: bytes | None = None) -> bool:
    """Whether ``edge_sig`` verifies this edge under ``verifier``'s key.

    Unlike a seal, an edge carries no ``status`` column — the signature *is* the
    seal — so an edge with no signature is a **proposal**, never a fact, and this
    returns ``False`` for an empty signature regardless of signing mode. That is
    the covenant made mechanical: ``constraints_on`` traverses an edge only when
    this returns ``True``, so a machine-proposed edge (``edge_sig=""``) cannot
    constrain anything until a human signs it. With a present signature the rule
    matches :func:`seal_is_valid` — under a keyring it must verify under the key
    of the verifier named on it, and with signing off a present signature is
    trusted (legacy).
    """
    if not edge_sig:
        return False
    refs = _verifying_refs(verifier, key)
    if not refs and not keyring_mod.enabled():
        return True  # signing disabled — a present signature is trusted (legacy)
    message = _edge_message(src_id, dst_id, kind)
    return any(_verifies_with(k, kb, message, edge_sig) for k, kb in refs)
