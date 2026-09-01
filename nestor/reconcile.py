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

import warnings

from . import memory
from .cascade import _ledger_append
from .matcher import NumericMatcher
from .storage import Storage, supports_curation


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
                      origin: str = "", override_conflict: bool = False,
                      override_rejection: bool = False,
                      seal_sig: str = "") -> dict:
        """Seal a canonical numeric baseline for ``label``.

        The value's canonical numeric key is the pair's source (so an
        observation can be matched against it numerically); the raw value string
        is the target. Returns the sealed baseline and logs it.

        Re-baselining a label to a *different* figure is a conflicting seal —
        one auditor restating another's verified number — and it needed its own
        guard, because ``add_pair``'s does not fire here. That guard keys on the
        *normalized source*, and under a ``NumericMatcher`` every figure is its
        own key: a second baseline for the same label was not an overwrite at
        all, it was an insert. Both stayed sealed, and :meth:`check` then scored
        an observation against whichever one it happened to sit nearest, so
        ``$1,240,000`` passed cleanly against a superseded ``$1,250,000`` ceiling
        while the standing ``$1,000,000`` one went unconsulted. A recipe whose
        entire job is to flag a deviation cannot let a caller add the baseline
        that excuses it.

        So a differing figure from a different verifier raises
        :class:`~nestor.memory.ConflictingSealError`. A same-verifier restatement
        proceeds — that is an auditor correcting their own number — and so does
        an explicit ``override_conflict``; in both cases the superseded baselines
        are unsealed so exactly one stands, and the replacement is ledgered.
        Retiring needs the optional curation capability; without it the new
        baseline is still sealed, the old ones remain, and both the warning here
        and ``check``'s ``ambiguous`` flag say so rather than leaving the caller
        to discover it from a figure that quietly passed.
        """
        detail = self.matcher.parse_detail(value)
        num = detail["value"]
        if detail["partial"]:
            # A baseline is sealed *and stored as its own text*, so a figure the
            # matcher only half-read is the one case where the discrepancy is
            # permanent: the row says "$1,00o,000" and every future check runs
            # against 100. Reporting it in the result is not enough here — this
            # is a human sealing a number, which is the moment to say so.
            warnings.warn(
                f"the baseline sealed for {label!r} reads {value!r} but the "
                f"figure compared will be {num!r} — {detail['residue']!r} was "
                f"not part of the number. Seal the figure you mean, or accept "
                f"that check() will compare against {num!r}.",
                RuntimeWarning, stacklevel=2)
        self._guard_existing_baselines(label, value, verifier, num,
                                       override_conflict)
        pair = memory.add_pair(
            source_text=str(value), target_text=str(value),
            source_lang=label, target_lang=self.domain,
            status="sealed", verifier=verifier, origin=origin,
            store=self.store, matcher=self.matcher,
            override_conflict=override_conflict,
            override_rejection=override_rejection,
            seal_sig=seal_sig,
        )
        _ledger_append({
            "kind": "baseline_seal", "domain": self.domain, "label": label,
            "baseline": num, "verifier": verifier, "pair_id": pair["id"],
            # A bool, not the text: ledger entries are mirrored verbatim into
            # shared provenance by nestor.frank, and "the figure was read out of
            # a longer string" is the auditable fact — the string itself is the
            # caller's, and it is already in the store.
            "baseline_partial": detail["partial"],
        })
        return {"label": label, "baseline": num, "baseline_text": detail["text"],
                "baseline_partial": detail["partial"], "sealed": True,
                "pair_id": pair["id"], "verifier": verifier}

    # -- one baseline per label -------------------------------------------

    def sealed_baselines(self, label: str) -> list[dict]:
        """Every verified sealed baseline row for ``label``, newest first.

        Normally one. More than one means a replacement could not be retired
        (see :meth:`seal_baseline`), and a caller reading a single ``baseline``
        deserves to be able to see that.
        """
        rows = [r for r in self.store.memory_candidates(label, self.domain)
                if memory.is_verified_seal(r)]
        return sorted(rows, key=lambda r: r.get("created_at", ""), reverse=True)

    def _guard_existing_baselines(self, label: str, value, verifier: str,
                                  num, override_conflict: bool) -> None:
        """Refuse, or retire, the baselines this one supersedes."""
        superseded = [r for r in self.sealed_baselines(label)
                      if r["source_norm"] != self.matcher.normalize(value)]
        if not superseded:
            return
        if not override_conflict and not all(
                memory._same_verifier(r.get("verifier", ""), verifier) for r in superseded):
            others = ", ".join(sorted({r.get("verifier") or "an unknown verifier"
                                       for r in superseded}))
            raise memory.ConflictingSealError(
                f"{label!r} already has a sealed baseline of "
                f"{[r['target_text'] for r in superseded]} from {others}; "
                f"{verifier or 'an unknown verifier'!r} is now asserting {value!r}. "
                f"This will not be sealed implicitly — a second baseline does not "
                f"replace the first, it joins it, and check() would then have two "
                f"figures to pass against. Reseal as the SAME verifier if this is "
                f"your own correction, or pass override_conflict=True."
            )
        can_retire = supports_curation(self.store)
        for row in superseded:
            if can_retire:
                self.store.memory_unseal(
                    row["id"], verifier, f"superseded by baseline {value}")
            _ledger_append({
                "kind": "baseline_replaced", "domain": self.domain, "label": label,
                "pair_id": row["id"], "replaced_baseline": row["target_text"],
                "replaced_verifier": row.get("verifier", ""), "verifier": verifier,
                "baseline": num, "retired": can_retire,
            })
        if not can_retire:
            warnings.warn(
                f"{type(self.store).__name__} cannot unseal (see "
                f"storage.supports_curation), so {len(superseded)} superseded "
                f"baseline(s) for {label!r} stay sealed. check() will report "
                f"ambiguous=True; retire them by hand before trusting a result.",
                RuntimeWarning, stacklevel=3)

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
             "tolerance_abs": float,    # the slack the verdict turned on
             "flagged": bool,
             "ambiguous": bool,         # more than one baseline stands for this label
             "baseline_count": int,
             "observed_text": str,      # what the caller actually passed
             "observed_partial": bool,  # digits were dropped reading it
             "baseline_text": str,      # the sealed baseline as it was written
             "baseline_partial": bool}

        ``within_tolerance`` is true iff the NumericMatcher scores the pair a
        perfect ``1.0`` (i.e. ``|observed - baseline| <= max(abs_tol,
        pct_tol*max(|.|))``). Anything else with a known baseline is ``flagged``.
        Every check is appended to the ledger.

        **``variation_pct`` and the verdict do not share a denominator, and
        ``tolerance_abs`` is what reconciles them.** The percentage is
        baseline-relative (``variation / |baseline|``) because that is the
        figure an auditor means by "how far off was it." The verdict is
        symmetric, so its proportional leg is a fraction of the *larger*
        magnitude (:meth:`~nestor.matcher.NumericMatcher.tolerance_for`).
        Against a rising observation the larger magnitude is the observation,
        so a check can report a percentage above ``pct_tol`` and still pass —
        at the default ``pct_tol=0.05`` anything up to ``pct/(1-pct)``, i.e.
        ``5.2632%``, reads as over-tolerance while passing. Both numbers are
        right; a reader given only one of them cannot see why. So the absolute
        slack the comparison actually used travels with the result, and
        ``variation <= tolerance_abs`` is checkable arithmetic that needs no
        denominator convention at all. ``None`` when there is no baseline or no
        readable observation — there is nothing to have measured against.

        **The two ``_text`` / ``_partial`` fields answer "is this figure the one
        I typed?"** ``NumericMatcher.parse`` searches for a number rather than
        requiring one, so ``"1,00o,000"`` is compared as ``100``. That is safe —
        it gets flagged and a human looks — but a result that reports only
        ``observed: 100.0`` cannot be told apart from one where 100 was
        genuinely observed, and an audit is exactly where that difference
        matters. ``observed_partial`` is true when digits were left outside the
        figure the comparison used; the raw string is beside it so the reader
        can see both at once. Currency and unit suffixes do not trip it (see
        ``NumericMatcher.parse_detail``).

        When more than one sealed baseline stands for a label, the **newest**
        one is used and ``ambiguous`` is set. It used to be whichever scored
        highest, i.e. whichever sat closest to the observation — the one choice
        guaranteed to under-report a deviation, since the figure most likely to
        excuse an observation is the one nearest it. :meth:`seal_baseline` now
        keeps a label to one baseline, so this is the fallback for stores that
        cannot retire the old one, not the normal path.
        """
        obs = self.matcher.parse_detail(observed)
        obs_num = obs["value"]
        # context_threshold=0.0 so even a wildly off observation still returns
        # the baseline candidate (we need it to report the variation). The limit
        # is raised past lookup's default because ranking is by similarity and
        # the baseline we want is the newest, which may not be in the top 5.
        matches = memory.lookup(
            observed, label, self.domain, store=self.store,
            matcher=self.matcher, context_threshold=0.0, limit=100,
        )
        # Verified seals only — a forged "sealed" row must not become a trusted
        # baseline (Nestor#2 follow-up: this path used to skip the signature
        # check that best_sealed does).
        sealed = memory.verified_sealed(matches)

        if not sealed:
            result = {
                "label": label, "baseline": None, "observed": obs_num,
                "within_tolerance": False, "variation": None,
                "variation_pct": None, "tolerance_abs": None, "flagged": False,
                "ambiguous": False, "baseline_count": 0,
                "baseline_text": "", "baseline_partial": False,
            }
        else:
            sealed = sorted(sealed, key=lambda m: m["pair"].get("created_at", ""),
                            reverse=True)
            top = sealed[0]
            baseline = float(top["pair"]["source_norm"])
            within = top["similarity"] == 1.0
            variation = abs(obs_num - baseline) if obs_num is not None else None
            variation_pct = (variation / abs(baseline)
                             if variation is not None and baseline != 0 else None)
            # Recomputed from the same method the score turned on, rather than
            # inferred from the verdict — an unreadable observation has no
            # tolerance because it was never compared, not a tolerance of zero.
            tolerance_abs = (self.matcher.tolerance_for(baseline, obs_num)
                             if obs_num is not None else None)
            # The baseline's own text is what a human sealed; source_norm is the
            # figure it was read as. They differ exactly when the seal was made
            # from a partially-parsed value, which is the case worth surfacing.
            base_text = top["pair"].get("target_text", "")
            result = {
                "label": label, "baseline": baseline, "observed": obs_num,
                "within_tolerance": within, "variation": variation,
                "variation_pct": variation_pct, "tolerance_abs": tolerance_abs,
                "flagged": not within,
                "ambiguous": len(sealed) > 1, "baseline_count": len(sealed),
                "baseline_text": base_text,
                "baseline_partial": self.matcher.parse_detail(base_text)["partial"],
            }
        result["observed_text"] = obs["text"]
        result["observed_partial"] = obs["partial"]

        _ledger_append({
            "kind": "reconcile", "domain": self.domain, "label": label,
            "baseline": result["baseline"], "observed": result["observed"],
            "within_tolerance": result["within_tolerance"],
            "variation": result["variation"], "flagged": result["flagged"],
            "ambiguous": result["ambiguous"],
            # Flags, not the raw strings — see seal_baseline. "the figure I
            # compared was not the figure that was typed" is the auditable fact.
            "observed_partial": result["observed_partial"],
            "baseline_partial": result["baseline_partial"],
        })
        return result
