#!/usr/bin/env python3
"""N1 — does the matcher recognize a *re-worded* decision? (docs/decision-memory.md)

`nestor decision check` (N9(1)) is only as good as `constraints_on`'s retrieval,
and `constraints_on` today matches a question by its EXACT normalized form. So a
proposal that is the same decision as a rejected one, phrased differently, is not
caught — the gate returns exit 0. This bench measures how much a *fuzzy* matcher
would recover, and — the number that actually decides it — the **wrong-key** rate:
how often a re-worded probe's best match is a DIFFERENT decision above the serving
bar, which under the gate would be a *false constraint* (block the wrong thing) or,
worse, mask the right one.

    python bench/bench_decision_n1.py --corpus bench/corpus_decision_n1 --matcher string
    python bench/bench_decision_n1.py --corpus bench/corpus_decision_n1 --matcher token
    python bench/bench_decision_n1.py --corpus bench/corpus_decision_n1 \
        --scores bench/corpus_decision_n1/semantic_scores.json --label "haiku stand-in"

The corpus dir holds ``corpus.json`` (``{id: {question, commitment}}``) and
``probes.json`` (``{id: re-worded question}``). ``--scores`` reads a precomputed
``{probe_id: {cand_id: sim}}`` map (for a matcher this process cannot run, e.g. a
language-model embedder stand-in over an egress-blocked backend).

Reported every run, because a bench's controls belong in the bench (§3.4): the
**paraphrase bite** — the fraction of probes that normalize *identically* to their
source question. A high number means the probes are not really re-worded and every
recall figure is a lookup test wearing a fuzzy-match costume.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from nestor.matcher import StringMatcher, match_similarity, uses_raw_score  # noqa: E402

BAR = 0.92
BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")


def _load(corpus_dir: pathlib.Path):
    corpus = {int(k): v for k, v in
              json.loads((corpus_dir / "corpus.json").read_text()).items()}
    probes = {int(k): v for k, v in
              json.loads((corpus_dir / "probes.json").read_text()).items()}
    return corpus, probes


def _build_matcher(name: str):
    if name == "string":
        return StringMatcher()
    if name in ("token", "overlap", "jaccard"):
        from token_matchers import TokenJaccard, TokenOverlap
        return TokenJaccard() if name == "jaccard" else TokenOverlap()
    raise SystemExit(f"unknown matcher {name!r} (string|token|jaccard)")


def _scores_matcher(matcher, probe_text, cand_text) -> float:
    raw = uses_raw_score(matcher)
    return match_similarity(matcher, probe_text, matcher.normalize(probe_text),
                            cand_text, matcher.normalize(cand_text), _raw_score=raw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--matcher", default="string")
    ap.add_argument("--scores", default="", help="precomputed {probe:{cand:sim}} JSON")
    ap.add_argument("--label", default="")
    ap.add_argument("--bar", type=float, default=BAR)
    ap.add_argument("--json", action="store_true", help="emit the metrics as JSON")
    args = ap.parse_args()

    corpus_dir = pathlib.Path(args.corpus)
    corpus, probes = _load(corpus_dir)
    ids = sorted(corpus)
    label = args.label or (f"scores:{pathlib.Path(args.scores).name}"
                           if args.scores else args.matcher)

    precomputed = None
    matcher = None
    if args.scores:
        raw = json.loads(pathlib.Path(args.scores).read_text())
        precomputed = {int(p): {int(c): float(s) for c, s in d.items()}
                       for p, d in raw.items()}
    else:
        matcher = _build_matcher(args.matcher)

    # paraphrase bite — the control: are the probes actually re-worded?
    sm = StringMatcher()
    identical = sum(1 for k in probes
                    if sm.normalize(probes[k]) == sm.normalize(corpus[k]["question"]))

    rank1 = recall = wrongkey = 0
    n = 0
    rows = []
    for k in ids:
        if k not in probes:
            continue
        n += 1
        probe = probes[k]
        if precomputed is not None:
            scored = sorted(((precomputed[k].get(c, 0.0), c) for c in ids),
                            key=lambda t: (-t[0], corpus[t[1]]["question"]))
        else:
            scored = sorted(((_scores_matcher(matcher, probe, corpus[c]["question"]), c)
                             for c in ids),
                            key=lambda t: (-t[0], corpus[t[1]]["question"]))
        top_score, top_id = scored[0]
        own = next(s for s, c in scored if c == k)
        pos = [c for _s, c in scored].index(k) + 1
        if top_id == k:
            rank1 += 1
        if own >= args.bar:
            recall += 1
        wrong = top_id != k and top_score >= args.bar
        if wrong:
            wrongkey += 1
        rows.append((k, pos, own, top_id, top_score, wrong))

    metrics = {"label": label, "n": n, "decisions": len(ids), "bar": args.bar,
               "paraphrase_bite_identical": identical, "rank1": rank1,
               "recall": recall, "wrong_key": wrongkey}
    if args.json:
        print(json.dumps(metrics))
        return 0

    print(f"\n{BOLD}N1: does the matcher recognize a re-worded decision?{OFF}  "
          f"{DIM}{label}, {n} probes over {len(ids)} decisions, bar {args.bar}{OFF}")
    print(f"  {DIM}paraphrase bite: {identical}/{n} probes normalize identically to "
          f"their source{OFF}"
          + (f"  {RED}<- probes are not re-worded; recall is a lookup test{OFF}"
             if identical > n * 0.5 else ""))
    print(f"  {BOLD}rank@1{OFF}         {rank1}/{n} ({rank1/n:.0%})   "
          f"{DIM}correct decision is the top match{OFF}")
    print(f"  {BOLD}recall@{args.bar}{OFF}    {recall}/{n} ({recall/n:.0%})   "
          f"{DIM}correct decision scores at/above the bar (would be caught){OFF}")
    colour = GREEN if wrongkey == 0 else RED
    print(f"  {colour}{BOLD}wrong-key@{args.bar}{OFF} {wrongkey}/{n} ({wrongkey/n:.0%})   "
          f"{DIM}a DIFFERENT decision serves >= bar — a false constraint{OFF}")

    worst = sorted((r for r in rows if r[5]), key=lambda r: -r[4])[:4]
    for k, pos, own, top_id, top_score, _w in worst:
        print(f"    {RED}wrong-key{OFF} probe[{k}] '{probes[k][:44]}' -> "
              f"decision[{top_id}] @{top_score:.2f} (own {own:.2f}, rank {pos})")
        print(f"      {DIM}asked: {corpus[k]['question'][:66]}{OFF}")
        print(f"      {DIM}got:   {corpus[top_id]['question'][:66]}{OFF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
