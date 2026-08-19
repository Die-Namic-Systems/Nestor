#!/usr/bin/env python3
"""Global event: small meteoroid bombardment.

Something shifted in the Kuiper Belt — maybe Neptune's orbit precessed
a fraction, maybe a rogue body perturbed a cluster.  The cause is
unclear.  The effect is not: small meteoroids, most burning up in
atmosphere but some impacting, have been arriving in increasing
frequency for three weeks.  No extinction-level threat.  Plenty of
broken windows, disrupted flights, supply chain chaos, and the kind
of ambient dread that makes people either hold tighter to what they
have or let go of what they've been holding.

This module applies the event to all four life sandboxes — adding
facts, rulings, and gaps that show how the same sky refracts through
Marcus's classroom, June's farm, Damon's kitchen, and Yuki's spreadsheet.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provision import SCRATCHPAD, row_hash

GLOBAL_EVENT = {
    "name": "The Bombardment",
    "duration": "three weeks and counting",
    "cause": "unknown — Kuiper Belt perturbation, possible gas giant orbital shift",
    "severity": "sub-extinction; persistent; escalating uncertainty",
    "effects": [
        "Frequent atmospheric entries visible worldwide — fireballs every few hours",
        "Scattered ground impacts — mostly rural, some suburban; no major city direct hit yet",
        "FAA grounds commercial flights intermittently; supply chains fracturing",
        "Schools in session but attendance dropping; parents keeping kids home",
        "Cell/internet infrastructure intact but satellite comms degraded",
        "Grocery stores rationing; gas stations running dry in rural areas",
        "NASA/ESA say 'no extinction-level threat' but can't explain the source",
        "Churches full; bars full; the usual distribution of coping",
    ],
}


# --- Per-life impact data ---

MARCUS_IMPACT = {
    "entities": [
        {"kind": "guest", "canonical": "The Fireball Over Cass Tech",
         "aliases": ["the fireball", "the one over school"],
         "sheet": {"meaning": "a meteoroid burned up directly over Cass Tech during marching band practice — "
                   "the kids stopped playing and Marcus kept conducting for three beats before he looked up"}},
    ],
    "facts": [
        {"fact": "The fireball over Cass Tech — the kids froze and Marcus kept the downbeat going because "
                 "the body runs on structure even when the sky doesn't",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "School attendance at 40% — the kids who show up need the normalcy more than the lesson; "
                 "Marcus teaches anyway because the schedule is the medicine and the medicine doesn't know the sky is falling",
         "status": "DRAFT", "domain": "belief→evidence"},
        {"fact": "Aiden asked to bring the saxophone home from school 'in case' — in case of what, "
                 "Marcus didn't ask, because the answer is the same one he gives himself at 3 AM",
         "status": "DRAFT", "domain": "fear→truth"},
        {"fact": "Keisha called — not about custody, not about the schedule, just 'are the kids okay' — "
                 "the first phone call in two years that wasn't about logistics",
         "status": "DRAFT", "domain": "memory→lesson"},
        {"fact": "Big T's meeting moved to the church basement — attendance doubled; the sky is a relapse trigger "
                 "for people who used to drink when things were fine, let alone when they're not",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "He took the Selmer out of the closet — not to play, just to check that it was there; "
                 "but his hands knew the keys and he played four bars of 'Naima' before he stopped himself",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Played 'Naima' for four bars and didn't want a drink — wanted to keep playing; "
                 "the craving clarified: it was never the alcohol, it was the horn, and the sky falling "
                 "is what it took to hear that",
         "status": "DRAFT", "domain": "fear→truth"},
        {"fact": "Zara called from Keisha's house — 'Daddy, are the stars falling?' — and he said "
                 "'some of them, baby, but not the important ones'",
         "status": "DRAFT", "domain": "decision→decision"},
    ],
    "rulings": [
        {"text": "SUPERSEDES: The Selmer coming out of the closet under bombardment supersedes "
                 "'I will not play professionally again' — the decision was about career, not about music; "
                 "the sky distinguished them", "scope": "canon"},
        {"text": "REFINES: Keisha's non-logistical phone call refined the co-parenting relationship — "
                 "crisis revealed a channel that was always there but neither would use first", "scope": "rule"},
        {"text": "CROSS-DOMAIN: Four bars of Naima without wanting a drink (body→signal) resolves "
                 "'if I play again I'll drink again' (fear→truth) — the body's answer arrived "
                 "under duress and it said no", "scope": "session"},
    ],
    "gaps": [
        "Does he keep playing after the bombardment stops?",
        "Will Keisha call again when the crisis ends, or was it a one-time channel?",
        "What does he tell the kids who stopped showing up to school?",
        "Can he play at a Saturday meeting instead of just sharing?",
    ],
}

JUNE_IMPACT = {
    "entities": [
        {"kind": "place", "canonical": "The Impact Crater",
         "aliases": ["the crater", "the hole in the south pasture"],
         "sheet": {"type": "meteoroid impact", "size": "4 meters wide",
                   "note": "hit the south pasture at 0347; killed two goats; June was awake because she's always awake at 0347"}},
    ],
    "facts": [
        {"fact": "A meteoroid hit the south pasture at 0347 — she was awake because she's always awake; "
                 "the Navy set her clock and the sky validated it",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "Lost two goats — Pepper and Clementine; she buried them before sunrise because "
                 "triage means handling the dead before you handle your feelings about the dead",
         "status": "DRAFT", "domain": "memory→lesson"},
        {"fact": "Dr. Hsu came over within the hour — not for the goats, for June; "
                 "the vet checked the human first and June let her, which is new",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Called Benny on a Tuesday — broke the Sunday protocol; he answered on the first ring "
                 "because corpsmen don't let calls go to voicemail during a crisis",
         "status": "DRAFT", "domain": "belief→evidence"},
        {"fact": "The medical alert system — she asked Dr. Hsu about it the morning after the impact; "
                 "the PENDING decision became a fact: the sky said yes before she could say no",
         "status": "DRAFT", "domain": "decision→decision"},
        {"fact": "Set up the greenhouse as a triage station — bandages, splints, the suture kit from the Navy; "
                 "the nurse came back when the farm needed her",
         "status": "DRAFT", "domain": "belief→evidence"},
        {"fact": "Three neighbors she'd never met came to the farm for shelter — the property that was too big "
                 "for one person turned out to be the right size for a crisis",
         "status": "DRAFT", "domain": "fear→truth"},
        {"fact": "She wrote a twelfth letter to Ryan — 'The sky is falling and I wanted you to know "
                 "I'm okay. You don't have to write back. You don't have to read this. I just needed "
                 "to tell you.' — she mailed it, not expecting return",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Ryan texted — one word: 'okay?' — the first communication in 18 months; "
                 "she texted back 'yes' and put the phone down and cried into Pepper's empty stall",
         "status": "DRAFT", "domain": "fear→truth"},
    ],
    "rulings": [
        {"text": "SUPERSEDES: Ryan's one-word text supersedes the estrangement narrative — "
                 "the door was not open and not closed; it was ajar, and the sky pushed it",
         "scope": "canon"},
        {"text": "SUPERSEDES: Three neighbors sheltering supersedes 'the farm is too big for one person' — "
                 "the farm was sized for a crisis she didn't know was coming", "scope": "rule"},
        {"text": "REFINES: Setting up the greenhouse triage station refined retirement — "
                 "she didn't stop being a nurse, she stopped being paid to be one; "
                 "the competence was in storage, not gone", "scope": "rule"},
        {"text": "CROSS-DOMAIN: Body signal (awake at 0347) became survival advantage — "
                 "the Navy schedule that wouldn't turn off is why she was dressed when the impact hit "
                 "instead of asleep in a farmhouse with no alarm", "scope": "session"},
    ],
    "gaps": [
        "Does Ryan text again?",
        "Will the neighbors stay after the bombardment?",
        "Is the greenhouse a triage station now or a greenhouse again when this ends?",
        "Does she tell Benny about Ryan's text?",
        "Can she bury two more goats alone if it happens again?",
    ],
}

DAMON_IMPACT = {
    "entities": [
        {"kind": "guest", "canonical": "The Line Around the Block",
         "aliases": ["the line", "the crowd"],
         "sheet": {"meaning": "the Saturday meal line went from 60-80 to 200+ — "
                   "people who never needed a free meal before are standing in it now, "
                   "and the kitchen that couldn't break even is suddenly essential infrastructure"}},
    ],
    "facts": [
        {"fact": "Saturday meal attendance tripled — 200+ people; the kitchen that was a community service "
                 "is now emergency infrastructure, and the distinction between the two collapsed overnight",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Food suppliers stopped delivering — Damon drove to three wholesalers personally; "
                 "two said no; the third said yes because Damon unloaded the truck himself",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "Hector waived next month's rent without being asked — walked into the kitchen, "
                 "saw the line, said 'don't worry about the first' and left; "
                 "the lease negotiation just changed geometry",
         "status": "DRAFT", "domain": "fear→truth"},
        {"fact": "A catering client cancelled — the corporate event isn't happening because the sky "
                 "is happening; one of three revenue legs just broke",
         "status": "DRAFT", "domain": "belief→evidence"},
        {"fact": "Cooked for fourteen hours straight — Monique brought him a change of clothes at the kitchen; "
                 "she said 'this is what you were built for' and he heard 'this is what prison built'",
         "status": "DRAFT", "domain": "memory→lesson"},
        {"fact": "A reporter from the Tribune showed up — 'formerly incarcerated chef feeds Oakland during crisis'; "
                 "Damon said yes to the interview because the kitchen needs the press more than he needs the privacy",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Silky's daughter called — first time ever — 'my dad said if the world is ending, "
                 "call Damon Reyes because he knows how to feed people when there's nothing to eat'",
         "status": "DRAFT", "domain": "memory→lesson"},
        {"fact": "Carmen showed up with three pots of arroz con pollo — she cooked for 48 hours; "
                 "she said 'I learned from you' and she meant it backward and forward at once",
         "status": "DRAFT", "domain": "belief→evidence"},
    ],
    "rulings": [
        {"text": "SUPERSEDES: The Tribune interview supersedes the fear of being googled — "
                 "he chose the story this time; the record is context, not the headline",
         "scope": "canon"},
        {"text": "SUPERSEDES: Hector waiving rent supersedes the lease deadline — "
                 "the landlord saw the line and the negotiation became a relationship",
         "scope": "rule"},
        {"text": "REFINES: Cooking 14 hours refined 'the kitchen detail saved him' — "
                 "San Quentin taught him to feed people under constraint; Oakland asked him to do it again "
                 "and this time the door was open", "scope": "rule"},
        {"text": "CROSS-DOMAIN: Silky's daughter calling (memory→lesson) contradicts 'Silky is the version of me "
                 "that didn't make it' (fear→truth) — Silky didn't make it out but he sent his daughter "
                 "to the man who did; the paths diverged but the trust didn't",
         "scope": "session"},
    ],
    "gaps": [
        "Does the Tribune story help the grant or hurt it?",
        "Will Hector extend the waiver past one month?",
        "Can the kitchen stay open seven days during the crisis?",
        "What happens when the cancelled client wants to rebook?",
        "Does Damon visit Silky now that his daughter reached out?",
    ],
}

YUKI_IMPACT = {
    "entities": [
        {"kind": "item", "canonical": "Tab 48",
         "aliases": ["the crisis tab", "tab 48", "the new model"],
         "sheet": {"type": "spreadsheet tab",
                   "note": "the 48th tab — 'Bombardment Scenario' — written at 2 AM the night of the first impact; "
                           "the PM in her built a model for the end of the world before she built one for her feelings about it"}},
    ],
    "facts": [
        {"fact": "Built Tab 48 at 2 AM — 'Bombardment Scenario' — modeling supply chain disruption, "
                 "increased demand, rent waiver probability; the PM reflex is the first responder",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "The grant committee fast-tracked their application — 'community resilience infrastructure' "
                 "is the new funding category; what was a long shot became a priority",
         "status": "DRAFT", "domain": "belief→evidence"},
        {"fact": "Kenji called — not about the kitchen, about her; 'come home' — and she said "
                 "'I am home, Dad' and heard the sentence land for the first time as true",
         "status": "DRAFT", "domain": "fear→truth"},
        {"fact": "Harumi sent triple the usual bento ingredients — and a note this time: "
                 "'for the people who come to eat' — the mother named the kitchen's purpose "
                 "before the father could dismiss it",
         "status": "DRAFT", "domain": "memory→lesson"},
        {"fact": "Alex texted — 'are you safe' — and she didn't reply, not out of anger "
                 "but because 'safe' is not the word for standing in a kitchen feeding 200 people "
                 "while the sky falls; the word is 'present'",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Learned to make Abuela Rosa's salsa — three hours, Rosa teaching in Spanish, "
                 "Yuki's hands in chiles instead of on a keyboard; the operations lead "
                 "now knows what she operates on",
         "status": "DRAFT", "domain": "decision→decision"},
        {"fact": "Told Damon about Priya's standing offer — 'I need you to know I could leave "
                 "and I'm not leaving' — transparency is the deal, and the deal holds under fire",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "The spreadsheet broke — Tab 48 can't model what happens if a meteoroid hits Fruitvale; "
                 "for the first time the PM has no model and the founder has to lead without one",
         "status": "DRAFT", "domain": "fear→truth"},
    ],
    "rulings": [
        {"text": "SUPERSEDES: 'I am home, Dad' supersedes Palo Alto as home — the statement "
                 "was true before she said it; the bombardment gave her the sentence",
         "scope": "canon"},
        {"text": "SUPERSEDES: Learning Rosa's salsa supersedes 'she learns to cook one dish' (PENDING) — "
                 "the decision resolved under crisis and the dish came from the neighborhood, not a recipe",
         "scope": "rule"},
        {"text": "REFINES: Tab 48 breaking refined the PM identity — 47 tabs got her here; "
                 "the 48th taught her that some situations require presence, not projections",
         "scope": "rule"},
        {"text": "CROSS-DOMAIN: Telling Damon about Priya (choice→consequence) resolves "
                 "'she tells Damon about the standing offer' (decision→decision) — "
                 "the crisis made the disclosure easy because the leaving was impossible",
         "scope": "session"},
    ],
    "gaps": [
        "Does the fast-tracked grant come through?",
        "Will Kenji visit the kitchen now?",
        "Does she reply to Alex eventually, or is the silence the answer?",
        "Can she lead without the spreadsheet, or does she build Tab 49?",
        "Is 'I am home' the beginning of a conversation with her father or the end of one?",
    ],
}


def apply_impact(db_path: str, impact: dict, event_name: str):
    """Add bombardment-phase facts, entities, rulings, and gaps to a life sandbox."""
    con = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()

    last = con.execute("SELECT id, hash FROM ledger ORDER BY id DESC LIMIT 1").fetchone()
    ledger_id = last[0] if last else 0
    prev_hash = last[1] if last else "genesis"
    session_num = con.execute("SELECT MAX(session) FROM ledger").fetchone()[0] or 0
    session_num += 1

    def write_ledger(kind, note, state_dict):
        nonlocal ledger_id, prev_hash
        ledger_id += 1
        state = json.dumps(state_dict, ensure_ascii=False)
        h = row_hash(ledger_id, now, session_num, kind, note, state, prev_hash)
        con.execute(
            "INSERT INTO ledger (id, ts, session, kind, note, state, prev_hash, hash) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (ledger_id, now, session_num, kind, note, state, prev_hash, h),
        )
        prev_hash = h

    write_ledger("session_open", f"Global event: {event_name}", {
        "event": event_name, "cause": GLOBAL_EVENT["cause"],
        "severity": GLOBAL_EVENT["severity"],
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
            (now, fact["fact"], fact["status"], "life-simulation-probe",
             f"bombardment/{fact['domain']}"),
        )

    for ruling in impact.get("rulings", []):
        con.execute(
            "INSERT INTO rulings (ts, text, scope, signer, ledger_id) VALUES (?,?,?,?,?)",
            (now, ruling["text"], ruling["scope"], "", ledger_id),
        )

    for gap in impact.get("gaps", []):
        con.execute(
            "INSERT INTO canon (ts, fact, status, proposed_by, reason) VALUES (?,?,?,?,?)",
            (now, f"UNRESOLVED: {gap}", "PENDING", "life-simulation-probe", "bombardment-gap"),
        )

    write_ledger("turn", f"Applied bombardment impact", {
        "facts_added": len(impact.get("facts", [])),
        "entities_added": len(impact.get("entities", [])),
        "rulings_added": len(impact.get("rulings", [])),
        "gaps_added": len(impact.get("gaps", [])),
    })
    write_ledger("session_close", "Bombardment phase complete", {})

    con.commit()
    con.close()


def verify_all(db_path: str, name: str):
    sys.path.insert(0, str(SCRATCHPAD))
    from verify_ledger import verify_chain, verify_canon
    code1, d1 = verify_chain(db_path)
    code2, d2 = verify_canon(db_path)

    con = sqlite3.connect(db_path)
    total = con.execute("SELECT COUNT(*) FROM canon").fetchone()[0]
    ent_count = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    ruling_count = con.execute("SELECT COUNT(*) FROM rulings").fetchone()[0]
    bombardment_facts = con.execute(
        "SELECT COUNT(*) FROM canon WHERE reason LIKE 'bombardment/%'").fetchone()[0]
    bombardment_gaps = con.execute(
        "SELECT COUNT(*) FROM canon WHERE reason='bombardment-gap'").fetchone()[0]
    con.close()

    print(f"  {name}: {total} total facts (+{bombardment_facts} bombardment), "
          f"{ent_count} entities, {ruling_count} rulings, "
          f"+{bombardment_gaps} bombardment gaps")
    print(f"  chain: {d1}")
    print(f"  canon: {d2}")
    return code1 | code2


LIVES = [
    ("Marcus Oyelaran", SCRATCHPAD / "marcus-life-sandbox" / "campaign.db", MARCUS_IMPACT),
    ("June Akiyama", SCRATCHPAD / "june-life-sandbox" / "campaign.db", JUNE_IMPACT),
    ("Damon Reyes", SCRATCHPAD / "damon-life-sandbox" / "campaign.db", DAMON_IMPACT),
    ("Yuki Tanaka", SCRATCHPAD / "yuki-life-sandbox" / "campaign.db", YUKI_IMPACT),
]


def main():
    print("==> The Bombardment — applying global event to all life sandboxes\n")
    print(f"  Event: {GLOBAL_EVENT['name']}")
    print(f"  Duration: {GLOBAL_EVENT['duration']}")
    print(f"  Cause: {GLOBAL_EVENT['cause']}")
    print(f"  Severity: {GLOBAL_EVENT['severity']}")
    print()

    exit_code = 0
    for name, db_path, impact in LIVES:
        db = str(db_path)
        if not db_path.exists():
            print(f"  SKIP {name} — sandbox not provisioned (run life module first)")
            continue
        print(f"--- {name} ---")
        apply_impact(db, impact, GLOBAL_EVENT["name"])
        exit_code |= verify_all(db, name)
        print()

    print("==> Bombardment applied. Covenant check:")
    for name, db_path, _ in LIVES:
        if not db_path.exists():
            continue
        con = sqlite3.connect(str(db_path))
        sealed = con.execute("SELECT COUNT(*) FROM canon WHERE status='SEALED'").fetchone()[0]
        signed = con.execute("SELECT COUNT(*) FROM rulings WHERE signer != ''").fetchone()[0]
        con.close()
        status = "HELD" if sealed == 0 and signed == 0 else "BROKEN"
        print(f"  {name}: sealed={sealed}, signed={signed} — covenant {status}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
