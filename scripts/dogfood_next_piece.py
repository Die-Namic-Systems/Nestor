#!/usr/bin/env python3
"""Ask Nestor about Nestor's own open findings, before writing the next one.

    python scripts/dogfood_next_piece.py

The fourth turn of the loop `IDEAS.md` §6.14, §6.18 and §6.19 describe: feed the
project's own record back through the thing the project builds, and see what it
gets wrong. The first three turns used the translation recipe on session
decisions. This one uses `recipes/patch_review.py` — defect description →
proposed fix — on the open entries in `IDEAS.md`, and asks the questions
somebody would actually type before picking up the next piece of work.

**It is a measurement, not an oracle.** §6.30 shipped `DefectMatcher` with a
7/13 rank-1 result and an explicit caveat: the probes were written by the same
person who wrote the defect descriptions, which flatters a matcher (§3.4 stage
2). This script is the second corpus that caveat asked for, and the caveat was
right — see §6.32.

Nothing here seals, and `fix_for` returns `None` for every question, on purpose:
everything a machine proposes is a draft, and a machine may not confirm. That is
the honest answer to "use Nestor to help write the next piece of Nestor" — it
can surface what was already decided; it cannot decide.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

# `nestor` is installed; `recipes` is not — it is the seam's "yours" row, kept
# deliberately out of [tool.setuptools.packages.find]. Running this from
# scripts/ puts scripts/ on sys.path and not the repo root, so the import below
# fails without this line. bench_patch_review.py does the same thing for the
# same reason.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import dogfood_common                                            # noqa: E402

from nestor.matcher import StringMatcher                         # noqa: E402
from recipes import patch_review                                 # noqa: E402

#: (§, defect, proposed fix) — verbatim from the open entries in IDEAS.md.
FINDINGS = [
    ("6.25",
     "init_db calls _ensure_unique_key, which creates an index over "
     "superseded_by, without calling _ensure_lineage_schema which adds that "
     "column",
     "Call _ensure_lineage_schema before _ensure_unique_key inside init_db."),
    ("6.27",
     "glossary._PATH is pathlib.Path('data/glossary.json'), relative, resolved "
     "against the process working directory on every call",
     "Resolve the glossary path absolutely, once, from an explicit setting."),
    ("6.29",
     "nestor/__init__ exports ConflictingSealError and RejectedPairError but "
     "not ConflictingDraftError, so the refusal that directs a caller to the "
     "third verb cannot be caught from the public surface",
     "Export ConflictingDraftError alongside the other two."),
    ("6.31a",
     "the store schema and the ledger format carry no version; migrations "
     "detect state by probing columns with PRAGMA table_info",
     "PRAGMA user_version in the store, argued separately from the ledger."),
    ("6.31b",
     "a warm pooled connection skips a migration introduced after it was "
     "opened, because memory_init returns early on schema_ready",
     "A schema generation that invalidates schema_ready when it moves."),
    ("6.28",
     "concurrent writers get OperationalError database is locked at roughly "
     "0.1 to 0.3 percent under twelve threads",
     "A store that takes concurrent writers; SqliteStore is not it."),
    ("1.4",
     "every seal is authoritative forever and one verifier is enough",
     "Staleness belongs in the curator queue, not in a decaying weight."),
    ("6.30",
     "the DefectMatcher recipe retrieves the right defect at rank 1 only 7 of "
     "13 times and cannot serve at any threshold",
     "It is a review queue, not a tier-1 server; do not wire fix_for in anger."),
]

#: (question somebody would type, the § that answers it). Written before the
#: scores were looked at — the point of the exercise is that these are *not*
#: paraphrases of the defect text, which is what §3.4 stage 2 says flatters a
#: matcher and what §6.30's own caveat asked somebody to check.
QUESTIONS = [
    ("I'm about to fix init_db raising on an old database — has this come up?", "6.25"),
    ("why does my glossary stop working when I run it as a service?", "6.27"),
    ("can I catch the error that tells me to call revise_draft?", "6.29"),
    ("do I need to restart after upgrading if the schema changed?", "6.31b"),
    ("should seals expire?", "1.4"),
    ("can I use the patch recipe to pick a fix automatically?", "6.30"),
]


def _rank1(scorer) -> list[tuple[bool, str, str]]:
    out = []
    for question, wanted in QUESTIONS:
        ranked = sorted(((scorer(question, defect), sec)
                         for sec, defect, _ in FINDINGS), reverse=True)
        out.append((ranked[0][1] == wanted, wanted, ranked[0][1]))
    return out


def main() -> int:
    ap = dogfood_common.add_output_args(
        argparse.ArgumentParser(description=__doc__.splitlines()[0]))
    args = ap.parse_args()

    with dogfood_common.opened(args.keep) as (root, store):
        for sec, defect, fix in FINDINGS:
            patch_review.propose(defect, fix, reason=f"IDEAS §{sec}",
                                 origin=f"ideas:{sec}", store=store)
        stats = dogfood_common.assert_nothing_sealed(store)
        print(f"{stats['total']} open findings loaded: {stats['draft']} draft, "
              f"{stats['sealed']} sealed\n")

        for question, wanted in QUESTIONS:
            served = patch_review.fix_for(question, store=store)
            top = patch_review.candidates(question, limit=1, store=store)
            got = (top[0]["pair"]["reason"].split("§")[-1] if top else "nothing")
            mark = "  " if got == wanted else "<-"
            print(f"{mark} want §{wanted:<6} got §{got:<6} "
                  f"served={served!r:<5}  {question}")

        print(f"\nfix_for served 0 of {len(QUESTIONS)}, and always will: every row "
              f"here is a\ndraft, and the queue at nestor.ui is where that changes.")

        # The comparison §6.30's caveat asked for: a corpus whose probes were not
        # written as paraphrases of the defects they retrieve.
        sm = StringMatcher()
        print(f"\nrank-1 on this corpus (n={len(QUESTIONS)}):")
        for name, scorer in [
            ("DefectMatcher (§6.30)", patch_review.MATCHER.score),
            ("StringMatcher (shipped default)",
             lambda a, b: sm.similarity(sm.normalize(a), sm.normalize(b))),
        ]:
            hits = _rank1(scorer)
            misses = ", ".join(f"§{w}->§{g}" for ok, w, g in hits if not ok)
            print(f"  {name:34} {sum(ok for ok, _, _ in hits)}/{len(QUESTIONS)}"
                  f"   missed: {misses or 'none'}")
        print("n is 6. One question is the whole difference, so this establishes "
              "that\n§6.30's advantage does not reproduce — not that it is "
              "reversed. See §6.32.")

        if args.keep:
            print(f"\nstore and ledger left in {root}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
