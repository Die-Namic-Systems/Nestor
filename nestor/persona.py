"""How Nestor speaks when Nestor is the speaker — and only then.

**Not how a translation sounds.** That is ground rule 2b and it lives in
:data:`nestor.engine.VOICE_RULE` — read it there. It is deliberately not
restated here, because ``tests/test_engine.py::test_the_rule_is_written_once``
pins that sentence to exactly one place in the package and this docstring was
its second occurrence within a minute of being written. Nothing here
may reach :func:`nestor.engine.system_prompt`;
``tests/test_persona.py::TestTheEngineCannotReachThePersona`` fails the build if
it can. The two voices share a word and are different objects, and conflating
them is how a translation memory starts sounding like a chatbot.

What this module governs is the other voice: the one Nestor uses to say *I do
not know*, *a machine wrote this*, *nobody has checked it*. That voice already
existed. It was written across :mod:`nestor.answer` as literals, consistent by
luck, and — this is the part worth keeping in mind — it was noticeably more
alive in the **comments** than in the strings, because the comments were
addressed to reviewers and the strings only to users.

**Why it is worth a module at all.** By volume Nestor's output *is* refusal. A
sealed hit is instant and silent; that is the success case and nobody reads it.
What a curator reads, hundreds of times a day, is a machine declining. The
argument for taking that seriously is already in the tree, in
:func:`nestor.portable._canonical`: *"an integrity check that fails on a
lossless round-trip trains people to ignore it, which is worse than not having
one."* A refusal that reads as officious trains people to route around it, on
exactly the same mechanism. The register is load-bearing, which is also why
there is no ``warmth=`` knob — the only reason to make it optional would be to
turn it off, which is :func:`~nestor.engine.system_prompt`'s own rule about
``VOICE_RULE``.

**The one rule inside the rule.** A persona styles a refusal and may not soften
the fact of one. Every act below is a *not-served* outcome, so the facts a
rendering interpolates are supplied by the caller and there is no field here
that could assert otherwise. `Persona` cannot say something was verified,
because nothing gives it the ability to.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

#: Acts whose subject is the **machine's own shortfall**. These may be dry and
#: self-deprecating: the machine is the junior party — it may propose and may
#: not confirm — so it is the one that can be laughed at.
MACHINE_ACTS = frozenset({
    "below_threshold",     # scored everything, best is under the bar
    "nothing_sealed",      # above the bar, and only drafts up there
    "nothing_in_domain",   # no candidate scored at all
})

#: Acts whose subject is **a human's decision or signature**. Plain, always.
#: When two people assert different things, when a curator's "no" is being
#: honoured, when a signature does not verify — nothing is funny, and a wry
#: sentence would be reporting someone else's judgment in a register they did
#: not choose.
HUMAN_ACTS = frozenset({
    "forged_seal",         # says sealed; the signature disagrees
    "rejected_outright",   # memory.reject_pair — wrong in its own right
    "suppressed",          # memory.reject_match — refused for this query
})

#: Every act in which Nestor speaks as itself. Closed, and pinned the way
#: :data:`nestor.cascade.LEDGER_KINDS` is pinned, for the same reason: add a
#: member and its first caller in the same change, with the mirroring test in
#: ``tests/test_persona.py``. An unpinned act is not a new way of speaking, it
#: is a string that bypassed review.
SPEECH_ACTS = MACHINE_ACTS | HUMAN_ACTS

#: Substrings that make a refusal *read* as one. Every rendering must contain at
#: least one. The styling may change; the negation may not disappear into it.
#: This is the guard a ``warmth=`` knob would have needed, and the reason there
#: is no knob.
NEGATIONS = ("nothing", "not ", "no ", "below", "never", "nobody",
             "unverified", "rejected", "suppress", "does not")


class PersonaError(ValueError):
    """A persona that is incomplete, over-complete, or cannot render an act.

    Never a fallback. A persona missing one act and quietly falling back to
    another voice for that one string is worse than no persona: it looks like
    it works, and the act that lost its voice is the act nobody tested. Same
    rule as :func:`nestor.storage.supports_rejection` and its siblings — a
    capability is all-or-nothing because a partial one is indistinguishable
    from a working one until it matters.
    """


@dataclass(frozen=True)
class Persona:
    """One rendering per speech act. Style only.

    There is deliberately no ``state``, ``served`` or ``confidence`` field, for
    the same reason :class:`nestor.engine.Draft` has none: the honest part is
    composed by the caller and is not available here to be softened. A persona
    chooses the words around *nothing verified matches*. It is given no way to
    say that something does.

    ``renderings`` maps act → callable taking the act's facts as keyword
    arguments and returning the sentence. Callables rather than format strings
    because two of the six acts are conditional on a count — the display-slice
    note appears only when something was sliced — and a format string that has
    to branch is a template language nobody asked for.
    """

    name: str
    renderings: Mapping[str, Callable[..., str]]

    def __post_init__(self) -> None:
        missing = SPEECH_ACTS - set(self.renderings)
        unknown = set(self.renderings) - SPEECH_ACTS
        if missing or unknown:
            raise PersonaError(
                f"persona {self.name!r} is not complete: "
                f"missing {sorted(missing)}, unknown {sorted(unknown)}. "
                f"A persona renders every act in persona.SPEECH_ACTS or it is "
                f"not installed — there is no per-act fallback, because the "
                f"act that silently fell back is the one nobody would test."
            )

    def say(self, act: str, /, **facts) -> str:
        """Render one act. The only way to get a sentence out of a persona.

        The result is checked against :data:`NEGATIONS` here rather than at
        construction, because a rendering is a callable and its output depends
        on the facts: a sentence that negates at one count and not at another
        is exactly the failure mode this catches. That check costs a substring
        scan per refusal, on a path that has already scanned the whole domain.
        """
        try:
            render = self.renderings[act]
        except KeyError:
            raise PersonaError(
                f"{act!r} is not a speech act. Nestor speaks as itself only in "
                f"{sorted(SPEECH_ACTS)}; add a member and its first caller in "
                f"the same change, with the pinning test."
            ) from None
        said = render(**facts)
        if not any(n in said.lower() for n in NEGATIONS):
            raise PersonaError(
                f"persona {self.name!r} rendered {act!r} with no negation in "
                f"it, so a refusal reads as though something was served: "
                f"{said!r}. Every act here is a not-served outcome."
            )
        return said


# --------------------------------------------------------------- Nestor's ----
# Reconstructed from the literals that were already in `answer.py` rather than
# invented. If these read like the surrounding error messages, that is the
# test, not a coincidence.
#
# The generative rule, taken from the comments in `answer.py` that already
# worked: **be exact about your own failure and the humour is a byproduct.**
# "The previous fix for this sentence reproduced its own bug one line lower" is
# not a joke construction; it is an unflattering, precise description, which is
# why it lands and why it will not age. Wordplay dies on the second read and
# these sentences are read hundreds of times.
#
# The second rule, which the writing produced rather than the design: a pointed
# clause must be true across the **whole** range its facts can take. An early
# draft of `below_threshold` read "close enough to be tempting, which is why it
# is not served" — a good sentence, and false at 0.11. Both clauses below are
# about the BAR, not about this row, which is what makes them true at every
# score. `TestRangeSafety` renders each act at both ends and forbids the four
# words that were the temptation.


def _below_threshold(*, count: int, best: float, threshold: float,
                     shown: int) -> str:
    # `(showing N)`, not `(N scored, showing M)`: the count is already the
    # second word of the sentence, and repeating it read as two numbers that
    # happened to agree.
    more = f" (showing {shown})" if shown < count else ""
    return (f"closest of {count} candidate(s) is {best}, below {threshold}"
            f"{more} — the bar exists because a near miss served as verified "
            f"is worse than no answer")


def _nothing_sealed(*, best: float, threshold: float, kinds: str) -> str:
    # The closing clause names WHICH of the two refusals this is. Without it a
    # reader who has just seen `below_threshold` assumes the score is the
    # problem and goes looking for a lower bar, when the score is fine and the
    # missing thing is a signature.
    #
    # It says nothing about who wrote the candidates, deliberately: `kinds` can
    # be 'draft' or 'rejected' or both, and a sentence true of one is a lie
    # about the other.
    return (f"matched at {best}, at or above {threshold} — but nothing sealed; "
            f"above the bar there is only {kinds}. Close is not the problem "
            f"here, unverified is")


def _nothing_in_domain(*, source_lang: str, target_lang: str) -> str:
    # The opening phrase is load-bearing beyond this sentence: four negative
    # assertions in `tests/test_findings_2026_08_05.py` are pinned to it, and
    # rewording it would leave all four passing while checking nothing.
    #
    # The second half takes the blame. "nothing matched at all", alone, leaves
    # the reader wondering whether the question was the problem. It usually was
    # not, and an empty store is the likelier cause. That is the real principle
    # under "at the machine's expense": absorb the awkwardness of an empty
    # result rather than leaving it where the user will pick it up.
    return (f"nothing in this domain matched at all — no candidate scored, "
            f"which usually means {source_lang}→{target_lang} is empty rather "
            f"than that the question was strange")


def _forged_seal(*, count: int, threshold: float) -> str:
    # Plain. A signature that does not verify is the most alarming thing that
    # can be true of a query, and it is a statement about a human's seal.
    return (f"{count} match(es) at or above {threshold} say sealed but their "
            f"signature does not verify — a forged seal, or one made with a "
            f"different key")


def _rejected_outright(*, count: int) -> str:
    # Plain. This is a curator's judgment being honoured, not a machine's miss.
    return (f"{count} pair(s) matching this query were rejected outright "
            f"(memory.reject_pair) — the mapping is wrong in its own right, so "
            f"it is never served or offered again")


def _suppressed(*, count: int) -> str:
    # Plain, same reason. `count` is RECORDS — how many "no"s were recorded,
    # not how many rows they suppressed; see answer._classify.
    return (f"nothing left to match — {count} recorded rejection(s) for this "
            f"query suppress every candidate that would otherwise have been "
            f"scored")


NESTOR = Persona(name="nestor", renderings={
    "below_threshold": _below_threshold,
    "nothing_sealed": _nothing_sealed,
    "nothing_in_domain": _nothing_in_domain,
    "forged_seal": _forged_seal,
    "rejected_outright": _rejected_outright,
    "suppressed": _suppressed,
})


# ------------------------------------------------------------------ seam ----

_persona: Persona = NESTOR


def set_persona(p: Persona) -> None:
    """Install the process-wide persona used when no explicit one is passed.

    The same seam as :func:`nestor.storage.set_store` and
    :func:`nestor.memory.set_matcher`, deliberately — and deliberately *not* a
    ``data/persona.json``. `IDEAS.md` §6.22 measured what that costs: the
    glossary is the one place Nestor can say "do not translate this", and
    ``grep glossary`` across ``portable.py``, ``cascade.py`` and
    ``sqlite_store.py`` returns 0, 0, 0 — not bundled, not ledgered, not
    sealable. One ungoverned data plane is a finding; two would be a habit.

    A persona installed by a host is that host's to govern, exactly as an
    injected :class:`~nestor.storage.Storage` is. What Nestor guarantees is
    that it is complete (:class:`PersonaError`) and that every sentence it
    produces still reads as a refusal (:data:`NEGATIONS`).
    """
    global _persona
    if not isinstance(p, Persona):
        raise PersonaError(
            f"expected a persona.Persona, got {type(p).__name__} — the "
            f"completeness and negation checks live on that class and a "
            f"duck-typed stand-in would skip both."
        )
    _persona = p


def get_persona(p: Persona | None = None) -> Persona:
    """Resolve the persona to use — an explicit argument wins, else the global."""
    return p if p is not None else _persona
