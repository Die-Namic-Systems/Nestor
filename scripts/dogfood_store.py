#!/usr/bin/env python3
"""The growing decision memory, rebuilt from the repository and nothing else.

    python scripts/dogfood_store.py --rebuild    # regenerate the committed store
    python scripts/dogfood_store.py --verify     # CI/pre-PR: it matches, nothing sealed

**The standing rule.** Every PR that makes a decision worth keeping adds one
file to ``docs/dogfood/decisions/`` and re-runs ``--rebuild``. The store grows
one merged PR at a time, and its whole contents are derivable from files a
reviewer can read in the diff.

**Direction: remote to local, never local to remote.** This script builds the
store in a temporary directory from the decision files in *this checkout*, and
imports nothing else. It never reads a developer's ``data/nestor.db``, never
touches the process-wide store from :func:`nestor.storage.get_store`, and never
consults an ambient path. That is not a promise about how it is invoked — a
local store cannot reach the committed one because there is no code path from
one to the other, and ``test_dogfood_store.py`` poisons a process-wide store and
proves none of it arrives.

The reason is the same reason the whole exercise exists: a memory whose contents
came from somewhere nobody can see is not an audit trail. Every row here is
traceable to a file in a merged PR.

**Why one file per PR rather than one growing bundle.** A bundle would conflict
on every concurrent PR, and a binary ``.db`` would conflict unresolvably.
Separate files never collide, and the ``.db`` is derived rather than merged —
so the artifact can always be regenerated from text somebody reviewed.

**Nothing here seals.** Every row lands as a draft, and ``--verify`` fails if a
sealed one ever appears. The queue belongs to a human at ``nestor.ui``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import dogfood_common                                            # noqa: E402

from nestor import memory, portable                              # noqa: E402
from nestor.sqlite_store import SqliteStore                      # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
DECISIONS_DIR = ROOT / "docs" / "dogfood" / "decisions"
STORE_PATH = ROOT / "docs" / "dogfood" / "nestor.db"
BUNDLE_PATH = ROOT / "docs" / "dogfood" / "decisions.json"

DOMAIN = "decision"

#: Fixed namespace so a row's id is a pure function of the decision it came from
#: — identical across every rebuild and every machine. Not a secret and not
#: signed; it exists only to make ``uuid5`` deterministic, the way the file
#: order and the rows digest already are.
_ID_NS = uuid.UUID("b6f2d1e0-9c3a-4a7b-8e5f-2d1c0b9a8f7e")


def decision_files() -> list[pathlib.Path]:
    """Every decision file, in a stable order so the build is reproducible.

    Thin wrapper over :func:`dogfood_common.decision_files`, pointed at this
    checkout's ``DECISIONS_DIR`` — the reading itself lives there so this
    script and ``demo/the_dogfooding.py`` read the corpus one way.
    """
    return dogfood_common.decision_files(DECISIONS_DIR)


def load_decisions() -> list[tuple[str, str, str, str]]:
    """``(question, commitment, why, origin)`` from the repository's files only.

    Adapts :func:`dogfood_common.load_decisions` — the shared reader owns the
    remote-to-local rule and returns :class:`dogfood_common.Decision` rows;
    this unpacks them to the 4-tuple shape :func:`build` and this module's
    tests already expect, so nothing downstream had to change.
    """
    return [(d.question, d.commitment, d.why, d.origin)
            for d in dogfood_common.load_decisions(DECISIONS_DIR)]


def _row_id(d: "dogfood_common.Decision") -> str:
    """A row's id, as a pure function of the decision — stable across rebuilds."""
    return str(uuid.uuid5(_ID_NS, f"{d.file}\x1f{d.question}\x1f{d.commitment}"))


def build(store) -> dict:
    """Feed every decision in as a draft, with a **deterministic** id and
    ``created_at`` so the committed store and bundle are byte-identical on every
    rebuild.

    The id is ``uuid5`` over ``(file, question, commitment)`` and the timestamp is
    the decision file's own ``date`` — both pure functions of reviewed source. The
    rows digest never depended on either; pinning them stops the *artifact*
    churning, which used to bury a one-line change under ~560 lines of fresh
    uuids and rebuild timestamps and made the committed store re-dirty on any
    process that merely opened it.
    """
    for d in dogfood_common.load_decisions(DECISIONS_DIR):
        created_at = f"{d.date}T00:00:00+00:00" if d.date else ""
        memory.add_pair(d.question, d.commitment, DOMAIN, DOMAIN, status="draft",
                        reason=d.why, origin=d.origin, pair_id=_row_id(d),
                        created_at=created_at, store=store)
    return dogfood_common.assert_nothing_sealed(store)


def _bundle_digest(bundle: dict) -> str:
    """Over the rows, not the whole envelope — timestamps must not churn the diff."""
    rows = sorted((p["source_text"], p["target_text"], p["status"])
                  for p in bundle["pairs"])
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()[:16]


def _pin_bundle_time(bundle: dict) -> None:
    """Replace the export's ``_now()`` envelope timestamp with the latest decision
    date, so the committed bundle is a pure function of the decision files."""
    dates = [p.get("created_at", "") for p in bundle.get("pairs", [])
             if p.get("created_at")]
    bundle["created_at"] = max(dates) if dates else ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--rebuild", action="store_true",
                      help="regenerate the committed store from the decision files")
    mode.add_argument("--verify", action="store_true",
                      help="check the committed store matches the files, and seals nothing")
    args = ap.parse_args()

    files = decision_files()
    if not files:
        print(f"no decision files in {DECISIONS_DIR.relative_to(ROOT)}")
        return 1

    # Built in a temp dir, always. The committed store is a *copy* of a fresh
    # build, never a file this script has opened and mutated in place — so a
    # half-finished run cannot leave a store that no set of decision files
    # explains.
    with dogfood_common.opened(None) as (root, fresh):
        stats = build(fresh)
        bundle = portable.export_bundle(fresh)
        # The rows are pinned in build(); export_bundle still stamps the ENVELOPE
        # with _now(), which alone would churn the committed file on every rebuild.
        # Pin it to the latest decision date — deterministic, and the digest is
        # over the rows, not this, so nothing downstream shifts.
        _pin_bundle_time(bundle)
        digest = _bundle_digest(bundle)
        built = pathlib.Path(root) / "nestor.db"

        print(f"{len(files)} decision file(s) -> {stats['total']} pair(s): "
              f"{stats['draft']} draft, {stats['sealed']} sealed")
        print(f"rows digest: {digest}")

        if args.rebuild:
            STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            fresh.close()                       # checkpoint WAL before copying
            STORE_PATH.write_bytes(built.read_bytes())
            BUNDLE_PATH.write_text(
                json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            print(f"wrote {STORE_PATH.relative_to(ROOT)} and "
                  f"{BUNDLE_PATH.relative_to(ROOT)}")
            return 0

    # --verify: the committed store must say the same thing as the files.
    if not STORE_PATH.exists():
        print(f"! {STORE_PATH.relative_to(ROOT)} is missing — run --rebuild")
        return 1
    committed = SqliteStore(str(STORE_PATH))
    try:
        committed.memory_init()
        got = _bundle_digest(portable.export_bundle(committed))
        stats_committed = memory.stats(store=committed)
    finally:
        committed.close()

    if stats_committed["sealed"]:
        print(f"! the committed store has {stats_committed['sealed']} sealed row(s) — "
              f"this script proposes and must never confirm")
        return 1
    if got != digest:
        print(f"! the committed store does not match the decision files "
              f"({got} != {digest}) — run --rebuild and commit the result")
        return 1
    print("the committed store matches the decision files, and seals nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
