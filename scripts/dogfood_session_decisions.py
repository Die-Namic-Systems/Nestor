#!/usr/bin/env python3
"""Feed a working session's own decisions through Nestor. Reproduces IDEAS §6.14.

    python scripts/dogfood_session_decisions.py            # into a temp store
    python scripts/dogfood_session_decisions.py --keep DIR  # leave it behind

The content is one session's decisions — the ground-rule-2b work of
2026-08-05 (§6.13) — kept verbatim so the numbers in §6.14 can be re-derived
rather than taken on trust. `test_docs.py` says it best: a claim nobody
executes is a claim nobody maintains, and §6.14 makes three.

**Nothing here seals.** Every pair goes in as a draft with no verifier and no
signature, because the machine may propose and may not confirm. That is the one
thing this script asserts rather than prints: if a run ever produces a sealed
row, the covenant broke and the exit code says so. The seal queue belongs to a
human at `nestor.ui`, which is a sign-in.

The other two findings are printed, not asserted, and the reason is worth
stating. The re-worded recall numbers move with the matcher, so pinning floats
would fail on an improvement. The bundle's rejection count is a defect at time
of writing — asserting it stays broken would fail the build on the fix. Both
are measurements this script puts in front of you; §6.14 is where they are
argued.
"""
from __future__ import annotations

import argparse
import pathlib
import tempfile

from nestor import cascade, memory, portable, storage
from nestor.sqlite_store import SqliteStore

DOMAIN = "decision"

#: (question, commitment, why-yes). The `reason` column is N4 — Nestor always
#: recorded why a reviewer said no, never why they said yes.
DECISIONS = [
    (
        "Where is Nestor's output-voice rule defined?",
        "nestor/engine.py VOICE_RULE — one module-level constant, referenced and never retyped.",
        "It existed twice — prose in the module docstring and a retyped literal inside "
        "ClaudeEngine._system — and was executed by neither. test_docs.py had already named "
        "that failure mode for the README: a claim nobody executes is a claim nobody "
        "maintains. Two copies and no check is not redundancy, it is a pending disagreement.",
    ),
    (
        "Which layer owns ground rule 2b — the engine class, or the tier?",
        "The tier. engine.system_prompt is module-level and is the single prompt builder "
        "for every model-backed engine.",
        "The engine slot is pluggable by design: get_engine dispatches, and OfflineEngine is "
        "documented as the eventual local-model slot. A rule owned by one class is a "
        "guarantee the next engine walks around — TODO.md's shape, caught before it bit "
        "rather than after.",
    ),
    (
        "Should the voice rule be a parameter of the prompt builder?",
        "No. There is no voice= argument and no way to compose the prompt without the rule.",
        "The only reason to make it optional would be to turn it off.",
    ),
    (
        "How do we stop a future engine handing a model a prompt built elsewhere?",
        "An AST gate over nestor/*.py: every `system=` keyword argument in a call must be "
        "system_prompt(...).",
        "It catches the engine nobody has written yet — the second path in that TODO.md "
        "warns about. Proven against a RogueEngine mutation calling messages.create with "
        "its own string; the gate was the only test that failed.",
    ),
    (
        "How is 'drafts are always marked unverified' enforced?",
        "By shape. Draft carries no state, verified or seal_sig field, so an engine has "
        "nothing to claim verification with; cascade.Passage owns state.",
        "This half of 2b was already true and written down nowhere. It is not a convention "
        "the engine is trusted to honour — it is the only shape available to it, and the "
        "test pins that no such field appears.",
    ),
    (
        "Should a pinning test import the constant it pins?",
        "No. Mirror the literal in the test file.",
        "Importing would make the pin true by construction and therefore vacuous. Changing "
        "what a model is told about whose voice to use should require two files in one "
        "reviewed diff — test_ledger_kinds.py set that precedent for LEDGER_KINDS.",
    ),
    (
        "Should nestor/engine.py's CLAUDE_MODEL be changed in this work?",
        "No. Left at claude-opus-4-8 — a live, supported model one generation behind "
        "claude-opus-5.",
        "Checked rather than assumed: it is neither retired nor deprecated. Changing a "
        "product's model is a behaviour decision for the operator, not cleanup, and it is "
        "outside what a ground-rule-2b change implies.",
    ),
    (
        "What does 'work on the persona' mean in this repo?",
        "Nestor's persona — the output-voice rule cited as ground rule 2b in "
        "nestor/engine.py — not the agent's persona for this seat.",
        "The operator chose this from four options when the reading was genuinely "
        "ambiguous. Recorded as a DRAFT rather than a seal: a choice made in conversation "
        "is not a signature, and writing verifier='rudi' here would be the machine "
        "confirming on a human's behalf.",
    ),
]

#: (question, rejected alternative, why-no, reopen_when). Empty reopen_when is
#: NEVER; non-empty is NOT YET, and names what reopens it (N5).
REJECTIONS = [
    (
        "How do we stop a future engine handing a model a prompt built elsewhere?",
        "A regex over nestor/*.py source lines for `system=`.",
        "It flagged the phrase `system=` inside a docstring about the rule — prose about "
        "the rule tripping the check for the rule. 'Is this a keyword argument in a call' "
        "is a syntax question, and the syntax tree answers it exactly where a regex has to "
        "keep guessing which quotes it is inside.",
        "",
    ),
    (
        "How do we revert a mutation while proving a test gate catches it?",
        "git checkout <file>",
        "It reverts to HEAD, discarding uncommitted work. It destroyed the very edits under "
        "test and silently invalidated three of the four gate proofs — the control run "
        "still 'passed' because the baseline had been reverted too. Use a backup copy.",
        "",
    ),
    (
        "Where do the numbered ground rules live?",
        "Write the full numbered ground-rule set into this repo.",
        "Only 2b is cited here — `grep -rn 'ground rule'` returns exactly one docstring. "
        "Inventing rules 1, 2a and 3 to fill out the set would be fabrication. 2b's text is "
        "the half Nestor is entitled to own, and that half is now defined in VOICE_RULE.",
        "the operator decides to carry the fleet's ground rules home, the way "
        "docs/decision-memory.md was carried home from the SAFE store",
    ),
    (
        "Should nestor/engine.py's CLAUDE_MODEL be changed in this work?",
        "Bump CLAUDE_MODEL to claude-opus-5 as part of this change.",
        "Out of scope for ground rule 2b, and not free: on Opus 5 thinking is on by default, "
        "and max_tokens caps thinking plus response text together. translate() passes "
        "max_tokens=4096 with no thinking parameter, so the same call could start "
        "truncating mid-translation.",
        "the operator decides to migrate the engine model — re-check max_tokens headroom "
        "before the swap, not after",
    ),
]

#: Re-worded probes and the row each one is *trying* to reach. The point of
#: naming the target is that "did it retrieve anything" is the wrong question —
#: §6.14's finding is that two of these rank a DIFFERENT decision first.
PROBES = [
    ("Should the voice rule be a parameter of the prompt builder?",
     "Should the voice rule be a parameter of the prompt builder?"),
    ("who owns ground rule 2b, the class or the tier?",
     "Which layer owns ground rule 2b — the engine class, or the tier?"),
    ("can callers turn off the voice rule?",
     "Should the voice rule be a parameter of the prompt builder?"),
    ("why was the model id left alone?",
     "Should nestor/engine.py's CLAUDE_MODEL be changed in this work?"),
]


def feed(store) -> None:
    for question, commitment, reason in DECISIONS:
        memory.add_pair(question, commitment, DOMAIN, DOMAIN, status="draft",
                        reason=reason, origin="session:getting-settled-9p41pb",
                        store=store)
    for question, alternative, reason, reopen_when in REJECTIONS:
        memory.reject_match(question, DOMAIN, DOMAIN, target_text=alternative,
                            reason=reason, reopen_when=reopen_when, store=store)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", metavar="DIR",
                    help="write the store and ledger here instead of a temp dir")
    args = ap.parse_args()

    tmp = None
    if args.keep:
        root = pathlib.Path(args.keep)
        root.mkdir(parents=True, exist_ok=True)
    else:
        tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(tmp.name)

    try:
        cascade.set_ledger_path(root / "ledger.jsonl")
        store = SqliteStore(str(root / "nestor.db"))
        storage.set_store(store)
        store.memory_init()
        feed(store)

        stats = memory.stats(store=store)
        print(f"fed  {len(DECISIONS)} decisions, {len(REJECTIONS)} rejected alternatives")
        print(f"     {stats['total']} pair(s): {stats['sealed']} sealed, {stats['draft']} draft")

        # The one assertion. Everything else here is a measurement; this is the
        # covenant, and a run that seals has broken it.
        assert stats["sealed"] == 0, (
            f"{stats['sealed']} sealed row(s) — this script proposes and must never "
            f"confirm. A seal belongs to a human at nestor.ui (ground rule: the machine "
            f"may propose and may not confirm).")

        print(f"\nre-worded recall, threshold {memory.SEAL_THRESHOLD} "
              f"(IDEAS §6.14 — moves with the matcher, so it is printed, not pinned)")
        for query, wanted in PROBES:
            rows = memory.lookup(query, DOMAIN, DOMAIN, limit=8, store=store,
                                 context_threshold=0.0)
            top = rows[0] if rows else None
            hit = next((r for r in rows if r["pair"]["source_text"] == wanted), None)
            score = f"{hit['similarity']:.4f}" if hit else "not retrieved"
            served = "serves" if hit and hit["similarity"] >= memory.SEAL_THRESHOLD else "—"
            rank1 = "itself" if (top and hit and top["pair"]["id"] == hit["pair"]["id"]) \
                else f"A DIFFERENT DECISION ({top['similarity']:.4f})" if top else "nothing"
            print(f"  {score:>13}  rank-1: {rank1:<34}  {served:<6}  {query!r}")

        bundle = portable.export_bundle(store)
        print(f"\nexport: {bundle['counts']['pairs']} pair(s), "
              f"{bundle['counts']['rejections']} rejection(s) — from a store holding "
              f"{len(REJECTIONS)}")
        # Was 0 of 4 when this script was written: export walked the exported
        # pairs, and a rejection naming no pair_id has no pair to be walked
        # from (IDEAS §6.14). Fixed in §6.15 by collecting rejections by domain.
        if bundle["counts"]["rejections"] < len(REJECTIONS):
            print(f"  ! only {bundle['counts']['rejections']} of {len(REJECTIONS)} "
                  f"rejections travelled — the §6.15 fix has regressed, or this store "
                  f"cannot list rejections by domain")

        if args.keep:
            print(f"\nstore and ledger left in {root}")
        return 0
    finally:
        if tmp is not None:
            tmp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
