#!/usr/bin/env python3
"""Shared provisioner for life sandboxes.

Each life module defines ENTITIES, CANON_FACTS, RULINGS, GAPS, and a
PROTAGONIST dict.  This module provisions a campaign.db from the GM schema
and populates it — same four tables, same hash-chained ledger, same
NOT_A_PERSON guard.

Usage from a life module:
    from provision import create_life
    create_life(db_path, PROTAGONIST, ENTITIES, CANON_FACTS, RULINGS, GAPS)
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCRATCHPAD = Path(os.environ.get(
    "LIFE_SANDBOX_DIR",
    "/tmp/claude-0/-home-user-Nestor/b2bb32f9-9208-5449-8125-3d3598b210a2/scratchpad",
))
SCHEMA_DIR = SCRATCHPAD

GENESIS = "genesis"


def canonical_row(id_, ts, session, kind, note, state, prev_hash) -> str:
    return json.dumps({
        "id": id_, "ts": ts, "session": session, "kind": kind,
        "note": note, "state": state, "prev_hash": prev_hash,
    }, ensure_ascii=False)


def row_hash(*args) -> str:
    return hashlib.sha256(canonical_row(*args).encode("utf-8")).hexdigest()


def provision_schema(db_path: str):
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.unlink()
    con = sqlite3.connect(db_path)
    for ddl in ["01_ledger.sql", "02_canon.sql", "03_entities.sql", "04_rulings.sql"]:
        con.executescript((SCHEMA_DIR / ddl).read_text())
    con.close()


def populate(db_path: str, protagonist: dict, entities: list[dict],
             canon_facts: list[dict], rulings: list[dict], gaps: list[str]):
    con = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    ledger_id = [0]
    prev_hash = [GENESIS]

    def write_ledger(session, kind, note, state_dict):
        ledger_id[0] += 1
        state = json.dumps(state_dict, ensure_ascii=False)
        h = row_hash(ledger_id[0], now, session, kind, note, state, prev_hash[0])
        con.execute(
            "INSERT INTO ledger (id, ts, session, kind, note, state, prev_hash, hash) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (ledger_id[0], now, session, kind, note, state, prev_hash[0], h),
        )
        prev_hash[0] = h
        return ledger_id[0]

    name = protagonist["name"]

    lid = write_ledger(0, "session_open", f"Entity registration — who is in {name}'s life", {})
    for ent in entities:
        con.execute(
            "INSERT INTO entities (kind, canonical, aliases, sheet, sealed_by, introduced_ledger_id) "
            "VALUES (?,?,?,?,?,?)",
            (ent["kind"], ent["canonical"], json.dumps(ent.get("aliases", [])),
             json.dumps(ent.get("sheet", {})), None, lid),
        )
    write_ledger(0, "session_close", f"Registered {len(entities)} entities",
                 {"entity_count": len(entities)})

    domains_seen = {}
    lid = write_ledger(1, "session_open",
                       f"{name}'s life — {len(canon_facts)} facts", {})
    for fact in canon_facts:
        domain = fact["domain"]
        domains_seen[domain] = domains_seen.get(domain, 0) + 1
        con.execute(
            "INSERT INTO canon (ts, fact, status, proposed_by, reason) VALUES (?,?,?,?,?)",
            (now, fact["fact"], fact["status"], "life-simulation-probe", domain),
        )
    write_ledger(1, "turn",
                 f"Wrote {len(canon_facts)} canon facts across {len(domains_seen)} domains",
                 {"facts": len(canon_facts), "domains": domains_seen})
    write_ledger(1, "session_close",
                 "All facts written — none sealed", {})

    lid = write_ledger(2, "session_open",
                       f"Decision graph — {len(rulings)} edges", {})
    for ruling in rulings:
        con.execute(
            "INSERT INTO rulings (ts, text, scope, signer, ledger_id) VALUES (?,?,?,?,?)",
            (now, ruling["text"], ruling["scope"], "", lid),
        )
    write_ledger(2, "turn",
                 f"Wrote {len(rulings)} rulings — all unsigned",
                 {"rulings": len(rulings), "signed": 0})
    write_ledger(2, "session_close", "Decision graph complete", {})

    lid = write_ledger(3, "session_open",
                       f"Unresolved questions — {len(gaps)} gaps", {})
    for gap in gaps:
        con.execute(
            "INSERT INTO canon (ts, fact, status, proposed_by, reason) VALUES (?,?,?,?,?)",
            (now, f"UNRESOLVED: {gap}", "PENDING", "life-simulation-probe", "jeles-gap"),
        )
    write_ledger(3, "turn",
                 f"Wrote {len(gaps)} unresolved questions as PENDING canon",
                 {"gaps": len(gaps)})
    write_ledger(3, "session_close", "Gaps recorded", {})

    con.commit()
    con.close()


def create_life(db_path: str, protagonist: dict, entities: list[dict],
                canon_facts: list[dict], rulings: list[dict], gaps: list[str]):
    provision_schema(db_path)
    populate(db_path, protagonist, entities, canon_facts, rulings, gaps)

    import sys
    sys.path.insert(0, str(SCRATCHPAD))
    from verify_ledger import verify_chain, verify_canon
    code1, d1 = verify_chain(db_path)
    code2, d2 = verify_canon(db_path)

    con = sqlite3.connect(db_path)
    total = con.execute("SELECT COUNT(*) FROM canon").fetchone()[0]
    ent_count = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    ruling_count = con.execute("SELECT COUNT(*) FROM rulings").fetchone()[0]
    gap_count = con.execute("SELECT COUNT(*) FROM canon WHERE reason='jeles-gap'").fetchone()[0]
    sealed = con.execute("SELECT COUNT(*) FROM canon WHERE status='SEALED'").fetchone()[0]
    con.close()

    print(f"  {protagonist['name']}: {total} facts, {ent_count} entities, "
          f"{ruling_count} rulings, {gap_count} gaps, {sealed} sealed")
    print(f"  chain: {d1}")
    print(f"  canon: {d2}")

    return code1 | code2
