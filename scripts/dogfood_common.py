#!/usr/bin/env python3
"""The part every dogfood script must not get its own copy of.

There is one rule these scripts exist under — *the machine may propose and may
not confirm* — and it is enforced by a single assertion. A second script with a
second copy of that assertion is two paths into the same guarantee, one of which
some later script will forget: the shape ``TODO.md``'s closing note names and
``IDEAS.md`` §1.6/§1.7/§1.8 are the worked examples of.

So the covenant lives here, once, and a dogfood script cannot run a store
without going through it.
"""
from __future__ import annotations

import argparse
import contextlib
import pathlib
import tempfile

from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore


def add_output_args(ap: argparse.ArgumentParser) -> argparse.ArgumentParser:
    ap.add_argument("--keep", metavar="DIR",
                    help="write the store and ledger here instead of a temp dir")
    return ap


@contextlib.contextmanager
def opened(keep: str | None):
    """Yield a store rooted at ``keep`` or in a temp dir, and close it after.

    Closing matters more than it looks: a file-backed store runs in WAL mode, so
    recent commits may live only in ``nestor.db-wal`` until something
    checkpoints. ``SqliteStore.close`` checkpoints. A dogfood run that leaves
    without closing and then has its ``.db`` committed has committed a file
    missing the rows it was written to hold — the trap the README's quick start
    warns about, reached from the other end.
    """
    tmp = None
    if keep:
        root = pathlib.Path(keep)
        root.mkdir(parents=True, exist_ok=True)
    else:
        tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(tmp.name)
    try:
        cascade.set_ledger_path(root / "ledger.jsonl")
        store = SqliteStore(str(root / "nestor.db"))
        storage.set_store(store)
        store.memory_init()
        try:
            yield root, store
        finally:
            store.close()
    finally:
        if tmp is not None:
            tmp.cleanup()


def assert_nothing_sealed(store) -> dict:
    """The covenant. Returns ``memory.stats`` so a caller can print it.

    Asserted rather than printed because it is the one claim in a dogfood run
    that is not a measurement. A run that seals has not produced a worse number;
    it has broken the rule the whole exercise is a demonstration of, and it
    should fail the build rather than report itself.
    """
    stats = memory.stats(store=store)
    assert stats["sealed"] == 0, (
        f"{stats['sealed']} sealed row(s) — this script proposes and must never "
        f"confirm. A seal belongs to a human at nestor.ui (ground rule: the machine "
        f"may propose and may not confirm).")
    return stats


def feed_drafts(store, decisions, domain: str, origin: str) -> None:
    """``(question, commitment, reason)`` triples in as drafts. Nothing else.

    ``reason`` is the N4 column — Nestor always recorded why a reviewer said no
    and never why they said yes.
    """
    for question, commitment, reason in decisions:
        memory.add_pair(question, commitment, domain, domain, status="draft",
                        reason=reason, origin=origin, store=store)


def feed_rejections(store, rejections, domain: str) -> None:
    """``(question, alternative, reason, reopen_when)`` in as rejections.

    **Only for alternatives a human actually rejected.** A rejection is a
    person's "no", durable and signed, and a script writing one on its own
    initiative is the machine confirming — the same violation as sealing, in the
    one direction the covenant assertion above cannot see. `assert_nothing_sealed`
    counts sealed rows; it cannot tell whose "no" a rejection records. That part
    is on the author of the decision list.
    """
    for question, alternative, reason, reopen_when in rejections:
        memory.reject_match(question, domain, domain, target_text=alternative,
                            reason=reason, reopen_when=reopen_when, store=store)
