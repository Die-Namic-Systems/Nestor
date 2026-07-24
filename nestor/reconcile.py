"""Numeric reconciliation — a domain recipe over Nestor's verified-match memory.

Same mechanic again, now with a :class:`~nestor.matcher.NumericMatcher`. A
:class:`Reconciler` seals a verified numeric *baseline* for a label (a contract
ceiling, a reported figure, a prior period's number) and then checks fresh
*observations* against it: within tolerance passes; outside tolerance is flagged
with the exact variation. Every check is written to the hash-chained ledger —
so this is "match the numbers" with an audit trail, the numeric sibling of the
translation memory and the entity graph.

Each label gets its own bucket via the pair's language tags (``source_lang`` =
label, ``target_lang`` = domain), so one store can track many labelled figures
independently.
"""
from __future__ import annotations

from typing import Optional

from . import memory
from .cascade import _ledger_append
from .matcher import NumericMatcher
from .storage import Storage


class Reconciler:
    """Numeric baseline-vs-observation checking over a NumericMatcher memory."""

    def __init__(self, store: Storage, domain: str = "value",
                 abs_tol: float = 0.0, pct_tol: float = 0.05) -> None:
        self.store = store
        self.domain = domain
        self.matcher = NumericMatcher(abs_tol=abs_tol, pct_tol=pct_tol)
        store.memory_init()

    # -- sealing ----------------------------------------------------------

    def seal_baseline(self, label: str, value, verifier: str = "",
                      origin: str = "") -> dict:
        """Seal a canonical numeric baseline for ``label``.

        The value's canonical numeric key is the pair's source (so an
        observation can be matched against it numerically); the raw value string
        is the target. Returns the sealed baseline and logs it.
        """
        num = self.matcher.parse(value)
        pair = memory.add_pair(
            source_text=str(value), target_text=str(value),
            source_lang=label, target_lang=self.domain,
            status="sealed", verifier=verifier, origin=origin,
            store=self.store, matcher=self.matcher,
        )
        _ledger_append({
            "kind": "baseline_seal", "domain": self.domain, "label": label,
            "baseline": num, "verifier": verifier, "pair_id": pair["id"],
        })
        return {"label": label, "baseline": num, "sealed": True,
                "pair_id": pair["id"], "verifier": verifier}

    # -- checking ---------------------------------------------------------

    def check(self, label: str, observed) -> dict:
        """Compare an observed value against the sealed baseline for ``label``.

        Returns::

            {"label": str,
             "baseline": float | None,
             "observed": float,
             "within_tolerance": bool,
             "variation": float,        # absolute |observed - baseline|
             "variation_pct": float,    # variation / |baseline| (a fraction)
             "flagged": bool}

        ``within_tolerance`` is true iff the NumericMatcher scores the pair a
        perfect ``1.0`` (i.e. ``|observed - baseline| <= max(abs_tol,
        pct_tol*max(|.|))``). Anything else with a known baseline is ``flagged``.
        Every check is appended to the ledger.
        """
        obs_num = self.matcher.parse(observed)
        # context_threshold=0.0 so even a wildly off observation still returns
        # the baseline candidate (we need it to report the variation).
        matches = memory.lookup(
            observed, label, self.domain, store=self.store,
            matcher=self.matcher, context_threshold=0.0,
        )
        sealed = [m for m in matches if m["pair"]["status"] == "sealed"]

        if not sealed:
            result = {
                "label": label, "baseline": None, "observed": obs_num,
                "within_tolerance": False, "variation": None,
                "variation_pct": None, "flagged": False,
            }
        else:
            top = sealed[0]
            baseline = float(top["pair"]["source_norm"])
            within = top["similarity"] == 1.0
            variation = abs(obs_num - baseline) if obs_num is not None else None
            variation_pct = (variation / abs(baseline)
                             if variation is not None and baseline != 0 else None)
            result = {
                "label": label, "baseline": baseline, "observed": obs_num,
                "within_tolerance": within, "variation": variation,
                "variation_pct": variation_pct, "flagged": not within,
            }

        _ledger_append({
            "kind": "reconcile", "domain": self.domain, "label": label,
            "baseline": result["baseline"], "observed": result["observed"],
            "within_tolerance": result["within_tolerance"],
            "variation": result["variation"], "flagged": result["flagged"],
        })
        return result
