"""Evidence — what a claim rests on, kept apart from who checked it.

Seal state answers *has a human checked this?*; evidence answers *what does it
rest on?*. They are orthogonal: a sealed pair can carry no evidence, and a draft
can be perfectly evidenced. Nestor's ``provenance`` only ever meant the first
(who verified, and what suggested it); this module adds the second — a reference
from a pair to the thing behind it — and a read-only report of the sealed pairs
that carry none.

**No signature, on purpose.** Unlike an edge or a seal, attaching a reference is
not a ratification. It is additive and append-only, and it changes neither what
is served nor whether a pair is sealed — so it carries no authority and needs
none. A machine may attach evidence as a proposal exactly as it may write a
draft; ``attached_by`` records who did, but it is a plain label, not a
credential, and nothing downstream trusts it as one. That is the structural
reason the covenant is untouched here: there is no power to forge.

**The report is a queue, not a gate.** :func:`unevidenced_seals` lists sealed
pairs with nothing attached, for a curator to work through — it never blocks a
seal, never changes a score, and never removes a row from serving. This is the
same shape ``triage/report.py`` and ``due_for_reverification`` already take, and
the conclusion ``docs/seal-staleness-and-quorum.md`` reached for aged seals:
work for a human belongs in the queue, not in the score.

v1 has **no exemptions** — every live sealed pair without evidence is listed.
Should one ever be wanted, it must key on a structural fact (authorship, or a
key the store cannot forge), never a list of names (decision 0142, caution B).

See ``docs/evidence-edge.md`` and decision 0142.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, cast

from .storage import EvidenceStorage, Storage, get_store, supports_evidence

#: The reference kinds evidence may carry. A kind outside this set is a typo that
#: would silently grow an unqueryable taxonomy, so it is refused at attach time
#: rather than stored — the same posture as ``EDGE_KINDS``. This is a *starting*
#: set (decision 0142): widen it against real references, not up front.
EVIDENCE_KINDS = frozenset(
    {"document", "url", "prior_seal", "human_statement"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_evidence(store: Storage) -> None:
    if not supports_evidence(store):
        raise RuntimeError(
            f"{type(store).__name__} does not implement Nestor's evidence "
            f"capability (memory_add_evidence, memory_evidence_for, "
            f"memory_unevidenced_seals — see nestor.storage).")


def attach(pair_id: str, kind: str, locator: str, *, reason: str = "",
           attached_by: str = "", attaches_to: str = "",
           store: Optional[Storage] = None) -> dict:
    """Attach one reference to ``pair_id`` and record it in the ledger.

    ``kind`` must be one of :data:`EVIDENCE_KINDS`; ``locator`` is the thing the
    reference points at (a path, a URL, a prior seal id, a quoted statement) and
    may not be empty. The pair must exist. ``attaches_to`` defaults to the pair's
    status at attach time (``sealed`` / ``draft``), recording which state the
    reference was offered against. Returns the stored row.

    Confirms nothing: no signature, no change to the pair's status, no effect on
    serving. Refuses — with nothing written — an unknown kind, an empty locator,
    or a pair that does not exist.
    """
    store = get_store(store)
    _require_evidence(store)
    if kind not in EVIDENCE_KINDS:
        raise ValueError(
            f"unknown evidence kind {kind!r} — one of {sorted(EVIDENCE_KINDS)}")
    if not locator or not locator.strip():
        raise ValueError(
            "evidence needs a locator — the thing it points at (a path, url, "
            "prior seal id, or statement); refusing a reference to nothing")
    pair = store.memory_get(pair_id) if hasattr(store, "memory_get") else None
    if pair is None:
        raise ValueError(f"no pair {pair_id!r} in this store")

    ev = {
        "id": str(uuid.uuid4()), "pair_id": pair_id, "kind": kind,
        "locator": locator, "attaches_to": attaches_to or pair.get("status", ""),
        "reason": reason, "attached_by": attached_by, "created_at": _now(),
    }
    cast(EvidenceStorage, store).memory_add_evidence(ev)
    # Append-only in the ledger, like every other decision. Lazy import: cascade
    # imports memory at load, and evidence is reachable from there.
    from .cascade import _ledger_append
    _ledger_append({
        "kind": "attach_evidence", "pair_id": pair_id, "evidence_id": ev["id"],
        "evidence_kind": kind, "attaches_to": ev["attaches_to"],
        "attached_by": attached_by,
    })
    return ev


def evidence_for(pair_id: str, store: Optional[Storage] = None) -> list[dict]:
    """Every reference attached to ``pair_id``, newest first."""
    store = get_store(store)
    _require_evidence(store)
    return cast(EvidenceStorage, store).memory_evidence_for(pair_id)


def unevidenced_seals(store: Optional[Storage] = None) -> list[dict]:
    """Live sealed pairs with no evidence attached — the curator queue.

    Read-only. Never blocks a seal, never changes a score. The analogue of the
    SQL view in decision 0142: a sealed row is groundless not because it is
    wrong but because nothing recorded what it rests on, and only this can say
    so — the seal itself cannot.
    """
    store = get_store(store)
    _require_evidence(store)
    return cast(EvidenceStorage, store).memory_unevidenced_seals()
