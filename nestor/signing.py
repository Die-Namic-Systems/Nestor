"""nestor.signing — bind a seal to a key the store does not hold.

Red-team finding (Nestor#2): ``status="sealed"`` and ``verifier`` are just
columns, so any caller that can write ``tm_pairs`` forges a human seal and it
serves as tier-1. This binds a seal to an HMAC over its load-bearing fields
``(source_norm, target_text, verifier)``, keyed by a secret held OUTSIDE the
store (``NESTOR_SEAL_KEY`` or injected). A store-writer without the key cannot
produce a signature ``best_sealed`` will accept — so a forged sealed row is not
served.

Stdlib only, so the dependency-light core is preserved. This is the symmetric
(HMAC) form; the asymmetric upgrade — an Ed25519 signature the verifier checks
with a public key, or a Biscuit capability — is the follow-on (see Nestor#2).

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
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import warnings
from typing import Optional

from . import keyring as keyring_mod


class SigningRequiredError(RuntimeError):
    """``NESTOR_REQUIRE_SEAL_KEY`` is set but no ``NESTOR_SEAL_KEY`` is
    configured — strict mode refuses to serve seals it cannot verify."""


_warned_unsigned = False


def _key(key: Optional[bytes] = None) -> Optional[bytes]:
    if key is not None:
        return key
    env = os.environ.get("NESTOR_SEAL_KEY")
    return env.encode() if env else None


def _signing_key(verifier: str, key: Optional[bytes] = None) -> Optional[bytes]:
    """The key ``verifier`` signs with. Raises if a keyring refuses them.

    The refusal is the feature: with per-verifier keys, an unregistered or
    revoked name has no key, and the alternative to raising is putting a name on
    a verification that nothing backs.
    """
    if key is not None:
        return key
    ring = keyring_mod.get_keyring()
    if ring is not None:
        return ring.signing_key(verifier)
    return _key(None)


def _verifying_keys(verifier: str, key: Optional[bytes] = None) -> list[bytes]:
    """Every key a seal by ``verifier`` may legitimately have been signed with.

    Usually one. Two only during migration: a keyring with a ``legacy_key`` also
    accepts signatures made under the old single deployment key, which is what
    every seal predating the keyring carries. Those are reported as ``legacy``
    by the curator rather than attributed to a person, because that is what they
    are.
    """
    if key is not None:
        return [key]
    ring = keyring_mod.get_keyring()
    if ring is not None:
        keys = []
        own = ring.verifying_key(verifier)
        if own is not None:
            keys.append(own)
        if ring.legacy_key:
            keys.append(ring.legacy_key)
        return keys
    shared = _key(None)
    return [shared] if shared else []


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

    def signed_with(k: Optional[bytes]) -> bool:
        return bool(k) and hmac.compare_digest(
            hmac.new(k, message, hashlib.sha256).hexdigest(), seal_sig)

    if signed_with(ring.verifying_key(verifier)):
        return "verifier"
    if signed_with(ring.legacy_key):
        return "legacy"
    return "none"


def _strict() -> bool:
    return os.environ.get("NESTOR_REQUIRE_SEAL_KEY", "").strip().lower() in (
        "1", "true", "yes", "on")


def signing_enabled(key: Optional[bytes] = None) -> bool:
    """True iff seals are signed at all — a keyring, or a shared key."""
    return _key(key) is not None or keyring_mod.enabled()


def _message(source_norm: str, target_text: str, verifier: str) -> bytes:
    """The bytes an HMAC is taken over. JSON-encoded array — a *structured*
    encoding so no combination of field values can collide by shifting a
    delimiter. (The old ``"\\x1f".join(...)`` form was forgeable: ``target_text``
    and ``verifier`` are not normalized and could contain the separator, so
    ``("ok\\x1fadmin", "alice")`` and ``("ok", "admin\\x1falice")`` signed the
    same bytes — Nestor#2 follow-up. Matches willow-mcp/session_binder's
    canonical encoding.)"""
    return json.dumps([source_norm, target_text, verifier],
                      separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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


def _rejection_key(verifier: str, key: Optional[bytes] = None) -> Optional[bytes]:
    """The key a rejection by ``verifier`` is signed with — and never a refusal.

    Deliberately not :func:`_signing_key`. A seal by an unregistered verifier
    must fail loudly; a *rejection* by one must not, because refusing to record
    a "no" is the one direction rejection cannot fail in — it would leave a bad
    answer serving because the reviewer's name was not on a list. An unknown
    verifier's rejection is recorded, honored, and reported as unsigned.
    """
    if key is not None:
        return key
    ring = keyring_mod.get_keyring()
    if ring is not None:
        own = ring.verifying_key(verifier)
        return own if own is not None else ring.legacy_key
    return _key(None)


def sign_rejection(query_norm: str, pair_id: str, target_text: str,
                   verifier: str, key: Optional[bytes] = None) -> str:
    """HMAC-SHA256 over a rejection's bound fields. ``""`` when signing is off."""
    k = _rejection_key(verifier, key)
    if not k:
        return ""
    return hmac.new(k, _rejection_message(query_norm, pair_id, target_text, verifier),
                    hashlib.sha256).hexdigest()


def rejection_is_valid(query_norm: str, pair_id: str, target_text: str,
                       verifier: str, reject_sig: str,
                       key: Optional[bytes] = None) -> bool:
    """Whether ``reject_sig`` is a valid rejection signature.

    NOTE: unlike :func:`seal_is_valid`, this is *reporting only* — Nestor honors
    a rejection whether or not it verifies. See ``memory.rejected_ids`` for why
    suppression fails safe in a way that serving does not.
    """
    k = _rejection_key(verifier, key)
    if k is None:
        # Nothing to check against: with signing off every rejection is as good
        # as any other, and saying "invalid" would be a report about the
        # deployment dressed up as a report about the reviewer.
        return not keyring_mod.enabled()
    expected = hmac.new(k, _rejection_message(query_norm, pair_id, target_text, verifier),
                        hashlib.sha256).hexdigest()
    return bool(reject_sig) and hmac.compare_digest(expected, reject_sig)


def sign_seal(source_norm: str, target_text: str, verifier: str,
              key: Optional[bytes] = None) -> str:
    """HMAC-SHA256 over the seal's bound fields. Returns ``""`` when no key is
    configured (unsigned — signing disabled).

    With a keyring installed this signs with ``verifier``'s own key, and raises
    :class:`~nestor.keyring.UnknownVerifierError` or
    :class:`~nestor.keyring.RevokedKeyError` if they have none. Callers reach
    here through ``memory.add_pair``, before the store write, so a refusal
    leaves nothing behind.
    """
    k = _signing_key(verifier, key)
    if not k:
        return ""
    return hmac.new(k, _message(source_norm, target_text, verifier),
                    hashlib.sha256).hexdigest()


def seal_is_valid(source_norm: str, target_text: str, verifier: str,
                  seal_sig: str, key: Optional[bytes] = None) -> bool:
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
    keys = _verifying_keys(verifier, key)
    if not keys and not keyring_mod.enabled():
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
    return any(hmac.compare_digest(
        hmac.new(k, message, hashlib.sha256).hexdigest(), seal_sig) for k in keys)
