"""nestor.ledger — verify the hash-chained ledger (Nestor#2, RT-N2/RT-N3).

The ledger is tamper-*evident*: each line's ``prev`` is the SHA-256 of the whole
previous line. But a tamper-evident log nobody verifies is just a log — Nestor
shipped the chain and no verifier. This is the verifier: walk the chain and
confirm every link. Run it on read/boot; a broken chain is a refusal, not a
warning.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional, Tuple


class LedgerError(RuntimeError):
    """The ledger is unusable (e.g. a non-file path that would swallow the
    audit trail) or its hash-chain is broken."""


def verify(path: Optional[str] = None) -> Tuple[bool, str]:
    """Walk the chain: line N's ``prev`` must equal SHA-256 of line N-1's bytes,
    rooted at ``"genesis"``. Returns ``(ok, detail)``.

    Editing any past line changes its hash, so the next line's ``prev`` no
    longer matches — the break is detected here.
    """
    if path is None:
        from .cascade import _ledger_path  # lazy: avoid an import cycle
        p = _ledger_path()
    else:
        p = Path(path)
    if not p.exists():
        return True, "no ledger yet"
    prev = "genesis"
    count = 0
    for i, raw in enumerate(p.read_text(encoding="utf-8").splitlines()):
        line = raw.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception as e:  # a line that won't parse breaks the audit
            return False, f"line {i}: not valid JSON ({e})"
        if rec.get("prev") != prev:
            return False, (f"broken chain at line {i}: prev={rec.get('prev')!r} "
                           f"expected {prev!r}")
        prev = hashlib.sha256(line.encode("utf-8")).hexdigest()
        count += 1
    return True, f"intact — {count} entries"
