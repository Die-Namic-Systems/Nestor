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
(scored via ``matcher.score()`` on raw text when available, otherwise on
normalized text pruned by ``similarity_bound`` so ~50k pairs stay cheap):

* commitments also align (commitment similarity ``>= bar``) -> **supersedes**:
  the later decision (higher id — ids are zero-padded ``"<file>#<index>"``, so a
  plain string compare orders them) supersedes the earlier duplicate.
  ``src`` = later, ``dst`` = earlier.
* commitments diverge (commitment similarity ``< bar``) **and** question
  similarity ``>= bar + _CONTRADICT_UPLIFT`` -> **contradicts**: one question,
  two different answers. The higher gate for contradiction cuts structural
  false positives ("Should the X?" / "Should the Y?" pairs whose skeleton
  scores 0.55–0.65 on difflib). Emitted as a **single canonical edge, later
  -> earlier** — the same direction as ``supersedes`` so the two kinds read
  consistently. Contradiction is symmetric; the direction is a convention, not a
  claim that the later answer wins (that is the human's call).

``refines`` is left unemitted: a reliable "strict specialization of another
question" test is not cheap on difflib ratios, and the package's rule is to omit
a mechanism rather than ship an unreliable one.

The store's 7 hand-written ``consolidated_onto`` files (now under
``docs/archive/decisions/``) are a **sanity check**,
not an input — this pass re-derives supersession from the questions themselves
so it can find the rewordings the hand notes missed, and a hand note it *does*
recover is corroboration, never the source.
"""
from __future__ import annotations

from nestor.matcher import Matcher, uses_raw_score
from nestor.triage import Decision, ProposedEdge

#: How much of a question / commitment to quote in an edge's evidence. Enough to
#: recognize the pair, short enough that a report of hundreds of edges stays
#: readable. The full text is one lookup away by id.
_CLIP = 90


def _clip(text: str, limit: int = _CLIP) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _question_bound(matcher: Matcher, a_norm: str, b_norm: str,
                    floor: float) -> float:
    """Upper bound on the question similarity, using the matcher's cheap
    ``similarity_bound`` when it offers one (lossless prune) and falling back to
    the real ``similarity`` for a matcher that does not — a candidate whose upper
    bound is below ``floor`` cannot clear it, so it never gets fully scored."""
    bound = getattr(matcher, "similarity_bound", None)
    if callable(bound):
        return bound(a_norm, b_norm, floor=floor)
    return matcher.similarity(a_norm, b_norm)


def _score_pair(matcher: Matcher, raw_a: str, norm_a: str,
                raw_b: str, norm_b: str, has_raw: bool) -> float:
    """Score a pair using ``score()`` on raw text when available, else
    ``similarity()`` on normalised text."""
    if has_raw:
        return matcher.score(raw_a, raw_b)  # type: ignore[attr-defined]
    return matcher.similarity(norm_a, norm_b)


#: Contradiction needs stronger question evidence than supersession.
#: At bar=0.55 structural skeleton overlap ("Should the X?" / "Should the Y?")
#: scores 0.55–0.65 on difflib, flooding the report with false positives (98
#: of 103 edges on the 316-row dogfood corpus). Genuine same-question /
#: divergent-answer pairs score 0.75+. The uplift raises the question gate for
#: contradiction specifically, cutting the skeleton noise without touching
#: supersession recall (which already requires commitments to align).
_CONTRADICT_UPLIFT = 0.15


def find_supersessions(decisions: list[Decision], matcher: Matcher,
                       bar: float) -> list[ProposedEdge]:
    """Propose ``supersedes`` / ``contradicts`` edges between draft decisions.

    Pure and deterministic: same decisions and matcher in, same edges out, sorted
    by ``(src_id, dst_id)``. Scores questions using ``matcher.score()`` on raw
    text when available, falling back to ``similarity()`` on normalised text.
    A pair only survives if the questions match at or above ``bar``
    (supersession) or ``bar + _CONTRADICT_UPLIFT`` (contradiction — the higher
    gate cuts structural false positives). Commitments decide the kind: aligned
    is a supersession, divergent is a contradiction. Writes nothing.
    """
    has_raw = uses_raw_score(matcher)
    norm_q = [matcher.normalize(d.question) for d in decisions]
    norm_c = [matcher.normalize(d.commitment) for d in decisions]
    raw_q = [d.question for d in decisions]
    raw_c = [d.commitment for d in decisions]

    contradict_bar = bar + _CONTRADICT_UPLIFT

    edges: list[ProposedEdge] = []
    n = len(decisions)
    for i in range(n):
        qi = norm_q[i]
        if not qi:
            continue
        for j in range(i + 1, n):
            qj = norm_q[j]
            if not qj:
                continue
            if not has_raw and _question_bound(matcher, qi, qj, bar) < bar:
                continue
            q_sim = _score_pair(matcher, raw_q[i], qi, raw_q[j], qj, has_raw)
            if q_sim < bar:
                continue

            c_sim = _score_pair(matcher, raw_c[i], norm_c[i],
                                raw_c[j], norm_c[j], has_raw)

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
            elif q_sim >= contradict_bar:
                kind = "contradicts"
                evidence = (
                    f"same question (q-sim {q_sim:.2f} >= contradict bar "
                    f"{contradict_bar:.2f}) but commitments diverge "
                    f"(c-sim {c_sim:.2f} < bar {bar:.2f}) -> "
                    f"{later.id} answers it differently from {earlier.id}. "
                    f"A: {_clip(later.commitment)!r} vs {_clip(earlier.commitment)!r}"
                )
            else:
                continue

            edges.append(ProposedEdge(
                src_id=later.id,
                dst_id=earlier.id,
                kind=kind,
                score=round(q_sim, 6),
                evidence=evidence,
            ))

    edges.sort(key=lambda e: (e.src_id, e.dst_id))
    return edges
