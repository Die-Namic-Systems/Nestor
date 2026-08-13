#!/usr/bin/env python3
"""The Dispatches audit — Nestor's loop, proved on someone else's corpus.

    python demo/the_dispatches_audit.py

Every prior proof of Nestor's memory loop points it at Nestor's own decisions
(``demo/the_dogfooding.py``). This points it at an **external** corpus: the
findings from a real audit of the companion writing repo
``rudi193-cmd/DispatchesFromReality`` — broken links, a mislabelled provenance
table, a self-contradicting revenue figure, three clean pieces. The corpus is
``demo/dispatches_audit_corpus.json``; each row was verified during that audit and
is traceable to a commit or file there. Hand-recorded, because this repo cannot
see that one — which is the honest limit stated up front, not buried.

Three ways, because a loop is only proved from more than one side:

* **Way 1 — the ledger.** Seal the findings into a throwaway store and ask them
  back. The floor (verbatim) serves every one; a question nobody audited comes
  back *pending*, never a fabricated answer; and no query is ever served the
  WRONG finding. That is the anti-rediscovery loop: a later session asks "did
  anyone check the sociotechnical money?" and gets the recorded answer instead
  of re-running the audit.
* **Way 2 — the matcher as detector, and its ceiling.** The matcher can *align*
  a packet claim to its draft claim (retrieval). It cannot *check* that their
  numbers agree, and it is blind to a contradiction that lives inside one file —
  which is exactly where the one real contradiction was. So Way 2 rediscovers
  the ad-breaks paper's own thesis: the ``measured`` tier — a person reading the
  thing — does not automate.
* **Way 3 — provenance as the through-line.** The findings carry the paper's own
  ``assumed``/``fitted``/``measured`` states, and a combined view is worth its
  weakest input (``min()``), never an average. The ad-breaks evidence, pooled,
  is ``fitted`` — because its load-bearing rows are — no matter how many
  ``measured`` audit rows sit beside it.

Nothing here seals anything real: Way 1 seals a throwaway copy with a fixture
key to exercise the serve path, and closes it. A machine may propose and may not
confirm, including about an audit it ran itself.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# A fixture key is not a secret. Sealing under a real key (as demo/the_dogfooding
# does) means the serve path is genuinely exercised — a demo that measured
# retrieval with signing off would be measuring rows nobody could have sealed.
os.environ.setdefault("NESTOR_SEAL_KEY", "dispatches-fixture-key-not-a-secret")

from demo import desks                                            # noqa: E402
from demo.desks import (AMBER, BOLD, DIM, GREEN, OFF, RED,        # noqa: E402
                        beat, claim, note, say, verdict)
from nestor import memory                                          # noqa: E402
from nestor.matcher import StringMatcher                          # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
CORPUS = REPO / "demo" / "dispatches_audit_corpus.json"
DOMAIN = "audit"
ORIGIN = "demo:the-dispatches-audit"

#: assumed < fitted < measured — the ad-breaks paper's ordering, and the one
#: this demo propagates by min() in Way 3.
STATES = ("assumed", "fitted", "measured")


def load_corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def weakest(states) -> str:
    """min() over the provenance ordering — a pooled view is its weakest input."""
    return min(states, key=STATES.index)


def main() -> int:
    data = load_corpus()
    findings = data["findings"]
    rows = [(f["question"], f["finding"]) for f in findings]

    print(f"\n{BOLD}The Dispatches audit{OFF}  {DIM}Nestor's loop, proved on an "
          f"external corpus{OFF}")
    note("Corpus: demo/dispatches_audit_corpus.json — real findings from auditing "
         "rudi193-cmd/DispatchesFromReality, each traceable to a commit there.")

    work = pathlib.Path(tempfile.mkdtemp(prefix="nestor-dispatches-"))
    store = desks.seal_measurable_copy(
        work / "audit", rows, DOMAIN, DOMAIN,
        matcher=StringMatcher(), verifier="dispatches-fixture", origin=ORIGIN)

    # ------------------------------------------------------------------ Way 1
    beat(1, "The ledger — asked its findings back")
    hit = wrong = pending = 0
    for q, ans in rows:
        best = memory.best_sealed(q, DOMAIN, DOMAIN, store=store, matcher=StringMatcher())
        if best is None:
            pending += 1
        elif best["pair"]["target_text"] == ans:
            hit += 1
        else:
            wrong += 1
    claim(hit == len(rows) and wrong == 0,
          "every recorded finding, asked verbatim, serves back its own answer")
    say(f"{GREEN}{hit}/{len(rows)} served{OFF}, {wrong} wrong, {pending} pending "
        f"(the floor).")

    # The anti-rediscovery move: a question nobody audited must NOT be answered.
    unaudited = "has the essays folder been audited for contradictions?"
    miss = memory.best_sealed(unaudited, DOMAIN, DOMAIN, store=store, matcher=StringMatcher())
    claim(miss is None,
          "a question nobody audited returns pending, not an invented answer")
    say(f"{AMBER}~ pending{OFF}  {DIM}{unaudited}{OFF}")

    # And it never serves the WRONG finding — the property that makes recall
    # failures safe (they fall toward pending, never toward a confident lie).
    served_wrong = 0
    for q, ans in rows:
        top = memory.lookup(q, DOMAIN, DOMAIN, limit=3, store=store,
                            matcher=StringMatcher(), context_threshold=0.0)
        for h in top:
            if (h["pair"]["target_text"] != ans
                    and h["similarity"] >= memory.SEAL_THRESHOLD):
                served_wrong += 1
    claim(served_wrong == 0,
          "no finding's question serves a DIFFERENT finding at the serve bar")
    say(f"{GREEN}0 wrong serves{OFF} across {len(rows)} questions — recall fails "
        f"toward pending, never toward a lie.")
    note("This is the loop: a later session asks 'did anyone check the "
         "sociotechnical revenue figures?' and is served the recorded finding — "
         "instead of re-running the whole audit to re-derive it.")

    # ------------------------------------------------------------------ Way 2
    beat(2, "The matcher as detector — and the ceiling it hits")
    # Build a tiny store of DRAFT claims; query with PACKET claims. Retrieval
    # aligns a packet claim to its draft claim — but alignment is not a numbers
    # check, and there is no cross-file pair for a within-file contradiction.
    probes = data["drift_probes"]
    cross = [p for p in probes if p["packet_claim"] != "not repeated in the packet"]
    within = [p for p in probes if p["packet_claim"] == "not repeated in the packet"]
    claim_store = desks.seal_measurable_copy(
        work / "claims", [(p["draft_claim"], p["label"]) for p in cross],
        DOMAIN, DOMAIN, matcher=StringMatcher(), verifier="dispatches-fixture",
        origin=ORIGIN)
    aligned = 0
    for p in cross:
        top = memory.lookup(p["packet_claim"], DOMAIN, DOMAIN, limit=1,
                            store=claim_store, matcher=StringMatcher(),
                            context_threshold=0.0)
        if top and top[0]["pair"]["target_text"] == p["label"]:
            aligned += 1
    claim(aligned == len(cross),
          "the matcher aligns every cross-file packet claim to its draft claim")
    say(f"{GREEN}{aligned}/{len(cross)} cross-file claims aligned{OFF} by retrieval.")
    claim(bool(within),
          "the one real contradiction lived INSIDE a single file — no pair to align")
    for p in within:
        say(f"{RED}! invisible{OFF}  {DIM}{p['label']}{OFF}")
    note("Alignment is not a numbers check, and a within-file contradiction has no "
         "cross-file pair to retrieve. So the matcher cannot find the contradiction "
         "a human found by reading one file — which is the ad-breaks paper's own "
         "point: the measured tier does not automate.")

    # ------------------------------------------------------------------ Way 3
    beat(3, "Provenance as the through-line — a view is worth its weakest input")
    counts = {s: sum(1 for f in findings if f["provenance"] == s) for s in STATES}
    say(f"corpus states: {GREEN}{counts['measured']} measured{OFF}, "
        f"{AMBER}{counts['fitted']} fitted{OFF}, {counts['assumed']} assumed.")
    # The ad-breaks evidence pooled: the verification row (fitted) sits beside
    # measured audit rows. min() over the pool is fitted, not measured.
    adbreaks_states = [f["provenance"] for f in findings
                       if "ad breaks" in f["question"].lower()
                       or "ad Breaks" in f["question"]]
    pooled = weakest(adbreaks_states)
    claim("fitted" in adbreaks_states and pooled == "fitted",
          "pooling the ad-breaks evidence yields fitted — its weakest input, not an average")
    say(f"ad-breaks evidence {adbreaks_states} → {AMBER}{pooled}{OFF} "
        f"(min, not mean).")
    # min() is monotone: adding measured rows never lifts a fitted pool.
    claim(weakest(["measured", "measured", "fitted"]) == "fitted"
          and weakest(["measured", "measured"]) == "measured",
          "min() is honest: one fitted input holds the whole view down; all-measured stays measured")
    note("Averaging would let a pile of measured audit rows hide the one fitted "
         "verification row and report the paper as better-sourced than it is. min() "
         "refuses that — the same rule Nestor keeps for its own combined views.")

    store.close()
    claim_store.close()
    shutil.rmtree(work, ignore_errors=True)

    say()
    say(f"{BOLD}Way 1{OFF}: it remembers, and refuses to invent. "
        f"{BOLD}Way 2{OFF}: it aligns, and cannot judge. "
        f"{BOLD}Way 3{OFF}: it pools by the weakest, never the average.")
    return verdict()


if __name__ == "__main__":
    raise SystemExit(main())
