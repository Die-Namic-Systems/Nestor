#!/usr/bin/env python3
"""humans_in_offices.py — Yuki fixes Nestor, no fantasy.

Same seven issues.  Same dice pools.  Same clocks.  Same math.
Different names.  The wizard became a staff engineer.  The ability
scores became job skills.  The dungeon became an office.  The dragon
became an approval form nobody uses.

The point: the statistical truth — 11.2% full solve without the
shortcut, 79.4% with it — doesn't change when you swap the costume.
The system literally works better if you violate the rule the system
exists to enforce.  That sentence reads the same in chainmail and
in business casual.

Stats:
    Analysis  (4d) — reading code, understanding systems.
    Awareness (3d) — seeing what's actually happening.
    Buy-In    (1d) — getting a human to commit to action.

Position:
    Scheduled   — planned work, on the sprint, expected.
    Ad-hoc      — unplanned, squeezing it in, might get pushback.
    Unbudgeted  — no time allocated, no mandate, pure persuasion.

Effect:
    Mentioned — it came up, people nodded, nobody committed.
    Assigned  — someone owns it, there's a ticket.
    Mandated  — executive backing, deadline set.

Stress  → Burnout (9 capacity).
Trauma  → Disillusionment (first) / Resignation (second).

Dice pool mechanics based on Blades in the Dark by John Harper,
licensed under CC BY 3.0 Unported.
http://www.bladesinthedark.com/

Usage:
    python3 humans_in_offices.py                # seed=42
    python3 humans_in_offices.py --seed 937
    python3 humans_in_offices.py --verbose
    python3 humans_in_offices.py --distribution 500
    python3 humans_in_offices.py --shortcut      # take the shortcut
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass, field


# =========================================================================
# RESOLUTION MECHANICS
# =========================================================================

def roll_pool(n: int, rng: random.Random) -> dict:
    """Roll a dice pool.  n>0: roll n d6, take highest.
    n<=0: roll 2d6, take lowest."""
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

BURNOUT = {
    "scheduled":   {"critical": 0, "success": 0, "partial": 0, "failure": 0},
    "ad-hoc":      {"critical": 0, "success": 0, "partial": 0, "failure": 1},
    "unbudgeted":  {"critical": 0, "success": 0, "partial": 1, "failure": 2},
}

MAX_BURNOUT = 9
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
    """A person working the backlog."""
    name: str
    title: str
    base_skills: dict[str, int]
    burnout: int = 0
    disillusionments: int = 0
    conditions: list[str] = field(default_factory=list)

    def skill(self, name: str) -> int:
        return max(0, self.base_skills.get(name, 0) - self.disillusionments)

    def take_burnout(self, amount: int) -> str | None:
        if amount <= 0:
            return None
        self.burnout += amount
        if self.burnout >= MAX_BURNOUT:
            self.disillusionments += 1
            self.burnout = 0
            if self.disillusionments >= MAX_DISILLUSION:
                return "resigned"
            return "disillusioned"
        return None

    @property
    def resigned(self) -> bool:
        return self.disillusionments >= MAX_DISILLUSION

    def coffee_break(self):
        if self.burnout > 0 and not self.resigned:
            self.burnout = max(0, self.burnout - COFFEE_BREAK)


def make_yuki() -> Employee:
    """Yuki Tanaka, Staff Software Engineer, Tools & Infrastructure.

    Analysis 4d — she reads code in her sleep and the code is usually
    right.  Awareness 3d — she sees the pattern before the dashboard
    confirms it.  Buy-In 1d — she can make the case once; she cannot
    make them care.
    """
    return Employee(
        name="Yuki Tanaka",
        title="Staff Software Engineer, Tools & Infrastructure",
        base_skills={"analysis": 4, "awareness": 3, "buy-in": 1},
    )


# =========================================================================
# THE BACKLOG — seven items, each tracked as a progress bar
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
            "instead of 1230. The default was set during the prototype "
            "and nobody revisited it."
        ),
        completed=(
            "The default is removed. The CLI infers the dataset from "
            "the store's contents. `nestor stats` shows which datasets "
            "exist and their sizes."
        ),
        half=(
            "A warning fires when the default dataset is suspiciously "
            "small. The user sees 'searching 9 of 1369' and knows to "
            "switch. The default doesn't change."
        ),
        quarter=(
            "She found the line — cli.py:803, source='en', target='es'. "
            "She wrote the patch. She hasn't tested the edge cases."
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
            "governance. The search engine uses string matching. It "
            "cannot bridge a question to a claim unless the question "
            "IS the claim, verbatim."
        ),
        completed=(
            "Semantic search is the default when an embedding model is "
            "available. String matching stays as the zero-dependency "
            "fallback. The relevance threshold recalibrates per search "
            "method via `nestor calibrate --matcher`."
        ),
        half=(
            "Query normalization improved — stop words stripped, "
            "stemming applied. Scores climb from 0.385 to ~0.55. "
            "Still string-based, but less fragile."
        ),
        quarter=(
            "She understood the failure — the search is ratio-based, "
            "not meaning-based. She documented the gap and the seam "
            "that already exists for swapping the engine."
        ),
        empty="The search engine still requires exact phrasing.",
        shortcut=(
            "Ship the new search engine without recalibrating the "
            "relevance threshold. +1d. The feature launches immediately."
        ),
        shortcut_cost=(
            "The threshold was tuned for string matching. The new "
            "engine's scores are on a different scale. It either "
            "returns garbage or returns nothing."
        ),
    ),

    Item(
        key="governance_graph",
        title="The approval workflow has no blocking rules",
        where="docs/dogfood/nestor.db — 0 edges, 0 rejections, 0 evidence",
        segments=6,
        skill="awareness", position="ad-hoc", effect="assigned",
        requires="matcher",
        obstacle="The Org Chart With No Lines",
        evidence=(
            "451 decisions on file, 0 relationships between them. "
            "The 'check for conflicts' command always returns 'clear' "
            "— not because nothing conflicts, but because nobody ever "
            "recorded a conflict."
        ),
        completed=(
            "The CLI writes draft relationships between decisions. The "
            "UI shows them in the graph view. The conflict checker can "
            "actually block a proposal that contradicts an existing "
            "decision. The process has teeth."
        ),
        half=(
            "A script scans the decision files and flags overlapping "
            "concepts as candidate relationships. The output is a list. "
            "Nobody's wired it into the daily workflow."
        ),
        quarter=(
            "She counted: 451 decisions, 0 relationships. She named "
            "why the conflict checker always returns 'clear' — the "
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
            "451 product decisions on file, all marked 'draft'. The "
            "tool's serve path requires 'approved' status. The 1230 "
            "knowledge entries are unreachable because nobody has ever "
            "sat down, read one, and clicked 'approve'."
        ),
        completed=(
            "Twenty decisions are approved — the reversals, the CI "
            "gates, the product boundary definitions. The serve path "
            "returns answers. The conflict checker blocks proposals "
            "that contradict approved decisions. The process works."
        ),
        half=(
            "A triage list exists: the ten highest-value unapproved "
            "decisions, ranked by query frequency. The list is ready. "
            "It's in the team lead's inbox. They haven't opened it."
        ),
        quarter=(
            "She wrote the triage criteria, identified the decisions "
            "that matter most, drafted the memo. Nobody's read it."
        ),
        empty=(
            "451 draft, 0 approved. The tool that insists 'a human "
            "must approve' has never had a human approve anything."
        ),
        shortcut=(
            "Run the auto-approval script. The forms get stamped. "
            "+1d. The dashboard turns green immediately."
        ),
        shortcut_cost=(
            "The approval field now says 'machine' where it should "
            "say a person's name. The rule 'a human must approve' is "
            "violated by the system designed to enforce it."
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
            "Product decisions and research findings live in separate "
            "databases. A search for 'AI governance' can't surface "
            "both the product decision that gates it and the research "
            "finding that grounds it."
        ),
        completed=(
            "A `--stores` flag searches multiple databases in one "
            "query. Results are interleaved by relevance, tagged by "
            "source. One search, both datasets."
        ),
        half=(
            "A wrapper script searches both databases sequentially. "
            "No ranking, no interleaving, but both datasets visible "
            "in one command."
        ),
        quarter=(
            "She mapped the schema overlap. She knows which table "
            "could bridge them."
        ),
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
            "The core rule — 'a human must approve' — appears in six "
            "files, each phrased slightly differently. The instruction "
            "'do not duplicate this policy — it drifts' is itself "
            "duplicated in three of them."
        ),
        completed=(
            "Two files are the source of truth. The other four contain "
            "a one-line pointer. When the policy changes, it changes "
            "in one place."
        ),
        half=(
            "Each copy is marked with a comment pointing to the "
            "canonical source. The duplication is acknowledged."
        ),
        quarter=(
            "She counted: six files, six slightly different phrasings."
        ),
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
            "The approval function accepts any string as the approver's "
            "name. There is no employee list, no role check, no "
            "verification that the signer exists."
        ),
        completed=(
            "An allow-list in the database. The approval function "
            "rejects names not on the list. 'Approved' means a "
            "registered employee reviewed it."
        ),
        half=(
            "A warning fires on unrecognized names. The approval goes "
            "through but the log flags it."
        ),
        quarter=(
            "She read the code: any string passes as an approver. "
            "She documented the gap between the policy and the code."
        ),
        empty="Any name is accepted. The field is cosmetic.",
    ),
]

BACKLOG_BY_KEY = {item.key: item for item in BACKLOG}

MAX_ROLLS = 30


# =========================================================================
# THE SPRINT
# =========================================================================

def run_sprint(seed: int, *, verbose: bool = False,
               shortcut: bool = False) -> dict:
    """Yuki works the backlog.  The dice decide how far she gets."""
    rng = random.Random(seed)
    yuki = make_yuki()
    done: set[str] = set()
    shortcuts_taken: list[str] = []
    log: list[dict] = []

    for item in BACKLOG:
        if yuki.resigned:
            log.append({"item": item, "skipped": True,
                        "reason": "resigned"})
            continue

        if item.requires and item.requires not in done:
            req = BACKLOG_BY_KEY[item.requires]
            log.append({"item": item, "skipped": True,
                        "reason": f"blocked on [{req.title}]"})
            continue

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
            burn = BURNOUT[item.position][result["result"]]

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
        })

        yuki.coffee_break()

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
        "log": log,
    }


def _verbose(entry: dict, emp: Employee) -> None:
    item = entry["item"]
    base = emp.base_skills.get(item.skill, 0)
    eff = emp.skill(item.skill)
    print()
    print("─" * 60)
    print(f"  {item.title}")
    print(f"  {item.where}")
    deg = "" if base == eff else f" (was {base}d)"
    sc = " +1d shortcut" if entry.get("shortcut") else ""
    print(f"  {item.skill} {eff}d{deg}{sc}, "
          f"{item.position}, {item.effect}")
    print(f"  Obstacle: {item.obstacle}")
    print(f"  Progress: {item.segments} segments")
    print()
    for r in entry["rolls"]:
        bar = _bar(r["filled"], r["segments"])
        extras = []
        if r["burn"]:
            extras.append(f"burnout {r['burnout']}/{MAX_BURNOUT}")
        if r["event"] == "disillusioned":
            extras.append("DISILLUSIONED — burnout clears, skills degrade")
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
    lines.append("  HUMANS IN OFFICES")
    lines.append("  A project tracker, seven items, one engineer")
    lines.append(f"  Seed: {result['seed']}")
    if result["shortcuts"]:
        lines.append(f"  Shortcuts taken: {', '.join(result['shortcuts'])}")
    lines.append("=" * 64)
    lines.append("")
    lines.append("Yuki Tanaka joined Infrastructure three months ago.")
    lines.append("She was told the governance tooling 'basically works.'")
    lines.append("She opened the database, ran the queries the docs said")
    lines.append("to run, and discovered that 'basically works' means")
    lines.append("'nobody has tested the parts that require a human.'")
    lines.append("")
    lines.append("She has seven items on her tech debt tracker.")
    lines.append("Her manager says the sprint is full.")
    lines.append("")

    for entry in result["log"]:
        item = entry["item"]

        if entry.get("skipped"):
            lines.append(f"  — BLOCKED: {item.title}")
            lines.append(f"    ({entry['reason']})")
            lines.append("")
            continue

        lines.append("─" * 64)
        lines.append(f"  {item.title}")
        lines.append(f"  {item.where}")
        lines.append(f"  Skill: {item.skill}  |  "
                      f"Priority: {item.position}  |  "
                      f"Scope: {item.effect}")
        bar = _bar(entry["filled"], entry["segments"])
        lines.append(f"  Progress: {bar} {entry['filled']}/{entry['segments']}")
        lines.append(f"  Obstacle: {item.obstacle}")
        if entry.get("shortcut"):
            lines.append(f"  Shortcut: {item.shortcut}")
        lines.append("")

        lines.append("  What she found:")
        for wl in _wrap(item.evidence, 56):
            lines.append(f"    {wl}")
        lines.append("")

        for r in entry["rolls"]:
            extras = []
            if r["burn"]:
                extras.append(f"burnout {r['burnout']}/{MAX_BURNOUT}")
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
        lines.append("  All items closed.")
        lines.append("  The search works. The approval graph has edges.")
        lines.append("  Twenty decisions are approved. The databases")
        lines.append("  talk to each other. The policy lives in two")
        lines.append("  files, not six. The sign-off field rejects")
        lines.append("  fake names.")
        lines.append("")
        if dis:
            lines.append(f"  Cost: {dis} disillusionment{'s' if dis > 1 else ''}.")
            for c in result["conditions"]:
                lines.append(f"    — {c}")
            lines.append("  The system works. She is tired.")
        else:
            lines.append("  No burnout. Everything landed.")
        if result["shortcuts"]:
            lines.append("")
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
                lines.append(f"  — Blocked: {be['item'].title}")
            lines.append("")

        if completed >= total - 2:
            lines.append("  Most of the system works. The items that")
            lines.append("  remain require a human, not an engineer.")
        else:
            lines.append("  The progress bars show how far she got.")
            lines.append("  The empty ones show where she stopped.")

    lines.append("")
    lines.append("  Everything above is a draft.")
    lines.append("  The engineer can open the codebase.")
    lines.append("  She cannot approve her own work.")
    lines.append("  Someone has to sit down and do this.")
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

def distribution(n: int, *, shortcut: bool = False) -> None:
    from collections import Counter

    completion_hist: Counter[int] = Counter()
    item_pcts: dict[str, list[float]] = {i.key: [] for i in BACKLOG}
    item_rolls: dict[str, list[int]] = {i.key: [] for i in BACKLOG}
    dis_hist: Counter[int] = Counter()

    for seed in range(n):
        result = run_sprint(seed, shortcut=shortcut)
        completion_hist[len(result["done"])] += 1
        dis_hist[result["disillusionments"]] += 1

        for entry in result["log"]:
            k = entry["item"].key
            if entry.get("skipped"):
                item_pcts[k].append(0.0)
                item_rolls[k].append(0)
            else:
                item_pcts[k].append(entry["pct"])
                item_rolls[k].append(len(entry["rolls"]))

    label = " (with shortcuts)" if shortcut else ""
    print(f"\nDistribution over {n} seeds — Humans in Offices{label}")
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

    print(f"\n{'Item':<42} {'Avg%':>5} {'Done':>5} "
          f"{'≥50%':>5} {'=0%':>5} {'Avg effort':>10}")
    print("─" * 75)
    for item in BACKLOG:
        pcts = item_pcts[item.key]
        rs = item_rolls[item.key]
        avg_pct = sum(pcts) / len(pcts) if pcts else 0
        done_c = sum(1 for p in pcts if p >= 1.0)
        half_c = sum(1 for p in pcts if p >= 0.5)
        zero_c = sum(1 for p in pcts if p == 0)
        avg_r = sum(rs) / len(rs) if rs else 0
        print(f"  {item.title[:40]:<41} {100 * avg_pct:>4.0f}% "
              f"{done_c:>5} {half_c:>5} {zero_c:>5} {avg_r:>9.1f}")
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
    args = ap.parse_args()

    if args.distribution:
        distribution(args.distribution, shortcut=args.shortcut)
        return 0

    result = run_sprint(args.seed, verbose=args.verbose,
                        shortcut=args.shortcut)
    print(narrate(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
