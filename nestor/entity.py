"""Entity resolution — a domain recipe over Nestor's verified-match memory.

Same mechanic as the translation memory, different matcher. An
:class:`EntityResolver` seals ``surface -> canonical`` mappings (an alias and
the entity it denotes) into Nestor's memory using a
:class:`~nestor.matcher.StringMatcher`, then resolves a raw surface form to its
canonical entity by fuzzy-matching against the sealed aliases. A match at or
above the seal threshold is served with the sealed mapping's provenance; below
it, the top candidate is returned as an *unsealed suggestion* for a human to
seal.

This realizes gap #15 — the entity-graph engine — on top of the exact same
seal/serve/ledger machinery that powers translation.

The ``domain`` (default ``"entity"``) rides in the pair's language tags, so a
single store can hold several disjoint entity graphs (e.g. ``"company"``,
``"person"``, ``"drug"``) side by side without cross-talk.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from . import memory
from .cascade import _ledger_append
from .matcher import Matcher, StringMatcher
from .storage import Storage


class EntityResolver:
    """Alias -> canonical-entity resolution over a StringMatcher-backed memory."""

    def __init__(self, store: Storage, domain: str = "entity",
                 matcher: Optional[Matcher] = None,
                 seal_threshold: Optional[float] = None,
                 context_threshold: Optional[float] = None) -> None:
        self.store = store
        self.domain = domain
        self.matcher = matcher or StringMatcher()
        # None -> use memory's module defaults (SEAL_THRESHOLD / CONTEXT_THRESHOLD).
        self.seal_threshold = seal_threshold
        self.context_threshold = context_threshold
        store.memory_init()

    # -- sealing ----------------------------------------------------------

    def seal(self, surface: str, canonical: str, verifier: str = "",
             weight: float = 1.0, origin: str = "") -> dict:
        """Seal a verified ``surface -> canonical`` alias mapping.

        The alias is the pair's source, the canonical entity its target; the
        domain rides in both language tags. Returns the sealed mapping and logs
        it to the ledger.
        """
        pair = memory.add_pair(
            source_text=surface, target_text=canonical,
            source_lang=self.domain, target_lang=self.domain,
            status="sealed", verifier=verifier, weight=weight, origin=origin,
            store=self.store, matcher=self.matcher,
        )
        _ledger_append({
            "kind": "entity_seal", "domain": self.domain,
            "surface": surface, "canonical": canonical,
            "verifier": verifier, "pair_id": pair["id"],
            "surface_sha": hashlib.sha256(surface.encode()).hexdigest()[:16],
        })
        return {"surface": surface, "canonical": canonical, "sealed": True,
                "pair_id": pair["id"], "verifier": verifier}

    def add_alias(self, surface: str, canonical: str, verifier: str = "",
                  weight: float = 1.0, origin: str = "") -> dict:
        """Convenience alias for :meth:`seal` — reads naturally as a graph op."""
        return self.seal(surface, canonical, verifier=verifier, weight=weight,
                         origin=origin)

    # -- resolving --------------------------------------------------------

    def resolve(self, surface: str) -> dict:
        """Resolve a raw surface form to its canonical entity.

        Returns a dict::

            {"canonical": str | None,
             "confidence": float,
             "sealed": bool,
             "provenance": {...}}

        A sealed match at/above the seal threshold yields the canonical entity
        with ``sealed=True`` and the sealed mapping's provenance. Otherwise the
        top candidate (if any) is offered as an unsealed *suggestion*
        (``canonical=None``, ``sealed=False``, ``provenance["draft"]=True`` with
        a ``suggestion`` the caller may queue for a human seal). An unseen
        surface returns ``canonical=None`` with confidence ``0.0``.
        """
        hit = memory.best_sealed(
            surface, self.domain, self.domain, store=self.store,
            matcher=self.matcher, seal_threshold=self.seal_threshold,
            context_threshold=self.context_threshold,
        )
        if hit:
            pair = hit["pair"]
            result = {
                "canonical": pair["target_text"],
                "confidence": hit["similarity"],
                "sealed": True,
                "provenance": {
                    "pair_id": pair["id"],
                    "sealed_surface": pair["source_text"],
                    "verifier": pair.get("verifier", ""),
                    "origin": pair.get("origin", ""),
                    "weight": pair.get("weight", 1.0),
                    "sealed_at": pair.get("created_at", ""),
                },
            }
        else:
            matches = memory.lookup(
                surface, self.domain, self.domain, store=self.store,
                matcher=self.matcher, context_threshold=self.context_threshold,
            )
            if matches:
                top = matches[0]
                pair = top["pair"]
                result = {
                    "canonical": None,
                    "confidence": top["similarity"],
                    "sealed": False,
                    "provenance": {
                        "draft": True,
                        "suggestion": pair["target_text"],
                        "sealed_surface": pair["source_text"],
                        "pair_status": pair["status"],
                    },
                }
            else:
                result = {"canonical": None, "confidence": 0.0, "sealed": False,
                          "provenance": {"draft": True, "suggestion": None}}

        _ledger_append({
            "kind": "entity_resolve", "domain": self.domain,
            "surface_sha": hashlib.sha256(surface.encode()).hexdigest()[:16],
            "canonical": result["canonical"], "sealed": result["sealed"],
            "confidence": result["confidence"],
        })
        return result
