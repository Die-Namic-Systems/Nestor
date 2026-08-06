"""Recipe — defect description → proposed fix, under the covenant.

The README's Matcher-seam table has a row reading *yours / yours / whatever you
can normalize and score*, and claims a date matcher and a CSV-header mapper were
both built against the shipped package without modifying it. This is a third,
built the same way: nothing in ``nestor/`` changes, and every guarantee — the
three states, the hash chain, the refusal to let a machine confirm — is
inherited rather than reimplemented.

    source  = a defect, described in prose
    target  = the fix for it
    sealed  = a human has checked that this fix is the fix for this defect

**What this does not do.** It does not decide whether a patch is correct. There
is no execution anywhere in Nestor and this recipe adds none. A seal here means
exactly what it means everywhere else — *a person checked this* — and never
*the tests passed*. That distinction is the product, and a recipe that blurred
it would be worth less than no recipe.

---

## Rival patches, and why the refusal is right

The obvious objection to putting patches in Nestor is that a defect can have two
plausible fixes, and the store permits **one live row per normalized source**:
a second, different draft for one defect raises ``ConflictingDraftError``.

That refusal is correct, and it took building this to see why. ``IDEAS.md``
§6.19 records what the silence before it cost — ``add_pair`` over an existing
draft with a different target wrote nothing, ledgered nothing, warned about
nothing, and handed the *stored* proposal back to a caller who had proposed
something else. The two rival hazards it names apply here word for word: a
machine swapping the row under a reviewer mid-review, so they seal something
they never read; or a caller believing a proposal landed when it did not.

So rival patches get two named exits, and this module gives them names rather
than routing around the guard:

* :func:`revise` — *I changed my mind.* The old proposal is kept as history
  with the reason it was abandoned for, which is `revise_draft`'s whole point.
  Rivals become a **sequence**, and the record shows the order and the why.
* :func:`split_hint` — *both are still live.* Then the defect description is
  doing double duty, and the honest move is two defects rather than one row
  with two answers. This is §6.22's collision in a new domain: the key says
  these are the same source when they are not.

What you cannot have is two live proposals for one defect awaiting one
decision. That is a real loss, and it is the same gap ``docs/detection-kit-as-gates.md``
finds at the kit's tool #4: Nestor holds alternatives as *lineage*, never as
*concurrent competitors*. If you want a bake-off between two patches, Nestor is
not where the bake-off happens — it is where the outcome is recorded.

---

## Why `StringMatcher` is the wrong scorer here, and what replaces it

Defect descriptions are prose *about* code, and they carry two populations of
token that a character-similarity matcher cannot tell apart:

* **prose** — "returns", "silently", "the caller" — high frequency, low signal,
  and near-identical across every defect ever written;
* **identifiers** — ``memory_init``, ``ConflictingSealError``,
  ``superseded_by``, ``sqlite_store.py:374`` — rare, and almost the whole
  signal.

`StringMatcher` is difflib over characters, so two unrelated defects written in
the same house style score high on shared prose, and one defect written twice in
different words scores low despite naming the same function both times.
:class:`DefectMatcher` weights identifier tokens above prose tokens and compares
token sets, which is symmetric — `bench/token_matchers.py` records that
`StringMatcher`'s asymmetry broke serving in measurable ways, and a matcher that
regressed on that would be worse than useless.

``IDENT_WEIGHT`` was fixed at ``3.0`` **before** anything was measured. A weight
tuned until the numbers improve is, in that module's words, *"a way of fitting
the corpus and calling it a method."* ``recipes/bench_patch_review.py`` reports
the whole curve so the choice can be judged rather than trusted.

**One inherited limitation, stated because §6.22 exists.** ``normalize``
case-folds, so ``ConflictingSealError`` and ``conflictingsealerror`` are one
key. That is right for prose *about* code, where a human types a name from
memory. It would be wrong for a store holding code *itself*, where case is
frequently the meaning — the same trap §6.22 documents for ``Nestor`` versus
``nestor``. If this recipe is ever pointed at source text rather than
descriptions, this normalize is the first thing that has to go.
"""
from __future__ import annotations

import re
from typing import Optional

from nestor import memory
# ConflictingDraftError is NOT on the package's public surface, though
# ConflictingSealError and RejectedPairError both are — so the one error that
# directs a caller to the third verb is the one you cannot catch from `nestor`.
# Recorded as IDEAS §6.29; imported from the module until that is settled.
from nestor.memory import ConflictingDraftError

DOMAIN = "defect"

#: How much more a token that looks like code counts than a token that looks
#: like English. Chosen a priori; see the module docstring and the bench.
IDENT_WEIGHT = 3.0

# Same tiny list as bench/token_matchers.py, and tiny for the same reason: a
# stopword list grown until the numbers improve is corpus-fitting wearing a
# method's clothes.
STOPWORDS = frozenset({"the", "a", "an", "of", "and", "or", "to", "in", "for",
                       "this", "that", "these", "those", "its", "it", "is"})

# A token may carry _ . : so `sqlite_store.py:374` and `memory_init` survive
# tokenization whole. Trailing separators are sentence punctuation, not part of
# the name, and are stripped after the match.
_TOKEN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:]*")
_SNAKE = re.compile(r"[A-Za-z0-9]_[A-Za-z0-9]")
_CAMEL = re.compile(r"[a-z][A-Z]")


def looks_like_code(token: str) -> bool:
    """Whether a token is an identifier rather than an English word.

    Three mechanical signals, no vocabulary list: snake_case, an internal
    case change (``camelCase`` / ``CamelCase``), or a dotted/colonned path such
    as ``sqlite_store.py:374``. Deliberately syntactic — a list of "known code
    words" would need maintaining and would silently mis-weight every project
    that did not write it.
    """
    return bool(_SNAKE.search(token) or _CAMEL.search(token)
                or "." in token or ":" in token)


def _weighted(value) -> dict[str, float]:
    """Token -> weight, for one raw input. Case-folded; see the docstring."""
    out: dict[str, float] = {}
    for raw in _TOKEN.findall(str(value)):
        tok = raw.rstrip(".:")
        if not tok:
            continue
        weight = IDENT_WEIGHT if looks_like_code(tok) else 1.0
        low = tok.lower()
        if weight == 1.0 and low in STOPWORDS:
            continue
        # A token seen twice is one token: this is a set measure, and letting
        # repetition raise a score rewards verbosity in a bug report.
        out[low] = max(out.get(low, 0.0), weight)
    if not out:  # never normalize to empty — token_matchers.py's rule
        out = {t.lower(): 1.0 for t in _TOKEN.findall(str(value))}
    return out


def _jaccard(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    union = sum(max(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)
    inter = sum(min(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)
    return inter / union if union else 0.0


class DefectMatcher:
    """Token-set matcher that weights identifiers above prose. Symmetric.

    Satisfies ``nestor.matcher.Matcher``: ``normalize`` + ``similarity``, plus
    the optional ``score`` so :mod:`nestor.memory` compares raw texts and
    ``normalize`` can stay a plain dedup key (IDEAS §3.1).
    """

    def normalize(self, value) -> str:
        return " ".join(sorted(_weighted(value)))

    def similarity(self, a_norm: str, b_norm: str) -> float:
        return _jaccard(_weighted(a_norm), _weighted(b_norm))

    def score(self, raw_a, raw_b) -> float:
        return _jaccard(_weighted(raw_a), _weighted(raw_b))


MATCHER = DefectMatcher()


class RivalPatchError(RuntimeError):
    """Two live proposals were wanted for one defect. Names the two exits.

    Subclasses nothing from ``nestor`` on purpose: this is the recipe's own
    vocabulary for a refusal the store made, and swallowing the store's
    exception would hide which guard fired.
    """


def propose(defect: str, patch: str, reason: str = "", *, origin: str = "",
            store=None) -> dict:
    """Propose ``patch`` as the fix for ``defect``. Always a draft.

    There is no ``verifier`` parameter and no way to reach ``status="sealed"``
    from this function. That is not an oversight to be helpful about later — the
    machine may propose and may not confirm, and a recipe that offered a
    shortcut past ``nestor.ui`` would be the covenant inverted.
    """
    try:
        return memory.add_pair(defect, patch, DOMAIN, DOMAIN, status="draft",
                               reason=reason, origin=origin,
                               store=store, matcher=MATCHER)
    except ConflictingDraftError as exc:
        raise RivalPatchError(
            f"{defect!r} already holds a different live proposal. Nestor keeps "
            f"one live row per defect, deliberately — see this module's "
            f"docstring. Two exits: revise() if this replaces the old proposal "
            f"(the old one is kept with its reason), or split the defect in two "
            f"if both are genuinely live, because a defect with two right "
            f"answers is usually two defects. There is no third exit and this "
            f"recipe does not offer one."
        ) from exc


def revise(defect: str, patch: str, reason: str, *, origin: str = "",
           store=None) -> dict:
    """Replace the live draft for ``defect``, keeping the old one as history.

    ``reason`` is required here and optional in :func:`propose`, which is the
    one place this recipe is stricter than the package. Abandoning a proposal
    without saying why throws away the only part of it that was worth keeping.
    """
    if not reason.strip():
        raise ValueError(
            "revise() needs a reason. The superseded proposal is kept as "
            "history and the reason is what makes that history worth having.")
    return memory.revise_draft(defect, patch, DOMAIN, DOMAIN, reason=reason,
                               origin=origin, store=store, matcher=MATCHER)


def split_hint(defect: str, *, store=None) -> str:
    """The sentence to read when :func:`propose` refused. Deliberately not code.

    Splitting a defect is an editorial judgment about what the defect *is*, and
    a function that did it automatically would be guessing at the thing a human
    is better placed to see. This returns the argument, not an action.
    """
    return (
        f"{defect!r} has two live answers. Before forcing one in, check whether "
        f"it is two defects: a description broad enough to admit two correct "
        f"patches is usually describing two problems, and splitting it gives "
        f"each one its own row, its own review and its own seal. This is "
        f"IDEAS.md §6.22 in another domain — the key says these are the same "
        f"source when they are not.")


def fix_for(defect: str, *, store=None, seal_threshold: Optional[float] = None):
    """The **verified** fix for this defect, or ``None``.

    Tier 1. Returns only a sealed row above the threshold, so a draft nobody
    checked can never come back from this call — which is the entire reason to
    put patches in Nestor rather than in a wiki.
    """
    return memory.best_sealed(defect, DOMAIN, DOMAIN, store=store,
                              matcher=MATCHER, seal_threshold=seal_threshold)


def candidates(defect: str, limit: int = 5, *, store=None) -> list[dict]:
    """Ranked matches, sealed **and** draft, for a human deciding what to read.

    The queue view rather than the serving view. `fix_for` is what a machine
    should call; this is what a person browsing looks at.
    """
    return memory.lookup(defect, DOMAIN, DOMAIN, limit=limit, store=store,
                         matcher=MATCHER, context_threshold=0.0)
