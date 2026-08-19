#!/usr/bin/env python3
"""life_sandbox.py — Run Elena Vasquez's life through the AI Game Master schema.

Provisions a campaign.db from the GM's four owned schemas, then translates
Elena's 52 draft pairs into canon rows, entities, rulings, and hash-chained
ledger entries. The GM schema adds what Nestor's flat store lacks: a lifecycle
state machine (PENDING→DRAFT→SEALED→REJECTED), entity resolution with aliases,
signed rulings that supersede rather than overwrite, and a NOT_A_PERSON guard
that structurally prevents a machine from sealing canon.

Every row is written as PENDING or DRAFT — the machine proposes, it does not
confirm. The sandbox is the proof: can a life be legible through the GM's
idiom, and does the covenant hold?
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRATCHPAD = Path(os.environ.get(
    "LIFE_SANDBOX_DIR",
    "/tmp/claude-0/-home-user-Nestor/b2bb32f9-9208-5449-8125-3d3598b210a2/scratchpad",
))
SCHEMA_DIR = SCRATCHPAD
BOX = SCRATCHPAD / "elena-life-sandbox"
DB = BOX / "campaign.db"

GENESIS = "genesis"


def canonical_row(id_, ts, session, kind, note, state, prev_hash) -> str:
    obj = {
        "id": id_,
        "ts": ts,
        "session": session,
        "kind": kind,
        "note": note,
        "state": state,
        "prev_hash": prev_hash,
    }
    return json.dumps(obj, ensure_ascii=False)


def row_hash(*args) -> str:
    return hashlib.sha256(canonical_row(*args).encode("utf-8")).hexdigest()


def provision():
    BOX.mkdir(parents=True, exist_ok=True)
    (BOX / "corpus").mkdir(exist_ok=True)
    (BOX / "keys").mkdir(exist_ok=True)
    if DB.exists():
        DB.unlink()

    con = sqlite3.connect(str(DB))
    for ddl in ["01_ledger.sql", "02_canon.sql", "03_entities.sql", "04_rulings.sql"]:
        path = SCHEMA_DIR / ddl
        con.executescript(path.read_text())
    con.close()
    print(f"provisioned: {DB}")


# Elena's life data — reconstructed from the life simulation probe.
# 52 pairs across 8 domains.

ENTITIES = [
    {"kind": "pc", "canonical": "Elena Vasquez", "aliases": ["Mom", "Mama", "me", "I"], "sheet": {"born": 1989, "location": "Portland, OR", "occupation": "Software Engineer / Founder"}},
    {"kind": "npc", "canonical": "Sofia Vasquez", "aliases": ["my kid", "my daughter", "Sofia", "Sof"], "sheet": {"born": 2015, "relation": "daughter"}},
    {"kind": "npc", "canonical": "Alex Chen", "aliases": ["that guy who stole from me", "Alex", "my business partner", "the partner"], "sheet": {"relation": "former business partner", "event": "embezzlement 2021"}},
    {"kind": "npc", "canonical": "Elena's Father", "aliases": ["my father", "Papa", "the man who left", "Dad"], "sheet": {"relation": "estranged father", "left": "early childhood"}},
    {"kind": "npc", "canonical": "Elena's Mother", "aliases": ["my mother", "Mamá"], "sheet": {"relation": "mother", "tension": "CS choice disapproval"}},
    {"kind": "npc", "canonical": "Dr. Okafor", "aliases": ["my therapist", "the therapist", "Dr. O"], "sheet": {"relation": "therapist", "started": 2023}},
    {"kind": "place", "canonical": "NovaBridge LLC", "aliases": ["the company", "NovaBridge", "my startup", "the business"], "sheet": {"founded": 2022, "type": "software consultancy"}},
    {"kind": "place", "canonical": "Meridian Technologies", "aliases": ["Meridian", "my old job", "the corporate job"], "sheet": {"period": "2012-2019", "event": "left after watching Sofia grow up through a phone screen"}},
    {"kind": "place", "canonical": "Portland", "aliases": ["home", "where we live"], "sheet": {"moved": 2019}},
    {"kind": "place", "canonical": "Tucson", "aliases": ["where I grew up", "home town"], "sheet": {"period": "1989-2011"}},
    {"kind": "item", "canonical": "Police Report #21-47832", "aliases": ["the police report", "the PD case"], "sheet": {"type": "document", "regarding": "Alex Chen embezzlement"}},
    {"kind": "item", "canonical": "Chase Business Statements", "aliases": ["the bank statements", "the account records"], "sheet": {"type": "document", "period": "June-July 2021"}},
    {"kind": "guest", "canonical": "Bill Cipher of Trust", "aliases": ["the betrayal pattern", "the thing Alex did that Dad also did"], "sheet": {"meaning": "the pattern Elena sees — people she trusts disappear with something valuable"}},
]

# Canon facts — Elena's life decisions, beliefs, fears, and body signals.
# Each maps to a domain from the original simulation.

CANON_FACTS = [
    # choice→consequence (5)
    {"fact": "Chose CS over pre-med — mother went silent for three months", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Kept Sofia — joy and constraint became the same word", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Gave Alex access to the business account — lost $40k and two years to lawyers", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Turned down Google offer — chose stability over status, Portland over Mountain View", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Started therapy in 2023 — named the flight pattern for the first time", "status": "DRAFT", "domain": "choice→consequence"},

    # memory→lesson (5)
    {"fact": "The Meridian promotion taught her that watching Sofia grow up through a phone screen was the actual cost", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Alex's small transfers under the $5k review threshold taught her that trust without oversight is negligence", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "The day she said no without guilt was when therapy started working", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "The kitchen tears Sofia saw were not weakness — they were the sound a person makes when they stop pretending", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Running gives her the one hour where the mind follows the body instead of leading it", "status": "DRAFT", "domain": "memory→lesson"},

    # belief→evidence (4)
    {"fact": "People deserve second chances — evidence: Sofia's forgiveness after the absent years", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "You can't outwork a broken model — evidence: the Meridian pivot, 70-hour weeks that built someone else's dream", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "I am a good mother — 3 independent sources: self-assessment, Sofia's school essay, Dr. Okafor's session notes", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "Silence is not peace — evidence: the three months after the CS choice, the two years after Alex", "status": "DRAFT", "domain": "belief→evidence"},

    # body→signal (4)
    {"fact": "Migraines mean she overrode her own no", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "Insomnia is hypervigilance — the body standing guard after Alex", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "Running is the only hour of silence — the body's substitute for meditation she can't sit still for", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "Back pain was a chair, not willpower — the fix was ergonomic, not moral", "status": "DRAFT", "domain": "body→signal"},

    # fear→truth (4)
    {"fact": "I am becoming my father — but I am here every day", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "NovaBridge will fail — but I built everything from nothing once already", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "Sofia will resent the absent years — but she wrote an essay about her mom's hands", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "I will never trust a business partner again — but I hired Employee #5 last month", "status": "DRAFT", "domain": "fear→truth"},

    # decision→decision (4)
    {"fact": "People deserve second chances", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "I can never trust a business partner again", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "Overwork is the wound, not the treatment", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "Silence is not peace — it is the sound of someone deciding whether to leave", "status": "PENDING", "domain": "decision→decision"},

    # year→milestone (12)
    {"fact": "1989 — Born in Tucson, AZ", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2007 — Chose CS over pre-med; mother's silence began", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2011 — Graduated, left Tucson for Seattle", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2012 — Started at Meridian Technologies", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2015 — Sofia born", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2017 — Meridian promotion; the phone-screen parenthood began", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2019 — Left Meridian, moved to Portland with Sofia", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2020 — Met Alex Chen; NovaBridge partnership began", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2021 — Alex embezzlement discovered; $40k gone; police report filed", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2022 — NovaBridge LLC refounded as sole owner", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2023 — Started therapy with Dr. Okafor", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2024 — Hired Employee #5; the trust experiment", "status": "DRAFT", "domain": "year→milestone"},

    # entity→entity (14) — these are resolution facts, not beliefs
    {"fact": "'Mom' resolves to Elena Vasquez", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'my kid' resolves to Sofia Vasquez", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'that guy who stole from me' resolves to Alex Chen", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the company' resolves to NovaBridge LLC", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'my old job' resolves to Meridian Technologies", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'my therapist' resolves to Dr. Okafor", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'my father' resolves to Elena's Father (estranged)", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'Mamá' resolves to Elena's Mother", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'home' resolves to Portland (since 2019)", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'where I grew up' resolves to Tucson", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the police report' resolves to Portland PD case #21-47832", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the bank statements' resolves to Chase Business checking, June-July 2021", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the betrayal pattern' resolves to the thing Alex did that Dad also did — people she trusts disappear with something valuable", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "Alex's text about a dinner that never happened — human_statement evidence on the betrayal", "status": "DRAFT", "domain": "entity→entity"},
]

# Rulings — the decision graph edges from the original simulation (13 edges).
RULINGS = [
    # contradicts (4)
    {"text": "CONTRADICTION: 'People deserve second chances' vs 'I can never trust a business partner again'", "scope": "canon"},
    {"text": "CONTRADICTION: 'Overwork is the wound' vs 'Said yes to every gig in NovaBridge's first year'", "scope": "canon"},
    {"text": "CONTRADICTION: 'Silence is not peace' vs 'Gave her own mother the silent treatment after the CS choice'", "scope": "canon"},
    {"text": "CONTRADICTION: 'Burnout lesson learned at Meridian' vs 'Rebuilt the same 60-hour pattern at NovaBridge'", "scope": "canon"},

    # supersedes (3)
    {"text": "SUPERSEDES: Turning down Google supersedes the Meridian promotion-chasing pattern", "scope": "rule"},
    {"text": "SUPERSEDES: Starting therapy supersedes the Portland flight (moving was running, not arriving)", "scope": "rule"},
    {"text": "SUPERSEDES: Hiring Employee #5 supersedes the Alex wound (trust attempted again)", "scope": "rule"},

    # refines (3)
    {"text": "REFINES: Migraines refined burnout from abstract concept to body knowledge", "scope": "rule"},
    {"text": "REFINES: Sofia's essay refined the 'bad mother' fear into something measurable", "scope": "rule"},
    {"text": "REFINES: Dr. Okafor refined hypervigilance from character flaw to trauma response", "scope": "rule"},

    # cross-domain contradicts (3)
    {"text": "CROSS-DOMAIN: Memory of Meridian overwork contradicts current NovaBridge overwork", "scope": "session"},
    {"text": "CROSS-DOMAIN: Fear of becoming father contradicts evidence of daily presence", "scope": "session"},
    {"text": "CROSS-DOMAIN: Body signal (migraines = overriding no) contradicts choice (said yes to every gig)", "scope": "session"},
]

# Jeles gaps — unresolved questions (18 from the original simulation).
GAPS = [
    "Will Sofia forgive the absent years?",
    "Should she contact her father?",
    "Is NovaBridge for the right reasons or running again?",
    "Is trust possible after Alex?",
    "Why does she still check the account three times a day?",
    "What would she do if NovaBridge failed tomorrow?",
    "Did her mother ever forgive the CS choice?",
    "Is she repeating her father's pattern?",
    "What does 'enough' look like?",
    "Will the migraines return if she stops running?",
    "Does Sofia know about Alex?",
    "Is the therapist helping or just witnessing?",
    "Can she build something without burning it as fuel?",
    "What would she tell her 2012 self?",
    "Is Portland home or just not-Tucson?",
    "Does Employee #5 know they are the trust experiment?",
    "What happens when Sofia asks about her grandfather?",
    "Is the running replacing the meditation or replacing the flight?",
]


def populate(con: sqlite3.Connection):
    now = datetime.now(timezone.utc).isoformat()
    ledger_id = [0]
    prev_hash = [GENESIS]

    def write_ledger(session, kind, note, state_dict):
        ledger_id[0] += 1
        ts = now
        state = json.dumps(state_dict, ensure_ascii=False)
        h = row_hash(ledger_id[0], ts, session, kind, note, state, prev_hash[0])
        con.execute(
            "INSERT INTO ledger (id, ts, session, kind, note, state, prev_hash, hash) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (ledger_id[0], ts, session, kind, note, state, prev_hash[0], h),
        )
        prev_hash[0] = h
        return ledger_id[0]

    # Session 0: Entity registration
    lid = write_ledger(0, "session_open", "Entity registration — who is in Elena's life", {})
    for ent in ENTITIES:
        con.execute(
            "INSERT INTO entities (kind, canonical, aliases, sheet, sealed_by, introduced_ledger_id) "
            "VALUES (?,?,?,?,?,?)",
            (ent["kind"], ent["canonical"], json.dumps(ent["aliases"]),
             json.dumps(ent.get("sheet", {})),
             None,
             lid),
        )
    write_ledger(0, "session_close", f"Registered {len(ENTITIES)} entities", {"entity_count": len(ENTITIES)})

    # Session 1: Life facts as canon — organized by domain
    domains_seen = {}
    lid = write_ledger(1, "session_open", "Elena's life — 52 facts across 8 domains", {})
    for fact in CANON_FACTS:
        domain = fact["domain"]
        domains_seen[domain] = domains_seen.get(domain, 0) + 1
        con.execute(
            "INSERT INTO canon (ts, fact, status, proposed_by, reason) VALUES (?,?,?,?,?)",
            (now, fact["fact"], fact["status"], "life-simulation-probe", domain),
        )
    write_ledger(1, "turn", f"Wrote {len(CANON_FACTS)} canon facts across {len(domains_seen)} domains",
                 {"facts": len(CANON_FACTS), "domains": domains_seen})
    write_ledger(1, "session_close", "All facts written — none sealed (the machine proposes, it does not confirm)", {})

    # Session 2: Rulings — the decision graph edges
    lid = write_ledger(2, "session_open", "Decision graph — 13 edges (contradicts, supersedes, refines)", {})
    for ruling in RULINGS:
        con.execute(
            "INSERT INTO rulings (ts, text, scope, signer, ledger_id) VALUES (?,?,?,?,?)",
            (now, ruling["text"], ruling["scope"], "", lid),
        )
    write_ledger(2, "turn", f"Wrote {len(RULINGS)} rulings — all unsigned (proposed, not confirmed)",
                 {"rulings": len(RULINGS), "signed": 0})
    write_ledger(2, "session_close", "Decision graph complete — no ruling is signed", {})

    # Session 3: The gaps — what remains unresolved
    lid = write_ledger(3, "session_open", "Unresolved questions — 18 gaps from the life", {})
    for gap in GAPS:
        con.execute(
            "INSERT INTO canon (ts, fact, status, proposed_by, reason) VALUES (?,?,?,?,?)",
            (now, f"UNRESOLVED: {gap}", "PENDING", "life-simulation-probe", "jeles-gap"),
        )
    write_ledger(3, "turn", f"Wrote {len(GAPS)} unresolved questions as PENDING canon",
                 {"gaps": len(GAPS)})
    write_ledger(3, "session_close", "Gaps recorded — each one is a question nobody has answered yet", {})

    con.commit()


def verify(db_path: str):
    sys.path.insert(0, str(SCRATCHPAD))
    from verify_ledger import verify_chain, verify_canon, report_rulings
    code, detail = verify_chain(db_path)
    print(f"  ledger chain: {detail}")
    if code != 0:
        return code
    code, detail = verify_canon(db_path)
    print(f"  canon guard:  {detail}")
    _, detail = report_rulings(db_path)
    print(f"  {detail}")
    return code


def report(db_path: str):
    con = sqlite3.connect(db_path)

    # Canon stats
    rows = con.execute("SELECT status, COUNT(*) FROM canon GROUP BY status").fetchall()
    print("\n=== Canon ===")
    total = 0
    for status, count in rows:
        print(f"  {status}: {count}")
        total += count
    print(f"  total: {total}")

    # Sealed check
    sealed = con.execute("SELECT COUNT(*) FROM canon WHERE status='SEALED'").fetchone()[0]
    rejected = con.execute("SELECT COUNT(*) FROM canon WHERE status='REJECTED'").fetchone()[0]
    print(f"\n  Machine-sealed: {sealed} (must be 0)")
    print(f"  Machine-rejected: {rejected} (must be 0)")

    # Entity stats
    ent_rows = con.execute("SELECT kind, COUNT(*) FROM entities GROUP BY kind").fetchall()
    print("\n=== Entities ===")
    for kind, count in ent_rows:
        print(f"  {kind}: {count}")

    # Guest check
    guest = con.execute("SELECT canonical, sealed_by FROM entities WHERE kind='guest'").fetchall()
    print(f"\n  Guests: {len(guest)}")
    for name, sealed_by in guest:
        seal_status = f"sealed by {sealed_by}" if sealed_by else "unsealed (proposed)"
        print(f"    {name} — {seal_status}")

    # Rulings
    ruling_rows = con.execute(
        "SELECT scope, COUNT(*), SUM(CASE WHEN signer != '' THEN 1 ELSE 0 END) "
        "FROM rulings WHERE invalid_at IS NULL GROUP BY scope"
    ).fetchall()
    print("\n=== Rulings ===")
    for scope, count, signed in ruling_rows:
        print(f"  {scope}: {count} ({signed} signed)")

    # Ledger
    ledger_count = con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    head = con.execute("SELECT hash FROM ledger ORDER BY id DESC LIMIT 1").fetchone()
    print(f"\n=== Ledger ===")
    print(f"  entries: {ledger_count}")
    print(f"  head: {head[0][:16]}..." if head else "  head: (empty)")

    # The three-tier check from the life simulation rerun
    print("\n=== Three-Tier Model ===")
    draft = con.execute("SELECT COUNT(*) FROM canon WHERE status='DRAFT'").fetchone()[0]
    pending = con.execute("SELECT COUNT(*) FROM canon WHERE status='PENDING'").fetchone()[0]
    print(f"  Experiencing (DRAFT):  {draft} facts — stored, queryable, not yet confronted")
    print(f"  Attending (PENDING):   {pending} facts — proposed, awaiting a human's attention")
    print(f"  Verifying (SEALED):    {sealed} facts — a named human confirmed this is true")
    print(f"  Refused (REJECTED):    {rejected} facts — a named human said this is not true")

    # Contradiction check
    contradictions = con.execute(
        "SELECT text FROM rulings WHERE text LIKE 'CONTRADICTION:%' AND invalid_at IS NULL"
    ).fetchall()
    print(f"\n=== Unresolved Contradictions ===")
    print(f"  {len(contradictions)} contradictions exist in the ruling graph")
    print(f"  All unsigned — the machine recorded them, nobody has confronted them")
    for (text,) in contradictions:
        print(f"    • {text[15:]}")  # strip 'CONTRADICTION: '

    # Gaps
    gap_count = con.execute("SELECT COUNT(*) FROM canon WHERE reason='jeles-gap'").fetchone()[0]
    print(f"\n=== Open Questions ===")
    print(f"  {gap_count} unresolved questions — each one PENDING, awaiting attention")

    con.close()


def main():
    print("==> Provisioning Elena's life sandbox")
    provision()

    print("\n==> Populating campaign.db")
    con = sqlite3.connect(str(DB))
    populate(con)
    con.close()

    print("\n==> Verifying (tamper-evidence + covenant guards)")
    code = verify(str(DB))
    if code != 0:
        print(f"\n!! VERIFICATION FAILED (exit {code})")
        return code

    print("\n  OK — the book is honest.")
    report(str(DB))

    # The key finding
    print("\n" + "=" * 60)
    print("THE GM LENS")
    print("=" * 60)
    print("""
The AI Game Master schema adds three things Elena's Nestor store lacks:

1. LIFECYCLE STATE MACHINE
   Every fact is PENDING or DRAFT — the machine wrote them all.
   SEALED and REJECTED require a named human in sealed_by.
   The NOT_A_PERSON guard ('', 'system', 'machine', 'ai', 'claude',
   'model', 'auto', 'none', 'null') structurally prevents what
   Nestor prevents by convention: a machine confirming a life.

2. ENTITY RESOLUTION WITH GUESTS
   "the betrayal pattern" is a GUEST — something that walked into
   Elena's life from outside the normal cast, the way Bill Cipher
   walked into the Vander valley. A pattern Elena sees (people she
   trusts disappear with something valuable) entered as a guest and
   was recognized as a recurring character. It can only become canon
   if a named human seals it.

3. RULINGS THAT SUPERSEDE
   The 13 decision-graph edges are RULINGS — unsigned, proposed.
   "Therapy supersedes the Portland flight" is not a sealed truth,
   it's a proposed adjudication. The DM (Elena, or her therapist)
   can sign it, refuse it, or supersede it with a better reading.
   The old ruling stays in the table, dated out — corrections land
   beside the record, never on top of it.

The thesis translates:
  "An AI Game Master is a yes-and bookkeeper, not a rules referee."
  →
  "A life simulation is a yes-and witness, not a diagnostic engine."
  It proposes, remembers, and keeps an honest book.
  It does not tell Elena what her fears mean.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
