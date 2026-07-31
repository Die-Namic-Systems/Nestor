"""The cascade — memory, draft, seal. One loop per segment.

Segments that reach tier 2 are queued into the injected store's
documents/segments review pipeline; verification (tier 3) graduates them into
the TM via ``graduate_segment``. Every passage is appended to a local
hash-chained ledger (default ``data/ledger.jsonl``) — Nestor's audit trail.
Install a forwarder with :mod:`nestor.frank` to also mirror every entry into
FRANK, willow-mcp's shared append-only governance ledger.

Storage is injected (see :mod:`nestor.storage`): pass ``store=`` to the public
entry functions, or install one globally with ``storage.set_store``.

The ledger path is configurable — set ``NESTOR_LEDGER`` in the environment or
call :func:`set_ledger_path`. It defaults to the original ``data/ledger.jsonl``.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from . import frank, langid, memory
from .engine import get_engine
from .ledger import LedgerError, verify as _ledger_verify
from .matcher import matcher_audit_fields
from .segment import _split_segments
from .storage import Storage, get_store

try:                                    # POSIX only; the threading lock stands alone without it
    import fcntl
except ImportError:                     # pragma: no cover — Windows
    fcntl = None                        # type: ignore[assignment]


def _lock_file(handle, shared: bool = False) -> None:
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH if shared else fcntl.LOCK_EX)


def _unlock_file(handle) -> None:
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# One writer at a time, within this process. See ledger_append.
_append_lock = threading.Lock()

_DEFAULT_LEDGER = "data/ledger.jsonl"
_LEDGER_OVERRIDE: Optional[pathlib.Path] = None
_verified_ledgers: set[str] = set()  # paths already chain-verified this process

# path -> (byte offset of the last line THIS process wrote, that line's sha256).
# The append-time checkpoint; see _check_tail.
_checkpoints: dict[str, tuple[int, str]] = {}


def _line_sha(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _check_tail(ledger: pathlib.Path) -> None:
    """Refuse if the tail has moved under us since this process last wrote to it.

    The full chain walk runs **once per process** (``_verified_ledgers``), which
    is a deliberate cost trade and leaves a real window: :mod:`nestor.ui` is a
    long-lived process, so a reviewer's shift is hours of appends after a single
    verification. Tampering during that shift was caught by the next
    ``verify()`` — a page render, a CLI run, tomorrow — rather than by the next
    append, which meanwhile chained new entries onto it and laundered it into
    history (IDEAS §5.3).

    This closes the tail of that window on every append, for the price of
    reading the bytes appended since our last one:

    * we remember the offset and hash of the line we last wrote;
    * that line must still be there, unchanged — it is the entry the chain
      itself cannot vouch for while it is the newest one (IDEAS §5.5);
    * anything appended after it, by us or by another process, must chain onto
      it and onto each other.

    What it does **not** cover, stated plainly: an edit to a line *older* than
    our checkpoint. That breaks the link at the following line, and only the
    full walk finds it — so ``verify()`` is still the complete answer, and the
    Ledger view calls it on every render. The checkpoint is the cheap guard on
    the part of the chain that is being written right now, not a replacement for
    the walk.

    The one assumption is that the ledger is bytes-appended-only, which is the
    same thing the hash chain assumes already: an offset into it stays valid
    because nothing ahead of it is supposed to move. A rewrite that shifts it
    lands us mid-line, the hash does not match, and the refusal is correct.

    **The caller must hold the file lock**, shared or exclusive — the same rule
    :func:`_verify_chain_once` carries, and for the same reason: this reads
    bytes another process may be part-way through writing, and a torn line reads
    as a broken chain. Refusing a perfectly good seal because a colleague was
    mid-append is a worse failure than the one being guarded against.
    """
    cp = _checkpoints.get(str(ledger))
    if cp is None:
        return
    offset, digest = cp
    try:
        with open(ledger, "rb") as fh:
            fh.seek(offset)
            raw = fh.read()
    except FileNotFoundError:
        raise LedgerError(
            f"the ledger this process has been appending to is gone: {ledger}. "
            f"Its trail cannot be extended somewhere else — restore it, or point "
            f"NESTOR_LEDGER at the chain you mean to continue.") from None
    lines = [ln.strip() for ln in raw.decode("utf-8", "replace").splitlines() if ln.strip()]
    if not lines:
        raise LedgerError(
            f"the entry this process last wrote is no longer in {ledger} — the "
            f"trail was truncated. Refusing to append onto what is left.")
    if _line_sha(lines[0]) != digest:
        raise LedgerError(
            f"the entry this process last wrote to {ledger} has changed since it "
            f"was written. The newest entry is the one the chain cannot vouch for, "
            f"and it has been edited — refusing to chain onto a tampered tail.")
    prev = digest
    for offset_i, line in enumerate(lines[1:], start=1):
        try:
            rec = json.loads(line)
        except Exception as exc:                      # noqa: BLE001
            raise LedgerError(f"entry {offset_i} after this process's last append is "
                              f"not valid JSON ({exc}) — refusing to append") from None
        if rec.get("prev") != prev:
            raise LedgerError(
                f"an entry appended after this process's last one does not chain "
                f"onto it: prev={rec.get('prev')!r}, expected {prev!r}. Refusing "
                f"to extend a broken tail.")
        prev = _line_sha(line)


def set_ledger_path(path) -> None:
    """Override the hash-chained ledger location (wins over ``NESTOR_LEDGER``)."""
    global _LEDGER_OVERRIDE
    _LEDGER_OVERRIDE = pathlib.Path(path)
    reset_ledger_session()


def reset_ledger_session() -> None:
    """Drop in-process verify/checkpoint state without changing the path.

    Changing the ledger file or simulating a fresh process (tests, tooling) must
    not inherit another chain's ``_verified_ledgers`` / ``_checkpoints`` cache.
    """
    _verified_ledgers.clear()
    _checkpoints.clear()


def _ledger_path() -> pathlib.Path:
    if _LEDGER_OVERRIDE is not None:
        return _LEDGER_OVERRIDE
    return pathlib.Path(os.environ.get("NESTOR_LEDGER", _DEFAULT_LEDGER))


@dataclass
class Passage:
    source: str
    target: str
    tier: int           # 1 = memory (sealed), 2 = draft, 0 = no candidate
    state: str          # "sealed" | "draft" | "pending"
    engine: str = ""
    confidence: float = 0.0
    segment_id: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def mark(self) -> str:
        return {"sealed": "✓", "draft": "~", "pending": "!"}[self.state]


def _refuse_unusable_path(ledger: pathlib.Path) -> None:
    """The checks that need no read: the trail must not be redirectable."""
    # Fail closed: a ledger that exists but is not a regular file (e.g.
    # /dev/null) would silently swallow the audit trail. Refuse it (Nestor#2).
    if ledger.exists() and not ledger.is_file():
        raise LedgerError(f"ledger path is not a regular file — the audit trail "
                          f"cannot be suppressed: {ledger}")
    # A symlinked ledger (or symlinked final component) redirects the chain onto
    # storage the attacker controls; is_file() follows the link and passes, so
    # check the link itself (Nestor#2 follow-up).
    if ledger.is_symlink():
        raise LedgerError(f"ledger path is a symlink — refusing to chain onto a "
                          f"redirected audit trail: {ledger}")


def _verify_chain_once(ledger: pathlib.Path) -> None:
    """Walk the chain the first time this process touches it, and remember.

    **The caller must hold the file lock.** This reads the whole file, and a
    reader without the lock can catch another process mid-append and see a
    half-written final line — which walks as a broken chain and refuses a
    perfectly good seal. That is not hypothetical: it turned a green branch red
    the first time two processes appended at once in CI, and it failed exactly
    once per process, because the result is cached below.
    """
    key = str(ledger)
    if key not in _verified_ledgers and ledger.exists():
        ok, detail = _ledger_verify(key)
        if not ok:
            raise LedgerError(f"ledger chain is broken — refusing to append: {detail}")
        _verified_ledgers.add(key)


def ledger_preflight() -> None:
    """Raise :class:`LedgerError` if the next append would be refused. Writes nothing.

    The refusals have to be available *before* a caller mutates the store, or
    fail-closed becomes fail-late: a seal written to the database and then
    refused by the ledger leaves a verified answer with no trail, which is the
    one state this package exists to prevent. So a decision that must be audited
    calls this first, and only writes if the trail will take it. See
    ``memory.add_pair`` and the ``reject_*`` entry points.

    Both reads take a **shared** lock — several processes may verify at once,
    none may do it while a writer holds the exclusive lock.
    """
    ledger = _ledger_path()
    _refuse_unusable_path(ledger)
    if not ledger.exists():
        # Nothing to open. A checkpoint for a path with no file is the trail
        # having been deleted under a running process, which _check_tail names.
        _check_tail(ledger)
        return
    if str(ledger) in _verified_ledgers and str(ledger) not in _checkpoints:
        return                       # neither read has anything left to do
    with _append_lock:
        with open(ledger, "r", encoding="utf-8") as f:
            _lock_file(f, shared=True)
            try:
                _verify_chain_once(ledger)
                _check_tail(ledger)
            finally:
                _unlock_file(f)


def ledger_append(entry: dict) -> None:
    """Append one entry to the hash-chained ledger. The only way to write to it.

    Every entry's ``prev`` is the hash of the line before it, so reading the tail
    and writing the next line have to be one indivisible step. They were not, and
    the consequence was not a lost entry but a **broken chain**: eight threads
    appending concurrently wrote all 160 lines and left a trail that
    :func:`~nestor.ledger.verify` rejects — an audit trail that indicts itself,
    on a system whose whole claim is the trail. :mod:`nestor.ui` serves from a
    thread pool, so two reviewers sealing at the same moment reach this.

    Two locks, because there are two kinds of concurrent writer. A process-wide
    lock covers threads. An advisory file lock covers *processes* — a UI and a
    `nestor import` against the same ledger are not exotic — and is best-effort:
    where ``fcntl`` is absent the threading lock still holds, and the file lock
    is a lock, not a guarantee about other software.

    Every append also re-checks the tail it is extending — see :func:`_check_tail`
    — and records where its own line landed, so the next one can do the same.
    That is the guard the once-per-process chain walk does not give: the walk
    happens at the start of a long-lived process and the appends keep coming for
    hours afterwards.

    The FRANK mirror is deliberately forwarded **after** the lock is released:
    it speaks to a subprocess over stdio, and holding the ledger's write lock
    across somebody else's I/O would make a slow governance mirror into a stalled
    review queue.
    """
    ledger = _ledger_path()
    _refuse_unusable_path(ledger)
    # Ask before opening: "a+" below re-creates a deleted ledger, and a
    # checkpoint for a path with no file means the trail was removed under a
    # running process. Re-creating it would quietly start a second chain and
    # call it the first one. A stat needs no lock and reads no content.
    if not ledger.exists():
        _check_tail(ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "prev": "genesis", **entry}
    with _append_lock:
        # "a+" creates the file if absent and keeps the read and the write on one
        # handle, so the tail we hash is the tail we chain onto.
        with open(ledger, "a+", encoding="utf-8") as f:
            _lock_file(f)
            try:
                # Both reads happen inside the lock, for the same reason the
                # tail read below does: anything that reads this file while
                # another process is mid-append sees a torn line.
                _verify_chain_once(ledger)
                _check_tail(ledger)
                f.seek(0)
                last = ""
                for raw in f:
                    if raw.strip():
                        last = raw.strip()
                if last:
                    entry["prev"] = hashlib.sha256(last.encode("utf-8")).hexdigest()
                line = json.dumps(entry, ensure_ascii=False)
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
                # Where our line landed, measured after the write and while the
                # lock is still held, so no cooperating writer can have moved the
                # end of the file between the write and the measurement.
                size = os.fstat(f.fileno()).st_size
                start = size - len(line.encode("utf-8")) - 1
                if start >= 0:
                    _checkpoints[str(ledger)] = (start, _line_sha(line))
            finally:
                _unlock_file(f)
    # Mirror into FRANK (willow-mcp's shared governance ledger) when a forwarder
    # is installed — see nestor.frank. The local chain above is written first and
    # stays the source of truth: a governance mirror that is down, denied, or
    # absent must never fail a translation, so the forward is best-effort unless
    # NESTOR_FRANK_STRICT says otherwise.
    try:
        frank.forward(entry, line_hash=hashlib.sha256(line.encode("utf-8")).hexdigest())
    except Exception:
        if frank.strict():
            raise


# Kept because six modules import it and did so before it had a public name.
_ledger_append = ledger_append


def translate_segment(text: str, source_lang: str, target_lang: str,
                      engine=None, document_id: str = "", position: int = 0,
                      store: Optional[Storage] = None) -> Passage:
    store = get_store(store)
    # tier 1 — Nestor's ledger
    hit = memory.best_sealed(text, source_lang, target_lang, store=store)
    if hit:
        m = memory.get_matcher()
        audit = matcher_audit_fields(m)
        passage = Passage(source=text, target=hit["pair"]["target_text"], tier=1,
                          state="sealed", engine="memory",
                          confidence=hit["similarity"],
                          meta={"pair_id": hit["pair"]["id"],
                                "verifier": hit["pair"]["verifier"],
                                **audit})
    else:
        # tier 2 — Nova's draft
        engine = engine or get_engine()
        try:
            draft = engine.translate(text, source_lang, target_lang, store=store)
        except TypeError:
            # A custom engine that doesn't accept store= relies on the global store.
            draft = engine.translate(text, source_lang, target_lang)
        if draft:
            passage = Passage(source=text, target=draft.text, tier=2, state="draft",
                              engine=draft.engine, confidence=draft.confidence)
        else:
            passage = Passage(source=text, target="", tier=0, state="pending",
                              engine=getattr(engine, "name", ""))
        # queue for tier 3 — the seal
        if document_id:
            seg = store.create_segment(document_id=document_id, position=position,
                                       source_text=text, candidate=passage.target,
                                       jeles_score=passage.confidence)
            passage.segment_id = seg["id"]

    _ledger_append({
        "kind": "passage", "tier": passage.tier, "state": passage.state,
        "engine": passage.engine, "confidence": passage.confidence,
        "source_lang": source_lang, "target_lang": target_lang,
        "source_sha": hashlib.sha256(text.encode()).hexdigest()[:16],
        "segment_id": passage.segment_id,
        **({k: v for k, v in passage.meta.items()
            if k.startswith("matcher")} if passage.tier == 1 else {}),
    })
    return passage


def translate_text(text: str, target_lang: str, source_lang: str = "",
                   engine_name: str = "auto", title: str = "",
                   store: Optional[Storage] = None) -> tuple[dict, list[Passage]]:
    """Run the cascade over a block of text. Returns (document, passages).
    A document is created only if at least one segment needs review."""
    store = get_store(store)
    store.init_db()
    memory.init_tm(store=store)
    source_lang = source_lang or langid.detect(text)
    segments = _split_segments(text)
    engine = get_engine(engine_name)

    doc = store.create_document(title=title or (segments[0][:40] if segments else "untitled"),
                                source_lang=source_lang, target_lang=target_lang)
    passages = [
        translate_segment(seg, source_lang, target_lang, engine=engine,
                          document_id=doc["id"], position=i, store=store)
        for i, seg in enumerate(segments)
    ]
    if any(p.tier != 1 for p in passages):
        store.update_document_status(doc["id"], "pending_review")
    else:
        store.update_document_status(doc["id"], "verified")
    return doc, passages


def reject_segment(segment_id: str, verifier: str = "", reason: str = "",
                   store: Optional[Storage] = None) -> Optional[dict]:
    """The reviewer's "no" — the missing half of :func:`graduate_segment`.

    A reviewer could always accept a queued draft and never reject one, so a bad
    candidate came back identically forever and every reviewer paid the same
    attention tax to dismiss it again. This records the rejection against the
    segment's source text, so that candidate is never offered for it again —
    neither served nor fed to the engine as reference material.

    Returns the rejection record, or ``None`` if the segment is unknown or has
    no candidate to reject. Marks the segment ``rejected`` when the store
    supports it (``update_segment_status`` is outside the Storage Protocol, so
    it is best-effort).
    """
    store = get_store(store)
    seg = store.get_segment(segment_id)
    if not seg or not seg.get("candidate"):
        return None
    doc = store.get_document(seg["document_id"]) or {}
    rejection = memory.reject_match(
        source_text=seg["source_text"],
        source_lang=doc.get("source_lang", "en"),
        target_lang=doc.get("target_lang", "es"),
        target_text=seg["candidate"], verifier=verifier,
        reason=reason or f"segment:{segment_id[:8]}", store=store,
    )
    updater = getattr(store, "update_segment_status", None)
    if callable(updater):
        updater(segment_id, "rejected")
    _ledger_append({"kind": "reject_segment", "segment_id": segment_id,
                    "rejection_id": rejection["id"], "verifier": verifier,
                    "reason": reason})
    return rejection


def graduate_segment(segment_id: str, verifier: str = "", weight: float = 1.0,
                     store: Optional[Storage] = None) -> Optional[dict]:
    """Tier 3 → tier 1: a verified segment's pair enters the sealed memory.
    Called from the host's review path when a segment reaches 'verified'."""
    store = get_store(store)
    seg = store.get_segment(segment_id)
    if not seg or not seg.get("candidate"):
        return None
    doc = store.get_document(seg["document_id"]) or {}
    pair = memory.add_pair(
        source_text=seg["source_text"], target_text=seg["candidate"],
        source_lang=doc.get("source_lang", "en"), target_lang=doc.get("target_lang", "es"),
        status="sealed", verifier=verifier, weight=weight, origin=f"doc:{seg['document_id'][:8]}",
        store=store,
    )
    # Mark the segment decided, exactly as `reject_segment` does. Without this a
    # sealed segment stayed 'pending' forever: the pair was in the memory and
    # serving, while the queue still offered it for review — the accept side of
    # the same "the same item comes back identically" tax rejection exists to
    # end. Best-effort for a store predating the queue capability
    # (`storage.supports_queue`), which is why it is a getattr rather than a
    # Protocol call.
    updater = getattr(store, "update_segment_status", None)
    if callable(updater):
        updater(segment_id, "verified")
    # `add_pair` writes the "seal" entry for the pair itself; this one records
    # the other half — which queued segment a human decided, and in which
    # document — so the two join in the trail without saying "seal" twice.
    _ledger_append({"kind": "segment_sealed", "segment_id": segment_id,
                    "document_id": seg["document_id"], "pair_id": pair["id"],
                    "verifier": verifier})
    return pair
