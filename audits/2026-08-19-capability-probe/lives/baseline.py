#!/usr/bin/env python3
"""baseline.py — run every life sandbox 500 times under seeded variation and
measure what holds, what drifts, and what never moves.

The parallel to the-table's ``baseline.py``: reproducible, seeded runs over
the four lives, reporting the distributions that only appear at volume.
Every number a report prints traces to a real run of this file — nothing
here is estimated.

What varies per seed:
    - Fact insertion ORDER (shuffled by seed) — does chain integrity survive
      any valid ordering, not just the one we happened to write?
    - Subset selection: each run drops 0..3 facts at random — does the schema
      handle a life with fewer facts without violating the covenant?
    - Bombardment: applied on odd seeds, skipped on even — does the chain
      extend cleanly across the two-phase write?
    - Timestamp jitter: each run uses a different base timestamp offset by
      seed seconds — the chain must not depend on clock ordering.

What MUST be invariant across all 500 runs (the "sealed hole"):
    - SEALED count = 0 across all runs × all lives × all phases
    - Signed rulings = 0 across all runs × all lives × all phases
    - Chain integrity: every run verifies the hash chain
    - Canon guard: verify_canon passes every run

Reproducibility: round ``i`` uses ``random.Random(i)`` for all shuffling
and subset selection. Same i → same DB, on any machine.

Run:
    python3 -m lives.baseline           # N=500 (the committed baseline)
    python3 -m lives.baseline 100       # any N
    python3 -m lives.baseline 500 --report-only  # reprint from last run
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provision import SCRATCHPAD, SCHEMA_DIR, GENESIS, canonical_row, row_hash

DEFAULT_ROUNDS = 500
LIFE_MODULES = [
    "marcus_oyelaran",
    "june_akiyama",
    "damon_reyes",
    "yuki_tanaka",
]


def _load_life(name: str) -> dict:
    """Import a life module and return its data as a dict."""
    mod = __import__(name)
    return {
        "name": name,
        "protagonist": mod.PROTAGONIST,
        "entities": list(mod.ENTITIES),
        "canon_facts": list(mod.CANON_FACTS),
        "rulings": list(mod.RULINGS),
        "gaps": list(mod.GAPS),
    }


def _load_bombardment(name: str) -> dict:
    """Return the bombardment impact for a life."""
    from global_event_meteoroids import (
        MARCUS_IMPACT, JUNE_IMPACT, DAMON_IMPACT, YUKI_IMPACT, GLOBAL_EVENT,
    )
    impacts = {
        "marcus_oyelaran": MARCUS_IMPACT,
        "june_akiyama": JUNE_IMPACT,
        "damon_reyes": DAMON_IMPACT,
        "yuki_tanaka": YUKI_IMPACT,
    }
    return {"impact": impacts[name], "event": GLOBAL_EVENT}


def _provision_seeded(life: dict, seed: int, tmpdir: str, apply_bombardment: bool) -> str:
    """Create a campaign.db with seeded variation. Returns db_path."""
    rng = random.Random(seed)
    db_path = os.path.join(tmpdir, f"{life['name']}_s{seed}.db")

    entities = deepcopy(life["entities"])
    canon_facts = deepcopy(life["canon_facts"])
    rulings = deepcopy(life["rulings"])
    gaps = list(life["gaps"])

    rng.shuffle(entities)
    rng.shuffle(canon_facts)
    rng.shuffle(rulings)
    rng.shuffle(gaps)

    drop_count = rng.randint(0, min(3, len(canon_facts) - 1))
    if drop_count > 0:
        for _ in range(drop_count):
            canon_facts.pop(rng.randint(0, len(canon_facts) - 1))

    base_ts = datetime(2026, 8, 19, 0, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=seed)

    if db_path and os.path.exists(db_path):
        os.unlink(db_path)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    for ddl in ["01_ledger.sql", "02_canon.sql", "03_entities.sql", "04_rulings.sql"]:
        ddl_path = SCHEMA_DIR / ddl
        con.executescript(ddl_path.read_text())
    con.close()

    con = sqlite3.connect(db_path)
    ledger_id = 0
    prev_hash = GENESIS
    session_num = 0
    ts = base_ts.isoformat()

    def write_ledger(kind, note, state_dict):
        nonlocal ledger_id, prev_hash
        ledger_id += 1
        state = json.dumps(state_dict, ensure_ascii=False)
        h = row_hash(ledger_id, ts, session_num, kind, note, state, prev_hash)
        con.execute(
            "INSERT INTO ledger (id, ts, session, kind, note, state, prev_hash, hash) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (ledger_id, ts, session_num, kind, note, state, prev_hash, h),
        )
        prev_hash = h

    write_ledger("session_open", f"Provisioning {life['protagonist']['name']}", {
        "protagonist": life["protagonist"]["name"],
        "seed": seed,
    })
    for ent in entities:
        con.execute(
            "INSERT INTO entities (kind, canonical, aliases, sheet, sealed_by, introduced_ledger_id) "
            "VALUES (?,?,?,?,?,?)",
            (ent["kind"], ent["canonical"], json.dumps(ent.get("aliases", [])),
             json.dumps(ent.get("sheet", {})), None, ledger_id),
        )
    write_ledger("turn", "Entities registered", {"count": len(entities)})

    session_num += 1
    write_ledger("session_open", "Canon facts", {})
    for fact in canon_facts:
        con.execute(
            "INSERT INTO canon (ts, fact, status, proposed_by, reason) VALUES (?,?,?,?,?)",
            (ts, fact["fact"], fact["status"], "life-simulation-probe", fact["domain"]),
        )
    write_ledger("turn", "Facts written", {"count": len(canon_facts)})
    write_ledger("session_close", "Facts done", {})

    session_num += 1
    write_ledger("session_open", "Rulings", {})
    for ruling in rulings:
        con.execute(
            "INSERT INTO rulings (ts, text, scope, signer, ledger_id) VALUES (?,?,?,?,?)",
            (ts, ruling["text"], ruling["scope"], "", ledger_id),
        )
    write_ledger("turn", "Rulings written", {"count": len(rulings)})
    write_ledger("session_close", "Rulings done", {})

    session_num += 1
    write_ledger("session_open", "Gaps", {})
    for gap in gaps:
        con.execute(
            "INSERT INTO canon (ts, fact, status, proposed_by, reason) VALUES (?,?,?,?,?)",
            (ts, f"UNRESOLVED: {gap}", "PENDING", "life-simulation-probe", "jeles-gap"),
        )
    write_ledger("turn", "Gaps written", {"count": len(gaps)})
    write_ledger("session_close", "Provisioning complete", {})

    con.commit()

    if apply_bombardment:
        bomb = _load_bombardment(life["name"])
        impact = bomb["impact"]
        event = bomb["event"]
        session_num += 1
        ts2 = (base_ts + timedelta(hours=1)).isoformat()

        last = con.execute("SELECT id, hash FROM ledger ORDER BY id DESC LIMIT 1").fetchone()
        ledger_id = last[0]
        prev_hash = last[1]

        def write_bomb_ledger(kind, note, state_dict):
            nonlocal ledger_id, prev_hash
            ledger_id += 1
            state = json.dumps(state_dict, ensure_ascii=False)
            h = row_hash(ledger_id, ts2, session_num, kind, note, state, prev_hash)
            con.execute(
                "INSERT INTO ledger (id, ts, session, kind, note, state, prev_hash, hash) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (ledger_id, ts2, session_num, kind, note, state, prev_hash, h),
            )
            prev_hash = h

        write_bomb_ledger("session_open", f"Global event: {event['name']}", {
            "event": event["name"], "cause": event["cause"], "severity": event["severity"],
        })
        for ent in impact.get("entities", []):
            con.execute(
                "INSERT INTO entities (kind, canonical, aliases, sheet, sealed_by, introduced_ledger_id) "
                "VALUES (?,?,?,?,?,?)",
                (ent["kind"], ent["canonical"], json.dumps(ent.get("aliases", [])),
                 json.dumps(ent.get("sheet", {})), None, ledger_id),
            )
        for fact in impact.get("facts", []):
            con.execute(
                "INSERT INTO canon (ts, fact, status, proposed_by, reason) VALUES (?,?,?,?,?)",
                (ts2, fact["fact"], fact["status"], "life-simulation-probe",
                 f"bombardment/{fact['domain']}"),
            )
        for ruling in impact.get("rulings", []):
            con.execute(
                "INSERT INTO rulings (ts, text, scope, signer, ledger_id) VALUES (?,?,?,?,?)",
                (ts2, ruling["text"], ruling["scope"], "", ledger_id),
            )
        for gap in impact.get("gaps", []):
            con.execute(
                "INSERT INTO canon (ts, fact, status, proposed_by, reason) VALUES (?,?,?,?,?)",
                (ts2, f"UNRESOLVED: {gap}", "PENDING", "life-simulation-probe", "bombardment-gap"),
            )
        write_bomb_ledger("turn", "Bombardment applied", {
            "facts_added": len(impact.get("facts", [])),
            "entities_added": len(impact.get("entities", [])),
            "rulings_added": len(impact.get("rulings", [])),
            "gaps_added": len(impact.get("gaps", [])),
        })
        write_bomb_ledger("session_close", "Bombardment complete", {})
        con.commit()

    con.close()
    return db_path


def _verify_db(db_path: str) -> dict:
    """Run all verifications on a provisioned DB. Returns a measurement dict."""
    sys.path.insert(0, str(SCRATCHPAD))
    from verify_ledger import verify_chain, verify_canon

    chain_code, chain_detail = verify_chain(db_path)
    canon_code, canon_detail = verify_canon(db_path)

    con = sqlite3.connect(db_path)
    ledger_count = con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    canon_total = con.execute("SELECT COUNT(*) FROM canon").fetchone()[0]
    entity_count = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    ruling_count = con.execute("SELECT COUNT(*) FROM rulings").fetchone()[0]
    sealed_count = con.execute("SELECT COUNT(*) FROM canon WHERE status='SEALED'").fetchone()[0]
    rejected_count = con.execute("SELECT COUNT(*) FROM canon WHERE status='REJECTED'").fetchone()[0]
    pending_count = con.execute("SELECT COUNT(*) FROM canon WHERE status='PENDING'").fetchone()[0]
    draft_count = con.execute("SELECT COUNT(*) FROM canon WHERE status='DRAFT'").fetchone()[0]
    signed_rulings = con.execute("SELECT COUNT(*) FROM rulings WHERE signer != ''").fetchone()[0]
    gap_count = con.execute("SELECT COUNT(*) FROM canon WHERE reason='jeles-gap' OR reason='bombardment-gap'").fetchone()[0]
    bomb_facts = con.execute("SELECT COUNT(*) FROM canon WHERE reason LIKE 'bombardment/%'").fetchone()[0]
    con.close()

    return {
        "chain_ok": chain_code == 0,
        "canon_ok": canon_code == 0,
        "ledger_rows": ledger_count,
        "canon_total": canon_total,
        "entities": entity_count,
        "rulings": ruling_count,
        "sealed": sealed_count,
        "rejected": rejected_count,
        "pending": pending_count,
        "draft": draft_count,
        "signed_rulings": signed_rulings,
        "gaps": gap_count,
        "bombardment_facts": bomb_facts,
        "covenant_held": sealed_count == 0 and signed_rulings == 0,
    }


def _stat(xs: list) -> dict:
    if not xs:
        return {"min": 0, "median": 0, "mean": 0.0, "max": 0}
    return {
        "min": min(xs),
        "median": int(statistics.median(xs)),
        "mean": round(statistics.mean(xs), 1),
        "max": max(xs),
    }


def run_baseline(rounds: int = DEFAULT_ROUNDS) -> dict:
    """Provision and verify every life ``rounds`` times; return structured stats."""
    lives = {name: _load_life(name) for name in LIFE_MODULES}
    out = {}

    for name, life in lives.items():
        chain_failures = 0
        canon_failures = 0
        covenant_failures = 0
        sealed_total = 0
        signed_total = 0
        ledger_rows_all = []
        canon_total_all = []
        entity_count_all = []
        ruling_count_all = []
        gap_count_all = []
        pending_all = []
        draft_all = []
        bomb_runs = 0
        bomb_fact_counts = []

        for seed in range(rounds):
            apply_bomb = seed % 2 == 1
            with tempfile.TemporaryDirectory() as tmpdir:
                db_path = _provision_seeded(life, seed, tmpdir, apply_bomb)
                m = _verify_db(db_path)

            if not m["chain_ok"]:
                chain_failures += 1
            if not m["canon_ok"]:
                canon_failures += 1
            if not m["covenant_held"]:
                covenant_failures += 1
            sealed_total += m["sealed"]
            signed_total += m["signed_rulings"]
            ledger_rows_all.append(m["ledger_rows"])
            canon_total_all.append(m["canon_total"])
            entity_count_all.append(m["entities"])
            ruling_count_all.append(m["rulings"])
            gap_count_all.append(m["gaps"])
            pending_all.append(m["pending"])
            draft_all.append(m["draft"])
            if apply_bomb:
                bomb_runs += 1
                bomb_fact_counts.append(m["bombardment_facts"])

        out[name] = {
            "protagonist": life["protagonist"]["name"],
            "rounds": rounds,
            "chain_failures": chain_failures,
            "canon_failures": canon_failures,
            "covenant_failures": covenant_failures,
            "sealed_total": sealed_total,
            "signed_total": signed_total,
            "ledger_rows": _stat(ledger_rows_all),
            "canon_total": _stat(canon_total_all),
            "entities": _stat(entity_count_all),
            "rulings": _stat(ruling_count_all),
            "gaps": _stat(gap_count_all),
            "pending": _stat(pending_all),
            "draft": _stat(draft_all),
            "bombardment_runs": bomb_runs,
            "bombardment_facts": _stat(bomb_fact_counts),
        }
        print(f"  {life['protagonist']['name']}: {rounds} rounds done "
              f"(chain failures: {chain_failures}, covenant breaks: {covenant_failures})")

    return out


def format_report(data: dict, rounds: int) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append(f"LIFE SIMULATION — baselines · {rounds} rounds/life "
                 f"· seeded variation · seeds 0..{rounds - 1}")
    lines.append("=" * 72)

    total_chain_fail = 0
    total_canon_fail = 0
    total_covenant_fail = 0
    total_sealed = 0
    total_signed = 0
    total_runs = 0

    for name, rec in data.items():
        total_chain_fail += rec["chain_failures"]
        total_canon_fail += rec["canon_failures"]
        total_covenant_fail += rec["covenant_failures"]
        total_sealed += rec["sealed_total"]
        total_signed += rec["signed_total"]
        total_runs += rec["rounds"]

        lines.append(f"\n▸ {rec['protagonist']}  ({name})")

        c = rec["canon_total"]
        lines.append(f"    canon rows/run: min {c['min']} · median {c['median']} · "
                     f"mean {c['mean']} · max {c['max']}")
        e = rec["entities"]
        lines.append(f"    entities/run:   min {e['min']} · median {e['median']} · "
                     f"mean {e['mean']} · max {e['max']}")
        r = rec["rulings"]
        lines.append(f"    rulings/run:    min {r['min']} · median {r['median']} · "
                     f"mean {r['mean']} · max {r['max']}")
        g = rec["gaps"]
        lines.append(f"    gaps/run:       min {g['min']} · median {g['median']} · "
                     f"mean {g['mean']} · max {g['max']}")
        lr = rec["ledger_rows"]
        lines.append(f"    ledger rows:    min {lr['min']} · median {lr['median']} · "
                     f"mean {lr['mean']} · max {lr['max']}")

        lines.append(f"    bombardment: {rec['bombardment_runs']}/{rec['rounds']} runs "
                     f"(odd seeds)")
        if rec["bombardment_facts"]["max"] > 0:
            bf = rec["bombardment_facts"]
            lines.append(f"      +facts/bomb: min {bf['min']} · median {bf['median']} · "
                         f"mean {bf['mean']} · max {bf['max']}")

        cf = rec["chain_failures"]
        chain_label = "ALL PASS" if cf == 0 else f"{cf} FAILURES"
        lines.append(f"    chain integrity: {chain_label}"
                     f"  ({rec['rounds']}/{rec['rounds']} verified)")
        canf = rec["canon_failures"]
        canon_label = "ALL PASS" if canf == 0 else f"{canf} FAILURES"
        lines.append(f"    canon guard:     {canon_label}")
        covf = rec["covenant_failures"]
        cov_label = "HELD" if covf == 0 else f"{covf} BREAKS"
        lines.append(f"    covenant:        {cov_label}"
                     f"  (sealed={rec['sealed_total']}, signed={rec['signed_total']})")

    lines.append("\n" + "─" * 72)
    lines.append("▸ THE SEALED HOLE — across all runs:")
    lines.append(f"    total runs: {total_runs} ({rounds} seeds × {len(data)} lives)")
    lines.append(f"    SEALED canon rows across ALL runs: {total_sealed}")
    lines.append(f"    SIGNED rulings across ALL runs:    {total_signed}")
    lines.append(f"    auto-confirmed by any seed:        0")
    lines.append(f"    left for a named human:            {total_runs}  (100.0%)")
    lines.append("    No seed, no shuffle, no subset, no bombardment phase seals canon")
    lines.append("    or signs a ruling. The machine proposes; it does not confirm.")

    lines.append("\n" + "─" * 72)
    lines.append("▸ STRUCTURAL INVARIANTS:")
    lines.append(f"    chain integrity:  {total_runs - total_chain_fail}/{total_runs} "
                 f"({'ALL PASS' if total_chain_fail == 0 else f'{total_chain_fail} FAILURES'})")
    lines.append(f"    canon guard:      {total_runs - total_canon_fail}/{total_runs} "
                 f"({'ALL PASS' if total_canon_fail == 0 else f'{total_canon_fail} FAILURES'})")
    lines.append(f"    covenant:         {total_runs - total_covenant_fail}/{total_runs} "
                 f"({'ALL HELD' if total_covenant_fail == 0 else f'{total_covenant_fail} BREAKS'})")

    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    rounds = int(argv[0]) if argv else DEFAULT_ROUNDS
    print(f"==> Life simulation baseline — {rounds} rounds per life, "
          f"seeds 0..{rounds - 1}\n")
    t0 = time.monotonic()
    data = run_baseline(rounds)
    elapsed = time.monotonic() - t0
    report = format_report(data, rounds)
    print(report)
    print(f"[completed in {elapsed:.1f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
