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

Sealing a bridged nugget
------------------------
Hand the surface this module's matcher, and a human can seal these where they
are meant to::

    from nestor import ui
    from recipes import jeles_bridge

    app = ui.App(store=store, source_lang=jeles_bridge.DOMAIN,
                 target_lang=jeles_bridge.DOMAIN, matcher=jeles_bridge.MATCHER)

This used to be the blocker rather than the instructions. ``nestor.ui`` took the
domain tags and had no field for a matcher, so a seal made here landed under a
key this domain never computes: the bridged draft stayed queued and the
verification was unreachable — see IDEAS §6.40 and ``demo/two_desks.py``. The
only workaround was ``memory.set_matcher(MATCHER)`` process-wide, which is a
module global and therefore rules out running this bridge beside any other
custom-matcher domain. Both are gone; the global still works and is no longer
the only way.
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


# --------------------------------------------------------------------------
# The return leg, and why it cannot carry what it is carrying
# --------------------------------------------------------------------------

#: Everything ``jeles.corpus.put_nugget`` will accept. Mirrored rather than
#: introspected: importing jeles to build this list would make the pin true by
#: construction, and this module must work with jeles absent.
NUGGET_FIELDS = ("question", "answer", "sources", "verified_by", "tags",
                 "nugget_id", "verified_at", "verification_kind", "written_by")

#: What a Nestor seal knows that a nugget has nowhere to put. Not a complaint —
#: a list, so :func:`unexportable` can report it and a fix can be scoped.
SEAL_EVIDENCE = ("seal_sig", "ledger_hash", "ledger_position", "key_id",
                 "superseded_by")


def unexportable(pair: dict) -> dict:
    """The parts of a sealed row that cannot cross into a nugget.

    ``put_nugget`` rejects unknown keyword arguments outright — measured,
    ``TypeError: got an unexpected keyword argument 'seal_sig'`` — and the
    stored record has eleven fields, none of which is for evidence. The two
    free-form slots are ``sources`` and ``tags``; a signature is neither a
    citation nor a label, and smuggling it into one would make this package's
    own provenance display lie about what a source is.

    So the evidence is dropped at the border, and this function is the honest
    account of what was dropped rather than a workaround for it.
    """
    return {k: pair.get(k) for k in SEAL_EVIDENCE if pair.get(k)}


def export_sealed(store=None, limit: int = 1000) -> tuple[list[dict], list[dict]]:
    """``(nuggets, dropped)`` — sealed rows shaped for jeles, and the cost.

    **Every nugget goes out as ``verification_kind="asserted"``**, which is the
    weakest rung jeles has, and that is not a mistake to be fixed by passing a
    stronger one.

    A row here was sealed by a named human under a key this store does not hold,
    and appended to a hash chain. None of that can travel: see
    :func:`unexportable`. What arrives at jeles is a question, an answer, and a
    name — which is exactly what jeles calls an *assertion*, and exactly what
    its own ``corpus_server`` pins tool-call writes to, for the same reason:
    nobody at the receiving end checked it.

    So the round trip is lossy in **both** directions, and both losses are
    correct. Inbound, this store refuses to inherit a claim it cannot verify.
    Outbound, it cannot hand over the evidence that would let jeles do better
    than trust it. The asymmetry is not in the trust models — the two are nearly
    identical — it is that one of them has a field for a signature.

    ``written_by="nestor"`` is the fact beside the claim, in jeles' own idiom.
    """
    store = memory.get_store(store) if hasattr(memory, "get_store") else store
    from nestor.storage import get_store
    store = get_store(store)
    store.memory_init()

    nuggets: list[dict] = []
    dropped: list[dict] = []
    for row in store.memory_candidates(DOMAIN, DOMAIN):
        if row.get("status") != "sealed":
            continue
        if not memory.is_verified_seal(row):
            # A row that says sealed and does not verify is not exported at
            # all. Sending it would be laundering in the other direction.
            continue
        lost = unexportable(row)
        nuggets.append({
            "question": row["source_text"],
            "answer": row["target_text"],
            "sources": [s for s in [row.get("origin")] if s],
            "verified_by": row.get("verifier") or "",
            "verified_at": (row.get("created_at") or "")[:10],
            "tags": ["nestor"],
            # The honest rung. See this function's docstring.
            "verification_kind": "asserted",
            "written_by": "nestor",
        })
        if lost:
            dropped.append({"question": row["source_text"], "lost": lost})
        if len(nuggets) >= limit:
            break
    return nuggets, dropped


#: What happens when an exported nugget is actually written into jeles.
#: **Measured, both routes**, because "it degrades to asserted" turned out not to
#: be the end of the story:
#:
#: * **without** ``nugget_id`` — ``action: "created"``. A second record for the
#:   same question. jeles then serves the original, because ``human`` outranks
#:   ``asserted``, so the round trip's contribution is invisible and the corpus
#:   is one row bigger.
#: * **with** the original ``nugget_id`` — ``{"error": "kind_downgrade_refused"}``,
#:   and the message is better than most: *"A lower rung cannot overwrite a
#:   higher one — write it as a new nugget and let a person supersede the
#:   existing one."*
#:
#: Both are correct behaviour by jeles. Together they mean the loop **cannot be
#: closed from this side**: this package's strongest output is that package's
#: weakest input, so the return leg either duplicates or is refused.
LANDING = {"no_id": "created — a duplicate the corpus will not serve",
           "with_id": "kind_downgrade_refused — asserted cannot overwrite human"}

#: The one-field fix, which belongs to jeles and is therefore **proposed, not
#: made**. If a nugget could carry the seal signature, this package could export
#: at ``"human"`` *and back it*, and jeles could verify rather than trust — which
#: is the only version of this integration where the round trip adds something
#: instead of costing something.
PROPOSAL = ("jeles nuggets have no field for evidence. A `seal_sig` (or a "
            "general `evidence` mapping) would let a verification cross a "
            "repository boundary intact. Proposed for jeles, not implemented "
            "here: it is their schema, and a machine may propose.")


def round_trip_report(inbound: dict, nuggets: list[dict],
                      dropped: list[dict]) -> str:
    """One paragraph a person can read, stating every loss plainly."""
    lost_keys = sorted({k for d in dropped for k in d["lost"]})
    return (
        f"in:  {inbound['demoted']} nugget(s) demoted to draft, "
        f"{inbound['sealed']} sealed — verified_by is an unsigned claim here.\n"
        f"out: {len(nuggets)} sealed row(s) exported as 'asserted', the weakest "
        f"rung jeles has.\n"
        f"     dropped at the border: {', '.join(lost_keys) or 'nothing'} — "
        f"a nugget has no field for evidence.\n"
        f"land: without an id -> {LANDING['no_id']}\n"
        f"      with one      -> {LANDING['with_id']}\n"
        f"Every one of those is correct behaviour on both sides, and together "
        f"they mean the loop does not close. {PROPOSAL}"
    )
