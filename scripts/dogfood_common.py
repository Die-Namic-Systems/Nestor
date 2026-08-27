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
from nestor import keyring as keyring_mod
from nestor import signing
from nestor.sqlite_store import SqliteStore

ROOT = pathlib.Path(__file__).resolve().parents[1]
DECISIONS_DIR = ROOT / "docs" / "dogfood" / "decisions"
SEALS_DIR = ROOT / "docs" / "dogfood" / "seals"
VERIFIERS_PATH = ROOT / "docs" / "dogfood" / "verifiers.json"


class DecisionCorpusError(ValueError):
    """A decision file is unreadable, truncated, or collides with another.

    Raised — never swallowed — so a malformed or duplicated file fails loudly at
    the point of reading rather than vanishing from the corpus. *Absence is a
    recorded value, not a missing row:* a file that cannot be parsed is a defect
    to surface, not a row to silently drop. Subclasses ``ValueError`` so existing
    callers that catch ``ValueError`` keep working.
    """


class SealFileError(ValueError):
    """A seal file is malformed, orphaned, or fails cryptographic verification."""


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


@dataclasses.dataclass(frozen=True)
class SealRecord:
    """One human seal folded into the committed store at ``--rebuild``.

    ``pair_id`` is the deterministic row id from :func:`dogfood_store._row_id`.
    ``sealed_at`` is audit metadata for the git diff; the store's ``created_at``
    stays pinned to the decision file's date.
    """

    pair_id: str
    verifier: str
    sealed_at: str
    seal_sig: str
    file: str


def seal_files(seals_dir: pathlib.Path | None = None) -> list[pathlib.Path]:
    """Every ``*.json`` seal file, in stable order."""
    root = seals_dir or SEALS_DIR
    if not root.is_dir():
        return []
    return sorted(root.glob("*.json"))


def load_seal(path: pathlib.Path) -> SealRecord:
    """Read and validate one seal file under ``docs/dogfood/seals/``."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SealFileError(
            f"{path.name} is not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise SealFileError(f"{path.name} must contain a JSON object")
    pair_id = str(data.get("pair_id") or "").strip()
    verifier = str(data.get("verifier") or "").strip()
    sealed_at = str(data.get("sealed_at") or "").strip()
    seal_sig = str(data.get("seal_sig") or "").strip()
    missing = [name for name, val in (
        ("pair_id", pair_id), ("verifier", verifier),
        ("sealed_at", sealed_at), ("seal_sig", seal_sig),
    ) if not val]
    if missing:
        raise SealFileError(
            f"{path.name} is missing required field(s): {', '.join(missing)}")
    if path.stem != pair_id:
        raise SealFileError(
            f"{path.name} names pair_id {path.stem!r} but the file says "
            f"{pair_id!r} — the filename and body must agree")
    return SealRecord(pair_id=pair_id, verifier=verifier, sealed_at=sealed_at,
                      seal_sig=seal_sig, file=path.name)


def load_verifiers_keyring(path: pathlib.Path | None = None) -> keyring_mod.Keyring:
    """The distributable public keyring for dogfood seal verification."""
    target = path or VERIFIERS_PATH
    if not target.is_file():
        return keyring_mod.Keyring(path=str(target))
    return keyring_mod.load(str(target))


def _verifiers_label() -> str:
    try:
        return str(VERIFIERS_PATH.relative_to(ROOT))
    except ValueError:
        return str(VERIFIERS_PATH)


def apply_seal_files(store, seals_dir: pathlib.Path | None = None) -> int:
    """Upgrade draft rows to sealed when a matching seal file verifies.

    Returns the number of seals applied. Raises :class:`SealFileError` when a
    file is orphaned, duplicated, or cryptographically invalid.
    """
    paths = seal_files(seals_dir)
    if not paths:
        return 0
    records = [load_seal(path) for path in paths]
    seen: set[str] = set()
    for record in records:
        if record.pair_id in seen:
            raise SealFileError(
                f"duplicate seal for pair_id {record.pair_id!r}")
        seen.add(record.pair_id)

    ring = load_verifiers_keyring()
    if not list(ring.entries()):
        raise SealFileError(
            f"{len(records)} seal file(s) present but "
            f"{_verifiers_label()} has no verifier keys — "
            f"register the signer's ed25519 public key before committing seals")

    previous = keyring_mod.get_keyring()
    keyring_mod.set_keyring(ring)
    try:
        applied = 0
        for record in records:
            row = store.memory_get(record.pair_id)
            if row is None:
                raise SealFileError(
                    f"{record.file} seals pair_id {record.pair_id!r}, which is "
                    f"not in the rebuilt store — orphan seal file")
            if row.get("status") == "sealed":
                if (row.get("verifier") == record.verifier
                        and row.get("seal_sig") == record.seal_sig):
                    applied += 1
                    continue
                raise SealFileError(
                    f"{record.file} disagrees with the store row for "
                    f"{record.pair_id!r}")
            if row.get("status") != "draft":
                raise SealFileError(
                    f"{record.file} targets pair_id {record.pair_id!r} in "
                    f"status {row.get('status')!r}, expected draft")
            if not signing.seal_is_valid(row["source_norm"], row["target_text"],
                                         record.verifier, record.seal_sig):
                raise SealFileError(
                    f"{record.file}: seal_sig does not verify for verifier "
                    f"{record.verifier!r}")
            memory.add_pair(
                row["source_text"], row["target_text"],
                row["source_lang"], row["target_lang"],
                status="sealed", verifier=record.verifier,
                seal_sig=record.seal_sig, reason=row.get("reason", ""),
                origin=row.get("origin", ""), pair_id=record.pair_id,
                created_at=row.get("created_at", ""), audit=False, store=store)
            applied += 1
        return applied
    finally:
        keyring_mod.set_keyring(previous)


def finalize_sealed_store(store, expected_seals: int) -> dict:
    """The covenant after seal files are folded in."""
    stats = memory.stats(store=store)
    assert stats["sealed"] == expected_seals, (
        f"expected {expected_seals} sealed row(s) from seal files, store has "
        f"{stats['sealed']}")
    return stats


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
    """The covenant when no seal files are present. Returns ``memory.stats``."""
    return finalize_sealed_store(store, expected_seals=0)


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
