"""Supersession / refutation pass — the payoff of "search for what REFUTES,
not what resembles."

This is Jeles' ``conflict_scan`` stance re-landed clean-room for the seal queue:
before a human seals a draft decision, tell them which drafts are *already
answered* by another — resolved-and-duplicated (``supersedes``) or, the finding
that actually earns its keep, same-question / divergent-answer
(``contradicts``). A mirror pass ("what resembles this") would hand a reviewer a
pile of look-alikes; this one hands them the pairs where sealing the older row
would contradict a newer decision.

The stance carried across from ``jeles.reactions.conflict_scan``:

* **Injected scorer.** Similarity rides the passed-in ``matcher`` (the same
  offline character matcher the store already uses) — no embeddings, no network,
  nothing imported at module load.
* **Propose, don't execute.** :func:`find_supersessions` returns
  :class:`~nestor.triage.ProposedEdge` values and writes nothing — not a seal,
  not a ``verifier``, not the store. The sink (``DecisionMemory.propose_edge``)
  is a separate act a human drives.
* **Every proposal names its evidence.** An edge carries the matched questions
  and the commitment agreement / divergence that classified it, so a human
  re-checks the finding rather than trusting the score.

Classification, for each pair whose **questions** match at or above ``bar``
(scored on normalized text, pruned by ``similarity_bound`` so ~50k pairs stay
cheap):

* commitments also align (commitment similarity ``>= bar``) -> **supersedes**:
  the later decision (higher id — ids are zero-padded ``"<file>#<index>"``, so a
  plain string compare orders them) supersedes the earlier duplicate.
  ``src`` = later, ``dst`` = earlier.
* commitments diverge (commitment similarity ``< bar``) -> **contradicts**: one
  question, two different answers. Emitted as a **single canonical edge, later
  -> earlier** — the same direction as ``supersedes`` so the two kinds read
  consistently. Contradiction is symmetric; the direction is a convention, not a
  claim that the later answer wins (that is the human's call).

``refines`` is left unemitted: a reliable "strict specialization of another
question" test is not cheap on difflib ratios, and the package's rule is to omit
a mechanism rather than ship an unreliable one.

The store's 7 hand-written ``consolidated_onto`` files are a **sanity check**,
not an input — this pass re-derives supersession from the questions themselves
so it can find the rewordings the hand notes missed, and a hand note it *does*
recover is corroboration, never the source.
"""
from __future__ import annotations

from nestor.matcher import StringMatcher
from nestor.triage import Decision, ProposedEdge

#: How much of a question / commitment to quote in an edge's evidence. Enough to
#: recognize the pair, short enough that a report of hundreds of edges stays
#: readable. The full text is one lookup away by id.
_CLIP = 90


def _clip(text: str, limit: int = _CLIP) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _question_bound(matcher: StringMatcher, a_norm: str, b_norm: str,
                    floor: float) -> float:
    """Upper bound on the question similarity, using the matcher's cheap
    ``similarity_bound`` when it offers one (lossless prune) and falling back to
    the real ``similarity`` for a matcher that does not — a candidate whose upper
    bound is below ``floor`` cannot clear it, so it never gets fully scored."""
    bound = getattr(matcher, "similarity_bound", None)
    if callable(bound):
        return bound(a_norm, b_norm, floor=floor)
    return matcher.similarity(a_norm, b_norm)


def find_supersessions(decisions: list[Decision], matcher: StringMatcher,
                       bar: float) -> list[ProposedEdge]:
    """Propose ``supersedes`` / ``contradicts`` edges between draft decisions.

    Pure and deterministic: same decisions and matcher in, same edges out, sorted
    by ``(src_id, dst_id)``. Scores questions on their normalized text; a pair
    only survives if the questions match at or above ``bar``. Then the
    commitments decide the kind — aligned is a duplicate the later row
    supersedes, divergent is a contradiction. Writes nothing.
    """
    norm_q = [matcher.normalize(d.question) for d in decisions]
    norm_c = [matcher.normalize(d.commitment) for d in decisions]

    edges: list[ProposedEdge] = []
    n = len(decisions)
    for i in range(n):
        qi = norm_q[i]
        if not qi:
            continue  # a decision with no question cannot be matched on one
        for j in range(i + 1, n):
            qj = norm_q[j]
            if not qj:
                continue
            # Cheap upper-bound prune first — most of the ~50k pairs die here
            # without ever paying for a full difflib ratio.
            if _question_bound(matcher, qi, qj, bar) < bar:
                continue
            q_sim = matcher.similarity(qi, qj)
            if q_sim < bar:
                continue

            # Questions match. The commitments now decide supersede vs contradict.
            c_sim = matcher.similarity(norm_c[i], norm_c[j])

            # Direction: the later decision (higher id) is src. ids are
            # zero-padded "<file>#<index>", so a string compare is the ordering.
            a, b = decisions[i], decisions[j]
            later, earlier = (a, b) if a.id > b.id else (b, a)

            if c_sim >= bar:
                kind = "supersedes"
                evidence = (
                    f"same question (q-sim {q_sim:.2f} >= bar {bar:.2f}); "
                    f"commitments align (c-sim {c_sim:.2f} >= bar) -> later "
                    f"{later.id} supersedes earlier {earlier.id}. "
                    f"Q: {_clip(later.question)!r} ~ {_clip(earlier.question)!r}"
                )
            else:
                kind = "contradicts"
                evidence = (
                    f"same question (q-sim {q_sim:.2f} >= bar {bar:.2f}) but "
                    f"commitments diverge (c-sim {c_sim:.2f} < bar {bar:.2f}) -> "
                    f"{later.id} answers it differently from {earlier.id}. "
                    f"A: {_clip(later.commitment)!r} vs {_clip(earlier.commitment)!r}"
                )

            edges.append(ProposedEdge(
                src_id=later.id,
                dst_id=earlier.id,
                kind=kind,
                score=round(q_sim, 6),
                evidence=evidence,
            ))

    edges.sort(key=lambda e: (e.src_id, e.dst_id))
    return edges
