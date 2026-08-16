"""``nestor init`` — the guided, honest first run (IDEAS.md §7.5).

The raw materials for a first five minutes were already here: a ``nestor``
console entry point, ``nestor demo``'s seeded store, a tested README quick
start. None of the three is an actual walkthrough. ``nestor demo`` hands a
stranger *somebody else's* memory to look at (``rita``'s, sealed in advance);
this module hands them their own, one guided step at a time — ask a
question, watch the matcher say nothing is verified yet (because nothing is,
on a fresh store), and propose a first decision.

**The one thing this cannot do, on purpose.** Nestor's covenant is propose,
never confirm (``docs/agent-guide.md``), and only a human sets a seal, only by
signing in at ``nestor ui``. A welcome wizard is not exempt from that — one
that quietly sealed its own demo row to feel finished would be lying about
the exact fact the product exists to keep honest, on the one screen a
newcomer is most likely to take at face value. So the walk below has exactly
one write, :meth:`nestor.decision.DecisionMemory.propose`, which the
covenant already makes *incapable* of writing anything but a draft — there is
no ``verifier=`` or ``status=`` parameter on :func:`run` for a caller to pass,
scripted or not, and ``tests/test_onboarding.py`` pins both the row it leaves
and the shape of the function that leaves it.

Interactive by default — ``input()``-shaped prompts read from ``in_stream``
and written to ``out`` — but every step is a plain function over those two
streams and a handful of strings, so a test drives the whole thing with
:class:`io.StringIO` and never touches a TTY. ``yes=True`` (``nestor init
--yes`` on the command line) skips the prompts and fills in a small built-in
example instead, so a scripted run is complete and non-interactive without
needing to fake a stream at all.
"""
from __future__ import annotations

import sys
from typing import IO, Optional

from . import seed as seed_mod
from .answer import match as answer_match
from .decision import DecisionMemory
from .storage import Storage

#: The domain a proposal lands in — the same tag ``nestor decision check``
#: reads (docs/decision-memory.md N8: one domain, ridden in both language
#: tags identically).
DOMAIN = "decision"

#: What a prompt or ``--yes`` falls back to when nothing else was typed.
#: Deliberately small and deliberately not about Nestor's own governance —
#: the wizard's job is to show the *shape* of a decision, not to make one for
#: real, so the example reads as an example rather than as a stray policy row
#: buried in a demo store.
DEFAULT_QUESTION = "Should this team review PRs same-day or next-day?"
DEFAULT_COMMITMENT = "Same-day when the diff is under 200 lines; next-day above that."
DEFAULT_RATIONALE = ("a first decision, walked through by `nestor init` so the "
                     "pattern is on the record before the real ones start")


def already_initialized(store: Storage) -> bool:
    """True when ``store`` already holds memory.

    The guided walk is for a first run. Writing a second onboarding draft
    into a store that already has real content is the exact surprise write
    ``nestor demo`` already refuses for the same reason
    (:func:`nestor.seed.is_empty`) — a filename is not a promise, and neither
    is "this must be the first time".
    """
    return not seed_mod.is_empty(store)


def _prompt(out: IO[str], in_stream: IO[str], text: str, default: str) -> str:
    """One line from ``in_stream``, falling back to ``default`` on a blank
    line or on EOF (a closed pipe, or a stream a test never fed anything)."""
    out.write(text)
    out.flush()
    line = in_stream.readline()
    if not line:                  # EOF: a script, a closed pipe, an empty StringIO
        out.write("\n")
        return default
    line = line.rstrip("\n").strip()
    return line or default


def welcome(out: IO[str]) -> None:
    out.write(
        "Nestor — a guided first run.\n\n"
        "Three steps: ask something, watch nothing verify it (nothing has, "
        "yet), then propose your first decision as a draft. The draft is as "
        "far as this wizard goes — sealing it is a human's signature, made "
        "by hand, in `nestor ui`, and nothing here can do that for you.\n\n"
    )


def ask_step(store: Storage, question: str, out: IO[str]) -> dict:
    """Run ``question`` through the matcher and print what it finds.

    Goes through :func:`nestor.answer.match` — the same bare seam every other
    domain is checked with — over the ``decision`` domain, so what a
    newcomer sees here is the real mechanic and the real persona voice
    (:mod:`nestor.persona`), not a mocked-up stand-in for either.
    """
    result = answer_match(store, question, DOMAIN, DOMAIN)
    if result["served"]:
        out.write(f"  already answered: {result['target']!r} "
                  f"(sealed by {result['verifier'] or 'a human'})\n")
    else:
        out.write(f"  {result['reason']}\n")
    return result


def propose_step(store: Storage, question: str, commitment: str, rationale: str,
                 out: IO[str]) -> dict:
    """The one write: a draft, via :meth:`DecisionMemory.propose`.

    Nothing above this function's own two lines constructs a ``DecisionMemory``
    or calls ``memory.add_pair`` directly, and this is the only call site in
    the module — the covenant is enforced by there being exactly one place
    that writes, and that place accepting no ``verifier``/``status`` of its
    own to pass through.
    """
    dm = DecisionMemory(store, domain=DOMAIN)
    row = dm.propose(question, commitment, rationale=rationale, origin="nestor init")
    out.write(
        f"  proposed — status={row['status']!r}, verifier={row.get('verifier', '') or '(none)'!r} "
        f"(a draft; nothing here can write 'sealed' or a name)\n")
    return row


def finale(out: IO[str], db_path: str) -> None:
    out.write(
        "\nThat is a draft, not a decision — a machine proposed it, same as "
        "any other row Nestor writes on its own. Nobody has checked it.\n\n"
        f"The seal is yours to set, by hand: open `nestor ui --db {db_path}`, "
        "sign in, and look at what you just proposed. If it still reads "
        "right, seal it there — nowhere else, because nowhere else is a "
        "person checking anything.\n")


def run(store: Storage, *, db_path: str = "", out: Optional[IO[str]] = None,
       in_stream: Optional[IO[str]] = None, yes: bool = False,
       question: Optional[str] = None, commitment: Optional[str] = None,
       rationale: Optional[str] = None) -> dict:
    """The whole guided walk: ask, watch it resolve, propose. Never seals.

    ``yes=True`` (or supplying ``question``/``commitment``/``rationale``
    directly) skips the interactive prompts for that field; the built-in
    example fills whatever is still unset, so ``run(store, yes=True)`` is a
    complete, non-interactive pass — the mode a test or a CI job drives
    without a TTY, and the one ``nestor init --yes`` uses on the command
    line. There is deliberately no parameter here that could name a
    verifier or a status: the only row this ever writes is a draft, decided
    by :func:`propose_step` rather than by anything a caller passes in.

    Returns a small report (``question``, ``commitment``, ``rationale``,
    ``matched_before``, ``pair_id``, ``status``) a test can assert on without
    parsing the transcript. ``status`` is always ``"draft"``.
    """
    out = out if out is not None else sys.stdout
    in_stream = in_stream if in_stream is not None else sys.stdin

    welcome(out)

    q = question if question is not None else (
        DEFAULT_QUESTION if yes else
        _prompt(out, in_stream, f"A question to ask [{DEFAULT_QUESTION}]: ",
               DEFAULT_QUESTION))
    out.write(f"\nasking: {q!r}\n")
    match_result = ask_step(store, q, out)

    c = commitment if commitment is not None else (
        DEFAULT_COMMITMENT if yes else
        _prompt(out, in_stream, f"\nWhat should the answer be [{DEFAULT_COMMITMENT}]: ",
               DEFAULT_COMMITMENT))
    r = rationale if rationale is not None else (
        DEFAULT_RATIONALE if yes else
        _prompt(out, in_stream, f"Why, one line [{DEFAULT_RATIONALE}]: ",
               DEFAULT_RATIONALE))

    out.write("\nproposing your first decision as a draft:\n")
    proposed = propose_step(store, q, c, r, out)

    finale(out, db_path or "data/nestor.db")

    return {"question": q, "commitment": c, "rationale": r,
           "matched_before": match_result["served"],
           "pair_id": proposed["id"], "status": proposed["status"]}
