"""Recipe — a Jeles nugget → the same answer, under a signature.

`jeles <https://github.com/rudi193-cmd/Jeles>`_ is the fleet's verified-corpus
organ: a **nugget** is ``{question, answer, sources, verified_by, verified_at,
tags}``, and a miss is logged as a **gap** — *"I don't know yet"*. It is a
sibling of this package in everything but lineage, and the two repositories
contain **zero** references to each other.

What the two arrived at independently
--------------------------------------
=========================  ==========================================
jeles                      nestor
=========================  ==========================================
``verification_kind``      status
``"human"``                ``sealed``
``"machine"``              ``draft`` (a machine proposed it)
``"asserted"``             a tool-call write nobody checked
a **gap**                  ``pending`` — nothing to offer, said plainly
``search_nuggets``         :func:`nestor.memory.lookup`
``ask_corpus``             :func:`nestor.memory.best_sealed`
"a write may not          ``ConflictingSealError`` and the status
overwrite a nugget of      precedence in ``add_pair``
a higher kind"
=========================  ==========================================

Even the refusals match. With ``include_asserted=False`` — the default —
``ask_corpus`` returns ``found: false`` for an asserted nugget and drops it to
``candidates``. That is tier 1 refusing to serve tier 2, written by somebody who
had never read this package.

The one thing that does not map, which is the whole reason for this module
---------------------------------------------------------------------------
``corpus.put_nugget``'s own docstring, verbatim:

    ``verified_by`` is a claim: whatever string the writer supplied.

jeles is scrupulous about it — it adds ``written_by`` as *"the fact beside it"*,
pins tool-call writes to ``"asserted"``, and refuses to let a lower kind
overwrite a higher one. Every one of those is a good decision and none of them
is a **check**. Nothing stops a writer typing any name into ``verified_by``, and
nothing downstream can tell a real verification from a typed one.

That is the exact gap this package exists to close: a seal is bound to a key the
store does not hold, and a row that merely *says* it was verified is not served.

So: **every nugget crosses as a draft.** Not as a judgement about jeles' data —
as the only honest reading of an unsigned claim, and precisely what
:func:`nestor.portable.import_bundle` already does to a bundle asserting a seal
it cannot prove (*"N demoted to draft (signature does not verify here)"*). This
module reports in the same shape, for the same reason. A ``verification_kind``
of ``"human"`` is carried into the row's ``reason`` so nothing is lost and a
reviewer can see what jeles believed — it just does not arrive as a seal.

**Re-sealing here is a real decision, not an import step.** A human opens the
queue, reads the nugget and its sources, and seals under their own key. What
they are signing is *"I checked this"*, which is a different sentence from what
jeles stored, and the difference is the point.

.. warning::

   Sealing a bridged nugget through ``nestor.ui`` currently **loses it**.
   :class:`NuggetMatcher` is a custom matcher, the surface has no way to be told
   about one, and the seal lands under a key this domain never computes — see
   IDEAS §6.40 and ``demo/two_desks.py``. Until that is fixed the only way to
   seal these correctly is in-process with ``memory.set_matcher(MATCHER)``
   installed. This integration is blocked on that finding, which is the most
   useful thing it has to say.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from nestor import memory

DOMAIN = "nugget"

#: Carried onto every row so a reviewer can see where it came from without
#: reading this module.
ORIGIN = "jeles:corpus"

_TOKEN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]*")

#: jeles' own asking rule, in its words: a nugget answers only when its question
#: contains *every* content word the asker used and the two overlap
#: symmetrically. Its stopword list is small for the same reason
#: ``recipes/patch_review.py``'s is — a list grown until the numbers improve is
#: corpus-fitting wearing a method's clothes.
STOPWORDS = frozenset({"the", "a", "an", "of", "and", "or", "to", "in", "for",
                       "is", "are", "was", "were", "do", "does", "did", "what",
                       "which", "who", "when", "where", "how", "why", "it",
                       "this", "that", "on", "at", "by", "with", "as", "be"})


def content_words(text: Any) -> set[str]:
    """Content tokens of a question, case-folded. Never empty if there was text."""
    toks = [t.lower().rstrip(".:-") for t in _TOKEN.findall(str(text))]
    kept = {t for t in toks if t and t not in STOPWORDS}
    return kept or {t for t in toks if t}


class NuggetMatcher:
    """Two-method seam, matching jeles' *answering* rule rather than its ranking.

    ``ask_corpus`` and ``search_nuggets`` are deliberately different decisions in
    jeles — one ranks loosely, the other answers strictly. This mirrors the
    strict one, because in this package the strict decision is what
    :func:`nestor.memory.best_sealed` makes and the loose one is
    :func:`nestor.memory.lookup`'s.

    Containment, then symmetry: a question about *staging* must not be answered
    by a nugget about *production*, and one shared word must not pull an answer
    out of a nugget it barely resembles.
    """

    def normalize(self, value: Any) -> str:
        return " ".join(sorted(content_words(value)))

    def similarity(self, a_norm: str, b_norm: str) -> float:
        a, b = set(a_norm.split()), set(b_norm.split())
        if not a or not b:
            return 0.0
        shared = a & b
        if not shared:
            return 0.0
        # Symmetric overlap (Jaccard), gated on the asker's words all being
        # present — the containment half of jeles' rule.
        contained = a <= b or b <= a
        overlap = len(shared) / len(a | b)
        return overlap if contained else overlap * 0.5


MATCHER = NuggetMatcher()


def _reason(nugget: dict) -> str:
    """What jeles believed, kept beside the row rather than acted on."""
    kind = nugget.get("verification_kind") or nugget.get("status") or "unknown"
    who = nugget.get("verified_by") or "unspecified"
    wrote = nugget.get("written_by")
    when = nugget.get("verified_at") or ""
    srcs = ", ".join(str(s) for s in (nugget.get("sources") or [])) or "none listed"
    said = (f"jeles held this as {kind!r}, verified_by={who!r}"
            + (f", written_by={wrote!r}" if wrote else "")
            + (f", {when}" if when else ""))
    return (f"{said}. Sources: {srcs}. Crossed as a DRAFT because verified_by is "
            f"an unsigned claim — jeles' own docstring says so — and this store "
            f"only serves what it can verify.")


def bridge_nuggets(nuggets: Iterable[dict], store=None) -> dict:
    """Bring jeles nuggets in. **Every one lands as a draft.**

    Reports in :func:`nestor.portable.import_bundle`'s shape, because it is the
    same event: something arrived claiming verification it cannot prove here.

    Returns ``{"sealed": 0, "demoted": n, "existing": n, "conflicts": [...],
    "gaps_seen": 0}``.
    """
    report: dict[str, Any] = {"sealed": 0, "demoted": 0, "existing": 0,
                              "conflicts": [], "gaps_seen": 0}
    for nugget in nuggets:
        question = str(nugget.get("question") or "").strip()
        answer = str(nugget.get("answer") or "").strip()
        if not question or not answer:
            continue
        try:
            row = memory.add_pair(question, answer, DOMAIN, DOMAIN,
                                  status="draft", origin=ORIGIN,
                                  reason=_reason(nugget), store=store,
                                  matcher=MATCHER)
        except Exception as exc:      # a live row already disagrees
            report["conflicts"].append({"question": question,
                                        "incoming": answer,
                                        "refused": type(exc).__name__})
            continue
        # `add_pair` returns the stored row; an identical re-import is a no-op.
        if row.get("target_text") == answer and row.get("status") == "draft":
            report["demoted"] += 1
        else:
            report["existing"] += 1
    return report


def bridge_gaps(gaps: Iterable[dict]) -> list[dict]:
    """jeles gaps, shaped for a human to read. Deliberately **not** written.

    A gap is a question with no answer. There is nothing to propose, so there is
    no row to write — putting an empty target in the memory would be inventing
    the thing the gap exists to record the absence of. Returned for a queue view
    and for :func:`nestor.memory.best_sealed` to keep answering ``None`` about.
    """
    out = []
    for gap in gaps:
        question = str(gap.get("question") or "").strip()
        if not question:
            continue
        out.append({"question": question,
                    "asked_count": gap.get("asked_count", 0),
                    "variants": list(gap.get("variants") or [])})
    out.sort(key=lambda g: g["asked_count"], reverse=True)
    return out


def answer_for(question: str, *, store=None,
               seal_threshold: Optional[float] = None):
    """The **verified** answer, or ``None``. jeles' ``ask_corpus``, with a key.

    Returns only a sealed row above the threshold, so a bridged nugget nobody
    re-checked here can never come back from this call — which is the entire
    reason to bridge rather than to copy.
    """
    return memory.best_sealed(question, DOMAIN, DOMAIN, store=store,
                              matcher=MATCHER, seal_threshold=seal_threshold)


def candidates(question: str, limit: int = 5, *, store=None) -> list[dict]:
    """Ranked matches, sealed and draft — jeles' ``search_nuggets``. The queue
    view, not the serving view."""
    return memory.lookup(question, DOMAIN, DOMAIN, limit=limit, store=store,
                         matcher=MATCHER, context_threshold=0.0)
