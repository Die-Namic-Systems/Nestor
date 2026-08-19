#!/usr/bin/env python3
"""humans.py — Yuki fixes Nestor, with everything else happening.

Same seven items.  Same dice pools.  Same clocks.  But now the person
working the backlog also has a herniated disc, a house in foreclosure,
two kids, an ex-wife who is both extremely helpful and extremely
boundaried, a cross-country move in three weeks, a car with 210K miles,
and an insurance company that put her back specialist out of network
six weeks ago and hasn't finished "reviewing" the appeal.

The mechanics are the same as humans_in_offices.py.  The dice are the
same.  The person is different — not less skilled, but more encumbered.
The system's completion rate depends on the employee's life
circumstances.  The governance model doesn't account for that.

Stats:
    Analysis  (4d) — she still reads code better than anyone on the team.
    Awareness (3d) — she sees the pattern, when the pain lets her focus.
    Buy-In    (1d) — she can make the case, but she has to leave by 3:15.

Life:
    L4-L5 disc herniation — burnout capacity reduced from 9 to 7.
    Foreclosure — a danger clock.  If it fills, she stops.
    Cross-country move — 5 items max.  She leaves in three weeks.
    Before each item — life happens.  The dice decide what.

Dice pool mechanics based on Blades in the Dark by John Harper,
licensed under CC BY 3.0 Unported.
http://www.bladesinthedark.com/

Usage:
    python3 humans.py                # seed=42
    python3 humans.py --seed 937
    python3 humans.py --verbose
    python3 humans.py --distribution 500
    python3 humans.py --shortcut
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass, field


# =========================================================================
# RESOLUTION MECHANICS (same as humans_in_offices.py)
# =========================================================================

def roll_pool(n: int, rng: random.Random) -> dict:
    zero = n <= 0
    count = 2 if zero else n
    dice = [rng.randint(1, 6) for _ in range(count)]
    effective = min(dice) if zero else max(dice)
    sixes = sum(1 for d in dice if d == 6)

    if sixes >= 2:
        result = "critical"
    elif effective >= 6:
        result = "success"
    elif effective >= 4:
        result = "partial"
    else:
        result = "failure"

    return {
        "dice": sorted(dice), "effective": effective,
        "sixes": sixes, "result": result, "pool": n,
    }


TICKS = {
    "mentioned": {"critical": 2, "success": 1, "partial": 1, "failure": 0},
    "assigned":  {"critical": 3, "success": 2, "partial": 1, "failure": 0},
    "mandated":  {"critical": 5, "success": 3, "partial": 2, "failure": 0},
}

BURNOUT_TABLE = {
    "scheduled":   {"critical": 0, "success": 0, "partial": 0, "failure": 0},
    "ad-hoc":      {"critical": 0, "success": 0, "partial": 0, "failure": 1},
    "unbudgeted":  {"critical": 0, "success": 0, "partial": 1, "failure": 2},
}

MAX_BURNOUT_DEFAULT = 9
MAX_BURNOUT_LIFE = 7    # the back takes 2 slots
MAX_DISILLUSION = 2
COFFEE_BREAK = 1

RESULT_LABELS = {
    "critical": "breakthrough",
    "success":  "done",
    "partial":  "progress",
    "failure":  "nothing",
}


# =========================================================================
# EMPLOYEE
# =========================================================================

@dataclass
class Employee:
    name: str
    title: str
    base_skills: dict[str, int]
    burnout_cap: int = MAX_BURNOUT_DEFAULT
    burnout: int = 0
    disillusionments: int = 0
    conditions: list[str] = field(default_factory=list)

    def skill(self, name: str) -> int:
        return max(0, self.base_skills.get(name, 0) - self.disillusionments)

    def take_burnout(self, amount: int) -> str | None:
        if amount <= 0:
            return None
        self.burnout += amount
        if self.burnout >= self.burnout_cap:
            self.disillusionments += 1
            self.burnout = 0
            if self.disillusionments >= MAX_DISILLUSION:
                return "resigned"
            return "disillusioned"
        return None

    def recover_burnout(self, amount: int):
        if not self.resigned:
            self.burnout = max(0, self.burnout - amount)

    @property
    def resigned(self) -> bool:
        return self.disillusionments >= MAX_DISILLUSION


def make_yuki() -> Employee:
    """Yuki Tanaka, 34, Staff Software Engineer, Tools & Infrastructure.

    Three months in.  Took the job for the relocation package.
    Analysis 4d — she still reads code better than anyone on the team.
    Awareness 3d — she sees the pattern, when the pain lets her focus.
    Buy-In 1d — she can make the case, but she has to leave by 3:15.

    Also:
    - L4-L5 disc herniation, 18 months, ibuprofen and a $15 desk riser.
    - A house on Elm, 60 days from foreclosure.
    - Hana (7), Kai (4).
    - Nadia Orozco (35), ex-wife, shared custody, helpful, boundaried.
    - A move to Portland in three weeks.
    - A 2016 Civic with 210,000 miles.
    - An insurance appeal that has been "in review" for six weeks.
    """
    return Employee(
        name="Yuki Tanaka",
        title="Staff Software Engineer, Tools & Infrastructure",
        base_skills={"analysis": 4, "awareness": 3, "buy-in": 1},
        burnout_cap=MAX_BURNOUT_LIFE,
    )


# =========================================================================
# LIFE OUTSIDE THE OFFICE
# =========================================================================

@dataclass
class Life:
    """Everything that isn't the backlog."""

    # The back
    back: str = "L4-L5 disc herniation, 18 months"
    specialist_status: str = "out of network since June, appeal 'in review'"

    # The house
    house: str = "Elm Street, purchased 2019, joint mortgage"
    foreclosure_clock: int = 0
    foreclosure_max: int = 4
    mortgage_note: str = (
        "Rate went variable January 2026. Payment: $2,400 → $3,800. "
        "Nadia's name removed from deed in divorce, NOT removed from "
        "loan. The bank calls Tuesday and Thursday."
    )

    # The kids
    kids: tuple[str, ...] = ("Hana (7)", "Kai (4)")
    hana_note: str = "Asks questions Yuki isn't ready to answer."
    kai_note: str = "Doesn't understand why they're putting things in boxes."

    # The ex
    ex: str = "Nadia Orozco"
    ex_age: int = 35
    ex_title: str = "Architectural engineer"
    ex_note: str = (
        "Shared custody. Pays exactly half and not a dollar more. "
        "Will drive the kids to any appointment. Will also send a "
        "4-paragraph text about the 529 allocation at 2 PM on a Tuesday."
    )

    # The move
    move_to: str = "Portland"
    move_weeks: int = 3
    move_reason: str = (
        "New job starts September 1. Pays $15K more. Nadia's sister "
        "Elena offered to help with the kids."
    )
    move_item_limit: int = 5

    # The car
    car: str = "2016 Honda Civic, 210,000 miles"
    car_note: str = "Makes a new noise every week. The mechanic says 'it's fine.'"

    # Tracking
    life_events: list[dict] = field(default_factory=list)

    @property
    def foreclosure_full(self) -> bool:
        return self.foreclosure_clock >= self.foreclosure_max


LIFE_EVENTS = [
    {
        "roll": 1,
        "key": "kid_sick",
        "burn": 3,
        "foreclosure_tick": False,
        "text": (
            "Kai has a fever. School called at 10 AM. She packs the "
            "laptop, picks him up, holds him on the couch while he "
            "sleeps, and tries to read a diff one-handed."
        ),
    },
    {
        "roll": 2,
        "key": "car",
        "burn": 2,
        "foreclosure_tick": False,
        "text": (
            "The Civic won't start. The new noise was a warning. "
            "Uber to school, Uber to office — $47 she doesn't have "
            "in the checking account, so it goes on the card."
        ),
    },
    {
        "roll": 3,
        "key": "foreclosure",
        "burn": 2,
        "foreclosure_tick": True,
        "text": (
            "The bank called. Not Tuesday, not Thursday — today. "
            "The conversation takes 25 minutes. She learns the word "
            "'deficiency judgment' and wishes she hadn't."
        ),
    },
    {
        "roll": 4,
        "key": "coparent",
        "burn": 1,
        "foreclosure_tick": False,
        "text": (
            "Nadia texts during standup: 'Can we talk about the 529 "
            "allocation before the move? Also Hana's teacher wants "
            "to schedule a transition meeting.' The text is four "
            "paragraphs. The conversation takes 40 minutes."
        ),
    },
    {
        "roll": 5,
        "key": "back",
        "burn": 2,
        "foreclosure_tick": False,
        "text": (
            "The L4-L5 is screaming. She can't sit. She stands at "
            "the $15 desk riser and works in 20-minute intervals "
            "between stretches. The insurance appeal is still "
            "'in review.' It has been 'in review' for six weeks."
        ),
    },
    {
        "roll": 6,
        "key": "school",
        "burn": 1,
        "foreclosure_tick": False,
        "text": (
            "Hana's teacher emails: 'Can we discuss how Hana is "
            "processing the move? She told another student her "
            "house is being taken away.' The conference is at 2 PM. "
            "Yuki leaves work at 1:45."
        ),
    },
    {
        "roll": 7,
        "key": "packing",
        "burn": 1,
        "foreclosure_tick": False,
        "text": (
            "She packed three boxes last night after the kids went "
            "to bed. Kai came out at 10 PM and asked why Splash "
            "was in a box. She took the whale out. The box is still "
            "open on the living room floor."
        ),
    },
    {
        "roll": 8,
        "key": "quiet",
        "burn": 0,
        "foreclosure_tick": False,
        "text": (
            "A quiet morning. Both kids at school. No calls from the "
            "bank. The back is a 4 out of 10. She has until 3:15."
        ),
    },
    {
        "roll": 9,
        "key": "nadia_helps",
        "burn": -1,
        "foreclosure_tick": False,
        "text": (
            "Nadia picks up both kids and takes them to Elena's for "
            "the evening. 'You need to pack,' she says, which means "
            "'I know you need to work.' Yuki gets five uninterrupted "
            "hours. The back still hurts but nobody needs her."
        ),
    },
    {
        "roll": 10,
        "key": "nadia_helps_big",
        "burn": -2,
        "foreclosure_tick": False,
        "text": (
            "Nadia takes the kids for the whole weekend. 'Elena's "
            "taking them to the zoo,' she says. It's not in the "
            "custody schedule. She doesn't mention that. Yuki "
            "sleeps nine hours and wakes up without pain for the "
            "first time in weeks."
        ),
    },
]


def roll_life_event(rng: random.Random, life: Life) -> dict:
    """Roll for what happens before she can open the laptop."""
    roll = rng.randint(1, len(LIFE_EVENTS))
    event = LIFE_EVENTS[roll - 1]
    if event["foreclosure_tick"]:
        life.foreclosure_clock = min(
            life.foreclosure_clock + 1, life.foreclosure_max
        )
    life.life_events.append(event)
    return event


# =========================================================================
# THE BACKLOG (same items as humans_in_offices.py)
# =========================================================================

@dataclass
class Item:
    key: str
    title: str
    where: str
    segments: int
    skill: str
    position: str
    effect: str
    obstacle: str
    evidence: str

    completed: str
    half: str
    quarter: str
    empty: str

    requires: str = ""
    shortcut: str = ""
    shortcut_cost: str = ""


BACKLOG = [
    Item(
        key="routing",
        title="The CLI default routes queries to the wrong dataset",
        where="nestor/cli.py:803-804",
        segments=4,
        skill="awareness", position="scheduled", effect="assigned",
        obstacle="The Default Nobody Questioned",
        evidence=(
            "`nestor match 'data breaches'` searches 9 candidates "
            "instead of 1230. The default was set during the prototype."
        ),
        completed=(
            "The default is removed. The CLI infers the dataset from "
            "the store's contents."
        ),
        half=(
            "A warning fires when the default dataset is suspiciously "
            "small. The default doesn't change."
        ),
        quarter=(
            "She found the line — cli.py:803. The patch is written "
            "but untested."
        ),
        empty="The default is still wrong.",
    ),

    Item(
        key="matcher",
        title="The search engine needs you to already know the answer",
        where="nestor/semantic_matcher.py, nestor/memory.py",
        segments=6,
        skill="analysis", position="ad-hoc", effect="assigned",
        requires="routing",
        obstacle="The Search Bar That Requires Exact Phrasing",
        evidence=(
            "'AI governance' scores 0.444 against a corpus about AI "
            "governance. The search engine uses string matching."
        ),
        completed=(
            "Semantic search is the default. String matching stays as "
            "fallback. The relevance threshold recalibrates per method."
        ),
        half=(
            "Query normalization improved. Scores climb from 0.385 to "
            "~0.55. Still string-based."
        ),
        quarter="She documented the gap and the seam for swapping the engine.",
        empty="The search engine still requires exact phrasing.",
        shortcut=(
            "Ship without recalibrating the threshold. +1d."
        ),
        shortcut_cost=(
            "The threshold is tuned for string matching. The new "
            "engine's scores are on a different scale."
        ),
    ),

    Item(
        key="governance_graph",
        title="The approval workflow has no blocking rules",
        where="docs/dogfood/nestor.db — 0 edges, 0 rejections",
        segments=6,
        skill="awareness", position="ad-hoc", effect="assigned",
        requires="matcher",
        obstacle="The Org Chart With No Lines",
        evidence=(
            "451 decisions, 0 relationships between them. The conflict "
            "checker always returns 'clear.'"
        ),
        completed=(
            "The CLI writes draft relationships. The conflict checker "
            "can block proposals. The process has teeth."
        ),
        half=(
            "A script flags overlapping concepts as candidate "
            "relationships. Nobody's wired it into the workflow."
        ),
        quarter=(
            "She named why the checker always returns 'clear' — the "
            "gate is open because nobody built a wall."
        ),
        empty="The approval workflow has no blocking rules.",
    ),

    Item(
        key="seal_gap",
        title="Nobody has ever used the approval ceremony",
        where="docs/dogfood/nestor.db — 451 draft, 0 approved",
        segments=8,
        skill="buy-in", position="unbudgeted", effect="mentioned",
        requires="governance_graph",
        obstacle="The Approval Form Nobody Fills Out",
        evidence=(
            "451 product decisions, all draft. The serve path requires "
            "'approved.' Nobody has ever sat down and clicked 'approve.'"
        ),
        completed=(
            "Twenty decisions are approved. The serve path returns "
            "answers. The process works."
        ),
        half=(
            "A triage list is in the team lead's inbox. "
            "They haven't opened it."
        ),
        quarter=(
            "She wrote the memo. Nobody's read it."
        ),
        empty=(
            "451 draft, 0 approved. The tool that insists 'a human "
            "must approve' has never had a human approve anything."
        ),
        shortcut="Run the auto-approval script. +1d. Dashboard turns green.",
        shortcut_cost=(
            "The approval field says 'machine' where it should say "
            "a person's name."
        ),
    ),

    Item(
        key="cross_domain",
        title="The two databases don't talk to each other",
        where="docs/dogfood/nestor.db vs data/nestor-demo.db",
        segments=8,
        skill="analysis", position="ad-hoc", effect="assigned",
        requires="matcher",
        obstacle="The Two Teams That Share A Kitchen But Not A Database",
        evidence=(
            "Product decisions and research findings in separate "
            "databases. One search can't surface both."
        ),
        completed=(
            "A `--stores` flag searches multiple databases. Results "
            "interleaved by relevance."
        ),
        half="A wrapper script searches both sequentially.",
        quarter="She mapped the schema overlap.",
        empty="The databases remain separate.",
    ),

    Item(
        key="policy_duplication",
        title="The company policy is copied in six documents",
        where="CLAUDE.md, AGENTS.md, docs/agent-guide.md, hooks/seat.md",
        segments=4,
        skill="awareness", position="scheduled", effect="assigned",
        obstacle="The Style Guide That Drifted Into Six Versions",
        evidence=(
            "'A human must approve' appears in six files, each "
            "phrased slightly differently."
        ),
        completed="Two files are the source of truth. The other four are pointers.",
        half="Each copy is marked with a pointer to the canonical source.",
        quarter="She counted: six files, six phrasings.",
        empty="Each document drifts independently.",
    ),

    Item(
        key="verifier_policy",
        title="The sign-off field accepts any name",
        where="nestor/memory.py — add_pair accepts any verifier string",
        segments=6,
        skill="analysis", position="ad-hoc", effect="assigned",
        requires="seal_gap",
        obstacle="The Signature Line That Accepts 'Mickey Mouse'",
        evidence=(
            "The approval function accepts any string as the "
            "approver's name. No employee list, no role check."
        ),
        completed=(
            "An allow-list in the database. The approval function "
            "rejects unknown names."
        ),
        half="A warning fires on unrecognized names.",
        quarter="She documented the gap between the policy and the code.",
        empty="Any name is accepted. The field is cosmetic.",
    ),
]

BACKLOG_BY_KEY = {item.key: item for item in BACKLOG}

MAX_ROLLS = 30


# =========================================================================
# THE SPRINT
# =========================================================================

def run_sprint(seed: int, *, verbose: bool = False,
               shortcut: bool = False, no_cap: bool = False) -> dict:
    rng = random.Random(seed)
    yuki = make_yuki()
    life = Life()
    if no_cap:
        life.move_item_limit = len(BACKLOG)
    done: set[str] = set()
    shortcuts_taken: list[str] = []
    log: list[dict] = []
    items_attempted = 0

    for item in BACKLOG:
        if yuki.resigned:
            log.append({"item": item, "skipped": True,
                        "reason": "resigned"})
            continue

        if items_attempted >= life.move_item_limit:
            log.append({"item": item, "skipped": True,
                        "reason": (
                            f"the move — Portland is in {life.move_weeks} "
                            f"weeks and the boxes aren't packed"
                        )})
            continue

        if life.foreclosure_full:
            log.append({"item": item, "skipped": True,
                        "reason": (
                            "the house — she has to be at the bank in "
                            "person tomorrow morning"
                        )})
            continue

        if item.requires and item.requires not in done:
            req = BACKLOG_BY_KEY[item.requires]
            log.append({"item": item, "skipped": True,
                        "reason": f"blocked on [{req.title}]"})
            continue

        # Life happens before the work
        life_ev = roll_life_event(rng, life)
        if life_ev["burn"] > 0:
            yuki.take_burnout(life_ev["burn"])
        elif life_ev["burn"] < 0:
            yuki.recover_burnout(abs(life_ev["burn"]))

        if yuki.resigned:
            log.append({"item": item, "skipped": True,
                        "reason": "resigned (life burnout before she opened the laptop)",
                        "life_event": life_ev})
            continue

        if life.foreclosure_full:
            log.append({"item": item, "skipped": True,
                        "reason": "the house — foreclosure clock filled",
                        "life_event": life_ev})
            continue

        items_attempted += 1

        filled = 0
        rolls: list[dict] = []
        took_shortcut = shortcut and bool(item.shortcut)
        if took_shortcut:
            shortcuts_taken.append(item.key)
        bonus = 1 if took_shortcut else 0

        for roll_num in range(MAX_ROLLS):
            if yuki.resigned or filled >= item.segments:
                break

            pool = yuki.skill(item.skill) + bonus
            result = roll_pool(pool, rng)
            ticks = TICKS[item.effect][result["result"]]
            burn = BURNOUT_TABLE[item.position][result["result"]]

            filled = min(filled + ticks, item.segments)
            event = yuki.take_burnout(burn)

            if event == "disillusioned":
                yuki.conditions.append(
                    f"disillusioned: {item.obstacle.lower()}"
                    if item.key == "seal_gap"
                    else f"burned out on {item.key}"
                )

            rolls.append({
                "roll": roll_num + 1,
                "pool": pool,
                "dice": result["dice"],
                "effective": result["effective"],
                "result": result["result"],
                "label": RESULT_LABELS[result["result"]],
                "ticks": ticks,
                "filled": filled,
                "segments": item.segments,
                "burn": burn,
                "burnout": yuki.burnout,
                "disillusionments": yuki.disillusionments,
                "event": event,
            })

            if event == "resigned":
                break

        pct = filled / item.segments
        if pct >= 1.0:
            level = "completed"
            done.add(item.key)
        elif pct >= 0.5:
            level = "half"
        elif pct > 0:
            level = "quarter"
        else:
            level = "empty"

        log.append({
            "item": item,
            "rolls": rolls,
            "filled": filled,
            "segments": item.segments,
            "pct": pct,
            "level": level,
            "description": getattr(item, level),
            "shortcut": took_shortcut,
            "life_event": life_ev,
        })

        yuki.recover_burnout(COFFEE_BREAK)

        if verbose and not log[-1].get("skipped"):
            _verbose(log[-1], yuki)

    return {
        "seed": seed,
        "done": done,
        "total": len(BACKLOG),
        "burnout": yuki.burnout,
        "disillusionments": yuki.disillusionments,
        "conditions": list(yuki.conditions),
        "shortcuts": shortcuts_taken,
        "life": {
            "foreclosure": life.foreclosure_clock,
            "foreclosure_max": life.foreclosure_max,
            "events": [e["key"] for e in life.life_events],
        },
        "log": log,
    }


def _verbose(entry: dict, emp: Employee) -> None:
    item = entry["item"]
    base = emp.base_skills.get(item.skill, 0)
    eff = emp.skill(item.skill)
    life_ev = entry.get("life_event")
    print()
    print("─" * 60)
    if life_ev:
        print(f"  Before work: {life_ev['text'][:100]}...")
        if life_ev["burn"] > 0:
            print(f"  (burnout +{life_ev['burn']} → {emp.burnout}/{emp.burnout_cap})")
        elif life_ev["burn"] < 0:
            print(f"  (burnout {life_ev['burn']} → {emp.burnout}/{emp.burnout_cap})")
        print()
    print(f"  {item.title}")
    print(f"  {item.where}")
    deg = "" if base == eff else f" (was {base}d)"
    sc = " +1d shortcut" if entry.get("shortcut") else ""
    print(f"  {item.skill} {eff}d{deg}{sc}, "
          f"{item.position}, {item.effect}")
    print(f"  Obstacle: {item.obstacle}")
    print()
    for r in entry["rolls"]:
        bar = _bar(r["filled"], r["segments"])
        extras = []
        if r["burn"]:
            extras.append(f"burnout {r['burnout']}/{emp.burnout_cap}")
        if r["event"] == "disillusioned":
            extras.append("DISILLUSIONED")
        elif r["event"] == "resigned":
            extras.append("RESIGNED")
        extra = "  " + ", ".join(extras) if extras else ""
        dice_str = ",".join(str(d) for d in r["dice"])
        print(f"    {r['roll']:>2}. {r['pool']}d→[{dice_str}] "
              f"{r['label']:<12} +{r['ticks']} {bar}{extra}")
    print()
    print(f"  {entry['level'].upper()}: "
          f"{entry['description'][:200]}")


# =========================================================================
# REPORT
# =========================================================================

def narrate(result: dict) -> str:
    lines: list[str] = []
    lines.append("=" * 64)
    lines.append("  HUMANS")
    lines.append(f"  Seed: {result['seed']}")
    if result["shortcuts"]:
        lines.append(f"  Shortcuts: {', '.join(result['shortcuts'])}")
    lines.append("=" * 64)
    lines.append("")
    lines.append("Yuki Tanaka, 34. Staff Software Engineer, three months in.")
    lines.append("She took this job for the relocation package.")
    lines.append("")
    lines.append("What's on her desk:")
    lines.append("  - Seven items in the tech debt tracker")
    lines.append("  - A herniated disc at L4-L5 (the back specialist")
    lines.append("    is out of network since the plan change in June)")
    lines.append("  - A house on Elm Street, 60 days from foreclosure")
    lines.append("    (the rate went variable, the payment doubled,")
    lines.append("    Nadia took her name off the deed but not the loan)")
    lines.append("  - A cross-country move to Portland in three weeks")
    lines.append("  - Hana, 7, who told her teacher the house is being")
    lines.append("    taken away")
    lines.append("  - Kai, 4, who doesn't understand why Splash is in a box")
    lines.append("  - Nadia, her ex-wife, who will drive the kids to")
    lines.append("    school and who will also text about the 529")
    lines.append("    allocation during standup")
    lines.append("  - A 2016 Civic with 210,000 miles")
    lines.append("")
    lines.append("Her manager says the sprint is full.")
    lines.append("Her life says the sprint is full.")
    lines.append("They're talking about different sprints.")
    lines.append("")

    fc = result["life"]["foreclosure"]
    fc_max = result["life"]["foreclosure_max"]
    lines.append(f"Foreclosure: {_bar(fc, fc_max)} {fc}/{fc_max}")
    lines.append("")

    for entry in result["log"]:
        item = entry["item"]

        if entry.get("skipped"):
            lines.append(f"  — BLOCKED: {item.title}")
            lines.append(f"    ({entry['reason']})")
            life_ev = entry.get("life_event")
            if life_ev:
                for wl in _wrap(life_ev["text"], 56):
                    lines.append(f"    {wl}")
            lines.append("")
            continue

        life_ev = entry.get("life_event")
        if life_ev:
            lines.append(f"  Before work:")
            for wl in _wrap(life_ev["text"], 56):
                lines.append(f"    {wl}")
            burn = life_ev["burn"]
            if burn > 0:
                lines.append(f"    (burnout +{burn})")
            elif burn < 0:
                lines.append(f"    (burnout {burn})")
            lines.append("")

        lines.append("─" * 64)
        lines.append(f"  {item.title}")
        lines.append(f"  {item.where}")
        lines.append(f"  Skill: {item.skill}  |  "
                      f"Priority: {item.position}  |  "
                      f"Scope: {item.effect}")
        bar = _bar(entry["filled"], entry["segments"])
        lines.append(f"  Progress: {bar} {entry['filled']}/{entry['segments']}")
        lines.append(f"  Obstacle: {item.obstacle}")
        lines.append("")

        for r in entry["rolls"]:
            extras = []
            if r["burn"]:
                extras.append(f"burnout {r['burnout']}/{MAX_BURNOUT_LIFE}")
            if r["event"] == "disillusioned":
                extras.append("DISILLUSIONED")
            elif r["event"] == "resigned":
                extras.append("RESIGNED")
            extra = "  " + ", ".join(extras) if extras else ""
            dice_str = ",".join(str(d) for d in r["dice"])
            bar_r = _bar(r["filled"], r["segments"])
            lines.append(
                f"    {r['roll']:>2}. {r['pool']}d→[{dice_str}] "
                f"{r['label']:<12} +{r['ticks']} {bar_r}{extra}"
            )

        lines.append("")
        lines.append(f"  Status: {entry['level'].upper()}")
        for wl in _wrap(entry["description"], 56):
            lines.append(f"    {wl}")
        lines.append("")

    # — Summary —
    completed = len(result["done"])
    total = result["total"]
    dis = result["disillusionments"]

    lines.append("=" * 64)
    lines.append("  END OF SPRINT")
    lines.append("=" * 64)
    lines.append("")

    if completed == total:
        lines.append("  All items closed. Despite everything.")
        if dis:
            lines.append(f"  Cost: {dis} disillusionment{'s' if dis > 1 else ''}.")
            for c in result["conditions"]:
                lines.append(f"    — {c}")
        if result["shortcuts"]:
            lines.append("  But she took the shortcut.")
            for s in result["shortcuts"]:
                item = BACKLOG_BY_KEY[s]
                for wl in _wrap(item.shortcut_cost, 56):
                    lines.append(f"    {wl}")
    else:
        partial = [
            e for e in result["log"]
            if not e.get("skipped") and e.get("level") != "completed"
        ]
        blocked = [e for e in result["log"] if e.get("skipped")]

        lines.append(f"  {completed}/{total} items closed.")
        if dis:
            lines.append(f"  {dis} disillusionment{'s' if dis > 1 else ''}.")
            for c in result["conditions"]:
                lines.append(f"    — {c}")
        lines.append("")
        if partial:
            for pe in partial:
                bar = _bar(pe["filled"], pe["segments"])
                lines.append(f"  {pe['item'].title[:50]}")
                lines.append(f"    {bar} {pe['filled']}/{pe['segments']}")
            lines.append("")
        if blocked:
            for be in blocked:
                lines.append(f"  — {be['item'].title}")
                lines.append(f"    ({be['reason']})")
            lines.append("")

        lines.append("  The code is the same. The dice are the same.")
        lines.append("  The person is different — not less skilled,")
        lines.append("  but more encumbered.")
        lines.append("")
        lines.append("  The system's completion rate depends on the")
        lines.append("  employee's life circumstances.")
        lines.append("  The governance model doesn't account for that.")

    lines.append("")
    lines.append("  Everything above is a draft.")
    lines.append("  The engineer can open the codebase.")
    lines.append("  She cannot approve her own work.")
    lines.append("  And she has to pick up Kai by 3:15.")
    lines.append("")

    return "\n".join(lines)


def _bar(filled: int, segments: int) -> str:
    return "[" + "■" * filled + "□" * (segments - filled) + "]"


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    out: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            out.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        out.append(current)
    return out


# =========================================================================
# DISTRIBUTION
# =========================================================================

def distribution(n: int, *, shortcut: bool = False,
                 no_cap: bool = False) -> None:
    from collections import Counter

    completion_hist: Counter[int] = Counter()
    item_pcts: dict[str, list[float]] = {i.key: [] for i in BACKLOG}
    dis_hist: Counter[int] = Counter()
    fc_hist: Counter[int] = Counter()
    life_event_counts: Counter[str] = Counter()

    for seed in range(n):
        result = run_sprint(seed, shortcut=shortcut, no_cap=no_cap)
        completion_hist[len(result["done"])] += 1
        dis_hist[result["disillusionments"]] += 1
        fc_hist[result["life"]["foreclosure"]] += 1
        for ev_key in result["life"]["events"]:
            life_event_counts[ev_key] += 1

        for entry in result["log"]:
            k = entry["item"].key
            if entry.get("skipped"):
                item_pcts[k].append(0.0)
            else:
                item_pcts[k].append(entry["pct"])

    cap = " (no move cap)" if no_cap else ""
    label = " (with shortcuts)" if shortcut else ""
    print(f"\nDistribution over {n} seeds — Humans{label}{cap}")
    print("=" * 70)

    full = completion_hist.get(len(BACKLOG), 0)
    print(f"\nAll items closed: {full}/{n} ({100 * full / n:.1f}%)")

    print(f"\nItems completed:")
    for k in range(len(BACKLOG) + 1):
        count = completion_hist.get(k, 0)
        pct = 100 * count / n
        bar_len = int(40 * count / n)
        print(f"  {k}/7: {count:>5} ({pct:>5.1f}%) {'█' * bar_len}")

    print(f"\nDisillusionments:")
    for d in range(MAX_DISILLUSION + 1):
        count = dis_hist.get(d, 0)
        print(f"  {d}: {count:>5} ({100 * count / n:>5.1f}%)")

    print(f"\nForeclosure clock at end:")
    for f in range(5):
        count = fc_hist.get(f, 0)
        print(f"  {f}/{Life.foreclosure_max}: {count:>5} ({100 * count / n:>5.1f}%)")

    print(f"\nLife events ({sum(life_event_counts.values())} total):")
    for ev in LIFE_EVENTS:
        count = life_event_counts.get(ev["key"], 0)
        print(f"  {ev['key']:<16} {count:>5}")

    print(f"\n{'Item':<42} {'Avg%':>5} {'Done':>5} "
          f"{'≥50%':>5} {'=0%':>5}")
    print("─" * 65)
    for item in BACKLOG:
        pcts = item_pcts[item.key]
        avg_pct = sum(pcts) / len(pcts) if pcts else 0
        done_c = sum(1 for p in pcts if p >= 1.0)
        half_c = sum(1 for p in pcts if p >= 0.5)
        zero_c = sum(1 for p in pcts if p == 0)
        print(f"  {item.title[:40]:<41} {100 * avg_pct:>4.0f}% "
              f"{done_c:>5} {half_c:>5} {zero_c:>5}")
    print()


# =========================================================================
# MAIN
# =========================================================================

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--shortcut", action="store_true",
                    help="take the shortcut on items that offer one")
    ap.add_argument("--distribution", type=int, metavar="N",
                    help="run N seeds and report statistics")
    ap.add_argument("--no-cap", action="store_true",
                    help="lift the move item limit (5 -> 7)")
    args = ap.parse_args()

    if args.distribution:
        distribution(args.distribution, shortcut=args.shortcut,
                     no_cap=args.no_cap)
        return 0

    result = run_sprint(args.seed, verbose=args.verbose,
                        shortcut=args.shortcut, no_cap=args.no_cap)
    print(narrate(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
