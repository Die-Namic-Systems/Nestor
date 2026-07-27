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

Usage::

    from nestor.curator import Curator

    c = Curator(store, source_lang="en", target_lang="es")
    c.list(status="sealed", contains="invoice")     # browse
    c.get(pair_id)                                  # provenance + rejections
    c.unseal(pair_id, verifier="rita", reason="terminology changed")
    c.export()                                      # everything, JSON-ready
"""
from __future__ import annotations

from typing import Optional

from . import ledger, memory, signing
from .storage import Storage, get_store, supports_curation, supports_rejection


class CurationUnsupportedError(RuntimeError):
    """The injected store does not implement the curation capability."""


class Curator:
    """Browse, inspect, revoke and export the sealed memory.

    ``source_lang`` / ``target_lang`` are Nestor's generic domain tags; leave
    them empty to curate across every domain in the store at once.
    """

    def __init__(self, store: Optional[Storage] = None, source_lang: str = "",
                 target_lang: str = "") -> None:
        self.store = get_store(store)
        if not supports_curation(self.store):
            raise CurationUnsupportedError(
                f"{type(self.store).__name__} does not implement Nestor's curation "
                f"capability. Implement memory_list, memory_get, memory_unseal and "
                f"memory_rejections_for_pair (see nestor.storage.Storage)."
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
        """One pair with full provenance, signature validity and its rejections.

        ``rejections`` lists every query this pair was refused for. A pair
        rejected against many different queries is probably junk — that is a
        curator's cue to unseal or reject it outright, and it is not visible
        anywhere else.
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
        return out

    def unverifiable(self, limit: int = 200) -> list[dict]:
        """Rows claiming ``sealed`` that Nestor would refuse to serve.

        With signing enabled these are rows written by something that did not
        hold the seal key — the Nestor#2 forgery, surfaced for a human. With
        signing disabled every seal verifies and this is always empty, which is
        itself worth knowing.
        """
        return [p for p in self.list(status="sealed", limit=limit)
                if not p["servable"]]

    def replaced_seals(self, conflicts_only: bool = True,
                       limit: int = 200) -> list[dict]:
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
        return {
            "sealed": len(sealed),
            "draft": len(draft),
            "rejected": len(rejected),
            "sealed_unverifiable": sum(1 for p in sealed if not p["servable"]),
            "verifiers": sorted({p.get("verifier", "") for p in sealed if p.get("verifier")}),
        }
