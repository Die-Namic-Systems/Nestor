#!/usr/bin/env python3
"""Stage 3 — human-authored surfaces AND human-authored probes, real corpus.

IDEAS.md §3.4. The entry's own "still untested" list names three gaps; this
closes two of them.

    stage 1  generator authored the surfaces and the probes .... ceiling
    stage 2  Claude authored the surfaces, Claude authored the
             "independent" probes ................................ 0.377 / 0.670,
                                                                   unresolved
    stage 3  a person authored every string on both sides ....... this file

Why the disagreement in stage 2 could not be settled from inside stage 2: probe
author and surface author were the same model family, so the 0.670 framing
rewarded the model for agreeing with itself and the 0.377 framing punished it
for not guessing a generator's arbitrary conventions. Neither is a user. Here
both sides are one person's prose, written across fourteen documents of
`terpsi-music` before any of it was going to be matched against anything.

Design
------
**Referent** is a file path — ground truth that owes nothing to string
similarity, so the labels cannot be circular with the thing being measured.

**Canonical surface** is the artifact's stem (`SENSITIVITY`), the name a person
types into a search box.

**Alternate surfaces** are verbatim spans of the human's prose, gated by
`corpus_terpsi.gate` — re-read from the source file and dropped if not a
literal substring. Annotation by a model, authorship by a person.

**The split is by source document, never by referent.** Surfaces written in the
seal-side documents are sealed; surfaces written in the probe-side documents are
queries. No string is on both sides. Two splits are run rather than one, because
a single arbitrary partition of fourteen documents is a sample of size one.

Arms
----
    canonical only     one row per referent — §3.4's baseline
    + human surfaces   canonical plus every seal-side span for that referent

Both arms answer the same probe list, so only the sealed rows differ.

Usage
-----
    python bench/bench_surfaces_human.py --extraction bench/results/terpsi_spans.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from bench import corpus_terpsi, harness  # noqa: E402
from bench.bench_accuracy import (THRESHOLDS, best_match,  # noqa: E402
                                  best_match_fast)
from bench.bench_surfaces import FLOOR, _seal_meaning  # noqa: E402
from nestor import memory  # noqa: E402
from bench.token_matchers import (TokenJaccard, TokenOverlap,  # noqa: E402
                                  shares_no_token)
from nestor.matcher import StringMatcher  # noqa: E402

# One partition of the source documents, run in **both directions** — seal from
# side A and probe with B, then seal from B and probe with A. A single direction
# is a sample of size one over an arbitrary cut; if the arms' ordering flips when
# the cut is reversed, the split was doing the work and the result is a coin toss
# reported as a finding.
#
# `SIDE_A` is listed and everything else is side B, so a source document that
# nobody thought about lands somewhere by construction rather than defaulting
# silently onto the probe side.
# Nestor's sweep starts at 0.80 and this corpus turns out to live below it, so
# "0.000 at every threshold" is a true statement that answers nothing. These
# extend the sweep *below anything Nestor would ship* — not as an operating
# proposal, but to turn a wall of zeros into a number: how far would the
# threshold have to move, and what does it cost in false seals when it does.
DIAGNOSTIC_THRESHOLDS = (0.55, 0.60, 0.65, 0.70, 0.75)
SWEEP = tuple(sorted(set(DIAGNOSTIC_THRESHOLDS) | set(THRESHOLDS)))

DUMP = []

SIDE_A = {
    "docs/ARCHITECTURE.md", "docs/CAPABILITY-MAP.md", "docs/CROSSINGS.md",
    "docs/SKINS.md", "docs/OPEN-SOURCE-SURVEY.md", "README.md", "CLAUDE.md",
}


def sides(records: list[dict]) -> tuple[set[str], set[str]]:
    """Partition every source document actually present into the two sides."""
    docs = {r["source_file"] for r in records}
    a = docs & SIDE_A
    b = docs - SIDE_A
    return a, b


def collisions(sealed: dict[str, list[str]], matcher) -> dict[str, list[str]]:
    """Surfaces that normalize the same for two different referents.

    A real-corpus property `aliased` could not have: the human writes "the
    architecture" for one file and could equally have written it for another.
    Sealing both raises `ConflictingSealError` — correctly — so the collision
    has to be reported rather than caught and dropped, or the bench would quietly
    seal whichever referent it happened to reach first.
    """
    owners: dict[str, list[str]] = {}
    for ref, surfaces in sealed.items():
        for s in surfaces:
            owners.setdefault(matcher.normalize(s), []).append(ref)
    return {k: v for k, v in owners.items() if len(set(v)) > 1}


def leave_one_out_false_seals(sealed: dict[str, list[str]],
                              probes: list[tuple[str, str]], matcher,
                              thresholds) -> dict:
    """False-seal rate measured on every probe, not on the eleven spare ones.

    The `absent` list is whatever probes happened to have an unsealed referent —
    on this corpus, eleven. A false-seal rate of 0/11 is not evidence of safety,
    it is an absence of evidence, and it matters most for exactly the matcher
    most likely to false-seal: `TokenOverlap` saturates at 1.0 whenever a probe
    shares one token with a one-token canonical, and it reported 0/11.

    So: for each probe, rebuild the store **without its own referent** and ask
    what comes back. The correct answer is now genuinely absent, so anything
    scoring above threshold is a false seal by construction. That turns eleven
    samples into one per probe, drawn from the real query distribution rather
    than from whatever was left over.

    Costs one store per referent, which at fourteen referents is free.
    """
    by_ref = {}
    for ref in sealed:
        store = harness.fresh_store()
        for r, surfaces in sealed.items():
            if r == ref:
                continue
            for s in surfaces:
                try:
                    _seal_meaning(store, [s], f"TERPSI:{r}", matcher)
                except memory.ConflictingSealError:
                    pass
        by_ref[ref] = store.memory_candidates("en", "es")

    def score(n, rows):
        if isinstance(matcher, StringMatcher):
            return best_match_fast(n, rows, matcher, 0.0)[0]
        return best_match(n, rows, matcher)[0]

    sims = [score(matcher.normalize(p), by_ref[ref])
            for p, ref in probes if ref in by_ref]
    n = max(1, len(sims))
    return {"n": len(sims),
            "rate": {str(t): round(sum(1 for s in sims if s >= t) / n, 4)
                     for t in thresholds}}


def score_arm(label: str, sealed: dict[str, list[str]], probes: list[tuple[str, str]],
              absent: list[str], matcher) -> dict:
    store = harness.fresh_store()
    intended = refused = 0
    for ref, surfaces in sealed.items():
        for s in surfaces:
            intended += 1
            try:
                _seal_meaning(store, [s], f"TERPSI:{ref}", matcher)
            except memory.ConflictingSealError:
                # A surface the human uses for two different files. Nestor
                # refuses the second seal, which is the correct behavior; the
                # bench's job is to count it, not to work around it.
                refused += 1
    actual = memory.stats(store=store)["sealed"]
    rows = store.memory_candidates("en", "es")

    # `best_match_fast` prunes with difflib's own upper bounds and its docstring
    # says so plainly: "Only valid for StringMatcher ... callers must fall back
    # to best_match for any other matcher." It accepts a `matcher` argument and
    # ignores it for scoring. Passing a token matcher to it produced difflib
    # over token-normalized strings, and the tell was that TokenJaccard and
    # TokenOverlap — which share a `normalize` and differ only in `similarity` —
    # returned byte-identical numbers in all 24 cells. Those runs were discarded.
    #
    # StringMatcher keeps the fast path because it is exactly equivalent there
    # and this corpus is small enough that the rest can afford the slow one.
    #
    # floor=0.0 either way: the fast path censors scores below the lowest
    # threshold, which is the range this corpus lives in, so a floor would
    # report "0.000 recall" and destroy the evidence for why.
    scorer = (lambda n: best_match_fast(n, rows, matcher, 0.0)) \
        if isinstance(matcher, StringMatcher) else (lambda n: best_match(n, rows, matcher))
    scored = [(*scorer(matcher.normalize(p)), f"TERPSI:{ref}") for p, ref in probes]
    absent_scored = [scorer(matcher.normalize(p)) for p in absent]

    # rank@1: how often the correct referent is the argmax, threshold ignored.
    # This is the number that separates the two failure modes. If rank@1 is high
    # and recall is zero, the matcher can see the answer and the threshold is in
    # the wrong place; if rank@1 is also low, the surfaces do not carry the
    # meaning and no threshold rescues them.
    rank1 = sum(1 for _, tgt, _, expect in scored if tgt == expect)
    sims = sorted(s for s, _, _, _ in scored)

    def pct(p):
        return round(sims[min(len(sims) - 1, int(p * len(sims)))], 4) if sims else 0.0

    # Recall's structural ceiling here is **1.0**, and saying so is the point.
    # Every scored probe's referent has at least one sealed row in both arms —
    # probes whose referent is unsealed were moved to `absent` — so unlike
    # stage 1, where recall was bounded by surface-family coverage, nothing but
    # the matcher stands between these arms and a perfect score. Whatever the
    # gap is, it is the matcher failing to bridge one human phrasing to another.
    out = {"arm": label, "referents_sealed": len(sealed),
           "rows_intended": intended, "rows_sealed": actual,
           "rows_refused_as_conflict": refused,
           "rows_lost_to_duplicate": intended - actual - refused,
           "n_probes": len(scored), "n_absent": len(absent_scored),
           "recall_ceiling": 1.0,
           "rank_at_1": round(rank1 / max(1, len(scored)), 4),
           "score_p50": pct(0.50), "score_p90": pct(0.90),
           "score_max": round(sims[-1], 4) if sims else 0.0,
           "by_threshold": []}

    for t in SWEEP:
        hit = sum(1 for sim, tgt, _, expect in scored if sim >= t and tgt == expect)
        fs = sum(1 for sim, _, _ in absent_scored if sim >= t)
        out["by_threshold"].append({
            "threshold": t,
            "recall": round(hit / max(1, len(scored)), 4),
            "false_seal_rate": round(fs / max(1, len(absent_scored)), 4),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--extraction", default="bench/results/terpsi_spans.json")
    ap.add_argument("--matcher", default="string",
                    choices=["string", "jaccard", "overlap"])
    args = ap.parse_args()

    matcher = {'string': StringMatcher, 'jaccard': TokenJaccard,
               'overlap': TokenOverlap}[args.matcher]()
    print(f"matcher: {args.matcher}")
    raw = corpus_terpsi.load(args.extraction)
    all_records, gate_report = corpus_terpsi.gate(raw, matcher=matcher)

    print("verbatim gate")
    print(f"  in {gate_report['in']}   kept {gate_report['kept']}   "
          f"rejected {gate_report['rejected']}")
    for reason, n in sorted(gate_report["by_reason"].items(), key=lambda kv: -kv[1]):
        print(f"    {n:4d}  {reason}")
    if gate_report["rejected"] == 0:
        print("  ** 0 rejections — distrust the gate before trusting the corpus **")

    disp = corpus_terpsi.dispersion(all_records, matcher)
    print(f"\ncorpus dispersion (span vs canonical): p10={disp['p10']} "
          f"p50={disp['p50']} p90={disp['p90']} max={disp['max']}")
    print(f"  exact after normalize: {disp['exact_rate']:.1%}   "
          f"already >=0.92: {disp['above_0.92']:.1%}")
    if disp["exact_rate"] > 0.5:
        print("  ** over half the spans ARE the canonical — this is a lookup test **")

    # The de-slug decision, quantified rather than asserted. Positive means the
    # raw filename form was costing the baseline arm similarity for punctuation
    # reasons; it is removed, so the baseline is scored at its best.
    refs = sorted({r["referent"] for r in all_records})
    deltas = []
    for r in all_records:
        p = matcher.normalize(r["span"])
        raw = matcher.similarity(p, matcher.normalize(corpus_terpsi._canonical(r["referent"], deslug=False)))
        des = matcher.similarity(p, matcher.normalize(corpus_terpsi._canonical(r["referent"])))
        deltas.append(des - raw)
    print(f"  de-slugging the canonical is worth {sum(deltas) / max(1, len(deltas)):+.4f} "
          f"mean similarity to the baseline arm (max {max(deltas, default=0):+.4f}) "
          f"over {len(refs)} referents — applied, as the conservative choice")



    harness.quiet_ledger(tempfile.mkdtemp())
    harness.seal_key("bench-key")

    results = []
    side_a, side_b = sides(all_records)
    print(f"\n{len(all_records)} spans — {len(side_a)} docs on side A, "
          f"{len(side_b)} on side B")
    for cut, strict in (("inclusive", False), ("strict (no substring overlap)", True)):
        print(f"\n=== {cut} cut ===")
        _run_splits(cut, all_records, side_a, side_b, matcher, results, strict)

    path = harness.record(
        "surfaces_human",
        {"extraction": args.extraction, "gate": gate_report, "dispersion": disp,
         "matcher": args.matcher, "corpus": str(corpus_terpsi.TERPSI),
         "corpus_revision": corpus_terpsi.corpus_revision(),
         "side_a_declared": sorted(SIDE_A), "thresholds": SWEEP,
         "shipped_thresholds": THRESHOLDS,
         "diagnostic_thresholds": DIAGNOSTIC_THRESHOLDS},
        results,
        notes=("Stage 3 of IDEAS.md 3.4. Every surface and every probe is a verbatim "
               "span of one person's prose in terpsi-music, gated by re-reading the "
               "source file; a model only labelled which span refers to which file. "
               "Split is by SOURCE DOCUMENT and run in both directions, so no string "
               "is both sealed and probed and no single arbitrary cut carries the "
               "result. Scored twice: 'templated' section references (§N of the X) "
               "are a family whose members differ by a digit, close enough to an "
               "exact-match lookup to carry a result on their own, so the variant "
               "without them is the conservative number."),
        # The files whose contents decide these numbers. Not a commit hash:
        # every one of this file's first 23 runs recorded git_rev 111c187,
        # because the bench was untracked while it was being edited.
        code_files=[__file__,
                    pathlib.Path(__file__).parent / "corpus_terpsi.py",
                    pathlib.Path(__file__).parent / "token_matchers.py",
                    pathlib.Path(__file__).parent / "bench_accuracy.py",
                    pathlib.Path(__file__).parent / "bench_surfaces.py",
                    pathlib.Path(__file__).parent / "harness.py",
                    pathlib.Path(__file__).parent.parent / "nestor" / "matcher.py"],
    )
    print(f"\nwrote {path}")
    d = pathlib.Path("bench/results/terpsi_splits.json")
    d.write_text(json.dumps(DUMP, indent=1, ensure_ascii=False))
    print(f"wrote {d} — the resolved splits, so another implementation\n  can answer the identical probe list rather than a similar one")


def _run_splits(variant, records, side_a, side_b, matcher, results, strict=False) -> None:
    for split_name, seal_docs in (("A->B", side_a), ("B->A", side_b)):
        # The lookup drop is computed with StringMatcher for EVERY run, not with
        # the matcher under test. Otherwise each matcher's `normalize` drops a
        # different set and the arms answer different questions — the first
        # token run had 17 probes where the string run had 41, and I nearly
        # compared the two numbers.
        surfaces, probes, srep = corpus_terpsi.split(
            records, seal_docs, StringMatcher(), strict)
        if not probes:
            print(f"\nsplit {split_name}: no probes — skipped")
            continue

        canon_only = {ref: [corpus_terpsi._canonical(ref)] for ref in surfaces}
        with_human = {ref: [corpus_terpsi._canonical(ref)] + s for ref, s in surfaces.items()}

        # Absent probes: spans whose referent has nothing sealed in this split.
        # Real near-misses from the same corpus, not synthetic strangers.
        absent = [p for p, ref in probes if ref not in surfaces]
        probes = [(p, ref) for p, ref in probes if ref in surfaces]
        if not probes:
            print(f"\nsplit {split_name}: every probe's referent is unsealed — skipped")
            continue

        print(f"\nsplit {split_name}: seal from {len(seal_docs)} docs -> "
              f"{len(surfaces)} referents, {sum(len(v) for v in surfaces.values())} spans; "
              f"probe with {len(probes)} spans ({len(absent)} absent)")
        before = srep["probes_before_drop"]
        bite = (srep["exact_dropped"] + srep["template_sibling_dropped"]) / max(1, before)
        extra = srep.get("containment_dropped", 0)
        bite = (srep["exact_dropped"] + srep["template_sibling_dropped"] + extra) / max(1, before)
        print(f"  dropped as lookups: {srep['exact_dropped']} exact + "
              f"{srep['template_sibling_dropped']} template-sibling"
              f"{f' + {extra} substring' if extra else ''} of {before} ({bite:.1%})")
        if bite > 0.5:
            print("  ** over half the probes were lookups — the split barely bites **")
        if len(probes) < 20:
            print(f"  ** {len(probes)} probes — too few to read a third decimal from **")
        if len(absent) < 10:
            print(f"  ** {len(absent)} absent probes — the false-seal rate is noise **")

        sealed_all = [s for ref, ss in surfaces.items()
                      for s in [corpus_terpsi._canonical(ref)] + ss]
        floor_n = sum(1 for p, _ in probes if shares_no_token(p, sealed_all))
        print(f"  probes sharing NO token with any sealed surface: {floor_n}/{len(probes)} "
              f"({floor_n / max(1, len(probes)):.1%}) — the lexical floor; "
              f"no matcher of any kind reaches these")

        DUMP.append({"cut": variant, "split": split_name,
                     "canonical": {r: corpus_terpsi._canonical(r) for r in surfaces},
                     "sealed": {r: list(v) for r, v in surfaces.items()},
                     "probes": [[p, r] for p, r in probes]})

        clash = collisions(with_human, matcher)
        if clash:
            print(f"  {len(clash)} surface(s) claimed by more than one referent — "
                  "dropped by the seal, not silently reassigned:")
            for norm, refs in sorted(clash.items())[:5]:
                print(f"    {norm!r} -> {sorted(set(refs))}")

        # Negative control. Same referents, same canonical rows, same NUMBER of
        # extra rows — but each referent gets another referent's surfaces. If
        # "+ human surfaces" beats "canonical only" because more rows in the
        # index is simply more chances to clear a threshold, this arm scores
        # the same and the finding is an artifact of index size. It should
        # collapse to roughly canonical-only recall with a higher false-seal
        # rate. An arm that cannot fail is not a control.
        refs = sorted(surfaces)
        arms = [("canonical only", canon_only), ("+ human surfaces", with_human)]
        if len(refs) > 1:
            rotated = {r: surfaces[refs[(i + 1) % len(refs)]] for i, r in enumerate(refs)}
            arms.append(("+ WRONG surfaces",
                         {r: [corpus_terpsi._canonical(r)] + rotated[r] for r in refs}))
        else:
            print("  ** one referent — the negative control cannot be built **")

        for label, sealed in arms:
            r = score_arm(label, sealed, probes, absent, matcher)
            loo = leave_one_out_false_seals(sealed, probes, matcher, (0.92, 0.96))
            r["loo_false_seal"] = loo
            r["split"] = split_name
            r["variant"] = variant
            results.append(r)
            at92 = next(x for x in r["by_threshold"] if x["threshold"] == 0.92)
            at96 = next(x for x in r["by_threshold"] if x["threshold"] == 0.96)
            print(f"  {label:18s} rows={r['rows_sealed']:3d}  "
                  f"recall@.92={at92['recall']:.3f} fs={at92['false_seal_rate']:.3f}  "
                  f"recall@.96={at96['recall']:.3f}  |  "
                  f"rank@1={r['rank_at_1']:.3f}  "
                  f"score p50={r['score_p50']:.3f} max={r['score_max']:.3f}  |  "
                  f"LOO-fs@.92={loo['rate']['0.92']:.3f} (n={loo['n']})")


if __name__ == "__main__":
    main()
