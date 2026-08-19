#!/usr/bin/env python3
"""Damon Reyes — 31, culinary school grad, formerly incarcerated, Oakland.

Did five years (age 19-24) for armed robbery.  Got his GED inside,
then culinary certificate at Laney College after release.  Co-founded
The Kindling Kitchen with Yuki Tanaka.  Engaged to Monique (30, social
worker).  His mother Carmen lives in East Oakland and pretends the
five years didn't happen.

The tension: he built a new life but the record follows him into
every lease, every loan application, every background check.
The kitchen is proof he changed; the paperwork says he's a risk.

INTERCONNECTED with Yuki Tanaka — they share the kitchen, the
neighborhood, the landlord, the inspector, and the Saturday meal.
Private domains: reentry, the record, Carmen, Monique, the years inside.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provision import create_life, SCRATCHPAD
from shared_entities import (
    SHARED_ENTITIES, SHARED_FACTS, SHARED_RULINGS, SHARED_GAPS,
)

BOX = SCRATCHPAD / "damon-life-sandbox"
DB = str(BOX / "campaign.db")

PROTAGONIST = {
    "name": "Damon Reyes",
    "born": 1995,
    "location": "Oakland, CA",
    "occupation": "Chef / co-founder, The Kindling Kitchen",
}

PRIVATE_ENTITIES = [
    {"kind": "pc", "canonical": "Damon Reyes",
     "aliases": ["Damon", "D", "Chef Reyes", "me"],
     "sheet": {"born": 1995, "location": "Oakland, CA",
               "record": "armed robbery, served 5 years (2014-2019)",
               "education": "GED (inside), culinary certificate (Laney College, 2021)"}},
    {"kind": "npc", "canonical": "Monique Thibodeaux",
     "aliases": ["Monique", "Mo", "my fiancée"],
     "sheet": {"born": 1996, "relation": "fiancée", "occupation": "Social worker, Alameda County",
               "note": "met at a reentry resource fair; she was staffing a table, he was a client"}},
    {"kind": "npc", "canonical": "Carmen Reyes",
     "aliases": ["my mother", "Carmen", "Mami"],
     "sheet": {"relation": "mother", "age": 54, "lives_in": "East Oakland",
               "note": "pretends the five years were a long trip — loves him by not mentioning it"}},
    {"kind": "npc", "canonical": "Chef Antoine Broussard",
     "aliases": ["Chef Antoine", "Antoine", "my instructor"],
     "sheet": {"relation": "Laney College culinary instructor",
               "note": "wrote his first recommendation letter — 'the best hands in the cohort'"}},
    {"kind": "npc", "canonical": "Marcus 'Silky' Webb",
     "aliases": ["Silky", "my old cellmate"],
     "sheet": {"relation": "former cellmate", "status": "back inside, second offense",
               "note": "they don't talk about it but Damon sends money to Silky's daughter"}},
    {"kind": "place", "canonical": "San Quentin",
     "aliases": ["inside", "Q", "the facility"],
     "sheet": {"type": "state prison", "note": "five years, ages 19-24; the kitchen detail saved him"}},
    {"kind": "place", "canonical": "Damon and Monique's Apartment",
     "aliases": ["home", "our place", "the apartment"],
     "sheet": {"type": "residence", "neighborhood": "Temescal, Oakland",
               "note": "the third apartment — first two rejected him on background check"}},
    {"kind": "item", "canonical": "The Recommendation Letter",
     "aliases": ["the letter", "Antoine's letter"],
     "sheet": {"type": "document", "from": "Chef Antoine Broussard",
               "note": "laminated, in his wallet — the first professional document with his name that wasn't a court record"}},
]

ENTITIES = SHARED_ENTITIES + PRIVATE_ENTITIES

PRIVATE_FACTS = [
    # choice→consequence (5)
    {"fact": "Robbed a liquor store at 19 — needed $200 for rent and got five years instead", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Took the kitchen detail in San Quentin — it was that or laundry, and the kitchen had knives they trusted him with", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Told Monique about the record on the second date — she said 'I know, I read your intake file by accident'", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Chose Oakland over LA for the kitchen — closer to Carmen, closer to the neighborhood that saw him go in", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Sends money to Silky's daughter every month — $150 he can't afford because Silky is the version of him that didn't get the kitchen detail", "status": "DRAFT", "domain": "choice→consequence"},

    # memory→lesson (5)
    {"fact": "The first meal he cooked inside — powdered eggs and canned tomatoes, and the CO said 'not bad' — the first compliment in eleven months", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Carmen's face at the release — she brought a suit that didn't fit and he wore it anyway because the suit was the sentence she served", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Chef Antoine tasting his mole and saying nothing for ten seconds — the silence was the diploma", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "The first apartment rejection — 'We don't rent to...' and the sentence didn't need finishing", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Monique at the reentry fair — she handed him a pamphlet and a granola bar and said 'eat first, then we'll talk about services'", "status": "DRAFT", "domain": "memory→lesson"},

    # belief→evidence (4)
    {"fact": "People can change — evidence: he is standing in a kitchen he owns, not one he was assigned to", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "The record will always matter — evidence: the third apartment application, the bank loan denial, the catering client who googled him", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "Carmen loves him — evidence: the suit, the weekly Sunday dinner, the way she never asks about the kitchen's finances", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "Monique sees him, not the file — evidence: she said yes to the ring he bought with catering money", "status": "DRAFT", "domain": "belief→evidence"},

    # body→signal (4)
    {"fact": "The count — he still wakes at count time, 0300, even though nobody is counting", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "The flinch when someone stands behind him in the kitchen — five years of watching your back doesn't turn off at the gate", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "His hands in the dough — the only time his shoulders drop; Monique says she can hear the exhale from the living room", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "Walking past a cop car and his pace changing — not faster, not slower, just different, and he notices the difference every time", "status": "DRAFT", "domain": "body→signal"},

    # fear→truth (4)
    {"fact": "Going back inside — but the kitchen is open and Monique is home and the parole ended two years ago", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "Yuki will leave when it gets hard — but she left a $160K salary for this, and that's not a tourist's bet", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "Carmen will find out about the bank loan denial — but Carmen survived raising him alone in East Oakland; a loan denial is not the worst news he's brought home", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "Silky's path is still possible — but Silky didn't have Chef Antoine or Monique or the kitchen; the variables are different, not the odds", "status": "DRAFT", "domain": "fear→truth"},

    # decision→decision (4)
    {"fact": "He will tell the full story on the grant application — no euphemisms, no gaps", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "The wedding happens in the kitchen — Monique said yes to the ring and the venue in the same sentence", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "He will not hire anyone with a record without telling Yuki first — transparency is the deal", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "If the kitchen closes, he cooks somewhere else — the record doesn't erase the hands", "status": "PENDING", "domain": "decision→decision"},

    # year→milestone (8)
    {"fact": "1995 — Born in East Oakland. Father left before he could remember; Carmen worked two jobs", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2014 — Armed robbery, age 19. Sentenced to seven years, served five", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2016 — Kitchen detail at San Quentin. The CO who assigned him said 'you've got two years to make this mean something'", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2019 — Released. Carmen's suit. The first night in a bed without a count", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2020 — Enrolled at Laney College culinary program. Met Chef Antoine", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2021 — Graduated Laney. Met Monique at the reentry fair. Met Yuki at a food co-op volunteer shift", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2024 — The Kindling Kitchen opens. First Saturday meal: 23 people. Abuela Rosa brought salsa", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2025 — Proposed to Monique. The ring cost less than a month's food budget for Saturday meals; she said it cost exactly right", "status": "DRAFT", "domain": "year→milestone"},

    # entity→entity (4)
    {"fact": "'inside' resolves to San Quentin — five years, kitchen detail, the place that almost ended him and accidentally trained him", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the letter' resolves to Chef Antoine's recommendation — laminated, in his wallet, the first document he's proud of", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'Silky' resolves to Marcus Webb — former cellmate, back inside; the money Damon sends is not charity, it's a debt to a road not taken", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'Mami' resolves to Carmen Reyes — she pretends the five years were a trip; the pretending is how she loves him", "status": "DRAFT", "domain": "entity→entity"},
]

CANON_FACTS = SHARED_FACTS + PRIVATE_FACTS

PRIVATE_RULINGS = [
    {"text": "CONTRADICTION: 'People can change' vs the record that follows every application — the change is real and the system doesn't care", "scope": "canon"},
    {"text": "CONTRADICTION: 'The record will always matter' vs Monique seeing him, not the file — it matters everywhere except where it matters most", "scope": "canon"},
    {"text": "SUPERSEDES: Chef Antoine's letter supersedes the court record as the defining document — but only in the kitchen, not at the bank", "scope": "rule"},
    {"text": "REFINES: Sending money to Silky's daughter refined 'I got lucky' into 'I got a kitchen detail and Silky got laundry' — luck is resource allocation", "scope": "rule"},
    {"text": "CROSS-DOMAIN: Body signal (waking at count time) contradicts belief (people can change) — the body hasn't changed; the choices have", "scope": "session"},
    {"text": "CROSS-DOMAIN: Fear of Yuki leaving contradicts shared evidence (she left $160K) — distrust is a prison habit, not a present-tense assessment", "scope": "session"},
]

RULINGS = SHARED_RULINGS + PRIVATE_RULINGS

PRIVATE_GAPS = [
    "Does the grant committee read 'armed robbery' and stop?",
    "Can he tell Carmen about the loan denial?",
    "What happens when a catering client googles him mid-contract?",
    "Will he hire someone with a record?",
    "Does Monique worry about him going back or has she moved past it?",
    "What does he cook when he's scared?",
    "Can he visit Silky without it pulling him backward?",
    "What would Chef Antoine say about the Saturday meal margins?",
    "Is the wedding in the kitchen a celebration or a statement?",
]

GAPS = SHARED_GAPS + PRIVATE_GAPS


def main():
    print(f"==> Provisioning Damon Reyes's life sandbox")
    create_life(DB, PROTAGONIST, ENTITIES, CANON_FACTS, RULINGS, GAPS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
