"""What was asked and had no verified answer — the seal queue's odometer.

A ``pending`` answer means nothing verified matched, and the architecture this
package exists to serve rests on that set shrinking: every seal retires a
question from the inference path permanently. That is a claim about a *rate*,
and until now nothing measured it. The ledger holds 599 seals against 4
recorded passages — 5.7% of everything known is sealed — and the question a
human actually faces, *"which of these should I seal next?"*, has a correct
answer (the ones missed most often) and had no data behind it. Sealing in the
order things happen to be written is the least efficient possible ordering for
a cache.

**Two tiers, and the threshold is not a compromise.** A question asked once is
noise; a question asked twice is a gap. You would not want singletons in a seal
queue anyway — a one-off is exactly what is not worth a human's scarce seal —
so gating at ``k >= 2`` improves the queue *and* means no question asked once
is ever written down in readable form. The privacy property falls out of the
correct design rather than costing anything. Same shape as homestead's
``cover_counts``, where a category that does not survive ``k >= 2`` is absent
rather than reported as zero.

So :data:`_HASH_ONLY_UNTIL` sightings store only ``sha256(source_norm)``, and
the readable text lands when the gate opens.

**Honest scope.** A singleton row still confirms a guess: someone holding the
exact normalized query can test whether it was asked. It cannot be enumerated
back to text, and that is the whole of what it hides. Stated here rather than
implied, the way ``corpus-lens``'s ``CoarseTime`` declares that ``day_offset %
7`` still leaks weekly cadence.

**A miss is not a proposal, and must never be recorded as one.**
:func:`nestor.answer.propose` writes a ``draft``, and the cascade serves drafts
at tier 2 — so a miss queued that way would put an *empty answer* in the
servable tier, which is strictly worse than the honest ``pending`` it replaced.
A proposal says *a machine produced an answer and wants review*; a miss says
*nobody has an answer*. Different tables, deliberately.

**This is a record of what the operator asked.** It does not travel: bundles
carry sealed answers, which are the portable asset, and not the record of what
was not known (``portable.py`` draws the same line for warrants — an import may
carry a warrant and may never carry a conclusion about it). Nothing here is
served, exported, or reachable from the read path.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .storage import Storage

#: Sightings stored as a hash alone. The readable form appears at the next one.
#: Also the floor :func:`coverage` reports at, because the two are the same
#: number for the same reason — see the module docstring.
_HASH_ONLY_UNTIL = 1

#: Default page for the queue readout. A display page, not the set.
_DEFAULT_LIMIT = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(source_norm: str) -> str:
    """The identity of a miss: a hash of its normalized form.

    Normalized, not raw, so the same question asked with different spacing or
    casing counts once — the same key the store already uses to decide two rows
    are about one thing.
    """
    return hashlib.sha256(source_norm.encode("utf-8")).hexdigest()


def supports_misses(store: Storage) -> bool:
    """Whether ``store`` can carry a miss log. Absence is not an error."""
    return all(hasattr(store, name) for name in
               ("memory_record_miss", "memory_misses", "memory_miss_totals"))


def record(store: Storage, source_norm: str, source_lang: str = "",
           target_lang: str = "") -> int:
    """Count one miss; return its new sighting count, or ``0`` if not recorded.

    Returns rather than raises on a store that cannot carry misses, because an
    odometer is not worth failing an answer over. It does **not** swallow the
    reason — the caller surfaces it (see :func:`nestor.answer.ask`), which is
    the difference between fail-open and fail-silent. This box has spent
    enough on the second: an expired propagation token stopped eleven
    verticals for three and a half weeks with no signal, and a Grove sender
    wrapped in ``except Exception: pass`` has sent zero messages since it was
    written.
    """
    if not source_norm.strip() or not supports_misses(store):
        return 0
    return int(store.memory_record_miss(  # type: ignore[attr-defined]
        digest(source_norm), source_norm, source_lang, target_lang, _now()))


def queue(store: Storage, limit: int = _DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """The seal queue: misses seen more than once, most-missed first.

    Only rows past the gate are returned, so every entry carries readable text.
    A caller never sees a row it cannot act on.
    """
    if not supports_misses(store):
        return []
    rows = store.memory_misses(_HASH_ONLY_UNTIL + 1, max(1, limit))  # type: ignore[attr-defined]
    return [{"query": str(r.get("source_norm") or ""),
             "seen": int(r.get("seen") or 0),
             "source_lang": str(r.get("source_lang") or ""),
             "target_lang": str(r.get("target_lang") or ""),
             "first_seen": str(r.get("first_seen") or ""),
             "last_seen": str(r.get("last_seen") or "")} for r in rows]


def coverage(store: Storage, limit: int = _DEFAULT_LIMIT) -> dict[str, Any]:
    """What the ratchet has and has not retired.

    ``withheld`` is the count of distinct questions seen exactly once, whose
    text is deliberately not stored. Reported as a number so the readout is
    honest about how much it is not showing — an absence with a stated size,
    rather than a queue that quietly looks shorter than the truth.
    """
    if not supports_misses(store):
        return {"supported": False}
    totals = store.memory_miss_totals()  # type: ignore[attr-defined]
    distinct = int(totals.get("distinct_misses") or 0)
    surfaced = int(totals.get("surfaced") or 0)
    return {
        "supported": True,
        "distinct_misses": distinct,
        "total_misses": int(totals.get("total_misses") or 0),
        "surfaced": surfaced,
        "withheld": distinct - surfaced,
        "queue": queue(store, limit),
    }
