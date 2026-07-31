#!/usr/bin/env python3
"""Do multiple sealed surfaces per meaning buy recall that raising the threshold can't?

IDEAS.md §3.4. The hypothesis is that the acronym/synonym miss class (§3.1's
``AWS`` → ``Amazon Web Services``) is answerable by sealing several *surfaces*
for one meaning — the shape ``entity.py`` already uses — rather than by a
semantic matcher (§3.3) and its dependency.

This bench is written to falsify that, not to confirm it. §1.1 is the reason:
margin was called the highest-value change on the list, and measuring it turned
a confident hypothesis into "mostly falsified." This one has exactly the same
shape — a plausible mechanism, an obvious story about why it should work — so it
gets the same treatment.

The trap it is built to avoid
-----------------------------
Sealing K surfaces per meaning multiplies the row count, and false seals rise
with row count on their own (accuracy.json: boilerplate 2k → 1.6%, 24k → 16.0%).
So "5 surfaces beat 1 surface" measured at equal *meanings* is not a result — it
is the corpus-size penalty and the surface benefit tangled together, reported as
whichever one you were hoping for.

Both budgets are therefore measured and reported apart:

* ``fixed-rows``     — M meanings × K surfaces, M·K held constant. Equal index
                       size, equal scan cost, different structure. **This is the
                       honest comparison**, and the one §3.4 stands or falls on.
* ``fixed-meanings`` — M held constant, rows grow with K. The naive reading,
                       included precisely because it is the one that will look
                       good for the wrong reason.

Which corpus to run it on — this bench was blind twice before it wasn't
-----------------------------------------------------------------------
Run against ``boilerplate``/``prose``, recall is identical to three decimals
across K=1/3/5 and the canonical surface wins 117 matches out of 117. That is
not a result about §3.4; it is a property of ``corpora.perturb``, whose
paraphrases sit at similarity 0.62–0.85 in a tight cluster around one string. In
that geometry the centroid is always the best bridge and extra points around it
are redundant. The miss class §3.4 targets lives at 0.27–0.50 (``AWS`` /
``Amazon Web Services`` = 0.273) and those corpora cannot express it.

``corpora.aliased`` was written for that, and its dispersion is measured into
every result (p50 0.407, vs perturb's 0.62–0.85) rather than assumed.

Then it was blind a second way. ``perturb`` does not bite on short name-like
surfaces — no company vocabulary in the synonym tables, no clauses to reorder,
no function words to drop, and a typo rule that needs >12 characters — so 88% of
surface-tier and **100%** of paraphrase-tier probes normalized identically to the
row they were meant to find. "Recall" was measuring whether the exact string had
been sealed. ``corpora.aliased_query`` replaces it with noise a person actually
introduces, and ``aliased_query_bite`` measures how far it moves the string
(31% still exact, p50 0.947). The bench prints that number every run and warns
above 50%, because both blindnesses looked like clean results at the time.

The rule both times: **measure the property the harness depends on, in the
harness, every run.** A corpus property that is asserted in a docstring is not
a control.

Usage
-----
    python bench/bench_surfaces.py --probes 250
    python bench/bench_surfaces.py --rows 4000 --surfaces 1,3,5 --quick
"""
from __future__ import annotations

import argparse
import random
import sys
import tempfile

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from bench import corpora, harness  # noqa: E402
from bench.bench_accuracy import THRESHOLDS, best_match_fast  # noqa: E402
from nestor import memory  # noqa: E402
from nestor.matcher import StringMatcher  # noqa: E402

FLOOR = min(THRESHOLDS)


def variants(phrase: str, need: int, rng: random.Random) -> list[str] | None:
    """``need`` distinct re-expressions of one meaning, or ``None``.

    Distinctness is enforced rather than assumed: ``perturb`` returns its input
    unchanged when no strategy fires, and a duplicate surface is not a second
    surface — it is the same row written twice, which would silently turn a K=5
    arm into a K=3 arm and inflate the measured per-row benefit.

    ``None`` when the phrase cannot produce ``need`` distinct variants. The
    caller must then drop that meaning from **every** arm, not just the arm that
    hit the limit — see :func:`_meaning_pool`.
    """
    out = [phrase]
    for _ in range(need * 12):
        if len(out) >= need:
            return out
        cand = corpora.perturb(phrase, rng, tier="paraphrase")
        if cand not in out:
            out.append(cand)
    return out if len(out) >= need else None


def _meaning_pool(phrases: list[str], need: int, seed: int) -> list[list[str]]:
    """Variant sets for the meanings that can supply ``need`` of them.

    ``need`` is ``max(K) + 1`` for the whole sweep, not each arm's own K, and
    that is the load-bearing detail.

    The first version of this bench generated variants per arm. A K=5 arm then
    required six distinct re-expressions where the K=1 arm required two, so the
    high-K arms silently ran on the subset of phrases with the richest
    paraphrase space — and dropped 115 of 120 probes reaching for the rest.
    Prose K=5 duly reported ``recall=1.000`` on five surviving probes, which is
    the kind of number that ends up in a table.

    Fixing the requirement across the sweep makes every arm run on the same
    meanings with the same probe; K then controls only how many of the already
    generated variants get sealed. Element ``need-1`` is never sealed by any arm
    and is the probe.
    """
    pool = []
    for i, phrase in enumerate(phrases):
        # Seeded per phrase index so the variant set for a given meaning is
        # identical no matter which arm asks for it.
        v = variants(phrase, need, random.Random(seed * 1_000_003 + i))
        if v is not None:
            pool.append(v)
    return pool


def _seal_meaning(store, surfaces: list[str], target: str, matcher) -> int:
    """Seal every surface of one meaning onto one target. Returns rows written.

    Not ``harness.seal_all``: that seals ``phrase -> BENCH:<i>`` one-to-one, and
    the whole point here is many-to-one.
    """
    written = 0
    for s in surfaces:
        memory.add_pair(s, target, "en", "es", status="sealed",
                        verifier="bench", store=store, matcher=matcher)
        written += 1
    return written


def run_arm(corpus_name: str, budget: str, k: int, rows: int, n_probes: int,
            seed: int, matcher, pool: list[list[str]], absent: list[str],
            probes: list[str], probe_universe: int) -> dict:
    """One (corpus, budget, K) cell of the sweep.

    ``pool`` and ``absent`` are built once for the whole sweep and shared, so
    every arm runs on identical meanings and identical never-sealed probes.
    """
    want = rows // k if budget == "fixed-rows" else rows
    sets = pool[:want]

    store = harness.fresh_store()
    intended = 0
    for i, v in enumerate(sets):
        # v[:k] are the sealed surfaces, in the generator's priority order.
        _seal_meaning(store, v[:k], f"BENCH:{i}", matcher)
        intended += k

    # Surfaces from different meanings can normalize to the same key. The store
    # keys on source_norm, and every seal here shares verifier "bench", so a
    # collision is treated as a self-correction and OVERWRITES rather than
    # raising — one meaning silently vanishes. Reported, because an arm that
    # quietly holds fewer rows than it intended is not the arm being compared.
    actual = memory.stats(store=store)["sealed"]

    # Probes are drawn from the meanings EVERY arm holds — the K=5 arm keeps
    # rows//5 meanings, so that is the shared prefix. Sampling from each arm's
    # own range instead would give the arms different probe sets, and a recall
    # difference between them could then be which meanings got picked rather
    # than what K did. Same seed, same universe, same probes across arms.
    rng = random.Random(seed)
    idx = rng.sample(range(min(probe_universe, len(sets))),
                     min(n_probes, probe_universe, len(sets)))
    recall_probes = [(probes[i], f"BENCH:{i}") for i in idx]

    rows_all = store.memory_candidates("en", "es")
    recall_scores = [
        (*best_match_fast(p, rows_all, matcher, FLOOR), expect)
        for p, expect in recall_probes
    ]
    absent_scores = [
        best_match_fast(p, rows_all, matcher, FLOOR)
        for p in absent
    ]

    measurements = []
    for t in THRESHOLDS:
        # Served AND routed to the right meaning. A hit that clears the
        # threshold but returns another meaning's target is not recall, it is a
        # false seal wearing recall's clothes.
        correct = sum(1 for sim, tgt, _, expect in recall_scores
                      if sim >= t and tgt == expect)
        false_seals = sum(1 for sim, _, _ in absent_scores if sim >= t)
        measurements.append({
            "corpus": corpus_name, "budget": budget, "surfaces_per_meaning": k,
            "meanings": len(sets), "rows_sealed": actual,
            "n_recall_probes": len(recall_scores),
            "threshold": t,
            "recall_paraphrase": round(correct / max(1, len(recall_scores)), 4),
            "false_seal_rate": round(false_seals / max(1, len(absent_scores)), 4),
            "false_seals": false_seals,
        })

    return {
        "measurements": measurements,
        "meta": {
            "corpus": corpus_name, "budget": budget, "surfaces_per_meaning": k,
            "meanings": len(sets),
            "rows_intended": intended, "rows_sealed": actual,
            "rows_lost_to_collision": intended - actual,
            "n_recall_probes": len(recall_scores), "n_absent_probes": len(absent_scores),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rows", type=int, default=6000,
                    help="row budget held constant across the fixed-rows arms")
    ap.add_argument("--surfaces", default="1,3,5",
                    help="comma-separated surfaces-per-meaning values")
    ap.add_argument("--probes", type=int, default=250)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--corpora", default="aliased,boilerplate")
    ap.add_argument("--probe-tier", default="surface", choices=("surface", "paraphrase"),
                    help="noise applied on top of the chosen surface family. "
                         "'surface' (typo/case/spacing) models a user typing a "
                         "surface they know; 'paraphrase' additionally rewords "
                         "it, which is a harder and arguably different case.")
    ap.add_argument("--min-probes", type=int, default=40,
                    help="flag any cell measured on fewer probes than this")
    ap.add_argument("--quick", action="store_true",
                    help="fixed-rows only — skip the fixed-meanings reference arms")
    args = ap.parse_args()

    ks = [int(x) for x in args.surfaces.split(",")]
    names = args.corpora.split(",")
    budgets = ["fixed-rows"] if args.quick else ["fixed-rows", "fixed-meanings"]

    tmp = tempfile.mkdtemp()
    harness.quiet_ledger(tmp)
    harness.seal_key("bench-key")     # sign the seals; unsigned would warn per row
    matcher = StringMatcher()

    run_id = harness.new_run_id()
    params = {
        "rows": args.rows, "surfaces": ks, "probes": args.probes,
        "seed": args.seed, "corpora": names, "budgets": budgets,
        "matcher": "StringMatcher", "thresholds": THRESHOLDS,
        "surface_source": "corpora.aliased families / corpora.perturb for non-aliased",
        "probe_tier": args.probe_tier,
        "aliased_probe_noise": "corpora.aliased_query (suffix abbreviation, "
                               "acronym dotting, word drop, typo) — perturb() "
                               "does not bite on short name-like surfaces",
        "stage": "1 of 2 — synthetic disjoint surfaces. Stage 2 (model-authored "
                 "surfaces, unseen probe) is untested; see IDEAS.md 3.4.",
    }
    notes = (
        "Tests IDEAS.md §3.4. recall_paraphrase = share of held-out paraphrase "
        "probes served at/above threshold AND routed to the correct meaning; a "
        "hit that clears the threshold but returns another meaning is counted "
        "as a miss, not a hit. false_seal_rate = share of never-sealed probes "
        "served. Read the 'fixed-rows' budget: it holds M*K constant so the "
        "arms have equal index size, isolating surface structure from the "
        "corpus-size penalty. 'fixed-meanings' grows rows with K and is "
        "included only as the naive reading. Surfaces here are corpus-drawn "
        "paraphrases from the same generator as the probe, so model quality is "
        "held at 'perfect'. KNOWN BLIND SPOT: corpora.perturb produces "
        "paraphrases clustered at sim 0.62-0.85 around the canonical phrase, so "
        "the canonical always wins and extra surfaces never fire (117/117 "
        "instrumented). The acronym/rename class §3.4 targets sits at 0.27-0.50 "
        "and is absent from these corpora. Needs corpora.aliased() to be a "
        "measurement of the hypothesis rather than of the generator."
    )

    need = max(ks) + 1          # K surfaces for the largest arm, plus the probe
    probe_slot = need - 1

    all_rows: list[dict] = []
    meta: list[dict] = []
    for corpus_name in names:
        # Built ONCE per corpus and shared by every arm: identical meanings,
        # identical probes, so K is the only thing that varies between arms.
        dispersion = {}
        if corpus_name == "aliased":
            # Surfaces come straight from the generator — no perturb-derived
            # variants, because perturbing one string is exactly what cannot
            # produce the disjoint case (see module docstring).
            raw = corpora.aliased(args.rows + args.probes, seed=args.seed)
            pool, absent_meanings = raw[:args.rows], raw[args.rows:]
            rng = random.Random(args.seed)
            # The probe is a LIGHT surface perturbation (case/typo/spacing) of
            # one randomly chosen family. Light, so it is not an exact match to
            # the sealed row and still has to be found by fuzzy scoring; random
            # family, so an arm sealing K of V families covers K/V of the query
            # distribution and the rest must be reached across families or not
            # at all. That cross-family question is the one worth measuring —
            # recall tracking K/V is arithmetic, what it costs is not.
            probe_families = [rng.randrange(len(m)) for m in pool]
            probes = [corpora.aliased_query(m[probe_families[i]], rng)
                      for i, m in enumerate(pool)]
            absent = [corpora.aliased_query(m[rng.randrange(len(m))], rng)
                      for m in absent_meanings]
            dispersion = corpora.aliased_dispersion(pool, matcher)
            bite = corpora.aliased_query_bite(pool, args.seed, matcher)
            print(f"\n{corpus_name}: {len(pool)} meanings x {len(pool[0])} surfaces, "
                  f"{len(absent)} absent probes")
            print(f"  intra-meaning similarity (measured, not assumed): {dispersion}")
            print(f"  probe bite vs its own sealed surface: {bite}")
            # The guard that would have caught the first two blind harnesses.
            # If probes normalize identically to the row they are meant to find,
            # "recall" is measuring exact lookup and nothing about matching.
            if bite["identical_pct"] > 0.5:
                print(f"  !! {bite['identical_pct']:.0%} of probes are EXACT after "
                      f"normalization — this measures lookup, not matching. "
                      f"Recall figures below are void.")
        else:
            gen = corpora.boilerplate if corpus_name == "boilerplate" else corpora.prose
            raw = list(dict.fromkeys(gen(args.rows + args.probes * 3, seed=args.seed)))
            absent = raw[-args.probes:]
            pool = _meaning_pool(raw[:-args.probes], need, args.seed)
            probe_families = []
            probes = [v[need - 1] for v in pool]
            print(f"\n{corpus_name}: {len(pool)} meanings usable of "
                  f"{len(raw) - args.probes} ({need} distinct variants required), "
                  f"{len(absent)} absent probes")
        # Common to every arm: the K=max arm is the narrowest.
        probe_universe = min(args.rows // max(ks), len(pool))
        for budget in budgets:
            for k in ks:
                if budget == "fixed-meanings" and k == 1:
                    continue          # identical to the fixed-rows K=1 arm
                out = run_arm(corpus_name, budget, k, args.rows, args.probes,
                              args.seed, matcher, pool, absent, probes,
                              probe_universe)
                for row in out["measurements"]:
                    row["intra_meaning_sim_p50"] = dispersion.get("p50")
                all_rows.extend(out["measurements"])
                out["meta"]["dispersion"] = dispersion
                if corpus_name == "aliased":
                    out["meta"]["probe_bite"] = bite
                if probe_families:
                    out["meta"]["probe_family_covered"] = round(
                        sum(1 for f in probe_families[:probe_universe] if f < k)
                        / max(1, min(probe_universe, len(probe_families))), 4)
                meta.append(out["meta"])
                m = out["meta"]
                print(f"{corpus_name:11s} {budget:14s} K={k} "
                      f"meanings={m['meanings']:5d} rows={m['rows_sealed']:5d} "
                      f"lost={m['rows_lost_to_collision']:4d} "
                      f"n_probes={m['n_recall_probes']}")
                for row in out["measurements"]:
                    if row["threshold"] in (0.92, 0.96):
                        cov = out["meta"].get("probe_family_covered")
                        cov_s = f"  (families sealed: {cov:.2f})" if cov is not None else ""
                        print(f"    t={row['threshold']}  "
                              f"recall={row['recall_paraphrase']:.3f}  "
                              f"false_seals={row['false_seal_rate']:.3f}{cov_s}")
                # Checkpoint after every arm: a run that dies partway leaves
                # its completed arms on disk rather than taking them with it.
                harness.record("surfaces", {**params, "arms": meta}, all_rows,
                               notes=notes, run_id=run_id, complete=False)

    path = harness.record("surfaces", {**params, "arms": meta}, all_rows,
                          notes=notes, run_id=run_id, complete=True)
    thin = [m for m in meta if m["n_recall_probes"] < args.min_probes]
    for m in thin:
        print(f"  !! {m['corpus']} {m['budget']} K={m['surfaces_per_meaning']} "
              f"measured on {m['n_recall_probes']} probes — too few to quote")
    print(f"\nwrote {path}")
    print("\nNOTE: only the 'aliased' corpus can express the disjoint-surface "
          "class §3.4 is about. On boilerplate/prose, flat recall across K is a "
          "property of corpora.perturb (paraphrases cluster at sim 0.62-0.85) "
          "and says nothing about the hypothesis. Read the fixed-rows arms; "
          "fixed-meanings is the naive reading and overstates the false-seal "
          "cost by ~2.3x at K=5.")


if __name__ == "__main__":
    main()
