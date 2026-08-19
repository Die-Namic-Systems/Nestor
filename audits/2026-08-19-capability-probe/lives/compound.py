#!/usr/bin/env python3
"""compound.py — The survivors converge, and find out what the sky was.

A parallel session in the same world, on the same seed.  Whoever lived
through `session.py` is eligible here; whoever died is not, and the dead
are named rather than quietly dropped.

The site is June Akiyama's farm outside Grants Pass.  That is not an
arbitrary choice — her bombardment canon already reads *"The nurse set up
a triage station. Nobody came."*  This is the session where they come.

Four phases:

  1. CONVERGENCE  Each candidate rolls the road.  Oakland is four hundred
                  miles; Detroit is two thousand three hundred.  Some do
                  not arrive, and one of them has to choose desertion to
                  try.
  2. OPERATIONS   Ability checks — not saving throws — against a document
                  ladder.  Success accumulates EVIDENCE.  Failure
                  accumulates HEAT, and heat has teeth.
  3. REVELATION   What the assembled evidence actually says.
  4. ARRIVAL      They descend.  This is fixed.

On the fixed ending, deliberately: rolling *whether* aliens exist would be
a coin-flip on the premise, which is not a game.  The arrival is a global
event exactly as the bombardment was.  What the dice decide is whether
anyone assembled the picture before it happened, and who was standing
there when it did.  Understanding is the win condition; the sky opens
either way.

The tell is physical and was always latent in the fiction — NASA said they
could not explain the source.  Rocks do not decelerate.

Covenant: the arrival is written as DRAFT canon and its meaning as a
PENDING question.  The machine can open the sky.  It cannot tell you what
it means.

Rules content derived from the System Reference Document 5.1,
copyright Wizards of the Coast, LLC., licensed under the
Creative Commons Attribution 4.0 International License.
https://dnd.wizards.com/resources/systems-reference-document

Usage:
    python3 compound.py                  # full session, seed=42
    python3 compound.py --seed 7
    python3 compound.py --verbose        # roll-by-roll
    python3 compound.py --distribution 500
    python3 compound.py --apply          # write the compound campaign.db
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import npcs as npc_mod
import resolution
from provision import SCRATCHPAD, provision_schema, row_hash
from resolution import (
    Character,
    Hazard,
    LedgerWriter,
    modifier,
    resolve_death_saves,
    resolve_one,
    roll_d20,
    roll_dice,
)

COMPOUND_DB = SCRATCHPAD / "compound-sandbox" / "campaign.db"

SITE = {
    "name": "The Akiyama farm",
    "where": "twelve miles outside Grants Pass, Oregon",
    "why": "Water, land, a barn with a triage station already set up in it, "
           "and a retired Navy nurse who has been waiting for someone to "
           "need it.",
}


# =========================================================================
# NEW MECHANIC: ABILITY CHECKS WITH DEGREES OF SUCCESS
# =========================================================================
# Saving throws answer "does this hurt me."  Document work needs the other
# half of the d20 system: ability checks, where beating the DC by a margin
# means you got more than you went in for, and missing it badly means you
# were noticed.

CRIT = "critical"
FULL = "full"
PARTIAL = "partial"
FAIL = "fail"
BOTCH = "botch"

DEGREE_LABEL = {
    CRIT: "CRITICAL", FULL: "FULL", PARTIAL: "PARTIAL",
    FAIL: "FAIL", BOTCH: "BOTCH",
}


def ability_check(
    char: Character, ability: str, dc: int, rng: random.Random,
    proficient: bool = False, expertise: bool = False,
    advantage: bool = False, disadvantage: bool = False,
) -> dict:
    """SRD 5.1 ability check with degrees of success.

    nat 20, or DC+10 .. CRITICAL  everything, plus a thread they weren't after
    DC+5 ............... FULL      the document, clean
    DC ................. PARTIAL   fragments; enough to point somewhere
    below DC ........... FAIL      nothing
    nat 1, or DC-5 ..... BOTCH     nothing, and the query is now logged
    """
    if char.exhaustion >= 1:
        # SRD 5.1 exhaustion level 1: disadvantage on ability checks.
        disadvantage = True
    if advantage and disadvantage:
        advantage = disadvantage = False

    r1 = roll_d20(rng)
    if advantage:
        r2 = roll_d20(rng)
        natural = max(r1, r2)
    elif disadvantage:
        r2 = roll_d20(rng)
        natural = min(r1, r2)
    else:
        natural = r1

    bonus = char.mod(ability)
    if proficient:
        bonus += char.proficiency_bonus * (2 if expertise else 1)
    total = natural + bonus

    if natural == 1:
        degree = BOTCH
    elif natural == 20 or total >= dc + 10:
        degree = CRIT
    elif total >= dc + 5:
        degree = FULL
    elif total >= dc:
        degree = PARTIAL
    elif total <= dc - 5:
        degree = BOTCH
    else:
        degree = FAIL

    return {
        "natural": natural, "bonus": bonus, "total": total, "dc": dc,
        "degree": degree, "ability": ability, "proficient": proficient,
        "disadvantage": disadvantage, "advantage": advantage,
    }


# =========================================================================
# PHASE 1: CONVERGENCE — the roads
# =========================================================================

@dataclass
class Traveller:
    key: str
    source: str          # "pc" or "npc"
    origin: str
    miles: int
    hazards: list
    motive: str
    cost: str = ""       # what coming here costs them
    protected_by: str = ""  # an adult is shielding them: advantage on saves


def road(name: str, desc: str, ability: str, dc: int,
         dice: str, dtype: str, half: bool = True,
         exh: int = 0, narrative: str = "") -> Hazard:
    return Hazard(
        name=name, description=desc, save_ability=ability, dc=dc,
        damage_dice=dice, damage_type=dtype, half_on_save=half,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=exh, narrative=narrative,
    )


# Route hazard sets, by distance. The road is the same road for everyone;
# what differs is how much of it you have to be on.
ROADBLOCK = road(
    "A roadblock that is not official",
    "Somebody has decided this stretch is theirs. There are four of them "
    "and a truck across both lanes.",
    "CHA", 13, "2d6", "bludgeoning", half=True,
    narrative="Most of them let you through. This is about the ones who don't.",
)
FUEL = road(
    "Running dry between towns",
    "Stations are dry or rationed. The distance between working pumps is "
    "now longer than a tank.",
    "INT", 13, "", "", exh=2,
    narrative="You walk the last of it, or you don't go.",
)
IMPACT_ON_ROAD = road(
    "An entry, close",
    "One comes down near enough to light the inside of the car. The road "
    "afterwards is not where it was.",
    "DEX", 14, "5d6", "bludgeoning",
    narrative="Three weeks in and it still stops the breath.",
)
EXPOSURE = road(
    "Nights in the vehicle",
    "August days, cold nights, no fixed shelter, and water you are "
    "rationing against a distance you keep re-estimating.",
    "CON", 13, "", "", exh=2,
    narrative="The distance is the enemy. It always was.",
)
CROWD = road(
    "A town that is not taking anyone",
    "A place that has decided it is full. They are not cruel about it. "
    "They are just done.",
    "WIS", 12, "2d6", "psychic", half=False,
    narrative="You would have made the same call from the other side of it.",
)

# A close entry is a catastrophe, not a toll booth. Making every traveller
# eat one turned the road into a scripted execution for anyone with a
# commoner's hit points — measured at N=300, it killed 97% of the ordinary
# people and 99.7% of Hector. It is a 1-in-3 event per leg instead.
IMPACT_CHANCE = {"regional": 1, "long": 2, "transcontinental": 3}

ROUTES = {
    "onsite": [],
    "local": [ROADBLOCK],
    "regional": [FUEL, ROADBLOCK],
    "long": [FUEL, EXPOSURE, ROADBLOCK],
    "transcontinental": [FUEL, EXPOSURE, ROADBLOCK, CROWD, EXPOSURE],
}

ROUTE_OF = {id(v): k for k, v in ROUTES.items()}


def roll_road(t: "Traveller", rng: random.Random) -> list:
    """The traveller's actual hazard list for this run.

    Fixed hazards are the road itself — fuel, distance, people. The close
    entry is rolled: each leg is a 1-in-3 chance, so a long road means
    more chances rather than a guaranteed catastrophe.
    """
    hazards = list(t.hazards)
    route = ROUTE_OF.get(id(t.hazards), "onsite")
    legs = IMPACT_CHANCE.get(route, 0)
    hits = sum(1 for _ in range(legs) if rng.randint(1, 3) == 1)
    hazards.extend([IMPACT_ON_ROAD] * hits)
    return hazards, hits


TRAVELLERS = [
    Traveller("june", "pc", "the farm itself", 0, ROUTES["onsite"],
              "It is her farm. She has been ready for this since 2011."),
    Traveller("hsu", "npc", "the adjacent property", 2, ROUTES["onsite"],
              "She already came with a backhoe once. She never left."),
    Traveller("linda", "npc", "Grants Pass", 20, ROUTES["local"],
              "She drove twenty miles on half a tank to bring water. "
              "This is the same trip with more in the truck."),
    Traveller("damon", "pc", "Oakland", 400, ROUTES["regional"],
              "The kitchen closed. He can feed two hundred people, and "
              "that skill is worth more here than a lease was there.",
              cost="He leaves the building his wedding was going to be in."),
    Traveller("yuki", "pc", "Oakland", 400, ROUTES["regional"],
              "She found the network. Church to kitchen to farm — she is "
              "the one who speaks the language of people who move things.",
              cost="She deletes Priya's email without answering it."),
    Traveller("monique", "npc", "Oakland", 400, ROUTES["regional"],
              "County crisis response collapsed into no county. She goes "
              "where Damon goes."),
    Traveller("antoine", "npc", "Oakland", 400, ROUTES["regional"],
              "He taught Damon to cook. He is old and he is coming anyway."),
    Traveller("hector", "npc", "Oakland", 400, ROUTES["regional"],
              "The building failed inspection. He has no building to be "
              "landlord of.",
              cost="He signs the deed over to nobody and locks it anyway."),
    Traveller("benny", "npc", "San Diego", 800, ROUTES["long"],
              "He calls June every Sunday. He stopped being able to, and "
              "that is how she knew something had changed.",
              cost="He is recalled. Leaving is desertion, and he knows the "
                   "word for it."),
    Traveller("keisha", "npc", "Detroit", 2300, ROUTES["transcontinental"],
              "Marcus is dead. The hospital is running on generators. She "
              "has two children and a nursing licence and no reason to stay.",
              cost="She leaves the city both her children were born in."),
    Traveller("aiden", "npc", "Detroit", 2300, ROUTES["transcontinental"],
              "Fourteen, and his father died in a parking lot three weeks "
              "ago. He goes where his mother goes.",
              protected_by="Keisha"),
    Traveller("zara", "npc", "Detroit", 2300, ROUTES["transcontinental"],
              "Ten. She has been told it is a long drive.",
              protected_by="Keisha"),
    Traveller("big_t", "npc", "Detroit", 2300, ROUTES["transcontinental"],
              "He buried the man he sponsored for four years. He drives "
              "Keisha and the kids because somebody has to and because "
              "staying is worse.",
              cost="He leaves thirty people who came to the church basement "
                   "for him."),
]


def build_character(key: str, source: str) -> Character | None:
    if source == "pc":
        maker = {
            "june": resolution.make_june,
            "damon": resolution.make_damon,
            "yuki": resolution.make_yuki,
            "marcus": resolution.make_marcus,
        }[key]
        return maker()
    npc = npc_mod.NPCS_BY_KEY.get(key)
    return npc.to_character() if npc else None


def display_name(key: str, source: str) -> str:
    if source == "pc":
        return {"june": "June Akiyama", "damon": "Damon Reyes",
                "yuki": "Yuki Tanaka", "marcus": "Marcus Oyelaran"}[key]
    return npc_mod.NPCS_BY_KEY[key].name


def convergence(seed: int, survivors: dict) -> dict:
    """Roll every eligible traveller's road. Returns the arrived roster."""
    rng = random.Random(seed ^ 0x5EED_C0DE)

    arrived, lost, ineligible = [], [], []

    for t in TRAVELLERS:
        name = display_name(t.key, t.source)
        if not survivors.get(t.key, False):
            ineligible.append((t, name))
            continue

        char = build_character(t.key, t.source)
        # Weeks have passed since the bombardment resolution.
        char.current_hp = char.max_hp
        char.exhaustion = 0

        def snapshot(c):
            # The arrival phase mutates these same Character objects, so
            # the roster has to record what was true on arrival day rather
            # than hold a live reference to a body that keeps changing.
            return {"hp": c.current_hp, "max_hp": c.max_hp,
                    "exhaustion": c.exhaustion}

        if not t.hazards:
            arrived.append({"t": t, "name": name, "char": char,
                            "result": None, "status": "alive",
                            "impacts": 0, "on_arrival": snapshot(char)})
            continue

        hazards, impacts = roll_road(t, rng)

        # Someone shielding you is the difference between a road and a
        # sentence. SRD 5.1: advantage on the save.
        if t.protected_by:
            hazards = [
                Hazard(**{**h.__dict__, "advantage": True}) for h in hazards
            ]

        ally = {"allies_present": True, "ally_name": "the convoy",
                "medicine_mod": 1,
                "note": "People travel together now. It is the only way "
                        "anyone travels."}
        result = resolve_one(char, hazards, ally, rng)
        entry = {"t": t, "name": name, "char": char, "impacts": impacts,
                 "result": result, "status": result["status"],
                 "on_arrival": snapshot(char)}
        (arrived if result["status"] == "alive" else lost).append(entry)

    return {"arrived": arrived, "lost": lost, "ineligible": ineligible}


def compound_recovery(roster: list):
    """Weeks pass at the farm while the document work happens.

    Two nurses, a corpsman and a vet, in a barn with a triage station.
    Without this the arrival lands on bodies still carrying road damage —
    Keisha reached the farm at 1/27 with five levels of exhaustion, and
    exhaustion 6 is death.
    """
    for e in roster:
        c = e["char"]
        if not c.alive:
            continue
        c.current_hp = c.max_hp
        c.exhaustion = max(0, c.exhaustion - 3)
        e["after_recovery"] = {"hp": c.current_hp, "max_hp": c.max_hp,
                               "exhaustion": c.exhaustion}


# =========================================================================
# PHASE 2: OPERATIONS — the document ladder
# =========================================================================

@dataclass
class Document:
    key: str
    title: str
    holder: str          # where it lives
    ability: str
    dc: int
    evidence: int        # evidence points on FULL
    heat: int            # heat on BOTCH
    skill: str           # what the check represents
    content: str         # what it says
    partial: str         # what fragments give you
    requires: str = ""   # prerequisite document key


DOCUMENTS = [
    Document(
        key="county",
        title="Josephine County emergency management incident log",
        holder="a county office with no working phone line",
        ability="CHA", dc=12, evidence=1, heat=1,
        skill="Persuasion — talking a clerk into a filing cabinet",
        content="Impact timings for the county, logged by hand. "
                "The entries cluster. Somebody wrote 'again, same field?' "
                "in the margin and did not follow it up.",
        partial="Timings for three weeks, incomplete, but the clustering "
                "is visible even in fragments.",
    ),
    Document(
        key="notam",
        title="FAA NOTAM archive and grounding orders",
        holder="a public archive nobody has thought to take down",
        ability="INT", dc=13, evidence=1, heat=0,
        skill="Investigation — reading a public record properly",
        content="The groundings are not random. They precede impacts by "
                "forty to ninety minutes, consistently, in regions where "
                "no impact had yet occurred.",
        partial="The groundings look predictive. It could be caution. "
                "It reads like caution.",
        requires="county",
    ),
    Document(
        key="tracking",
        title="Space Force orbital tracking deltas, weeks 1-3",
        holder="a terminal on a base Benny still has a badge for",
        ability="INT", dc=15, evidence=2, heat=2,
        skill="Investigation — knowing which system holds the raw numbers",
        content="Object trajectories, uncorrected. The deltas do not fit "
                "ballistic arcs. Every object's velocity falls between "
                "acquisition and entry.",
        partial="Velocity columns that do not behave. Without the "
                "ballistic reference you cannot prove they should.",
        requires="notam",
    ),
    Document(
        key="assessment",
        title="Classified preliminary assessment — DECELERATION",
        holder="a safe in an office whose occupant was recalled elsewhere",
        ability="DEX", dc=17, evidence=3, heat=3,
        skill="Sleight of Hand — a safe, a badge, and nine minutes",
        content="The finding, in one line: THE OBJECTS ARE DECELERATING. "
                "Ballistic bodies do not shed velocity on approach. "
                "The assessment recommends the public framing remain "
                "'meteoroid activity of undetermined origin.'",
        partial="A cover sheet and a redacted summary. The word "
                "DECELERATION survives the redaction because it is in "
                "the title.",
        requires="tracking",
    ),
    Document(
        key="protocol",
        title="Contact protocol annex — signal and posture",
        holder="the same safe, underneath the assessment",
        ability="INT", dc=18, evidence=3, heat=3,
        skill="Investigation — understanding what you are holding",
        content="The deceleration curves resolve to arrival windows. "
                "The annex specifies posture on arrival: no ordnance, "
                "no broadcast, no approach. It reads less like a plan "
                "than like an instruction somebody was given.",
        partial="Arrival windows without the posture annex. You know when. "
                "You do not know what anyone decided to do about it.",
        requires="assessment",
    ),
]

DOCS_BY_KEY = {d.key: d for d in DOCUMENTS}

# Who is competent at what. Proficiency is drawn from the life data, not
# invented: Yuki built forty-eight tabs of financial model; Benny has the
# badge; June ran Navy medical administration; Damon has spent five years
# learning exactly how institutions handle a person.
OPERATIVES = {
    "yuki": {"abilities": ["INT"], "expertise": True,
             "why": "INT 17 and the reflex that wakes her at 2 AM to run "
                    "the numbers one more time."},
    "benny": {"abilities": ["INT", "DEX"], "expertise": False,
              "why": "Thirty years in the system. He knows which terminal "
                     "and whose office."},
    "june": {"abilities": ["CHA", "WIS"], "expertise": False,
             "why": "Navy medical administration. She knows how a filing "
                    "system thinks."},
    "damon": {"abilities": ["DEX", "CHA"], "expertise": False,
              "why": "Five years learning how institutions handle a person, "
                     "from the inside of one."},
    "keisha": {"abilities": ["INT", "CHA"], "expertise": False,
               "why": "Hospital records. Same locks, different building."},
    "monique": {"abilities": ["CHA", "WIS"], "expertise": False,
                "why": "County systems were her job."},
}

# Up to three passes at any one document, and the whole operation stops if
# heat reaches the abort line — at that point they are not stealing files,
# they are being watched stealing files.
MAX_ATTEMPTS = 3
HEAT_ABORT = 12

HEAT_EVENTS = [
    (4, "A vehicle parks at the end of the county road for six hours "
        "and then leaves."),
    (7, "Benny's badge stops working. No notice, no explanation."),
    (10, "Two people arrive asking about a corpsman by name. "
         "Pastor Linda tells them nothing and is believed."),
    (13, "The farm's road is watched openly. Nobody approaches. "
         "That is somehow worse."),
]


def operations(seed: int, roster: list, rng: random.Random) -> dict:
    """Run the document ladder with whoever is here and capable."""
    by_key = {e["t"].key: e for e in roster}
    operatives = [(k, by_key[k]) for k in OPERATIVES if k in by_key]

    evidence = 0
    heat = 0
    collected = {}
    log = []
    heat_fired = []

    if not operatives:
        return {"evidence": 0, "heat": 0, "collected": {}, "log": [],
                "operatives": [], "heat_fired": [],
                "blocked": "Nobody who arrived can do this work."}

    for doc in DOCUMENTS:
        if doc.requires and doc.requires not in collected:
            log.append({"doc": doc, "skipped": True,
                        "reason": f"needs {DOCS_BY_KEY[doc.requires].title}"})
            continue

        # Best-suited first, then whoever else can try. Nobody gives up on
        # a filing cabinet after one attempt — but every retry is another
        # query somebody can correlate later.
        ranked = sorted(
            [(k, e) for k, e in operatives
             if doc.ability in OPERATIVES[k]["abilities"]] or operatives,
            key=lambda ke: ke[1]["char"].mod(doc.ability)
            + (ke[1]["char"].proficiency_bonus
               * (2 if OPERATIVES[ke[0]]["expertise"] else 1)),
            reverse=True,
        )

        attempts = []
        gained = 0
        for attempt_no in range(min(MAX_ATTEMPTS, len(ranked) + 1)):
            if heat >= HEAT_ABORT:
                break
            key, entry = ranked[min(attempt_no, len(ranked) - 1)]
            char = entry["char"]

            check = ability_check(
                char, doc.ability, doc.dc, rng,
                proficient=True,
                expertise=OPERATIVES[key]["expertise"],
            )
            deg = check["degree"]
            if attempt_no > 0:
                heat += 1  # going back a second time is its own exposure
            if deg == BOTCH:
                heat += doc.heat

            attempts.append({"operative": entry["name"], "op_key": key,
                             "check": check, "attempt": attempt_no + 1})

            if deg == CRIT:
                gained = doc.evidence + 1
                collected[doc.key] = "full"
                break
            if deg == FULL:
                gained = doc.evidence
                collected[doc.key] = "full"
                break
            if deg == PARTIAL:
                gained = max(1, doc.evidence // 2)
                collected[doc.key] = "partial"
                break

        if not attempts:
            # Heat hit the abort line before this document was ever tried.
            log.append({"doc": doc, "skipped": True, "aborted": True,
                        "reason": f"operation aborted — heat {heat}"})
            continue

        evidence += gained
        final = attempts[-1]

        log.append({"doc": doc, "operative": final["operative"],
                    "op_key": final["op_key"], "check": final["check"],
                    "attempts": attempts, "gained": gained,
                    "heat_now": heat, "skipped": False,
                    "aborted": heat >= HEAT_ABORT})

        for threshold, text in HEAT_EVENTS:
            if heat >= threshold and threshold not in [h[0] for h in heat_fired]:
                heat_fired.append((threshold, text))

    return {"evidence": evidence, "heat": heat, "collected": collected,
            "log": log, "operatives": [e["name"] for _, e in operatives],
            "heat_fired": heat_fired, "blocked": None}


# =========================================================================
# PHASE 3: REVELATION
# =========================================================================

UNDERSTANDING = [
    (9, "CERTAIN", "They know what is coming, when, and that somebody "
                   "decided in advance not to shoot at it."),
    (6, "CONVINCED", "They know the objects decelerate. Rocks do not "
                     "decelerate. They have not worked out the timing."),
    (3, "SUSPICIOUS", "The pattern is wrong and they can say why it is "
                      "wrong, but not what it means."),
    (1, "UNEASY", "Fragments. A margin note. A groundings pattern that "
                  "reads like foreknowledge."),
    (0, "BLIND", "Three weeks of rocks and no reason to think otherwise."),
]


def revelation(evidence: int) -> dict:
    for threshold, tier, text in UNDERSTANDING:
        if evidence >= threshold:
            return {"evidence": evidence, "tier": tier, "text": text,
                    "threshold": threshold}
    return {"evidence": evidence, "tier": "BLIND",
            "text": UNDERSTANDING[-1][2], "threshold": 0}


# =========================================================================
# PHASE 4: ARRIVAL
# =========================================================================
# Fixed. The dice decide who is standing where, not whether it happens.

ARRIVAL_KNOWN = Hazard(
    name="The descent, expected",
    description="They have the arrival window. They are in the barn, "
                "away from glass, with the animals moved and the "
                "generator off.",
    save_ability="WIS", dc=12,
    damage_dice="2d6", damage_type="psychic", half_on_save=False,
    advantage=True, disadvantage=False, exhaustion_on_fail=0,
    narrative="Knowing does not make it small. It makes it survivable.",
)

ARRIVAL_UNKNOWN = Hazard(
    name="The descent, unannounced",
    description="The sky goes wrong in a way that has no precedent, "
                "and they are outdoors, and nobody told them.",
    save_ability="WIS", dc=16,
    damage_dice="5d6", damage_type="psychic", half_on_save=False,
    advantage=False, disadvantage=False, exhaustion_on_fail=1,
    narrative="A mind can be injured by a fact.",
)

ARRIVAL_TEXT = """\
  They do not fall.

  That is the first thing, and for the people who have the deceleration
  curves it is the only confirmation they need: the objects come down
  slowly, and they stop.

  Nine of them over the valley, at an altitude somebody with the tracking
  data could have named to the metre. No sound that carries. The cattle
  do not bolt. Dr. Hsu will say afterwards that this was the part that
  frightened her most, because animals bolt from everything.

  Three weeks of what the news called meteoroid activity of undetermined
  origin. The origin was never undetermined. It was decelerating.
"""


def arrival(roster: list, rev: dict, rng: random.Random) -> dict:
    known = rev["tier"] in ("CERTAIN", "CONVINCED")
    hazard = ARRIVAL_KNOWN if known else ARRIVAL_UNKNOWN
    ally = {"allies_present": True, "ally_name": "the compound",
            "medicine_mod": 4,
            "note": "Two nurses, a corpsman and a vet, all in one barn."}

    outcomes = []
    for entry in roster:
        char = entry["char"]
        if not char.alive:
            continue
        res = resolve_one(char, [hazard], ally, rng)
        outcomes.append({"name": entry["name"], "result": res,
                         "status": res["status"],
                         "hp": res["hp_final"], "max_hp": res["max_hp"]})
    return {"known": known, "hazard": hazard, "outcomes": outcomes}


# =========================================================================
# DATABASE
# =========================================================================

def write_compound_db(state: dict) -> dict:
    db = COMPOUND_DB
    db.parent.mkdir(parents=True, exist_ok=True)
    provision_schema(str(db))
    con = sqlite3.connect(str(db))
    lw = LedgerWriter(con)
    ts = datetime.now(timezone.utc).isoformat()

    counts = {"facts": 0, "gaps": 0, "entities": 0, "rulings": 0}

    def fact(text, reason, status="DRAFT"):
        con.execute(
            "INSERT INTO canon (ts, fact, status, proposed_by, reason) "
            "VALUES (?,?,?,?,?)",
            (ts, text, status, "compound-session", reason))
        counts["gaps" if status == "PENDING" else "facts"] += 1

    lid = lw.write(0, "session_open",
                   f"The compound — {SITE['name']}, {SITE['where']}",
                   {"site": SITE["name"]})
    for e in state["convergence"]["arrived"]:
        con.execute(
            "INSERT INTO entities (kind, canonical, aliases, sheet, "
            "sealed_by, introduced_ledger_id) VALUES (?,?,?,?,?,?)",
            ("pc" if e["t"].source == "pc" else "npc", e["name"],
             json.dumps([]),
             json.dumps({"origin": e["t"].origin, "miles": e["t"].miles,
                         "motive": e["t"].motive, "cost": e["t"].cost}),
             None, lid))
        counts["entities"] += 1
    lw.write(0, "session_close",
             f"{counts['entities']} arrived at the farm", {})

    # Convergence
    lw.write(1, "session_open", "Convergence — the roads", {})
    for e in state["convergence"]["arrived"]:
        fact(f"{e['name']} reached the farm from {e['t'].origin} "
             f"({e['t'].miles} miles). {e['t'].motive}", "convergence")
        if e["t"].cost:
            fact(f"What it cost {e['name']}: {e['t'].cost}", "convergence")
    for e in state["convergence"]["lost"]:
        fact(f"{e['name']} did not reach the farm. "
             f"{e['t'].miles} miles from {e['t'].origin}.", "convergence-death")
        fact(f"Who tells the people at the farm about {e['name']}?",
             "jeles-gap", status="PENDING")
    for t, name in state["convergence"]["ineligible"]:
        fact(f"{name} was already dead before the convergence began.",
             "convergence-ineligible")
    lw.write(1, "turn",
             f"{len(state['convergence']['arrived'])} arrived, "
             f"{len(state['convergence']['lost'])} lost on the road, "
             f"{len(state['convergence']['ineligible'])} already dead",
             {"arrived": len(state["convergence"]["arrived"]),
              "lost": len(state["convergence"]["lost"])})
    lw.write(1, "session_close", "The roster is what it is", {})

    # Operations
    ops = state["operations"]
    lw.write(2, "session_open", "Operations — the document ladder", {})
    for item in ops["log"]:
        doc = item["doc"]
        if item["skipped"]:
            fact(f"NOT OBTAINED: {doc.title}. {item['reason']}.",
                 "operations-blocked")
            continue
        deg = item["check"]["degree"]
        if deg in (CRIT, FULL):
            fact(f"{doc.title} — obtained by {item['operative']}. "
                 f"{doc.content}", "operations")
        elif deg == PARTIAL:
            fact(f"{doc.title} — partial, by {item['operative']}. "
                 f"{doc.partial}", "operations")
        else:
            fact(f"NOT OBTAINED: {doc.title}. "
                 f"{item['operative']} failed the attempt"
                 f"{' and was logged' if deg == BOTCH else ''}.",
                 "operations-failed")
    for threshold, text in ops["heat_fired"]:
        fact(f"HEAT {threshold}: {text}", "operations-heat")
    lw.write(2, "turn",
             f"Evidence {ops['evidence']}, heat {ops['heat']}",
             {"evidence": ops["evidence"], "heat": ops["heat"],
              "collected": ops["collected"]})
    lw.write(2, "session_close", "What could be got, was got", {})

    # Revelation + arrival
    rev = state["revelation"]
    lw.write(3, "session_open", "Revelation", {})
    fact(f"Understanding at arrival: {rev['tier']}. {rev['text']}",
         "revelation")
    lw.write(3, "session_close", f"Tier {rev['tier']}",
             {"tier": rev["tier"], "evidence": rev["evidence"]})

    arr = state["arrival"]
    lw.write(4, "session_open", "Arrival", {})
    fact("They do not fall. Nine objects decelerate over the valley "
         "and stop. The origin was never undetermined.", "arrival")
    for o in arr["outcomes"]:
        if o["status"] != "alive":
            fact(f"{o['name']} did not survive the arrival.", "arrival-death")
    fact("What do they want?", "jeles-gap", status="PENDING")
    fact("Who decided, in advance, not to shoot at them?",
         "jeles-gap", status="PENDING")
    fact("Was the bombardment an approach, or a message, or neither?",
         "jeles-gap", status="PENDING")
    lw.write(4, "turn",
             "Nine objects. They stop. Nobody at the farm has an answer.",
             {"known_in_advance": arr["known"]})
    lw.write(4, "session_close",
             "The session ends with the sky open and the questions PENDING.",
             {})

    con.commit()
    con.close()
    return counts


# =========================================================================
# OUTPUT
# =========================================================================

BAR = "=" * 70


def banner(title: str, sub: str = ""):
    print(f"\n\n{'▓' * 70}")
    print(f"  {title}")
    if sub:
        print(f"  {sub}")
    print("▓" * 70)


def run_session(seed: int, verbose: bool = False) -> dict:
    # The same world, on the same seed.
    npc_outcomes = npc_mod.resolve_npcs(seed)
    ally_ctx = npc_mod.build_ally_context(npc_outcomes)
    pc_results = resolution.resolve_all(seed, ally_context=ally_ctx)

    survivors = {}
    for r in pc_results:
        survivors[r["db_key"]] = r["status"] == "alive"
    for k, r in npc_outcomes.items():
        survivors[k] = r["status"] == "alive"

    conv = convergence(seed, survivors)
    compound_recovery(conv["arrived"])
    rng = random.Random(seed ^ 0xA11E_1234)
    ops = operations(seed, conv["arrived"], rng)
    rev = revelation(ops["evidence"])
    arr = arrival(conv["arrived"], rev, rng)

    return {"seed": seed, "survivors": survivors, "convergence": conv,
            "operations": ops, "revelation": rev, "arrival": arr}


def print_session(state: dict, verbose: bool = False):
    conv = state["convergence"]

    banner("PHASE 1: CONVERGENCE",
           f"{SITE['name']}, {SITE['where']}")
    print(f"\n  {SITE['why']}\n")

    if conv["ineligible"]:
        print("  Not eligible — died in the bombardment:")
        for t, name in conv["ineligible"]:
            print(f"    ☠  {name:<28} would have come from {t.origin}")
        print()

    print("  ARRIVED:")
    for e in sorted(conv["arrived"], key=lambda x: -x["t"].miles):
        snap = e["on_arrival"]
        miles = f"{e['t'].miles:>5} mi" if e["t"].miles else "  on site"
        hp = f"{snap['hp']}/{snap['max_hp']}"
        exh = f" exh {snap['exhaustion']}" if snap["exhaustion"] else ""
        hits = f"  [{e['impacts']} close entry]" if e.get("impacts") else ""
        prot = "  (shielded)" if e["t"].protected_by else ""
        print(f"    ·  {e['name']:<28} {miles}  {hp:>7}{exh}{hits}{prot}")
        if e["t"].cost:
            print(f"       cost: {e['t'].cost}")

    if conv["lost"]:
        print("\n  LOST ON THE ROAD:")
        for e in conv["lost"]:
            cause = npc_mod.death_cause(e["result"]).replace("_", " ")
            print(f"    ☠  {e['name']:<28} {e['t'].miles:>5} mi from "
                  f"{e['t'].origin} — {cause}")

    ops = state["operations"]
    banner("PHASE 2: OPERATIONS", "The document ladder. Ability checks, "
                                  "not saving throws.")
    if ops["blocked"]:
        print(f"\n  {ops['blocked']}")
    else:
        print(f"\n  Operatives present: {', '.join(ops['operatives'])}\n")
        for item in ops["log"]:
            doc = item["doc"]
            if item["skipped"]:
                print(f"  ✗  {doc.title}")
                print(f"     skipped — {item['reason']}")
                continue
            ck = item["check"]
            print(f"\n  ▸  {doc.title}")
            print(f"     held at: {doc.holder}")
            print(f"     {doc.skill}")
            for a in item["attempts"]:
                c = a["check"]
                dis = " [disadv]" if c["disadvantage"] else ""
                lead = "     " if a["attempt"] == 1 else "     retry "
                print(f"{lead}{a['operative']}: d20 = {c['natural']} "
                      f"{c['bonus']:+d} = {c['total']} vs DC {c['dc']}{dis}"
                      f" → {DEGREE_LABEL[c['degree']]}")
            if item["gained"]:
                print(f"     +{item['gained']} evidence")
            if ck["degree"] in (CRIT, FULL):
                print(f"     {doc.content}")
            elif ck["degree"] == PARTIAL:
                print(f"     {doc.partial}")
            elif ck["degree"] == BOTCH:
                print(f"     Nothing. The query is logged. +{doc.heat} heat")
        if ops["heat_fired"]:
            print(f"\n  HEAT — someone is paying attention:")
            for threshold, text in ops["heat_fired"]:
                print(f"    [{threshold}] {text}")
        print(f"\n  EVIDENCE: {ops['evidence']}    HEAT: {ops['heat']}")

    rev = state["revelation"]
    banner("PHASE 3: REVELATION", f"Evidence {rev['evidence']} → {rev['tier']}")
    print(f"\n  {rev['text']}\n")
    got = state["operations"]["collected"]
    if "assessment" in got:
        print("  They are holding the line that changes it:")
        print("    THE OBJECTS ARE DECELERATING.\n")
        print("  Ballistic bodies do not shed velocity on approach.")
        print("  Whatever is coming down is under power.\n")
    elif rev["tier"] == "BLIND":
        print("  They think it is rocks. It was never rocks.\n")

    arr = state["arrival"]
    banner("PHASE 4: ARRIVAL", "This part is not rolled.")
    print()
    print(ARRIVAL_TEXT)
    print(f"  They were {'expecting it' if arr['known'] else 'not expecting it'}.")
    print(f"  Save: {arr['hazard'].save_ability} DC {arr['hazard'].dc}, "
          f"{arr['hazard'].damage_dice} psychic"
          f"{' with advantage' if arr['hazard'].advantage else ''}\n")

    hurt = [o for o in arr["outcomes"] if o["hp"] < o["max_hp"]]
    down = [o for o in arr["outcomes"] if o["status"] != "alive"]
    print(f"  {len(arr['outcomes'])} people standing in that valley.")
    if hurt:
        print(f"  {len(hurt)} of them are not the same afterwards:")
        for o in sorted(hurt, key=lambda x: x["hp"] / x["max_hp"])[:6]:
            print(f"    {o['name']:<28} {o['hp']}/{o['max_hp']}")
    if down:
        for o in down:
            print(f"    ☠  {o['name']} did not survive the arrival.")
    if not hurt and not down:
        print("  All of them hold.")

    banner("SESSION COMPLETE", "The sky is open. The questions are PENDING.")
    print()
    print("  Three questions go into the database unanswered:")
    print("    · What do they want?")
    print("    · Who decided, in advance, not to shoot at them?")
    print("    · Was the bombardment an approach, or a message, or neither?")
    print()
    print("  The machine can open the sky.")
    print("  It cannot tell you what it means.")
    print()


# =========================================================================
# DISTRIBUTION
# =========================================================================

def run_distribution(n: int) -> dict:
    from collections import Counter
    tiers = Counter()
    arrived = Counter()
    lost_road = Counter()
    ev = []
    heat = []
    per_person_arrived = Counter()

    for seed in range(n):
        s = run_session(seed)
        tiers[s["revelation"]["tier"]] += 1
        arrived[len(s["convergence"]["arrived"])] += 1
        lost_road[len(s["convergence"]["lost"])] += 1
        ev.append(s["operations"]["evidence"])
        heat.append(s["operations"]["heat"])
        for e in s["convergence"]["arrived"]:
            per_person_arrived[e["name"]] += 1

    return {"n": n, "tiers": tiers, "arrived": arrived,
            "lost_road": lost_road,
            "evidence_mean": sum(ev) / n, "heat_mean": sum(heat) / n,
            "evidence_max": max(ev), "evidence_min": min(ev),
            "per_person": per_person_arrived}


def main(argv=None):
    argv = argv or sys.argv[1:]
    seed = 42
    verbose = "--verbose" in argv
    apply = "--apply" in argv
    distribution = None
    for i, a in enumerate(argv):
        if a == "--seed" and i + 1 < len(argv):
            seed = int(argv[i + 1])
        if a == "--distribution" and i + 1 < len(argv):
            distribution = int(argv[i + 1])

    if distribution:
        print(f"Running {distribution}-iteration compound distribution...\n")
        d = run_distribution(distribution)
        print(BAR)
        print(f"  COMPOUND OUTCOMES — N={d['n']}")
        print(BAR)
        print("\n  Understanding at arrival:")
        for tier, _, _ in UNDERSTANDING:
            pass
        order = ["CERTAIN", "CONVINCED", "SUSPICIOUS", "UNEASY", "BLIND"]
        for tier in order:
            c = d["tiers"].get(tier, 0)
            pct = c / d["n"] * 100
            bar = "█" * int(pct / 2.5) + "░" * (40 - int(pct / 2.5))
            print(f"    {tier:<11} {bar} {pct:5.1f}% ({c})")
        print(f"\n  Evidence: mean {d['evidence_mean']:.2f}, "
              f"range {d['evidence_min']}–{d['evidence_max']}")
        print(f"  Heat:     mean {d['heat_mean']:.2f}")
        print("\n  Arrived at the farm:")
        for k in sorted(d["arrived"]):
            c = d["arrived"][k]
            print(f"    {k:>2} people: {c} ({c / d['n'] * 100:.1f}%)")
        print("\n  Lost on the road:")
        for k in sorted(d["lost_road"]):
            c = d["lost_road"][k]
            print(f"    {k:>2} lost: {c} ({c / d['n'] * 100:.1f}%)")
        print("\n  Per person, chance of reaching the farm:")
        for name, c in d["per_person"].most_common():
            print(f"    {name:<28} {c / d['n'] * 100:5.1f}%")
        return 0

    print(BAR)
    print("  THE COMPOUND — a parallel session in the same world")
    print(f"  Seed: {seed}   (same seed, same survivors)")
    print("  System: D&D 5e SRD 5.1 (CC-BY-4.0, Wizards of the Coast)")
    print(BAR)

    state = run_session(seed, verbose=verbose)
    print_session(state, verbose=verbose)

    if apply:
        counts = write_compound_db(state)
        print(BAR)
        print("  COMPOUND DATABASE")
        print(BAR)
        print(f"  {COMPOUND_DB}")
        print(f"  entities={counts['entities']}  facts={counts['facts']}  "
              f"PENDING questions={counts['gaps']}")
        sys.path.insert(0, str(SCRATCHPAD))
        try:
            from verify_ledger import verify_chain, verify_canon
            c1, d1 = verify_chain(str(COMPOUND_DB))
            c2, d2 = verify_canon(str(COMPOUND_DB))
            print(f"  chain: {'PASS' if c1 == 0 else 'FAIL'} ({d1})")
            print(f"  canon: {'PASS' if c2 == 0 else 'FAIL'} ({d2})")
        except ImportError:
            print("  (verify_ledger unavailable)")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
