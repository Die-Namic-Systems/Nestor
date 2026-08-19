#!/usr/bin/env python3
"""session.py — Full post-apocalyptic survival session.

One script, start to finish:
  1. Provision all four lives from scratch
  2. Apply the meteoroid bombardment
  3. Resolve hazards through D&D 5e SRD 5.1 rules (who lives, who dies)
  4. Run progression for survivors (who shows up, what they decide)
  5. Print the full session report

The pipeline is deterministic for a given seed.  Seed 42 is the canonical
run.  Change it and a different person dies — or nobody does, or everybody
does.  That's the point: the dice don't care about your character arc.

Usage:
    python3 session.py                 # full session, seed=42
    python3 session.py --seed 0        # different seed
    python3 session.py --seed 42 --distribution 500
                                       # also run the survival distribution
    python3 session.py --seed 42 --verify
                                       # verify all chains after each phase

Rules content derived from the System Reference Document 5.1,
copyright Wizards of the Coast, LLC., licensed under the
Creative Commons Attribution 4.0 International License.
https://dnd.wizards.com/resources/systems-reference-document
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from provision import SCRATCHPAD

VERIFY_AVAILABLE = False
try:
    sys.path.insert(0, str(SCRATCHPAD))
    from verify_ledger import verify_chain, verify_canon
    VERIFY_AVAILABLE = True
except ImportError:
    pass

DIVIDER = "=" * 70
THIN = "-" * 70


def phase_banner(title: str, subtitle: str = ""):
    print(f"\n\n{'▓' * 70}")
    print(f"  {title}")
    if subtitle:
        print(f"  {subtitle}")
    print(f"{'▓' * 70}\n")


def section(title: str):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def db_path(name: str) -> str:
    return str(SCRATCHPAD / f"{name}-life-sandbox" / "campaign.db")


def db_stats(path: str) -> dict:
    con = sqlite3.connect(path)
    stats = {}
    stats["canon"] = con.execute("SELECT COUNT(*) FROM canon").fetchone()[0]
    stats["entities"] = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    stats["rulings"] = con.execute("SELECT COUNT(*) FROM rulings WHERE invalid_at IS NULL").fetchone()[0]
    stats["ledger"] = con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    stats["by_status"] = dict(
        con.execute("SELECT status, COUNT(*) FROM canon GROUP BY status").fetchall()
    )
    stats["rulings_signed"] = con.execute(
        "SELECT COUNT(*) FROM rulings WHERE signer != ''"
    ).fetchone()[0]
    con.close()
    return stats


def verify_db(path: str, label: str):
    if not VERIFY_AVAILABLE:
        return
    c1, d1 = verify_chain(path)
    c2, d2 = verify_canon(path)
    tag1 = "PASS" if c1 == 0 else "FAIL"
    tag2 = "PASS" if c2 == 0 else "FAIL"
    print(f"    {label}: chain {tag1} ({d1}), canon {tag2} ({d2})")


# =========================================================================
# PHASE 1: PROVISION
# =========================================================================

def run_provision():
    phase_banner("PHASE 1: PROVISION", "Four lives. Four databases. No decisions yet.")

    import marcus_oyelaran
    import june_akiyama
    import damon_reyes
    import yuki_tanaka

    lives = [
        ("Marcus Oyelaran", marcus_oyelaran),
        ("June Akiyama", june_akiyama),
        ("Damon Reyes", damon_reyes),
        ("Yuki Tanaka", yuki_tanaka),
    ]

    for name, mod in lives:
        mod.main() if hasattr(mod, "main") else None

    # If modules don't have main(), provision directly
    for name, mod in lives:
        if not Path(mod.DB).exists():
            from provision import create_life
            create_life(
                mod.DB, mod.PROTAGONIST, mod.ENTITIES,
                mod.CANON_FACTS, mod.RULINGS, mod.GAPS,
            )

    print()
    for name, mod in lives:
        s = db_stats(mod.DB)
        print(f"  {name}: {s['canon']} facts, {s['entities']} entities, "
              f"{s['rulings']} rulings, {s['ledger']} ledger entries")
        print(f"    statuses: {s['by_status']}")


# =========================================================================
# PHASE 2: BOMBARDMENT
# =========================================================================

def run_bombardment(verify: bool = False):
    phase_banner("PHASE 2: THE BOMBARDMENT",
                 "Something shifted in the Kuiper Belt. The sky is falling — slowly.")

    import global_event_meteoroids as bombardment

    print("  Three weeks of meteoroids. No extinction-level threat.")
    print("  Plenty of broken windows. Plenty of ambient dread.")
    print()

    bombardment.main()

    if verify:
        print()
        for key in ["marcus", "june", "damon", "yuki"]:
            verify_db(db_path(key), key)


# =========================================================================
# PHASE 3: RESOLUTION (D&D 5e)
# =========================================================================

def run_resolution(seed: int, verify: bool = False) -> list[dict]:
    phase_banner("PHASE 3: HAZARD RESOLUTION",
                 f"D&D 5e SRD 5.1 — seed={seed}. The dice don't care.")

    import resolution

    results = resolution.resolve_all(seed)

    for r in results:
        resolution.print_result(r)

    alive = [r for r in results if r["status"] == "alive"]
    dead = [r for r in results if r["status"] == "dead"]

    section(f"BOMBARDMENT RESOLUTION — {len(alive)} survived, {len(dead)} dead")
    for r in results:
        s = "ALIVE" if r["status"] == "alive" else "DEAD"
        hp = f"{r['hp_final']}/{r['max_hp']}" if r["status"] == "alive" else "0"
        print(f"  {r['name']:20s}  {r['class']:35s}  {s:5s}  HP: {hp}")

    if dead:
        print()
        print("  The dead do not show up.")
        print("  Their decisions stay PENDING. Their rulings stay unsigned.")
        print("  That is the data.")

    if alive:
        print()
        print("  The living show up. They get to decide.")

    # Write outcomes to databases
    section("APPLYING OUTCOMES TO DATABASES")
    import shutil
    for r in results:
        key = r["db_key"]
        path = db_path(key)
        backup = path + ".pre-resolution"
        shutil.copy2(path, backup)

        if r["status"] == "dead":
            resolution.write_death_to_db(path, r["name"], r)
            print(f"  {r['name']}: DEATH recorded. Session closed permanently.")
        else:
            resolution.write_survival_to_db(path, r["name"], r)
            print(f"  {r['name']}: SURVIVAL recorded. Proceeds to progression.")

    if verify:
        print()
        for key in ["marcus", "june", "damon", "yuki"]:
            verify_db(db_path(key), key)

    return results


# =========================================================================
# PHASE 4: PROGRESSION
# =========================================================================

def run_progression(resolution_results: list[dict], verify: bool = False):
    alive_keys = {r["db_key"] for r in resolution_results if r["status"] == "alive"}
    dead_keys = {r["db_key"] for r in resolution_results if r["status"] != "alive"}
    dead_names = {r["db_key"]: r["name"] for r in resolution_results if r["status"] != "alive"}
    alive_names = {r["db_key"]: r["name"] for r in resolution_results if r["status"] == "alive"}

    phase_banner("PHASE 4: PROGRESSION",
                 f"{len(alive_keys)} show up. {len(dead_keys)} do not.")

    for key in dead_keys:
        name = dead_names[key]
        print(f"  {name} — DEAD")
        print(f"    Does not show up. PENDING decisions stay PENDING forever.")
        print(f"    Unsigned rulings stay unsigned. That is the data.")
        print()

    print(THIN)
    print("  The living sit down. They have data. They make their calls.\n")

    import progression

    all_results = []
    for key in ["marcus", "june", "damon", "yuki"]:
        if key in dead_keys:
            all_results.append({
                "name": dead_names[key], "dead": True,
                "sealed": 0, "rejected": 0, "signed": 0,
                "gaps_resolved": 0, "gaps_left_open": 0,
            })
            continue
        result = progression.run_one(key, verify=verify)
        all_results.append(result)

    # Summary
    alive_results = [r for r in all_results if not r.get("dead")]
    dead_results = [r for r in all_results if r.get("dead")]

    section(f"PROGRESSION COMPLETE — {len(alive_results)} survived, {len(dead_results)} dead")
    total_sealed = sum(r.get("sealed", 0) for r in alive_results)
    total_rejected = sum(r.get("rejected", 0) for r in alive_results)
    total_signed = sum(r.get("signed", 0) for r in alive_results)
    total_gaps_resolved = sum(r.get("gaps_resolved", 0) for r in alive_results)
    total_gaps_open = sum(r.get("gaps_left_open", 0) for r in alive_results)

    print(f"  Sealed:   {total_sealed}")
    print(f"  Rejected: {total_rejected}")
    print(f"  Signed:   {total_signed} rulings")
    print(f"  Gaps:     {total_gaps_resolved} resolved, {total_gaps_open} left open")
    print()
    for r in alive_results:
        print(f"    {r['name']}: sealed={r['sealed']} rejected={r['rejected']} "
              f"signed={r['signed']} gaps_open={r['gaps_left_open']}")
    for r in dead_results:
        print(f"    {r['name']}: DEAD — did not show up")

    return all_results


# =========================================================================
# FINAL REPORT
# =========================================================================

def final_report(resolution_results: list[dict], progression_results: list[dict]):
    phase_banner("SESSION COMPLETE", "The data is the data.")

    alive = [r for r in resolution_results if r["status"] == "alive"]
    dead = [r for r in resolution_results if r["status"] != "alive"]

    section("THE FOUR LIVES")
    for r in resolution_results:
        name = r["name"]
        cls = r["class"]
        if r["status"] == "alive":
            hp = f"{r['hp_final']}/{r['max_hp']}"
            exh = f"exhaustion {r['exhaustion']}"
            print(f"  {name:20s}  {cls:35s}")
            print(f"    Survived. HP: {hp}. {exh.title()}.")

            prog = next((p for p in progression_results
                        if p.get("name") == name and not p.get("dead")), None)
            if prog:
                print(f"    Decisions: {prog['sealed']} sealed, "
                      f"{prog['rejected']} rejected, "
                      f"{prog['signed']} rulings signed")
                print(f"    Gaps: {prog['gaps_resolved']} resolved, "
                      f"{prog['gaps_left_open']} left open")
        else:
            cause = "unknown"
            for entry in reversed(r["log"]):
                if entry.get("event") == "death":
                    cause = entry.get("cause", "unknown")
                    break
            print(f"  {name:20s}  {cls:35s}")
            print(f"    Dead. Cause: {cause.replace('_', ' ')}.")
            print(f"    Did not show up. Decisions stay PENDING.")
        print()

    section("DATABASE STATE")
    for key in ["marcus", "june", "damon", "yuki"]:
        path = db_path(key)
        if not Path(path).exists():
            continue
        s = db_stats(path)
        name = key.replace("_", " ").title()
        print(f"  {name}:")
        print(f"    canon={s['canon']}  statuses={s['by_status']}")
        print(f"    rulings: {s['rulings']} total, {s['rulings_signed']} signed")
        print(f"    ledger: {s['ledger']} entries")

    section("COVENANT CHECK")
    all_held = True
    for key in ["marcus", "june", "damon", "yuki"]:
        path = db_path(key)
        if not Path(path).exists():
            continue
        con = sqlite3.connect(path)
        sealed_rows = con.execute(
            "SELECT id, sealed_by FROM canon WHERE status='SEALED'"
        ).fetchall()
        unsigned_seals = [r for r in sealed_rows if not r[1]]
        signed_rows = con.execute(
            "SELECT id, signer FROM rulings WHERE signer != ''"
        ).fetchall()
        empty_signers = [r for r in signed_rows if not r[1].strip()]
        con.close()

        covenant = "HELD" if not unsigned_seals and not empty_signers else "BROKEN"
        if covenant == "BROKEN":
            all_held = False
        name = key.title()
        print(f"  {name}: covenant {covenant}")
        if unsigned_seals:
            print(f"    !! {len(unsigned_seals)} sealed facts with no human name")
        if empty_signers:
            print(f"    !! {len(empty_signers)} signed rulings with no signer")

    if all_held:
        print()
        print("  Every sealed fact carries a human name.")
        print("  Every signed ruling carries a human name.")
        print("  The machine proposed. The people decided.")

    section("THE TABLE")
    print()
    print("  Four lives entered the bombardment.")
    print(f"  {len(alive)} survived. {len(dead)} did not.")
    if dead:
        for r in dead:
            print(f"  {r['name']} is dead.")
    if alive:
        survivors = [r["name"] for r in alive]
        print(f"  {', '.join(survivors[:-1])}, and {survivors[-1]} showed up." if len(survivors) > 1
              else f"  {survivors[0]} showed up.")
        print("  They had data. They made their calls.")
    print()
    alive_prog = [p for p in progression_results if not p.get("dead")]
    if alive_prog:
        total_s = sum(p["sealed"] for p in alive_prog)
        total_r = sum(p["rejected"] for p in alive_prog)
        total_g = sum(p["gaps_left_open"] for p in alive_prog)
        print(f"  {total_s} decisions sealed. {total_r} rejected. {total_g} gaps left open.")
        print("  The gaps stay open because the data doesn't close them yet.")
        print("  That's honest. That's the data.")
    print()


# =========================================================================
# MAIN
# =========================================================================

def main(argv=None):
    argv = argv or sys.argv[1:]

    seed = 42
    verify = "--verify" in argv
    distribution = None

    for i, arg in enumerate(argv):
        if arg == "--seed" and i + 1 < len(argv):
            seed = int(argv[i + 1])
        if arg == "--distribution" and i + 1 < len(argv):
            distribution = int(argv[i + 1])

    print(DIVIDER)
    print("  POST-APOCALYPTIC SURVIVAL SESSION")
    print(f"  Seed: {seed}")
    print(f"  System: D&D 5e SRD 5.1 (CC-BY-4.0, Wizards of the Coast)")
    print(DIVIDER)

    t0 = time.time()

    run_provision()
    run_bombardment(verify=verify)
    resolution_results = run_resolution(seed, verify=verify)
    progression_results = run_progression(resolution_results, verify=verify)
    final_report(resolution_results, progression_results)

    elapsed = time.time() - t0
    print(f"  Session completed in {elapsed:.1f}s.\n")

    if distribution:
        import resolution
        phase_banner("SURVIVAL DISTRIBUTION",
                     f"N={distribution} — how often does each person survive?")
        resolution.main(["--distribution", str(distribution)])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
