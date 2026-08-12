"""Decision memory — a domain recipe over Nestor's verified-match memory, with a
graph (docs/decision-memory.md N6/N8).

The other recipes (translation, entity, numeric) answer *what is the verified
value*. This one adds the question git's merged-PR history answers and a bare
key-value store cannot: **what does what we already committed to constrain about
what I am proposing.** A decision is a sealed pair (question -> commitment); an
*edge* relates one decision to another (``supersedes | refines | depends_on |
contradicts``); ``constraints_on`` is the traversal.

The covenant holds at both levels. The machine may :meth:`propose` a decision and
:meth:`propose_edge` a relation — both land unsigned, exactly where a draft pair
lands. Only a human, signing with their own key, may :meth:`seal` a decision or
:meth:`seal_edge` a relation, and **only a sealed edge is ever traversed as a
constraint** — a proposed one is surfaced to a curator, never treated as fact.

Same mechanic as ``entity.py``: ``domain`` (default ``"decision"``) rides in the
pair language tags, so one store holds disjoint decision graphs
(``decision:architecture``, ``decision:governance``) without cross-talk.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from . import memory, signing
from .cascade import _ledger_append
from .matcher import Matcher, StringMatcher
from .storage import (Storage, supports_edges, supports_lineage,
                      supports_rejection)

#: The relations an edge may assert (docs/decision-memory.md N6). A kind outside
#: this set is a typo that would silently grow an ungraphable graph, so it is
#: refused at proposal time rather than stored.
EDGE_KINDS = frozenset({"supersedes", "refines", "depends_on", "contradicts"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DecisionMemory:
    """Sealed decisions and the signed edges between them, over one store."""

    def __init__(self, store: Storage, domain: str = "decision",
                 matcher: Optional[Matcher] = None,
                 seal_threshold: Optional[float] = None,
                 context_threshold: Optional[float] = None) -> None:
        self.store = store
        self.domain = domain
        self.matcher = matcher or StringMatcher()
        self.seal_threshold = seal_threshold
        self.context_threshold = context_threshold
        store.memory_init()

    # -- decisions --------------------------------------------------------

    def propose(self, question: str, commitment: str, rationale: str = "",
                origin: str = "") -> dict:
        """A machine's proposed decision — a **draft**, never served as verified.

        The rationale is kept in ``reason`` because a future proposal needs the
        argument behind what was chosen, not only the choice. This is the one
        write a model may make; it confirms nothing.
        """
        return memory.add_pair(
            source_text=question, target_text=commitment,
            source_lang=self.domain, target_lang=self.domain,
            status="draft", reason=rationale, origin=origin,
            store=self.store, matcher=self.matcher)

    def seal(self, question: str, commitment: str, verifier: str,
             seal_sig: str, reason: str = "", origin: str = "") -> dict:
        """A human's ratified decision. ``seal_sig`` is produced by the verifier's
        own key over the standard seal message ``[normalize(question), commitment,
        verifier]`` — this instance only verifies it (``add_pair`` refuses an
        invalid one), so a public-key-only keyring can seal, and the machine
        running this code can never forge the ratification.
        """
        return memory.add_pair(
            source_text=question, target_text=commitment,
            source_lang=self.domain, target_lang=self.domain,
            status="sealed", verifier=verifier, seal_sig=seal_sig,
            reason=reason, origin=origin,
            store=self.store, matcher=self.matcher)

    # -- edges ------------------------------------------------------------

    def _require_edges(self) -> None:
        if not supports_edges(self.store):
            raise RuntimeError(
                f"{type(self.store).__name__} does not implement Nestor's "
                f"decision-graph capability (memory_add_edge, memory_edges_to, "
                f"memory_edges_from, memory_seal_edge — see nestor.storage).")

    def propose_edge(self, src_id: str, dst_id: str, kind: str,
                     reason: str = "") -> dict:
        """Propose that decision ``src_id`` ``kind`` decision ``dst_id``.

        A **draft** edge (``edge_sig=''``): the machine may assert the relation,
        but it does not constrain anything until a human seals it. Returns the
        edge row (its ``id`` is what :meth:`seal_edge` ratifies).
        """
        self._require_edges()
        if kind not in EDGE_KINDS:
            raise ValueError(
                f"unknown edge kind {kind!r} — one of {sorted(EDGE_KINDS)}")
        if src_id == dst_id:
            raise ValueError("a decision cannot relate to itself")
        for pid in (src_id, dst_id):
            if getattr(self.store, "memory_get", lambda _p: True)(pid) is None:
                raise ValueError(f"no decision {pid!r} in this store")
        edge = {"id": str(uuid.uuid4()), "src_id": src_id, "dst_id": dst_id,
                "kind": kind, "reason": reason, "verifier": "",
                "created_at": _now(), "edge_sig": ""}
        self.store.memory_add_edge(edge)
        return edge

    def seal_edge(self, src_id: str, dst_id: str, kind: str, verifier: str,
                  edge_sig: str, reason: str = "") -> dict:
        """Ratify the relation ``src_id`` ``kind`` ``dst_id`` under ``verifier``'s
        key. ``edge_sig`` is signed over ``["edge", src_id, dst_id, kind]`` by the
        verifier's own key; this instance verifies it and never signs, so — as
        with a seal — a public-only keyring can ratify and the machine cannot
        forge. Refuses an invalid signature. Seals a matching proposed edge in
        place if one exists, else records a fresh sealed edge. Ledgers
        ``edge_seal``.
        """
        self._require_edges()
        if kind not in EDGE_KINDS:
            raise ValueError(
                f"unknown edge kind {kind!r} — one of {sorted(EDGE_KINDS)}")
        if not signing.edge_is_valid(src_id, dst_id, kind, verifier, edge_sig):
            raise ValueError(
                f"edge signature does not verify for {verifier!r} over "
                f"{kind} {src_id}->{dst_id}; refusing to ratify a relation "
                f"nothing backs (the seal covenant, for edges).")
        proposed = [e for e in self.store.memory_edges_to(dst_id, kind)
                    if e["src_id"] == src_id and not e["edge_sig"]]
        if proposed:
            edge_id = proposed[0]["id"]
            self.store.memory_seal_edge(edge_id, verifier, edge_sig)
        else:
            edge_id = str(uuid.uuid4())
            self.store.memory_add_edge(
                {"id": edge_id, "src_id": src_id, "dst_id": dst_id,
                 "kind": kind, "reason": reason, "verifier": verifier,
                 "created_at": _now(), "edge_sig": edge_sig})
        _ledger_append({
            "kind": "edge_seal", "domain": self.domain, "edge_id": edge_id,
            "edge_kind": kind, "src_id": src_id, "dst_id": dst_id,
            "verifier": verifier})
        return {"id": edge_id, "src_id": src_id, "dst_id": dst_id,
                "kind": kind, "verifier": verifier, "sealed": True}

    # -- the traversal ----------------------------------------------------

    def constraints_on(self, question: str) -> dict:
        """What the committed record constrains about ``question``.

        Not "what is the answer" but the shape a proposal has to fit:

        * ``live`` — the live decision for this question, with its reason and
          whether a human has sealed it;
        * ``lineage`` — superseded predecessors, each with the reason it was
          replaced (the merged-PR history a key-value store loses);
        * ``constraints`` — **sealed** edges touching this decision, the only
          ones traversed as fact;
        * ``proposed`` — edges a machine proposed but no human has sealed,
          surfaced so a curator sees them and never as a constraint;
        * ``rejected`` — rejected alternatives, each with its reason and any
          ``reopen_when`` condition (a not-yet, not a closed door).
        """
        norm = self.matcher.normalize(question)
        row = self.store.memory_find(norm, self.domain, self.domain)
        result: dict = {"question": question, "live": None, "lineage": [],
                        "constraints": [], "proposed": [], "rejected": []}
        if row is not None:
            result["live"] = {
                "pair_id": row["id"], "commitment": row["target_text"],
                "reason": row.get("reason", ""),
                "verifier": row.get("verifier", ""),
                "sealed": row.get("status") == "sealed"}
            if supports_lineage(self.store):
                result["lineage"] = [
                    {"commitment": p["target_text"], "reason": p.get("reason", ""),
                     "verifier": p.get("verifier", "")}
                    for p in self.store.memory_lineage(row["id"])]
            if supports_edges(self.store):
                self._collect_edges(row["id"], result)

        if supports_rejection(self.store):
            for r in self.store.memory_rejections(norm, self.domain, self.domain):
                result["rejected"].append({
                    "option": r.get("target_text", ""),
                    "reason": r.get("reason", ""),
                    "reopen_when": r.get("reopen_when", "")})
        return result

    def _collect_edges(self, pair_id: str, result: dict) -> None:
        seen: set = set()
        for direction, edges in (
                ("out", self.store.memory_edges_from(pair_id)),
                ("in", self.store.memory_edges_to(pair_id))):
            for e in edges:
                if e["id"] in seen:
                    continue
                seen.add(e["id"])
                other = e["dst_id"] if direction == "out" else e["src_id"]
                got = getattr(self.store, "memory_get", lambda _p: None)(other)
                entry = {"kind": e["kind"], "direction": direction,
                         "other_id": other,
                         "other_commitment": got["target_text"] if got else None,
                         "edge_reason": e.get("reason", ""),
                         "verifier": e.get("verifier", "")}
                sealed = signing.edge_is_valid(
                    e["src_id"], e["dst_id"], e["kind"],
                    e.get("verifier", ""), e.get("edge_sig", ""))
                (result["constraints"] if sealed else result["proposed"]).append(entry)
