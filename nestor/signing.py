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
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import warnings
from typing import Optional


class SigningRequiredError(RuntimeError):
    """``NESTOR_REQUIRE_SEAL_KEY`` is set but no ``NESTOR_SEAL_KEY`` is
    configured — strict mode refuses to serve seals it cannot verify."""


_warned_unsigned = False


def _key(key: Optional[bytes] = None) -> Optional[bytes]:
    if key is not None:
        return key
    env = os.environ.get("NESTOR_SEAL_KEY")
    return env.encode() if env else None


def _strict() -> bool:
    return os.environ.get("NESTOR_REQUIRE_SEAL_KEY", "").strip().lower() in (
        "1", "true", "yes", "on")


def signing_enabled(key: Optional[bytes] = None) -> bool:
    """True iff a seal key is configured (env or injected)."""
    return _key(key) is not None


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


def sign_seal(source_norm: str, target_text: str, verifier: str,
              key: Optional[bytes] = None) -> str:
    """HMAC-SHA256 over the seal's bound fields. Returns ``""`` when no key is
    configured (unsigned — signing disabled)."""
    k = _key(key)
    if not k:
        return ""
    return hmac.new(k, _message(source_norm, target_text, verifier),
                    hashlib.sha256).hexdigest()


def seal_is_valid(source_norm: str, target_text: str, verifier: str,
                  seal_sig: str, key: Optional[bytes] = None) -> bool:
    """Whether ``seal_sig`` is a valid seal signature.

    With no key configured, signing is OFF and every seal is accepted (the
    legacy default) — but that silently reopens the Nestor#2 forgery, so it
    warns once, and ``NESTOR_REQUIRE_SEAL_KEY=1`` turns the degrade into a hard
    refusal. With a key, a seal is valid only if its stored signature matches an
    HMAC recomputed over its own fields.
    """
    if _key(key) is None:
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
    expected = sign_seal(source_norm, target_text, verifier, key)
    return bool(seal_sig) and hmac.compare_digest(expected, seal_sig)
