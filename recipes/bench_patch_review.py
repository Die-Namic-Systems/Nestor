#!/usr/bin/env python3
"""Does `DefectMatcher` actually retrieve a defect from a re-worded description?

    python recipes/bench_patch_review.py

Two halves, and the second one is the covenant rather than a number.

**Half one — ranking.** Thirteen real defect→fix pairs from this repository's
own history, each probed with a sentence somebody might type a month later.
Compared against `StringMatcher` (the shipped default, character difflib) and
`TokenJaccard` (bench/token_matchers.py, unweighted token sets), so the claim
"identifier weighting helps" is a measurement rather than a design intention.

The weight curve is printed in full. ``IDENT_WEIGHT`` was fixed at 3.0 before
any of this ran, and the curve is here so that choice can be judged — not so a
better one can be quietly substituted after the fact. If some other weight wins,
that is a finding to write down, not a constant to edit.

**Half two — the store.** All thirteen proposed through `recipes.patch_review`
into a real store, then `fix_for` asked for each. It returns ``None`` thirteen
times, and that is the point of the exercise: nothing here has been checked by
a person, so nothing here is served as verified.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from bench.token_matchers import TokenJaccard                    # noqa: E402
from nestor import cascade, memory                               # noqa: E402
from nestor.matcher import StringMatcher                         # noqa: E402
from nestor.sqlite_store import SqliteStore                      # noqa: E402
from recipes import patch_review                                 # noqa: E402

#: (defect, fix, probe). Every row is a real entry from IDEAS.md or TODO.md;
#: the probe is the same defect as somebody would ask about it later, without
#: the original wording in front of them.
CORPUS = [
    ("memory_init replays the whole idempotent schema script on every call, "
     "once per public function in nestor.memory",
     "A schema_ready flag on a sqlite3.Connection subclass, set by memory_init "
     "and deliberately not by init_db.",
     "why is every add_pair running CREATE TABLE again?"),

    ("init_db creates an index over superseded_by without running the lineage "
     "migration that adds the column",
     "Call _ensure_lineage_schema before _ensure_unique_key inside init_db.",
     "opening an old database with init_db raises no such column"),

    ("a second verifier sealing an already-sealed pair with the same target "
     "writes nothing, appends nothing and raises nothing",
     "Append a countersign entry to the ledger naming the second verifier, "
     "leaving the row and the serving path untouched.",
     "why did the other reviewer's seal disappear?"),

    ("glossary.json is resolved against the process working directory on every "
     "call, so term locks depend on where the process was launched",
     "Resolve the glossary path absolutely, once, from an explicit setting "
     "rather than from os.getcwd() at call time.",
     "term locks stop applying when I run it as a service"),

    ("add_pair over an existing draft with a different target wrote nothing and "
     "returned the stored proposal to a caller that had proposed something else",
     "Raise ConflictingDraftError, and add revise_draft as the third verb so a "
     "changed mind has somewhere to go.",
     "my proposal did not land and I got back somebody else's"),

    ("two threads sealing the same phrase at once each found nothing and each "
     "inserted, leaving two sealed rows for one source",
     "A partial unique index on (source_norm, source_lang, target_lang) over "
     "live rows, so the store cannot hold the second one.",
     "concurrent seals produce two live rows for one source"),

    ("an import could revive a pair a human had rejected, because rejection "
     "lived in add_pair and the import path walked around it",
     "Move the rejection check into the one write path that cannot be "
     "bypassed.",
     "importing a bundle brought back something we had said no to"),

    ("a seal could be made without being ledgered, because the seal audit lived "
     "in the callers and add_pair did not have it",
     "Audit the seal inside add_pair, where every seal path passes.",
     "there is a sealed row with nothing about it in the chain"),

    ("ledger verification runs once per process, so a long-lived UI never "
     "re-checks the chain it is serving from",
     "TTL'd re-verification on append, with the interval read from the "
     "environment and refused if malformed.",
     "a server that has been up for days never revalidates the audit trail"),

    ("lookup scores every row in the corpus, so the case where nothing matches "
     "costs as much as the case where something does",
     "A lossless prefilter using difflib's own length bounds, so candidates "
     "that cannot reach the threshold are never scored.",
     "the absent case is as expensive as a hit"),

    ("rejection_limit defaulted to limit, and because pairs read newest-first "
     "and rejections oldest-first the two windows were disjoint under any cap",
     "Two walks, each bounded by construction, unioned — not a third filter "
     "over the second.",
     "no pair-bound rejection travelled in the exported bundle"),

    ("a refusal message said the match was close enough to be tempting, which "
     "is true at 0.71 and false at 0.11",
     "Make the claim about the rule rather than about this case, so it holds "
     "across every value the sentence can take.",
     "the refusal wording is wrong when the score is very low"),

    ("a connection per operation left file descriptors to the cyclic collector, "
     "which runs a UI out of them long before a collection happens",
     "A bounded pool of idle connections, with anything borrowed beyond the "
     "ceiling closed on return rather than accumulated.",
     "the browser surface runs out of file descriptors"),
]


class _Weighted:
    """DefectMatcher at an arbitrary identifier weight, for the curve."""

    def __init__(self, weight: float) -> None:
        self.weight = weight

    def score(self, a, b) -> float:
        old = patch_review.IDENT_WEIGHT
        patch_review.IDENT_WEIGHT = self.weight
        try:
            return patch_review.MATCHER.score(a, b)
        finally:
            patch_review.IDENT_WEIGHT = old


def rank(matcher, probe: str) -> tuple[int, float, float]:
    """(rank of the correct defect, its score, the top score) for one probe."""
    idx = [p for _, _, p in CORPUS].index(probe)
    scorer = getattr(matcher, "score", None) or matcher.similarity
    scores = [scorer(probe, defect) for defect, _, _ in CORPUS]
    mine = scores[idx]
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    return order.index(idx) + 1, mine, scores[order[0]]


def evaluate(name: str, matcher) -> tuple[str, int, float, float]:
    at1 = 0
    total = 0.0
    margin = 0.0
    for _, _, probe in CORPUS:
        r, mine, top = rank(matcher, probe)
        at1 += (r == 1)
        total += mine
        margin += mine - top
    n = len(CORPUS)
    return name, at1, total / n, margin / n


def main() -> int:
    print(f"{len(CORPUS)} defect->fix pairs from this repo, each probed with a "
          f"re-worded description.\n")

    rows = [
        evaluate("StringMatcher (shipped default)", StringMatcher()),
        evaluate("TokenJaccard (bench, unweighted)", TokenJaccard()),
        evaluate(f"DefectMatcher (IDENT_WEIGHT={patch_review.IDENT_WEIGHT})",
                 patch_review.MATCHER),
    ]
    print(f"{'matcher':38} {'rank-1':>8} {'mean score':>11} {'mean gap to top':>16}")
    for name, at1, mean, margin in rows:
        print(f"{name:38} {at1:>4}/{len(CORPUS):<3} {mean:>11.4f} {margin:>16.4f}")

    print(f"\nweight curve — IDENT_WEIGHT was fixed at "
          f"{patch_review.IDENT_WEIGHT} before this was run")
    print(f"{'weight':>8} {'rank-1':>8} {'mean score':>11}")
    for w in (1.0, 2.0, 3.0, 5.0, 8.0):
        _, at1, mean, _ = evaluate("", _Weighted(w))
        mark = "  <- shipped" if w == patch_review.IDENT_WEIGHT else ""
        print(f"{w:>8.1f} {at1:>4}/{len(CORPUS):<3} {mean:>11.4f}{mark}")

    # Where would the threshold have to sit? The shipped 0.92 was measured for
    # StringMatcher and is meaningless here; this is bench_accuracy's shape in
    # miniature — recall against false seals, swept.
    print(f"\nthreshold sweep — the shipped {memory.SEAL_THRESHOLD} was measured "
          f"for StringMatcher and does not transfer")
    print(f"{'cutoff':>8} {'would serve the right one':>26} "
          f"{'would serve a WRONG one':>24}")
    for cut in (0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.92):
        right = wrong = 0
        for i, (_, _, probe) in enumerate(CORPUS):
            scores = [patch_review.MATCHER.score(probe, d) for d, _, _ in CORPUS]
            best = max(range(len(scores)), key=lambda j: scores[j])
            if scores[best] >= cut:
                right += (best == i)
                wrong += (best != i)
        print(f"{cut:>8.2f} {right:>18}/{len(CORPUS):<7} "
              f"{wrong:>16}/{len(CORPUS):<7}")
    print("Read it the way README's Accuracy section says to: no cutoff is good "
          "at both jobs,\nand this corpus is 13 rows, which is far too few to "
          "set a deployment's dial from.")

    # --- half two: through the real store ---------------------------------
    d = pathlib.Path(tempfile.mkdtemp())
    cascade.set_ledger_path(d / "ledger.jsonl")
    store = SqliteStore(str(d / "nestor.db"))
    store.memory_init()
    try:
        for defect, fix, _ in CORPUS:
            patch_review.propose(defect, fix, reason="proposed by the recipe bench",
                                 origin="bench:patch_review", store=store)

        stats = memory.stats(store=store)
        print(f"\nstore: {stats['total']} pair(s), {stats['sealed']} sealed, "
              f"{stats['draft']} draft")
        assert stats["sealed"] == 0, (
            f"{stats['sealed']} sealed row(s) — this recipe proposes and must "
            f"never confirm.")

        served = sum(patch_review.fix_for(p, store=store) is not None
                     for _, _, p in CORPUS)
        print(f"fix_for() served {served} of {len(CORPUS)} probes — "
              f"nothing has been checked by a person, so nothing is served.")

        # And the refusal, demonstrated rather than described.
        try:
            patch_review.propose(CORPUS[0][0], "a different patch entirely",
                                 store=store)
            print("! a rival patch was accepted — the guard did not fire")
            return 1
        except patch_review.RivalPatchError:
            print("rival patch refused, with both exits named (revise / split).")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
