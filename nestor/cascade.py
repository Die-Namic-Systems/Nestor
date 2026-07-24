"""The cascade — memory, draft, seal. One loop per segment.

Segments that reach tier 2 are queued into the injected store's
documents/segments review pipeline; verification (tier 3) graduates them into
the TM via ``graduate_segment``. Every passage is appended to a local
hash-chained ledger (default ``data/ledger.jsonl``) — Nestor's audit trail,
and the prototype stand-in for FRANK.

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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from . import langid, memory
from .engine import get_engine
from .segment import _split_segments
from .storage import Storage, get_store

_DEFAULT_LEDGER = "data/ledger.jsonl"
_LEDGER_OVERRIDE: Optional[pathlib.Path] = None


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


def _ledger_append(entry: dict) -> None:
    ledger = _ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    prev = "genesis"
    if ledger.exists():
        with open(ledger, "rb") as f:
            last = None
            for last in f:
                pass
        if last:
            prev = hashlib.sha256(last.strip()).hexdigest()
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "prev": prev, **entry}
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


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
    _ledger_append({"kind": "seal", "segment_id": segment_id,
                    "pair_id": pair["id"], "verifier": verifier})
    return pair
