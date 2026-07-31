"""nestor.calibrate — where the seal threshold should sit for *your* corpus.

``SEAL_THRESHOLD = 0.92`` is one global constant, and ``bench/`` measured that
no single value works: at 0.92 a 24,000-pair boilerplate corpus serves one
answer in six wrongly, while at 0.96 the same corpus is clean and effectively
dead (2.4% paraphrase recall). Different corpora sit in completely different
places on that trade (IDEAS §1.3). Those numbers have been sitting in
``bench/results/`` with nothing consuming them.

This is the consumer. It does not import the bench's corpora — it measures the
memory you actually have:

    for each sampled sealed pair, find the *other* sealed pair whose source
    scores highest against it and whose target is different.

Two sealed sources that score above the threshold and mean different things is
precisely a false seal: ask for one, get the other's verified answer. Every such
collision this reports is one that already exists in your memory, between two
things a human deliberately verified — not a synthetic probe, and not a
prediction.

**What it is a lower bound on.** Real queries include text that is not in the
memory at all, and those can collide too; this can only see the collisions the
corpus already contains. So a rate reported here is a floor, not a ceiling.
``bench/bench_accuracy.py`` measures the fuller picture with held-out probes and
a paraphrase tier — at the cost of needing a corpus built for it. Use this one
to answer "is 0.92 wrong for me, and roughly where should it be", and the bench
to answer "what does this matcher do in general".

**It does not change anything.** It prints a number. Moving the threshold is a
decision about how much unverified content you are willing to serve, and it
belongs to a person — pass ``seal_threshold=`` to ``best_sealed``, or set it per
call site. Recall is the other half of the trade and this cannot see it: your
memory contains no record of the paraphrases nobody asked yet.
"""
from __future__ import annotations

import random
from typing import Optional

from . import memory
from .matcher import Matcher
from .storage import Storage, get_store

# The sweep bench/ uses, so a number from here and a number from there can be
# read side by side.
THRESHOLDS = (0.80, 0.85, 0.90, 0.92, 0.94, 0.96, 0.98)

DEFAULT_TARGET = 0.01


def calibrate(store: Optional[Storage] = None, source_lang: str = "en",
              target_lang: str = "es", target_rate: float = DEFAULT_TARGET,
              sample: int = 300, thresholds=THRESHOLDS,
              matcher: Optional[Matcher] = None, seed: int = 0,
              examples: int = 5) -> dict:
    """Measure this memory's own collision rate across the threshold sweep.

    ``sample`` sampled rows are each scored against every sealed row in the
    domain, so the cost is ``sample × corpus`` comparisons — the same scan
    ``best_sealed`` does, run ``sample`` times. It uses the same lossless
    prefilter, floored at the lowest threshold in the sweep, so most candidates
    are discarded without being scored (IDEAS §2.1). Lower ``sample`` for a
    quick read; the whole corpus (``sample=0``) for the exact answer.

    Returns::

        {"domain", "corpus", "sampled",
         "sweep": [{"threshold", "collisions", "collision_rate"}, …],
         "current": 0.92, "current_rate": float,
         "target_rate": float, "recommended": float | None,
         "examples": [{"score", "source", "target", "collides_with", …}]}

    ``recommended`` is the **lowest** threshold in the sweep whose measured
    collision rate is at or below ``target_rate`` — lowest, because every point
    of threshold costs recall, so the cheapest cutoff that meets the safety
    target is the right one. ``None`` means no threshold in the sweep gets there,
    which is itself the finding: that corpus contains verified pairs that mean
    different things and read almost identically, and no cutoff separates them.
    """
    store = get_store(store)
    matcher = memory.get_matcher(matcher)
    store.memory_init()
    rows = [r for r in store.memory_candidates(source_lang, target_lang)
            if memory.is_verified_seal(r)]
    floor = min(thresholds)

    picked = rows
    if sample and 0 < sample < len(rows):
        picked = random.Random(seed).sample(rows, sample)

    bound = getattr(matcher, "similarity_bound", None)
    if not callable(bound):
        bound = None

    worst: list[dict] = []
    for probe in picked:
        best_sim, best_row = 0.0, None
        for other in rows:
            # A different row that says the SAME thing is not a collision; it is
            # a duplicate, and serving either one is correct. Only a
            # near-identical source with a different answer can serve the wrong
            # verified text.
            if other["id"] == probe["id"] or other["target_text"] == probe["target_text"]:
                continue
            need = max(floor, best_sim)
            if bound is not None and bound(probe["source_norm"],
                                           other["source_norm"], need) < need:
                continue
            sim = round(matcher.similarity(probe["source_norm"],
                                           other["source_norm"]), 3)
            if sim > best_sim:
                best_sim, best_row = sim, other
        if best_row is not None and best_sim >= floor:
            worst.append({"score": best_sim, "id": probe["id"],
                          "source": probe["source_text"],
                          "target": probe["target_text"],
                          "collides_with": best_row["source_text"],
                          "would_serve": best_row["target_text"],
                          "verifier": best_row.get("verifier", "")})
    worst.sort(key=lambda c: -c["score"])

    n = len(picked) or 1
    sweep = []
    for t in sorted(thresholds):
        hits = sum(1 for c in worst if c["score"] >= t)
        sweep.append({"threshold": t, "collisions": hits,
                      "collision_rate": hits / n})

    recommended = next((row["threshold"] for row in sweep
                        if row["collision_rate"] <= target_rate), None)
    current = memory.SEAL_THRESHOLD
    current_rate = sum(1 for c in worst if c["score"] >= current) / n

    return {
        "domain": {"source_lang": source_lang, "target_lang": target_lang},
        "corpus": len(rows), "sampled": len(picked),
        "sweep": sweep,
        "current": current, "current_rate": current_rate,
        "target_rate": target_rate, "recommended": recommended,
        "examples": worst[:examples],
        "floor": floor,
    }


def summarize(result: dict) -> str:
    """The calibration as a human reads it, verdict first."""
    d = result["domain"]
    lines = [f"{result['corpus']} sealed pair(s) in {d['source_lang']}→"
             f"{d['target_lang']}; sampled {result['sampled']}"]
    if not result["corpus"]:
        return lines[0] + "\n  nothing sealed here yet — nothing to calibrate against."
    lines.append("")
    lines.append("  threshold   collisions   rate")
    for row in result["sweep"]:
        mark = " ←shipped" if row["threshold"] == result["current"] else ""
        star = " ←recommended" if row["threshold"] == result["recommended"] else ""
        lines.append(f"    {row['threshold']:.2f}      {row['collisions']:>6}   "
                     f"{row['collision_rate'] * 100:6.2f}%{mark}{star}")
    lines.append("")
    if result["recommended"] is None:
        lines.append(f"  No threshold in the sweep reaches "
                     f"{result['target_rate'] * 100:.2f}%. This memory holds verified "
                     f"pairs that read almost identically and mean different things; "
                     f"no cutoff separates them. Look at the examples below — that is "
                     f"a corpus problem, not a dial problem.")
    elif result["recommended"] > result["current"]:
        lines.append(f"  {result['current']} lets {result['current_rate'] * 100:.2f}% of "
                     f"this corpus collide. {result['recommended']} reaches your "
                     f"{result['target_rate'] * 100:.2f}% target — and costs recall, "
                     f"which this cannot measure for you (see bench/).")
    elif result["recommended"] < result["current"]:
        lines.append(f"  {result['current']} is stricter than this corpus needs: "
                     f"{result['recommended']} already meets "
                     f"{result['target_rate'] * 100:.2f}%. Lowering it serves more real "
                     f"rewrites; check the recall side before you do.")
    else:
        lines.append(f"  {result['current']} is where this corpus wants it.")
    if result["examples"]:
        lines.append("\n  worst collisions (both sealed, different answers):")
        for c in result["examples"]:
            lines.append(f"    {c['score']:.3f}  {c['source'][:44]!r}")
            lines.append(f"           would serve  {c['would_serve'][:44]!r}  "
                         f"(sealed for {c['collides_with'][:34]!r})")
    lines.append("\n  This is a lower bound: it can only see collisions already in "
                 "the memory.")
    return "\n".join(lines)
