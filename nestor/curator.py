"""The curator's surface — see, audit, revoke and export the sealed memory.

Nestor has three humans, and until now the schema knew about one. The
**reviewer** works the tier-2 queue and accepts or rejects drafts. The
**auditor** asks months later why an answer was served. The **curator** decides
what is in the memory at all: which seals still stand, which are junk, which
were signed by a key nobody recognises.

The curator had no tools. Sealing was write-only — a pair could be verified but
never browsed, inspected, revoked or exported — so for a system whose entire
value proposition is human verification, the human could not see what they had
verified. This module is that surface.

Three things it deliberately does:

* **Reports signature validity on every row.** A curator's sharpest job is
  spotting a row marked ``sealed`` whose signature does not verify, which means
  it was written by something that did not hold the seal key. That is invisible
  in `memory_stats` and is the first thing a `list()` shows.
* **Separates *unseal* from *reject*.** Unsealing returns a pair to the review
  queue for re-verification; rejecting retires it as wrong. A curator who is
  merely unsure must not have to choose between destroying a mapping and leaving
  a seal standing that they no longer trust.
* **Writes revocation to the ledger.** Un-verifying is a verification decision.
  If only seals were audited, the trail would record every grant of trust and no
  withdrawal of it.
* **Reads the rejections back.** Serving consumes one rejection at a time — "not
  this answer for this query." :meth:`Curator.rejection_signals` reads the pile:
  a query refused repeatedly says the threshold is wrong for this domain, a pair
  refused for many unrelated queries says the pair is junk. Both were recorded
  from the day rejection shipped and read by nothing.

Usage::

    from nestor.curator import Curator

    c = Curator(store, source_lang="en", target_lang="es")
    c.list(status="sealed", contains="invoice")     # browse
    c.get(pair_id)                                  # provenance + rejections
    c.unseal(pair_id, verifier="rita", reason="terminology changed")
    c.export()                                      # everything, JSON-ready
"""
from __future__ import annotations

import builtins
from typing import Optional

from . import keyring, ledger, memory, signing
from .errors import NestorError
from .storage import Storage, get_store, require_capability, supports_rejection


class CurationUnsupportedError(NestorError):
    """The injected store does not implement the curation capability."""


class Curator:
    """Browse, inspect, revoke and export the sealed memory.

    ``source_lang`` / ``target_lang`` are Nestor's generic domain tags; leave
    them empty to curate across every domain in the store at once.
    """

    def __init__(self, store: Optional[Storage] = None, source_lang: str = "",
                 target_lang: str = "") -> None:
        self.store = get_store(store)
        require_capability(
            self.store, "curation",
            f"{type(self.store).__name__} does not implement Nestor's curation "
            f"capability. Implement memory_list, memory_get, memory_unseal and "
            f"memory_rejections_for_pair (see nestor.storage.Storage).",
            exc_type=CurationUnsupportedError,
        )
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.store.memory_init()

    # -- reading ----------------------------------------------------------

    def _annotate(self, pair: dict) -> dict:
        """Attach what a human needs and the raw row does not carry."""
        out = dict(pair)
        out["signature_valid"] = signing.seal_is_valid(
            pair.get("source_norm", ""), pair.get("target_text", ""),
            pair.get("verifier", ""), pair.get("seal_sig", ""))
        # The distinction that matters: a sealed row whose signature does not
        # verify was written by something without the seal key. is_verified_seal
        # is the same predicate the serve path uses, so this column answers
        # "would Nestor actually serve this?" rather than "does it say sealed?".
        out["servable"] = memory.is_verified_seal(pair)
        ring = keyring.get_keyring()
        if ring is not None:
            # With per-verifier keys there are more than two answers. "Valid"
            # covers a seal signed by rita's key and a seal signed by the old
            # deployment-wide key alike, and those are different facts about who
            # verified something — which is the whole reason the keyring exists.
            out["signed_by"] = signing.seal_attribution(
                pair.get("source_norm", ""), pair.get("target_text", ""),
                pair.get("verifier", ""), pair.get("seal_sig", ""))
            out["key_status"] = ring.status(pair.get("verifier", ""))
            # "Signed by rita's HMAC" and "signed by rita's key" are different
            # claims (Nestor#17); during a migration a curator needs to see
            # which one each seal makes.
            out["key_type"] = signing.verifier_key_type(pair.get("verifier", ""))
        return out

    def list(self, status: str = "", verifier: str = "", contains: str = "",
             limit: int = 50, offset: int = 0) -> list[dict]:
        """Browse pairs, newest first, each annotated with signature validity."""
        rows = self.store.memory_list(
            source_lang=self.source_lang, target_lang=self.target_lang,
            status=status, verifier=verifier, contains=contains,
            limit=limit, offset=offset)
        return [self._annotate(r) for r in rows]

    def get(self, pair_id: str) -> Optional[dict]:
        """One pair with full provenance: signature validity, rejections, what
        it rests on, and what entitles a stranger to believe it.

        ``rejections`` lists every query this pair was refused for. A pair
        rejected against many different queries is probably junk — that is a
        curator's cue to unseal or reject it outright, and it is not visible
        anywhere else.

        ``evidence`` and ``warrants`` answer the two different questions the
        auditor actually arrives with. Evidence is what the claim points at and
        carries no authority (:mod:`nestor.evidence`); a warrant names an
        authority and says how to check it (:mod:`nestor.warrant`). Both were
        reachable only through their own commands until now, which meant the one
        call named "provenance" — the call an auditor makes months later, and
        the one ``nestor_provenance`` serves to a model over MCP — answered
        "who sealed this and who argued with it" and nothing about what it rests
        on. Each is omitted, rather than empty, on a store lacking that optional
        capability: an empty list would read as "nothing attached" where the
        truth is "this store cannot say".

        ``warrants`` includes the ``attestation`` composed from the pair's own
        seal, marked ``stored: False``. Nothing here reports a warrant as
        satisfied, and no field could: a warrant row is the claim that a warrant
        exists plus what a reader needs to check it themselves.
        """
        pair = self.store.memory_get(pair_id)
        if not pair:
            return None
        out = self._annotate(pair)
        out["rejections"] = [
            {"query_norm": r.get("query_norm", ""), "verifier": r.get("verifier", ""),
             "reason": r.get("reason", ""), "created_at": r.get("created_at", ""),
             "signature_valid": signing.rejection_is_valid(
                 r.get("query_norm", ""), r.get("pair_id", ""),
                 r.get("target_text", ""), r.get("verifier", ""),
                 r.get("reject_sig", ""))}
            for r in self.store.memory_rejections_for_pair(pair_id)
        ]
        out["rejection_count"] = len(out["rejections"])
        # Local imports: both relations are optional capabilities, and neither
        # may become a hard dependency of the curator surface.
        from .storage import supports_evidence, supports_warrants
        if supports_evidence(self.store):
            from . import evidence as evidence_mod
            out["evidence"] = evidence_mod.evidence_for(pair_id, store=self.store)
            out["evidence_count"] = len(out["evidence"])
        if supports_warrants(self.store):
            from . import warrant as warrant_mod
            out["warrants"] = warrant_mod.warrants_for(pair_id, store=self.store)
            # A sorted set, said out loud, because the list's order is
            # presentation and a reader must not take the first row for the
            # strongest one. There is no strongest one.
            out["warrant_kinds"] = sorted({w["kind"] for w in out["warrants"]})
        return out

    def unverifiable(self, limit: int = 200) -> builtins.list[dict]:
        # `builtins.list`, not the bare `list[dict]` every other signature in
        # this file uses: this class defines its OWN method named `list`
        # above, which shadows the builtin type inside this class body from
        # this point on — mypy resolves an unqualified `list` here to
        # `Curator.list` (the method) and rejects it as "not valid as a
        # type". Only annotations written after that method's def are
        # affected; qualifying via `builtins` sidesteps the clash without
        # renaming the public `Curator.list` API.
        """Rows claiming ``sealed`` that Nestor would refuse to serve.

        With signing enabled these are rows written by something that did not
        hold the seal key — the Nestor#2 forgery, surfaced for a human. With
        signing disabled every seal verifies and this is always empty, which is
        itself worth knowing.
        """
        return [p for p in self.list(status="sealed", limit=limit)
                if not p["servable"]]

    def replaced_seals(self, conflicts_only: bool = True,
                       limit: int = 200) -> builtins.list[dict]:
        """Seals that were overwritten — someone re-sealed an already-sealed source.

        The memory keeps one row per normalized source, so a replacement leaves
        no trace in the store at all: the previous target and verifier exist only
        in the ledger. This reads them back.

        ``conflicts_only`` (the default) keeps replacements where a *different*
        verifier overwrote the earlier decision. Since ``add_pair`` now raises
        :class:`~nestor.memory.ConflictingSealError` on exactly that case, an
        entry here means somebody passed ``override_conflict=True`` — a
        deliberate decision to overrule another verifier. That is the highest-
        signal event this surface reports, and the store retains no trace of it.

        Pass ``False`` to include self-corrections, where the same verifier
        revised their own seal. Those are routine and were never refused.

        Targets appear as short digests rather than text: ledger entries are
        mirrored verbatim into shared provenance by :mod:`nestor.frank`, and the
        digest still identifies which text was replaced to anyone holding it.
        """
        rows = ledger.entries(kind="seal_replaced", limit=limit)
        if conflicts_only:
            rows = [r for r in rows if not r.get("same_verifier", False)]
        return rows

    def rejection_signals(self, min_query: int = 2, min_pair: int = 2,
                          limit: int = 2000) -> dict:
        """What the accumulated "no"s say, which nothing used to ask.

        Rejection has been recorded since it shipped and read by exactly one
        thing: :func:`~nestor.memory.lookup`, which suppresses the specific
        answer for the specific query. In aggregate the same records say two
        further things, and both were going unread (IDEAS §1.2):

        * **A query rejected repeatedly** — several different answers offered
          for one input, all refused — is evidence the *threshold* is wrong for
          this domain rather than evidence about any one pair. Nestor's
          ``SEAL_THRESHOLD`` is a single global constant and no single value
          works across corpora (§1.3); this is the only per-domain signal the
          system actually collects.
        * **A pair rejected against many different queries** is evidence about
          the pair. A good mapping is the wrong answer for a query now and
          then; one that is wrong for a dozen unrelated inputs is junk, and the
          curator's next move is :meth:`unseal` or ``reject_pair``.

        Returns ``{"queries": [...], "pairs": [...], "rejections": int,
        "domain": {...}}``, each list ordered by weight of evidence.

        **Read from the ledger, not the store.** ``memory_rejections`` answers
        "what was refused for *this* query", which is what serving needs; there
        is no enumerate-everything call, and adding one would change the
        Storage Protocol every host implements for a reporting feature. The
        chain already holds every rejection, in order, with its verifier and
        reason — the same reason :meth:`replaced_seals` reads it. A store whose
        rejections predate the ledger, or whose chain was rotated, will report
        fewer; the count says how many entries were read so that is visible
        rather than assumed.

        What it deliberately does not do is guess a new threshold. The score a
        rejected match was made at is not recorded — the rejection knows the
        query and the answer, not what they scored — so this reports that the
        dial is wrong here, and :mod:`nestor.calibrate` is what measures where
        to put it.
        """
        entries = ledger.entries(kind="reject_match", limit=limit)
        if self.source_lang:
            entries = [e for e in entries if e.get("source_lang") == self.source_lang]
        if self.target_lang:
            entries = [e for e in entries if e.get("target_lang") == self.target_lang]

        by_query: dict[str, dict] = {}
        by_pair: dict[str, dict] = {}
        for e in entries:
            query = e.get("query_norm", "")
            pair_id = e.get("pair_id", "")
            who = e.get("verifier", "") or "(unknown)"
            reason = e.get("reason", "")
            if query:
                q = by_query.setdefault(query, {
                    "query_norm": query, "rejections": 0, "verifiers": set(),
                    "pair_ids": set(), "reasons": [],
                    "source_lang": e.get("source_lang", ""),
                    "target_lang": e.get("target_lang", ""),
                })
                q["rejections"] += 1
                q["verifiers"].add(who)
                if pair_id:
                    q["pair_ids"].add(pair_id)
                if reason:
                    q["reasons"].append(reason)
            if pair_id:
                p = by_pair.setdefault(pair_id, {
                    "pair_id": pair_id, "queries": set(), "verifiers": set(),
                    "reasons": [],
                })
                if query:
                    p["queries"].add(query)
                p["verifiers"].add(who)
                if reason:
                    p["reasons"].append(reason)

        queries = []
        for q in by_query.values():
            if q["rejections"] < min_query:
                continue
            queries.append({
                "query_norm": q["query_norm"], "rejections": q["rejections"],
                "distinct_answers": len(q["pair_ids"]),
                "verifiers": sorted(q["verifiers"]), "reasons": q["reasons"][:5],
                "source_lang": q["source_lang"], "target_lang": q["target_lang"],
            })
        queries.sort(key=lambda r: (-r["rejections"], r["query_norm"]))

        pairs = []
        for p in by_pair.values():
            if len(p["queries"]) < min_pair:
                continue
            row = self.store.memory_get(p["pair_id"]) or {}
            pairs.append({
                "pair_id": p["pair_id"], "queries": len(p["queries"]),
                "query_norms": sorted(p["queries"])[:10],
                "verifiers": sorted(p["verifiers"]), "reasons": p["reasons"][:5],
                # The pair may since have been unsealed or rejected outright —
                # a curator wants to see the ones still standing first.
                "status": row.get("status", "(gone)"),
                "source_text": row.get("source_text", ""),
                "target_text": row.get("target_text", ""),
                "servable": memory.is_verified_seal(row) if row else False,
            })
        pairs.sort(key=lambda r: (-r["queries"], r["pair_id"]))

        return {
            "queries": queries, "pairs": pairs, "rejections": len(entries),
            "domain": {"source_lang": self.source_lang or "*",
                       "target_lang": self.target_lang or "*"},
            "thresholds": {"min_query": min_query, "min_pair": min_pair},
        }

    # -- revoking ---------------------------------------------------------

    def unseal(self, pair_id: str, verifier: str = "", reason: str = "") -> Optional[dict]:
        """Demote a sealed pair back to ``draft`` for re-verification.

        The pair stops being served as tier 1 and re-enters the review queue; it
        can be sealed again later. Use ``memory.reject_pair`` instead when the
        mapping is wrong rather than merely stale.

        Logged to the ledger: withdrawing trust is a verification decision, and
        a trail that records only grants is not an audit trail.

        Returns the updated pair, or ``None`` if the id is unknown.
        """
        pair = self.store.memory_get(pair_id)
        if not pair:
            return None
        memory._ledger_preflight()   # refuse before the write, not after it
        self.store.memory_unseal(pair_id, verifier, reason)
        memory._log_rejection({
            "kind": "unseal", "pair_id": pair_id, "verifier": verifier,
            "reason": reason, "was_status": pair.get("status", ""),
            "source_lang": pair.get("source_lang", ""),
            "target_lang": pair.get("target_lang", ""),
        })
        return self._annotate(self.store.memory_get(pair_id) or {})

    def restore(self, pair_id: str, verifier: str = "",
                reason: str = "") -> Optional[dict]:
        """Undo a rejection: return a ``rejected`` pair to ``draft``.

        Rejection is deliberate, so undoing it is deliberate too — ``add_pair``
        refuses to re-seal a rejected pair implicitly (``RejectedPairError``).
        This is the explicit path back, and it goes to ``draft`` rather than
        straight to ``sealed``: a mapping a human once called wrong should be
        re-verified, not silently reinstated.

        Returns the updated pair, or ``None`` if the id is unknown.
        """
        pair = self.store.memory_get(pair_id)
        if not pair:
            return None
        memory._ledger_preflight()
        self.store.memory_unseal(pair_id, verifier, f"restored: {reason}")
        memory._log_rejection({
            "kind": "restore", "pair_id": pair_id, "verifier": verifier,
            "reason": reason, "was_status": pair.get("status", ""),
        })
        return self._annotate(self.store.memory_get(pair_id) or {})

    # -- exporting --------------------------------------------------------

    def export(self, limit: int = 100_000) -> dict:
        """The whole curated memory as a JSON-ready dict.

        Includes each pair's signature validity and its rejections, so an export
        carries the same picture the curator sees rather than a bare table dump.
        Signatures are exported as-is: they are HMACs, not secrets, and without
        the key they cannot be recomputed — which is the point.
        """
        pairs = self.list(limit=limit)
        detailed = []
        for p in pairs:
            full = self.get(p["id"])
            if full:
                detailed.append(full)
        return {
            "domain": {"source_lang": self.source_lang or "*",
                       "target_lang": self.target_lang or "*"},
            "signing_enabled": signing.signing_enabled(),
            "rejection_capable": supports_rejection(self.store),
            "counts": self.summary(),
            "pairs": detailed,
        }

    def summary(self) -> dict:
        """Counts a curator acts on, including the ones `memory_stats` omits."""
        sealed = self.list(status="sealed", limit=100_000)
        draft = self.list(status="draft", limit=100_000)
        rejected = self.list(status="rejected", limit=100_000)
        out = {
            "sealed": len(sealed),
            "draft": len(draft),
            "rejected": len(rejected),
            "sealed_unverifiable": sum(1 for p in sealed if not p["servable"]),
            "verifiers": sorted({p.get("verifier", "") for p in sealed if p.get("verifier")}),
        }
        ring = keyring.get_keyring()
        if ring is not None:
            # Two counts a keyring makes meaningful and a shared key cannot:
            # seals nobody in particular signed, and seals by a name the
            # keyring does not know.
            out["sealed_legacy"] = sum(1 for p in sealed if p.get("signed_by") == "legacy")
            out["unknown_verifiers"] = sorted(
                {p.get("verifier", "") for p in sealed
                 if ring.status(p.get("verifier", "")) == "unknown"})
        return out
