#!/usr/bin/env python3
"""Step 3 of the quorum memo — age the seals, and change nothing about serving.

    python scripts/due_for_reverification.py --ledger l.jsonl --older-than 90
    python scripts/due_for_reverification.py --ledger l.jsonl --expected-head HASH

`docs/seal-staleness-and-quorum.md` §3 argues that staleness belongs in the
**queue**, not in the score: an aged seal keeps serving and keeps saying who
sealed it and when, and additionally shows up as *due for re-verification*, where
a person decides. The alternative — a decay curve feeding a score multiplier —
converts the one structural fact the package sells (*a human checked this*) back
into a confidence number, and does it silently, on a date nobody chose, with no
decision anywhere in the trail to explain why an answer stopped being served.

This is that listing. It is deliberately unable to do the other thing:

* it **reads**. No store is opened for writing, no row is touched, nothing is
  appended to the chain. `nestor/` is not imported except to verify and parse.
* it produces a **list**, not a number. There is no score, no weight, no
  multiplier, and nothing here is consulted by any serving path.
* every row it lists **is still being served**, and it says so.

**Age comes from the chain, never from the row.** §2 of the memo is the reason
and it is measurable: `signing._message` takes the HMAC over exactly
``[source_norm, target_text, verifier]``, so `tm_pairs.created_at` is outside the
signature. Measured — moving a sealed row's `created_at` back twenty-seven years
leaves `is_verified_seal` returning True. A staleness computed from that column
is a number anyone who can write the row can put back.

**And the chain's timestamp has one hole, which this reports rather than hides.**
`ledger.verify` documents it: each line is vouched for by the line after it, so
the newest entry has nothing vouching for it and editing it leaves the walk
passing. Measured on a three-entry chain — editing `ts` on entry 0 or 1 breaks
it, editing entry 2 does not. That is a property of an append-only chain, not a
defect, and `verify(expected_head=...)` closes it for a caller who knows where
the chain was. So this refuses to call the newest seal's age *verified* unless
``--expected-head`` was supplied, and says which it is doing.

The memo's §2 does not carry that caveat. It says the ledger's timestamp is
*"the only timestamp in the system that cannot be moved without the chain saying
so"*, which is true of every entry except the one that matters most to a
freshness question — the latest.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from nestor import ledger                              # noqa: E402

BOLD, DIM, GREEN, AMBER, RED, CYAN, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[36m", "\033[0m")

#: Kinds that record a human deciding a pair is good. A re-verification resets
#: the clock, so the *latest* of these per pair is the one that counts.
FRESHENING = ("seal", "countersign")

#: Kinds that end a pair's life. A rejected or superseded row is not stale, it
#: is finished, and listing it as work would be noise.
RETIRING = ("reject_pair", "reject_match", "supersede", "unseal", "seal_replaced")

UNREADABLE = "could not look"
BROKEN = "chain does not verify"


def read(path: pathlib.Path) -> list[dict] | None:
    """Chain entries, or ``None`` for *I could not look*."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            got = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(got, dict):
            return None
        out.append(got)
    return out


def _when(entry: dict) -> dt.datetime | None:
    ts = entry.get("ts")
    if not isinstance(ts, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(ts)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def age_seals(entries: list[dict], now: dt.datetime) -> list[dict]:
    """``[{pair_id, verifier, last, days, tail}]``, newest decision per pair.

    Retired pairs are dropped: a superseded row is finished, not overdue. The
    freshest freshening entry wins, so a re-verification resets the clock — which
    is the whole point of putting this in a queue rather than in a score.
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
                # Only the final line of the file is unvouched-for. A pair whose
                # freshest decision is that line has an age nothing corroborates.
                "tail": i == last_index,
            }
    rows = [r for p, r in latest.items() if p not in retired]
    for r in rows:
        r["days"] = (now - r["last"]).days
    return sorted(rows, key=lambda r: r["days"], reverse=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--older-than", type=int, default=90,
                    help="listing threshold in days (default 90). A LISTING "
                         "threshold — nothing stops being served at any value.")
    ap.add_argument("--expected-head", default="",
                    help="the chain head you last recorded; without it the "
                         "newest entry's timestamp is unvouched-for")
    ap.add_argument("--now", default="",
                    help="ISO instant to age against, for reproducible runs")
    args = ap.parse_args()

    path = pathlib.Path(args.ledger)
    print(f"\n{BOLD}due for re-verification{OFF}  {DIM}{path}{OFF}")

    entries = read(path)
    if entries is None:
        print(f"   {RED}{UNREADABLE}{OFF} — no readable chain at that path")
        print(f"   {DIM}Not 'nothing is stale'. Nothing about this chain is "
              f"known.{OFF}\n")
        return 1

    ok, detail = ledger.verify(str(path), args.expected_head or None) \
        if entries else (True, "")
    if not ok:
        print(f"   {RED}{BROKEN}{OFF} — {str(detail)[:70]}")
        print(f"   {DIM}Refusing to age entries somebody may have edited. A "
              f"date read off a broken{OFF}")
        print(f"   {DIM}trail is worse than no date, because it looks like "
              f"evidence.{OFF}\n")
        return 1

    now = dt.datetime.fromisoformat(args.now) if args.now else \
        dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)

    rows = age_seals(entries, now)
    due = [r for r in rows if r["days"] >= args.older_than]

    print(f"   {len(entries)} entrie(s), chain verifies, {len(rows)} live "
          f"sealed pair(s)")
    print(f"   {DIM}head {ledger.head(str(path))[:16]}…"
          + (f" matches --expected-head" if args.expected_head else "") + f"{OFF}")

    print(f"\n{BOLD}listed at {args.older_than}+ days{OFF}  "
          f"{DIM}still served, every one{OFF}")
    if not due:
        print(f"   none — {len(rows)} pair(s) all newer than "
              f"{args.older_than} days")
    # The tail marker is about whether anything vouches for this row's date, and
    # a matching --expected-head is exactly that: verify() has already refused
    # above if the head did not match, so reaching here with one supplied means
    # the last entry is pinned. Flagging it anyway would contradict this
    # command's own advice two paragraphs down — measured, on the run where
    # passing the correct head still printed "unvouched-for".
    unvouched = (lambda r: r["tail"] and not args.expected_head)
    for r in due[:20]:
        mark = RED if unvouched(r) else AMBER
        print(f"   {mark}{r['days']:5}d{OFF}  {r['pair_id'][:8]}…  "
              f"{r['verifier'][:22]:22} {DIM}{r['kind']}{OFF}"
              + (f"  {RED}[tail: age unvouched-for]{OFF}" if unvouched(r) else ""))
    if len(due) > 20:
        print(f"   {DIM}… and {len(due) - 20} more{OFF}")

    by_verifier = collections.Counter(r["verifier"] for r in due)
    if by_verifier:
        print(f"\n{BOLD}whose desk{OFF}")
        for who, n in by_verifier.most_common(6):
            print(f"   {n:4}  {who}")

    tail_rows = [r for r in rows if r["tail"]]
    print(f"\n{BOLD}what this did not do{OFF}")
    print(f"   {DIM}Nothing stopped being served. No row was written, no score "
          f"changed, no decision{OFF}")
    print(f"   {DIM}was recorded. {len(due)} pair(s) are work for a person; "
          f"until one of them acts,{OFF}")
    print(f"   {DIM}every pair above answers exactly as it did before this "
          f"ran.{OFF}")
    if tail_rows and not args.expected_head:
        print(f"\n   {RED}{len(tail_rows)} pair(s) rest on the chain's last "
              f"entry, whose timestamp nothing{OFF}")
        print(f"   {RED}vouches for.{OFF} {DIM}ledger.verify documents it: each "
              f"line is vouched for by the line{OFF}")
        print(f"   {DIM}after it, so the newest has none. Pass --expected-head "
              f"to close it. Their age{OFF}")
        print(f"   {DIM}is reported and is not verified — a distinction the "
              f"memo's §2 does not draw.{OFF}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
