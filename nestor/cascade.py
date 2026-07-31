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
from .segment import _split_segments
from .storage import Storage, get_store

try:                                    # POSIX only; the threading lock stands alone without it
    import fcntl
except ImportError:                     # pragma: no cover — Windows
    fcntl = None                        # type: ignore[assignment]


def _lock_file(handle) -> None:
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_file(handle) -> None:
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# One writer at a time, within this process. See ledger_append.
_append_lock = threading.Lock()

_DEFAULT_LEDGER = "data/ledger.jsonl"
_LEDGER_OVERRIDE: Optional[pathlib.Path] = None
_verified_ledgers: set[str] = set()  # paths already chain-verified this process


def set_ledger_path(path) -> None:
    """Override the hash-chained ledger location (wins over ``NESTOR_LEDGER``)."""
    global _LEDGER_OVERRIDE
    _LEDGER_OVERRIDE = pathlib.Path(path)


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


def ledger_preflight() -> None:
    """Raise :class:`LedgerError` if the next append would be refused. Writes nothing.

    The refusals below have to be available *before* a caller mutates the store,
    or fail-closed becomes fail-late: a seal written to the database and then
    refused by the ledger leaves a verified answer with no trail, which is the
    one state this package exists to prevent. So a decision that must be audited
    calls this first, and only writes if the trail will take it. See
    ``memory.add_pair`` and the ``reject_*`` entry points.
    """
    ledger = _ledger_path()
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
    # Verify the existing chain once per process before extending it: chaining a
    # new entry onto a tampered history would launder the tamper. A broken chain
    # is a refusal, not a warning (Nestor#2 — verify() now has a caller).
    key = str(ledger)
    if key not in _verified_ledgers and ledger.exists():
        ok, detail = _ledger_verify(key)
        if not ok:
            raise LedgerError(f"ledger chain is broken — refusing to append: {detail}")
        _verified_ledgers.add(key)


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

    The FRANK mirror is deliberately forwarded **after** the lock is released:
    it speaks to a subprocess over stdio, and holding the ledger's write lock
    across somebody else's I/O would make a slow governance mirror into a stalled
    review queue.
    """
    ledger_preflight()
    ledger = _ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "prev": "genesis", **entry}
    with _append_lock:
        # "a+" creates the file if absent and keeps the read and the write on one
        # handle, so the tail we hash is the tail we chain onto.
        with open(ledger, "a+", encoding="utf-8") as f:
            _lock_file(f)
            try:
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
        passage = Passage(source=text, target=hit["pair"]["target_text"], tier=1,
                          state="sealed", engine="memory",
                          confidence=hit["similarity"],
                          meta={"pair_id": hit["pair"]["id"],
                                "verifier": hit["pair"]["verifier"]})
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
