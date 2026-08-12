"""The signature-verification path must compare in constant time.

`scripts/constant_time_guard.py` fails if a signature/MAC is compared with
``==``/``!=`` instead of ``hmac.compare_digest``. These tests assert the real path
is clean, that the guard actually flags the leak it exists to catch, and that it
does not cry wolf on the kind/trust/status comparisons that surround it.
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import constant_time_guard as ctg  # noqa: E402  (scripts/ is not an installed package)


def test_the_real_verification_path_is_constant_time():
    """The gate: nestor/signing.py verifies with hmac.compare_digest, never ==."""
    assert ctg.scan() == []


def test_it_flags_a_non_constant_time_secret_comparison():
    """The can-fail proof. Comparing a computed MAC to the supplied signature with
    == is the exact byte-at-a-time leak — the guard must see it."""
    leak = (
        "import hmac, hashlib\n"
        "def verify(key, message, sig):\n"
        "    mac = hmac.new(key, message, hashlib.sha256).hexdigest()\n"
        "    return mac == sig\n"        # the side channel
    )
    findings = ctg.scan_text(leak, "leak.py")
    assert findings, "the guard missed a == on a computed MAC"
    assert any(f.line == 4 for f in findings)


def test_it_does_not_flag_kind_or_trust_comparisons():
    """The false-positive guard. entry_kind/trust/status are not secrets, and the
    literal 'unsigned' contains 'sig' but is a Constant, not a Name — none flag."""
    benign = (
        'def f(entry_kind, trust, own):\n'
        '    a = entry_kind == "ed25519"\n'
        '    b = trust == "unsigned"\n'
        '    c = own.kind == "ed25519"\n'
        '    return a or b or c\n'
    )
    assert ctg.scan_text(benign, "benign.py") == []
