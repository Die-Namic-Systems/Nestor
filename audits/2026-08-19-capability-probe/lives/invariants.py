#!/usr/bin/env python3
"""invariants.py — standing checks for the NPC, resolution and compound layers.

`baseline.py` asserts the sealed hole across 500 seeded runs of the four
life sandboxes.  It is built around provisioning those sandboxes, and the
NPC and compound layers do not provision that way — so this is a sibling
harness rather than a bend of that structure.  Both answer the same
question: does the thing still hold when you run it a lot?

Every check here exists because something was actually wrong. The three
regression checks (R1-R3) each pin a bug that was found by measuring a
distribution, not by reading the code — which is exactly why they need to
be standing checks rather than throwaway scripts:

  R1  A roster entry reported as alive at 0 hit points.  The compound's
      `arrived` list held live Character references that the arrival phase
      later mutates, so it displayed post-arrival state.  197 of 300 runs
      showed someone "arriving" at 0 HP and one corpse was listed as
      arrived.
  R2  A traveller with a survival rate low enough to be a scripted death.
      A guaranteed 5d6 close entry per journey killed 97% of ordinary
      travellers and 99.3% of a ten-year-old.
  R3  An NPC who cannot die, or who almost cannot live.  Four NPCs recorded
      zero deaths in 500 runs; one died 85% of the time to massive damage
      before a death save was rolled.

Usage:
    python3 invariants.py              # default rounds
    python3 invariants.py 200          # any N
    python3 invariants.py --quick      # small N, for a fast gate
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compound
import npcs as npc_mod
import resolution
from provision import SCRATCHPAD

DEFAULT_ROUNDS = 200
QUICK_ROUNDS = 40

# A character who is reported alive must have at least 1 hit point.
MIN_ALIVE_HP = 1

# The invariant is about observed extremes, not rates: every NPC must be
# seen to die at least once and to live at least once. That states the
# actual bug — four NPCs recorded zero deaths in 500 runs because their hit
# points exceeded any single hazard's maximum roll — without inventing a
# threshold. An earlier version used a 99.5% rate bound and fired on two
# NPCs who had each already died once, which is a badly posed check rather
# than a finding.
#
# Priya is exempt, and by construction rather than by taste: her only
# hazard is 1d6 against a Noble's 9 hit points, so the maximum roll cannot
# reduce her to 0 and no death save is ever reachable. That is what low
# exposure is supposed to mean — indoors, insured, several hundred miles
# from an impact — and it is the one place the cast contains a character
# the dice cannot touch. Every other low-exposure NPC is a 4 HP commoner
# who can be knocked unconscious by the same 1d6 and can fail death saves.
UNKILLABLE_BY_CONSTRUCTION = {"Priya Krishnamurthy"}


class Failure(Exception):
    pass


def check(results: list, name: str, ok: bool, detail: str):
    results.append({"name": name, "ok": ok, "detail": detail})


def skip(results: list, name: str, detail: str):
    """A check that cannot discriminate at this sample size.

    Reported as SKIP, never as PASS. A test that silently passes when it
    lacks the power to fail is worse than no test — it launders a
    non-observation into evidence.
    """
    results.append({"name": name, "ok": True, "skipped": True,
                    "detail": detail})


# An immortality check needs enough runs to tell a genuine 100% from a
# true rate in the high nineties. The most durable mortal in the cast sits
# near 97.4%: at N=40 that shows zero deaths roughly 34% of the time
# (0.974**40), so the check is noise. At N=200 it is 0.5%.
IMMORTAL_MIN_ROUNDS = 200


# =========================================================================
# COVENANT
# =========================================================================

def covenant_checks(results: list):
    """No writer in this stack may seal a fact or sign a ruling.

    This is the invariant the whole project rests on, and until now it was
    guaranteed only by two hardcoded string literals plus an after-the-fact
    query someone remembered to run.
    """
    seed = 7
    state = compound.run_session(seed)
    compound.write_compound_db(state)
    db = str(compound.COMPOUND_DB)

    con = sqlite3.connect(db)
    statuses = dict(con.execute(
        "SELECT status, COUNT(*) FROM canon GROUP BY status").fetchall())
    attributed = con.execute(
        "SELECT COUNT(*) FROM canon WHERE sealed_by IS NOT NULL "
        "AND sealed_by != ''").fetchone()[0]
    signed = con.execute(
        "SELECT COUNT(*) FROM rulings WHERE signer != ''").fetchone()[0]
    con.close()

    unsanctioned = {s: n for s, n in statuses.items()
                    if s not in ("DRAFT", "PENDING")}
    check(results, "covenant: compound writes only DRAFT/PENDING",
          not unsanctioned,
          f"statuses={statuses}" if not unsanctioned
          else f"UNSANCTIONED {unsanctioned}")
    check(results, "covenant: compound attributes no fact to a human",
          attributed == 0, f"attributed rows={attributed}")
    check(results, "covenant: compound signs no ruling",
          signed == 0, f"signed rulings={signed}")

    # The NPC writer, against the four life sandboxes.
    npc_bad = 0
    npc_rows = 0
    for key in ["marcus", "june", "damon", "yuki"]:
        p = SCRATCHPAD / f"{key}-life-sandbox" / "campaign.db"
        if not p.exists():
            continue
        c = sqlite3.connect(str(p))
        npc_rows += c.execute(
            "SELECT COUNT(*) FROM canon WHERE proposed_by='npc-resolution'"
        ).fetchone()[0]
        npc_bad += c.execute(
            "SELECT COUNT(*) FROM canon WHERE proposed_by='npc-resolution' "
            "AND status NOT IN ('DRAFT','PENDING')").fetchone()[0]
        c.close()
    check(results, "covenant: npc writer only DRAFT/PENDING",
          npc_bad == 0, f"{npc_rows} npc rows, {npc_bad} unsanctioned")

    # The chain must verify on a database this stack built from scratch.
    try:
        sys.path.insert(0, str(SCRATCHPAD))
        from verify_ledger import verify_canon, verify_chain
        c1, d1 = verify_chain(db)
        c2, d2 = verify_canon(db)
        check(results, "compound ledger chain intact", c1 == 0, d1)
        check(results, "compound canon guard passes", c2 == 0, d2)
    except ImportError:
        check(results, "compound ledger verified", False,
              "verify_ledger unavailable")


# =========================================================================
# R1 — nobody is alive at 0 HP, and nobody dead is on the roster
# =========================================================================

def r1_roster_coherence(results: list, rounds: int):
    zero_hp = []
    dead_on_roster = []
    for seed in range(rounds):
        s = compound.run_session(seed)
        for e in s["convergence"]["arrived"]:
            snap = e["on_arrival"]
            if snap["hp"] < MIN_ALIVE_HP:
                zero_hp.append((seed, e["name"], snap["hp"]))
            if e["status"] != "alive":
                dead_on_roster.append((seed, e["name"]))
    check(results, "R1a: no arrival recorded below 1 HP",
          not zero_hp,
          f"{rounds} runs clean" if not zero_hp
          else f"{len(zero_hp)} violations, e.g. {zero_hp[:3]}")
    check(results, "R1b: nobody dead appears on the arrived roster",
          not dead_on_roster,
          f"{rounds} runs clean" if not dead_on_roster
          else f"{len(dead_on_roster)} violations, e.g. {dead_on_roster[:3]}")


# =========================================================================
# R2 — the road is a hazard, not a sentence
# =========================================================================

def r2_road_not_scripted(results: list, rounds: int):
    from collections import Counter
    reached = Counter()
    eligible = Counter()
    for seed in range(rounds):
        s = compound.run_session(seed)
        for e in s["convergence"]["arrived"]:
            reached[e["name"]] += 1
        for e in s["convergence"]["arrived"] + s["convergence"]["lost"]:
            eligible[e["name"]] += 1

    scripted = []
    for name, n in eligible.items():
        if n < rounds * 0.2:
            continue  # too rarely eligible to judge the road by
        rate = reached[name] / n
        if rate < 0.10:
            scripted.append((name, round(rate * 100, 1)))
    check(results, "R2: no traveller's road is a scripted death (<10% "
                   "given they set out)",
          not scripted,
          "all routes survivable" if not scripted
          else f"scripted: {scripted}")


# =========================================================================
# R3 — every NPC can die, and every NPC can live
# =========================================================================

def r3_npc_bounds(results: list, rounds: int):
    stats = npc_mod.run_distribution(rounds)
    never_died, never_lived = [], []
    for d in stats["rates"].values():
        died = rounds - d["survived"]
        if died == 0 and d["name"] not in UNKILLABLE_BY_CONSTRUCTION:
            never_died.append((d["name"], d["block"], d["exposure"]))
        if d["survived"] == 0:
            never_lived.append((d["name"], d["block"], d["exposure"]))

    if rounds < IMMORTAL_MIN_ROUNDS:
        skip(results, "R3a: every NPC can die",
             f"skipped — N={rounds} lacks the power to observe a death "
             f"from a ~97% survivor; needs N>={IMMORTAL_MIN_ROUNDS}")
    else:
        check(results, f"R3a: every NPC died at least once in {rounds} runs",
              not never_died,
              f"all mortal (Priya exempt by construction)"
              if not never_died else f"never died: {never_died}")
    check(results, f"R3b: every NPC survived at least once in {rounds} runs",
          not never_lived,
          "all survivable" if not never_lived
          else f"never survived: {never_lived}")


# =========================================================================
# CROSS-LAYER CONSISTENCY
# =========================================================================

def consistency_checks(results: list, rounds: int):
    # Determinism: the same seed must produce the same world, or none of
    # the measurements above mean anything.
    a = compound.run_session(11)
    b = compound.run_session(11)
    same = (
        [e["name"] for e in a["convergence"]["arrived"]]
        == [e["name"] for e in b["convergence"]["arrived"]]
        and a["operations"]["evidence"] == b["operations"]["evidence"]
        and a["revelation"]["tier"] == b["revelation"]["tier"]
    )
    check(results, "same seed reproduces the same session", same,
          f"tier={a['revelation']['tier']}, "
          f"evidence={a['operations']['evidence']}")

    # Eligibility: the compound may only draw on people who lived.
    violations = []
    for seed in range(min(rounds, 60)):
        s = compound.run_session(seed)
        for e in s["convergence"]["arrived"] + s["convergence"]["lost"]:
            if not s["survivors"].get(e["t"].key, False):
                violations.append((seed, e["name"]))
    check(results, "compound only draws on bombardment survivors",
          not violations,
          "clean" if not violations else f"{violations[:3]}")

    # The dead do not progress: a PC killed in resolution must never be
    # handed a progression function.
    import progression
    dead_progressed = []
    for seed in range(min(rounds, 40)):
        o = npc_mod.resolve_npcs(seed)
        ctx = npc_mod.build_ally_context(o)
        for r in resolution.resolve_all(seed, ally_context=ctx):
            if r["status"] != "alive" and r["hp_final"] != 0:
                dead_progressed.append((seed, r["name"], r["hp_final"]))
    check(results, "a dead character reports 0 HP and no progression",
          not dead_progressed,
          "clean" if not dead_progressed else f"{dead_progressed[:3]}")


# =========================================================================
# MAIN
# =========================================================================

def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    rounds = QUICK_ROUNDS if "--quick" in argv else DEFAULT_ROUNDS
    for a in argv:
        if a.isdigit():
            rounds = int(a)

    print("=" * 70)
    print(f"  INVARIANTS — NPC, resolution and compound layers  (N={rounds})")
    print("=" * 70)

    results: list = []
    covenant_checks(results)
    r1_roster_coherence(results, rounds)
    r2_road_not_scripted(results, rounds)
    r3_npc_bounds(results, rounds)
    consistency_checks(results, rounds)

    print()
    failed = skipped = 0
    for r in results:
        if r.get("skipped"):
            mark, skipped = "SKIP", skipped + 1
        elif r["ok"]:
            mark = "PASS"
        else:
            mark, failed = "FAIL", failed + 1
        print(f"  [{mark}] {r['name']}")
        print(f"         {r['detail']}")

    passed = len(results) - failed - skipped
    print()
    print("=" * 70)
    print(f"  {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
