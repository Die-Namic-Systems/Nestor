#!/usr/bin/env python3
"""Marcus Oyelaran — 42, high school music teacher, Detroit.

Divorced, two kids (Aiden 14, Zara 10) in a custody split.  Four years
sober.  Gave up a promising jazz career for stability after rehab.
The tension: he chose the safe life and it saved him, but the music
didn't stop mattering.

Domains lean toward body→signal (recovery, relapse triggers),
choice→consequence (career vs sobriety), memory→lesson (the marriage,
the band years), fear→truth (relapse, custody loss).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provision import create_life, SCRATCHPAD

BOX = SCRATCHPAD / "marcus-life-sandbox"
DB = str(BOX / "campaign.db")

PROTAGONIST = {
    "name": "Marcus Oyelaran",
    "born": 1984,
    "location": "Detroit, MI",
    "occupation": "High school music teacher",
}

ENTITIES = [
    {"kind": "pc", "canonical": "Marcus Oyelaran",
     "aliases": ["Mr. O", "Marc", "Dad", "me"],
     "sheet": {"born": 1984, "location": "Detroit, MI", "occupation": "Music teacher, Cass Tech HS"}},
    {"kind": "npc", "canonical": "Aiden Oyelaran",
     "aliases": ["my son", "Aiden", "the teenager"],
     "sheet": {"born": 2012, "relation": "son", "lives_with": "Marcus (weekdays)"}},
    {"kind": "npc", "canonical": "Zara Oyelaran",
     "aliases": ["my daughter", "Zara", "Z", "the little one"],
     "sheet": {"born": 2016, "relation": "daughter", "lives_with": "Keisha (primary)"}},
    {"kind": "npc", "canonical": "Keisha Oyelaran",
     "aliases": ["my ex", "Keisha", "their mother"],
     "sheet": {"relation": "ex-wife", "divorced": 2021, "occupation": "Nurse, Henry Ford Hospital"}},
    {"kind": "npc", "canonical": "Terrence 'Big T' Williams",
     "aliases": ["Big T", "T", "my sponsor"],
     "sheet": {"relation": "AA sponsor", "since": 2022}},
    {"kind": "npc", "canonical": "Principal Diane Kessler",
     "aliases": ["Dr. Kessler", "the principal", "Diane"],
     "sheet": {"relation": "employer", "school": "Cass Tech HS"}},
    {"kind": "npc", "canonical": "Jerome Oyelaran",
     "aliases": ["my brother", "Jerome", "Rome"],
     "sheet": {"relation": "younger brother", "lives_in": "Atlanta"}},
    {"kind": "place", "canonical": "Cass Technical High School",
     "aliases": ["Cass Tech", "school", "work"],
     "sheet": {"type": "public magnet school", "city": "Detroit"}},
    {"kind": "place", "canonical": "The Elbow Room",
     "aliases": ["the club", "the gig", "where it happened"],
     "sheet": {"type": "jazz club", "city": "Detroit", "note": "last gig before rehab"}},
    {"kind": "place", "canonical": "Marcus's Apartment",
     "aliases": ["home", "my place", "the apartment"],
     "sheet": {"type": "residence", "neighborhood": "Midtown Detroit"}},
    {"kind": "item", "canonical": "The Selmer Tenor",
     "aliases": ["my horn", "the saxophone", "the Selmer"],
     "sheet": {"type": "instrument", "model": "Selmer Mark VI tenor", "status": "in the closet since 2020"}},
    {"kind": "guest", "canonical": "The Empty Chair at Recitals",
     "aliases": ["the chair", "the absence"],
     "sheet": {"meaning": "the seat Zara saves for him at her school events on Keisha's weekends — sometimes he's there, sometimes custody math says no"}},
]

CANON_FACTS = [
    # choice→consequence (5)
    {"fact": "Chose teaching over gigging — sobriety needed a schedule, and a schedule needed a paycheck", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Sold the van — the band's touring vehicle became Zara's car seat fund", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Told Keisha about the relapse at three months sober instead of hiding it — lost the marriage, kept the honesty", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Said yes to the marching band director position — more hours, less practice time, but the kids need it", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Let Aiden hear the Coltrane records — the kid picked up a saxophone and Marcus felt the thing he was trying not to feel", "status": "DRAFT", "domain": "choice→consequence"},

    # memory→lesson (5)
    {"fact": "The Elbow Room set where he played 'Naima' drunk and the room went quiet — not because it was good but because it was obvious", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Keisha said 'I can't watch you choose this over us again' and he heard the word 'again' for the first time", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "The student who wrote 'Mr. O made me want to practice' on the year-end survey — the sentence he carries", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Jerome visiting from Atlanta, seeing the apartment, saying nothing — the silence was the review", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Zara's piano recital where she played the piece he taught her and looked for him in the audience — he was there", "status": "DRAFT", "domain": "memory→lesson"},

    # belief→evidence (4)
    {"fact": "Sobriety is not the absence of wanting — evidence: he can name every bar within walking distance of Cass Tech", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "Teaching is music — evidence: the kid who couldn't read treble clef in September played first chair by May", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "The marriage failed because of me — evidence: Keisha tried for two years after the first relapse", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "I am not my father — evidence: Dad played professionally and never came home; Marcus comes home and doesn't play", "status": "DRAFT", "domain": "belief→evidence"},

    # body→signal (4)
    {"fact": "The shaking hands before a parent-teacher conference — the body remembers performing", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "Three AM awake and the saxophone case in the closet is louder than the street — the craving is not for alcohol", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "The relief when the school day starts — structure is the medication", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "Running the marching band rehearsal in August heat and not wanting a drink afterward — that's new, and it's data", "status": "DRAFT", "domain": "body→signal"},

    # fear→truth (4)
    {"fact": "If I play again I'll drink again — but Aiden is learning and I'm teaching him sober", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "Keisha will take full custody — but the parenting plan has held for three years", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "The kids will see me the way I see my father — but Zara saves me a chair", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "I am wasting the talent — but 200 kids a year get a music education because I'm here", "status": "DRAFT", "domain": "fear→truth"},

    # decision→decision (4)
    {"fact": "I will not play professionally again", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "The kids come before the horn", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "Sobriety is a daily decision, not a permanent state", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "I owe Keisha an amends that isn't words", "status": "PENDING", "domain": "decision→decision"},

    # year→milestone (10)
    {"fact": "1984 — Born in Detroit. Father was a session musician who toured more than he was home", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2002 — Scholarship to Wayne State for jazz performance", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2006 — First professional gig; the Marcus O Quartet", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2010 — Married Keisha; she thought the gigging would slow down", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2012 — Aiden born; Marcus missed the birth for a festival date", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2016 — Zara born; first relapse three months later", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2019 — Second relapse; The Elbow Room incident; Keisha's ultimatum", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2020 — Rehab. Sold the van. Enrolled in teaching certification", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2021 — Divorce finalized. Started at Cass Tech. The Selmer went in the closet", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2024 — Aiden picks up a saxophone; Marcus teaches him at the kitchen table", "status": "DRAFT", "domain": "year→milestone"},

    # entity→entity (6)
    {"fact": "'Mr. O' resolves to Marcus Oyelaran", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'my ex' resolves to Keisha Oyelaran", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'my horn' resolves to the Selmer Mark VI tenor saxophone, in the closet since 2020", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'where it happened' resolves to The Elbow Room — last gig before rehab", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the absence' resolves to the empty chair Zara saves at recitals", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'my sponsor' resolves to Terrence 'Big T' Williams — three years and counting", "status": "DRAFT", "domain": "entity→entity"},
]

RULINGS = [
    {"text": "CONTRADICTION: 'I will not play professionally again' vs teaching Aiden the saxophone at the kitchen table", "scope": "canon"},
    {"text": "CONTRADICTION: 'The marriage failed because of me' vs Keisha's two-year effort after the first relapse — shared responsibility is harder to hold than sole blame", "scope": "canon"},
    {"text": "CONTRADICTION: 'Sobriety is a daily decision' vs the relief that the craving is for music, not alcohol — is that progress or substitution?", "scope": "canon"},
    {"text": "SUPERSEDES: Teaching Aiden supersedes the closeted Selmer — the horn is out, just in smaller hands", "scope": "rule"},
    {"text": "SUPERSEDES: The parenting plan holding for three years supersedes the custody fear", "scope": "rule"},
    {"text": "REFINES: The 3 AM saxophone craving refined the addiction narrative — the substance was the vehicle, the music was the destination", "scope": "rule"},
    {"text": "REFINES: The student's year-end survey refined 'I am wasting the talent' into 'the talent is being spent differently'", "scope": "rule"},
    {"text": "CROSS-DOMAIN: Body signal (shaking hands before conferences) contradicts belief (teaching is music) — if it's music, why the stage fright?", "scope": "session"},
    {"text": "CROSS-DOMAIN: Fear of becoming father contradicts evidence of daily presence — same pattern as Elena's, different instrument", "scope": "session"},
    {"text": "CROSS-DOMAIN: Memory of Keisha's 'again' contradicts the amends decision — an amends that isn't words requires action, and every action risks the 'again'", "scope": "session"},
]

GAPS = [
    "Will he play the Selmer again?",
    "Does Aiden know about the relapses?",
    "Can he watch Aiden perform without it triggering something?",
    "Will Keisha ever trust him with overnights on her weekends?",
    "Is teaching enough or is it settling?",
    "What happens when a student asks him to sit in with the jazz combo?",
    "Does Big T know about the 3 AM saxophone craving?",
    "Will Jerome ever say what he actually thinks?",
    "Is the empty chair a gift or an accusation?",
    "What does he tell Aiden about why he stopped playing?",
    "Can sobriety survive the music coming back?",
    "What would he play if he picked up the horn right now?",
    "Does Zara remember the bad years or only the after?",
    "Is Detroit home or is it the place he couldn't leave?",
]


def main():
    print(f"==> Provisioning Marcus Oyelaran's life sandbox")
    create_life(DB, PROTAGONIST, ENTITIES, CANON_FACTS, RULINGS, GAPS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
