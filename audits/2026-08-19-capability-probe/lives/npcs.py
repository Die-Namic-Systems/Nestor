#!/usr/bin/env python3
"""npcs.py — The people around them also have to survive.

Twenty-one living NPCs across four lives.  A protagonist is not a lone
saving throw; they are a person embedded in other people, and those
people are standing under the same sky.

This module runs BEFORE protagonist resolution, because the protagonists
depend on them.  Big T is the voice on the phone that keeps Marcus out of
the liquor store.  Monique is the +4 Medicine check that decides whether
Damon wakes up.  If they die first, the protagonist rolls without them.

Stat blocks are the SRD 5.1 NPC entries (Commoner, Acolyte, Guard, Scout,
Priest, Noble, Thug, Veteran), assigned by what the person actually does.
Where the life data already fixed a number — ALLY_CONTEXT gives Monique
Medicine +4 and Big T +0 — the block is chosen to match it, not to
override it.  Monique is an Acolyte (WIS 14, Medicine +4).  Big T is a
Guard (WIS 11, no proficiency, +0).  The existing data was the constraint.

Exposure follows the bombardment facts, not convenience:
  LOW       sheltered, indoors, away from the impact corridors
  MODERATE  travelling, or inside a building that is now suspect
  HIGH      mass-casualty work, crowds, or institutional confinement

A dead NPC gets `invalid_at` set on their entities row — the schema's own
way of saying this person is no longer current — plus a DRAFT canon fact
recording the death, and a PENDING gap naming what their absence opens up.
DRAFT and PENDING, never SEALED: the machine can take someone's friend
away, but only the person decides what that means.

Rules content derived from the System Reference Document 5.1,
copyright Wizards of the Coast, LLC., licensed under the
Creative Commons Attribution 4.0 International License.
https://dnd.wizards.com/resources/systems-reference-document

Usage:
    python3 npcs.py                    # resolve all NPCs, seed=42
    python3 npcs.py --seed 7           # different seed
    python3 npcs.py --verbose          # full roll-by-roll log
    python3 npcs.py --distribution 500 # NPC survival distribution
    python3 npcs.py --apply            # write outcomes to the databases
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import random

from provision import SCRATCHPAD, row_hash
from resolution import (
    Character,
    Hazard,
    LedgerWriter,
    resolve_one,
)


# =========================================================================
# SRD 5.1 NPC STAT BLOCKS
# =========================================================================
# Ability scores and hit points are the SRD entries verbatim.  A named
# variant (a corpsman's Wisdom, a vet's Medicine) is noted where it differs.

SRD_BLOCKS = {
    "commoner": {
        "scores": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "hp": 4, "cr": 0, "prof": 2,
    },
    "acolyte": {
        "scores": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 14, "CHA": 11},
        "hp": 9, "cr": 0.25, "prof": 2,
    },
    "guard": {
        "scores": {"STR": 13, "DEX": 12, "CON": 12, "INT": 10, "WIS": 11, "CHA": 10},
        "hp": 11, "cr": 0.125, "prof": 2,
    },
    "noble": {
        "scores": {"STR": 11, "DEX": 12, "CON": 11, "INT": 12, "WIS": 14, "CHA": 16},
        "hp": 9, "cr": 0.125, "prof": 2,
    },
    "scout": {
        "scores": {"STR": 11, "DEX": 14, "CON": 12, "INT": 11, "WIS": 13, "CHA": 11},
        "hp": 16, "cr": 0.5, "prof": 2,
    },
    "priest": {
        "scores": {"STR": 10, "DEX": 10, "CON": 12, "INT": 13, "WIS": 16, "CHA": 13},
        "hp": 27, "cr": 2, "prof": 2,
    },
    "thug": {
        "scores": {"STR": 15, "DEX": 11, "CON": 14, "INT": 10, "WIS": 10, "CHA": 11},
        "hp": 32, "cr": 0.5, "prof": 2,
    },
    "veteran": {
        "scores": {"STR": 16, "DEX": 13, "CON": 14, "INT": 10, "WIS": 11, "CHA": 10},
        "hp": 58, "cr": 3, "prof": 3,
    },
}


@dataclass
class NPC:
    """An NPC and everything the resolution needs to know about them."""
    key: str                 # stable id, e.g. "big_t"
    name: str                # canonical name, matches the entities row
    lives: list              # which databases they appear in
    block: str               # SRD block name
    descriptor: str          # what they actually do, for display
    exposure: str            # low / moderate / high
    hazards: list            # list[Hazard]
    ally_name: str | None    # who is there if they go down
    ally_medicine: int | None  # that person's Medicine modifier, None if alone
    ally_note: str
    medicine_mod: int | None = None   # what THEY can do for someone else
    score_overrides: dict = field(default_factory=dict)
    hp_override: int | None = None
    proficient_saves: list = field(default_factory=list)
    death_fact: str = ""     # canon fact written if they die
    death_gap: str = ""      # PENDING question their absence opens

    @property
    def rounds(self) -> int:
        """How many separate dangerous incidents they are in.

        The bombardment is three weeks and counting.  Exposure is not how
        hard any one event hits — a collapsing wall does not care about
        your Constitution — it is how many times you are standing under
        one.  Severity lives in the hazard; frequency lives here.
        """
        return {"high": 3, "moderate": 2, "low": 1}[self.exposure]

    def to_character(self) -> Character:
        base = SRD_BLOCKS[self.block]
        scores = dict(base["scores"])
        scores.update(self.score_overrides)
        cr = base["cr"]
        level = int(cr) if cr >= 1 else 0
        return Character(
            name=self.name,
            db_key=self.key,
            level=level,
            char_class=self.block.title(),
            subclass=self.descriptor,
            hit_die=8,
            ability_scores=scores,
            proficient_saves=list(self.proficient_saves),
            proficiency_bonus=base["prof"],
            max_hp=self.hp_override or base["hp"],
            features=[],
        )

    def ally_context(self) -> dict:
        return {
            "allies_present": self.ally_medicine is not None,
            "ally_name": self.ally_name,
            "medicine_mod": self.ally_medicine,
            "note": self.ally_note,
        }


# =========================================================================
# THE NPCs
# =========================================================================

# -- Marcus's people (Detroit) --------------------------------------------

NPCS: list[NPC] = [
    NPC(
        key="aiden", name="Aiden Oyelaran", lives=["marcus"],
        block="commoner", descriptor="14, Marcus's son, weekdays",
        exposure="low",
        hazards=[
            Hazard(
                name="Sheltering in the apartment",
                description="School is closed. The sky cracks every few hours. "
                            "He is fourteen and the adult in the room has "
                            "shaking hands.",
                save_ability="DEX", dc=10,
                damage_dice="1d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="He asked why Dad's hands were shaking. He got a "
                          "true answer and it frightened him more than the sky.",
            ),
        ],
        ally_name="Marcus", ally_medicine=0,
        ally_note="His father is in the next room and is not a medic.",
        medicine_mod=-1,
        death_fact="Aiden did not survive the bombardment.",
        death_gap="What is left of the custody question now?",
    ),
    NPC(
        key="zara", name="Zara Oyelaran", lives=["marcus"],
        block="commoner", descriptor="10, Marcus's daughter, with Keisha",
        exposure="low",
        hazards=[
            Hazard(
                name="Keisha's house, recital cancelled",
                description="The recital was cancelled. She is ten, at her "
                            "mother's house, and the adults keep checking "
                            "their phones.",
                save_ability="DEX", dc=10,
                damage_dice="1d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="The empty chair problem solved itself. "
                          "Marcus felt relief and hated himself for it.",
            ),
        ],
        ally_name="Keisha", ally_medicine=5,
        ally_note="Her mother is an ER nurse and is standing right there.",
        death_fact="Zara did not survive the bombardment.",
        death_gap="Is there anything left to co-parent?",
    ),
    NPC(
        key="keisha", name="Keisha Oyelaran", lives=["marcus"],
        block="priest", descriptor="ER nurse, Henry Ford Hospital",
        exposure="high",
        proficient_saves=["WIS"],
        hazards=[
            Hazard(
                name="Ambulance bay, mass casualty",
                description="Henry Ford is taking every impact injury on the "
                            "east side. The bay canopy is glass and the sky "
                            "is still dropping things.",
                save_ability="DEX", dc=14,
                damage_dice="4d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="She triaged in the bay because the bay is where "
                          "they arrive.",
            ),
            Hazard(
                name="Thirty-six hours on shift",
                description="Half the night staff can't get in. She has been "
                            "upright since the school closed and she filed "
                            "custody paperwork on a break.",
                save_ability="CON", dc=13,
                damage_dice="", damage_type="",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=2,
                narrative="She filed the emergency modification from the "
                          "hospital cafeteria at 4 AM.",
            ),
            Hazard(
                name="The ones she couldn't get to",
                description="Mass casualty triage means choosing. She is good "
                            "at it, which is its own kind of injury.",
                save_ability="WIS", dc=13,
                damage_dice="2d6", damage_type="psychic",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=1,
                narrative="She knows what no-structure does to Marcus. "
                          "She was protecting the kids, not punishing him.",
            ),
        ],
        ally_name="the trauma team", ally_medicine=5,
        ally_note="She goes down inside a hospital. That is the best place "
                  "in Detroit to go down.",
        medicine_mod=5,
        death_fact="Keisha did not survive the bombardment. She was working "
                   "the ambulance bay at Henry Ford.",
        death_gap="Who has the children now?",
    ),
    NPC(
        key="big_t", name="Terrence 'Big T' Williams", lives=["marcus"],
        block="guard", descriptor="AA sponsor, four years Marcus's lifeline",
        exposure="moderate",
        hazards=[
            Hazard(
                name="Woodward Avenue at 11 PM",
                description="He drives to whoever calls. Tonight that is a "
                            "liquor store parking lot, and the roads are full "
                            "of people who should not be driving.",
                save_ability="DEX", dc=13,
                damage_dice="3d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="T said 'stay on the line.' They sat in silence "
                          "for thirty minutes.",
            ),
            Hazard(
                name="The church basement, every night now",
                description="The meeting moved to daily. Half the room is "
                            "people he knows and half are new. The sky made "
                            "new addicts out of people who were fine last month.",
                save_ability="CON", dc=12,
                damage_dice="", damage_type="",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=1,
                narrative="He holds the room. Nobody asks who holds him.",
            ),
        ],
        ally_name="the rooms", ally_medicine=0,
        ally_note="Thirty people who would drive anywhere for him, "
                  "none of them trained.",
        medicine_mod=0,
        death_fact="Big T did not survive the bombardment.",
        death_gap="Who does Marcus call at 3 AM now?",
    ),
    NPC(
        key="kessler", name="Principal Diane Kessler", lives=["marcus"],
        block="noble", descriptor="principal, Cass Tech",
        exposure="low",
        hazards=[
            Hazard(
                name="Closing the building",
                description="She made the call to close for the week. "
                            "Liability, she said. She walked the building "
                            "herself first.",
                save_ability="DEX", dc=11,
                damage_dice="2d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="Her call cost Marcus his structure. "
                          "It was still the right call.",
            ),
        ],
        ally_name="school staff", ally_medicine=2,
        ally_note="A building full of adults with first-aid cards.",
        death_fact="Dr. Kessler did not survive the bombardment.",
        death_gap="Does Cass Tech reopen at all?",
    ),
    NPC(
        key="jerome", name="Jerome Oyelaran", lives=["marcus"],
        block="commoner", descriptor="Marcus's younger brother, Atlanta",
        exposure="low",
        hazards=[
            Hazard(
                name="Atlanta, eight hundred miles away",
                description="Far from the impact corridor. Close enough to "
                            "watch it on a phone and not call.",
                save_ability="DEX", dc=10,
                damage_dice="1d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="He still has not said what he actually thinks.",
            ),
        ],
        ally_name="neighbours", ally_medicine=1,
        ally_note="A city with working hospitals.",
        death_fact="Jerome did not survive the bombardment.",
        death_gap="Will Marcus ever know what Jerome thought?",
    ),

    # -- June's people (Grants Pass, Oregon) ------------------------------

    NPC(
        key="ryan", name="Ryan Akiyama", lives=["june"],
        block="commoner", descriptor="32, software developer, Portland",
        exposure="moderate",
        hazards=[
            Hazard(
                name="Portland under the bombardment",
                description="A city of glass towers under a sky that drops "
                            "things. He has not called his mother.",
                save_ability="DEX", dc=12,
                damage_dice="2d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="The silence held through a meteoroid impact on "
                          "her property. He did not text.",
            ),
            Hazard(
                name="The twelfth letter he has not read",
                description="Eleven letters in a drawer. A twelfth on her "
                            "kitchen table with no stamp. He knows the farm "
                            "is in the impact zone.",
                save_ability="WIS", dc=12,
                damage_dice="2d6", damage_type="psychic",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="Knowing and calling are different acts.",
            ),
        ],
        ally_name="Portland EMS", ally_medicine=3,
        ally_note="A functioning city, for now.",
        death_fact="Ryan did not survive the bombardment.",
        death_gap="Does the twelfth letter ever get mailed now?",
    ),
    NPC(
        key="hsu", name="Dr. Marguerite Hsu", lives=["june"],
        block="scout", descriptor="large-animal vet, June's nearest neighbour",
        exposure="high",
        score_overrides={"WIS": 14},
        proficient_saves=["CON"],
        hazards=[
            Hazard(
                name="The backhoe at first light",
                description="She drove a backhoe to June's south pasture to "
                            "bury two goats, then to the next farm, then the "
                            "next. Heavy equipment on cratered ground.",
                save_ability="DEX", dc=13,
                damage_dice="3d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="He didn't ask if it was medical. He asked where "
                          "the grave should go.",
            ),
            Hazard(
                name="Every animal in the county",
                description="She is the only large-animal vet for forty miles "
                            "and the livestock are panicking under the sky.",
                save_ability="CON", dc=14,
                damage_dice="", damage_type="",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=2,
                narrative="Overwhelmed is the word June used, and June "
                          "does not use it lightly.",
            ),
            Hazard(
                name="A frightened half-ton animal",
                description="A bull that has heard the sky crack for three "
                            "weeks does not care about her credentials.",
                save_ability="DEX", dc=14,
                damage_dice="4d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="Rural medicine is a contact sport.",
            ),
        ],
        ally_name="farm hands", ally_medicine=1,
        ally_note="Whoever's barn she is standing in.",
        medicine_mod=4,
        death_fact="Dr. Hsu did not survive the bombardment.",
        death_gap="Who buries the next thing that dies on the farm?",
    ),
    NPC(
        key="linda", name="Pastor Linda Greaves", lives=["june"],
        block="priest", descriptor="pastor, Grants Pass Community Church",
        exposure="moderate",
        proficient_saves=["WIS"],
        hazards=[
            Hazard(
                name="Twenty miles on half a tank",
                description="She drove out with water and batteries because "
                            "June is on her list and the list does not care "
                            "about fuel rationing.",
                save_ability="DEX", dc=12,
                damage_dice="3d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="Twenty miles on a half-empty tank, to a woman "
                          "who would never have asked.",
            ),
            Hazard(
                name="A church that is full again",
                description="Churches full, bars full — the usual distribution "
                            "of coping. She is carrying all of it.",
                save_ability="WIS", dc=13,
                damage_dice="2d6", damage_type="psychic",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=1,
                narrative="She has no pastor.",
            ),
        ],
        ally_name="the congregation", ally_medicine=2,
        ally_note="A full church notices when someone goes down.",
        medicine_mod=7,
        death_fact="Pastor Linda did not survive the bombardment.",
        death_gap="Who drives twenty miles to check on June now?",
    ),
    NPC(
        key="benny", name="Corpsman Benny Delacroix", lives=["june"],
        block="veteran", descriptor="FMF corpsman, recalled to active duty",
        exposure="high",
        score_overrides={"WIS": 13},
        proficient_saves=["STR", "CON"],
        hazards=[
            Hazard(
                name="Navy triage staging, San Diego",
                description="Recalled at fifty-nine. Standing up a casualty "
                            "collection point for a bombardment nobody has a "
                            "doctrine for.",
                save_ability="CON", dc=14,
                damage_dice="", damage_type="",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=2,
                narrative="The Sunday call is suspended. He did not get to "
                          "say for how long.",
            ),
            Hazard(
                name="An impact on the staging area",
                description="The collection point is outdoors by design. "
                            "That design assumed the danger came from "
                            "somewhere specific.",
                save_ability="DEX", dc=15,
                damage_dice="8d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="He went toward it. He has always gone toward it.",
            ),
            Hazard(
                name="Doing it again at fifty-nine",
                description="The last time he did this, Tom Akiyama was next "
                            "to him and did not come back.",
                save_ability="WIS", dc=14,
                damage_dice="3d6", damage_type="psychic",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=1,
                narrative="He calls June every Sunday. It has never once "
                          "been only about June.",
            ),
        ],
        ally_name="a Navy medical unit", ally_medicine=6,
        ally_note="He goes down surrounded by corpsmen. "
                  "It is the one advantage of being recalled.",
        medicine_mod=5,
        death_fact="Benny Delacroix did not survive the bombardment. "
                   "He was recalled to a triage staging area in San Diego.",
        death_gap="Who is left who knew Tom?",
    ),

    # -- Shared: the Kindling Kitchen's world (Oakland) -------------------

    NPC(
        key="hector", name="Hector Maldonado", lives=["damon", "yuki"],
        block="commoner", descriptor="63, landlord, owns the building",
        exposure="moderate",
        hazards=[
            Hazard(
                name="Walking his own groaning building",
                description="Hayward fault micro-tremors from the impacts. "
                            "He came to say it needs a structural inspection, "
                            "and then he walked it himself.",
                save_ability="DEX", dc=13,
                damage_dice="4d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="He gave them below-market rent in year one. "
                          "He has never once said why.",
            ),
        ],
        ally_name="kitchen staff", ally_medicine=1,
        ally_note="A building with two hundred people in and around it.",
        death_fact="Hector Maldonado did not survive the bombardment.",
        death_gap="Who owns the building now, and will they renew?",
    ),
    NPC(
        key="fujimoto", name="Inspector Carla Fujimoto", lives=["damon", "yuki"],
        block="guard", descriptor="Alameda County inspector",
        exposure="moderate",
        hazards=[
            Hazard(
                name="Condemned buildings, all week",
                description="Fair but literal. Every code enforced, no "
                            "warnings. This week the codes are structural and "
                            "the buildings are all suspect.",
                save_ability="DEX", dc=13,
                damage_dice="3d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="She walks into the buildings everyone else walks "
                          "out of. That is the entire job.",
            ),
            Hazard(
                name="More buildings than hours",
                description="Every commercial structure in the county wants "
                            "a sign-off and there is one of her.",
                save_ability="CON", dc=12,
                damage_dice="", damage_type="",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=1,
                narrative="The kitchen's inspection is somewhere in a queue.",
            ),
        ],
        ally_name="county crews", ally_medicine=3,
        ally_note="She works alongside emergency services all week.",
        death_fact="Inspector Fujimoto did not survive the bombardment.",
        death_gap="Does anyone sign off on the kitchen now?",
    ),
    NPC(
        key="rosa", name="Abuela Rosa", lives=["damon", "yuki"],
        block="commoner", descriptor="74, first regular at the Saturday meal",
        exposure="high",
        hazards=[
            Hazard(
                name="First in a line of two hundred",
                description="She has been first in that line since the first "
                            "Saturday. The line is now two hundred people and "
                            "the building is groaning.",
                save_ability="DEX", dc=13,
                damage_dice="2d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="She still brings her own salsa.",
            ),
            Hazard(
                name="The fight over the last tray of rice",
                description="Two men fighting, two hundred people packed in, "
                            "and a seventy-four-year-old woman near the front "
                            "of it.",
                save_ability="DEX", dc=14,
                damage_dice="2d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="Damon stepped between them. He was not the only "
                          "person in the room.",
            ),
            Hazard(
                name="Seventy-four, in August, in a queue",
                description="Hours standing. Supply chains fracturing. "
                            "She will not take a chair when others are standing.",
                save_ability="CON", dc=12,
                damage_dice="", damage_type="",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=2,
                narrative="She was the first regular. She acts like it is "
                          "a post.",
            ),
        ],
        ally_name="Damon and Monique", ally_medicine=4,
        ally_note="She goes down in a room with a chef who has done first "
                  "aid and a crisis counsellor.",
        death_fact="Abuela Rosa did not survive the bombardment.",
        death_gap="What is the Saturday meal without its first regular?",
    ),

    # -- Damon's people ---------------------------------------------------

    NPC(
        key="monique", name="Monique Thibodeaux", lives=["damon"],
        block="acolyte", descriptor="crisis counsellor, Alameda County",
        exposure="high",
        proficient_saves=["WIS"],
        hazards=[
            Hazard(
                name="County crisis response, in the field",
                description="Every social worker in Alameda County is doing "
                            "field triage on people, not buildings. She goes "
                            "where the calls are.",
                save_ability="DEX", dc=13,
                damage_dice="3d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="She came home to an empty apartment three nights "
                          "running. So did he.",
            ),
            Hazard(
                name="Carrying other people's crises",
                description="She counsels crisis mode for a living and she "
                            "just recognised it in the man she is going to "
                            "marry.",
                save_ability="WIS", dc=14,
                damage_dice="3d6", damage_type="psychic",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=1,
                narrative="She sees him. Right now she sees the version she "
                          "counsels at work.",
            ),
            Hazard(
                name="Three nights of no sleep",
                description="Field work by day, an empty apartment by night, "
                            "and a wedding to plan in a kitchen that might "
                            "not exist in six weeks.",
                save_ability="CON", dc=13,
                damage_dice="", damage_type="",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=2,
                narrative="She said yes to the ring and the venue in the "
                          "same sentence.",
            ),
        ],
        ally_name="county crisis team", ally_medicine=4,
        ally_note="She works in a team of people trained to notice.",
        medicine_mod=4,
        death_fact="Monique did not survive the bombardment. She was doing "
                   "field crisis response for Alameda County.",
        death_gap="Is there still a wedding in the kitchen?",
    ),
    NPC(
        key="carmen", name="Carmen Reyes", lives=["damon"],
        block="commoner", descriptor="54, Damon's mother, East Oakland",
        exposure="moderate",
        hazards=[
            Hazard(
                name="East Oakland, bad roads",
                description="She stopped coming by because the roads are bad. "
                            "The roads are bad because things are falling on "
                            "them.",
                save_ability="DEX", dc=12,
                damage_dice="2d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="She pretends the five years were a long trip. "
                          "She has never pretended about anything else.",
            ),
        ],
        ally_name="neighbours", ally_medicine=1,
        ally_note="A block where everyone has known her for thirty years.",
        death_fact="Carmen Reyes did not survive the bombardment.",
        death_gap="Does the five years ever get spoken about now?",
    ),
    NPC(
        key="antoine", name="Chef Antoine Broussard", lives=["damon"],
        block="commoner", descriptor="Damon's culinary instructor, Laney College",
        exposure="low",
        hazards=[
            Hazard(
                name="Laney College, closed for the week",
                description="The campus shut like every other campus. "
                            "He is at home, writing recommendation letters "
                            "for people the system will not read them for.",
                save_ability="DEX", dc=10,
                damage_dice="1d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="He wrote the first letter that ever described "
                          "Damon as a chef.",
            ),
        ],
        ally_name="his household", ally_medicine=1,
        ally_note="Indoors, with people.",
        death_fact="Chef Antoine did not survive the bombardment.",
        death_gap="Who vouches for Damon in writing now?",
    ),
    NPC(
        key="silky", name="Marcus 'Silky' Webb", lives=["damon"],
        block="thug", descriptor="Damon's old cellmate, back inside",
        exposure="high",
        proficient_saves=["STR"],
        hazards=[
            Hazard(
                name="Lockdown during the bombardment",
                description="A facility under a sky that drops things does "
                            "not evacuate. It locks down. He is in a concrete "
                            "box that was not built for this.",
                save_ability="DEX", dc=14,
                damage_dice="5d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="Damon still sends money to Silky's daughter.",
            ),
            Hazard(
                name="Medical response, eventually",
                description="Sick call is suspended. Everything is suspended. "
                            "The supply chain that fractured outside fractured "
                            "harder inside.",
                save_ability="CON", dc=14,
                damage_dice="2d6", damage_type="bludgeoning",
                half_on_save=False, advantage=False, disadvantage=False,
                exhaustion_on_fail=2,
                narrative="Second offence. He will be in there for this "
                          "whole thing.",
            ),
        ],
        ally_name=None, ally_medicine=None,
        ally_note="Nobody is coming. That is the design of the building.",
        death_fact="Silky did not survive the bombardment. He was inside.",
        death_gap="Who tells Silky's daughter?",
    ),

    # -- Yuki's people ----------------------------------------------------

    NPC(
        key="kenji", name="Kenji Tanaka", lives=["yuki"],
        block="commoner", descriptor="61, retired engineer, Palo Alto",
        exposure="low",
        hazards=[
            Hazard(
                name="Palo Alto, indoors",
                description="A neighbourhood with generators and a garage "
                            "full of water. He called and said 'come home.'",
                save_ability="DEX", dc=10,
                damage_dice="1d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="He did not offer money. He offered retreat.",
            ),
        ],
        ally_name="Harumi", ally_medicine=1,
        ally_note="His wife is in the house.",
        death_fact="Kenji did not survive the bombardment.",
        death_gap="Does 'come home' mean anything now?",
    ),
    NPC(
        key="harumi", name="Harumi Tanaka", lives=["yuki"],
        block="commoner", descriptor="58, piano teacher, Palo Alto",
        exposure="low",
        hazards=[
            Hazard(
                name="The bento ingredients that stopped",
                description="The delivery service is not running. She has "
                            "sent food without comment for two years and this "
                            "week she cannot.",
                save_ability="DEX", dc=10,
                damage_dice="1d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="She never once said she approved. She just sent "
                          "the ingredients.",
            ),
        ],
        ally_name="Kenji", ally_medicine=1,
        ally_note="Her husband is in the house.",
        death_fact="Harumi did not survive the bombardment.",
        death_gap="Who sends the ingredients now?",
    ),
    NPC(
        key="alex", name="Alex Chen", lives=["yuki"],
        block="commoner", descriptor="software engineer, Yuki's ex",
        exposure="low",
        hazards=[
            Hazard(
                name="A campus with a disaster plan",
                description="Big tech has generators, water, and a bunker "
                            "mentality that finally has a use.",
                save_ability="DEX", dc=10,
                damage_dice="1d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="He said the kitchen didn't scale. He was right, "
                          "and it did not matter.",
            ),
        ],
        ally_name="campus medical", ally_medicine=3,
        ally_note="On-site medical, because of course there is.",
        death_fact="Alex Chen did not survive the bombardment.",
        death_gap="Nothing. And that is its own answer.",
    ),
    NPC(
        key="priya", name="Priya Krishnamurthy", lives=["yuki"],
        block="noble", descriptor="Yuki's old PM lead, hiring again",
        exposure="low",
        hazards=[
            Hazard(
                name="Crisis ops, from a desk",
                description="She is staffing a crisis operations team for "
                            "$185K a head. The crisis is happening to other "
                            "people.",
                save_ability="DEX", dc=10,
                damage_dice="1d6", damage_type="bludgeoning",
                half_on_save=True, advantage=False, disadvantage=False,
                exhaustion_on_fail=0,
                narrative="A door held open is courtesy. $185K during a "
                          "crisis is gravity.",
            ),
        ],
        ally_name="corporate medical", ally_medicine=3,
        ally_note="Insured, indoors, and several hundred miles from an impact.",
        death_fact="Priya did not survive the bombardment.",
        death_gap="Is the offer still open if the person who made it is gone?",
    ),
]


NPCS_BY_KEY = {n.key: n for n in NPCS}

# Tom Akiyama is not in this list. He died in Helmand Province in 2011.
# The bombardment cannot touch him and June wears his tags through all of it.


# =========================================================================
# RESOLUTION
# =========================================================================

def long_rest(char: Character):
    """SRD 5.1 long rest: hit points restored, one level of exhaustion removed.

    Three weeks is long enough to recover between incidents.  Without this,
    a second incident is just attrition bookkeeping; with it, each incident
    is its own independent chance to die, which is what being repeatedly
    exposed actually means.
    """
    char.current_hp = char.max_hp
    if char.exhaustion > 0:
        char.exhaustion -= 1
    char.log.append({
        "event": "long_rest",
        "hp": char.current_hp,
        "exhaustion": char.exhaustion,
    })


def resolve_npc(npc: NPC, rng: random.Random) -> dict:
    """Resolve one NPC across every incident their exposure puts them in."""
    char = npc.to_character()
    ally_ctx = npc.ally_context()
    result = None

    for round_num in range(npc.rounds):
        if not char.alive:
            break
        if round_num > 0:
            long_rest(char)
            char.log.append({
                "event": "incident_begin",
                "incident": round_num + 1,
                "of": npc.rounds,
            })
        result = resolve_one(char, npc.hazards, ally_ctx, rng)

    result["npc"] = npc
    result["lives"] = npc.lives
    result["incidents"] = npc.rounds
    return result


def resolve_npcs(seed: int = 42) -> dict:
    """Resolve every NPC. Returns {key: outcome dict}."""
    rng = random.Random(seed ^ 0x9E3779B9)  # decorrelate from PC rolls
    outcomes = {}
    for npc in NPCS:
        outcomes[npc.key] = resolve_npc(npc, rng)
    return outcomes


def death_cause(result: dict) -> str:
    for entry in reversed(result["log"]):
        if entry.get("event") == "death":
            return entry.get("cause", "unknown")
    return "unknown"


def build_ally_context(npc_outcomes: dict) -> dict:
    """Derive the protagonists' ally context from who is still alive.

    This is the whole point of resolving NPCs first.  ALLY_CONTEXT in
    resolution.py is the everyone-lives case; this is what actually
    happened.
    """
    def alive(key: str) -> bool:
        return npc_outcomes[key]["status"] == "alive"

    ctx = {}

    # Marcus: Big T on the phone, Aiden in the house.
    if alive("big_t"):
        ctx["marcus"] = {
            "allies_present": True, "ally_name": "Big T", "medicine_mod": 0,
            "note": "Big T is on the phone. Aiden is in the house. "
                    "Neither is trained.",
        }
    elif alive("aiden"):
        ctx["marcus"] = {
            "allies_present": True, "ally_name": "Aiden", "medicine_mod": -1,
            "note": "Big T is dead. The person who finds Marcus is his "
                    "fourteen-year-old son.",
        }
    else:
        ctx["marcus"] = {
            "allies_present": False, "ally_name": None, "medicine_mod": None,
            "note": "Big T is dead and Aiden is dead. Nobody finds him.",
        }

    # June: alone at 0347 regardless. Dr. Hsu comes in the morning, and
    # morning is not soon enough to matter to a death save.
    hsu_note = ("Dr. Hsu comes the next morning."
                if alive("hsu") else
                "Dr. Hsu is dead. Nobody comes in the morning either.")
    ctx["june"] = {
        "allies_present": False, "ally_name": None, "medicine_mod": None,
        "note": f"Alone on the farm at 0347. {hsu_note} Death saves alone.",
    }

    # Damon: Monique, else the kitchen.
    if alive("monique"):
        ctx["damon"] = {
            "allies_present": True, "ally_name": "Monique", "medicine_mod": 4,
            "note": "Monique has crisis training. Kitchen staff, 200 people.",
        }
    else:
        ctx["damon"] = {
            "allies_present": True, "ally_name": "kitchen staff",
            "medicine_mod": 0,
            "note": "Monique is dead. Two hundred people and nobody trained.",
        }

    # Yuki: Damon, but Damon is a PC and may not survive his own hazards.
    # resolve_all patches this after Damon resolves.
    ctx["yuki"] = {
        "allies_present": True, "ally_name": "Damon", "medicine_mod": 1,
        "note": "Damon is present if the kitchen is standing. "
                "Not trained but stubborn.",
    }

    return ctx


# =========================================================================
# DATABASE INTEGRATION
# =========================================================================

def write_npcs_to_db(db_key: str, npc_outcomes: dict) -> dict:
    """Write NPC outcomes into one life's database.

    Dead NPCs get `invalid_at` on their entities row, a DRAFT canon fact,
    and a PENDING gap.  Nothing is SEALED and no ruling is signed — the
    covenant holds through a body count.
    """
    db_path = str(SCRATCHPAD / f"{db_key}-life-sandbox" / "campaign.db")
    if not Path(db_path).exists():
        return {"dead": 0, "alive": 0, "facts": 0, "gaps": 0}

    con = sqlite3.connect(db_path)
    lw = LedgerWriter(con)
    ts = datetime.now(timezone.utc).isoformat()
    session = 98  # NPC resolution runs before PC resolution (99)

    relevant = [
        (key, r) for key, r in npc_outcomes.items()
        if db_key in r["lives"]
    ]
    dead = [(k, r) for k, r in relevant if r["status"] != "alive"]
    alive = [(k, r) for k, r in relevant if r["status"] == "alive"]

    lw.write(session, "session_open",
             f"NPC hazard resolution — {len(relevant)} people in this life",
             {"system": "SRD 5.1", "npcs": len(relevant)})

    facts = 0
    gaps = 0
    for key, r in dead:
        npc = r["npc"]
        cause = death_cause(r)

        con.execute(
            "UPDATE entities SET invalid_at=? WHERE canonical=?",
            (ts, npc.name),
        )
        con.execute(
            "INSERT INTO canon (ts, fact, status, proposed_by, reason) "
            "VALUES (?,?,?,?,?)",
            (ts, npc.death_fact, "DRAFT", "npc-resolution",
             f"bombardment death — {cause}"),
        )
        facts += 1
        con.execute(
            "INSERT INTO canon (ts, fact, status, proposed_by, reason) "
            "VALUES (?,?,?,?,?)",
            (ts, f"UNRESOLVED: {npc.death_gap}", "PENDING",
             "npc-resolution", "jeles-gap"),
        )
        gaps += 1

    lw.write(session, "turn",
             f"{len(dead)} dead, {len(alive)} alive. "
             f"Wrote {facts} DRAFT facts and {gaps} PENDING gaps. "
             f"Nothing sealed — the deaths are facts, not decisions.",
             {"dead": [r["npc"].name for _, r in dead],
              "alive": [r["npc"].name for _, r in alive]})

    lw.write(session, "session_close",
             f"NPC resolution complete for {db_key}.",
             {"dead_count": len(dead), "alive_count": len(alive)})

    con.commit()
    con.close()
    return {"dead": len(dead), "alive": len(alive),
            "facts": facts, "gaps": gaps}


def apply_npcs(npc_outcomes: dict) -> dict:
    stats = {}
    for db_key in ["marcus", "june", "damon", "yuki"]:
        db_path = SCRATCHPAD / f"{db_key}-life-sandbox" / "campaign.db"
        if db_path.exists():
            shutil.copy2(str(db_path), str(db_path) + ".pre-npcs")
        stats[db_key] = write_npcs_to_db(db_key, npc_outcomes)
    return stats


# =========================================================================
# DISTRIBUTION
# =========================================================================

def run_distribution(n: int = 500) -> dict:
    from collections import Counter

    survived = Counter()
    causes = {}
    dead_per_run = Counter()

    for seed in range(n):
        outcomes = resolve_npcs(seed)
        dead_count = 0
        for key, r in outcomes.items():
            if r["status"] == "alive":
                survived[key] += 1
            else:
                dead_count += 1
                causes.setdefault(key, Counter())[death_cause(r)] += 1
        dead_per_run[dead_count] += 1

    return {
        "n": n,
        "rates": {
            npc.key: {
                "name": npc.name,
                "exposure": npc.exposure,
                "block": npc.block,
                "survived": survived[npc.key],
                "rate": survived[npc.key] / n,
                "causes": dict(causes.get(npc.key, {})),
            }
            for npc in NPCS
        },
        "dead_per_run": {str(k): v for k, v in sorted(dead_per_run.items())},
        "expected_dead": sum(k * v for k, v in dead_per_run.items()) / n,
    }


# =========================================================================
# OUTPUT
# =========================================================================

EXPOSURE_ORDER = {"high": 0, "moderate": 1, "low": 2}


def print_npc_summary(npc_outcomes: dict):
    by_life = {"marcus": [], "june": [], "damon": [], "yuki": []}
    shared = []
    for key, r in npc_outcomes.items():
        npc = r["npc"]
        if len(npc.lives) > 1:
            shared.append((key, r))
        else:
            by_life[npc.lives[0]].append((key, r))

    def render(entries):
        entries.sort(key=lambda kr: (
            EXPOSURE_ORDER[kr[1]["npc"].exposure], kr[1]["npc"].name))
        for key, r in entries:
            npc = r["npc"]
            if r["status"] == "alive":
                mark = "  ·"
                state = f"alive  {r['hp_final']:>2}/{r['max_hp']:<2}"
                if r["exhaustion"]:
                    state += f"  exh {r['exhaustion']}"
            else:
                mark = "  ☠"
                state = f"DEAD   {death_cause(r).replace('_', ' ')}"
            print(f"{mark} {npc.name:<28} {npc.block:<9} "
                  f"{npc.exposure:<9} {state}")

    for life, title in [
        ("marcus", "MARCUS'S PEOPLE — Detroit"),
        ("june", "JUNE'S PEOPLE — Grants Pass"),
        ("damon", "DAMON'S PEOPLE — Oakland"),
        ("yuki", "YUKI'S PEOPLE — Oakland / Palo Alto"),
    ]:
        print(f"\n  {title}")
        render(by_life[life])

    print(f"\n  SHARED — the Kindling Kitchen's world")
    render(shared)


def print_npc_detail(npc_outcomes: dict):
    import resolution
    for key, r in npc_outcomes.items():
        resolution.print_result(r)


def main(argv=None):
    argv = argv or sys.argv[1:]

    seed = 42
    apply = "--apply" in argv
    verbose = "--verbose" in argv
    distribution = None
    for i, arg in enumerate(argv):
        if arg == "--seed" and i + 1 < len(argv):
            seed = int(argv[i + 1])
        if arg == "--distribution" and i + 1 < len(argv):
            distribution = int(argv[i + 1])

    if distribution:
        print(f"Running {distribution}-iteration NPC survival distribution...\n")
        stats = run_distribution(distribution)
        print("=" * 70)
        print(f"  NPC SURVIVAL — N={stats['n']}")
        print("=" * 70)
        rows = sorted(stats["rates"].values(), key=lambda d: d["rate"])
        for d in rows:
            pct = d["rate"] * 100
            bar = "█" * int(pct / 2.5) + "░" * (40 - int(pct / 2.5))
            print(f"  {d['name']:<28} {bar} {pct:5.1f}%")
            print(f"    {d['block']:<9} exposure={d['exposure']:<9} "
                  f"{d['causes'] or ''}")
        print(f"\n  Dead per run:")
        for k in sorted(stats["dead_per_run"], key=int):
            v = stats["dead_per_run"][k]
            print(f"    {k:>2} dead: {v} ({v / stats['n'] * 100:.1f}%)")
        print(f"\n  Expected NPC deaths per run: {stats['expected_dead']:.2f}")
        return 0

    print("=" * 70)
    print(f"  NPC HAZARD RESOLUTION — seed={seed}")
    print(f"  SRD 5.1 NPC stat blocks (CC-BY-4.0, Wizards of the Coast)")
    print("=" * 70)

    npc_outcomes = resolve_npcs(seed)

    if verbose:
        print_npc_detail(npc_outcomes)

    print_npc_summary(npc_outcomes)

    dead = [r for r in npc_outcomes.values() if r["status"] != "alive"]
    alive = [r for r in npc_outcomes.values() if r["status"] == "alive"]

    print(f"\n{'=' * 70}")
    print(f"  {len(alive)} of {len(npc_outcomes)} NPCs survived. {len(dead)} did not.")
    print("=" * 70)

    ctx = build_ally_context(npc_outcomes)
    print("\n  WHO IS THERE WHEN THE PROTAGONIST GOES DOWN:")
    for k in ["marcus", "june", "damon", "yuki"]:
        c = ctx[k]
        mod = c["medicine_mod"]
        who = c["ally_name"] or "nobody"
        modtxt = f"Medicine {mod:+d}" if mod is not None else "no check"
        print(f"    {k:<8} {who:<16} {modtxt}")
        print(f"             {c['note']}")

    if apply:
        print(f"\n{'=' * 70}")
        print("  APPLYING TO DATABASES")
        print("=" * 70)
        stats = apply_npcs(npc_outcomes)
        for db_key, s in stats.items():
            print(f"  {db_key}: {s['dead']} dead, {s['alive']} alive — "
                  f"+{s['facts']} DRAFT facts, +{s['gaps']} PENDING gaps")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
