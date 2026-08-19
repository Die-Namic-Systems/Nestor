#!/usr/bin/env python3
"""Yuki Tanaka — 29, left tech, co-founder of The Kindling Kitchen, Oakland.

Third-generation Japanese-American.  Left a $160K product manager job at
a mid-stage startup to co-found a community kitchen with Damon Reyes.
Her parents (Kenji and Harumi, Palo Alto) see the kitchen as a detour
from the career they immigrated-for-their-parents-to-immigrate-for.
She sees it as the first thing she's done that she can explain without
a slide deck.

The tension: she traded legibility for meaning, and the meaning
has a four-month deadline attached to a lease renewal.

INTERCONNECTED with Damon Reyes — they share the kitchen, the
neighborhood, the landlord, the inspector, and the Saturday meal.
Private domains: tech guilt, family pressure, the Palo Alto she left,
the relationship she ended to come here.
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

BOX = SCRATCHPAD / "yuki-life-sandbox"
DB = str(BOX / "campaign.db")

PROTAGONIST = {
    "name": "Yuki Tanaka",
    "born": 1997,
    "location": "Oakland, CA",
    "occupation": "Operations lead / co-founder, The Kindling Kitchen",
}

PRIVATE_ENTITIES = [
    {"kind": "pc", "canonical": "Yuki Tanaka",
     "aliases": ["Yuki", "Y", "me"],
     "sheet": {"born": 1997, "location": "Oakland, CA",
               "previous": "Product Manager, Lattice (2019-2023)",
               "education": "Stanford, CS + Comparative Literature"}},
    {"kind": "npc", "canonical": "Kenji Tanaka",
     "aliases": ["my father", "Dad", "Kenji"],
     "sheet": {"relation": "father", "age": 61, "lives_in": "Palo Alto, CA",
               "occupation": "Retired engineer (Lockheed Martin)",
               "note": "said 'we didn't come to this country for you to run a soup kitchen'"}},
    {"kind": "npc", "canonical": "Harumi Tanaka",
     "aliases": ["my mother", "Mom", "Harumi"],
     "sheet": {"relation": "mother", "age": 58, "lives_in": "Palo Alto, CA",
               "occupation": "Piano teacher",
               "note": "sends bento ingredients to the kitchen without comment — the comment is the ingredients"}},
    {"kind": "npc", "canonical": "Alex Chen",
     "aliases": ["Alex", "my ex"],
     "sheet": {"relation": "ex-boyfriend", "occupation": "Software engineer, Google",
               "note": "broke up when she left tech — he said 'I can't follow you into something that doesn't scale'"}},
    {"kind": "npc", "canonical": "Priya Krishnamurthy",
     "aliases": ["Priya", "my old PM lead"],
     "sheet": {"relation": "former manager at Lattice",
               "note": "writes her a LinkedIn recommendation annually without being asked — a door held open"}},
    {"kind": "place", "canonical": "Palo Alto",
     "aliases": ["home", "my parents' house", "the peninsula"],
     "sheet": {"type": "hometown", "note": "45 minutes and a world from Fruitvale"}},
    {"kind": "place", "canonical": "Yuki's Studio",
     "aliases": ["my place", "the studio"],
     "sheet": {"type": "residence", "neighborhood": "West Oakland",
               "note": "400 square feet, $1800/month, the cheapest thing she's ever chosen"}},
    {"kind": "item", "canonical": "The Spreadsheet",
     "aliases": ["the model", "the numbers", "the spreadsheet"],
     "sheet": {"type": "financial model",
               "note": "a 47-tab spreadsheet that models every path to break-even — the PM in her built it; the founder in her checks it at 2 AM"}},
]

ENTITIES = SHARED_ENTITIES + PRIVATE_ENTITIES

PRIVATE_FACTS = [
    # choice→consequence (5)
    {"fact": "Left a $160K salary and RSUs for a community kitchen — the stock vested three months after she quit", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Chose Damon as a co-founder after one volunteer shift — she saw his hands in the dough and knew he was the cook she wasn't", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Ended things with Alex — he wanted the version of her that shipped features, not the one that chops onions at 5 AM", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Moved to West Oakland from Palo Alto — her rent went up and her square footage went down and her commute became a bike ride", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Told her father about the kitchen over the phone — she could hear him set down his coffee; the silence was louder than the sentence about the soup kitchen", "status": "DRAFT", "domain": "choice→consequence"},

    # memory→lesson (5)
    {"fact": "The product launch that got 40K signups and felt like nothing — the metrics were green and she was gray", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Grandmother Sachiko's story about the internment camp garden — 'we grew food because it was the one thing they couldn't take from the soil'", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "The first Saturday meal — 23 people and she cried in the walk-in cooler afterward because someone said 'thank you' and meant it about food, not features", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Alex saying 'this doesn't scale' — he was right about the business and wrong about the point", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Harumi's first bento delivery to the kitchen — no note, just ingredients for tamago and tsukemono; the food was the note", "status": "DRAFT", "domain": "memory→lesson"},

    # belief→evidence (4)
    {"fact": "Tech was not her life — evidence: she doesn't miss the standups, the sprints, the OKRs; she misses the paycheck", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "She is good at this — evidence: the 47-tab spreadsheet, the three catering contracts, the grant application she wrote in one sitting", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "Her parents will come around — evidence: Harumi's bento ingredients; Kenji hasn't said 'soup kitchen' again since the first time", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "Damon is the right partner — evidence: he doesn't read the spreadsheet and she doesn't taste the mole; the division is clean", "status": "DRAFT", "domain": "belief→evidence"},

    # body→signal (4)
    {"fact": "Sleeping through the night for the first time in years — the anxiety dreams about sprint velocity stopped when the sprints did", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "The 2 AM spreadsheet check — the PM muscle memory found a new target; the worry migrated, not the relief", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "Her hands after Saturday prep — cuts, burns, onion sting; her body has evidence now, not just her calendar", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "The bike ride through Fruitvale at 5 AM — dark streets, nobody else up, and she's not afraid; the neighborhood is hers now in a way Palo Alto never was", "status": "DRAFT", "domain": "body→signal"},

    # fear→truth (4)
    {"fact": "Her father was right — but right about what? The money, the stability, the legibility? He wasn't wrong about any of them. He was wrong about what matters", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "Damon's record will sink the grant — but the grant committee asked for 'founder stories' and his is the one that matters", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "She'll go back to tech when the money runs out — but Priya's standing recommendation is a safety net, not a destination, and she knows the difference", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "She's performing poverty — $1800 studio, Stanford degree, parents in Palo Alto; the kitchen is real but the sacrifice is optional, and she knows Damon knows", "status": "DRAFT", "domain": "fear→truth"},

    # decision→decision (4)
    {"fact": "She will not ask Kenji for money for the kitchen", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "If the lease renews at market rate, she renegotiates before she fundraises — the spreadsheet says there's a number that works", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "She tells Damon about the standing job offer from Priya — transparency is the deal, his phrase, and it applies to her too", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "She learns to cook one dish well enough to serve on Saturday — the operations lead should know what she's operating on", "status": "PENDING", "domain": "decision→decision"},

    # year→milestone (8)
    {"fact": "1997 — Born in Palo Alto. Third-generation; Sachiko's garden story was the family scripture", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2015 — Stanford, CS and Comparative Literature. Kenji wanted just CS; the lit degree was her first quiet rebellion", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2019 — Product manager at Lattice. The salary made Kenji stop asking about the lit degree", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2021 — Met Damon at a food co-op volunteer shift. He was making stock from scraps and she thought 'this is what product-market fit actually looks like'", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2023 — Quit Lattice. The RSUs vested three months later. Alex left the same week", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2024 — The Kindling Kitchen opens. She built the spreadsheet; Damon built the menu. Abuela Rosa showed up week one", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2025 — Grant application submitted. Catering contracts signed. The lease clock starts", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2026 — Four months to break-even or close. The spreadsheet has 47 tabs and one answer", "status": "DRAFT", "domain": "year→milestone"},

    # entity→entity (4)
    {"fact": "'the spreadsheet' resolves to a 47-tab financial model — the PM's last product, built for a kitchen instead of a SaaS company", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'my ex' resolves to Alex Chen — he said 'this doesn't scale'; she heard 'you don't scale'", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the peninsula' resolves to Palo Alto — 45 minutes from Fruitvale, a world from the kitchen", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the garden' resolves to Sachiko's internment camp garden — the family origin story: food is what they can't take from the soil", "status": "DRAFT", "domain": "entity→entity"},
]

CANON_FACTS = SHARED_FACTS + PRIVATE_FACTS

PRIVATE_RULINGS = [
    {"text": "CONTRADICTION: 'Tech was not her life' vs the 2 AM spreadsheet habit — the PM left the building but not the body", "scope": "canon"},
    {"text": "CONTRADICTION: 'She's performing poverty' vs the real cuts on her hands — the safety net is real but so is the work; the contradiction is the privilege, not the commitment", "scope": "canon"},
    {"text": "SUPERSEDES: Harumi's bento deliveries supersede Kenji's 'soup kitchen' remark — the mother's actions outweigh the father's words, but neither parent has said what they mean", "scope": "rule"},
    {"text": "REFINES: 'This doesn't scale' refined from Alex's rejection into the kitchen's thesis — correct; it's not supposed to", "scope": "rule"},
    {"text": "CROSS-DOMAIN: Body signal (sleeping through the night) contradicts body signal (2 AM spreadsheet) — the anxiety changed shape, not size", "scope": "session"},
    {"text": "CROSS-DOMAIN: Fear of performing poverty contradicts Sachiko's garden story — the grandmother grew food in a camp; the granddaughter grows food in a gentrifying neighborhood; the privilege is different, the impulse is the same", "scope": "session"},
]

RULINGS = SHARED_RULINGS + PRIVATE_RULINGS

PRIVATE_GAPS = [
    "Will she tell Damon about Priya's standing offer?",
    "Can she eat dinner at her parents' house without defending the kitchen?",
    "What happens when the RSU money runs out?",
    "Does she resent Damon for not reading the spreadsheet?",
    "Is the lit degree the key to the grant narrative or just her own?",
    "Will Alex reach out when the kitchen gets press?",
    "Can she admit she misses the paycheck without it meaning she was wrong?",
    "What does Sachiko's garden mean to Damon, if anything?",
    "Is the 47th tab the one where she models going back to tech?",
]

GAPS = SHARED_GAPS + PRIVATE_GAPS


def main():
    print(f"==> Provisioning Yuki Tanaka's life sandbox")
    create_life(DB, PROTAGONIST, ENTITIES, CANON_FACTS, RULINGS, GAPS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
