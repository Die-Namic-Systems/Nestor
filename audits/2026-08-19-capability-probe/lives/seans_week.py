#!/usr/bin/env python3
"""seans_week.py — the Monte Carlo planner, run against a real life.

Twelve matters.  Real deadlines.  Real dependencies.  Real constraints.
The person doing the work has a herniated disc, a workers' comp case,
two girls, an ex-wife who is helpful and boundaried, $227/week in TTD,
a foreclosure sale in two days, and a Schmidt grant application pending.

This is not a game.  The dice model uncertainty: whether someone picks
up the phone, whether the queue moves, whether the back cooperates,
whether a child gets sick, whether Jessi's "working on something"
arrives by Thursday afternoon.

The engine finds the seeds where the most matters advance, reads them
backward, and reports what had to happen in what order.

Stats:
    Research   (4d) — he built a 49-file database from scratch in 72 hours.
    Persuasion (2d) — he can explain the case.  The back limits the hours.
    Endurance  (1d) — TTD, two kids, a body that screams at the desk.

Dice pool mechanics based on Blades in the Dark by John Harper,
licensed under CC BY 3.0 Unported.
http://www.bladesinthedark.com/

Usage:
    python3 seans_week.py                # seed=42
    python3 seans_week.py --seed 937
    python3 seans_week.py --distribution 1000
    python3 seans_week.py --best 1000
    python3 seans_week.py --shortcut
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass, field


# =========================================================================
# RESOLUTION (same engine, same odds)
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

COST_TABLE = {
    "scheduled":   {"critical": 0, "success": 0, "partial": 0, "failure": 0},
    "ad-hoc":      {"critical": 0, "success": 0, "partial": 0, "failure": 1},
    "unbudgeted":  {"critical": 0, "success": 0, "partial": 1, "failure": 2},
}

MAX_BURN = 7           # the back takes 2 of the 9
MAX_COLLAPSE = 2       # two collapses = can't continue
RECOVERY = 1           # per completed matter

RESULT_LABELS = {
    "critical": "breakthrough",
    "success":  "done",
    "partial":  "progress",
    "failure":  "nothing",
}


# =========================================================================
# THE PERSON
# =========================================================================

@dataclass
class Sean:
    name: str = "Sean Campbell"
    skills: dict[str, int] = field(default_factory=lambda: {
        "research": 4,    # he built a 49-file database in 72 hours
        "persuasion": 2,  # he can make the case, when the back lets him sit
        "endurance": 1,   # $227/week, two kids, a body that screams
    })
    burn: int = 0
    collapses: int = 0
    conditions: list[str] = field(default_factory=list)

    def skill(self, name: str) -> int:
        return max(0, self.skills.get(name, 0) - self.collapses)

    def take_burn(self, amount: int) -> str | None:
        if amount <= 0:
            return None
        self.burn += amount
        if self.burn >= MAX_BURN:
            self.collapses += 1
            self.burn = 0
            if self.collapses >= MAX_COLLAPSE:
                return "stopped"
            return "collapsed"
        return None

    def recover(self, amount: int):
        if not self.stopped:
            self.burn = max(0, self.burn - amount)

    @property
    def stopped(self) -> bool:
        return self.collapses >= MAX_COLLAPSE


# =========================================================================
# THE WEEK — what happens before each matter
# =========================================================================

LIFE_EVENTS = [
    {"roll": 1, "key": "back_bad",    "burn": 3,
     "text": "The L4-L5 is a 9 out of 10.  She can't sit, can't stand long, can't think through it.  The insurance appeal is still 'in review.'"},
    {"roll": 2, "key": "kid_sick",    "burn": 2,
     "text": "Ruby has a fever.  School called.  He picks her up, holds her on the couch, tries to read a brief one-handed."},
    {"roll": 3, "key": "bank_calls",  "burn": 2, "sale_tick": True,
     "text": "The bank called.  Not Tuesday, not Thursday — today.  Twenty-five minutes on a number he already knew."},
    {"roll": 4, "key": "car",         "burn": 2,
     "text": "The car won't start.  The mechanic said it was fine.  Uber to school, Uber to USBC — $47 on the card."},
    {"roll": 5, "key": "jessi_text",  "burn": 1,
     "text": "Jessi texts about the 529 allocation and the school transition meeting.  Forty minutes.  Both things matter."},
    {"roll": 6, "key": "opal_asks",   "burn": 1,
     "text": "Opal asks why they're putting things in boxes.  He doesn't have an answer that fits in a sentence."},
    {"roll": 7, "key": "back_ok",     "burn": 0,
     "text": "The back is a 4 out of 10.  Nobody called.  Both girls at school.  He has until 3:15."},
    {"roll": 8, "key": "comp_check",  "burn": 0,
     "text": "The TTD check cleared.  $227.16.  It covers groceries and gas.  Not the mortgage.  Not the move."},
    {"roll": 9, "key": "jessi_helps", "burn": -1,
     "text": "Jessi picks up both girls.  'You need to make your calls,' she says.  Five uninterrupted hours."},
    {"roll": 10, "key": "jessi_big",  "burn": -2,
     "text": "Jessi takes the girls for the weekend.  'Elena's got them.'  He sleeps nine hours.  The back is a 3 when he wakes up."},
]


def roll_life(rng: random.Random) -> dict:
    roll = rng.randint(1, len(LIFE_EVENTS))
    return LIFE_EVENTS[roll - 1]


# =========================================================================
# THE MATTERS — all twelve, modeled from the database
# =========================================================================

@dataclass
class Matter:
    key: str
    title: str
    slug: str
    urgency: int
    segments: int
    skill: str
    position: str
    effect: str
    what: str

    completed: str
    half: str
    quarter: str
    empty: str

    requires: str = ""
    shortcut: str = ""
    shortcut_cost: str = ""
    deadline: str = ""


MATTERS = [
    Matter(
        key="usbc", title="Get to United South Broadway today",
        slug="madeira", urgency=1, segments=4,
        skill="endurance", position="ad-hoc", effect="mandated",
        what="Walk in or call.  They have foreclosure attorneys.  Open until 5:30.",
        deadline="Today — they close at 5:30",
        completed="A foreclosure attorney is looking at the case.  Someone is standing up in court.",
        half="They took the intake.  A callback is promised.",
        quarter="He called.  The line was busy.  He'll try again or drive there.",
        empty="He didn't make the call.",
    ),

    Matter(
        key="planet", title="Call Planet — who actually services this loan?",
        slug="madeira", urgency=1, segments=4,
        skill="persuasion", position="ad-hoc", effect="assigned",
        what="Planet may be the current servicer.  HomeLoanServ says they have nothing.  Establish the chain.",
        completed="Planet confirmed they service the loan.  The application path is clear.",
        half="Planet took the call.  Transfer date is on the record.  File location unclear.",
        quarter="He reached a rep.  They're 'looking into it.'",
        empty="The call wasn't made.",
    ),

    Matter(
        key="reinstatement", title="Get the reinstatement mechanics — how does money stop the sale?",
        slug="madeira", urgency=1, segments=6,
        skill="research", position="ad-hoc", effect="assigned",
        requires="planet",
        what="Certified funds or wire?  To Planet or IDEA Law Group?  What's the cutoff hour?",
        completed="Written confirmation: amount, form, recipient, cutoff.  The path is clear if money appears.",
        half="Verbal answer on mechanics.  Nothing in writing yet.",
        quarter="He asked.  They said they'd get back to him.",
        empty="Nobody has asked how money physically stops the sale.",
    ),

    Matter(
        key="jessi_path", title="Jessi is 'working on something' — does money appear by Thursday?",
        slug="madeira", urgency=1, segments=8,
        skill="persuasion", position="unbudgeted", effect="mentioned",
        requires="reinstatement",
        what="She asked for the reinstatement figure.  She said 'give me some time.'  This is not a plan yet.",
        deadline="Thursday afternoon — the sale is Friday 10 AM",
        completed="Funds confirmed, logistics confirmed, sale stopped or stayed.",
        half="She has a source.  Amount and mechanics are agreed.  Execution pending.",
        quarter="She's working on it.  No amount confirmed.  No logistics.",
        empty="It was a possibility, not a plan.",
        shortcut="Assume the money will come and stop working other paths.  +1d.",
        shortcut_cost="If it doesn't come, Friday happens with nothing else in place.",
    ),

    Matter(
        key="ch13", title="Can a Chapter 13 stop the sale?",
        slug="bankruptcy", urgency=1, segments=6,
        skill="research", position="ad-hoc", effect="assigned",
        what="Prior dismissal count decides the stay.  Need a lawyer who files with nothing down.  Credit counseling first.",
        deadline="Thursday — the petition has to be on file BEFORE the sale",
        completed="A lawyer is filing.  Credit counseling done.  Petition going in Thursday.",
        half="A lawyer is identified.  Counseling not done yet.",
        quarter="He knows the law.  No lawyer, no counseling certificate.",
        empty="The option exists on paper.",
        shortcut="File pro se without a lawyer.  +1d.  The automatic stay fires either way.",
        shortcut_cost="A pro-se Chapter 13 with a prior dismissal and the 24-month question unanswered is a plan with no margin.",
    ),

    Matter(
        key="partial_claim", title="The FHA partial claim — does IHFA/Planet have an application?",
        slug="madeira", urgency=2, segments=6,
        skill="research", position="ad-hoc", effect="assigned",
        requires="planet",
        what="FHA-insured loan → partial claim possible.  HUD advances the arrearage as a zero-interest lien.  But does anyone have the application?",
        completed="Application confirmed on file.  Partial claim in process.  A decision is coming.",
        half="Application located.  Incomplete or needs resubmission.",
        quarter="He knows the path.  No confirmation the application exists.",
        empty="The partial claim path is described in the database but not confirmed with the servicer.",
    ),

    Matter(
        key="redemption", title="Read the mortgage — is redemption 1 month or 9?",
        slug="madeira", urgency=2, segments=4,
        skill="research", position="scheduled", effect="assigned",
        what="NMSA 39-5-18 says 9 months.  39-5-19 says it can be shortened to 1.  The mortgage decides.",
        completed="The mortgage is read.  The redemption period is known.  The timeline is real.",
        half="The mortgage is located but the clause hasn't been found.",
        quarter="He knows to look.  The document hasn't been opened.",
        empty="The single most consequential unknown after the 24-month question.",
    ),

    Matter(
        key="workerscomp", title="Workers' comp — the engine under everything",
        slug="workerscomp", urgency=2, segments=8,
        skill="persuasion", position="unbudgeted", effect="mentioned",
        what="TTD at $227/week, no AWW worksheet produced, 15 weeks retro unpaid.  The injury IS the foreclosure.",
        completed="AWW corrected.  Back pay issued.  The income picture changes.",
        half="The AWW question is raised with Sedgwick.  No answer yet.",
        quarter="He knows the number is wrong.  Nobody with authority has heard it.",
        empty="$227/week, and the math that produced it was never shown.",
    ),

    Matter(
        key="eeoc", title="ADA / EEOC charge — is the window still open?",
        slug="eeoc", urgency=2, segments=4,
        skill="research", position="scheduled", effect="assigned",
        what="Job ended while an accommodation request was pending.  180/300 day clock running.",
        deadline="Unknown — placeholder Sep 15",
        completed="Charge filed or adverse-action date confirmed with time to file.",
        half="Adverse-action date established.  Filing deadline known.",
        quarter="He knows the clock exists.  The date hasn't been established.",
        empty="Never checked.",
    ),

    Matter(
        key="portland", title="Portland — the move, on the numbers",
        slug="portland", urgency=2, segments=6,
        skill="research", position="scheduled", effect="assigned",
        what="Schools, IEP transfer, renting with a foreclosure, cost of living.  The Ivy School question.",
        completed="The Ivy School is confirmed open.  The IEP transfer plan is documented.  The rental path is clear.",
        half="The research is done.  The Ivy School closure question is unresolved.",
        quarter="The comparison exists in the database.  No calls made.",
        empty="He hasn't been able to do any research on where he's supposed to be moving.",
    ),

    Matter(
        key="kids", title="Ruby, Opal, and the week",
        slug="kids", urgency=1, segments=4,
        skill="endurance", position="scheduled", effect="mandated",
        what="Standing commitment.  Not a task list.  A witness, not a contest.",
        completed="The girls are where they need to be.  Someone else knows what tomorrow is.",
        half="One person knows the plan.  The documents are somewhere safe.",
        quarter="He's holding it together.  Barely.",
        empty="The week took the oxygen.",
    ),

    Matter(
        key="funding", title="The Schmidt application — waiting, not working",
        slug="funding", urgency=4, segments=4,
        skill="research", position="scheduled", effect="mentioned",
        what="Submitted Aug 5.  Ethan is the advisor.  One funder already said no.  This one is pending.",
        completed="A follow-up or a fiscal sponsor answer is on the record.",
        half="BERI or Ashgro responded.  The fiscal sponsor question is moving.",
        quarter="He checked email.  Nothing new.",
        empty="The application is filed.  The house is on fire.  He's not looking at this.",
    ),
]

MATTERS_BY_KEY = {m.key: m for m in MATTERS}

# Hard constraints
SALE_CLOCK_MAX = 4      # if the sale panic fills, everything stops
MAX_ROLLS_PER = 20      # max rolls per matter
DAYS_LEFT = 5           # matters he can attempt before the week is up


# =========================================================================
# THE WEEK
# =========================================================================

def run_week(seed: int, *, verbose: bool = False,
             shortcut: bool = False) -> dict:
    rng = random.Random(seed)
    sean = Sean()
    done: set[str] = set()
    shortcuts_taken: list[str] = []
    log: list[dict] = []
    sale_clock = 0
    items_attempted = 0

    for matter in MATTERS:
        if sean.stopped:
            log.append({"matter": matter, "skipped": True,
                        "reason": "stopped — the body said no"})
            continue

        if items_attempted >= DAYS_LEFT and matter.urgency > 1:
            log.append({"matter": matter, "skipped": True,
                        "reason": "the week ran out — urgency-1 only from here"})
            continue

        if sale_clock >= SALE_CLOCK_MAX:
            log.append({"matter": matter, "skipped": True,
                        "reason": "the sale consumed everything"})
            continue

        if matter.requires and matter.requires not in done:
            req = MATTERS_BY_KEY[matter.requires]
            log.append({"matter": matter, "skipped": True,
                        "reason": f"blocked on [{req.title}]"})
            continue

        # Life happens first
        life_ev = roll_life(rng)
        if life_ev["burn"] > 0:
            sean.take_burn(life_ev["burn"])
        elif life_ev["burn"] < 0:
            sean.recover(abs(life_ev["burn"]))

        if life_ev.get("sale_tick"):
            sale_clock = min(sale_clock + 1, SALE_CLOCK_MAX)

        if sean.stopped:
            log.append({"matter": matter, "skipped": True,
                        "reason": "stopped — life burned through the margin before work",
                        "life_event": life_ev})
            continue

        if sale_clock >= SALE_CLOCK_MAX:
            log.append({"matter": matter, "skipped": True,
                        "reason": "the sale consumed everything",
                        "life_event": life_ev})
            continue

        items_attempted += 1

        filled = 0
        rolls: list[dict] = []
        took_shortcut = shortcut and bool(matter.shortcut)
        if took_shortcut:
            shortcuts_taken.append(matter.key)
        bonus = 1 if took_shortcut else 0

        for roll_num in range(MAX_ROLLS_PER):
            if sean.stopped or filled >= matter.segments:
                break

            pool = sean.skill(matter.skill) + bonus
            result = roll_pool(pool, rng)
            ticks = TICKS[matter.effect][result["result"]]
            burn = COST_TABLE[matter.position][result["result"]]

            filled = min(filled + ticks, matter.segments)
            event = sean.take_burn(burn)

            if event == "collapsed":
                sean.conditions.append(f"collapsed on {matter.key}")

            rolls.append({
                "roll": roll_num + 1,
                "pool": pool,
                "dice": result["dice"],
                "effective": result["effective"],
                "result": result["result"],
                "label": RESULT_LABELS[result["result"]],
                "ticks": ticks,
                "filled": filled,
                "segments": matter.segments,
                "burn": burn,
                "burnout": sean.burn,
                "collapses": sean.collapses,
                "event": event,
            })

            if event == "stopped":
                break

        pct = filled / matter.segments
        if pct >= 1.0:
            level = "completed"
            done.add(matter.key)
        elif pct >= 0.5:
            level = "half"
        elif pct > 0:
            level = "quarter"
        else:
            level = "empty"

        log.append({
            "matter": matter,
            "rolls": rolls,
            "filled": filled,
            "segments": matter.segments,
            "pct": pct,
            "level": level,
            "description": getattr(matter, level),
            "shortcut": took_shortcut,
            "life_event": life_ev,
        })

        sean.recover(RECOVERY)

    return {
        "seed": seed,
        "done": done,
        "total": len(MATTERS),
        "burn": sean.burn,
        "collapses": sean.collapses,
        "conditions": list(sean.conditions),
        "shortcuts": shortcuts_taken,
        "sale_clock": sale_clock,
        "log": log,
    }


# =========================================================================
# NARRATION
# =========================================================================

def narrate(result: dict) -> str:
    lines: list[str] = []
    lines.append("=" * 64)
    lines.append("  SEAN'S WEEK")
    lines.append(f"  Seed: {result['seed']}")
    if result["shortcuts"]:
        lines.append(f"  Shortcuts: {', '.join(result['shortcuts'])}")
    lines.append("=" * 64)
    lines.append("")
    lines.append("Sean Campbell, Albuquerque, 19 August 2026.")
    lines.append("The foreclosure sale is Friday.")
    lines.append("")
    lines.append("What's on his desk:")
    lines.append("  - 12 matters in the database he built in 72 hours")
    lines.append("  - A herniated disc at L4-L5, 18 months, $15 desk riser")
    lines.append("  - A house on Madeira, sale set for Friday 10 AM")
    lines.append("  - Workers' comp at $227/week, no AWW worksheet produced")
    lines.append("  - Ruby and Opal")
    lines.append("  - Jessi, who texted at 8:41 asking for the number")
    lines.append("  - A Schmidt grant pending")
    lines.append("  - Legal Aid closed until September")
    lines.append("  - USBC open until 5:30")
    lines.append("")

    for entry in result["log"]:
        matter = entry["matter"]

        if entry.get("skipped"):
            lines.append(f"  -- BLOCKED: {matter.title}")
            lines.append(f"     ({entry['reason']})")
            lines.append("")
            continue

        life_ev = entry.get("life_event")
        if life_ev:
            lines.append(f"  Before work:")
            for wl in _wrap(life_ev["text"], 56):
                lines.append(f"    {wl}")
            burn = life_ev["burn"]
            if burn > 0:
                lines.append(f"    (burn +{burn})")
            elif burn < 0:
                lines.append(f"    (burn {burn})")
            lines.append("")

        lines.append("-" * 64)
        dl = f"  DEADLINE: {matter.deadline}" if matter.deadline else ""
        lines.append(f"  {matter.title}")
        if dl:
            lines.append(dl)
        lines.append(f"  Skill: {matter.skill}  |  "
                      f"Priority: {matter.position}  |  "
                      f"Scope: {matter.effect}")
        bar = _bar(entry["filled"], entry["segments"])
        lines.append(f"  Progress: {bar} {entry['filled']}/{entry['segments']}")
        lines.append("")

        for r in entry["rolls"]:
            extras = []
            if r["burn"]:
                extras.append(f"burn {r['burnout']}/{MAX_BURN}")
            if r["event"] == "collapsed":
                extras.append("COLLAPSED")
            elif r["event"] == "stopped":
                extras.append("STOPPED")
            extra = "  " + ", ".join(extras) if extras else ""
            dice_str = ",".join(str(d) for d in r["dice"])
            bar_r = _bar(r["filled"], r["segments"])
            lines.append(
                f"    {r['roll']:>2}. {r['pool']}d->[{dice_str}] "
                f"{r['label']:<12} +{r['ticks']} {bar_r}{extra}"
            )

        lines.append("")
        lines.append(f"  {entry['level'].upper()}: ", )
        for wl in _wrap(entry["description"], 56):
            lines.append(f"    {wl}")
        lines.append("")

    completed = len(result["done"])
    total = result["total"]

    lines.append("=" * 64)
    lines.append(f"  {completed}/{total} matters advanced.")
    if result["collapses"]:
        lines.append(f"  {result['collapses']} collapse(s).")
        for c in result["conditions"]:
            lines.append(f"    -- {c}")
    if result["shortcuts"]:
        lines.append("  Shortcuts taken:")
        for s in result["shortcuts"]:
            m = MATTERS_BY_KEY[s]
            for wl in _wrap(m.shortcut_cost, 56):
                lines.append(f"    {wl}")
    lines.append("=" * 64)
    lines.append("")
    lines.append("  Everything above is a draft.")
    lines.append("  The system can hold a life.")
    lines.append("  It cannot live one.")
    lines.append("")
    return "\n".join(lines)


def _bar(filled: int, segments: int) -> str:
    return "[" + "#" * filled + "." * (segments - filled) + "]"


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
# DISTRIBUTION + BEST-SEED FINDER
# =========================================================================

def distribution(n: int, *, shortcut: bool = False) -> None:
    from collections import Counter

    comp_hist: Counter[int] = Counter()
    matter_pcts: dict[str, list[float]] = {m.key: [] for m in MATTERS}
    collapse_hist: Counter[int] = Counter()
    life_counts: Counter[str] = Counter()
    best_seed = -1
    best_done = -1
    best_ties: list[int] = []

    for seed in range(n):
        result = run_week(seed, shortcut=shortcut)
        nd = len(result["done"])
        comp_hist[nd] += 1
        collapse_hist[result["collapses"]] += 1

        if nd > best_done:
            best_done = nd
            best_seed = seed
            best_ties = [seed]
        elif nd == best_done:
            best_ties.append(seed)

        for entry in result["log"]:
            k = entry["matter"].key
            if entry.get("skipped"):
                matter_pcts[k].append(0.0)
            else:
                matter_pcts[k].append(entry["pct"])

        for entry in result["log"]:
            le = entry.get("life_event")
            if le:
                life_counts[le["key"]] += 1

    label = " (with shortcuts)" if shortcut else ""
    print(f"\nDistribution over {n} seeds — Sean's Week{label}")
    print("=" * 70)

    full = comp_hist.get(len(MATTERS), 0)
    print(f"\nAll matters resolved: {full}/{n} ({100 * full / n:.1f}%)")
    print(f"Best seed: {best_seed} ({best_done}/{len(MATTERS)} matters)")
    print(f"Seeds tying at {best_done}: {len(best_ties)}")

    print(f"\nMatters completed:")
    for k in range(len(MATTERS) + 1):
        count = comp_hist.get(k, 0)
        pct = 100 * count / n
        bar_len = int(40 * count / n)
        print(f"  {k:>2}/{len(MATTERS)}: {count:>5} ({pct:>5.1f}%) "
              f"{'#' * bar_len}")

    print(f"\nCollapses:")
    for d in range(MAX_COLLAPSE + 1):
        count = collapse_hist.get(d, 0)
        print(f"  {d}: {count:>5} ({100 * count / n:>5.1f}%)")

    print(f"\nLife events ({sum(life_counts.values())} total):")
    for ev in LIFE_EVENTS:
        count = life_counts.get(ev["key"], 0)
        print(f"  {ev['key']:<14} {count:>5}  (burn {ev['burn']:+d})")

    print(f"\n{'Matter':<50} {'Avg%':>5} {'Done':>5} "
          f"{'>=50':>5} {'=0%':>5}")
    print("-" * 75)
    for m in MATTERS:
        pcts = matter_pcts[m.key]
        avg = sum(pcts) / len(pcts) if pcts else 0
        dc = sum(1 for p in pcts if p >= 1.0)
        hc = sum(1 for p in pcts if p >= 0.5)
        zc = sum(1 for p in pcts if p == 0)
        print(f"  {m.title[:48]:<49} {100 * avg:>4.0f}% "
              f"{dc:>5} {hc:>5} {zc:>5}")

    print()


def find_best(n: int, top: int = 5, *, shortcut: bool = False) -> None:
    results: list[tuple[int, int, set[str], list[str]]] = []

    for seed in range(n):
        result = run_week(seed, shortcut=shortcut)
        nd = len(result["done"])
        events = [
            e.get("life_event", {}).get("key", "?")
            for e in result["log"] if not e.get("skipped")
        ]
        results.append((nd, seed, result["done"], events))

    results.sort(key=lambda x: (-x[0], x[1]))

    label = " (with shortcuts)" if shortcut else ""
    print(f"\nTop {top} seeds out of {n} — Sean's Week{label}")
    print("=" * 70)

    for i, (nd, seed, done, events) in enumerate(results[:top]):
        print(f"\n  #{i+1}  Seed {seed}: {nd}/{len(MATTERS)} matters")
        print(f"       Done: {', '.join(sorted(done))}")
        print(f"       Life: {' -> '.join(events)}")
        not_done = set(m.key for m in MATTERS) - done
        if not_done:
            print(f"       Not done: {', '.join(sorted(not_done))}")

    print()

    # What do the top seeds have in common?
    top_n = results[:min(top * 5, len(results))]
    all_done = set.intersection(*(r[2] for r in top_n)) if top_n else set()
    never_done = set(m.key for m in MATTERS) - set.union(*(r[2] for r in top_n))

    print("Pattern in the best seeds:")
    if all_done:
        print(f"  Always done: {', '.join(sorted(all_done))}")
    if never_done:
        print(f"  Never done:  {', '.join(sorted(never_done))}")

    from collections import Counter
    event_freq: Counter[str] = Counter()
    for _, _, _, events in top_n:
        for e in events:
            event_freq[e] += 1
    print(f"  Life events in top {len(top_n)} seeds:")
    for ev, count in event_freq.most_common():
        pct = 100 * count / len(top_n)
        print(f"    {ev:<14} {count:>3} ({pct:.0f}%)")
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
                    help="take shortcuts where offered")
    ap.add_argument("--distribution", type=int, metavar="N",
                    help="run N seeds and report statistics")
    ap.add_argument("--best", type=int, metavar="N",
                    help="find the best seeds out of N runs")
    args = ap.parse_args()

    if args.distribution:
        distribution(args.distribution, shortcut=args.shortcut)
        return 0

    if args.best:
        find_best(args.best, shortcut=args.shortcut)
        return 0

    result = run_week(args.seed, verbose=args.verbose,
                      shortcut=args.shortcut)
    print(narrate(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
