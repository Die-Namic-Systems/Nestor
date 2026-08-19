#!/usr/bin/env python3
"""June Akiyama — 58, retired Navy nurse, rural Oregon.

Widowed (husband Tom, Navy corpsman, killed in Afghanistan 2011).
One adult son, Ryan (32), estranged — he blames her for re-enlisting
after Tom's death instead of coming home.  Lives alone on a small
hobby farm outside Grants Pass.  Three years into retirement.
The tension: she built a life around service and now the service
is over, the person she served beside is gone, and the person she
was serving it all for won't return her calls.

Domains lean toward body→signal (aging alone, the farm's demands),
memory→lesson (Tom, the Navy, Ryan's childhood she missed),
choice→consequence (career over presence), fear→truth (isolation,
health, dying alone on the property).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provision import create_life, SCRATCHPAD

BOX = SCRATCHPAD / "june-life-sandbox"
DB = str(BOX / "campaign.db")

PROTAGONIST = {
    "name": "June Akiyama",
    "born": 1968,
    "location": "Grants Pass, OR",
    "occupation": "Retired (Navy Nurse Corps, Lt. Commander)",
}

ENTITIES = [
    {"kind": "pc", "canonical": "June Akiyama",
     "aliases": ["June", "Mom", "Lieutenant Commander", "me"],
     "sheet": {"born": 1968, "location": "Grants Pass, OR", "retired": 2023,
               "service": "Navy Nurse Corps, 24 years"}},
    {"kind": "npc", "canonical": "Tom Akiyama",
     "aliases": ["Tom", "my husband", "your father"],
     "sheet": {"born": 1967, "died": 2011, "cause": "KIA, Helmand Province",
               "rank": "HM1 (Fleet Marine Force)", "relation": "husband"}},
    {"kind": "npc", "canonical": "Ryan Akiyama",
     "aliases": ["Ryan", "my son", "the kid"],
     "sheet": {"born": 1994, "relation": "son", "lives_in": "Portland, OR",
               "occupation": "Software developer", "last_contact": "2024-03"}},
    {"kind": "npc", "canonical": "Dr. Marguerite Hsu",
     "aliases": ["Dr. Hsu", "Marguerite", "the vet"],
     "sheet": {"relation": "neighbor / large-animal vet", "lives": "adjacent property"}},
    {"kind": "npc", "canonical": "Pastor Linda Greaves",
     "aliases": ["Pastor Linda", "Linda"],
     "sheet": {"relation": "pastor, Grants Pass Community Church", "since": "2020"}},
    {"kind": "npc", "canonical": "Corpsman Benny Delacroix",
     "aliases": ["Benny", "Del", "my old corpsman"],
     "sheet": {"relation": "former colleague, Navy", "lives_in": "San Diego",
               "status": "calls every Sunday"}},
    {"kind": "place", "canonical": "The Akiyama Farm",
     "aliases": ["the farm", "home", "the property", "my place"],
     "sheet": {"type": "hobby farm", "acres": 12, "city": "Grants Pass, OR",
               "note": "goats, chickens, a greenhouse, and too much silence"}},
    {"kind": "place", "canonical": "Naval Medical Center San Diego",
     "aliases": ["Balboa", "NMCSD", "the hospital"],
     "sheet": {"type": "military hospital", "note": "last duty station, 2018-2023"}},
    {"kind": "place", "canonical": "The Wall in the Hallway",
     "aliases": ["the wall", "the photos"],
     "sheet": {"type": "memorial", "note": "Tom's flag case, unit photos, Ryan's school pictures — the whole story in one hallway"}},
    {"kind": "item", "canonical": "Tom's Dog Tags",
     "aliases": ["the tags", "his tags"],
     "sheet": {"type": "personal effect", "status": "worn daily under her shirt since 2011"}},
    {"kind": "item", "canonical": "The Unanswered Letters",
     "aliases": ["the letters", "the stack"],
     "sheet": {"type": "correspondence", "count": "eleven",
               "note": "handwritten letters to Ryan, all returned unopened, in a shoebox under the bed"}},
    {"kind": "guest", "canonical": "The Sunday Phone Call",
     "aliases": ["the call", "Sunday"],
     "sheet": {"meaning": "Benny calls every Sunday at 0800 Pacific — it's the only appointment on her calendar that isn't a vet visit or a church service"}},
]

CANON_FACTS = [
    # choice→consequence (5)
    {"fact": "Re-enlisted after Tom's death — Ryan was 17 and needed her home; she needed to be anywhere but home", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Chose Grants Pass over San Diego for retirement — closer to Ryan, who won't see her, farther from Benny, who would", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Kept the farm instead of downsizing — twelve acres is too much for one person, but selling means admitting the family isn't coming", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Took the Nurse Corps over line duty — Tom went to the front, she went to the ward; he didn't come back", "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Stopped calling Ryan after the eleventh letter came back — the silence is her answer, or her cowardice, and she can't tell which", "status": "DRAFT", "domain": "choice→consequence"},

    # memory→lesson (5)
    {"fact": "Tom proposed at the Balboa parking lot after a double shift — no ring, just a question and a vending machine coffee", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Ryan's Little League game she watched on a satellite phone from Kandahar — he hit a double and she clapped and nobody heard", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "The casualty notification — two Marines at the door and she knew before they spoke because she'd done the same walk for other families", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Benny held her when she broke at the memorial and said 'You don't owe anyone composure' — the only useful sentence that week", "status": "DRAFT", "domain": "memory→lesson"},
    {"fact": "Ryan's graduation — she was there, front row, and he looked through her like glass", "status": "DRAFT", "domain": "memory→lesson"},

    # belief→evidence (4)
    {"fact": "Service was the right choice — evidence: 24 years of patients who walked out of her ward alive", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "Ryan will come around — evidence: none; hope is not evidence and she knows it", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "She can handle the farm alone — evidence: the fence she fixed in January, the goat she delivered in March, the back she threw out in April", "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "Tom would have understood — evidence: he re-enlisted too; they were the same person in different uniforms", "status": "DRAFT", "domain": "belief→evidence"},

    # body→signal (4)
    {"fact": "The knee that locks on cold mornings — 24 years of hospital floors, and now the floor is dirt and gravel", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "Waking at 0530 without an alarm — the Navy set her clock and retirement can't unset it", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "The flinch when a helicopter flies over the valley — Grants Pass is under a flight path and the body doesn't know it's not a medevac", "status": "DRAFT", "domain": "body→signal"},
    {"fact": "Hands steady enough to suture but shaking when she writes 'Dear Ryan' — the body knows which wound is open", "status": "DRAFT", "domain": "body→signal"},

    # fear→truth (4)
    {"fact": "Falling on the property with no one to find her — Dr. Hsu checks in, but not every day", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "Ryan will learn she died from a stranger's phone call — but that's his choice, not hers", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "The farm will outlast her and no one will want it — but the goats don't know that, and they need feeding now", "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "She stayed too long in the Navy and lost the civilian skills — but she can start an IV in the dark and deliver a breech kid goat, so the skills are just different", "status": "DRAFT", "domain": "fear→truth"},

    # decision→decision (4)
    {"fact": "She will not move to Portland uninvited", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "The letters stop but the door stays open", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "She will ask Dr. Hsu about the medical alert system", "status": "PENDING", "domain": "decision→decision"},
    {"fact": "Tom's tags stay on until they don't — that day is not today", "status": "PENDING", "domain": "decision→decision"},

    # year→milestone (10)
    {"fact": "1968 — Born in Sacramento. Third-generation Japanese-American; grandparents were at Tule Lake", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "1986 — Enlisted, Navy Hospital Corps; wanted to be a doctor, settled for the path she could afford", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "1990 — Commissioned through the Nurse Corps program; Tom was her patient with a broken wrist, then her husband", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "1994 — Ryan born at Balboa; Tom was deployed; Benny drove her to the hospital", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2001 — First deployment to Afghanistan; Ryan was 7 and stayed with Tom's parents", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2011 — Tom KIA, Helmand Province. Ryan was 17. She re-enlisted within the month", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2014 — Ryan stopped answering calls. The letters started", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2018 — Final tour at NMCSD; Lt. Commander; the rank Tom would have been proud of", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2023 — Retired. Bought the Grants Pass property. Twelve acres, five goats, and the quiet she didn't know she'd hate", "status": "DRAFT", "domain": "year→milestone"},
    {"fact": "2025 — The eleventh letter came back unopened. She stopped writing", "status": "DRAFT", "domain": "year→milestone"},

    # entity→entity (6)
    {"fact": "'Mom' resolves to June Akiyama — but only Benny still calls her that, joking", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the vet' resolves to Dr. Marguerite Hsu — neighbor, not just the goat doctor", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the hospital' resolves to Naval Medical Center San Diego — Balboa, where everything began and ended", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'his tags' resolves to Tom's dog tags — worn daily, the weight is the point", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the letters' resolves to eleven handwritten letters to Ryan, all returned, in a shoebox under the bed", "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'Sunday' resolves to Benny's weekly phone call — 0800 Pacific, never missed", "status": "DRAFT", "domain": "entity→entity"},
]

RULINGS = [
    {"text": "CONTRADICTION: 'Service was the right choice' vs Ryan's estrangement — the ward saved lives but the home lost one", "scope": "canon"},
    {"text": "CONTRADICTION: 'Tom would have understood' vs the fact that understanding doesn't undo absence — mutual re-enlistment is a shared flaw, not a justification", "scope": "canon"},
    {"text": "CONTRADICTION: 'She can handle the farm alone' vs the thrown-out back in April — capability and sustainability are different measurements", "scope": "canon"},
    {"text": "SUPERSEDES: Stopping the letters supersedes the open-door claim — a door is not open if nobody knocks and you've stopped inviting", "scope": "rule"},
    {"text": "SUPERSEDES: The Sunday call with Benny supersedes the isolation narrative — she is not alone, she is lonely, and those are different problems", "scope": "rule"},
    {"text": "REFINES: The helicopter flinch refined the retirement from 'peaceful' to 'quiet' — quiet is not peace, it's the absence of the noise she knew how to navigate", "scope": "rule"},
    {"text": "REFINES: Wearing Tom's tags refined grief from past tense to present continuous — she is not mourning, she is carrying", "scope": "rule"},
    {"text": "CROSS-DOMAIN: Body signal (shaking hand writing to Ryan) contradicts belief (hands steady enough to suture) — the wound is relational, not physical", "scope": "session"},
    {"text": "CROSS-DOMAIN: Fear of dying alone contradicts choice to buy the farm alone — she chose the isolation she's afraid of", "scope": "session"},
    {"text": "CROSS-DOMAIN: Memory of Tom's proposal (no ring, parking lot) parallels current life (no ceremony, just showing up) — she married the pattern, not just the person", "scope": "session"},
]

GAPS = [
    "Will Ryan read the letters after she's gone?",
    "Does Benny know she wears the tags?",
    "Can she ask Dr. Hsu for help without framing it as a medical question?",
    "What happens the first time she can't get up after a fall?",
    "Is the farm a home or a foxhole?",
    "Will she go to the VA for the knee?",
    "Does she know what Ryan does for a living?",
    "What would she say if Ryan called tomorrow?",
    "Is the greenhouse a project or a reason to get up?",
    "Can she forgive herself for re-enlisting, or does she need Ryan to do it first?",
    "What does she tell Pastor Linda about the letters?",
    "Will she let Benny visit?",
    "Does she talk to Tom at the wall, or just stand there?",
    "Is retirement the first thing she's failed at?",
]


def main():
    print(f"==> Provisioning June Akiyama's life sandbox")
    create_life(DB, PROTAGONIST, ENTITIES, CANON_FACTS, RULINGS, GAPS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
