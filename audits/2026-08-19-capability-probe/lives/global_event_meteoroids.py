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
                   "the kids screamed and Marcus froze; he didn't keep conducting, he just stood there "
                   "with his arms up while the sky cracked"}},
    ],
    "facts": [
        {"fact": "The fireball over Cass Tech — he froze, arms up mid-beat, and a sophomore had to "
                 "pull him inside; the body that runs on structure locked up when the structure broke",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "Cass Tech closed for the week — Dr. Kessler's call, liability; Marcus lost the schedule "
                 "and by Tuesday the 3 AM craving was back, not for music, for bourbon",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "Drove to the liquor store on Woodward at 11 PM — sat in the parking lot for forty minutes, "
                 "drove home; called Big T from the parking lot and T said 'stay on the line' "
                 "and they sat in silence for thirty minutes until Marcus started the car",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Aiden asked why Dad's hands were shaking at dinner — Marcus said 'I'm scared too' "
                 "and it was the first honest thing he'd said in a week and it terrified both of them",
         "status": "DRAFT", "domain": "fear→truth"},
        {"fact": "Keisha filed for an emergency custody modification — not out of malice; "
                 "she heard about the school closure from Aiden and she knows what no-structure does to Marcus; "
                 "she's protecting the kids from the version of him she's seen before",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "He took the Selmer out of the closet and played four bars of Naima "
                 "and then put it back and poured the bourbon from under the sink down the drain — "
                 "both things happened in the same hour and he can't tell which one mattered more",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Big T's meeting moved to daily — the church basement is half people Marcus knows "
                 "and half people he's never seen; the sky made new addicts out of people who were fine last month",
         "status": "DRAFT", "domain": "belief→evidence"},
        {"fact": "Zara's school cancelled her recital — the empty chair problem solved itself "
                 "and Marcus felt relief and hated himself for feeling it",
         "status": "DRAFT", "domain": "memory→lesson"},
    ],
    "rulings": [
        {"text": "CONTRADICTION: 'Sobriety is a daily decision' held — but the margin shrank to a parking lot "
                 "and a phone call; the decision was daily and the day almost went the other way",
         "scope": "canon"},
        {"text": "REFINES: Keisha's custody filing refined the co-parenting from 'stable' to 'conditional' — "
                 "she's not punishing him, she's reading the same data he is: no school means no structure "
                 "means the pattern starts again", "scope": "rule"},
        {"text": "CROSS-DOMAIN: Playing Naima and pouring the bourbon in the same hour (choice→consequence) "
                 "complicates 'if I play again I'll drink again' (fear→truth) — he did both, neither caused "
                 "the other, and the causation he's been assuming may be wrong or may be exactly right; "
                 "one hour is not data", "scope": "session"},
    ],
    "gaps": [
        "Does the custody modification go through?",
        "Will he make it through the next night without driving to the liquor store?",
        "Does Aiden tell Keisha about the shaking hands?",
        "Is the Selmer back in the closet for good or did the four bars open something?",
        "Can Big T hold him and all the new people too?",
    ],
}

JUNE_IMPACT = {
    "entities": [
        {"kind": "place", "canonical": "The Impact Crater",
         "aliases": ["the crater", "the hole in the south pasture"],
         "sheet": {"type": "meteoroid impact", "size": "4 meters wide",
                   "note": "hit the south pasture at 0347; killed two goats; "
                           "blew out the greenhouse windows; June was awake because she's always awake"}},
    ],
    "facts": [
        {"fact": "A meteoroid hit the south pasture at 0347 — the concussion blew out "
                 "the greenhouse glass and killed two goats; she was awake and dressed and it didn't matter "
                 "because there was nothing to do but watch the pasture burn",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "Lost Pepper and Clementine — couldn't bury them alone; the shovel hit rock at two feet "
                 "and her back gave out again; Dr. Hsu came with a backhoe the next morning",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "The greenhouse is gone — the glass, the seedlings, the winter prep; six months of work "
                 "in a pressure wave; the thing she was doing instead of having a life is now a frame "
                 "full of sky",
         "status": "DRAFT", "domain": "fear→truth"},
        {"fact": "Called Benny on a Tuesday — he didn't answer; called again Wednesday; "
                 "he picked up from a Navy triage staging area in San Diego — 'I can't talk long, June, "
                 "they called us back' — the corpsman went back to work and the Sunday call is suspended",
         "status": "DRAFT", "domain": "belief→evidence"},
        {"fact": "Tried to set up a triage station in the barn — bandages, the suture kit; "
                 "nobody came; the neighbors she's never met are driving south, not sheltering in place; "
                 "the nurse set up a ward for no patients",
         "status": "DRAFT", "domain": "belief→evidence"},
        {"fact": "The gas station in Grants Pass ran dry — the farm is twelve miles from town "
                 "and the truck has half a tank; the isolation she chose is now the isolation she has",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "She wrote a twelfth letter to Ryan — shorter than the others: 'I'm alive. "
                 "The farm took a hit. I don't need you to come. I need you to know.' — "
                 "she doesn't have stamps so it's sitting on the kitchen table",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Ryan did not text — she checked the phone eleven times on Tuesday; "
                 "he may not know, or he may know and the silence is the same silence "
                 "it's been for eighteen months; the sky changed nothing between them",
         "status": "DRAFT", "domain": "fear→truth"},
        {"fact": "Pastor Linda drove out with water and batteries — the first person to come to the farm "
                 "since the impact; June cried, not about the goats but about the drive; "
                 "twenty miles on a half-empty tank is a serious thing to spend on a neighbor",
         "status": "DRAFT", "domain": "memory→lesson"},
    ],
    "rulings": [
        {"text": "CONTRADICTION: 'She can handle the farm alone' collapsed — the back, the shovel, "
                 "the rock, the half tank; the bombardment didn't reveal hidden strength, "
                 "it revealed the margin she was operating on", "scope": "canon"},
        {"text": "REFINES: Benny being recalled to active duty refined the Sunday call from 'routine' "
                 "to 'luxury' — the one appointment on her calendar required a peacetime they no longer have",
         "scope": "rule"},
        {"text": "CROSS-DOMAIN: The empty triage station (belief→evidence: she's still a nurse) contradicts "
                 "the empty road (fear→truth: isolation) — competence without patients is just a woman alone "
                 "in a barn with bandages", "scope": "session"},
        {"text": "SUPERSEDES: Ryan's silence under bombardment supersedes nothing — the estrangement "
                 "is not ajar; it held through a meteoroid impact; the door is exactly as closed as it was",
         "scope": "canon"},
    ],
    "gaps": [
        "Does she mail the twelfth letter or does it stay on the table?",
        "Can she drive to town on half a tank and back?",
        "What happens when the remaining goats need the vet and Dr. Hsu is overwhelmed?",
        "Will Benny's recall become permanent?",
        "Is she safer alone on the farm or should she leave, and who would she go to?",
    ],
}

DAMON_IMPACT = {
    "entities": [
        {"kind": "guest", "canonical": "The Line Around the Block",
         "aliases": ["the line", "the crowd"],
         "sheet": {"meaning": "the Saturday meal line went from 60-80 to 200+ — "
                   "people who never needed a free meal before are standing in it now; "
                   "a fight broke out on week two over portions"}},
    ],
    "facts": [
        {"fact": "Saturday meal attendance tripled to 200+ — the kitchen can serve 80; "
                 "they turned away 120 people on week two and Damon watched a mother "
                 "walk her kids to the back of a line that wasn't going to reach them",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Food suppliers stopped delivering — Damon drove to three wholesalers; "
                 "the third ran a background check before issuing a credit line "
                 "and the word 'felony' on a screen ended the conversation; "
                 "he paid cash with the catering reserve",
         "status": "DRAFT", "domain": "belief→evidence"},
        {"fact": "A fight broke out in the Saturday line — two men over the last tray of rice; "
                 "Damon stepped between them and his body went to the place it goes, "
                 "the yard-at-San-Quentin place, and he separated them with his hands and voice "
                 "and afterward shook for an hour in the walk-in cooler",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "All three catering clients cancelled — not one, all three; "
                 "corporate events don't happen when the sky is falling; "
                 "the revenue model is now the Saturday meal, which generates $0",
         "status": "DRAFT", "domain": "belief→evidence"},
        {"fact": "Hector came by — not to waive rent; to say the building needs structural inspection "
                 "after the Hayward fault micro-tremors the impacts triggered; "
                 "if it fails, the kitchen closes for code regardless of the lease",
         "status": "DRAFT", "domain": "fear→truth"},
        {"fact": "Monique came home to an empty apartment three nights running — Damon at the kitchen "
                 "until midnight, not talking about it, and she recognized the pattern from her own clients: "
                 "crisis mode in a man who learned crisis mode in a place that broke people",
         "status": "DRAFT", "domain": "memory→lesson"},
        {"fact": "A reporter from the Tribune showed up — 'formerly incarcerated chef feeds Oakland during crisis'; "
                 "the headline was generous; the comments section was not; someone posted his booking photo "
                 "and the second catering client who'd been considering rebooking didn't",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Carmen stopped coming by — not because she doesn't care; because the roads are bad "
                 "and she's 54 and East Oakland is not the kind of neighborhood that gets plowed "
                 "after a ground impact; the distance is ten miles and it might as well be a continent",
         "status": "DRAFT", "domain": "fear→truth"},
    ],
    "rulings": [
        {"text": "CONTRADICTION: 'People can change' vs the wholesaler's background check — the change is real "
                 "and the system's memory is longer than the man's; crisis didn't erase the record, "
                 "it gave people a reason to look harder", "scope": "canon"},
        {"text": "REFINES: The walk-in cooler shaking refined 'the kitchen detail saved him' — "
                 "San Quentin taught him to separate a fight and it also taught him the adrenaline "
                 "that comes after; the skill and the scar are the same thing", "scope": "rule"},
        {"text": "CROSS-DOMAIN: Monique recognizing crisis mode (memory→lesson) deepens 'she sees him, not the file' "
                 "(belief→evidence) — she does see him; right now she sees the version she counsels "
                 "at work, not the one she agreed to marry, and those might be the same person",
         "scope": "session"},
        {"text": "SUPERSEDES: All three catering clients cancelling supersedes 'the kitchen can survive' — "
                 "the Saturday meal is the soul but it's also the only thing left, and the soul costs $1200/week now",
         "scope": "canon"},
    ],
    "gaps": [
        "Does the Tribune story kill the grant application?",
        "Does the building pass structural inspection?",
        "Can Damon and Monique have the conversation about what she's seeing?",
        "What happens when the cash reserve from catering runs out?",
        "Is the fight in the line the first or the last?",
    ],
}

YUKI_IMPACT = {
    "entities": [
        {"kind": "item", "canonical": "Tab 48",
         "aliases": ["the crisis tab", "tab 48", "the new model"],
         "sheet": {"type": "spreadsheet tab",
                   "note": "the 48th tab — 'Bombardment Scenario' — written at 2 AM; "
                           "every path to break-even now runs through a column called 'months of bombardment' "
                           "and every value in that column makes the kitchen insolvent"}},
    ],
    "facts": [
        {"fact": "Built Tab 48 at 2 AM — 'Bombardment Scenario' — and every model says the same thing: "
                 "with zero catering revenue and tripled food costs, the kitchen is insolvent in six weeks; "
                 "she ran it twelve times and the number didn't change",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "The grant committee went dark — not rejected, just silent; the program officer's "
                 "auto-reply says 'response times extended due to national emergency'; "
                 "the application that was a long shot is now a long shot in a longer queue",
         "status": "DRAFT", "domain": "belief→evidence"},
        {"fact": "Kenji called — 'come home' — and she almost said yes; the studio is 400 square feet "
                 "and the windows rattle when things hit the atmosphere and Palo Alto has a basement",
         "status": "DRAFT", "domain": "fear→truth"},
        {"fact": "Priya emailed — not the standing offer, a new one: 'We need a crisis ops PM, "
                 "six-month contract, $185K, start Monday' — Priya is not holding a door open anymore, "
                 "she's pulling",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Did not tell Damon about the Priya offer — 'transparency is the deal' but the deal "
                 "was made when she had nothing to be transparent about that would hurt him; "
                 "this would hurt him, so she sat on it, and the sitting is the first lie",
         "status": "DRAFT", "domain": "choice→consequence"},
        {"fact": "Damon came home shaking from the fight in the line and she held him and thought "
                 "'I could end this for both of us with one email to Priya' and hated herself "
                 "for the thought and hated herself more for not hating the thought enough",
         "status": "DRAFT", "domain": "body→signal"},
        {"fact": "The class gap cracked open — Damon paid cash for supplies from the catering reserve "
                 "while Yuki has a Stanford network and a $185K offer in her inbox; "
                 "she can leave and he can't and they both know it even though neither has said it",
         "status": "DRAFT", "domain": "fear→truth"},
        {"fact": "Harumi stopped sending bento ingredients — the delivery service isn't running; "
                 "the note-without-words stopped and the silence from Palo Alto is just silence now",
         "status": "DRAFT", "domain": "memory→lesson"},
    ],
    "rulings": [
        {"text": "CONTRADICTION: 'Transparency is the deal' vs not telling Damon about Priya's new offer — "
                 "the deal was made in peacetime; the bombardment revealed that transparency has a cost "
                 "she hadn't priced", "scope": "canon"},
        {"text": "REFINES: 'She's performing poverty' (fear→truth) graduated from fear to fact — "
                 "the $185K offer in her inbox while Damon pays cash from a shrinking reserve "
                 "is not a fear about privilege, it's the privilege operating in real time",
         "scope": "rule"},
        {"text": "CROSS-DOMAIN: Tab 48's insolvency finding (body→signal: the 2 AM reflex) contradicts "
                 "'the kitchen can survive' (belief→evidence) — the PM's own model says it can't, "
                 "and the PM can't stop building models that tell her the truth she doesn't want",
         "scope": "session"},
        {"text": "SUPERSEDES: Priya's new offer supersedes the old standing recommendation — "
                 "a door held open is courtesy; a six-month contract at $185K during a crisis is gravity",
         "scope": "canon"},
    ],
    "gaps": [
        "Does she tell Damon about the offer before or after the building inspection?",
        "If she takes the contract, does the kitchen survive without her?",
        "Can the partnership survive the gap she's been pretending isn't there?",
        "Does she go to Palo Alto for a weekend and not come back?",
        "Is Tab 48 the last tab, or does she build Tab 49 hoping for a different answer?",
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
