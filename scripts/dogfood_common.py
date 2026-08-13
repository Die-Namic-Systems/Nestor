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
import dataclasses
import json
import pathlib
import tempfile

from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore

ROOT = pathlib.Path(__file__).resolve().parents[1]
DECISIONS_DIR = ROOT / "docs" / "dogfood" / "decisions"


class DecisionCorpusError(ValueError):
    """A decision file is unreadable, truncated, or collides with another.

    Raised — never swallowed — so a malformed or duplicated file fails loudly at
    the point of reading rather than vanishing from the corpus. *Absence is a
    recorded value, not a missing row:* a file that cannot be parsed is a defect
    to surface, not a row to silently drop. Subclasses ``ValueError`` so existing
    callers that catch ``ValueError`` keep working.
    """


@dataclasses.dataclass(frozen=True)
class Decision:
    """One row of the decision corpus, traceable back to the file it came from.

    ``file`` is the decision file's stem (``"0079"`` for
    ``0079-the-store-on-itself.json``) — not the whole filename, because that
    stem is what origins and cross-references in this repo are written in.
    ``origin`` is ``"pr:<pr>"``, read from the file's own ``pr`` field, so a row
    served out of a built store still names the PR that added it.
    """

    file: str
    question: str
    commitment: str
    why: str
    origin: str
    #: The decision file's own ``date`` (``"2026-08-06"``), or ``""``. Used to
    #: stamp the derived store's ``created_at`` deterministically, so a rebuild
    #: does not churn a timestamp on every row.
    date: str = ""


def decision_files(decisions_dir: pathlib.Path | None = None) -> list[pathlib.Path]:
    """Every ``*.json`` decision file, in a stable order so builds reproduce.

    ``decisions_dir`` defaults to this checkout's ``docs/dogfood/decisions`` —
    pass it only to point at a fixture in a test.
    """
    return sorted((decisions_dir or DECISIONS_DIR).glob("*.json"))


def load_decisions(decisions_dir: pathlib.Path | None = None) -> list[Decision]:
    """Read the decision corpus from the repository, and nowhere else.

    **Direction: remote to local, never local to remote.** This reads the
    committed ``*.json`` files under ``decisions_dir`` (default:
    ``docs/dogfood/decisions`` in this checkout) and nothing besides — no
    ``data/nestor.db``, no process-wide store from
    :func:`nestor.storage.get_store`, no configured or ambient path. A memory
    whose rows came from somewhere nobody can see in the diff is not an audit
    trail, so every :class:`Decision` this returns is traceable to a file a
    reviewer read in a merged PR.

    One :class:`Decision` per entry in a file's ``"decisions"`` list, in the
    stable file order :func:`decision_files` returns — the order both
    ``scripts/dogfood_store.py`` and ``demo/the_dogfooding.py`` build and
    measure against, so it must not depend on filesystem iteration order.

    **Fails loud, never silent.** A file that does not parse (a truncated write,
    a bad merge) raises :class:`DecisionCorpusError` naming the file, rather than
    dropping out of the corpus unnoticed. And every row carries the same
    ``"<file-number>#<index>"`` identity ``nestor.triage`` enforces; two files
    sharing a PR number — or any collision of that identity — is refused rather
    than resolved by keeping one and losing the other. Corpus integrity is a
    guarantee, so it is a mechanism here, not a hope.
    """
    rows: list[Decision] = []
    seen_number: dict[str, str] = {}
    seen_id: set[str] = set()
    for path in decision_files(decisions_dir):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DecisionCorpusError(
                f"{path.name} is not valid JSON — truncated or malformed decision "
                f"file, refusing to skip it silently ({exc})") from exc
        stem = path.name.split("-")[0]
        if stem in seen_number:
            raise DecisionCorpusError(
                f"two decision files share PR number {stem!r}: {seen_number[stem]!r} "
                f"and {path.name!r}. A duplicate PR-number file collides ids and "
                f"would silently keep one — refusing.")
        seen_number[stem] = path.name
        origin = f"pr:{data.get('pr', '?')}"
        date = str(data.get("date", ""))
        for i, row in enumerate(data["decisions"]):
            row_id = f"{stem}#{i}"
            if row_id in seen_id:
                raise DecisionCorpusError(
                    f"duplicate decision id {row_id!r} (from {path.name!r}) — the "
                    f"'<file-number>#<index>' identity must be unique, refusing.")
            seen_id.add(row_id)
            rows.append(Decision(file=stem, question=row["question"],
                                 commitment=row["commitment"], why=row["why"],
                                 origin=origin, date=date))
    return rows


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
