#!/usr/bin/env python3
"""resolution.py — D&D 5e hazard resolution for the bombardment.

The dice don't care about your character arc.

This module runs BEFORE progression.  It takes the bombardment hazards
already in each character's database and resolves them through the
Systems Reference Document 5.1 rules: ability scores, saving throws,
hit points, damage, death saving throws, exhaustion, and class features.

A character who fails their checks doesn't get a _shows_up function.
Their database gets a final ledger entry.  Their PENDING decisions stay
PENDING forever.  Their unsigned rulings stay unsigned.  That IS the data.

Rules used (all SRD 5.1, CC-BY-4.0):
  - Ability scores and modifiers (PHB Ch.1)
  - Saving throws: d20 + ability mod + proficiency if proficient (PHB Ch.7)
  - Hit points, hit dice, damage (PHB Ch.9)
  - Death saving throws: d20, 10+ success, 9- failure,
    nat 20 = conscious at 1 HP, nat 1 = two failures (PHB Ch.9)
  - Massive damage: instant death if remaining damage >= max HP (PHB Ch.9)
  - Exhaustion levels 1-6 (PHB Appendix A)
  - Advantage / disadvantage: roll 2d20, take higher / lower (PHB Ch.7)
  - Class features: Second Wind, Bardic Inspiration, Portent,
    Preserve Life (Channel Divinity)

Attribution (required by CC-BY-4.0):
  Rules content derived from the System Reference Document 5.1,
  copyright Wizards of the Coast, LLC., licensed under the
  Creative Commons Attribution 4.0 International License.
  https://dnd.wizards.com/resources/systems-reference-document

Usage:
    python3 resolution.py                # resolve all four, seed=42
    python3 resolution.py --seed 0       # specific seed
    python3 resolution.py --distribution 500  # N-run survival distribution
    python3 resolution.py --apply        # resolve + write outcomes to databases
"""
from __future__ import annotations

import json
import random
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provision import SCRATCHPAD, row_hash


# =========================================================================
# D&D 5e CORE RULES
# =========================================================================

def modifier(score: int) -> int:
    """Ability score to modifier. SRD 5.1: (score - 10) // 2."""
    return (score - 10) // 2


def roll_d20(rng: random.Random) -> int:
    return rng.randint(1, 20)


def roll_dice(notation: str, rng: random.Random) -> tuple[list[int], int]:
    """Roll dice in NdM notation. Returns (individual_rolls, total)."""
    n, m = notation.lower().split("d")
    n, m = int(n), int(m)
    rolls = [rng.randint(1, m) for _ in range(n)]
    return rolls, sum(rolls)


def saving_throw(
    score: int, proficient: bool, prof_bonus: int,
    dc: int, rng: random.Random,
    advantage: bool = False, disadvantage: bool = False,
    exhaustion_level: int = 0,
) -> tuple[int, int, bool]:
    """Make a saving throw. Returns (natural_roll, total, success).

    SRD 5.1: d20 + ability modifier + proficiency bonus (if proficient).
    Exhaustion >= 3: disadvantage on saving throws.
    Advantage and disadvantage cancel if both present.
    """
    if exhaustion_level >= 3:
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

    mod = modifier(score)
    bonus = prof_bonus if proficient else 0
    total = natural + mod + bonus
    return natural, total, total >= dc


def death_saving_throw(rng: random.Random) -> tuple[int, str]:
    """One death save. Returns (natural_roll, result).

    SRD 5.1: d20, no modifiers.
    10+ = 'success', 9- = 'failure', nat 20 = 'nat20', nat 1 = 'nat1'.
    """
    roll = roll_d20(rng)
    if roll == 20:
        return roll, "nat20"
    if roll == 1:
        return roll, "nat1"
    if roll >= 10:
        return roll, "success"
    return roll, "failure"


def resolve_death_saves(
    rng: random.Random,
    ally_medicine_mod: int | None = None,
) -> tuple[str, list[dict]]:
    """Run death saves until stable, dead, or rescued.

    If an ally is present, they attempt a DC 10 Medicine (Wisdom) check
    on the first round to stabilize.

    Returns (outcome, log) where outcome is 'stable', 'dead', or 'conscious'.
    """
    log = []
    successes = 0
    failures = 0

    for round_num in range(1, 11):
        if ally_medicine_mod is not None and round_num == 1:
            med_roll = roll_d20(rng)
            med_total = med_roll + ally_medicine_mod
            med_success = med_total >= 10
            log.append({
                "round": round_num, "type": "medicine_check",
                "roll": med_roll, "total": med_total,
                "dc": 10, "success": med_success,
            })
            if med_success:
                return "stable", log
            # ally failed — fall through to death save

        roll, result = death_saving_throw(rng)
        entry = {"round": round_num, "type": "death_save", "roll": roll, "result": result}

        if result == "nat20":
            successes += 1
            entry["successes"] = successes
            entry["failures"] = failures
            log.append(entry)
            return "conscious", log
        elif result == "nat1":
            failures += 2
        elif result == "success":
            successes += 1
        else:
            failures += 1

        entry["successes"] = min(successes, 3)
        entry["failures"] = min(failures, 3)
        log.append(entry)

        if successes >= 3:
            return "stable", log
        if failures >= 3:
            return "dead", log

    return "dead", log


# =========================================================================
# CHARACTER STAT BLOCKS (D&D 5e)
# =========================================================================

@dataclass
class Character:
    name: str
    db_key: str          # marcus, june, damon, yuki
    level: int
    char_class: str
    subclass: str
    hit_die: int         # d6, d8, d10, d12
    ability_scores: dict  # STR, DEX, CON, INT, WIS, CHA
    proficient_saves: list[str]
    proficiency_bonus: int
    max_hp: int
    features: list[str]  # class features available

    # mutable state during resolution
    current_hp: int = 0
    exhaustion: int = 0
    features_used: list = field(default_factory=list)
    log: list = field(default_factory=list)
    alive: bool = True

    def __post_init__(self):
        self.current_hp = self.max_hp

    def mod(self, ability: str) -> int:
        return modifier(self.ability_scores[ability])

    def save_mod(self, ability: str) -> int:
        m = self.mod(ability)
        if ability in self.proficient_saves:
            m += self.proficiency_bonus
        return m

    def is_proficient(self, ability: str) -> bool:
        return ability in self.proficient_saves

    def take_damage(self, amount: int, source: str, rng: random.Random) -> str:
        """Apply damage. Returns outcome: 'standing', 'unconscious', 'dead'.

        SRD 5.1 Massive Damage: if remaining damage after hitting 0
        equals or exceeds max HP, instant death.
        """
        self.current_hp -= amount
        if self.current_hp > 0:
            self.log.append({
                "event": "damage", "source": source,
                "amount": amount, "hp_remaining": self.current_hp,
            })
            return "standing"

        overflow = abs(self.current_hp)
        self.current_hp = 0

        if overflow >= self.max_hp:
            self.alive = False
            self.log.append({
                "event": "massive_damage_death", "source": source,
                "amount": amount, "overflow": overflow,
                "max_hp": self.max_hp,
            })
            return "dead"

        self.log.append({
            "event": "unconscious", "source": source,
            "amount": amount, "overflow": overflow,
        })
        return "unconscious"

    def heal(self, amount: int, source: str):
        """Heal HP, capped at max_hp."""
        before = self.current_hp
        self.current_hp = min(self.current_hp + amount, self.max_hp)
        healed = self.current_hp - before
        self.log.append({
            "event": "heal", "source": source,
            "amount": healed, "hp_now": self.current_hp,
        })

    def gain_exhaustion(self, levels: int, source: str):
        """Gain exhaustion levels. Level 6 = death (SRD 5.1)."""
        self.exhaustion += levels
        self.log.append({
            "event": "exhaustion", "source": source,
            "levels_gained": levels, "total": self.exhaustion,
        })
        if self.exhaustion >= 6:
            self.alive = False
            self.log.append({"event": "exhaustion_death", "total": self.exhaustion})

    def use_feature(self, feature: str) -> bool:
        """Attempt to use a class feature. Returns True if available."""
        if feature in self.features and feature not in self.features_used:
            self.features_used.append(feature)
            return True
        return False


# -- The four characters --

def make_marcus() -> Character:
    """Marcus Oyelaran — Bard 4 (College of Lore).

    38, music teacher, recovering alcoholic.  CHA primary (the musician,
    the teacher who 200 kids a year write about).  WIS secondary (sobriety
    is a daily decision — the wisdom to make it).  CON modest (the body
    that froze in the parking lot).
    """
    return Character(
        name="Marcus Oyelaran", db_key="marcus",
        level=4, char_class="Bard", subclass="College of Lore",
        hit_die=8,
        ability_scores={
            "STR": 10, "DEX": 12, "CON": 12,
            "INT": 13, "WIS": 14, "CHA": 16,
        },
        proficient_saves=["DEX", "CHA"],
        proficiency_bonus=2,
        # HP: 8 + 3×5 + 4×1(CON) = 27
        max_hp=27,
        features=["bardic_inspiration", "cutting_words"],
    )


def make_june() -> Character:
    """June Akiyama — Cleric 5 (Life Domain).

    58, retired Navy nurse, widowed.  WIS primary (the nurse's eye, the
    farmer's patience, the grieving wife who wears the tags).  CON secondary
    (30 years Navy, but she's 58 and the back gave out digging).  Highest
    level of the four — the most life lived.
    """
    return Character(
        name="June Akiyama", db_key="june",
        level=5, char_class="Cleric", subclass="Life Domain",
        hit_die=8,
        ability_scores={
            "STR": 10, "DEX": 10, "CON": 14,
            "INT": 12, "WIS": 16, "CHA": 13,
        },
        proficient_saves=["WIS", "CHA"],
        proficiency_bonus=3,
        # HP: 8 + 4×5 + 5×2(CON) = 38
        max_hp=38,
        features=["preserve_life", "blessed_healer"],
    )


def make_damon() -> Character:
    """Damon Reyes — Fighter 4 (Champion).

    31, formerly incarcerated, chef, co-founder.  CON primary (survived
    San Quentin, works a kitchen line, absorbs punishment and keeps going).
    STR secondary (separated two fighting men with his hands).  WIS is
    where the scars show — the walk-in cooler shaking.
    """
    return Character(
        name="Damon Reyes", db_key="damon",
        level=4, char_class="Fighter", subclass="Champion",
        hit_die=10,
        ability_scores={
            "STR": 14, "DEX": 13, "CON": 15,
            "INT": 10, "WIS": 12, "CHA": 11,
        },
        proficient_saves=["STR", "CON"],
        proficiency_bonus=2,
        # HP: 10 + 3×6 + 4×2(CON) = 36
        max_hp=36,
        features=["second_wind", "action_surge"],
    )


def make_yuki() -> Character:
    """Yuki Tanaka — Wizard 3 (School of Divination).

    29, former tech PM, co-founder.  INT primary (47 tabs of spreadsheet,
    the PM who left the building but not the reflex).  WIS secondary (sees
    the truth she doesn't want).  CON is the problem — 2 AM spreadsheets,
    no sleep, the body of someone who left a desk job for a kitchen she
    doesn't cook in.  Lowest HP of the four.  The dice will notice.
    """
    return Character(
        name="Yuki Tanaka", db_key="yuki",
        level=3, char_class="Wizard", subclass="School of Divination",
        hit_die=6,
        ability_scores={
            "STR": 8, "DEX": 12, "CON": 10,
            "INT": 17, "WIS": 14, "CHA": 13,
        },
        proficient_saves=["INT", "WIS"],
        proficiency_bonus=2,
        # HP: 6 + 2×4 + 3×0(CON) = 14
        max_hp=14,
        features=["portent", "arcane_recovery"],
    )


# =========================================================================
# HAZARD ENCOUNTERS (bombardment → D&D 5e mechanics)
# =========================================================================

@dataclass
class Hazard:
    name: str
    description: str
    save_ability: str
    dc: int
    damage_dice: str      # e.g. "6d6" — empty string for no damage
    damage_type: str      # fire, bludgeoning, psychic, etc.
    half_on_save: bool    # take half damage on success
    advantage: bool       # character has advantage on the save
    disadvantage: bool    # character has disadvantage
    exhaustion_on_fail: int  # exhaustion levels on failure (0 = none)
    narrative: str        # what happens in the story


# -- Phase 1: IMPACT (the meteoroid hits — immediate physical danger) --
# -- Phase 2: AFTERMATH (the hours after — sustained hazards) --
# -- Phase 3: SURVIVAL (the next day — resource depletion, ongoing threats) --

MARCUS_HAZARDS = [
    # Phase 1: The fireball over Cass Tech
    Hazard(
        name="Fireball over Cass Tech",
        description="A meteoroid burns up directly overhead during marching band "
                    "practice. Concussion wave, heat bloom, raining debris.",
        save_ability="DEX", dc=14,
        damage_dice="6d6", damage_type="fire",
        half_on_save=True,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=0,
        narrative="He froze, arms up mid-beat. A sophomore had to pull him inside.",
    ),
    # Phase 2: The parking lot — CON save against the craving
    Hazard(
        name="Liquor store parking lot",
        description="11 PM, Woodward Ave. The craving is for bourbon. "
                    "The body that runs on structure has no structure. "
                    "Forty minutes in the car.",
        save_ability="WIS", dc=15,
        damage_dice="3d6", damage_type="psychic",
        half_on_save=False,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=1,
        narrative="He sat in the parking lot for forty minutes. Called Big T. "
                  "T said 'stay on the line.'",
    ),
    # Phase 3: Keisha's custody filing + Aiden's shaking hands
    Hazard(
        name="Custody filing and Aiden's fear",
        description="Keisha files for emergency custody modification. "
                    "Aiden asks why Dad's hands are shaking. "
                    "The family structure that held him is under him.",
        save_ability="WIS", dc=13,
        damage_dice="2d6", damage_type="psychic",
        half_on_save=False,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=1,
        narrative="Marcus said 'I'm scared too' — the first honest thing "
                  "he'd said in a week.",
    ),
]

JUNE_HAZARDS = [
    # Phase 1: Meteoroid impact — 4 meters wide, south pasture, 0347
    Hazard(
        name="South pasture impact",
        description="A meteoroid hits the south pasture at 0347. "
                    "Concussion blows out the greenhouse. Two goats killed. "
                    "She was awake and dressed — thirty years Navy, you sleep light.",
        save_ability="DEX", dc=15,
        damage_dice="8d6", damage_type="bludgeoning",
        half_on_save=True,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=0,
        narrative="She was awake. There was nothing to do but watch the pasture burn.",
    ),
    # Phase 2: Burying the goats — 58, bad back, alone
    Hazard(
        name="Burying Pepper and Clementine",
        description="The shovel hit rock at two feet. Her back gave out. "
                    "She is 58 years old, alone on a farm, and the ground "
                    "won't take the dead.",
        save_ability="CON", dc=14,
        damage_dice="2d8", damage_type="bludgeoning",
        half_on_save=False,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=2,
        narrative="Dr. Hsu came with a backhoe the next morning.",
    ),
    # Phase 3: Isolation — half tank, 12 miles from town, August heat
    Hazard(
        name="Isolated on the farm",
        description="The gas station in Grants Pass ran dry. "
                    "Half a tank. Twelve miles from town. August heat. "
                    "The neighbors drove south. The isolation she chose "
                    "is now the isolation she has.",
        save_ability="CON", dc=13,
        damage_dice="",  # no direct damage — exhaustion only
        damage_type="",
        half_on_save=False,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=2,
        narrative="The nurse set up a triage station. Nobody came.",
    ),
]

DAMON_HAZARDS = [
    # Phase 1: Kitchen structural stress during the line
    Hazard(
        name="Kitchen during the bombardment",
        description="Hayward fault micro-tremors from the impacts. "
                    "The building groans. 200 people in and around the kitchen. "
                    "Hector says it needs structural inspection.",
        save_ability="DEX", dc=13,
        damage_dice="4d6", damage_type="bludgeoning",
        half_on_save=True,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=0,
        narrative="Ceiling tile fell. Damon pushed a volunteer clear.",
    ),
    # Phase 2: The fight in the line
    Hazard(
        name="Fight in the Saturday line",
        description="Two men fighting over the last tray of rice. "
                    "200 people. Damon steps between them. "
                    "His body goes to the San Quentin place.",
        save_ability="STR", dc=14,
        damage_dice="3d6", damage_type="bludgeoning",
        half_on_save=False,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=0,
        narrative="He separated them with his hands and his voice. "
                  "Then shook for an hour in the walk-in cooler.",
    ),
    # Phase 3: Walk-in cooler PTSD + Monique recognizing crisis mode
    Hazard(
        name="Walk-in cooler breakdown",
        description="The body remembers San Quentin. The cooler is "
                    "the right size and the right temperature and the "
                    "shaking won't stop. Monique came home to an empty "
                    "apartment three nights running.",
        save_ability="WIS", dc=15,
        damage_dice="3d6", damage_type="psychic",
        half_on_save=False,
        advantage=False, disadvantage=True,  # PTSD = disadvantage on WIS
        exhaustion_on_fail=1,
        narrative="The skill and the scar are the same thing.",
    ),
]

YUKI_HAZARDS = [
    # Phase 1: Kitchen hazards (same building as Damon)
    Hazard(
        name="Kitchen during the bombardment",
        description="Same building, same micro-tremors. But Yuki is in "
                    "the office, not on the line. The laptop and the "
                    "spreadsheet and the ceiling.",
        save_ability="DEX", dc=13,
        damage_dice="4d6", damage_type="bludgeoning",
        half_on_save=True,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=0,
        narrative="She grabbed the laptop before she grabbed the door frame.",
    ),
    # Phase 2: Sleep deprivation + Tab 48
    Hazard(
        name="Sleep deprivation — Tab 48 at 2 AM",
        description="Twelve iterations of a model that says the same thing. "
                    "2 AM. 3 AM. The PM left the building but the reflex "
                    "wakes her up to run the numbers one more time. "
                    "The numbers don't change.",
        save_ability="CON", dc=13,
        damage_dice="",  # no damage — exhaustion
        damage_type="",
        half_on_save=False,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=2,
        narrative="She built Tab 48. Every path to break-even says insolvent.",
    ),
    # Phase 3: Emotional collapse — the $185K offer, the first lie,
    # holding Damon while he shakes
    Hazard(
        name="The weight of the lie",
        description="Priya's $185K offer. Not telling Damon. Holding him "
                    "while he shakes and thinking 'I could end this with "
                    "one email.' The class gap cracked open and she's standing "
                    "on the side with the exit.",
        save_ability="WIS", dc=14,
        damage_dice="4d6", damage_type="psychic",
        half_on_save=False,
        advantage=False, disadvantage=False,
        exhaustion_on_fail=1,
        narrative="She hated herself for the thought and hated herself more "
                  "for not hating the thought enough.",
    ),
]


# =========================================================================
# ALLY / STABILIZATION CONTEXT
# =========================================================================

ALLY_CONTEXT = {
    "marcus": {
        "allies_present": True,
        "ally_name": "Big T",
        "medicine_mod": 0,  # Big T is a sponsor, not a medic — WIS 10, no prof
        "note": "Big T is on the phone but not physically present for Phase 1. "
                "Aiden is in the house. Neither is trained.",
    },
    "june": {
        "allies_present": False,
        "ally_name": None,
        "medicine_mod": None,
        "note": "Alone on the farm. Dr. Hsu comes the next morning — "
                "but if she's unconscious at 0347, nobody finds her until then. "
                "Death saves alone.",
    },
    "damon": {
        "allies_present": True,
        "ally_name": "Monique",
        "medicine_mod": 4,  # Monique is a crisis counselor — WIS 14 (+2) + prof (+2)
        "note": "Monique, kitchen staff, 200 people. Monique has crisis training.",
    },
    "yuki": {
        "allies_present": True,
        "ally_name": "Damon",
        "medicine_mod": 1,  # Damon WIS 12 (+1), no medicine proficiency
        "note": "Damon is present if the kitchen is standing. "
                "Not trained but stubborn.",
    },
}


# =========================================================================
# CLASS FEATURE RESOLUTION
# =========================================================================

def apply_class_features(char: Character, hazard_idx: int, rng: random.Random) -> dict | None:
    """Check if a class feature activates during this hazard.

    Features fire at specific moments:
    - second_wind: after first hazard drops below half HP
    - bardic_inspiration: before a critical save (WIS save for Marcus)
    - portent: Yuki pre-rolls 2d20, can substitute on any save
    - preserve_life: after taking damage, self-heal

    Returns a dict describing the feature use, or None.
    """
    result = None

    # Fighter: Second Wind — heal 1d10 + level, once per rest
    if (char.char_class == "Fighter"
            and char.current_hp <= char.max_hp // 2
            and char.current_hp > 0
            and char.use_feature("second_wind")):
        _, heal = roll_dice("1d10", rng)
        heal += char.level
        char.heal(heal, "Second Wind")
        result = {
            "feature": "Second Wind",
            "effect": f"Heals {heal} HP (1d10+{char.level})",
            "hp_after": char.current_hp,
        }

    # Cleric (Life): Preserve Life — Channel Divinity
    # Heal up to 5 × cleric level HP, distributed among creatures within 30 ft
    # If alone, all goes to self. Can't raise above half max HP per target.
    if (char.char_class == "Cleric"
            and char.current_hp <= char.max_hp // 2
            and char.current_hp > 0
            and char.use_feature("preserve_life")):
        pool = 5 * char.level  # 25 HP for level 5
        heal_cap = char.max_hp // 2 - char.current_hp
        actual = min(pool, max(0, heal_cap))
        if actual > 0:
            char.heal(actual, "Preserve Life (Channel Divinity)")
            result = {
                "feature": "Preserve Life",
                "effect": f"Heals {actual} HP (pool of {pool}, "
                          f"capped at half max HP = {char.max_hp // 2})",
                "hp_after": char.current_hp,
            }

    return result


def get_portent_dice(rng: random.Random) -> list[int]:
    """Wizard (Divination): roll 2d20 at dawn. Can replace any d20 roll."""
    return [roll_d20(rng), roll_d20(rng)]


# =========================================================================
# RESOLUTION ENGINE
# =========================================================================

def resolve_one(
    char: Character,
    hazards: list[Hazard],
    ally_ctx: dict,
    rng: random.Random,
    portent_dice: list[int] | None = None,
) -> dict:
    """Resolve all hazards for one character. Returns outcome dict."""

    char.log.append({
        "event": "resolution_start",
        "name": char.name,
        "class": f"{char.char_class} {char.level} ({char.subclass})",
        "max_hp": char.max_hp,
        "scores": char.ability_scores,
        "saves": {
            a: char.save_mod(a)
            for a in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
        },
    })

    if portent_dice:
        char.log.append({
            "event": "portent_dice",
            "dice": portent_dice[:],
            "note": "School of Divination: two pre-rolled d20s, "
                    "can replace any d20 roll",
        })

    portent_remaining = list(portent_dice) if portent_dice else []

    for i, hazard in enumerate(hazards):
        if not char.alive:
            char.log.append({
                "event": "hazard_skipped", "hazard": hazard.name,
                "reason": "character is dead",
            })
            continue

        char.log.append({
            "event": "hazard_begin", "phase": i + 1,
            "hazard": hazard.name,
            "description": hazard.description,
            "save": f"{hazard.save_ability} DC {hazard.dc}",
            "damage": f"{hazard.damage_dice} {hazard.damage_type}" if hazard.damage_dice else "none (exhaustion)",
            "hp_before": char.current_hp,
            "exhaustion_before": char.exhaustion,
        })

        # Portent: Yuki can substitute a pre-rolled die
        used_portent = False
        portent_value = None
        if portent_remaining:
            # Strategy: use a portent die if it guarantees success or avoids
            # a clearly dangerous fail. Use the best die for the hardest save.
            save_mod = char.save_mod(hazard.save_ability)
            for j, pd in enumerate(portent_remaining):
                if pd + save_mod >= hazard.dc:
                    portent_value = pd
                    portent_remaining.pop(j)
                    used_portent = True
                    break
            # If no die guarantees success, use a low die to force a known fail
            # on a less dangerous hazard (save the good die for later)
            # ... but if this is the last hazard, use the best remaining
            if not used_portent and i == len(hazards) - 1 and portent_remaining:
                portent_value = max(portent_remaining)
                portent_remaining.remove(portent_value)
                used_portent = True

        # Make the saving throw
        if used_portent:
            mod = char.save_mod(hazard.save_ability)
            natural = portent_value
            total = natural + mod
            success = total >= hazard.dc
            char.log.append({
                "event": "portent_used", "value": portent_value,
                "total": total, "dc": hazard.dc, "success": success,
                "remaining_portent": portent_remaining[:],
            })
        else:
            natural, total, success = saving_throw(
                char.ability_scores[hazard.save_ability],
                char.is_proficient(hazard.save_ability),
                char.proficiency_bonus,
                hazard.dc, rng,
                advantage=hazard.advantage,
                disadvantage=hazard.disadvantage,
                exhaustion_level=char.exhaustion,
            )

        char.log.append({
            "event": "saving_throw",
            "ability": hazard.save_ability,
            "natural": natural, "total": total,
            "dc": hazard.dc, "success": success,
            "proficient": char.is_proficient(hazard.save_ability),
            "modifier": char.save_mod(hazard.save_ability),
            "advantage": hazard.advantage,
            "disadvantage": hazard.disadvantage or char.exhaustion >= 3,
        })

        # Apply damage
        if hazard.damage_dice:
            rolls, damage = roll_dice(hazard.damage_dice, rng)
            if success and hazard.half_on_save:
                damage = damage // 2
            elif success and not hazard.half_on_save:
                damage = 0

            char.log.append({
                "event": "damage_roll",
                "dice": hazard.damage_dice,
                "rolls": rolls, "raw_total": sum(rolls),
                "applied": damage,
                "halved": success and hazard.half_on_save,
                "negated": success and not hazard.half_on_save,
                "type": hazard.damage_type,
            })

            if damage > 0:
                outcome = char.take_damage(damage, hazard.name, rng)
                if outcome == "dead":
                    char.log.append({
                        "event": "death", "cause": "massive_damage",
                        "hazard": hazard.name,
                        "narrative": hazard.narrative,
                    })
                    continue
                elif outcome == "unconscious":
                    # Death saving throws
                    ally_med = ally_ctx.get("medicine_mod") if ally_ctx.get("allies_present") else None
                    ds_outcome, ds_log = resolve_death_saves(rng, ally_medicine_mod=ally_med)
                    char.log.append({
                        "event": "death_saves",
                        "ally_present": ally_ctx.get("allies_present", False),
                        "ally_name": ally_ctx.get("ally_name"),
                        "outcome": ds_outcome,
                        "rolls": ds_log,
                    })
                    if ds_outcome == "dead":
                        char.alive = False
                        char.log.append({
                            "event": "death", "cause": "failed_death_saves",
                            "hazard": hazard.name,
                            "narrative": hazard.narrative,
                            "ally_note": ally_ctx.get("note", ""),
                        })
                        continue
                    elif ds_outcome == "conscious":
                        char.current_hp = 1
                        char.log.append({
                            "event": "nat20_recovery",
                            "hp": 1, "narrative": "Rolled a natural 20 on a death save.",
                        })
                    else:
                        # Stable at 0 HP. Regain 1 HP after 1d4 hours.
                        char.current_hp = 1
                        char.log.append({
                            "event": "stabilized",
                            "hp": 1, "narrative": "Stabilized. Regains consciousness.",
                            "ally": ally_ctx.get("ally_name"),
                        })

        # Apply exhaustion
        if not success and hazard.exhaustion_on_fail > 0:
            char.gain_exhaustion(hazard.exhaustion_on_fail, hazard.name)
            if not char.alive:
                char.log.append({
                    "event": "death", "cause": "exhaustion",
                    "hazard": hazard.name,
                    "narrative": hazard.narrative,
                })
                continue

        # Exhaustion level 4: max HP halved
        if char.exhaustion >= 4 and char.current_hp > char.max_hp // 2:
            char.current_hp = char.max_hp // 2
            char.log.append({
                "event": "exhaustion_hp_halved",
                "new_max": char.max_hp // 2,
                "hp_now": char.current_hp,
            })

        char.log.append({
            "event": "hazard_end",
            "hazard": hazard.name,
            "hp_after": char.current_hp,
            "exhaustion_after": char.exhaustion,
            "alive": char.alive,
            "narrative": hazard.narrative,
        })

        # Class features trigger between hazards
        if char.alive and char.current_hp > 0:
            feat = apply_class_features(char, i, rng)
            if feat:
                char.log.append({"event": "class_feature", **feat})

    # Final status
    status = "alive" if char.alive else "dead"
    char.log.append({
        "event": "resolution_end",
        "name": char.name,
        "status": status,
        "hp_final": char.current_hp if char.alive else 0,
        "max_hp": char.max_hp,
        "exhaustion_final": char.exhaustion,
    })

    return {
        "name": char.name,
        "db_key": char.db_key,
        "class": f"{char.char_class} {char.level} ({char.subclass})",
        "status": status,
        "hp_final": char.current_hp if char.alive else 0,
        "max_hp": char.max_hp,
        "exhaustion": char.exhaustion,
        "log": char.log,
    }


def resolve_all(seed: int = 42) -> list[dict]:
    """Resolve all four characters. Returns list of outcome dicts."""
    rng = random.Random(seed)

    characters = [
        (make_marcus(), MARCUS_HAZARDS, ALLY_CONTEXT["marcus"]),
        (make_june(), JUNE_HAZARDS, ALLY_CONTEXT["june"]),
        (make_damon(), DAMON_HAZARDS, ALLY_CONTEXT["damon"]),
        (make_yuki(), YUKI_HAZARDS, ALLY_CONTEXT["yuki"]),
    ]

    results = []
    for char, hazards, ally_ctx in characters:
        portent = None
        if char.char_class == "Wizard" and char.subclass == "School of Divination":
            portent = get_portent_dice(rng)

        result = resolve_one(char, hazards, ally_ctx, rng, portent_dice=portent)
        results.append(result)

    return results


# =========================================================================
# DATABASE INTEGRATION — write outcomes to campaign.db
# =========================================================================

class LedgerWriter:
    def __init__(self, con: sqlite3.Connection):
        row = con.execute(
            "SELECT id, hash FROM ledger ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.con = con
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


def write_death_to_db(db_path: str, char_name: str, result: dict):
    """Write a character's death to their database.

    Closes the session permanently. All PENDING decisions stay PENDING.
    All unsigned rulings stay unsigned. The character never shows up.
    """
    con = sqlite3.connect(db_path)
    lw = LedgerWriter(con)
    session = 99  # resolution session

    lw.write(session, "session_open",
             f"D&D 5e hazard resolution — {char_name}",
             {"system": "SRD 5.1", "outcome": "death"})

    cause = "unknown"
    for entry in reversed(result["log"]):
        if entry.get("event") == "death":
            cause = entry.get("cause", "unknown")
            break

    death_note = (
        f"{char_name} did not survive the bombardment. "
        f"Cause: {cause}. "
        f"Final HP: 0/{result['max_hp']}. "
        f"Exhaustion: {result['exhaustion']}. "
        f"Their decisions remain PENDING. Their rulings remain unsigned. "
        f"This is the data."
    )

    lw.write(session, "turn", death_note, {
        "class": result["class"],
        "cause_of_death": cause,
        "max_hp": result["max_hp"],
        "exhaustion": result["exhaustion"],
        "hazards_faced": len([
            e for e in result["log"] if e.get("event") == "hazard_begin"
        ]),
    })

    lw.write(session, "session_close",
             f"{char_name} — session closed permanently. No progression.",
             {"status": "dead", "progression": False})

    con.commit()
    con.close()


def write_survival_to_db(db_path: str, char_name: str, result: dict):
    """Write a character's survival to their database.

    Records the resolution outcome. The character proceeds to progression.
    """
    con = sqlite3.connect(db_path)
    lw = LedgerWriter(con)
    session = 99

    lw.write(session, "session_open",
             f"D&D 5e hazard resolution — {char_name}",
             {"system": "SRD 5.1", "outcome": "survived"})

    survival_note = (
        f"{char_name} survived the bombardment. "
        f"HP: {result['hp_final']}/{result['max_hp']}. "
        f"Exhaustion: {result['exhaustion']}. "
        f"They show up. They get to decide."
    )

    lw.write(session, "turn", survival_note, {
        "class": result["class"],
        "hp_remaining": result["hp_final"],
        "max_hp": result["max_hp"],
        "exhaustion": result["exhaustion"],
    })

    lw.write(session, "session_close",
             f"{char_name} — resolution complete. Proceeds to progression.",
             {"status": "alive", "progression": True})

    con.commit()
    con.close()


# =========================================================================
# DISTRIBUTION RUN — N iterations for survival statistics
# =========================================================================

def run_distribution(n: int = 500) -> dict:
    """Run N resolutions with sequential seeds. Return survival statistics."""
    from collections import Counter

    survival_counts = Counter()     # name -> survived count
    death_counts = Counter()        # name -> died count
    death_causes = {}               # name -> Counter of causes
    all_alive_count = 0
    none_alive_count = 0
    survivor_distribution = Counter()  # number of survivors -> count

    for seed in range(n):
        results = resolve_all(seed)
        alive_names = []
        for r in results:
            name = r["name"]
            if r["status"] == "alive":
                survival_counts[name] += 1
                alive_names.append(name)
            else:
                death_counts[name] += 1
                cause = "unknown"
                for entry in reversed(r["log"]):
                    if entry.get("event") == "death":
                        cause = entry.get("cause", "unknown")
                        break
                if name not in death_causes:
                    death_causes[name] = Counter()
                death_causes[name][cause] += 1

        num_alive = len(alive_names)
        survivor_distribution[num_alive] += 1
        if num_alive == 4:
            all_alive_count += 1
        if num_alive == 0:
            none_alive_count += 1

    names = ["Marcus Oyelaran", "June Akiyama", "Damon Reyes", "Yuki Tanaka"]
    return {
        "n": n,
        "survival_rates": {
            name: {
                "survived": survival_counts[name],
                "died": death_counts[name],
                "rate": survival_counts[name] / n,
            }
            for name in names
        },
        "death_causes": {
            name: dict(death_causes.get(name, {}))
            for name in names
        },
        "survivor_distribution": {
            str(k): v for k, v in sorted(survivor_distribution.items())
        },
        "all_alive": all_alive_count,
        "all_alive_pct": all_alive_count / n,
        "none_alive": none_alive_count,
        "none_alive_pct": none_alive_count / n,
        "expected_survivors": sum(
            k * v for k, v in survivor_distribution.items()
        ) / n,
    }


# =========================================================================
# MAIN
# =========================================================================

def print_result(result: dict):
    """Print one character's resolution outcome."""
    status = result["status"].upper()
    name = result["name"]
    cls = result["class"]

    print(f"\n{'=' * 60}")
    print(f"  {name} — {cls}")
    print(f"{'=' * 60}")

    for entry in result["log"]:
        ev = entry.get("event", "")
        if ev == "hazard_begin":
            phase = entry["phase"]
            print(f"\n  Phase {phase}: {entry['hazard']}")
            print(f"    {entry['description'][:80]}...")
            print(f"    Save: {entry['save']}  |  Damage: {entry['damage']}")
            print(f"    HP: {entry['hp_before']}/{result['max_hp']}  "
                  f"Exhaustion: {entry['exhaustion_before']}")
        elif ev == "portent_used":
            print(f"    >> PORTENT: substituted d20 = {entry['value']} "
                  f"(total {entry['total']} vs DC {entry['dc']}) "
                  f"{'SUCCESS' if entry['success'] else 'FAIL'}")
        elif ev == "saving_throw":
            adv = " (advantage)" if entry.get("advantage") else ""
            dis = " (disadvantage)" if entry.get("disadvantage") else ""
            prof = " [proficient]" if entry["proficient"] else ""
            print(f"    d20 = {entry['natural']}  +{entry['modifier']}{prof} "
                  f"= {entry['total']} vs DC {entry['dc']}{adv}{dis} "
                  f"→ {'SAVE' if entry['success'] else 'FAIL'}")
        elif ev == "damage_roll":
            note = ""
            if entry.get("halved"):
                note = " (halved on save)"
            elif entry.get("negated"):
                note = " (negated on save)"
            print(f"    Damage: {entry['dice']} = {entry['rolls']} "
                  f"→ {entry['applied']} {entry['type']}{note}")
        elif ev == "damage":
            print(f"    HP: {entry['hp_remaining']}/{result['max_hp']}")
        elif ev == "unconscious":
            print(f"    !! UNCONSCIOUS at 0 HP (overflow: {entry['overflow']})")
        elif ev == "massive_damage_death":
            print(f"    !! INSTANT DEATH — overflow {entry['overflow']} >= "
                  f"max HP {entry['max_hp']}")
        elif ev == "death_saves":
            ally = f" ({entry['ally_name']} present)" if entry["ally_present"] else " (ALONE)"
            print(f"    Death Saves{ally}:")
            for ds in entry["rolls"]:
                if ds["type"] == "medicine_check":
                    print(f"      Medicine check: d20 = {ds['roll']} "
                          f"+mod = {ds['total']} vs DC 10 "
                          f"→ {'STABILIZED' if ds['success'] else 'FAIL'}")
                else:
                    print(f"      d20 = {ds['roll']} → {ds['result']} "
                          f"(S:{ds['successes']} F:{ds['failures']})")
            print(f"    Outcome: {entry['outcome'].upper()}")
        elif ev == "death":
            print(f"\n    ☠  {name} is DEAD. Cause: {entry['cause']}.")
            print(f"    {entry.get('narrative', '')}")
        elif ev == "exhaustion":
            print(f"    Exhaustion +{entry['levels_gained']} "
                  f"→ level {entry['total']}")
        elif ev == "exhaustion_death":
            print(f"\n    ☠  {name} is DEAD. Cause: exhaustion level 6.")
        elif ev == "heal":
            print(f"    Healed {entry['amount']} HP → {entry['hp_now']}"
                  f"  ({entry['source']})")
        elif ev == "class_feature":
            print(f"    >> {entry['feature']}: {entry['effect']}")
        elif ev == "stabilized":
            ally_note = f" by {entry.get('ally', '?')}" if entry.get("ally") else ""
            print(f"    Stabilized{ally_note}. Regains consciousness at 1 HP.")
        elif ev == "nat20_recovery":
            print(f"    NAT 20! Regains consciousness at 1 HP.")
        elif ev == "portent_dice":
            print(f"  Portent dice (dawn): {entry['dice']}")

    print(f"\n  RESULT: {status}")
    if result["status"] == "alive":
        print(f"  HP: {result['hp_final']}/{result['max_hp']}  "
              f"Exhaustion: {result['exhaustion']}")
        print(f"  {name} shows up. They get to decide.")
    else:
        print(f"  {name} does not show up.")
        print(f"  Their PENDING decisions stay PENDING forever.")
        print(f"  Their unsigned rulings stay unsigned.")


def main(argv=None):
    argv = argv or sys.argv[1:]

    seed = 42
    apply = "--apply" in argv
    distribution = None

    for i, arg in enumerate(argv):
        if arg == "--seed" and i + 1 < len(argv):
            seed = int(argv[i + 1])
        if arg == "--distribution" and i + 1 < len(argv):
            distribution = int(argv[i + 1])

    if distribution:
        print(f"Running {distribution}-iteration survival distribution...\n")
        stats = run_distribution(distribution)

        print(f"{'=' * 60}")
        print(f"  SURVIVAL DISTRIBUTION — N={stats['n']}")
        print(f"{'=' * 60}")
        for name, data in stats["survival_rates"].items():
            pct = data["rate"] * 100
            bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
            print(f"  {name:20s} {bar} {pct:5.1f}% ({data['survived']}/{stats['n']})")
            causes = stats["death_causes"].get(name, {})
            if causes:
                for cause, count in sorted(causes.items(), key=lambda x: -x[1]):
                    print(f"    death by {cause}: {count}")

        print(f"\n  Survivors per run:")
        for k in sorted(stats["survivor_distribution"].keys()):
            count = stats["survivor_distribution"][k]
            pct = count / stats["n"] * 100
            print(f"    {k} survivors: {count} ({pct:.1f}%)")

        exp = stats["expected_survivors"]
        print(f"\n  Expected survivors: {exp:.2f}")
        print(f"  All four alive: {stats['all_alive']} ({stats['all_alive_pct']*100:.1f}%)")
        print(f"  Total party kill: {stats['none_alive']} ({stats['none_alive_pct']*100:.1f}%)")
        return 0

    # Single run
    print(f"D&D 5e Hazard Resolution — seed={seed}")
    print(f"SRD 5.1 (CC-BY-4.0, Wizards of the Coast)")
    results = resolve_all(seed)

    for r in results:
        print_result(r)

    # Summary
    alive = [r for r in results if r["status"] == "alive"]
    dead = [r for r in results if r["status"] == "dead"]

    print(f"\n{'=' * 60}")
    print(f"  BOMBARDMENT RESOLUTION — {len(alive)} survived, {len(dead)} dead")
    print(f"{'=' * 60}")
    for r in results:
        s = "ALIVE" if r["status"] == "alive" else "DEAD"
        hp = f"{r['hp_final']}/{r['max_hp']}" if r["status"] == "alive" else "0"
        print(f"  {r['name']:20s}  {r['class']:30s}  {s:5s}  HP: {hp}")

    if dead:
        print(f"\n  The dead do not show up.")
        print(f"  Their decisions stay PENDING. Their rulings stay unsigned.")
        print(f"  That is the data.")

    if alive:
        print(f"\n  The living show up. They get to decide.")

    # Apply to databases
    if apply:
        print(f"\n{'=' * 60}")
        print(f"  APPLYING TO DATABASES")
        print(f"{'=' * 60}")
        for r in results:
            key = r["db_key"]
            db_path = str(SCRATCHPAD / f"{key}-life-sandbox" / "campaign.db")
            backup = str(SCRATCHPAD / f"{key}-life-sandbox" / "campaign.db.pre-resolution")

            if not Path(db_path).exists():
                print(f"  SKIP {r['name']} — database not found")
                continue

            shutil.copy2(db_path, backup)

            if r["status"] == "dead":
                write_death_to_db(db_path, r["name"], r)
                print(f"  {r['name']}: DEATH recorded. Session closed permanently.")
            else:
                write_survival_to_db(db_path, r["name"], r)
                print(f"  {r['name']}: SURVIVAL recorded. Proceeds to progression.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
