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
from typing import Iterable, Optional, cast

from . import memory, signing
from .cascade import _ledger_append
from .matcher import Matcher, StringMatcher
from .storage import (EdgeStorage, LineageStorage, Storage, require_capability,
                      supports_edges, supports_lineage, supports_rejection)

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
        require_capability(
            self.store, "edges",
            f"{type(self.store).__name__} does not implement Nestor's "
            f"decision-graph capability (memory_add_edge, memory_edges_to, "
            f"memory_edges_from, memory_seal_edge — see nestor.storage).")

    def _require_pair_lookup(self) -> None:
        """An edge's endpoints must be checkable against real decisions.

        ``supports_edges`` does not include ``memory_get`` (that is the curation
        capability), so a store can advertise the graph and lack it. The
        endpoint-existence guard below then cannot run — and *silently skipping*
        it, as this code first did, lets a **signed** edge be sealed against ids
        that name no decision. Refuse instead: an edge you cannot verify the
        ends of is one you must not ratify. Fail closed, the way
        :func:`nestor.evidence.attach` does for the same missing capability.
        Recorded in decision 0144 (it revises 0141's 'gracefully skipped').
        """
        if not callable(getattr(self.store, "memory_get", None)):
            raise RuntimeError(
                f"{type(self.store).__name__} implements the decision-graph "
                f"capability but not memory_get, needed to confirm an edge's "
                f"endpoints are real decisions (the curation capability — see "
                f"nestor.storage.supports_curation).")

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
        self._require_pair_lookup()
        for pid in (src_id, dst_id):
            if self.store.memory_get(pid) is None:
                raise ValueError(f"no decision {pid!r} in this store")
        edge = {"id": str(uuid.uuid4()), "src_id": src_id, "dst_id": dst_id,
                "kind": kind, "reason": reason, "verifier": "",
                "created_at": _now(), "edge_sig": ""}
        # _require_edges() above raises unless supports_edges(self.store) —
        # the cast just tells the type checker what that check established.
        cast(EdgeStorage, self.store).memory_add_edge(edge)
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
        if src_id == dst_id:
            raise ValueError("a decision cannot relate to itself")
        if not signing.edge_is_valid(src_id, dst_id, kind, verifier, edge_sig):
            raise ValueError(
                f"edge signature does not verify for {verifier!r} over "
                f"{kind} {src_id}->{dst_id}; refusing to ratify a relation "
                f"nothing backs (the seal covenant, for edges).")
        # A signature is valid over the id *bytes* whether or not those ids name
        # real decisions, so — like propose_edge — refuse an edge whose endpoints
        # are not both live decisions in this store. Placed AFTER the signature
        # gate, unlike propose_edge (which is the machine's own draft): this is a
        # caller-supplied request, and reading the store only for a caller who
        # has already proven authority keeps it from being an existence oracle
        # for an unsigned probe.
        self._require_pair_lookup()
        for pid in (src_id, dst_id):
            if self.store.memory_get(pid) is None:
                raise ValueError(f"no decision {pid!r} in this store")
        # Same check-then-cast shape as propose_edge above.
        edge_store = cast(EdgeStorage, self.store)
        proposed = [e for e in edge_store.memory_edges_to(dst_id, kind)
                    if e["src_id"] == src_id and not e["edge_sig"]]
        if proposed:
            edge_id = proposed[0]["id"]
            edge_store.memory_seal_edge(edge_id, verifier, edge_sig)
        else:
            edge_id = str(uuid.uuid4())
            edge_store.memory_add_edge(
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
                    for p in cast(LineageStorage, self.store).memory_lineage(row["id"])]
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
        # Only called from constraints_on after supports_edges(self.store)
        # already returned True; the cast documents that precondition rather
        # than re-checking it.
        edge_store = cast(EdgeStorage, self.store)
        seen: set = set()
        for direction, edges in (
                ("out", edge_store.memory_edges_from(pair_id)),
                ("in", edge_store.memory_edges_to(pair_id))):
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

    # -- the graph view (nestor.ui's read-only Graph tab) ------------------
    #
    # constraints_on is per-question: it answers "what does the record say
    # about THIS one". The graph view answers a different question — "show me
    # the whole thing" — and needs every decision and every edge, not one
    # neighbourhood. Both accessors below are read-only and additive: neither
    # writes, seals, or changes what constraints_on already does.

    def all_decisions(self) -> list[dict]:
        """Every live decision in this domain, sealed and draft alike.

        Deliberately built on :meth:`~nestor.storage.Storage.memory_candidates`
        rather than the curation-only ``memory_list`` — ``memory_candidates``
        is a REQUIRED Storage capability (every serve path already depends on
        it), so a store with no curation support still shows its decisions
        here rather than the graph silently going empty on a capability this
        view never needed. A superseded row (``superseded_by`` set) is
        excluded, same as every serve path — it is not the live decision for
        its question, which is the fact this view exists to make legible.

        Ordered by ``created_at`` then ``id`` so repeat calls return a stable
        order — a caller numbering the rows for display needs that order not
        to change between one fetch and the next.
        """
        rows = self.store.memory_candidates(self.domain, self.domain)
        return sorted(rows, key=lambda r: (r.get("created_at", ""), r["id"]))

    def all_edges(self, node_ids: Iterable[str]) -> list[dict]:
        """Every edge — sealed or merely proposed — touching any of ``node_ids``.

        Walks both :meth:`~nestor.storage.EdgeStorage.memory_edges_from` and
        ``memory_edges_to`` for each id, because an edge is stored once and
        surfaces from either endpoint; deduplicated by the edge's own ``id``
        so a relation between two ids both in ``node_ids`` is not returned
        twice. Returns ``[]``, not a raise, when this store has no decision-
        graph capability at all (:func:`~nestor.storage.supports_edges`) —
        "no edges" and "cannot have edges" render identically to a viewer
        that only ever asked to see what exists.
        """
        if not supports_edges(self.store):
            return []
        edge_store = cast(EdgeStorage, self.store)
        seen: dict[str, dict] = {}
        for nid in node_ids:
            for e in edge_store.memory_edges_from(nid):
                seen[e["id"]] = e
            for e in edge_store.memory_edges_to(nid):
                seen[e["id"]] = e
        return list(seen.values())
