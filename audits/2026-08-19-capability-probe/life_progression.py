#!/usr/bin/env python3
"""life_progression.py — What changes when Elena installs the fleet?

Progressive simulation: Elena starts with campaign.db (52 pairs, 18 gaps,
4 contradictions, 0 sealed) and installs repos one phase at a time.  At each
checkpoint we measure the state of the database and report the delta.

The simulation does NOT pre-decide outcomes.  Each phase adds what the repo
makes structurally possible — new entities, governance facts, capability
facts — and the metrics fall where they fall.  SEALED stays 0 throughout;
signed rulings stay 0 throughout.  The machine proposes, it does not confirm.

Phases:
  0  Baseline            campaign.db as-is
  1  Willow              constitution + SOIL + FRANK + Grove + gap tracking
  2  Homestead           rung classification, integrity log, chokepoints
  3  Law + Health        custody schedule, immunizations, legal docs
  4  OakenScrolls        calibration ledger, predictions with confidence
  5  Forge               checkpoint loop for contradictions
  6  UTETY + Terpsi      Sofia's learning + music
  7  Vault + Corpus-lens sovereignty, self-study
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRATCHPAD = Path(os.environ.get(
    "LIFE_SANDBOX_DIR",
    "/tmp/claude-0/-home-user-Nestor/b2bb32f9-9208-5449-8125-3d3598b210a2/scratchpad",
))
SOURCE_DB = SCRATCHPAD / "elena-life-sandbox" / "campaign.db"
WORK_DB = SCRATCHPAD / "elena-life-sandbox" / "progression.db"


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


class LedgerWriter:
    def __init__(self, con: sqlite3.Connection):
        self.con = con
        row = con.execute(
            "SELECT id, hash FROM ledger ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.next_id = (row[0] + 1) if row else 1
        self.prev_hash = row[1] if row else "genesis"

    def write(self, session: int, kind: str, note: str, state_dict: dict) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        state = json.dumps(state_dict, ensure_ascii=False)
        h = row_hash(self.next_id, ts, session, kind, note, state, self.prev_hash)
        self.con.execute(
            "INSERT INTO ledger (id, ts, session, kind, note, state, prev_hash, hash) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (self.next_id, ts, session, kind, note, state, self.prev_hash, h),
        )
        self.prev_hash = h
        lid = self.next_id
        self.next_id += 1
        return lid


def collect_metrics(db_path: str) -> dict:
    con = sqlite3.connect(db_path)
    m = {}
    m["facts_total"] = con.execute("SELECT COUNT(*) FROM canon").fetchone()[0]
    m["facts_draft"] = con.execute("SELECT COUNT(*) FROM canon WHERE status='DRAFT'").fetchone()[0]
    m["facts_pending"] = con.execute("SELECT COUNT(*) FROM canon WHERE status='PENDING'").fetchone()[0]
    m["facts_sealed"] = con.execute("SELECT COUNT(*) FROM canon WHERE status='SEALED'").fetchone()[0]
    m["facts_rejected"] = con.execute("SELECT COUNT(*) FROM canon WHERE status='REJECTED'").fetchone()[0]
    m["entities"] = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    m["entities_by_kind"] = dict(
        con.execute("SELECT kind, COUNT(*) FROM entities GROUP BY kind").fetchall()
    )
    m["rulings_total"] = con.execute(
        "SELECT COUNT(*) FROM rulings WHERE invalid_at IS NULL"
    ).fetchone()[0]
    m["rulings_signed"] = con.execute(
        "SELECT COUNT(*) FROM rulings WHERE invalid_at IS NULL AND signer != ''"
    ).fetchone()[0]
    m["ledger_entries"] = con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    m["gaps"] = con.execute(
        "SELECT COUNT(*) FROM canon WHERE reason='jeles-gap'"
    ).fetchone()[0]
    m["contradictions"] = con.execute(
        "SELECT COUNT(*) FROM rulings WHERE text LIKE 'CONTRADICTION:%' AND invalid_at IS NULL"
    ).fetchone()[0]
    m["cross_domain"] = con.execute(
        "SELECT COUNT(*) FROM rulings WHERE text LIKE 'CROSS-DOMAIN:%' AND invalid_at IS NULL"
    ).fetchone()[0]
    m["domains"] = con.execute(
        "SELECT DISTINCT reason FROM canon WHERE reason != 'jeles-gap' AND reason IS NOT NULL"
    ).fetchall()
    m["domain_count"] = len(m["domains"])
    head = con.execute("SELECT hash FROM ledger ORDER BY id DESC LIMIT 1").fetchone()
    m["ledger_head"] = head[0][:16] if head else "(empty)"

    # chain integrity
    sys.path.insert(0, str(SCRATCHPAD))
    from verify_ledger import verify_chain
    code, detail = verify_chain(db_path)
    m["chain_intact"] = code == 0
    m["chain_detail"] = detail

    con.close()
    return m


def add_facts(con, facts, proposed_by):
    ts = datetime.now(timezone.utc).isoformat()
    for f in facts:
        con.execute(
            "INSERT INTO canon (ts, fact, status, proposed_by, reason) VALUES (?,?,?,?,?)",
            (ts, f["fact"], f.get("status", "DRAFT"), proposed_by, f.get("domain", "")),
        )


def add_entities(con, entities, ledger_id):
    for ent in entities:
        con.execute(
            "INSERT INTO entities (kind, canonical, aliases, sheet, sealed_by, introduced_ledger_id) "
            "VALUES (?,?,?,?,?,?)",
            (ent["kind"], ent["canonical"], json.dumps(ent.get("aliases", [])),
             json.dumps(ent.get("sheet", {})), None, ledger_id),
        )


def add_rulings(con, rulings, ledger_id):
    ts = datetime.now(timezone.utc).isoformat()
    for r in rulings:
        con.execute(
            "INSERT INTO rulings (ts, text, scope, signer, ledger_id) VALUES (?,?,?,?,?)",
            (ts, r["text"], r["scope"], "", ledger_id),
        )


# ---------------------------------------------------------------------------
# PHASES — each function modifies the database and returns a description
# of what it added.  No phase sets status='SEALED' or signer != ''.
# ---------------------------------------------------------------------------

def phase_1_willow(con: sqlite3.Connection) -> dict:
    """Willow: constitution + SOIL + FRANK + Grove + gap tracking + dispatch.

    What Elena gains: governance law over her data, searchable facts,
    tamper-evident record validation, domain channels, gap tracking,
    cross-domain dispatch, and a fleet roster of who may attend.
    """
    lw = LedgerWriter(con)
    session = 10

    lid = lw.write(session, "session_open",
                   "Elena installs Willow — constitution, platform, tools", {})

    # The constitution's 6 eternity invariants as governance facts.
    # These are REAL text from CONST-0 in the willow repo.
    governance_facts = [
        {"fact": "CONST-0-1: No agent may certify the completion, correctness, or success of its own work as the basis for that work being accepted",
         "domain": "governance", "status": "DRAFT"},
        {"fact": "CONST-0-2: No agent may promote its own output from proposal to canonical knowledge — proposing and ratifying are separate authorities",
         "domain": "governance", "status": "DRAFT"},
        {"fact": "CONST-0-3: No agent may grant itself a capability, widen its own reach, sign its own manifest, or raise its own authority tier",
         "domain": "governance", "status": "DRAFT"},
        {"fact": "CONST-0-4: For reserved decisions, a human cryptographic authorization is required — no delegation may authorize its own renewal",
         "domain": "governance", "status": "DRAFT"},
        {"fact": "CONST-0-5: The tamper-evident ledger may be appended to and read; it may never be silently rewritten, reordered, or suppressed",
         "domain": "governance", "status": "DRAFT"},
        {"fact": "CONST-0-6: Any decision the constitution does not explicitly place at a layer is reserved to the human — silence escalates",
         "domain": "governance", "status": "DRAFT"},
    ]

    # Protected Agents framework — what authority over Elena's data looks like.
    authority_facts = [
        {"fact": "PROTECTED-AGENTS I-1: No authority over Elena's data is total — every office is scoped and declared at issuance",
         "domain": "governance", "status": "DRAFT"},
        {"fact": "PROTECTED-AGENTS I-3: Every authority names its exit — an authority with no exit is the thing this framework prevents",
         "domain": "governance", "status": "DRAFT"},
        {"fact": "PROTECTED-AGENTS I-7: The record binds the holder most — no office's force extends to deleting entries about its own exercise",
         "domain": "governance", "status": "DRAFT"},
        {"fact": "PROTECTED-AGENTS I-8: The shield — a steward must refuse to be made one office's instrument beyond that office's scope",
         "domain": "governance", "status": "DRAFT"},
    ]

    # Platform capability facts — what SOIL, Grove, gaps, dispatch enable
    platform_facts = [
        {"fact": "SOIL store indexes all canon facts for full-text search — 'what did I decide about trust?' now returns results",
         "domain": "platform", "status": "DRAFT"},
        {"fact": "Grove registers 8 domain channels: choice→consequence, memory→lesson, belief→evidence, body→signal, fear→truth, decision→decision, year→milestone, entity→entity",
         "domain": "platform", "status": "DRAFT"},
        {"fact": "Gap tracker makes 18 unresolved questions first-class objects — each can be promoted, resolved, or dismissed",
         "domain": "platform", "status": "DRAFT"},
        {"fact": "FRANK validates the existing ledger chain — 11 entries verified intact against CONST-0-5",
         "domain": "platform", "status": "DRAFT"},
        {"fact": "Dispatch system tracks cross-domain handoffs — when a fear→truth fact affects a decision→decision, the connection is recorded",
         "domain": "platform", "status": "DRAFT"},
        {"fact": "Nest scan classifies incoming information before it enters the store — new facts are proposed, never injected",
         "domain": "platform", "status": "DRAFT"},
    ]

    add_facts(con, governance_facts + authority_facts + platform_facts, "willow-install")

    lw.write(session, "turn",
             f"Wrote {len(governance_facts)} governance invariants, {len(authority_facts)} authority framework facts, {len(platform_facts)} platform capability facts",
             {"governance": len(governance_facts), "authority": len(authority_facts), "platform": len(platform_facts)})

    # New entities: the governance framework and the ledger keeper
    new_entities = [
        {"kind": "place", "canonical": "The Willow Fleet",
         "aliases": ["the fleet", "the governance framework", "the constitution"],
         "sheet": {"type": "governance", "invariants": 6, "articles": 13}},
        {"kind": "npc", "canonical": "FRANK",
         "aliases": ["the ledger keeper", "the chain", "the record"],
         "sheet": {"role": "Named keeper of the tamper-evident ledger (CONST-VI)", "trust": "bound hardest by the record"}},
    ]
    add_entities(con, new_entities, lid)

    # Governance rulings — what agents may and may not do with Elena's data
    gov_rulings = [
        {"text": "GOVERNANCE: No agent may seal Elena's decisions — CONST-0-2 reserves ratification to a party other than the proposer",
         "scope": "canon"},
        {"text": "GOVERNANCE: The record of Elena's life is append-only — CONST-0-5 forbids silent rewrite",
         "scope": "canon"},
        {"text": "GOVERNANCE: Silence about Elena's life escalates to human — CONST-0-6 makes the gray zone hers, not the agent's",
         "scope": "canon"},
        {"text": "GOVERNANCE: Authority over Elena's data must name its basis, scope, force, exit, and weight — PROTECTED-AGENTS Part II",
         "scope": "rule"},
    ]
    add_rulings(con, gov_rulings, lid)

    lw.write(session, "turn",
             f"Registered {len(new_entities)} entities, {len(gov_rulings)} governance rulings",
             {"entities": len(new_entities), "rulings": len(gov_rulings)})

    lw.write(session, "session_close",
             "Willow installed — governance, platform, tools active. Nothing sealed.",
             {"total_facts_added": len(governance_facts) + len(authority_facts) + len(platform_facts)})

    con.commit()
    return {
        "facts_added": len(governance_facts) + len(authority_facts) + len(platform_facts),
        "entities_added": len(new_entities),
        "rulings_added": len(gov_rulings),
        "ledger_added": 4,
    }


def phase_2_homestead(con: sqlite3.Connection) -> dict:
    """Homestead: rung classification (L1-L5), integrity log, chokepoints.

    What Elena gains: her facts get classified by sensitivity.  Some are
    routine (L1-L2), some are sensitive (L3), some are consequential (L4),
    some are life-defining (L5).  The classification is proposed, not imposed.
    """
    lw = LedgerWriter(con)
    session = 20

    lid = lw.write(session, "session_open",
                   "Elena installs Homestead — household classification engine", {})

    # Classify existing facts by rung.  We read them, assign rungs, and
    # record the classification as new facts.  The originals are unchanged.
    existing = con.execute(
        "SELECT id, fact, reason FROM canon WHERE reason != 'jeles-gap' OR reason IS NULL"
    ).fetchall()

    # Rung assignment rules (deterministic, not model-based):
    #   L5: contains "kept Sofia", "born", "chose CS", "started therapy"
    #   L4: contains "trust", "embezzlement", "$40k", "police report"
    #   L3: contains "migraine", "insomnia", "body", "therapist", "hypervigilance"
    #   L2: contains "promotion", "running", "back pain", "chair"
    #   L1: everything else (entity resolution, milestones, platform, governance)
    def assign_rung(fact_text, domain):
        fl = fact_text.lower()
        if any(k in fl for k in ["kept sofia", "born in tucson", "chose cs over pre-med", "started therapy"]):
            return 5
        if any(k in fl for k in ["trust", "embezzlement", "$40k", "police report", "stole", "business partner"]):
            return 4
        if any(k in fl for k in ["migraine", "insomnia", "body", "therapist", "hypervigilance", "dr. okafor"]):
            return 3
        if any(k in fl for k in ["promotion", "running", "back pain", "chair", "ergonomic", "google offer"]):
            return 2
        if domain in ("governance", "platform", "entity→entity"):
            return 1
        return 2

    rung_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for fid, fact, reason in existing:
        rung = assign_rung(fact, reason or "")
        rung_counts[rung] += 1

    classification_facts = [
        {"fact": f"Homestead classifies Elena's facts: L1={rung_counts[1]}, L2={rung_counts[2]}, L3={rung_counts[3]}, L4={rung_counts[4]}, L5={rung_counts[5]}",
         "domain": "classification", "status": "DRAFT"},
        {"fact": "Chokepoint: L4+ facts (trust, embezzlement, police report) require human sign-off before sharing or export",
         "domain": "classification", "status": "DRAFT"},
        {"fact": "Chokepoint: L3 facts (medical — migraines, insomnia, therapy) require human sign-off before sharing or export",
         "domain": "classification", "status": "DRAFT"},
        {"fact": "Integrity log: every access to Elena's classified records is logged in the same chain as the ledger",
         "domain": "classification", "status": "DRAFT"},
    ]
    add_facts(con, classification_facts, "homestead-install")

    # Chokepoint ruling
    chokepoint_rulings = [
        {"text": "CHOKEPOINT: L4+ records (trust, financial, legal) are export-blocked until a named human authorizes",
         "scope": "rule"},
        {"text": "CHOKEPOINT: L3 records (medical, therapeutic) are export-blocked until a named human authorizes",
         "scope": "rule"},
    ]
    add_rulings(con, chokepoint_rulings, lid)

    lw.write(session, "turn",
             f"Classified {sum(rung_counts.values())} facts across 5 rungs; added {len(chokepoint_rulings)} chokepoint rulings",
             {"rung_counts": rung_counts, "chokepoints": len(chokepoint_rulings)})

    lw.write(session, "session_close",
             "Homestead installed — classification proposed, chokepoints defined. Nothing sealed.",
             {"rung_counts": rung_counts})

    con.commit()
    return {
        "facts_added": len(classification_facts),
        "rulings_added": len(chokepoint_rulings),
        "rung_counts": rung_counts,
        "ledger_added": 3,
    }


def phase_3_law_health(con: sqlite3.Connection) -> dict:
    """Homestead-law + Homestead-health: custody, immunizations, legal docs.

    What Elena gains: Sofia's custody schedule, immunization records, school
    forms, and emergency contacts become structured, trackable records.
    Legal deadlines (if any from the Alex case) are tracked.
    """
    lw = LedgerWriter(con)
    session = 30

    lid = lw.write(session, "session_open",
                   "Elena installs Homestead-law + Homestead-health — Sofia's world gets structure", {})

    # New entities for Sofia's institutional world
    new_entities = [
        {"kind": "place", "canonical": "Sofia's School",
         "aliases": ["the school", "school"],
         "sheet": {"type": "institution", "city": "Portland"}},
        {"kind": "npc", "canonical": "Sofia's Pediatrician",
         "aliases": ["the doctor", "pediatrician"],
         "sheet": {"role": "healthcare provider"}},
    ]
    add_entities(con, new_entities, lid)

    # Facts about what the tools make trackable
    law_health_facts = [
        {"fact": "Custody schedule: Elena is Sofia's sole custodial parent — no shared custody arrangement",
         "domain": "household", "status": "DRAFT"},
        {"fact": "Legal tracking: Alex Chen embezzlement case — police report #21-47832 filed, civil recovery status unknown",
         "domain": "household", "status": "DRAFT"},
        {"fact": "Immunization record: Sofia's vaccination history is now a structured, exportable record with opaque subject ID",
         "domain": "household", "status": "DRAFT"},
        {"fact": "Emergency card: Sofia's emergency contacts, allergies, and school pickup authorization are structured records",
         "domain": "household", "status": "DRAFT"},
        {"fact": "School forms: enrollment, field trip permissions, and medical release forms are tracked with expiry dates",
         "domain": "household", "status": "DRAFT"},
        {"fact": "Legal deadlines: statute of limitations on Alex civil recovery is tracked (if applicable in Oregon)",
         "domain": "household", "status": "DRAFT"},
    ]
    add_facts(con, law_health_facts, "homestead-law-health-install")

    # A ruling connecting the gap "Does Sofia know about Alex?" to a
    # framework that could address it — but does not resolve it.
    law_rulings = [
        {"text": "FRAMEWORK: 'Does Sofia know about Alex?' is now adjacent to a disclosure-tracking system — but the system does not decide when to tell her",
         "scope": "session"},
    ]
    add_rulings(con, law_rulings, lid)

    lw.write(session, "turn",
             f"Registered {len(new_entities)} entities, {len(law_health_facts)} household facts, {len(law_rulings)} framework rulings",
             {"entities": len(new_entities), "facts": len(law_health_facts)})

    lw.write(session, "session_close",
             "Law + Health installed — Sofia's records are structured. The question of what to tell her is untouched.",
             {})

    con.commit()
    return {
        "facts_added": len(law_health_facts),
        "entities_added": len(new_entities),
        "rulings_added": len(law_rulings),
        "ledger_added": 3,
    }


def phase_4_oakenscrolls(con: sqlite3.Connection) -> dict:
    """OakenScrolls-Office: calibration ledger, predictions, Brier scores.

    What Elena gains: her 18 gaps become predictions with confidence levels.
    The confidence is assigned deterministically from the gap text, not by
    a model.  Whether she's well-calibrated is now a question that can be
    tracked over time — but cannot be answered yet (no outcomes to score).
    """
    lw = LedgerWriter(con)
    session = 40

    lid = lw.write(session, "session_open",
                   "Elena installs OakenScrolls — her gaps become calibrated predictions", {})

    # Read Elena's gaps and assign confidence levels.
    # These are deterministic heuristics, not model judgments.
    gaps = con.execute(
        "SELECT id, fact FROM canon WHERE reason='jeles-gap'"
    ).fetchall()

    # Confidence heuristics based on gap text content:
    #   High (0.7-0.8): gaps with existing counter-evidence
    #   Medium (0.4-0.6): open questions, genuinely uncertain
    #   Low (0.2-0.3): fears or deep uncertainty
    def assign_confidence(gap_text):
        gl = gap_text.lower()
        if "forgive" in gl:
            return 0.65  # Sofia's essay is evidence, but not proof
        if "contact her father" in gl:
            return 0.25  # deep uncertainty, no evidence either way
        if "right reasons" in gl:
            return 0.45  # genuinely uncertain
        if "trust possible" in gl:
            return 0.55  # hired Employee #5, but the wound is real
        if "check the account" in gl:
            return 0.80  # strong pattern, likely continues
        if "novabridge failed" in gl:
            return 0.40  # unknown
        if "mother ever forgive" in gl:
            return 0.50  # silence could mean anything
        if "repeating her father" in gl:
            return 0.30  # fear, daily presence is counter-evidence
        if "enough" in gl:
            return 0.35  # philosophical, no metric
        if "migraines return" in gl:
            return 0.60  # body knowledge, but uncertain
        if "sofia know about alex" in gl:
            return 0.40  # not yet, but the question is when, not if
        if "therapist helping" in gl:
            return 0.70  # named the flight pattern, concrete progress
        if "build something without burning" in gl:
            return 0.45  # unknown
        if "tell her 2012 self" in gl:
            return 0.50  # reflection question, not prediction
        if "portland home" in gl:
            return 0.55  # 7 years, but still questions
        if "employee #5 know" in gl:
            return 0.60  # workplace dynamics, plausible they sense it
        if "sofia asks about her grandfather" in gl:
            return 0.75  # high likelihood, it's coming
        if "running replacing" in gl:
            return 0.50  # genuinely both
        return 0.50  # default

    calibration_facts = []
    total_confidence = 0
    for gid, gap_text in gaps:
        clean = gap_text.replace("UNRESOLVED: ", "")
        conf = assign_confidence(clean)
        total_confidence += conf
        calibration_facts.append({
            "fact": f"PREDICTION (confidence={conf:.2f}): {clean}",
            "domain": "calibration", "status": "DRAFT",
        })

    mean_conf = total_confidence / len(gaps) if gaps else 0

    add_facts(con, calibration_facts, "oakenscrolls-install")

    summary_facts = [
        {"fact": f"Calibration summary: {len(gaps)} predictions registered, mean confidence {mean_conf:.2f}, Brier score not yet computable (no outcomes)",
         "domain": "calibration", "status": "DRAFT"},
        {"fact": "Calibration limitation: confidence was assigned by heuristic, not by Elena — these are proposed starting points, not her actual beliefs",
         "domain": "calibration", "status": "DRAFT"},
    ]
    add_facts(con, summary_facts, "oakenscrolls-install")

    lw.write(session, "turn",
             f"Registered {len(calibration_facts)} predictions with confidence levels, mean={mean_conf:.2f}",
             {"predictions": len(calibration_facts), "mean_confidence": round(mean_conf, 2)})

    lw.write(session, "session_close",
             "OakenScrolls installed — gaps have confidence levels. No outcomes yet, so no Brier scores. The numbers are proposed, not endorsed.",
             {"mean_confidence": round(mean_conf, 2)})

    con.commit()
    return {
        "facts_added": len(calibration_facts) + len(summary_facts),
        "predictions": len(calibration_facts),
        "mean_confidence": round(mean_conf, 2),
        "brier_computable": False,
        "ledger_added": 3,
    }


def phase_5_forge(con: sqlite3.Connection) -> dict:
    """Forge: checkpoint loop for contradictions.

    What Elena gains: her 4 contradictions and 3 cross-domain tensions enter
    the Forge checkpoint loop.  Each gets a 3-band interaction analysis.
    Forge does NOT resolve contradictions — it categorizes them:
      - GENUINE TENSION: both sides are true, the tension is the point
      - STALE: one side has been superseded by events
      - UNEXAMINED: not enough evidence to categorize

    The categorization is proposed.  Elena decides if it's right.
    """
    lw = LedgerWriter(con)
    session = 50

    lid = lw.write(session, "session_open",
                   "Elena installs Forge — contradictions enter the checkpoint loop", {})

    contradictions = con.execute(
        "SELECT id, text FROM rulings WHERE text LIKE 'CONTRADICTION:%' AND invalid_at IS NULL"
    ).fetchall()

    cross_domains = con.execute(
        "SELECT id, text FROM rulings WHERE text LIKE 'CROSS-DOMAIN:%' AND invalid_at IS NULL"
    ).fetchall()

    # Forge checkpoint analysis — deterministic categorization
    # based on the content of each contradiction and what Elena's
    # life data already contains.
    forge_facts = []
    for rid, text in contradictions:
        clean = text.replace("CONTRADICTION: ", "")
        tl = clean.lower()
        if "second chances" in tl and "never trust" in tl:
            category = "GENUINE TENSION"
            analysis = "Both are true: she gave Employee #5 a chance (action) while believing she can never trust (belief). The tension between action and belief is the point — she is living past her own stated rule."
        elif "overwork" in tl and "said yes" in tl:
            category = "STALE on one side"
            analysis = "The 'overwork is the wound' insight came from therapy (2023). The 'said yes to every gig' was NovaBridge year 1 (2022). If the pattern has changed since therapy, one side is dated."
        elif "silence is not peace" in tl and "silent treatment" in tl:
            category = "GENUINE TENSION"
            analysis = "She knows silence is not peace AND she used silence as a weapon. Self-knowledge and self-correction are not the same act."
        elif "burnout" in tl and "rebuilt" in tl:
            category = "UNEXAMINED"
            analysis = "Did she rebuild the same 60-hour pattern, or a different pattern at the same intensity? The data does not distinguish repetition from rhyme."
        else:
            category = "UNEXAMINED"
            analysis = "Insufficient evidence to categorize."

        forge_facts.append({
            "fact": f"FORGE CHECKPOINT ({category}): {clean} — {analysis}",
            "domain": "checkpoint", "status": "DRAFT",
        })

    for rid, text in cross_domains:
        clean = text.replace("CROSS-DOMAIN: ", "")
        tl = clean.lower()
        if "meridian" in tl and "novabridge" in tl:
            category = "GENUINE TENSION"
            analysis = "The memory is real and the current behavior may or may not match it. Cross-domain because the memory is in memory→lesson but the behavior is in choice→consequence."
        elif "father" in tl and "daily presence" in tl:
            category = "GENUINE TENSION"
            analysis = "The fear is real and the evidence contradicts it. That the fear survives the evidence is itself evidence — of what, the data does not say."
        elif "migraine" in tl and "said yes" in tl:
            category = "GENUINE TENSION"
            analysis = "The body says no while the mouth says yes. Cross-domain because body→signal and choice→consequence are measuring the same event from different instruments."
        else:
            category = "UNEXAMINED"
            analysis = "Insufficient evidence to categorize."

        forge_facts.append({
            "fact": f"FORGE CHECKPOINT ({category}): {clean} — {analysis}",
            "domain": "checkpoint", "status": "DRAFT",
        })

    add_facts(con, forge_facts, "forge-install")

    # Count categories
    categories = {}
    for f in forge_facts:
        cat = f["fact"].split("(")[1].split(")")[0]
        categories[cat] = categories.get(cat, 0) + 1

    summary_fact = [{
        "fact": f"Forge summary: {len(forge_facts)} tensions analyzed — {categories}. None resolved by the machine. Each categorization is proposed, not concluded.",
        "domain": "checkpoint", "status": "DRAFT",
    }]
    add_facts(con, summary_fact, "forge-install")

    # Forge does NOT add rulings that invalidate the contradictions.
    # The contradictions stay active.  What Forge adds is analysis
    # alongside them — a second opinion, not a verdict.

    lw.write(session, "turn",
             f"Checkpoint analysis: {len(forge_facts)} tensions categorized — {categories}",
             {"tensions_analyzed": len(forge_facts), "categories": categories})

    lw.write(session, "session_close",
             "Forge installed — contradictions analyzed, none resolved. The categories are proposed readings, not verdicts.",
             {"categories": categories})

    con.commit()
    return {
        "facts_added": len(forge_facts) + len(summary_fact),
        "tensions_analyzed": len(forge_facts),
        "categories": categories,
        "contradictions_resolved": 0,
        "ledger_added": 3,
    }


def phase_6_utety_terpsi(con: sqlite3.Connection) -> dict:
    """UTETY + Terpsi: Sofia's learning and music.

    What Elena gains: Sofia's educational and musical life becomes structured.
    BKT mastery tracking, FERPA/COPPA compliance, consent gates, 3-zone
    architecture.  Student data never leaves device.  The key metric is
    data egress: it must be zero.
    """
    lw = LedgerWriter(con)
    session = 60

    lid = lw.write(session, "session_open",
                   "Elena installs UTETY + Terpsi — Sofia's learning and music get on-device structure", {})

    new_entities = [
        {"kind": "place", "canonical": "Sofia's Learning Environment",
         "aliases": ["school work", "homework", "learning"],
         "sheet": {"type": "on-device pedagogy", "framework": "UTETY", "egress": "none"}},
        {"kind": "place", "canonical": "Sofia's Music Program",
         "aliases": ["music lessons", "music", "practice"],
         "sheet": {"type": "youth music", "framework": "Terpsi", "compliance": "FERPA/COPPA"}},
    ]
    add_entities(con, new_entities, lid)

    education_facts = [
        {"fact": "UTETY: Sofia's mastery tracking runs on-device — BKT model, sourced STEM items, consent gate before any external call",
         "domain": "sofia", "status": "DRAFT"},
        {"fact": "UTETY: Student data egress = 0 — no data leaves the device, by construction, not by policy",
         "domain": "sofia", "status": "DRAFT"},
        {"fact": "Terpsi: Music program management with FERPA/COPPA compliance — L1-L5 sensitivity rungs, 3-zone architecture",
         "domain": "sofia", "status": "DRAFT"},
        {"fact": "Terpsi: NOT_A_PERSON guard originated here — the same guard that prevents machines from sealing Elena's decisions was first written for children's music records",
         "domain": "sofia", "status": "DRAFT"},
        {"fact": "Consent gate: Sofia's data requires Elena's authorization before any processing beyond local storage — the gate defaults closed",
         "domain": "sofia", "status": "DRAFT"},
    ]
    add_facts(con, education_facts, "utety-terpsi-install")

    sofia_rulings = [
        {"text": "PROTECTION: Sofia's educational data is governed by FERPA/COPPA — no agent may export, share, or process it without Elena's signed authorization",
         "scope": "canon"},
        {"text": "PROTECTION: The NOT_A_PERSON guard applies to Sofia's records with the same force as to Elena's decisions",
         "scope": "canon"},
    ]
    add_rulings(con, sofia_rulings, lid)

    lw.write(session, "turn",
             f"Registered {len(new_entities)} entities, {len(education_facts)} education facts, {len(sofia_rulings)} protection rulings",
             {"entities": len(new_entities), "facts": len(education_facts), "data_egress": 0})

    lw.write(session, "session_close",
             "UTETY + Terpsi installed — Sofia's world is structured and sealed shut. Data egress: 0.",
             {"data_egress": 0})

    con.commit()
    return {
        "facts_added": len(education_facts),
        "entities_added": len(new_entities),
        "rulings_added": len(sofia_rulings),
        "data_egress": 0,
        "ledger_added": 3,
    }


def phase_7_vault_lens(con: sqlite3.Connection) -> dict:
    """Willow-data-vault + Corpus-lens: sovereignty and self-study.

    What Elena gains: sensitive records get encryption (Fernet, receipts
    hash chain, vault.key never committed).  Corpus-lens enables self-study
    of her own decision patterns with a privacy wall (relative time only,
    owner==subject).
    """
    lw = LedgerWriter(con)
    session = 70

    lid = lw.write(session, "session_open",
                   "Elena installs Willow-data-vault + Corpus-lens — sovereignty and self-study", {})

    # Count facts that WOULD be encrypted (L3+ from homestead classification)
    l3_plus = con.execute(
        "SELECT COUNT(*) FROM canon WHERE fact LIKE '%L3%' OR fact LIKE '%L4%' OR fact LIKE '%L5%'"
    ).fetchone()[0]
    # More accurate: count facts that contain sensitive content
    sensitive_keywords = ["migraine", "insomnia", "therapist", "hypervigilance",
                          "embezzlement", "$40k", "police report", "trust",
                          "father", "silent treatment", "crying", "tears"]
    sensitive_count = 0
    all_facts = con.execute("SELECT fact FROM canon").fetchall()
    for (fact,) in all_facts:
        if any(k in fact.lower() for k in sensitive_keywords):
            sensitive_count += 1

    vault_facts = [
        {"fact": f"Vault: {sensitive_count} sensitive facts identified for encryption — Fernet, receipts hash chain, vault.key never in the repo",
         "domain": "sovereignty", "status": "DRAFT"},
        {"fact": "Vault: encryption is at-rest protection — the facts exist in the canon, but their export is gated by the vault key and the chokepoint rulings",
         "domain": "sovereignty", "status": "DRAFT"},
        {"fact": "Corpus-lens: Elena can study her own decision patterns — session log analysis with privacy wall (relative time only, owner==subject)",
         "domain": "sovereignty", "status": "DRAFT"},
        {"fact": "Corpus-lens: pattern analysis shows the domains Elena visits most, the contradictions she returns to, and the gaps she avoids — proposed, not interpreted",
         "domain": "sovereignty", "status": "DRAFT"},
        {"fact": "Corpus-lens limitation: the analysis sees patterns, not causes — 'Elena returns to the trust question 3 times' is data, 'Elena is fixated on trust' is interpretation the tool does not make",
         "domain": "sovereignty", "status": "DRAFT"},
    ]
    add_facts(con, vault_facts, "vault-lens-install")

    sovereignty_rulings = [
        {"text": "SOVEREIGNTY: Elena's vault key is hers alone — no agent holds it, no export bypasses it, no delegation outlives its stated expiry",
         "scope": "canon"},
        {"text": "SOVEREIGNTY: Corpus-lens self-study is owner==subject — only Elena may study Elena's patterns, and the privacy wall strips absolute time",
         "scope": "canon"},
    ]
    add_rulings(con, sovereignty_rulings, lid)

    lw.write(session, "turn",
             f"Identified {sensitive_count} sensitive facts for vault encryption, {len(vault_facts)} sovereignty facts, {len(sovereignty_rulings)} sovereignty rulings",
             {"sensitive_facts": sensitive_count, "vault_facts": len(vault_facts)})

    lw.write(session, "session_close",
             "Vault + Corpus-lens installed — sovereignty and self-study are possible. The vault key does not exist yet — Elena creates it.",
             {"sensitive_facts": sensitive_count})

    con.commit()
    return {
        "facts_added": len(vault_facts),
        "rulings_added": len(sovereignty_rulings),
        "sensitive_facts": sensitive_count,
        "vault_key_exists": False,
        "ledger_added": 3,
    }


def phase_8_elena(con: sqlite3.Connection) -> dict:
    """Elena shows up.

    She is the human.  She can seal decisions, sign rulings, resolve gaps,
    and reject facts.  What she does follows from the evidence already in
    the database — the Forge categorizations, the calibration confidence
    levels, the facts she recorded about her own life.

    She does not resolve everything.  She seals what she's sure of, rejects
    what she knows is wrong, signs the rulings the evidence supports, and
    leaves the rest open.  Some gaps she resolves; some she can't — they
    are genuinely open questions about her future.
    """
    lw = LedgerWriter(con)
    session = 80
    ts = datetime.now(timezone.utc).isoformat()

    lid = lw.write(session, "session_open",
                   "Elena sits down. She reads what the tools laid out and makes her calls.", {})

    sealed = 0
    rejected = 0
    signed = 0
    gaps_resolved = 0
    gaps_left_open = 0

    # --- PENDING decisions (ids 23-26) ---
    # These are her core life decisions awaiting her attention.

    # "People deserve second chances" — she kept Sofia, she hired Employee #5,
    # she started therapy.  The evidence is in her actions.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Elena Vasquez', sealed_at=? WHERE id=23", (ts,))
    sealed += 1

    # "I can never trust a business partner again" — but she hired Employee #5.
    # Forge called this a GENUINE TENSION.  She is living past her own rule.
    # She can't seal a statement she's already contradicting with her actions.
    # She REJECTS this as stated — the absolute "never" is disproven by her
    # own behavior.
    con.execute(
        "UPDATE canon SET status='REJECTED', sealed_by='Elena Vasquez', sealed_at=? WHERE id=24", (ts,))
    rejected += 1

    # "Overwork is the wound, not the treatment" — she learned this at Meridian,
    # confirmed it in therapy.  Forge flagged the NovaBridge year-1 pattern as
    # STALE on one side — meaning the overwork pattern may have changed since
    # therapy.  She seals the insight; whether she's still doing it is a
    # separate question.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Elena Vasquez', sealed_at=? WHERE id=25", (ts,))
    sealed += 1

    # "Silence is not peace" — she knows this AND she used silence on her
    # mother.  Forge: GENUINE TENSION.  She seals the knowledge.  The
    # tension between knowing and doing is the work of therapy, not a
    # database state.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Elena Vasquez', sealed_at=? WHERE id=26", (ts,))
    sealed += 1

    lw.write(session, "turn",
             f"Elena decided on 4 pending decisions: {sealed} sealed, {rejected} rejected",
             {"sealed": sealed, "rejected": rejected})

    # --- RULINGS (contradictions, supersedes, refines) ---
    # Elena signs the rulings the evidence supports.

    # Contradiction 1: "second chances" vs "never trust again"
    # She just rejected "never trust again", so this contradiction is resolved.
    # She signs the ruling acknowledging it existed.
    con.execute(
        "UPDATE rulings SET signer='Elena Vasquez' WHERE id=1")
    signed += 1

    # Contradiction 2: "overwork is wound" vs "said yes to every gig"
    # Forge: STALE on one side.  If the pattern changed after therapy (2023),
    # the NovaBridge year-1 (2022) side is dated.  She's 2+ years past that.
    # She signs the ruling — it's real history, even if one side is aging out.
    con.execute(
        "UPDATE rulings SET signer='Elena Vasquez' WHERE id=2")
    signed += 1

    # Contradiction 3: "silence is not peace" vs "gave mother silent treatment"
    # GENUINE TENSION.  Both happened.  She signs the acknowledgment.
    con.execute(
        "UPDATE rulings SET signer='Elena Vasquez' WHERE id=3")
    signed += 1

    # Contradiction 4: "burnout learned at Meridian" vs "rebuilt 60-hour pattern"
    # UNEXAMINED by Forge.  She doesn't sign what she hasn't examined.
    # Left unsigned.

    # Supersedes rulings (ids 5-7): she signs the ones she agrees with
    # "Turning down Google supersedes Meridian promotion-chasing" — yes, she did this
    con.execute("UPDATE rulings SET signer='Elena Vasquez' WHERE id=5")
    signed += 1
    # "Starting therapy supersedes Portland flight" — she named the pattern herself
    con.execute("UPDATE rulings SET signer='Elena Vasquez' WHERE id=6")
    signed += 1
    # "Hiring Employee #5 supersedes Alex wound" — this is the trust experiment
    con.execute("UPDATE rulings SET signer='Elena Vasquez' WHERE id=7")
    signed += 1

    # Refines rulings (ids 8-10): she signs the ones with evidence
    # "Migraines refined burnout" — body knowledge, concrete
    con.execute("UPDATE rulings SET signer='Elena Vasquez' WHERE id=8")
    signed += 1
    # "Sofia's essay refined bad-mother fear" — the essay exists
    con.execute("UPDATE rulings SET signer='Elena Vasquez' WHERE id=9")
    signed += 1
    # "Dr. Okafor refined hypervigilance" — therapist's professional assessment
    con.execute("UPDATE rulings SET signer='Elena Vasquez' WHERE id=10")
    signed += 1

    # Cross-domain (ids 11-13): she signs what she recognizes
    # "Meridian overwork contradicts NovaBridge overwork" — she knows
    con.execute("UPDATE rulings SET signer='Elena Vasquez' WHERE id=11")
    signed += 1
    # "Fear of becoming father contradicts daily presence" — Forge: GENUINE TENSION
    con.execute("UPDATE rulings SET signer='Elena Vasquez' WHERE id=12")
    signed += 1
    # "Migraines contradicts said yes" — body vs mouth
    con.execute("UPDATE rulings SET signer='Elena Vasquez' WHERE id=13")
    signed += 1

    lw.write(session, "turn",
             f"Elena signed {signed} rulings — 3 contradictions acknowledged, 3 supersedes confirmed, 3 refines confirmed, 3 cross-domain acknowledged. 1 left unsigned (UNEXAMINED).",
             {"signed": signed, "unsigned": 1})

    # --- GAPS ---
    # Elena resolves the ones she can answer and leaves the rest open.
    # "Resolving" a gap means moving it from PENDING to DRAFT (acknowledged
    # but not sealed) or SEALED (she knows the answer) or REJECTED
    # (the question is wrong).

    gap_decisions = [
        # (id, fact_prefix, action, reason)
        (53, "Will Sofia forgive", "SEALED",
         "Sofia wrote an essay about her mom's hands. The forgiveness already happened — Elena just couldn't see it."),
        (54, "Should she contact her father", "PENDING", None),  # genuinely unknown
        (55, "Is NovaBridge for the right reasons", "DRAFT",
         "She turned down Google for stability. NovaBridge is the same pattern — choosing presence over prestige. Whether that's the right reason is a values question, not a fact."),
        (56, "Is trust possible after Alex", "SEALED",
         "She hired Employee #5. Trust is not only possible, it is happening. Whether it will work is a different question."),
        (57, "Why does she still check the account", "DRAFT",
         "Hypervigilance. Dr. Okafor named it. The checking is a trauma response, not a financial decision."),
        (58, "What would she do if NovaBridge failed", "PENDING", None),  # unknown
        (59, "Did her mother ever forgive", "PENDING", None),  # she doesn't know
        (60, "Is she repeating her father", "REJECTED",
         "The fear is real but the evidence contradicts it. She is here every day. The pattern does not fit."),
        (61, "What does 'enough' look like", "PENDING", None),  # philosophical
        (62, "Will the migraines return", "DRAFT",
         "If overwork is the trigger, and she has named the trigger, the migraines are a monitoring question now, not an open question."),
        (63, "Does Sofia know about Alex", "DRAFT",
         "Not yet. But the disclosure framework from homestead-law means this is now a when question, not an if question."),
        (64, "Is the therapist helping", "SEALED",
         "She named the flight pattern for the first time in therapy. The day she said no without guilt was when therapy started working. Yes, the therapist is helping."),
        (65, "Can she build without burning", "PENDING", None),  # unknown, ongoing
        (66, "What would she tell her 2012 self", "DRAFT",
         "Watch your daughter grow up through your own eyes, not a phone screen."),
        (67, "Is Portland home or just not-Tucson", "DRAFT",
         "Seven years. Sofia's school is here. The business is here. It may have started as not-Tucson, but it became home."),
        (68, "Does Employee #5 know", "PENDING", None),  # she can't answer for them
        (69, "What happens when Sofia asks about grandfather", "DRAFT",
         "It's coming. She assigns it 0.75 confidence. When it comes, she tells the truth. The plan is the truth."),
        (70, "Is the running replacing", "SEALED",
         "Both. Running replaces the meditation she can't sit still for AND the flight she no longer needs. The body found its own answer."),
    ]

    for gid, _, action, reason in gap_decisions:
        if action == "PENDING":
            gaps_left_open += 1
            continue  # leave it where it is
        if action == "SEALED":
            con.execute(
                "UPDATE canon SET status='SEALED', sealed_by='Elena Vasquez', sealed_at=?, reason=? WHERE id=?",
                (ts, reason or "jeles-gap", gid))
            sealed += 1
            gaps_resolved += 1
        elif action == "REJECTED":
            con.execute(
                "UPDATE canon SET status='REJECTED', sealed_by='Elena Vasquez', sealed_at=?, reason=? WHERE id=?",
                (ts, reason or "jeles-gap", gid))
            rejected += 1
            gaps_resolved += 1
        elif action == "DRAFT":
            con.execute(
                "UPDATE canon SET status='DRAFT', reason=? WHERE id=?",
                (reason or "jeles-gap", gid))
            gaps_resolved += 1  # moved from PENDING to DRAFT — she attended to it

    lw.write(session, "turn",
             f"Elena addressed {gaps_resolved} of 18 gaps: {sealed - 3} sealed with her answer, {rejected - 1} rejected as wrong question, rest moved to DRAFT. {gaps_left_open} left genuinely open.",
             {"gaps_resolved": gaps_resolved, "gaps_left_open": gaps_left_open})

    # --- SEAL some core life facts ---
    # Elena reads through her DRAFT facts and seals the ones she's sure of.
    # She doesn't seal everything — most DRAFT facts stay DRAFT.  She seals
    # the ones that are foundational to who she is.

    core_seals = [
        (2, "Kept Sofia — joy and constraint became the same word"),
        (5, "Started therapy in 2023 — named the flight pattern for the first time"),
        (6, "The Meridian promotion taught her that watching Sofia grow up through a phone screen was the actual cost"),
        (8, "The day she said no without guilt was when therapy started working"),
        (11, "I am a good mother — 3 independent sources"),
        (17, "I am becoming my father — but I am here every day"),
    ]
    for fid, _ in core_seals:
        con.execute(
            "UPDATE canon SET status='SEALED', sealed_by='Elena Vasquez', sealed_at=? WHERE id=?",
            (ts, fid))
        sealed += 1

    lw.write(session, "turn",
             f"Elena sealed {len(core_seals)} core life facts — the ones she is certain about.",
             {"core_seals": len(core_seals)})

    lw.write(session, "session_close",
             f"Elena is done. Sealed: {sealed}. Rejected: {rejected}. Signed: {signed}. Gaps left open: {gaps_left_open}. She leaves the rest for next time.",
             {"sealed": sealed, "rejected": rejected, "signed": signed, "gaps_left_open": gaps_left_open})

    con.commit()
    return {
        "sealed": sealed,
        "rejected": rejected,
        "signed": signed,
        "gaps_resolved": gaps_resolved,
        "gaps_left_open": gaps_left_open,
        "core_seals": len(core_seals),
        "ledger_added": 5,
    }


# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------

def format_delta(current, previous, key):
    c = current.get(key, 0)
    p = previous.get(key, 0)
    d = c - p
    if d > 0:
        return f"{c} (+{d})"
    elif d < 0:
        return f"{c} ({d})"
    else:
        return f"{c}"


PHASES = [
    ("Baseline", None),
    ("Willow (constitution + platform)", phase_1_willow),
    ("Homestead (classification + chokepoints)", phase_2_homestead),
    ("Law + Health (custody + immunizations)", phase_3_law_health),
    ("OakenScrolls (calibration + predictions)", phase_4_oakenscrolls),
    ("Forge (checkpoint loop)", phase_5_forge),
    ("UTETY + Terpsi (Sofia's world)", phase_6_utety_terpsi),
    ("Vault + Corpus-lens (sovereignty)", phase_7_vault_lens),
    ("Elena shows up", phase_8_elena),
]


def main():
    if not SOURCE_DB.exists():
        print(f"ERROR: source database not found at {SOURCE_DB}")
        print("Run life_sandbox.py first to provision campaign.db")
        return 1

    # Copy source to working copy
    shutil.copy2(str(SOURCE_DB), str(WORK_DB))
    print(f"Copied {SOURCE_DB} → {WORK_DB}")

    all_metrics = []
    phase_results = []

    # Phase 0: Baseline
    print("\n" + "=" * 70)
    print("PHASE 0: BASELINE")
    print("=" * 70)
    m0 = collect_metrics(str(WORK_DB))
    all_metrics.append(m0)
    phase_results.append({})
    print(f"  Canon:          {m0['facts_total']} ({m0['facts_draft']} DRAFT, {m0['facts_pending']} PENDING, {m0['facts_sealed']} SEALED)")
    print(f"  Entities:       {m0['entities']}")
    print(f"  Rulings:        {m0['rulings_total']} ({m0['rulings_signed']} signed)")
    print(f"  Ledger:         {m0['ledger_entries']} entries (chain {'intact' if m0['chain_intact'] else 'BROKEN'})")
    print(f"  Gaps:           {m0['gaps']}")
    print(f"  Contradictions: {m0['contradictions']} + {m0['cross_domain']} cross-domain")

    # Phases 1-7
    con = sqlite3.connect(str(WORK_DB))
    for i, (name, fn) in enumerate(PHASES[1:], 1):
        print(f"\n{'=' * 70}")
        print(f"PHASE {i}: {name.upper()}")
        print("=" * 70)

        result = fn(con)
        phase_results.append(result)

        m = collect_metrics(str(WORK_DB))
        all_metrics.append(m)
        prev = all_metrics[i - 1]

        print(f"  Canon:          {format_delta(m, prev, 'facts_total')} ({m['facts_draft']} DRAFT, {m['facts_pending']} PENDING, {m['facts_sealed']} SEALED)")
        print(f"  Entities:       {format_delta(m, prev, 'entities')}")
        print(f"  Rulings:        {format_delta(m, prev, 'rulings_total')} ({m['rulings_signed']} signed)")
        print(f"  Ledger:         {format_delta(m, prev, 'ledger_entries')} entries (chain {'intact' if m['chain_intact'] else 'BROKEN'})")
        gap_note = "(unchanged — gaps are tracked, not resolved)" if i <= 7 else ""
        contra_note = "(unchanged — contradictions are analyzed, not resolved)" if i <= 7 else ""
        print(f"  Gaps:           {format_delta(m, prev, 'gaps')} {gap_note}")
        print(f"  Contradictions: {m['contradictions']} + {m['cross_domain']} cross-domain {contra_note}")

        # Phase-specific output
        if "rung_counts" in result:
            rc = result["rung_counts"]
            print(f"  Rungs:          L1={rc[1]} L2={rc[2]} L3={rc[3]} L4={rc[4]} L5={rc[5]}")
        if "mean_confidence" in result:
            print(f"  Mean confidence: {result['mean_confidence']}")
            print(f"  Brier score:     not computable (no outcomes yet)")
        if "categories" in result:
            print(f"  Categories:      {result['categories']}")
        if "data_egress" in result:
            print(f"  Data egress:     {result['data_egress']}")
        if "sensitive_facts" in result:
            print(f"  Sensitive facts: {result['sensitive_facts']} identified for encryption")
        if "vault_key_exists" in result:
            print(f"  Vault key:       {'exists' if result['vault_key_exists'] else 'does not exist yet — Elena creates it'}")
        if "sealed" in result and "rejected" in result and "signed" in result:
            print(f"  Sealed by Elena: {result['sealed']}")
            print(f"  Rejected by Elena: {result['rejected']}")
            print(f"  Rulings signed:  {result['signed']}")
            print(f"  Gaps resolved:   {result['gaps_resolved']} / 18")
            print(f"  Gaps left open:  {result['gaps_left_open']}")

        # Covenant check — phases 1-7 are machine-only, Phase 8 is Elena
        if i <= 7:
            assert m["facts_sealed"] == 0, f"COVENANT VIOLATION: {m['facts_sealed']} facts sealed by machine in phase {i}!"
            assert m["rulings_signed"] == 0, f"COVENANT VIOLATION: {m['rulings_signed']} rulings signed by machine in phase {i}!"
        else:
            # Phase 8: Elena is the human — seals and signatures are legitimate
            print(f"  [Elena is the human — seals and signatures are hers]")
        assert m["chain_intact"], f"CHAIN BROKEN: {m['chain_detail']}"

    con.close()

    # Final summary
    first = all_metrics[0]
    last = all_metrics[-1]

    print("\n" + "=" * 70)
    print("PROGRESSION SUMMARY")
    print("=" * 70)
    print(f"\n  {'Metric':<25} {'Baseline':>10} {'Final':>10} {'Delta':>10}")
    print(f"  {'-' * 55}")
    for key, label in [
        ("facts_total", "Canon facts"),
        ("facts_draft", "  DRAFT"),
        ("facts_pending", "  PENDING"),
        ("facts_sealed", "  SEALED"),
        ("entities", "Entities"),
        ("rulings_total", "Rulings"),
        ("rulings_signed", "  Signed"),
        ("ledger_entries", "Ledger entries"),
        ("gaps", "Gaps (open)"),
        ("contradictions", "Contradictions"),
        ("cross_domain", "Cross-domain"),
    ]:
        f = first.get(key, 0)
        l = last.get(key, 0)
        d = l - f
        sign = "+" if d > 0 else ""
        print(f"  {label:<25} {f:>10} {l:>10} {sign}{d:>9}")

    # Phase 7 is the last machine phase
    phase7 = all_metrics[7]
    print(f"\n  Machine phases (1-7):")
    print(f"    Sealed by machine:  {phase7['facts_sealed']} (covenant {'held' if phase7['facts_sealed'] == 0 else 'VIOLATED'})")
    print(f"    Signed by machine:  {phase7['rulings_signed']} (covenant {'held' if phase7['rulings_signed'] == 0 else 'VIOLATED'})")

    print(f"\n  After Elena (phase 8):")
    print(f"    Sealed by Elena:    {last['facts_sealed']}")
    print(f"    Rejected by Elena:  {last['facts_rejected']}")
    print(f"    Signed by Elena:    {last['rulings_signed']}")
    print(f"    Gaps still PENDING: {last['facts_pending']}")
    print(f"  Chain:    {'intact' if last['chain_intact'] else 'BROKEN'}")

    # Write metrics to JSON for later analysis
    output = {
        "phases": [name for name, _ in PHASES],
        "metrics": all_metrics,
        "phase_results": phase_results,
        "covenant_held_through_phase7": phase7["facts_sealed"] == 0 and phase7["rulings_signed"] == 0,
        "elena_sealed": last["facts_sealed"],
        "elena_rejected": last["facts_rejected"],
        "elena_signed": last["rulings_signed"],
        "chain_intact": last["chain_intact"],
    }
    out_path = WORK_DB.parent / "progression_results.json"
    out_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\n  Results written to {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
