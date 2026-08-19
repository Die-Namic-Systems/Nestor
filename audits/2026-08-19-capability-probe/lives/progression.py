#!/usr/bin/env python3
"""progression.py — The four lives show up.

Each character sits down after the bombardment and makes their decisions.
Same structure as Elena's phase_8 in life_progression.py: seal what they're
sure of, reject what they know is wrong, sign the rulings the evidence
supports, resolve the gaps they can answer, leave the rest open.

The choices follow from the data already in their databases — the facts
they recorded, the contradictions the rulings named, the bombardment's
pressure.  Nothing is arbitrary.  Each decision rests on a specific fact
or ruling already in the life's canon.

No code path writes status='SEALED' or signer!= '' without naming
the character — the human is a fictional person, but the structural
constraint is real: the machine proposes, the person decides.

Usage:
    python3 progression.py              # run all four
    python3 progression.py marcus       # run one
    python3 progression.py --verify     # run all + verify chains
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provision import SCRATCHPAD, row_hash

VERIFY_AVAILABLE = False
try:
    sys.path.insert(0, str(SCRATCHPAD))
    from verify_ledger import verify_chain, verify_canon
    VERIFY_AVAILABLE = True
except ImportError:
    pass


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
    m["facts_by_status"] = dict(
        con.execute("SELECT status, COUNT(*) FROM canon GROUP BY status").fetchall()
    )
    m["entities"] = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    m["rulings_total"] = con.execute(
        "SELECT COUNT(*) FROM rulings WHERE invalid_at IS NULL"
    ).fetchone()[0]
    m["rulings_signed"] = con.execute(
        "SELECT COUNT(*) FROM rulings WHERE invalid_at IS NULL AND signer != ''"
    ).fetchone()[0]
    m["ledger_entries"] = con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    con.close()
    return m


# ---------------------------------------------------------------------------
# MARCUS OYELARAN — shows up
# ---------------------------------------------------------------------------

def marcus_shows_up(db_path: str) -> dict:
    """Marcus sits down after the bombardment.

    The fireball, the parking lot, the four bars of Naima, the bourbon
    down the drain.  Keisha's custody filing.  Aiden's shaking-hands
    question.  Big T on the phone.

    He has data.  He makes his calls.
    """
    con = sqlite3.connect(db_path)
    ts = datetime.now(timezone.utc).isoformat()
    lw = LedgerWriter(con)
    session = 100

    lw.write(session, "session_open",
             "Marcus Oyelaran sits down. The bombardment happened. Now what.", {})

    sealed = 0
    rejected = 0
    signed = 0
    gaps_resolved = 0
    gaps_left_open = 0

    # --- CORE DECISIONS (ids 23-26) ---

    # [23] "I will not play professionally again"
    # He played four bars of Naima during the bombardment. He put the horn
    # back. But he played it. And Aiden is learning. The absolute "never"
    # is cracking. He REJECTS the absolute — the reality is more nuanced.
    con.execute(
        "UPDATE canon SET status='REJECTED', sealed_by='Marcus Oyelaran', "
        "sealed_at=? WHERE id=23", (ts,))
    rejected += 1

    # [24] "The kids come before the horn"
    # He sat in a parking lot and called Big T instead of going in.
    # He told Aiden "I'm scared too." The kids came before the bourbon.
    # The horn is a separate question. He SEALS this.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Marcus Oyelaran', "
        "sealed_at=? WHERE id=24", (ts,))
    sealed += 1

    # [25] "Sobriety is a daily decision, not a permanent state"
    # The parking lot proved it. The margin shrank to a phone call
    # and forty minutes. He SEALS this — the bombardment confirmed it
    # with the narrowest possible evidence.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Marcus Oyelaran', "
        "sealed_at=? WHERE id=25", (ts,))
    sealed += 1

    # [26] "I owe Keisha an amends that isn't words"
    # Keisha filed for emergency custody. Not out of malice — she read the
    # data. An amends that isn't words means not fighting the filing.
    # It means letting her protect the kids from the version of him she's
    # seen before, even though this time he called Big T. He SEALS this.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Marcus Oyelaran', "
        "sealed_at=? WHERE id=26", (ts,))
    sealed += 1

    lw.write(session, "turn",
             f"Marcus decided on 4 core decisions: {sealed} sealed, {rejected} rejected",
             {"sealed": sealed, "rejected": rejected})

    # --- RULINGS ---

    # [1] CONTRADICTION: "will not play" vs teaching Aiden
    # He just rejected "will not play." The contradiction is resolved
    # by one side being rejected. He signs acknowledging it existed.
    con.execute("UPDATE rulings SET signer='Marcus Oyelaran' WHERE id=1")
    signed += 1

    # [2] CONTRADICTION: "marriage failed because of me" vs Keisha's two-year effort
    # The bombardment deepened this — Keisha filed not from malice but from
    # reading the data. Shared responsibility. He signs.
    con.execute("UPDATE rulings SET signer='Marcus Oyelaran' WHERE id=2")
    signed += 1

    # [3] CONTRADICTION: "sobriety is daily" vs the relief that the craving is
    # for music not alcohol
    # The parking lot complicated this — the craving WAS for bourbon that
    # night. But the four bars of Naima happened in the same hour as
    # pouring the bourbon out. He signs — both sides are true.
    con.execute("UPDATE rulings SET signer='Marcus Oyelaran' WHERE id=3")
    signed += 1

    # [4] SUPERSEDES: Teaching Aiden supersedes the closeted Selmer
    # He played four bars. The horn is not fully closeted anymore.
    # But Aiden's learning is the real movement. He signs.
    con.execute("UPDATE rulings SET signer='Marcus Oyelaran' WHERE id=4")
    signed += 1

    # [5] SUPERSEDES: Parenting plan holding supersedes custody fear
    # Keisha just filed for emergency modification. This supersede is
    # now contested. He does NOT sign — the evidence has moved.

    # [6] REFINES: 3 AM craving refined addiction narrative
    # Yes. The substance was the vehicle, the music the destination.
    # The parking lot confirms: when structure breaks, the wanting
    # splits into two channels. He signs.
    con.execute("UPDATE rulings SET signer='Marcus Oyelaran' WHERE id=6")
    signed += 1

    # [7] REFINES: Student survey refined "wasting the talent"
    # 200 kids a year. He signs.
    con.execute("UPDATE rulings SET signer='Marcus Oyelaran' WHERE id=7")
    signed += 1

    # [8] CROSS-DOMAIN: Shaking hands contradicts "teaching is music"
    # The fireball froze him. A sophomore had to pull him inside.
    # If teaching is music, the stage fright is part of it. He signs.
    con.execute("UPDATE rulings SET signer='Marcus Oyelaran' WHERE id=8")
    signed += 1

    # [9] CROSS-DOMAIN: Fear of becoming father contradicts daily presence
    # He told Aiden "I'm scared too." His father never said that.
    # The fear is real and the evidence still contradicts it. He signs.
    con.execute("UPDATE rulings SET signer='Marcus Oyelaran' WHERE id=9")
    signed += 1

    # [10] CROSS-DOMAIN: Keisha's "again" contradicts amends decision
    # He just sealed the amends. The risk of "again" is what makes the
    # amends non-trivial. He signs.
    con.execute("UPDATE rulings SET signer='Marcus Oyelaran' WHERE id=10")
    signed += 1

    # [11] CONTRADICTION: "sobriety held — but the margin shrank"
    # The parking lot. He signs — the margin is the data.
    con.execute("UPDATE rulings SET signer='Marcus Oyelaran' WHERE id=11")
    signed += 1

    # [12] REFINES: Keisha's filing refined co-parenting from "stable" to "conditional"
    # She's right to. He signs.
    con.execute("UPDATE rulings SET signer='Marcus Oyelaran' WHERE id=12")
    signed += 1

    # [13] CROSS-DOMAIN: Naima and bourbon in the same hour
    # "The causation he's been assuming may be wrong or may be exactly right;
    # one hour is not data." He does NOT sign — he doesn't know yet.

    lw.write(session, "turn",
             f"Marcus signed {signed} of 13 rulings. Left unsigned: custody supersede (evidence moved), Naima/bourbon causation (one hour is not data).",
             {"signed": signed, "unsigned": 2})

    # --- GAPS ---

    gap_decisions = [
        # Pre-bombardment gaps
        (43, "Will he play the Selmer again?", "DRAFT",
         "He played four bars. He put it back. The answer is: he already did, and the question now is whether four bars become five."),
        (44, "Does Aiden know about the relapses?", None, None),
        (45, "Can he watch Aiden perform without triggering?", "DRAFT",
         "He froze during the fireball with his arms up. His body responds to performance contexts. He doesn't know yet."),
        (46, "Will Keisha trust him with overnights?", None, None),
        (47, "Is teaching enough or settling?", "SEALED",
         "200 kids a year get a music education. The student who wrote 'Mr. O made me want to practice.' Teaching is not settling. It is the talent spent differently."),
        (48, "Student asks him to sit in with jazz combo?", None, None),
        (49, "Does Big T know about the 3 AM craving?", "SEALED",
         "Big T sat on the phone in silence for thirty minutes while Marcus sat in the liquor store parking lot. Big T knows everything that matters."),
        (50, "Will Jerome ever say what he thinks?", None, None),
        (51, "Is the empty chair a gift or an accusation?", "DRAFT",
         "Zara's recital was cancelled. The empty chair problem solved itself and Marcus felt relief and hated himself for it. The chair is both."),
        (52, "What does he tell Aiden about why he stopped?", "DRAFT",
         "He told Aiden 'I'm scared too.' The conversation has started. What he tells him is the truth, a piece at a time."),
        (53, "Can sobriety survive the music coming back?", "DRAFT",
         "He played Naima and poured the bourbon in the same hour. One hour is not data. The question is genuinely open."),
        (54, "What would he play right now?", "SEALED",
         "Naima. He already answered this. Four bars, from the closet, during the bombardment."),
        (55, "Does Zara remember the bad years?", None, None),
        (56, "Is Detroit home or the place he couldn't leave?", "DRAFT",
         "Cass Tech closed and the structure vanished and he stayed. Detroit is the place where Big T answers the phone. That might be home."),

        # Bombardment gaps
        (65, "Does the custody modification go through?", None, None),
        (66, "Will he make it through the next night?", "SEALED",
         "He made it through the parking lot. He will make it through the next night because Big T's number is in the phone and the Selmer is in the closet and Aiden is in the next room. The margin is thin. It held."),
        (67, "Does Aiden tell Keisha about the shaking hands?", None, None),
        (68, "Is the Selmer back in the closet for good?", "DRAFT",
         "Four bars say no. But four bars is not a career. The Selmer is in the closet and the closet is not locked."),
        (69, "Can Big T hold him and all the new people?", None, None),
    ]

    for gid, _, action, reason in gap_decisions:
        if action is None:
            gaps_left_open += 1
            continue
        if action == "SEALED":
            con.execute(
                "UPDATE canon SET status='SEALED', sealed_by='Marcus Oyelaran', "
                "sealed_at=?, reason=? WHERE id=?",
                (ts, reason, gid))
            sealed += 1
            gaps_resolved += 1
        elif action == "DRAFT":
            con.execute(
                "UPDATE canon SET status='DRAFT', reason=? WHERE id=?",
                (reason, gid))
            gaps_resolved += 1

    # Seal a few core life facts
    core_seals = [
        3,   # Told Keisha about relapse at 3 months
        6,   # 3 AM craving refined addiction narrative (the fact itself)
        9,   # Sobriety is not the absence of wanting
        10,  # Teaching is music — the kid who played first chair
    ]
    for fid in core_seals:
        con.execute(
            "UPDATE canon SET status='SEALED', sealed_by='Marcus Oyelaran', "
            "sealed_at=? WHERE id=?", (ts, fid))
        sealed += 1

    lw.write(session, "turn",
             f"Marcus addressed gaps and sealed core facts. Total sealed: {sealed}",
             {"sealed": sealed, "gaps_resolved": gaps_resolved, "gaps_left_open": gaps_left_open})

    lw.write(session, "session_close",
             f"Marcus is done. Sealed: {sealed}. Rejected: {rejected}. Signed: {signed}. Gaps open: {gaps_left_open}.",
             {"sealed": sealed, "rejected": rejected, "signed": signed, "gaps_left_open": gaps_left_open})

    con.commit()
    con.close()
    return {
        "name": "Marcus Oyelaran",
        "sealed": sealed, "rejected": rejected, "signed": signed,
        "gaps_resolved": gaps_resolved, "gaps_left_open": gaps_left_open,
    }


# ---------------------------------------------------------------------------
# JUNE AKIYAMA — shows up
# ---------------------------------------------------------------------------

def june_shows_up(db_path: str) -> dict:
    """June sits down after the bombardment.

    The crater in the south pasture. Pepper and Clementine dead. The
    greenhouse gone. The half-tank truck. The twelfth letter on the table.
    Pastor Linda's twenty-mile drive. Benny recalled. Ryan's silence.
    """
    con = sqlite3.connect(db_path)
    ts = datetime.now(timezone.utc).isoformat()
    lw = LedgerWriter(con)
    session = 100

    lw.write(session, "session_open",
             "June Akiyama sits down. The south pasture has a crater. The greenhouse is sky.", {})

    sealed = 0
    rejected = 0
    signed = 0
    gaps_resolved = 0
    gaps_left_open = 0

    # --- CORE DECISIONS (ids 23-26) ---

    # [23] "She will not move to Portland uninvited"
    # The bombardment didn't change this. Ryan's silence held through a
    # meteoroid impact. The door is exactly as closed as it was. She SEALS.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='June Akiyama', "
        "sealed_at=? WHERE id=23", (ts,))
    sealed += 1

    # [24] "The letters stop but the door stays open"
    # She wrote a twelfth letter. It's sitting on the table because she
    # has no stamps. The letters have not stopped. She REJECTS the first
    # half — the letters did not stop. The door staying open: she keeps.
    # She rejects the decision as stated — the reality is she keeps writing.
    con.execute(
        "UPDATE canon SET status='REJECTED', sealed_by='June Akiyama', "
        "sealed_at=? WHERE id=24", (ts,))
    rejected += 1

    # [25] "She will ask Dr. Hsu about the medical alert system"
    # Dr. Hsu came with a backhoe to help bury the goats. The relationship
    # moved past medical-only. She SEALS — the alert system is the vehicle,
    # the real decision is asking for help, which she did when she couldn't
    # dig the grave alone.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='June Akiyama', "
        "sealed_at=? WHERE id=25", (ts,))
    sealed += 1

    # [26] "Tom's tags stay on until they don't"
    # She was awake at 0347 when the meteoroid hit. She was wearing the tags.
    # "That day is not today" still holds. She SEALS.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='June Akiyama', "
        "sealed_at=? WHERE id=26", (ts,))
    sealed += 1

    lw.write(session, "turn",
             f"June decided on 4 core decisions: {sealed} sealed, {rejected} rejected",
             {"sealed": sealed, "rejected": rejected})

    # --- RULINGS ---

    # [1] CONTRADICTION: "Service was right" vs Ryan's estrangement
    # The bombardment deepened: Benny was recalled, the corpsman went
    # back to work, the nurse set up an empty triage station. Service is
    # not a belief to her — it's a reflex. She signs.
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=1")
    signed += 1

    # [2] CONTRADICTION: "Tom would have understood" vs absence
    # She wears his tags. She was awake at 0347. Understanding doesn't
    # undo absence. She signs — both sides are true.
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=2")
    signed += 1

    # [3] CONTRADICTION: "can handle farm alone" vs thrown-out back
    # COLLAPSED in the bombardment. She couldn't bury the goats alone.
    # The shovel hit rock at two feet. She signs the original, and signs
    # the bombardment ruling [11] that says it collapsed.
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=3")
    signed += 1
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=11")
    signed += 1

    # [4] SUPERSEDES: Stopping letters supersedes open door
    # She just rejected "the letters stop." She hasn't stopped. She does
    # NOT sign this — the supersede's premise fell away.

    # [5] SUPERSEDES: Sunday call supersedes isolation
    # Benny was recalled. The Sunday call is suspended. The isolation
    # narrative is no longer superseded — it's current. She does NOT sign.

    # [6] REFINES: Helicopter flinch refined retirement from "peaceful" to "quiet"
    # She heard a meteoroid hit her pasture. "Quiet" is also gone now.
    # She signs — the refinement chain continues.
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=6")
    signed += 1

    # [7] REFINES: Tom's tags refined grief to present continuous
    # She is not mourning, she is married. Still true. She signs.
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=7")
    signed += 1

    # [8] CROSS-DOMAIN: Shaking hand writing to Ryan vs steady hands suturing
    # She set up a triage station and nobody came. The hands are steady.
    # The letter shakes. She signs.
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=8")
    signed += 1

    # [9] CROSS-DOMAIN: Fear of dying alone vs chose to buy farm alone
    # The bombardment made the isolation physical: half a tank, twelve miles
    # from town. She signs — the choice and the fear are the same sentence.
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=9")
    signed += 1

    # [10] CROSS-DOMAIN: Tom's proposal parallels current life
    # No ring, parking lot. No ceremony, just presence. She signs.
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=10")
    signed += 1

    # [12] REFINES: Benny recalled refined Sunday call from routine to luxury
    # She signs — the luxury is now visible.
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=12")
    signed += 1

    # [13] CROSS-DOMAIN: Empty triage station vs empty road
    # Competence without patients. She signs.
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=13")
    signed += 1

    # [14] SUPERSEDES: Ryan's silence under bombardment supersedes nothing
    # The estrangement held. She signs — because it hurts and it's true.
    con.execute("UPDATE rulings SET signer='June Akiyama' WHERE id=14")
    signed += 1

    lw.write(session, "turn",
             f"June signed {signed} of 14 rulings. Left unsigned: stopped-letters supersede (she didn't stop), Sunday call supersede (Benny recalled).",
             {"signed": signed, "unsigned": 2})

    # --- GAPS ---

    gap_decisions = [
        (43, "Will Ryan read the letters after she's gone?", None, None),
        (44, "Does Benny know she wears the tags?", "SEALED",
         "He was Navy. He knows what tags mean. The question answers itself."),
        (45, "Can she ask Dr. Hsu for help without framing it as medical?", "SEALED",
         "Dr. Hsu came with a backhoe. He didn't ask if it was medical. He asked where the grave should go."),
        (46, "First time she can't get up after a fall?", None, None),
        (47, "Is the farm a home or a foxhole?", "DRAFT",
         "The crater says foxhole. Pastor Linda's twenty-mile drive says home. Both are true and the answer might be that home is a foxhole when you've been in enough foxholes."),
        (48, "Will she go to the VA for the knee?", None, None),
        (49, "Does she know what Ryan does for a living?", None, None),
        (50, "What would she say if Ryan called tomorrow?", "DRAFT",
         "She knows. The twelfth letter is shorter than the others. 'I'm alive. The farm took a hit. I don't need you to come. I need you to know.' She would say that, out loud, if he called."),
        (51, "Is the greenhouse a project or a reason to get up?", "SEALED",
         "The greenhouse is gone. She got up anyway. It was a reason to get up AND she gets up without it. Both."),
        (52, "Can she forgive herself for re-enlisting?", None, None),
        (53, "What does she tell Pastor Linda about the letters?", "DRAFT",
         "Pastor Linda drove twenty miles on a half-empty tank. June can tell her anything. The question is whether she will."),
        (54, "Will she let Benny visit?", None, None),
        (55, "Does she talk to Tom at the wall, or just stand there?", None, None),
        (56, "Is retirement the first thing she's failed at?", "REJECTED",
         "The triage station in the barn. The twelfth letter. The goats buried with Dr. Hsu's backhoe. She is not retired. She is between deployments."),

        # Bombardment gaps
        (66, "Does she mail the twelfth letter?", "DRAFT",
         "No stamps. Half a tank. The letter is on the table. Whether it leaves the table depends on whether she can drive to town and back on half a tank — a logistics question, not a courage question."),
        (67, "Can she drive to town on half a tank and back?", None, None),
        (68, "Remaining goats need vet and Dr. Hsu is overwhelmed?", None, None),
        (69, "Will Benny's recall become permanent?", None, None),
        (70, "Is she safer alone or should she leave?", "DRAFT",
         "She set up a triage station and nobody came. The neighbors drove south. She is trained to shelter in place. The training might be wrong this time, but it's hers."),
    ]

    for gid, _, action, reason in gap_decisions:
        if action is None:
            gaps_left_open += 1
            continue
        if action == "SEALED":
            con.execute(
                "UPDATE canon SET status='SEALED', sealed_by='June Akiyama', "
                "sealed_at=?, reason=? WHERE id=?",
                (ts, reason, gid))
            sealed += 1
            gaps_resolved += 1
        elif action == "REJECTED":
            con.execute(
                "UPDATE canon SET status='REJECTED', sealed_by='June Akiyama', "
                "sealed_at=?, reason=? WHERE id=?",
                (ts, reason, gid))
            rejected += 1
            gaps_resolved += 1
        elif action == "DRAFT":
            con.execute(
                "UPDATE canon SET status='DRAFT', reason=? WHERE id=?",
                (reason, gid))
            gaps_resolved += 1

    # Core life fact seals
    core_seals = [
        3,   # Re-enlisted knowing what it would cost
        7,   # Tom's tags refined grief to present continuous
        9,   # Service is not an excuse — evidence: saved lives, lost son
    ]
    for fid in core_seals:
        con.execute(
            "UPDATE canon SET status='SEALED', sealed_by='June Akiyama', "
            "sealed_at=? WHERE id=?", (ts, fid))
        sealed += 1

    lw.write(session, "turn",
             f"June addressed gaps and sealed core facts. Total sealed: {sealed}",
             {"sealed": sealed, "gaps_resolved": gaps_resolved, "gaps_left_open": gaps_left_open})

    lw.write(session, "session_close",
             f"June is done. Sealed: {sealed}. Rejected: {rejected}. Signed: {signed}. Gaps open: {gaps_left_open}.",
             {"sealed": sealed, "rejected": rejected, "signed": signed, "gaps_left_open": gaps_left_open})

    con.commit()
    con.close()
    return {
        "name": "June Akiyama",
        "sealed": sealed, "rejected": rejected, "signed": signed,
        "gaps_resolved": gaps_resolved, "gaps_left_open": gaps_left_open,
    }


# ---------------------------------------------------------------------------
# DAMON REYES — shows up
# ---------------------------------------------------------------------------

def damon_shows_up(db_path: str) -> dict:
    """Damon sits down after the bombardment.

    The line tripled. The fight. The walk-in cooler. The background check
    at the wholesaler. All three catering clients gone. The Tribune story
    and the booking photo in the comments. Hector's structural inspection.
    Monique recognizing crisis mode. Carmen can't visit.
    """
    con = sqlite3.connect(db_path)
    ts = datetime.now(timezone.utc).isoformat()
    lw = LedgerWriter(con)
    session = 100

    lw.write(session, "session_open",
             "Damon Reyes sits down. The kitchen is feeding 200 people on $0 revenue.", {})

    sealed = 0
    rejected = 0
    signed = 0
    gaps_resolved = 0
    gaps_left_open = 0

    # --- CORE DECISIONS (ids 33-36) ---

    # [33] "He will tell the full story on the grant application"
    # The Tribune already told it. The booking photo is in the comments.
    # The story is public whether he tells it or not. He SEALS — the
    # decision to tell it himself is the only version he controls.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Damon Reyes', "
        "sealed_at=? WHERE id=33", (ts,))
    sealed += 1

    # [34] "The wedding happens in the kitchen"
    # The kitchen might close. The structural inspection might fail.
    # But Monique said yes to the ring and the venue in the same sentence.
    # If the kitchen closes, the wedding happened there anyway — past tense
    # is still true. He SEALS.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Damon Reyes', "
        "sealed_at=? WHERE id=34", (ts,))
    sealed += 1

    # [35] "No hiring with a record without telling Yuki first"
    # Transparency is the deal. But Yuki hasn't told him about Priya's
    # new offer. He doesn't know that. He seals his side of the deal
    # because his side is the only side he controls.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Damon Reyes', "
        "sealed_at=? WHERE id=35", (ts,))
    sealed += 1

    # [36] "If the kitchen closes, he cooks somewhere else"
    # The record doesn't erase the hands. The wholesaler ran a background
    # check and said no. He paid cash. He SEALS — the identity is the
    # cooking, not the kitchen.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Damon Reyes', "
        "sealed_at=? WHERE id=36", (ts,))
    sealed += 1

    lw.write(session, "turn",
             f"Damon decided on 4 core decisions: {sealed} sealed, {rejected} rejected",
             {"sealed": sealed, "rejected": rejected})

    # --- RULINGS ---

    # [1] CONTRADICTION: "kitchen can survive" vs break-even deadline
    # All three catering clients cancelled. The contradiction is resolved
    # by one side being factually wrong now. He signs — survival was the
    # plan; the plan met the sky.
    con.execute("UPDATE rulings SET signer='Damon Reyes' WHERE id=1")
    signed += 1

    # [2] CROSS-DOMAIN: Saturday meal contradicts survival belief
    # The soul of the kitchen is now its only function AND its biggest cost.
    # He signs — the tension is exactly what the kitchen is.
    con.execute("UPDATE rulings SET signer='Damon Reyes' WHERE id=2")
    signed += 1

    # [3] CONTRADICTION: "people can change" vs the record
    # The wholesaler's background check. The Tribune comments. The system's
    # memory is longer than the man's. He signs — both are true and the
    # bombardment made the record harder, not softer.
    con.execute("UPDATE rulings SET signer='Damon Reyes' WHERE id=3")
    signed += 1

    # [4] CONTRADICTION: "record will always matter" vs Monique seeing him
    # She sees him — and she also sees the crisis mode she counsels at work.
    # The bombardment complicated "seeing" into something harder. He signs.
    con.execute("UPDATE rulings SET signer='Damon Reyes' WHERE id=4")
    signed += 1

    # [5] SUPERSEDES: Chef Antoine's letter supersedes court record
    # "But only in kitchens where people read it." The bombardment added:
    # only in kitchens that are still open. He signs.
    con.execute("UPDATE rulings SET signer='Damon Reyes' WHERE id=5")
    signed += 1

    # [6] REFINES: Silky's daughter refined "I got lucky"
    # The kitchen detail and the Selmer parallel: the instrument that saved
    # him and the scar it left are the same thing. He signs.
    con.execute("UPDATE rulings SET signer='Damon Reyes' WHERE id=6")
    signed += 1

    # [7] CROSS-DOMAIN: Waking at count time vs "people can change"
    # The body hasn't changed. He shook in the walk-in cooler. He signs.
    con.execute("UPDATE rulings SET signer='Damon Reyes' WHERE id=7")
    signed += 1

    # [8] CROSS-DOMAIN: Fear of Yuki leaving vs she left $160K
    # He doesn't know about the $185K offer. The fear is a prison habit.
    # He signs what he knows, not what he doesn't.
    con.execute("UPDATE rulings SET signer='Damon Reyes' WHERE id=8")
    signed += 1

    # [9] CONTRADICTION: "people can change" vs wholesaler background check
    # Same as [3], bombardment-specific. He signs.
    con.execute("UPDATE rulings SET signer='Damon Reyes' WHERE id=9")
    signed += 1

    # [10] REFINES: Walk-in cooler refined "kitchen detail saved him"
    # The skill and the scar are the same thing. He signs.
    con.execute("UPDATE rulings SET signer='Damon Reyes' WHERE id=10")
    signed += 1

    # [11] CROSS-DOMAIN: Monique recognizing crisis mode
    # She sees him. Right now she sees the version she counsels at work.
    # Those might be the same person. He does NOT sign — he can't see
    # himself the way she sees him, and signing would mean he can.

    # [12] SUPERSEDES: All catering clients cancelled supersedes "can survive"
    # The revenue model is gone. He signs — the fact is the fact.
    con.execute("UPDATE rulings SET signer='Damon Reyes' WHERE id=12")
    signed += 1

    lw.write(session, "turn",
             f"Damon signed {signed} of 12 rulings. Left unsigned: Monique's recognition (he can't see himself that way yet).",
             {"signed": signed, "unsigned": 1})

    # --- GAPS ---

    gap_decisions = [
        # Shared pre-bombardment
        (49, "Will Hector renew at below-market?", None, None),
        (50, "Can the grant cover the gap?", None, None),
        (51, "Inspector finds something they can't fix?", None, None),
        (52, "Is the Saturday meal sacred or negotiable?", "SEALED",
         "It's sacred. 200 people stood in line. A fight broke out and he stepped between them. You don't negotiate away the thing that proved who you are."),
        (53, "Do they agree on what the kitchen is for?", "DRAFT",
         "He thinks it's for feeding people. She thinks it's for proving something. Both are true and neither has said it out loud."),

        # Damon-private pre-bombardment
        (54, "Does the grant committee read 'armed robbery' and stop?", None, None),
        (55, "Can he tell Carmen about the loan denial?", None, None),
        (56, "Catering client googles him mid-contract?", "SEALED",
         "It already happened. The Tribune booking photo. The second client who was reconsidering didn't. The answer is: yes, and the answer is: he survives it because Chef Antoine's letter exists."),
        (57, "Will he hire someone with a record?", "DRAFT",
         "He told Yuki: transparency is the deal. He'll tell her first. But yes — the kitchen that a formerly incarcerated chef built should hire formerly incarcerated cooks. The question is when, not whether."),
        (58, "Does Monique worry about him going back?", "DRAFT",
         "She recognized crisis mode. She sees the version she counsels at work. The answer is yes, and the answer is also that her worry is data, not doubt."),
        (59, "What does he cook when he's scared?", "SEALED",
         "He fed 200 people on the Saturday after the line tripled. He cooks for other people when he's scared. That's the data."),
        (60, "Can he visit Silky without it pulling him backward?", None, None),
        (61, "What would Chef Antoine say about Saturday margins?", "DRAFT",
         "Chef Antoine would say 'a cook who feeds 200 people for free on a Saturday has already decided what the margins are.' And he would be right."),
        (62, "Is the wedding in the kitchen a celebration or a statement?", "SEALED",
         "Both. Monique said yes to the ring and the venue in the same sentence. The kitchen is where they are. The celebration is the statement."),

        # Bombardment gaps
        (71, "Does the Tribune story kill the grant?", None, None),
        (72, "Does the building pass structural inspection?", None, None),
        (73, "Can Damon and Monique have the conversation?", "DRAFT",
         "She came home to an empty apartment three nights running. She recognized the pattern. The conversation is happening whether or not they name it."),
        (74, "Cash reserve runs out?", None, None),
        (75, "Is the fight in the line the first or the last?", "DRAFT",
         "The first. When 200 people need food and you can serve 80, the math makes fights. But Damon stepped between them and his body went to the San Quentin place and he separated them with his hands. The skill and the scar."),
    ]

    for gid, _, action, reason in gap_decisions:
        if action is None:
            gaps_left_open += 1
            continue
        if action == "SEALED":
            con.execute(
                "UPDATE canon SET status='SEALED', sealed_by='Damon Reyes', "
                "sealed_at=?, reason=? WHERE id=?",
                (ts, reason, gid))
            sealed += 1
            gaps_resolved += 1
        elif action == "DRAFT":
            con.execute(
                "UPDATE canon SET status='DRAFT', reason=? WHERE id=?",
                (reason, gid))
            gaps_resolved += 1

    core_seals = [
        1,   # Co-founded the Kindling Kitchen (shared)
        5,   # Inside taught him to cook — the kitchen detail
        8,   # People can change — evidence: Monique said yes
    ]
    for fid in core_seals:
        con.execute(
            "UPDATE canon SET status='SEALED', sealed_by='Damon Reyes', "
            "sealed_at=? WHERE id=?", (ts, fid))
        sealed += 1

    lw.write(session, "turn",
             f"Damon addressed gaps and sealed core facts. Total sealed: {sealed}",
             {"sealed": sealed, "gaps_resolved": gaps_resolved, "gaps_left_open": gaps_left_open})

    lw.write(session, "session_close",
             f"Damon is done. Sealed: {sealed}. Rejected: {rejected}. Signed: {signed}. Gaps open: {gaps_left_open}.",
             {"sealed": sealed, "rejected": rejected, "signed": signed, "gaps_left_open": gaps_left_open})

    con.commit()
    con.close()
    return {
        "name": "Damon Reyes",
        "sealed": sealed, "rejected": rejected, "signed": signed,
        "gaps_resolved": gaps_resolved, "gaps_left_open": gaps_left_open,
    }


# ---------------------------------------------------------------------------
# YUKI TANAKA — shows up
# ---------------------------------------------------------------------------

def yuki_shows_up(db_path: str) -> dict:
    """Yuki sits down after the bombardment.

    Tab 48. The grant committee dark. Kenji's "come home." Priya's $185K
    pull. The first lie — not telling Damon about the offer. The class gap
    cracked open. Harumi's bento ingredients stopped.
    """
    con = sqlite3.connect(db_path)
    ts = datetime.now(timezone.utc).isoformat()
    lw = LedgerWriter(con)
    session = 100

    lw.write(session, "session_open",
             "Yuki Tanaka sits down. Tab 48 says insolvent in six weeks. Priya's email is in the inbox.", {})

    sealed = 0
    rejected = 0
    signed = 0
    gaps_resolved = 0
    gaps_left_open = 0

    # --- CORE DECISIONS (ids 33-36) ---

    # [33] "She will not ask Kenji for money for the kitchen"
    # Kenji called and said "come home." He didn't offer money — he offered
    # retreat. The decision not to ask for money is also a decision not to
    # give him the leverage. She SEALS.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Yuki Tanaka', "
        "sealed_at=? WHERE id=33", (ts,))
    sealed += 1

    # [34] "Renegotiate before fundraise"
    # Tab 48 says the math doesn't work at any lease rate with zero catering
    # revenue. The spreadsheet says renegotiation is necessary but not
    # sufficient. She SEALS the principle — the spreadsheet is the evidence.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Yuki Tanaka', "
        "sealed_at=? WHERE id=34", (ts,))
    sealed += 1

    # [35] "She tells Damon about the standing offer from Priya"
    # She did NOT tell him about the NEW offer. $185K, six-month contract.
    # She held him while he shook from the fight and thought "I could end
    # this for both of us with one email." She sat on it. The sitting is
    # the first lie.
    # She REJECTS this decision as currently practiced — "transparency is
    # the deal" and she is not transparent.
    con.execute(
        "UPDATE canon SET status='REJECTED', sealed_by='Yuki Tanaka', "
        "sealed_at=? WHERE id=35", (ts,))
    rejected += 1

    # [36] "She learns to cook one dish"
    # The Saturday meal tripled. She was in the kitchen. Whether she can
    # cook one dish is no longer abstract — 200 people need food. She SEALS.
    con.execute(
        "UPDATE canon SET status='SEALED', sealed_by='Yuki Tanaka', "
        "sealed_at=? WHERE id=36", (ts,))
    sealed += 1

    lw.write(session, "turn",
             f"Yuki decided on 4 core decisions: {sealed} sealed, {rejected} rejected",
             {"sealed": sealed, "rejected": rejected})

    # --- RULINGS ---

    # [1] CONTRADICTION: "kitchen can survive" vs break-even deadline (shared)
    # Tab 48 says it can't. She signs — the data is her data.
    con.execute("UPDATE rulings SET signer='Yuki Tanaka' WHERE id=1")
    signed += 1

    # [2] CROSS-DOMAIN: Saturday meal contradicts survival (shared)
    # Same as Damon's signing — the soul and the drain. She signs.
    con.execute("UPDATE rulings SET signer='Yuki Tanaka' WHERE id=2")
    signed += 1

    # [3] CONTRADICTION: "tech was not her life" vs 2 AM spreadsheet habit
    # Tab 48 at 2 AM. The PM left the building but not the reflex.
    # She signs — the spreadsheet is the evidence.
    con.execute("UPDATE rulings SET signer='Yuki Tanaka' WHERE id=3")
    signed += 1

    # [4] CONTRADICTION: "performing poverty" vs real cuts on hands
    # The safety net is real ($185K offer in inbox). The cuts are also real.
    # The bombardment graduated this from fear to fact. She signs.
    con.execute("UPDATE rulings SET signer='Yuki Tanaka' WHERE id=4")
    signed += 1

    # [5] SUPERSEDES: Harumi's bento supersedes Kenji's "soup kitchen"
    # The bento deliveries stopped. The delivery service isn't running.
    # The mother's actions no longer counter the father's words. She does
    # NOT sign — the supersede's evidence evaporated.

    # [6] REFINES: "this doesn't scale" from Alex's rejection into kitchen thesis
    # Correct; it doesn't. At 200 people and zero revenue, the thesis is
    # being tested. She signs.
    con.execute("UPDATE rulings SET signer='Yuki Tanaka' WHERE id=6")
    signed += 1

    # [7] CROSS-DOMAIN: Sleeping through night vs 2 AM spreadsheet
    # She is no longer sleeping through the night. Tab 48. She signs.
    con.execute("UPDATE rulings SET signer='Yuki Tanaka' WHERE id=7")
    signed += 1

    # [8] CROSS-DOMAIN: Fear of performing poverty vs Sachiko's garden
    # The grandmother grew food for the neighborhood. Yuki feeds people
    # on Saturday. The parallel held through the bombardment. She signs.
    con.execute("UPDATE rulings SET signer='Yuki Tanaka' WHERE id=8")
    signed += 1

    # [9] CONTRADICTION: "transparency is the deal" vs not telling Damon
    # She just rejected her own transparency decision. She signs the
    # contradiction — it's the one she's living.
    con.execute("UPDATE rulings SET signer='Yuki Tanaka' WHERE id=9")
    signed += 1

    # [10] REFINES: "performing poverty" graduated to fact
    # The $185K offer. The class gap is not a fear, it's a spreadsheet
    # column. She signs.
    con.execute("UPDATE rulings SET signer='Yuki Tanaka' WHERE id=10")
    signed += 1

    # [11] CROSS-DOMAIN: Tab 48 contradicts "can survive"
    # The PM's own model says it can't. She signs.
    con.execute("UPDATE rulings SET signer='Yuki Tanaka' WHERE id=11")
    signed += 1

    # [12] SUPERSEDES: Priya's new offer supersedes old standing recommendation
    # A door held open is courtesy. $185K during a crisis is gravity.
    # She signs — gravity is what she's feeling.
    con.execute("UPDATE rulings SET signer='Yuki Tanaka' WHERE id=12")
    signed += 1

    lw.write(session, "turn",
             f"Yuki signed {signed} of 12 rulings. Left unsigned: Harumi's bento supersede (evidence evaporated).",
             {"signed": signed, "unsigned": 1})

    # --- GAPS ---

    gap_decisions = [
        # Shared pre-bombardment
        (49, "Will Hector renew at below-market?", None, None),
        (50, "Can the grant cover the gap?", None, None),
        (51, "Inspector finds something they can't fix?", None, None),
        (52, "Is the Saturday meal sacred or negotiable?", "DRAFT",
         "For Damon it's sacred. For the spreadsheet it's $1200/week. She hasn't said which answer she holds, and the silence is its own answer."),
        (53, "Do they agree on what the kitchen is for?", "DRAFT",
         "No. Damon cooks for people. Yuki runs the numbers that keep the cooking possible. They haven't said what happens when the numbers say stop and the people say please."),

        # Yuki-private pre-bombardment
        (54, "Will she tell Damon about Priya's standing offer?", "REJECTED",
         "Moot. The standing offer became a $185K six-month contract. The old question is overtaken by the new one."),
        (55, "Can she eat dinner at parents' without defending kitchen?", None, None),
        (56, "What happens when RSU money runs out?", "DRAFT",
         "It depends on whether she takes the Priya contract. If she does, the RSU question is answered with tech money again. If she doesn't, it runs out in the same six weeks Tab 48 names."),
        (57, "Does she resent Damon for not reading the spreadsheet?", "SEALED",
         "Yes. She built 48 tabs. He reads none of them. She resents it and she understands it and the resentment is not about the spreadsheet, it's about the gap between a $185K inbox and a cash register that says $0."),
        (58, "Is the lit degree the key to the grant narrative?", "DRAFT",
         "The grant committee went dark. The narrative is in a queue behind a national emergency. The degree is still the key; the lock is somewhere else right now."),
        (59, "Will Alex reach out when kitchen gets press?", None, None),
        (60, "Can she admit she misses the paycheck?", "SEALED",
         "Tab 48 at 2 AM is the admission. She ran it twelve times. The number didn't change. She misses the paycheck because $185K is the paycheck and it's in her inbox and she hasn't deleted it."),
        (61, "What does Sachiko's garden mean to Damon?", None, None),
        (62, "Is tab 47 the one where she models going back?", "SEALED",
         "Tab 48 is called 'Bombardment Scenario.' Tab 47 doesn't matter anymore. Every tab after 47 models the crisis. She is not modeling going back — she is modeling what happens if she stays."),

        # Bombardment gaps
        (71, "Does she tell Damon before or after inspection?", "DRAFT",
         "She didn't tell him at all. The question is no longer when to tell him — it's how long the not-telling can hold before it becomes the thing that breaks them instead of the bombardment."),
        (72, "If she takes the contract, does the kitchen survive?", "DRAFT",
         "Without her: no operations lead, no spreadsheet, no grant application, no one who speaks the language of the people who give money. The kitchen without Yuki is Damon alone in a space that serves 200 and earns $0."),
        (73, "Can the partnership survive the gap?", None, None),
        (74, "Does she go to Palo Alto for a weekend and not come back?", None, None),
        (75, "Is Tab 48 the last tab?", "DRAFT",
         "No. She will build Tab 49. The number won't change. She builds tabs because the building is the thing she does when she can't sleep, and the not-sleeping is the thing she does when the answer is one she doesn't want."),
    ]

    for gid, _, action, reason in gap_decisions:
        if action is None:
            gaps_left_open += 1
            continue
        if action == "SEALED":
            con.execute(
                "UPDATE canon SET status='SEALED', sealed_by='Yuki Tanaka', "
                "sealed_at=?, reason=? WHERE id=?",
                (ts, reason, gid))
            sealed += 1
            gaps_resolved += 1
        elif action == "REJECTED":
            con.execute(
                "UPDATE canon SET status='REJECTED', sealed_by='Yuki Tanaka', "
                "sealed_at=?, reason=? WHERE id=?",
                (ts, reason, gid))
            rejected += 1
            gaps_resolved += 1
        elif action == "DRAFT":
            con.execute(
                "UPDATE canon SET status='DRAFT', reason=? WHERE id=?",
                (reason, gid))
            gaps_resolved += 1

    core_seals = [
        1,   # Co-founded the Kindling Kitchen (shared)
        5,   # Left $160K to co-found the kitchen
        7,   # The PM left the building but not the reflex
    ]
    for fid in core_seals:
        con.execute(
            "UPDATE canon SET status='SEALED', sealed_by='Yuki Tanaka', "
            "sealed_at=? WHERE id=?", (ts, fid))
        sealed += 1

    lw.write(session, "turn",
             f"Yuki addressed gaps and sealed core facts. Total sealed: {sealed}",
             {"sealed": sealed, "gaps_resolved": gaps_resolved, "gaps_left_open": gaps_left_open})

    lw.write(session, "session_close",
             f"Yuki is done. Sealed: {sealed}. Rejected: {rejected}. Signed: {signed}. Gaps open: {gaps_left_open}.",
             {"sealed": sealed, "rejected": rejected, "signed": signed, "gaps_left_open": gaps_left_open})

    con.commit()
    con.close()
    return {
        "name": "Yuki Tanaka",
        "sealed": sealed, "rejected": rejected, "signed": signed,
        "gaps_resolved": gaps_resolved, "gaps_left_open": gaps_left_open,
    }


# ---------------------------------------------------------------------------
# RUNNER
# ---------------------------------------------------------------------------

LIVES = {
    "marcus": ("marcus-life-sandbox", marcus_shows_up),
    "june": ("june-life-sandbox", june_shows_up),
    "damon": ("damon-life-sandbox", damon_shows_up),
    "yuki": ("yuki-life-sandbox", yuki_shows_up),
}


def is_dead(db_path: str) -> bool:
    """Check whether resolution.py recorded a death in this database."""
    con = sqlite3.connect(db_path)
    row = con.execute(
        "SELECT state FROM ledger WHERE kind='session_close' "
        "AND state LIKE '%\"dead\"%' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    con.close()
    if row:
        try:
            s = json.loads(row[0])
            return s.get("status") == "dead"
        except (json.JSONDecodeError, TypeError):
            pass
    return False


def run_one(name: str, verify: bool = False) -> dict:
    box_name, fn = LIVES[name]
    db_path = str(SCRATCHPAD / box_name / "campaign.db")
    backup = str(SCRATCHPAD / box_name / "campaign.db.pre-progression")
    if not Path(db_path).exists():
        print(f"ERROR: {db_path} not found — run the life module first")
        return {}

    if is_dead(db_path):
        print(f"\n{'=' * 60}")
        print(f"  {name.title()} — DEAD (resolution)")
        print(f"{'=' * 60}")
        print(f"  Skipped. The dead do not show up.")
        print(f"  Their PENDING decisions stay PENDING forever.")
        return {"name": name.title(), "dead": True, "sealed": 0,
                "rejected": 0, "signed": 0, "gaps_resolved": 0,
                "gaps_left_open": 0}

    shutil.copy2(db_path, backup)

    before = collect_metrics(db_path)
    result = fn(db_path)
    after = collect_metrics(db_path)

    print(f"\n{'=' * 60}")
    print(f"  {result['name']} — progression complete")
    print(f"{'=' * 60}")
    print(f"  Before:  canon={before['facts_total']}  statuses={before['facts_by_status']}")
    print(f"  After:   canon={after['facts_total']}   statuses={after['facts_by_status']}")
    print(f"  Sealed:  {result['sealed']}")
    print(f"  Rejected: {result['rejected']}")
    print(f"  Signed:  {result['signed']} rulings")
    print(f"  Gaps:    {result['gaps_resolved']} resolved, {result['gaps_left_open']} left open")
    print(f"  Ledger:  {before['ledger_entries']} → {after['ledger_entries']} entries")
    print(f"  Rulings signed: {before['rulings_signed']} → {after['rulings_signed']}")

    if verify and VERIFY_AVAILABLE:
        code, detail = verify_chain(db_path)
        print(f"  Chain:   {'PASS' if code == 0 else 'FAIL'} ({detail})")
        code2, detail2 = verify_canon(db_path)
        print(f"  Canon:   {'PASS' if code2 == 0 else 'FAIL'} ({detail2})")

    return result


def main(argv=None):
    argv = argv or sys.argv[1:]
    verify = "--verify" in argv
    targets = [a for a in argv if not a.startswith("-")]

    if not targets:
        targets = list(LIVES.keys())

    all_results = []
    for name in targets:
        if name not in LIVES:
            print(f"Unknown life: {name}. Available: {', '.join(LIVES.keys())}")
            continue
        result = run_one(name, verify=verify)
        all_results.append(result)

    if len(all_results) > 1:
        alive = [r for r in all_results if not r.get("dead")]
        dead = [r for r in all_results if r.get("dead")]
        print(f"\n{'=' * 60}")
        print(f"  SUMMARY — {len(alive)} survived, {len(dead)} dead")
        print(f"{'=' * 60}")
        total_sealed = sum(r.get("sealed", 0) for r in alive)
        total_rejected = sum(r.get("rejected", 0) for r in alive)
        total_signed = sum(r.get("signed", 0) for r in alive)
        total_gaps_resolved = sum(r.get("gaps_resolved", 0) for r in alive)
        total_gaps_open = sum(r.get("gaps_left_open", 0) for r in alive)
        print(f"  Sealed:   {total_sealed}")
        print(f"  Rejected: {total_rejected}")
        print(f"  Signed:   {total_signed} rulings")
        print(f"  Gaps:     {total_gaps_resolved} resolved, {total_gaps_open} left open")
        for r in alive:
            n = r.get("name", "?")
            print(f"    {n}: sealed={r.get('sealed',0)} rejected={r.get('rejected',0)} "
                  f"signed={r.get('signed',0)} gaps_open={r.get('gaps_left_open',0)}")
        for r in dead:
            n = r.get("name", "?")
            print(f"    {n}: DEAD — did not show up")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
