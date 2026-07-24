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
import os
from typing import Optional

_SEP = "\x1f"  # unit separator — unambiguous field boundary


def _key(key: Optional[bytes] = None) -> Optional[bytes]:
    if key is not None:
        return key
    env = os.environ.get("NESTOR_SEAL_KEY")
    return env.encode() if env else None


def signing_enabled(key: Optional[bytes] = None) -> bool:
    """True iff a seal key is configured (env or injected)."""
    return _key(key) is not None


def sign_seal(source_norm: str, target_text: str, verifier: str,
              key: Optional[bytes] = None) -> str:
    """HMAC-SHA256 over the seal's bound fields. Returns ``""`` when no key is
    configured (unsigned — signing disabled)."""
    k = _key(key)
    if not k:
        return ""
    msg = _SEP.join((source_norm, target_text, verifier)).encode()
    return hmac.new(k, msg, hashlib.sha256).hexdigest()


def seal_is_valid(source_norm: str, target_text: str, verifier: str,
                  seal_sig: str, key: Optional[bytes] = None) -> bool:
    """Whether ``seal_sig`` is a valid seal signature.

    With no key configured, signing is OFF and every seal is accepted (the
    legacy default). With a key, a seal is valid only if its stored signature
    matches an HMAC recomputed over its own fields — so a forged row whose
    ``seal_sig`` was written without the key is rejected.
    """
    if _key(key) is None:
        return True  # signing disabled — preserve legacy behavior
    expected = sign_seal(source_norm, target_text, verifier, key)
    return bool(seal_sig) and hmac.compare_digest(expected, seal_sig)
