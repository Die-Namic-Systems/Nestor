"""Staleness computation for sealed pairs.

Shared by ``nestor/ui.py`` (the API endpoint) and
``scripts/due_for_reverification.py`` (the CLI listing).
"""
from __future__ import annotations

from datetime import datetime, timezone

#: Kinds that record a human deciding a pair is good.  A re-verification
#: resets the clock, so the *latest* of these per pair is the one that counts.
FRESHENING = ("seal", "countersign")

#: Kinds that end a pair's life.  A rejected or superseded row is not stale,
#: it is finished, and listing it as work would be noise.
RETIRING = ("reject_pair", "reject_match", "supersede", "unseal", "seal_replaced")


def _when(entry: dict) -> datetime | None:
    """Parse an entry's ``ts`` into an aware datetime, or None."""
    ts = entry.get("ts")
    if not isinstance(ts, str):
        return None
    try:
        parsed = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def age_seals(entries: list[dict], now: datetime) -> list[dict]:
    """``[{pair_id, verifier, last, days, tail}]``, newest decision per pair.

    Retired pairs are dropped: a superseded row is finished, not overdue.  The
    freshest freshening entry wins, so a re-verification resets the clock —
    which is the whole point of putting this in a queue rather than in a score.
    """
    latest: dict[str, dict] = {}
    retired: set[str] = set()
    last_index = len(entries) - 1
    for i, e in enumerate(entries):
        pair_id = str(e.get("pair_id") or "")
        if not pair_id:
            continue
        kind = e.get("kind")
        if kind in RETIRING:
            retired.add(pair_id)
            continue
        if kind not in FRESHENING:
            continue
        when = _when(e)
        if when is None:
            continue
        prior = latest.get(pair_id)
        if prior is None or when >= prior["last"]:
            latest[pair_id] = {
                "pair_id": pair_id,
                "verifier": str(e.get("verifier") or ""),
                "last": when,
                "kind": kind,
                # Only the final line of the file is unvouched-for.  A pair
                # whose freshest decision is that line has an age nothing
                # corroborates.
                "tail": i == last_index,
            }
    rows = [r for p, r in latest.items() if p not in retired]
    for r in rows:
        r["days"] = (now - r["last"]).days
    return sorted(rows, key=lambda r: r["days"], reverse=True)
