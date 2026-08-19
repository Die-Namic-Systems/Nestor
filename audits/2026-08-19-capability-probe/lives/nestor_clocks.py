#!/usr/bin/env python3
"""nestor_clocks.py — Yuki fixes Nestor, tracked in clocks.

Same seven issues as nestor_ladder.py.  Different system.  The flat d20
gives every outcome equal weight — a novice and an expert have the same
variance, just shifted by a modifier.  Dice pools compress the curve:
expertise means more dice, and more dice means more consistency.  Clocks
model iterative progress instead of pass/fail: you don't fix a matcher
in one roll, you fill a clock segment by segment, and the system tracks
how much the effort cost you.

The mechanics are Forged in the Dark: dice pools (Nd6, take highest;
0 dice = 2d6, take lowest), three-tier outcomes with crits, progress
clocks, position/effect, stress, and trauma.  The system was designed
for heist fiction, but heist fiction is just project management with
better lighting.

Yuki Tanaka, Wizard 3, INT 17 → 4d, WIS 14 → 3d, CHA 13 → 1d.
The mapping: ability score to pool size, proficiency adds a die,
expertise adds another.  Her INT pool is fat.  Her CHA pool is a
single die rolling desperate against an 8-segment clock.

The covenant holds: every outcome this script writes is DRAFT.
The machine can open the codebase.  It cannot ship the fix.

This work is based on Blades in the Dark (found at
http://www.bladesinthedark.com/), product of One Seven Design,
developed and authored by John Harper, and licensed for our use
under the Creative Commons Attribution 3.0 Unported license
(http://creativecommons.org/licenses/by/3.0/).

Usage:
    python3 nestor_clocks.py                # seed=42
    python3 nestor_clocks.py --seed 937
    python3 nestor_clocks.py --verbose
    python3 nestor_clocks.py --distribution 500
    python3 nestor_clocks.py --bargain       # take the devil's bargain
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass, field


# =========================================================================
# DICE POOL MECHANICS (Forged in the Dark SRD)
# =========================================================================

def roll_pool(n: int, rng: random.Random) -> dict:
    """Roll a dice pool.  n>0: roll n d6, take highest.
    n<=0: roll 2d6, take lowest (zero-dice rule)."""
    zero_dice = n <= 0
    count = 2 if zero_dice else n
    dice = [rng.randint(1, 6) for _ in range(count)]

    effective = min(dice) if zero_dice else max(dice)
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
    "limited":  {"critical": 2, "success": 1, "partial": 1, "failure": 0},
    "standard": {"critical": 3, "success": 2, "partial": 1, "failure": 0},
    "great":    {"critical": 5, "success": 3, "partial": 2, "failure": 0},
}

STRESS_TABLE = {
    "controlled": {"critical": 0, "success": 0, "partial": 0, "failure": 0},
    "risky":      {"critical": 0, "success": 0, "partial": 0, "failure": 1},
    "desperate":  {"critical": 0, "success": 0, "partial": 1, "failure": 2},
}

MAX_STRESS = 9
MAX_TRAUMA = 2
RECOVERY_PER_CLOCK = 1


# =========================================================================
# CHARACTER
# =========================================================================

@dataclass
class Operator:
    """A person working the clocks.  Pools degrade on trauma."""
    name: str
    base_pools: dict[str, int]
    stress: int = 0
    traumas: int = 0
    conditions: list[str] = field(default_factory=list)

    def pool(self, ability: str) -> int:
        return max(0, self.base_pools.get(ability, 0) - self.traumas)

    def take_stress(self, amount: int) -> str | None:
        if amount <= 0:
            return None
        self.stress += amount
        if self.stress >= MAX_STRESS:
            self.traumas += 1
            self.stress = 0
            return "broken" if self.traumas >= MAX_TRAUMA else "trauma"
        return None

    @property
    def broken(self) -> bool:
        return self.traumas >= MAX_TRAUMA

    def recover(self):
        if self.stress > 0 and not self.broken:
            self.stress = max(0, self.stress - RECOVERY_PER_CLOCK)


def make_yuki() -> Operator:
    """Yuki Tanaka — mapped from the d20 stat block to dice pools.

    INT 17 + proficiency + expertise → 4d.  She builds compilers in
    her spare time.  WIS 14 + proficiency → 3d.  She sees the pattern
    before the spreadsheet confirms it.  CHA 13, no proficiency → 1d.
    She can make the case once; she cannot make it twice.
    """
    return Operator(
        name="Yuki Tanaka",
        base_pools={"INT": 4, "WIS": 3, "CHA": 1},
    )


# =========================================================================
# CLOCKS — the same seven issues, measured in segments
# =========================================================================

@dataclass
class Clock:
    key: str
    title: str
    where: str
    segments: int
    ability: str
    position: str
    effect: str
    evidence: str

    completed: str
    half: str
    quarter: str
    empty: str

    requires: str = ""
    bargain: str = ""
    bargain_cost: str = ""


CLOCKS = [
    Clock(
        key="routing",
        title="The default routing sends queries to the wrong lane",
        where="nestor/cli.py:803-804",
        segments=4,
        ability="WIS", position="controlled", effect="standard",
        evidence=(
            "`nestor match 'data breaches'` searches 9 candidates (en→es) "
            "instead of 1230 (en→en). The CLI defaults to "
            "`--source-lang en --target-lang es`."
        ),
        completed=(
            "The default is gone. `match` and `ask` infer the lane from "
            "the store's contents — 1230 pairs en→en searched first. "
            "`nestor stats` shows which lanes exist and their sizes."
        ),
        half=(
            "A warning fires when the default lane has fewer than 10% "
            "of the store's pairs. The user sees 'searching 9 of 1369' "
            "and knows something's wrong. The default doesn't change."
        ),
        quarter=(
            "She found the bug — cli.py:803, source='en', target='es'. "
            "The fix is obvious. The patch is written but untested."
        ),
        empty="She looked at the code. The default is still en→es.",
    ),

    Clock(
        key="matcher",
        title="The StringMatcher can't bridge questions to claims",
        where="nestor/semantic_matcher.py, nestor/memory.py",
        segments=6,
        ability="INT", position="risky", effect="standard",
        requires="routing",
        evidence=(
            "'AI governance' scores 0.444 against a corpus about AI "
            "governance. 'data breaches' scores 0.385 against 'Largest "
            "data breaches 2025-2026'. The matcher requires near-verbatim "
            "text — it cannot bridge a question to a claim."
        ),
        completed=(
            "SemanticMatcher is the shipped default when an embedding "
            "model is available. StringMatcher remains as the zero-dep "
            "fallback. The serve bar recalibrates per matcher via "
            "`nestor calibrate --matcher`. Query expansion is not "
            "needed — the embedding space handles synonymy."
        ),
        half=(
            "Query normalization improved — stop words stripped, "
            "stemming applied. 'data breaches' climbs from 0.385 to "
            "~0.55. Still lexical, still can't bridge a question to "
            "a claim, but less fragile."
        ),
        quarter=(
            "She understood why the matcher fails — it is ratio-based, "
            "not meaning-based. She documented the gap and the seam "
            "that already exists (docs/matcher-seam.md)."
        ),
        empty="'AI governance' still scores 0.444.",
        bargain=(
            "Ship SemanticMatcher without recalibrating the serve bar. "
            "+1d. The path opens immediately."
        ),
        bargain_cost=(
            "Cosine similarity runs 0.0-1.0 on a different distribution "
            "than StringMatcher's ratio. The 0.92 bar either serves "
            "garbage or serves nothing."
        ),
    ),

    Clock(
        key="governance_graph",
        title="The governance graph is structurally empty",
        where="docs/dogfood/nestor.db — 0 edges, 0 rejections, 0 evidence",
        segments=6,
        ability="WIS", position="risky", effect="standard",
        requires="matcher",
        evidence=(
            "451 decisions, 0 edges, 0 rejections, 0 evidence. "
            "`decision check` always returns 'clear' — not because "
            "nothing contradicts, but because nobody recorded one."
        ),
        completed=(
            "`nestor decision edge` writes draft edges. The UI shows "
            "edges in the graph view. `decision check` can block "
            "proposals that contradict an edge. The ceremony has teeth."
        ),
        half=(
            "A script walks the decision files and flags overlapping "
            "concepts as candidate edges. The output is a list. "
            "Nobody's wired it into the daily workflow yet."
        ),
        quarter=(
            "She counted: 451 decisions, 0 edges. She named why "
            "`decision check` always returns 'clear' — the gate is "
            "open because nobody has ever built a wall."
        ),
        empty="The graph stays empty. Every check returns 'clear'.",
    ),

    Clock(
        key="seal_gap",
        title="Nothing is sealed — the ceremony has never been exercised",
        where="docs/dogfood/nestor.db — 451 draft, 0 sealed",
        segments=8,
        ability="CHA", position="desperate", effect="limited",
        requires="governance_graph",
        evidence=(
            "451 product decisions, all draft. 1230 knowledge pairs "
            "unreachable through `nestor ask` because `ask` requires "
            "sealed status. The tool's strongest content is invisible "
            "to its own serve path."
        ),
        completed=(
            "Twenty decisions are sealed — the reversals (0161, 0162), "
            "the CI gates (0124, 0131), the product boundary (0132, "
            "0134). `nestor ask` returns answers. `decision check` "
            "blocks contradictions. The ceremony is proven sustainable."
        ),
        half=(
            "A triage list exists: the ten highest-value unsealed "
            "decisions, ranked by query frequency and edge count. "
            "The list is ready. No human has sat down to seal them."
        ),
        quarter=(
            "She made the case — wrote the criteria, identified the "
            "decisions that matter most, drafted the argument. "
            "Nobody's heard it yet."
        ),
        empty=(
            "451 draft, 0 sealed. The tool that insists 'you may "
            "propose, you may not confirm' has never had anything "
            "confirmed."
        ),
        bargain=(
            "Auto-seal the ten most-queried pairs with verifier="
            "'machine'. +1d. The serve path opens immediately."
        ),
        bargain_cost=(
            "The covenant is violated by the tool designed to enforce "
            "it. 'You may propose, you may not confirm' — and the "
            "machine just confirmed."
        ),
    ),

    Clock(
        key="cross_domain",
        title="No cross-domain search between stores",
        where="docs/dogfood/nestor.db vs data/nestor-demo.db",
        segments=8,
        ability="INT", position="risky", effect="standard",
        requires="matcher",
        evidence=(
            "Product decisions and research claims live in separate "
            "databases with no bridge. A question about 'AI governance' "
            "can't surface both the product decision that gates it and "
            "the research claim that grounds it."
        ),
        completed=(
            "`--stores` flag on `match`/`ask` accepts comma-separated "
            "database paths. Results interleaved by score, tagged by "
            "origin store. One query, both domains."
        ),
        half=(
            "A wrapper script searches both stores sequentially. "
            "No ranking, no interleaving, but both domains visible "
            "in one terminal command."
        ),
        quarter=(
            "She mapped the schema overlap between the two stores. "
            "She knows decision_evidence could bridge them."
        ),
        empty="The stores remain islands.",
    ),

    Clock(
        key="policy_duplication",
        title="'Do not duplicate policy' is stated six times",
        where="CLAUDE.md, AGENTS.md, docs/agent-guide.md, hooks/seat.md",
        segments=4,
        ability="WIS", position="controlled", effect="standard",
        evidence=(
            "'You may propose, you may not confirm' appears in six "
            "files, each slightly different. The instruction 'do not "
            "duplicate policy here — it drifts' is itself duplicated."
        ),
        completed=(
            "CLAUDE.md and AGENTS.md become pointers only. Policy text "
            "lives in docs/agent-guide.md and hooks/seat.md — the "
            "runtime surface. Two sources, not six."
        ),
        half=(
            "Each duplicate is marked with a comment pointing to the "
            "canonical source. The duplication is acknowledged but "
            "not removed."
        ),
        quarter=(
            "She counted: six files, six slightly different phrasings "
            "of the same rule."
        ),
        empty="Each file drifts independently.",
    ),

    Clock(
        key="verifier_policy",
        title="No per-domain verifier policy",
        where="nestor/memory.py — add_pair accepts any verifier string",
        segments=6,
        ability="INT", position="risky", effect="standard",
        requires="seal_gap",
        evidence=(
            "`add_pair(status='sealed', verifier='anybody-at-all')` is "
            "accepted. The covenant says 'you may not confirm' but the "
            "code doesn't enforce WHO may."
        ),
        completed=(
            "An allow-list in the store's metadata table. `add_pair` "
            "rejects unknown verifier strings. Sealed means a "
            "registered human reviewed it."
        ),
        half=(
            "A warning fires on unrecognized verifiers. The seal goes "
            "through but the log notes it. Cosmetic enforcement."
        ),
        quarter=(
            "She read memory.py: any string passes as a verifier. "
            "She documented the gap between the covenant and the code."
        ),
        empty="Any string is accepted. The field is cosmetic.",
    ),
]

CLOCKS_BY_KEY = {c.key: c for c in CLOCKS}

MAX_ROLLS_PER_CLOCK = 30


# =========================================================================
# THE SCORE
# =========================================================================

def run_score(seed: int, *, verbose: bool = False,
              bargain: bool = False) -> dict:
    """Yuki works the clocks.  The dice decide how far she gets."""
    rng = random.Random(seed)
    yuki = make_yuki()
    completed_keys: set[str] = set()
    bargains_taken: list[str] = []
    log: list[dict] = []

    for clock in CLOCKS:
        if yuki.broken:
            log.append({"clock": clock, "skipped": True,
                        "reason": "broken — she walked away"})
            continue

        if clock.requires and clock.requires not in completed_keys:
            req = CLOCKS_BY_KEY[clock.requires]
            log.append({"clock": clock, "skipped": True,
                        "reason": f"needs [{req.title}]"})
            continue

        filled = 0
        rolls: list[dict] = []
        took_bargain = bargain and bool(clock.bargain)
        if took_bargain:
            bargains_taken.append(clock.key)
        bonus = 1 if took_bargain else 0

        for roll_num in range(MAX_ROLLS_PER_CLOCK):
            if yuki.broken or filled >= clock.segments:
                break

            pool_size = yuki.pool(clock.ability) + bonus
            result = roll_pool(pool_size, rng)
            ticks = TICKS[clock.effect][result["result"]]
            stress_cost = STRESS_TABLE[clock.position][result["result"]]

            filled = min(filled + ticks, clock.segments)
            trauma_event = yuki.take_stress(stress_cost)

            if trauma_event == "trauma":
                condition = (
                    "the covenant feels hollow"
                    if clock.key == "seal_gap"
                    else f"the cost of {clock.key} shows"
                )
                yuki.conditions.append(condition)

            rolls.append({
                "roll": roll_num + 1,
                "pool": pool_size,
                "dice": result["dice"],
                "effective": result["effective"],
                "result": result["result"],
                "ticks": ticks,
                "filled": filled,
                "segments": clock.segments,
                "stress_cost": stress_cost,
                "stress": yuki.stress,
                "traumas": yuki.traumas,
                "trauma_event": trauma_event,
            })

            if trauma_event == "broken":
                break

        pct = filled / clock.segments
        if pct >= 1.0:
            level = "completed"
            completed_keys.add(clock.key)
        elif pct >= 0.5:
            level = "half"
        elif pct > 0:
            level = "quarter"
        else:
            level = "empty"

        description = getattr(clock, level)

        log.append({
            "clock": clock,
            "rolls": rolls,
            "filled": filled,
            "segments": clock.segments,
            "pct": pct,
            "level": level,
            "description": description,
            "bargain": took_bargain,
        })

        yuki.recover()

        if verbose and not log[-1].get("skipped"):
            _print_verbose(log[-1], yuki)

    return {
        "seed": seed,
        "completed": completed_keys,
        "total": len(CLOCKS),
        "stress": yuki.stress,
        "traumas": yuki.traumas,
        "conditions": list(yuki.conditions),
        "bargains": bargains_taken,
        "log": log,
    }


def _print_verbose(entry: dict, yuki: Operator) -> None:
    clock = entry["clock"]
    base = yuki.base_pools.get(clock.ability, 0)
    effective = yuki.pool(clock.ability)
    print()
    print("─" * 60)
    print(f"  {clock.title}")
    print(f"  {clock.where}")
    deg = "" if base == effective else f" (was {base}d)"
    barg = " +1d bargain" if entry.get("bargain") else ""
    print(f"  {clock.ability} {effective}d{deg}{barg}, "
          f"{clock.position}, {clock.effect}")
    print(f"  Clock: {clock.segments} segments")
    print()
    for r in entry["rolls"]:
        bar = _bar(r["filled"], r["segments"])
        extras = []
        if r["stress_cost"]:
            extras.append(f"stress {r['stress']}/{MAX_STRESS}")
        if r["trauma_event"] == "trauma":
            extras.append("TRAUMA — stress clears, pools degrade")
        elif r["trauma_event"] == "broken":
            extras.append("BROKEN — she walks away")
        extra = "  " + ", ".join(extras) if extras else ""
        dice_str = ",".join(str(d) for d in r["dice"])
        print(f"    {r['roll']:>2}. {r['pool']}d→[{dice_str}] "
              f"eff={r['effective']} {r['result']:<8} "
              f"+{r['ticks']} {bar}{extra}")
    print()
    print(f"  {entry['level'].upper()}: "
          f"{entry['description'][:200]}")


# =========================================================================
# NARRATIVE
# =========================================================================

def narrate(result: dict) -> str:
    lines: list[str] = []
    lines.append("=" * 64)
    lines.append("  NESTOR CLOCKS — Yuki Tanaka works the system")
    lines.append(f"  Seed: {result['seed']}    System: Forged in the Dark")
    if result["bargains"]:
        lines.append(f"  Bargains taken: {', '.join(result['bargains'])}")
    lines.append("=" * 64)
    lines.append("")
    lines.append("The d20 says: one roll, pass or fail, move on.")
    lines.append("The clock says: progress is incremental, setbacks")
    lines.append("accumulate, and the hardest problem is not the code.")
    lines.append("")

    for entry in result["log"]:
        clock = entry["clock"]

        if entry.get("skipped"):
            lines.append(f"  ⊘ SKIPPED: {clock.title}")
            lines.append(f"    ({entry['reason']})")
            lines.append("")
            continue

        lines.append("─" * 64)
        lines.append(f"  {clock.title}")
        lines.append(f"  {clock.where}")
        lines.append(f"  {clock.ability}, {clock.position}, "
                      f"{clock.effect} effect")
        bar = _bar(entry["filled"], entry["segments"])
        lines.append(f"  Clock: {bar} {entry['filled']}/{entry['segments']}")
        if entry.get("bargain"):
            lines.append(f"  Devil's bargain: {clock.bargain}")
        lines.append("")

        lines.append("  Evidence:")
        for wl in _wrap(clock.evidence, 56):
            lines.append(f"    {wl}")
        lines.append("")

        for r in entry["rolls"]:
            extras = []
            if r["stress_cost"]:
                extras.append(f"stress {r['stress']}/{MAX_STRESS}")
            if r["trauma_event"] == "trauma":
                extras.append("TRAUMA")
            elif r["trauma_event"] == "broken":
                extras.append("BROKEN")
            extra = "  " + ", ".join(extras) if extras else ""
            dice_str = ",".join(str(d) for d in r["dice"])
            bar_r = _bar(r["filled"], r["segments"])
            lines.append(
                f"    {r['roll']:>2}. {r['pool']}d→[{dice_str}] "
                f"eff={r['effective']} {r['result']:<8} "
                f"+{r['ticks']} {bar_r}{extra}"
            )

        lines.append("")
        lines.append(f"  {entry['level'].upper()}:")
        for wl in _wrap(entry["description"], 56):
            lines.append(f"    {wl}")
        lines.append("")

    # — Destination state —
    completed = len(result["completed"])
    total = result["total"]
    traumas = result["traumas"]

    lines.append("=" * 64)
    lines.append("  DESTINATION STATE")
    lines.append("=" * 64)
    lines.append("")

    if completed == total:
        lines.append("  Every clock filled. Every segment ticked.")
        lines.append("  The tool finds its own decisions. The graph has")
        lines.append("  edges. The ceremony has been exercised.")
        lines.append("  The stores talk to each other.")
        lines.append("  The policy lives in one place.")
        lines.append("  The verifier registry means 'sealed' means")
        lines.append("  something.")
        lines.append("")
        if traumas:
            lines.append(f"  Cost: {traumas} trauma.")
            for c in result["conditions"]:
                lines.append(f"    — {c}")
            lines.append("  The system works. She is different.")
        else:
            lines.append("  No trauma. Every roll landed.")
        if result["bargains"]:
            lines.append("")
            lines.append("  But she took the bargain.")
            for b in result["bargains"]:
                clock = CLOCKS_BY_KEY[b]
                lines.append(f"    {clock.bargain_cost}")
    else:
        partial_entries = [
            e for e in result["log"]
            if not e.get("skipped") and e.get("level") != "completed"
        ]
        skipped_entries = [e for e in result["log"] if e.get("skipped")]

        lines.append(f"  {completed}/{total} clocks filled.")
        if traumas:
            lines.append(f"  {traumas} trauma{'s' if traumas > 1 else ''}.")
            for c in result["conditions"]:
                lines.append(f"    — {c}")
        lines.append("")
        if partial_entries:
            for pe in partial_entries:
                bar = _bar(pe["filled"], pe["segments"])
                lines.append(
                    f"  {pe['clock'].title[:50]}")
                lines.append(
                    f"    {bar} {pe['filled']}/{pe['segments']}")
            lines.append("")
        if skipped_entries:
            for se in skipped_entries:
                lines.append(f"  ⊘ {se['clock'].title}")
            lines.append("")

        if completed >= total - 2:
            lines.append("  Most of the system works. The gaps that remain")
            lines.append("  are the ones that require a human, not a coder.")
        else:
            lines.append("  The clocks show exactly how far she got")
            lines.append("  and where she stopped.")

    lines.append("")
    lines.append("  Covenant: everything above is DRAFT.")
    lines.append("  The machine can open the codebase.")
    lines.append("  It cannot ship the fix.")
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

def distribution(n: int, *, bargain: bool = False) -> None:
    from collections import Counter

    completion_hist: Counter[int] = Counter()
    clock_pcts: dict[str, list[float]] = {c.key: [] for c in CLOCKS}
    clock_rolls: dict[str, list[int]] = {c.key: [] for c in CLOCKS}
    trauma_hist: Counter[int] = Counter()

    for seed in range(n):
        result = run_score(seed, bargain=bargain)
        completion_hist[len(result["completed"])] += 1
        trauma_hist[result["traumas"]] += 1

        for entry in result["log"]:
            k = entry["clock"].key
            if entry.get("skipped"):
                clock_pcts[k].append(0.0)
                clock_rolls[k].append(0)
            else:
                clock_pcts[k].append(entry["pct"])
                clock_rolls[k].append(len(entry["rolls"]))

    label = " (with bargains)" if bargain else ""
    print(f"\nDistribution over {n} seeds — Forged in the Dark{label}")
    print("=" * 70)

    full = completion_hist.get(len(CLOCKS), 0)
    print(f"\nFull solve rate (7/7): {full}/{n} ({100 * full / n:.1f}%)")

    print(f"\nClocks completed:")
    for k in range(len(CLOCKS) + 1):
        count = completion_hist.get(k, 0)
        pct = 100 * count / n
        bar_len = int(40 * count / n)
        print(f"  {k}/7: {count:>5} ({pct:>5.1f}%) {'█' * bar_len}")

    print(f"\nTrauma distribution:")
    for t in range(MAX_TRAUMA + 1):
        count = trauma_hist.get(t, 0)
        print(f"  {t}: {count:>5} ({100 * count / n:>5.1f}%)")

    print(f"\n{'Clock':<42} {'Avg%':>5} {'100%':>5} "
          f"{'≥50%':>5} {'=0%':>5} {'Avg rolls':>9}")
    print("─" * 75)
    for clock in CLOCKS:
        pcts = clock_pcts[clock.key]
        rs = clock_rolls[clock.key]
        avg_pct = sum(pcts) / len(pcts) if pcts else 0
        full_c = sum(1 for p in pcts if p >= 1.0)
        half_c = sum(1 for p in pcts if p >= 0.5)
        zero_c = sum(1 for p in pcts if p == 0)
        avg_r = sum(rs) / len(rs) if rs else 0
        print(f"  {clock.title[:40]:<41} {100 * avg_pct:>4.0f}% "
              f"{full_c:>5} {half_c:>5} {zero_c:>5} {avg_r:>8.1f}")
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
    ap.add_argument("--bargain", action="store_true",
                    help="take devil's bargains on clocks that offer them")
    ap.add_argument("--distribution", type=int, metavar="N",
                    help="run N seeds and report statistics")
    args = ap.parse_args()

    if args.distribution:
        distribution(args.distribution, bargain=args.bargain)
        return 0

    result = run_score(args.seed, verbose=args.verbose,
                       bargain=args.bargain)
    print(narrate(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
