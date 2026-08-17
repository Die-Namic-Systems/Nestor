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

import hashlib
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

#: A reference is a pointer, not the document. Generous caps that fit any real
#: path, url, prior-seal id, or quoted statement while refusing an unbounded
#: blob — the same defensive posture the rest of the package takes on free-text.
_MAX_LOCATOR = 4096
_MAX_REASON = 4096


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
    serving. Refuses — with nothing written — an unknown kind, an empty or
    over-long locator, a pair that does not exist, or a ledger that cannot take
    the entry.
    """
    store = get_store(store)
    _require_evidence(store)
    # A pair reference has to be checked against a real pair, which needs
    # ``memory_get`` — a *different* capability (curation) from the three
    # ``supports_evidence`` verifies. A store can advertise evidence and lack it,
    # so say so honestly rather than letting the check below read every pair as
    # absent and refuse everything with a false "no pair".
    if not callable(getattr(store, "memory_get", None)):
        raise RuntimeError(
            f"{type(store).__name__} implements the evidence capability but not "
            f"memory_get, which attach() needs to confirm a pair exists before "
            f"referencing it (the curation capability — see "
            f"nestor.storage.supports_curation).")
    if kind not in EVIDENCE_KINDS:
        raise ValueError(
            f"unknown evidence kind {kind!r} — one of {sorted(EVIDENCE_KINDS)}")
    if not locator or not locator.strip():
        raise ValueError(
            "evidence needs a locator — the thing it points at (a path, url, "
            "prior seal id, or statement); refusing a reference to nothing")
    if len(locator) > _MAX_LOCATOR or len(reason) > _MAX_REASON:
        # Reject rather than truncate: a silently shortened locator is a wrong
        # pointer, which is worse than no reference. Generous caps — a real path,
        # url, or quoted statement fits; an unbounded blob does not.
        raise ValueError(
            f"locator (max {_MAX_LOCATOR}) or reason (max {_MAX_REASON}) is too "
            f"long; a reference is a pointer, not the document itself")
    pair = store.memory_get(pair_id)
    if pair is None:
        raise ValueError(f"no pair {pair_id!r} in this store")

    ev = {
        "id": str(uuid.uuid4()), "pair_id": pair_id, "kind": kind,
        "locator": locator, "attaches_to": attaches_to or pair.get("status", ""),
        "reason": reason, "attached_by": attached_by, "created_at": _now(),
    }
    # Refuse before the store write if the trail will not take the entry, so an
    # evidence row can never outlive its ledger line — the rule every other
    # write path here holds (memory.add_pair, curator unseal/restore). Lazy
    # import: cascade imports memory at load, and evidence is reachable from it.
    from .cascade import _ledger_append, ledger_preflight
    ledger_preflight()
    cast(EvidenceStorage, store).memory_add_evidence(ev)
    _ledger_append({
        "kind": "attach_evidence", "pair_id": pair_id, "evidence_id": ev["id"],
        "evidence_kind": kind, "attaches_to": ev["attaches_to"],
        "attached_by": attached_by,
        # A hash of the mutable content (like a seal's source_sha/target_sha), so
        # an out-of-band edit to the row's locator or reason is detectable
        # against the append-only chain — not a signature, evidence holds no
        # authority, just tamper-evidence for an audit.
        "content_sha": _content_sha(kind, locator, reason),
    })
    return ev


def _content_sha(kind: str, locator: str, reason: str) -> str:
    """A stable hash of an evidence row's mutable content fields."""
    return hashlib.sha256(
        "\n".join((kind, locator, reason)).encode("utf-8")).hexdigest()


def evidence_for(pair_id: str, store: Optional[Storage] = None) -> list[dict]:
    """Every reference attached to ``pair_id``, newest first."""
    store = get_store(store)
    _require_evidence(store)
    return cast(EvidenceStorage, store).memory_evidence_for(pair_id)


def unevidenced_seals(store: Optional[Storage] = None, *,
                      source_lang: str = "", target_lang: str = "") -> list[dict]:
    """Live sealed pairs with no evidence attached — the curator queue.

    Read-only. Never blocks a seal, never changes a score. The analogue of the
    SQL view in decision 0142: a sealed row is groundless not because it is
    wrong but because nothing recorded what it rests on, and only this can say
    so — the seal itself cannot.

    ``source_lang`` / ``target_lang`` optionally scope the queue to one domain;
    empty (the default) is every domain.
    """
    store = get_store(store)
    _require_evidence(store)
    return cast(EvidenceStorage, store).memory_unevidenced_seals(
        source_lang, target_lang)
