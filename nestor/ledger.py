"""nestor.ledger — verify the hash-chained ledger (Nestor#2, RT-N2/RT-N3).

The ledger is tamper-*evident*: each line's ``prev`` is the SHA-256 of the whole
previous line. But a tamper-evident log nobody verifies is just a log — Nestor
shipped the chain and no verifier. This is the verifier: walk the chain and
confirm every link. Run it on read/boot; a broken chain is a refusal, not a
warning.

One limit, stated up front because it is easy to assume away: the walk vouches
for every line *except the last*, which nothing follows. :func:`head` returns the
tip and :func:`verify` takes an ``expected_head`` for a caller who kept it
somewhere the ledger's writer cannot reach — which is the only thing that can
close it, here or anywhere.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional, Tuple


class LedgerError(RuntimeError):
    """The ledger is unusable (e.g. a non-file path that would swallow the
    audit trail) or its hash-chain is broken."""


def _path(path: Optional[str] = None) -> Path:
    if path is None:
        from .cascade import _ledger_path  # lazy: avoid an import cycle
        return _ledger_path()
    return Path(path)


def head(path: Optional[str] = None) -> str:
    """SHA-256 of the last line — the chain's current tip.

    The value the **next** entry will carry as its ``prev``, and the one thing
    that protects the newest entry: see :func:`verify`. Returns ``"genesis"``
    for an absent or empty ledger, so a fresh instance has a head like any other.
    """
    p = _path(path)
    if not p.exists():
        return "genesis"
    last = ""
    for raw in p.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            last = raw.strip()
    return hashlib.sha256(last.encode("utf-8")).hexdigest() if last else "genesis"


def verify(path: Optional[str] = None,
           expected_head: Optional[str] = None) -> Tuple[bool, str]:
    """Walk the chain: line N's ``prev`` must equal SHA-256 of line N-1's bytes,
    rooted at ``"genesis"``. Returns ``(ok, detail)``.

    Editing any past line changes its hash, so the next line's ``prev`` no
    longer matches — the break is detected here.

    **Except for the last line.** Each line is vouched for by the line after it,
    so the newest entry has nothing after it to vouch for it: edit it, and the
    walk still passes. That is a property of the chain, not a bug in the walk,
    and it is not marginal — the newest entry is the one that just recorded who
    sealed what, and "the most recent decision is the editable one" is a strange
    thing for an audit trail to leave unsaid.

    ``expected_head`` closes it, for a caller who knows where the chain was: pass
    a previously recorded :func:`head` and this refuses a tip that does not match
    it. Anything that keeps that value outside the file works — a CI variable, a
    monitoring system, the ops process that ran the last check. :mod:`nestor.frank`
    is the same idea taken to its conclusion: every entry is mirrored into a
    ledger held by somebody else, carrying its own ``local_hash``.
    """
    p = _path(path)
    if not p.exists():
        if expected_head and expected_head != "genesis":
            return False, (f"no ledger at {p}, but head {expected_head[:16]}… was "
                           f"expected — the trail is missing, not empty")
        return True, "no ledger yet"
    prev = "genesis"
    count = 0
    # Numbered from 1, because the only thing anyone does with "line 7" is open
    # the file at line 7. This counted from 0 and reported the third line of a
    # damaged ledger as "line 2" — an audit message that sends the person acting
    # on it to the wrong line is worse than one that says nothing.
    for i, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
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
    if expected_head and expected_head != prev:
        return False, (f"chain walks clean over {count} entries but its head is "
                       f"{prev[:16]}…, not the expected {expected_head[:16]}… — the "
                       f"last entry was edited, or entries were added or removed")
    return True, f"intact — {count} entries"


def entries(kind: Optional[str] = None, path: Optional[str] = None,
            limit: int = 500) -> list[dict]:
    """Ledger entries, newest last, optionally filtered by ``kind``.

    The chain is the only record of things the store cannot hold. The memory
    keeps one row per normalized source, so when a seal is replaced the previous
    target and verifier survive *only* here — reading them back needs an
    accessor, or the audit trail is write-only in practice.

    Deliberately does NOT verify the chain: a caller investigating a broken
    ledger still needs to see what is in it. Call :func:`verify` for that, and
    treat the two answers together.

    This walk returns the lines that **parse**. The ones that do not are
    :func:`unreadable`'s: they are not returned here, and before that function
    existed nothing counted them — :func:`verify` names the first and stops,
    which is a verdict and never an inventory.
    """
    p = _path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:                      # noqa: BLE001 — the other walk's, see unreadable()
            continue
        if kind is None or rec.get("kind") == kind:
            out.append(rec)
    return out[-limit:]


def unreadable(path: Optional[str] = None) -> list[dict]:
    """The lines this ledger holds that are not valid JSON — ``{"line", "error"}``.

    Only writers of JSON append here, so a line that will not parse is a thing
    that cannot happen: a torn write, a truncated copy, an editor, a merge. It
    happens anyway, and until this existed **every reader that shows you the
    chain ignored it**. :func:`entries` walked past such a line and returned one
    fewer record without a word, so a four-line ledger showed three entries and
    nothing marked the gap — in ``nestor ledger entries``, in the UI's ledger
    tab, and in the ``ledger`` block of an export bundle, which is read by
    exactly the party who cannot go and look at the file. :func:`verify` did
    refuse, and so does the append path; neither is a caller of :func:`entries`,
    and neither says how many lines are missing from what you are looking at.

    So this is the other walk, and that is the shape of the fix: one pass
    collects what parses and one collects what does not, each bounded by
    construction, rather than one pass filtering and discarding. Together with
    an unfiltered, untruncated :func:`entries` they account for every non-blank
    line in the file — ``kind`` and ``limit`` narrow that side, never this one.

    ``line`` numbers from 1 and matches :func:`verify`'s, so a line named here
    can be opened with ``sed -n '<line>p'``. There is no ``limit``: the file is
    already fully in memory by the time this returns, so truncating the damage
    report would buy nothing and cost the only reason to read it.

    Returns ``[]`` for a ledger that does not exist, like :func:`entries` — an
    absent trail is not a damaged one, and :func:`verify` is where that
    distinction is already drawn.
    """
    p = _path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    for i, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            json.loads(line)
        except Exception as e:                 # noqa: BLE001 — this walk collects them
            out.append({"line": i, "error": str(e)})
    return out
