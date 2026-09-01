#!/usr/bin/env python3
"""The dogfooding — Nestor's memory of its own decisions, and how well it answers.

    python demo/the_dogfooding.py              # the measurement
    python demo/the_dogfooding.py --keep DIR   # leave the sealed copies behind

**This is not fiction**, which puts it beside ``demo/the_border.py`` rather than
the invented desks. The corpus is real: every ``docs/dogfood/decisions/*.json``
file, one per merged PR, the same rows ``scripts/dogfood_store.py`` ships. No
sentence below is invented and no number is asserted from memory — each one is
produced by running the queries against the real store, here, on this checkout.

What it measures
----------------
The store holds the decisions Nestor made about *itself*. The obvious question a
demo of an audit-memory owes is not "does it work" but **"asked its own
questions back, how well does it answer — and when it is unsure, what does it
do?"** The house rule that a near miss served as verified is worse than no
answer is the whole product; this points that rule at the product's own history
and reports the number, favourable or not.

Three independent measurements, in ascending honesty:

* **The floor.** Every decision, queried in the exact words it was sealed under,
  is served back. If this ever drops below 100% something is broken in serving,
  not in the corpus.
* **A human asking in their own words.** Ten short, reworded queries — the way
  somebody actually asks months later. Measured, not hoped: most come back
  *pending*. That is the seal threshold refusing to serve a decision the
  paraphrase did not clearly match, and it is the product working, not failing.
* **The same thing, authoring-free, over the whole corpus.** Every multi-sentence
  question, queried by its first sentence alone. No hand-picked probes to argue
  with — the degradation is measured across all of them at once.

And the finding it turns up
---------------------------
The decision store keys its rows with the **default** ``StringMatcher`` —
difflib over characters. But a decision's text is prose *about* code, which is
exactly the population ``recipes/patch_review.py`` built ``DefectMatcher`` for,
arguing (with a bench) that character similarity rewards shared house-style
prose over the identifiers that actually carry the signal. Measured here, that
argument has teeth **and** a cost: ``StringMatcher`` admits collisions at the
serve bar that ``DefectMatcher`` does not — two genuinely different decisions
whose questions differ by one word score 0.94, so asking one serves the other —
but ``DefectMatcher``'s stricter keying also lowers paraphrase recall. Neither
is a free win, which is why this ships as a **draft** finding for a human, not a
patch. IDEAS §6.94, decision ``0079``.

Nothing here seals anything in the real store. It seals throwaway copies with a
fixture key purely to exercise the serve path, and it proposes its finding as a
draft — a machine may propose and may not confirm, including about the memory of
the machine's own decisions.
"""
from __future__ import annotations

import argparse
import contextlib
import glob
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import warnings

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# A fixture's key is not a secret. The seals below are really signed so the
# serve path is really exercised; a demo that measured retrieval with signing
# off would be measuring a store that serves rows nobody could have sealed.
os.environ.setdefault("NESTOR_SEAL_KEY", "dogfooding-fixture-key-not-a-secret")

from demo import desks                                          # noqa: E402
from demo.desks import (AMBER, BOLD, DIM, GREEN, OFF, RED,       # noqa: E402
                        beat, claim, note, say, verdict)
from nestor import keyring as keyring_mod, memory                                        # noqa: E402
from nestor.matcher import StringMatcher, uses_raw_score        # noqa: E402
from nestor.sqlite_store import SqliteStore                     # noqa: E402
from recipes import patch_review                                # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DECISIONS_DIR = REPO / "docs" / "dogfood" / "decisions"
COMMITTED_DB = REPO / "docs" / "dogfood" / "nestor.db"
DOGFOOD_KEYRING = REPO / "docs" / "dogfood" / "verifiers.json"
BUNDLE = REPO / "docs" / "dogfood" / "decisions.json"

DOMAIN = "decision"        # the same domain scripts/dogfood_store.py builds under
ORIGIN = "demo:the-dogfooding"

# Ten short, reworded queries — a person asking the gist months later, not
# retyping the sealed sentence. Paired with the decision file whose answer is
# the right one to serve. Faithful to questions in the corpus; the mechanical
# sweep in beat 5 is the authoring-free check on this hand-picked set.
PARAPHRASES = [
    ("how do we stop the container from reading my Google Drive corpus", "0046"),
    ("what happens when a ledger line will not parse", "0050"),
    ("do jeles nuggets come across already sealed", "0055"),
    ("which field of a source declaration is worth sealing", "0058"),
    ("why count countersignatures with a script instead of a grep", "0061"),
    ("the client wanted two Nestors, is that one demo or two", "0053"),
    ("what are the source and target when you feed a repo a constitution", "0057"),
    ("what did running the feeders on an empty corpus find", "0059"),
    ("does the package satisfy the constitution it was extracted from", "0060"),
    ("copy the fixture or extract the scaffolding for two desks", "0054"),
]


# --------------------------------------------------------------------------
# The corpus, read from the repository and nowhere else
# --------------------------------------------------------------------------

@contextlib.contextmanager
def _shipped_store_trust():
    """Verify ed25519 seals in the committed store, not the fixture HMAC key.

    Beats 3+ seal throwaway copies with ``dogfood-fixture``; beat 2 reads the
    real ``docs/dogfood/nestor.db`` whose rows were signed in the browser.
    """
    saved_seal = os.environ.pop("NESTOR_SEAL_KEY", None)
    saved_kr = os.environ.get("NESTOR_KEYRING")
    os.environ["NESTOR_KEYRING"] = str(DOGFOOD_KEYRING)
    keyring_mod.set_keyring(None)
    try:
        yield
    finally:
        keyring_mod.set_keyring(None)
        if saved_kr is not None:
            os.environ["NESTOR_KEYRING"] = saved_kr
        else:
            os.environ.pop("NESTOR_KEYRING", None)
        if saved_seal is not None:
            os.environ["NESTOR_SEAL_KEY"] = saved_seal
        else:
            os.environ.setdefault("NESTOR_SEAL_KEY", "dogfooding-fixture-key-not-a-secret")


def load_decisions(decisions_dir: pathlib.Path | None = None) -> list[dict]:
    """``[{file, question, commitment}]`` for every decision file in the repo.

    Read straight from the same files ``scripts/dogfood_store.py`` reads, in the
    same stable order, so the corpus measured here is the corpus that ships.
    """
    root = decisions_dir or DEFAULT_DECISIONS_DIR
    rows: list[dict] = []
    for path in sorted(glob.glob(str(root / "*.json"))):
        stem = pathlib.Path(path).name.split("-")[0]           # "0051"
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        for r in data["decisions"]:
            rows.append({"file": stem, "question": r["question"],
                         "commitment": r["commitment"]})
    return rows


def paraphrases_for(decisions: list[dict]) -> list[tuple[str, str]]:
    """Hand-picked rewordings whose target decision is present in this corpus."""
    present = {d["file"] for d in decisions}
    return [(query, want) for query, want in PARAPHRASES if want in present]


def by_commitment(decisions: list[dict]) -> dict[str, str]:
    """commitment text -> decision file, to name which decision a serve returned."""
    return {d["commitment"]: d["file"] for d in decisions}


def first_sentence(question: str) -> str:
    m = re.match(r"(.+?[.?!])(\s|$)", question.strip())
    return m.group(1) if m else question.strip()


# --------------------------------------------------------------------------
# The measurements — each returns numbers, and prints nothing it did not count
# --------------------------------------------------------------------------

def exact_retrieval(store, matcher, decisions) -> tuple[int, int, int]:
    """Query each decision in its sealed words. (hit, wrong, pending)."""
    hit = wrong = pending = 0
    for d in decisions:
        best = memory.best_sealed(d["question"], DOMAIN, DOMAIN, store=store,
                                  matcher=matcher)
        if best is None:
            pending += 1
        elif best["pair"]["target_text"] == d["commitment"]:
            hit += 1
        else:
            wrong += 1
    return hit, wrong, pending


def paraphrase_eval(store, matcher, decisions, show=False,
                    paraphrases: list[tuple[str, str]] | None = None) -> tuple[int, int, int]:
    """Run the reworded queries. (hit, wrong, pending)."""
    who = by_commitment(decisions)
    probes = paraphrases if paraphrases is not None else paraphrases_for(decisions)
    hit = wrong = pending = 0
    for query, want in probes:
        best = memory.best_sealed(query, DOMAIN, DOMAIN, store=store, matcher=matcher)
        top = memory.lookup(query, DOMAIN, DOMAIN, limit=1, store=store,
                            matcher=matcher, context_threshold=0.0)
        topsim = top[0]["similarity"] if top else 0.0
        if best is None:
            pending += 1
            mark, detail = f"{AMBER}~ pending{OFF}", f"closest {topsim:.2f}, below the bar"
        elif who.get(best["pair"]["target_text"], "").startswith(want):
            hit += 1
            mark, detail = f"{GREEN}✓ served{OFF}", f"{best['similarity']:.2f} → §{want}"
        else:
            wrong += 1
            got = who.get(best["pair"]["target_text"], "?")
            mark, detail = f"{RED}! wrong{OFF}", f"{best['similarity']:.2f} → §{got}, wanted §{want}"
        if show:
            say(f"{mark}  {DIM}{detail:26}{OFF} {query[:48]}")
    return hit, wrong, pending


def first_sentence_sweep(store, matcher, decisions) -> tuple[int, int, int, int]:
    """Every multi-sentence question, queried by sentence one. (n, hit, wrong, pending)."""
    n = hit = wrong = pending = 0
    for d in decisions:
        fs = first_sentence(d["question"])
        if fs == d["question"].strip():         # one sentence: shortening is a no-op
            continue
        n += 1
        best = memory.best_sealed(fs, DOMAIN, DOMAIN, store=store, matcher=matcher)
        if best is None:
            pending += 1
        elif best["pair"]["target_text"] == d["commitment"]:
            hit += 1
        else:
            wrong += 1
    return n, hit, wrong, pending


def collisions_at_bar(store, matcher, decisions) -> list[tuple]:
    """(query_file, query, other_file, other_answer, score) for every case where a
    decision's own question serves a DIFFERENT decision at/above the seal bar.

    On the shipped ``StringMatcher`` path this runs the fast pairwise pass
    below — length-ratio and ``quick_ratio()`` are cheap upper bounds on
    ``SequenceMatcher.ratio()``, so a candidate whose upper bound sits below
    the seal bar (0.92) is skipped before the expensive ratio call. On the
    current 532-row dogfood corpus that skips ~98% of candidates and cuts
    this function's wall time from ~47s to ~1s (see decision 0195). For a
    ``score()``-based matcher (``DefectMatcher``, semantic backends) the
    upper bounds do not apply and we defer to :func:`memory.lookup`, which
    keeps the original shape.
    """
    if uses_raw_score(matcher):
        return _collisions_via_lookup(store, matcher, decisions)
    return _collisions_via_ratio_bailout(store, matcher, decisions)


def _collisions_via_lookup(store, matcher, decisions) -> list[tuple]:
    """The general path — one ``memory.lookup`` per decision. Used when the
    matcher exposes ``score()`` (custom scoring that neither length nor
    quick_ratio bounds usefully)."""
    who = by_commitment(decisions)
    found = []
    for d in decisions:
        hits = memory.lookup(d["question"], DOMAIN, DOMAIN, limit=50, store=store,
                             matcher=matcher, context_threshold=0.0)
        for h in hits:
            other = h["pair"]["target_text"]
            if other != d["commitment"] and h["similarity"] >= memory.SEAL_THRESHOLD:
                found.append((d["file"], d["question"], who.get(other, "?"),
                              other, h["similarity"]))
    return found


def _collisions_via_ratio_bailout(store, matcher, decisions) -> list[tuple]:
    """Fast path for a ``StringMatcher``-shaped matcher (no ``score()``).

    Fetches candidate rows once; for each decision, uses ``SequenceMatcher``
    with the length-ratio and ``quick_ratio`` upper bounds to skip candidates
    whose maximum possible ratio is below :data:`memory.SEAL_THRESHOLD`, then
    runs the full ratio only on survivors. Output tuples are ordered by
    decision (as before) and by similarity descending within each decision
    (as ``memory.lookup``'s sort would give). Rounds similarity to 3 decimals
    to match ``memory.lookup``.
    """
    from difflib import SequenceMatcher

    who = by_commitment(decisions)
    bar = memory.SEAL_THRESHOLD
    # Candidates fetched once; rejection filter mirrors memory.lookup.
    rows = [r for r in store.memory_candidates(DOMAIN, DOMAIN)
            if r.get("status") != "rejected"]
    # A norm-length cache: reused across every decision as the query changes.
    row_norms = [(r, r["source_norm"]) for r in rows]
    found = []
    for d in decisions:
        qnorm = matcher.normalize(d["question"])
        la = len(qnorm)
        if la == 0:
            continue
        sm = SequenceMatcher(None, qnorm, autojunk=False)
        hits_here: list[tuple] = []
        for row, cnorm in row_norms:
            lb = len(cnorm)
            if lb == 0:
                continue
            # Length-ratio upper bound (SequenceMatcher.real_quick_ratio):
            # 2 * min(la, lb) / (la + lb). If already below the bar, no ratio
            # can possibly clear it.
            if 2 * min(la, lb) / (la + lb) < bar:
                continue
            sm.set_seq2(cnorm)
            # quick_ratio is a tighter O(N) upper bound; same bail rule.
            if sm.quick_ratio() < bar:
                continue
            sim = sm.ratio()
            if sim < bar:
                continue
            other = row["target_text"]
            if other == d["commitment"]:
                continue
            hits_here.append((d["file"], d["question"], who.get(other, "?"),
                              other, round(sim, 3)))
        # Sort within a decision by similarity descending, then cap at 50 to
        # match memory.lookup(limit=50)'s truncation. Without this cap the
        # fast path finds MORE hits than the slow path on a dense corpus
        # where a query has 50+ real collisions above the bar; the demo's
        # counts and assertions are calibrated to the shipped truncation
        # and this optimization is a speed fix, not a behaviour change.
        hits_here.sort(key=lambda t: -t[4])
        found.extend(hits_here[:50])
    return found


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", default="", help="leave the sealed copies behind here")
    ap.add_argument("--decisions-dir", type=pathlib.Path, default=None,
                    help="decision JSON directory (default: docs/dogfood/decisions)")
    ap.add_argument("--smoke", action="store_true",
                    help="pinned CI corpus: skip committed-bundle parity check")
    args = ap.parse_args()
    decisions_dir = args.decisions_dir or DEFAULT_DECISIONS_DIR
    work = (pathlib.Path(args.keep) if args.keep
            else pathlib.Path(tempfile.mkdtemp(prefix="nestor-dogfooding-")))
    work.mkdir(parents=True, exist_ok=True)

    print(f"\n{BOLD}The dogfooding{OFF}  {DIM}Nestor's memory of its own decisions, "
          f"measured{OFF}")
    if args.smoke:
        note("Pinned smoke corpus for CI — real decision files, not the full active "
             "queue. See tests/fixtures/dogfood_smoke/.")
    else:
        note("Not fiction. Every row below is a decision in docs/dogfood/decisions/, "
             "the corpus scripts/dogfood_store.py ships.")

    decisions = load_decisions(decisions_dir)
    paraphrases = paraphrases_for(decisions)

    # ---------------------------------------------------------------- 1
    beat(1, "The corpus is real, and it is the one that ships")
    files = sorted({d["file"] for d in decisions})
    if args.smoke:
        claim(len(decisions) > 0,
              "the pinned smoke corpus loaded at least one decision row")
        say(f"{BOLD}{len(decisions)}{OFF} decisions across {len(files)} files "
            f"({DIM}smoke fixture{OFF}).")
    else:
        bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
        claim(len(decisions) == len(bundle["pairs"]),
              "the decisions measured here are exactly the pairs in the committed bundle")
        say(f"{BOLD}{len(decisions)}{OFF} decisions across {len(files)} files, one file "
            f"per merged PR.")
    for d in decisions[:2]:
        say(f"{DIM}§{d['file']}  {OFF}{d['question'][:64]}")
    note("Every row is traceable to a file in a merged PR — the point of the store, "
         "and the reason this measurement can be trusted at all.")

    # ---------------------------------------------------------------- 2
    beat(2, "In the store that ships, seals trace to reviewable files")
    copied = work / "committed"
    copied.mkdir(parents=True, exist_ok=True)
    shutil.copy(COMMITTED_DB, copied / "nestor.db")             # never touch the real one
    with _shipped_store_trust():
        shipped = SqliteStore(str(copied / "nestor.db"))
        shipped.memory_init()
        st = memory.stats(store=shipped)
        seal_dir = REPO / "docs" / "dogfood" / "seals"
        seal_files = sorted(seal_dir.glob("*.json")) if seal_dir.is_dir() else []
        claim(st["sealed"] == len(seal_files),
              "every sealed row in git must have a matching seal file, and vice versa")
        if st["sealed"]:
            sealed_rows = [r for r in shipped.memory_candidates(DOMAIN, DOMAIN)
                           if r.get("status") == "sealed"]
            probe_q = (sealed_rows[0]["source_text"] if sealed_rows
                       else decisions[0]["question"])
            example = memory.best_sealed(probe_q, DOMAIN, DOMAIN,
                                         store=shipped, matcher=StringMatcher())
            claim(example is not None,
                  "a verbatim question serves its sealed answer from the shipped store")
        else:
            example = memory.best_sealed(decisions[0]["question"], DOMAIN, DOMAIN,
                                         store=shipped, matcher=StringMatcher())
            claim(example is None, "so it serves nothing as verified, by covenant")
        shipped.close()
    say(f"{st['total']} rows, {GREEN}{st['sealed']} sealed{OFF}, "
        f"{AMBER}{st['draft']} draft{OFF}, {len(seal_files)} seal file(s).")
    note("dogfood_store.py rebuilds drafts from decision files and folds in "
         "docs/dogfood/seals/*.json at --rebuild — so a sealed row in git always "
         "traces to reviewable JSON, not an ambient local store.")

    # ---------------------------------------------------------------- 3
    string_store = desks.seal_measurable_copy(
        work / "string", ((d["question"], d["commitment"]) for d in decisions),
        DOMAIN, DOMAIN, matcher=StringMatcher(), verifier="dogfood-fixture",
        origin=ORIGIN)
    beat(3, "The floor — asked in the words it was sealed under")
    hit, wrong, pending = exact_retrieval(string_store, StringMatcher(), decisions)
    claim(hit == len(decisions) and wrong == 0,
          "every decision, queried verbatim, serves back its own answer")
    say(f"{GREEN}{hit}/{len(decisions)} served correctly{OFF}, "
        f"{wrong} wrong, {pending} pending.")
    note("What a human sealed is served, exactly, forever after. This is the floor "
         "everything below stands on — if it cracks, serving is broken, not the corpus.")

    # ---------------------------------------------------------------- 4
    beat(4, "A human asking in their own words")
    hit, wrong, pending = paraphrase_eval(string_store, StringMatcher(), decisions,
                                          show=True)
    claim(wrong == 0, "no reworded query is answered with the WRONG decision")
    say()
    say(f"{BOLD}{hit} served, {pending} pending, {wrong} wrong{OFF} out of "
        f"{len(paraphrases)}.")
    note("Most come back pending — nothing sealed matched the paraphrase closely "
         "enough to serve. That is not the memory failing; it is the seal threshold "
         "refusing to answer a question it is not sure it was asked. Zero wrong is "
         "the number that matters: it says 'I don't know' rather than guessing.")

    # ---------------------------------------------------------------- 5
    beat(5, "The same test, authoring-free, across the whole corpus")
    n, hit, wrong, pending = first_sentence_sweep(string_store, StringMatcher(),
                                                  decisions)
    claim(wrong == 0, "shortening a question never makes it serve the wrong decision")
    say(f"Of {n} multi-sentence questions, queried by their first sentence alone:")
    say(f"{GREEN}{hit} still served{OFF}, {AMBER}{pending} pending{OFF}, "
        f"{RED}{wrong} wrong{OFF}.")
    note("No hand-picked probes to argue with — every question compressed the same "
         "mechanical way. The paraphrase result holds at corpus scale: recall falls "
         "off a cliff, and it falls toward pending, never toward wrong.")

    # ---------------------------------------------------------------- 6
    beat(6, "The one place it WOULD serve the wrong decision")
    hits = collisions_at_bar(string_store, StringMatcher(), decisions)
    claim(bool(hits),
          "at least one measured collision exists — this beat has something to show")
    say(f"{RED}{len(hits)}{OFF} quer(y/ies) where a DIFFERENT decision scores at or "
        f"above the {memory.SEAL_THRESHOLD} serve bar:")
    seen = set()
    for qf, q, of, _ans, score in hits:
        key = tuple(sorted((qf, of)))
        if key in seen:
            continue
        seen.add(key)
        say(f"  §{qf} ↔ §{of} at {RED}{score:.2f}{OFF}")
        say(f"    {DIM}{q[:70]}{OFF}")
    note("Genuinely different decisions whose questions differ by a word or two. "
         "difflib over characters cannot tell them apart, so asking one would serve "
         "the other's answer as verified — the house-style-prose collision "
         "patch_review.py warns about, in the decision store's own rows.")

    # ---------------------------------------------------------------- 7
    beat(7, "A better matcher, and why it is not a free win")
    defect_store = desks.seal_measurable_copy(
        work / "defect", ((d["question"], d["commitment"]) for d in decisions),
        DOMAIN, DOMAIN, matcher=patch_review.MATCHER, verifier="dogfood-fixture",
        origin=ORIGIN)
    s_para_hit, _, _ = paraphrase_eval(string_store, StringMatcher(), decisions)
    # The package itself warns that 0.92 was measured for StringMatcher, not for a
    # custom matcher's score() — so this whole column is at an uncalibrated bar,
    # which is the point, not an aside. Catch the warning and narrate it rather
    # than let it print through the table or suppress a true caveat in silence.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        d_coll = collisions_at_bar(defect_store, patch_review.MATCHER, decisions)
        d_para_hit, _, _ = paraphrase_eval(defect_store, patch_review.MATCHER, decisions)
    threshold_warned = any("SEAL_THRESHOLD" in str(w.message) for w in caught)
    claim(len(d_coll) <= len(hits),
          "the identifier-weighted matcher admits no more collisions than the default")
    say(f"{'':18}{BOLD}collisions @{memory.SEAL_THRESHOLD}{OFF}   "
        f"{BOLD}paraphrases served{OFF}")
    say(f"  StringMatcher   {RED}{len(hits):>10}{OFF}   {len(paraphrases)} → "
        f"{s_para_hit}")
    say(f"  DefectMatcher   {GREEN}{len(d_coll):>10}{OFF}   {len(paraphrases)} → "
        f"{d_para_hit}")
    note("DefectMatcher weights identifiers over prose (recipes/patch_review.py, with "
         "a bench), so it separates the collisions — but its stricter keying only "
         "fires on shared identifiers, so paraphrase recall does not improve and can "
         "fall. Fewer wrong serves OR more recall, not both from this one change.")
    claim(threshold_warned,
          "the package itself warns 0.92 was calibrated for StringMatcher, not this one")
    say()
    say(f"{DIM}And the package caught the comparison being unfair before this demo "
        f"did:{OFF}")
    say(f"   {AMBER}⚠{OFF} the {memory.SEAL_THRESHOLD} bar was measured for "
        f"StringMatcher, not DefectMatcher.")
    note("nestor calibrate --matcher … is how you'd set the bar for a matcher before "
         "trusting its serves. So the column above is indicative, not a verdict — and "
         "the honest 'which matcher' answer needs a calibration this demo has not run.")

    # ---------------------------------------------------------------- 8
    beat(8, "What this found, filed the only way a machine may file it")
    review = desks.Desk(name="review", root=work / "review",
                        source_lang=patch_review.DOMAIN,
                        target_lang=patch_review.DOMAIN,
                        matcher=patch_review.MATCHER, origin=ORIGIN).open()
    queued = patch_review.propose(
        "The dogfood decision store keys prose-about-code with the default "
        "StringMatcher; it admits serve-bar collisions between near-identical "
        "decision questions that DefectMatcher separates, while paraphrase recall "
        "stays low under both.",
        "Open: choose between the identifier-weighted matcher (fewer wrong serves, "
        "no better recall), semantic embeddings via the [semantic] extra (recall, "
        "at a dependency), and shorter canonical questions (recall, by hand). "
        "Measured by demo/the_dogfooding.py; a human still decides.",
        reason="Found and measured by demo/the_dogfooding.py. IDEAS §6.94, decision "
               "0079. This demo re-measures it on every run.",
        origin=ORIGIN, store=review.store)
    claim(queued["status"] == "draft", "the finding is proposed, not sealed")
    say(f"{AMBER}~ {queued['status']}{OFF} queued for a human on the review desk.")
    note("A machine may propose and may not confirm — including about the memory of "
         "its own decisions, and the matcher that keys it.")

    # ---------------------------------------------------------------- 9
    beat(9, "How well does Nestor do on its own code?")
    say("It holds every decision it was told, and serves each back in the words it")
    say("was sealed under. Asked in other words it mostly says pending, and — outside")
    say(f"the one colliding pair (§{'/§'.join(sorted(seen)[0]) if seen else '—'}) — "
        f"it does not serve the wrong one.")
    say()
    say(f"{BOLD}Everything it was told; almost nothing it was not asked in the same "
        f"words; and, but for a handful of measured collisions, never a lie.{OFF}")
    note("Whether that reads as the product working or the product too strict is the "
         "conversation the number is meant to start — which is the only thing an "
         "audit memory is for.")

    string_store.close()
    defect_store.close()
    if args.keep:
        print(f"\n   {DIM}kept: {work}{OFF}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    return verdict()


if __name__ == "__main__":
    raise SystemExit(main())
