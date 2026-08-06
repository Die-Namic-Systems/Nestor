#!/usr/bin/env python3
"""This session's own build decisions, fed through Nestor. Reproduces the store
committed under ``docs/dogfood/2026-08-06-sandbox-build/``.

    python scripts/dogfood_sandbox_build.py                 # into a temp store
    python scripts/dogfood_sandbox_build.py --keep DIR      # leave it behind

The session: a sandboxed build of six open ``IDEAS.md`` entries in a cloud
container with no access to the operator's corpus (§6.8, §4.2, §4.4, §1.4,
§6.22, §6.12). Every choice below is one I made while building them, in the
words I would defend it in.

**Drafts only. No rejections.** ``dogfood_session_decisions.py`` writes both,
because the session it records contained a human's noes. This one does not.
``reject_match`` records a *person's* refusal, durably and signed, and a script
writing one on its own initiative is the machine confirming — the same violation
as sealing, in the direction ``assert_nothing_sealed`` cannot see. It counts
sealed rows; nothing counts whose "no" a rejection claims to be. The operator
made exactly two decisions in this session (which tranche of ideas to build, and
where the dogfood store should live); both appear below as drafts like
everything else, because a choice made in chat is not a signature.

So every row here is a proposal, and the queue at ``nestor.ui`` is where they
stop being proposals. Several of them deserve a no.
"""
from __future__ import annotations

import argparse

import dogfood_common

from nestor import memory

DOMAIN = "decision"
ORIGIN = "session:sandbox-thirsty-a7xqi7"

#: (question, commitment, why). ``reason`` is the N4 column — the one that
#: records why a yes was a yes, not only why a no was a no.
DECISIONS = [
    (
        "How is 'this container is not reading my Drive corpus' enforced?",
        "permissions.deny for mcp__Google_Drive, mcp__Gmail and mcp__Google_Calendar "
        "in the checked-in .claude/settings.json.",
        "Until that commit the guarantee was my own restraint, which is a condition "
        "checked by the caller guarding an action that can be reached around — the "
        "defect shape CLAUDE.md names and tells me not to add a condition for. "
        "permissions.deny is enforced by the harness before dispatch. Checked in "
        "rather than settings.local.json because the container is ephemeral: a local "
        "file dies with it and the next session starts unguarded.",
    ),
    (
        "Should the deny rule be proven by attempting a Drive read?",
        "No. The JSON and the rule syntax were verified; the dispatch path was not.",
        "That test's failure mode is the exact harm it tests for. It was confirmed "
        "anyway and for free: the session dropped 33 Google tools when the settings "
        "file changed, which is stronger evidence than a refused call would have been "
        "and cost nothing if it had gone wrong.",
    ),
    (
        "Where does the §6.8 schema-ready flag live?",
        "An attribute on a sqlite3.Connection subclass.",
        "sqlite3.Connection accepts neither attribute assignment nor weak references "
        "— both checked, both raise. That leaves a store-held set keyed by the "
        "connection, which pins it open and defeats _POOL_MAX, or by id(conn), which "
        "CPython reuses after a free: a recycled id marks a fresh connection as "
        "initialized and hands a caller a schema-less database. Subclassing makes the "
        "flag die exactly when the thing it describes dies.",
    ),
    (
        "Should init_db mark a connection schema-ready?",
        "No. Only memory_init sets the flag.",
        "init_db applies a strict subset — no _ensure_lineage_schema — so a connection "
        "it touched still owes the ALTERs a pre-lineage database needs. Marking ready "
        "there is the cheapest wrong version of the fix, which is why there is a guard "
        "test for it rather than a comment.",
    ),
    (
        "Was §6.8's 'measured once as noise for ingest' right?",
        "No. 0.556 -> 0.395 ms/op, -28.9%, and the entry is corrected in place.",
        "Probably true of an ingest where a model authors each draft — there the store "
        "is not the constraint and a schema replay hides behind a network round trip. "
        "What failed was the unqualified form. A ceiling measured before any code was "
        "written said 28-36% across four runs at two sizes, so the number was known to "
        "be worth having before there was a diff to defend.",
    ),
    (
        "Should the §6.25 init_db bug be fixed inside the §6.8 commit?",
        "No. Filed as its own entry, unfixed.",
        "It is a one-line fix and it is a correctness bug, and folding one into a "
        "performance commit is how a reviewer loses the ability to tell which half a "
        "regression came from. It was also reproduced on c68b8be first, so the claim "
        "that it predates the change is checked rather than assumed.",
    ),
    (
        "Should the README claim nobody else has solved AI verification?",
        "No. The clause was dropped and the omission recorded in IDEAS §4.2.",
        "IDEAS §4.2 proposed it, and it is a claim about every other system in the "
        "category that I cannot check and did not. The README asserts what regulated "
        "buyers are being asked, which is checkable, and stops. Recorded in place so "
        "the omission reads as a decision rather than an oversight.",
    ),
    (
        "Does §1.4's premise hold — is the data there for quorum?",
        "No. Concurrence is discarded; two verifiers agreeing leave one row and one "
        "ledger entry.",
        "Measured on a file-backed store with signing on. memory.py:374 writes only "
        "when the row is not already sealed or the target differs, so agreement "
        "satisfies neither arm and the stored row is returned as though the second "
        "person had sealed it. N-of-M cannot be computed from a history nobody wrote.",
    ),
    (
        "Should seal staleness be a decaying weight column?",
        "No.",
        "weight is written by every seal path, read by nothing in ranking, and absent "
        "from signing._message, which covers exactly [source_norm, target_text, "
        "verifier]. A decayed weight is unsigned mutable state anyone with write "
        "access resets to 1.0 while every signature still verifies. Worse, a decay "
        "multiplier withdraws a verified answer on a date nobody chose, leaving 'why "
        "did this stop being served' with no answer in the one place built to answer "
        "it.",
    ),
    (
        "Is a glossary identity lock a way to express the Nestor/nestor case?",
        "No. locks_in_text case-folds, so the lock fires on the common noun too.",
        "IDEAS §6.22 named it as the one mechanism that could express carry-through. "
        "Measured: {'Nestor': 'Nestor'} returns a lock for 'he was the nestor of the "
        "committee', which would put 'always render exactly as given' into the prompt "
        "for the only row in the pair that is a real translation. The glossary is a "
        "second mechanism with the same blindness, not an escape from it.",
    ),
    (
        "Does a carried string want a pair?",
        "No. Set membership — one column, no target, no language direction.",
        "The target can only ever equal the source, which is a table shape asking to "
        "drift, and carriage is not directional: a string carried en->ru is carried on "
        "the way back. Nestor -> Нестор is transliteration and does want a pair; "
        "Nestor -> Nestor is not a pair at all. This is what dissolves §6.22's first "
        "two questions rather than answering them.",
    ),
    (
        "Can Occam's razor become an exit code?",
        "No, and permanently.",
        "There is no mechanical test for 'simpler'. A check claiming to enforce "
        "parsimony would be a number standing in for a judgement, which is the exact "
        "substitution the detection kit is written to catch — a gate for #8 would be "
        "baloney about baloney detection. Writing that down is more useful than a "
        "metric nobody can defend.",
    ),
    (
        "Should each idea be built in its own git worktree?",
        "No, and I said so rather than performing it.",
        "I offered worktrees before checking what they would do here. EnterWorktree "
        "branches from origin/<default> by default, which would have dropped the "
        "deny-rules commit the whole sandbox rests on, and only one branch in this "
        "session can be pushed anyway. The isolation that was actually asked for is "
        "the corpus boundary, and that is structural. Per-idea worktrees would have "
        "been ceremony.",
    ),
]

#: Probes: the same question asked the way it would be asked in a month, to see
#: whether the memory would return the decision. Printed, never pinned — the
#: scores move with the matcher and pinning them fails on an improvement.
PROBES = [
    ("how do I stop it reading my drive?",
     "How is 'this container is not reading my Drive corpus' enforced?"),
    ("why not use id(conn) for the schema flag?",
     "Where does the §6.8 schema-ready flag live?"),
    ("should seals get weaker as they age?",
     "Should seal staleness be a decaying weight column?"),
    ("can the razor be a gate?",
     "Can Occam's razor become an exit code?"),
]


def main() -> int:
    ap = dogfood_common.add_output_args(
        argparse.ArgumentParser(description=__doc__.splitlines()[0]))
    args = ap.parse_args()

    with dogfood_common.opened(args.keep) as (root, store):
        dogfood_common.feed_drafts(store, DECISIONS, DOMAIN, ORIGIN)

        stats = dogfood_common.assert_nothing_sealed(store)
        print(f"fed  {len(DECISIONS)} decisions, 0 rejections (see the docstring)")
        print(f"     {stats['total']} pair(s): {stats['sealed']} sealed, "
              f"{stats['draft']} draft")

        print(f"\nwould the memory find these again? threshold "
              f"{memory.SEAL_THRESHOLD} — printed, not pinned")
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

        print("\nEvery row above is a draft. None of them is verified, and the "
              "queue at nestor.ui is where that changes.")
        if args.keep:
            print(f"store and ledger left in {root}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
