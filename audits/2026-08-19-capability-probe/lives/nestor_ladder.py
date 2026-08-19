#!/usr/bin/env python3
"""nestor_ladder.py — Yuki fixes Nestor.

A document ladder where the documents are not files in a safe but
real issues in a real codebase.  Each rung is a problem this tool
actually has, surfaced by running Nestor against itself on
2026-08-19.  The ability checks determine how completely each one
gets solved.  The destination state — the FULL or CRITICAL outcome
on every rung — is the spec for what Nestor looks like when it works.

Uses the same mechanics as compound.py: SRD 5.1 ability checks with
degrees of success (CRITICAL / FULL / PARTIAL / FAIL / BOTCH), the
same Character stat block, the same heat model.

Yuki Tanaka, Wizard 3 (School of Divination), INT 17, WIS 14.
Stanford CS + Comparative Literature.  Left a PM job because she
couldn't explain what she did without a slide deck.  Now she's
looking at a tool that can't find its own decisions by name and
thinking: I have seen this problem before.  It was the slide deck.

The covenant holds: every outcome this script writes is DRAFT.
The machine can open the codebase.  It cannot ship the fix.

Rules content derived from the System Reference Document 5.1,
copyright Wizards of the Coast, LLC., licensed under the
Creative Commons Attribution 4.0 International License.
https://dnd.wizards.com/resources/systems-reference-document

Usage:
    python3 nestor_ladder.py                # seed=42
    python3 nestor_ladder.py --seed 7
    python3 nestor_ladder.py --verbose
    python3 nestor_ladder.py --distribution 500
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from resolution import Character, modifier, roll_d20

# =========================================================================
# CHARACTER
# =========================================================================

def make_yuki() -> Character:
    """Yuki Tanaka — Wizard 3 (School of Divination).

    The same stat block as resolution.py.  INT 17 because the reflex
    that wakes her at 2 AM to run the numbers one more time is real.
    WIS 14 because she sees the truth she doesn't want to see.
    CON 10 because the body pays for both.
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
        max_hp=14,
        features=["portent", "arcane_recovery"],
    )


# =========================================================================
# DEGREES OF SUCCESS (same as compound.py)
# =========================================================================

CRIT = "critical"
FULL = "full"
PARTIAL = "partial"
FAIL = "fail"
BOTCH = "botch"

LABEL = {
    CRIT: "CRITICAL", FULL: "FULL", PARTIAL: "PARTIAL",
    FAIL: "FAIL", BOTCH: "BOTCH",
}


def ability_check(
    char: Character, ability: str, dc: int, rng: random.Random,
    proficient: bool = False, expertise: bool = False,
) -> dict:
    """SRD 5.1 ability check with degrees of success."""
    roll = roll_d20(rng)
    mod = char.mod(ability)
    if proficient:
        mod += char.proficiency_bonus * (2 if expertise else 1)
    total = roll + mod

    if roll == 20 or total >= dc + 10:
        degree = CRIT
    elif total >= dc + 5:
        degree = FULL
    elif total >= dc:
        degree = PARTIAL
    elif roll == 1 or total <= dc - 5:
        degree = BOTCH
    else:
        degree = FAIL

    return {"roll": roll, "mod": mod, "total": total, "dc": dc,
            "degree": degree}


# =========================================================================
# THE ISSUES — each one is a real problem, surfaced 2026-08-19
# =========================================================================

@dataclass
class Issue:
    key: str
    title: str
    where: str
    ability: str
    dc: int
    skill: str
    heat: int

    # What running Nestor against itself actually showed
    evidence: str

    # Degrees of resolution — what "solved" looks like at each level
    critical: str    # nat 20 or DC+10: solved and improved beyond the ask
    full: str        # DC+5: solved cleanly
    partial: str     # DC: the obvious fix, but not the structural one
    fail: str        # below DC: nothing changes
    botch: str       # nat 1 or DC-5: the fix makes it worse

    requires: str = ""


ISSUES = [
    Issue(
        key="routing",
        title="The default routing sends queries to the wrong lane",
        where="nestor/cli.py:803-804",
        ability="WIS", dc=10,
        skill="Perception — seeing what's obvious in the code",
        heat=0,
        evidence=(
            "`nestor match 'data breaches'` searches 9 candidates (en→es) "
            "instead of 1230 (en→en). The CLI defaults to "
            "`--source-lang en --target-lang es`. A user who doesn't know "
            "to pass `--from en --to en` will never reach the knowledge corpus."
        ),
        critical=(
            "The default is removed entirely. `match` and `ask` infer the "
            "lane from the store's contents — if 1230 pairs are en→en and "
            "9 are en→es, a bare query searches the large lane first. "
            "The `--from`/`--to` flags become overrides, not requirements. "
            "A `nestor stats` line shows which lanes exist and their sizes "
            "so the user knows what they're querying."
        ),
        full=(
            "The default changes from en→es to en→en for `match` and `ask`. "
            "The `decision` subcommand already defaults to decision→decision "
            "and doesn't break. Translation users pass `--from`/`--to` "
            "explicitly — they already knew to."
        ),
        partial=(
            "A warning is added when the default lane has fewer than 10% "
            "of the store's pairs. The user sees 'searching 9 of 1369 pairs "
            "— pass --from en --to en for the larger lane' and knows to "
            "retry. The default doesn't change."
        ),
        fail="The default stays en→es. Nobody notices until the next person asks.",
        botch=(
            "The default changes, but the flag names change too, and every "
            "script that passed `--from`/`--to` explicitly now breaks. "
            "Three CI pipelines fail, and the fix requires a deprecation cycle."
        ),
    ),

    Issue(
        key="matcher",
        title="The StringMatcher can't bridge questions to claims",
        where="nestor/semantic_matcher.py, nestor/memory.py",
        ability="INT", dc=14,
        skill="Investigation — understanding why the matcher fails",
        heat=1,
        evidence=(
            "'AI governance' scores 0.444 against a corpus about AI governance. "
            "'data breaches' scores 0.385 against 'Largest data breaches 2025-2026'. "
            "The matcher requires near-verbatim text. It cannot bridge from "
            "a question to a claim unless the question IS the claim."
        ),
        requires="routing",
        critical=(
            "A SemanticMatcher backed by sentence embeddings replaces "
            "StringMatcher as the default when an embedding model is "
            "available. StringMatcher remains as the zero-dependency "
            "fallback. The matcher-seam interface (docs/matcher-seam.md) "
            "already exists — both implement `Matcher`. The serve bar "
            "recalibrates per matcher: 0.92 was right for StringMatcher's "
            "scale; a cosine-similarity matcher needs its own `nestor "
            "calibrate` pass. Query expansion is not needed — the embedding "
            "space handles synonymy naturally."
        ),
        full=(
            "SemanticMatcher is promoted from optional to the shipped default. "
            "`pip install nestor[semantic]` installs sentence-transformers. "
            "The calibrate command gains a `--matcher` flag. The bar is "
            "re-derived for the new matcher's score distribution."
        ),
        partial=(
            "Query normalization is improved — strip stop words, stem, "
            "handle the→/a→ elision. Gets 'data breaches' from 0.385 to "
            "maybe 0.55. Still lexical, still can't bridge 'who controls "
            "AI infrastructure' to a claim about AI infrastructure control."
        ),
        fail=(
            "The matcher stays lexical. Every user learns to search by "
            "copying text they already found. The tool's strongest content "
            "remains invisible to its own query interface."
        ),
        botch=(
            "An embedding model is added but the serve bar isn't recalibrated. "
            "Cosine similarity runs 0.0-1.0 on a different distribution than "
            "StringMatcher's ratio. The 0.92 bar either serves garbage (too "
            "low for cosine) or serves nothing (too high). Worse than before "
            "because now it looks like it should work."
        ),
    ),

    Issue(
        key="governance_graph",
        title="The governance graph is structurally empty",
        where="docs/dogfood/nestor.db — 0 edges, 0 rejections, 0 evidence",
        ability="WIS", dc=13,
        skill="Insight — understanding what the empty store means",
        heat=0,
        evidence=(
            "451 decisions, 0 edges, 0 rejections, 0 evidence, 0 sealed. "
            "`decision check` looks for rejections and contradicts edges "
            "to block a proposal. With no edges and no rejections, every "
            "check returns 'clear'. The gate is open not because nothing "
            "contradicts, but because nobody has ever recorded a contradiction."
        ),
        requires="matcher",
        critical=(
            "A `nestor decision audit` command walks the store and proposes "
            "edges: 'decision 0127 (the read-only probe was not read-only) "
            "CONTRADICTS decision 0125 (the gate proof does not inherit a "
            "receipt)' — because if the probe wasn't read-only, the gate "
            "proof it generated is suspect. The audit proposes edges as "
            "DRAFT. A human reviews them in `nestor ui` and seals the real "
            "ones. `decision check` then has teeth: it can block a proposal "
            "that contradicts a sealed edge."
        ),
        full=(
            "Edge proposal is manual but supported: `nestor decision edge "
            "0127 contradicts 0125 --reason \"...\"` writes a draft edge. "
            "The UI shows edges in the graph view (which already exists — "
            "decision 0137). Edges appear in `decision check` output. "
            "The ceremony exists; someone has to do the work."
        ),
        partial=(
            "A script walks the decision files and flags pairs with "
            "overlapping keywords. It produces a list of candidate edges "
            "on stdout. Nobody wires it into the workflow, and it runs once."
        ),
        fail=(
            "The graph stays empty. Every `decision check` returns 'clear'. "
            "The covenant depends on data structures that have never been "
            "populated. The governance model is a valid design running on "
            "an unpopulated store."
        ),
        botch=(
            "Edges are auto-generated and auto-sealed by a script that runs "
            "on commit. The covenant — 'you may propose, you may not confirm' "
            "— is violated by the tool designed to enforce it. A machine "
            "sealed its own contradictions."
        ),
    ),

    Issue(
        key="seal_gap",
        title="Nothing is sealed — the ceremony has never been exercised",
        where="docs/dogfood/nestor.db — 451 draft, 0 sealed",
        ability="CHA", dc=15,
        skill="Persuasion — convincing a human to sit down and do this",
        heat=0,
        evidence=(
            "The dogfood store has 451 product decisions, all draft. "
            "The research corpus has 1369 pairs, 8 sealed — all translations "
            "and entity aliases. The 1230 knowledge pairs are unreachable "
            "through `nestor ask` because `ask` requires sealed status. "
            "The tool's strongest content is invisible to its own serve path."
        ),
        requires="governance_graph",
        critical=(
            "A triage workflow in `nestor ui` presents the highest-value "
            "unsealed pairs first — the ones most queried, most cited in "
            "edges, or most contradicted. The human seals ten in one sitting, "
            "and the serve path opens. A weekly `nestor due-for-reverification` "
            "cron (scripts/due_for_reverification.py already exists) surfaces "
            "stale seals. The ceremony is lightweight enough to sustain."
        ),
        full=(
            "The human seals the product decisions that matter most — the "
            "ones that came from reversals (0161, 0162), the ones that gate "
            "CI (0124, 0131), the ones that define the product boundary "
            "(0132, 0134). Maybe twenty out of 451. `nestor ask` starts "
            "returning answers. `decision check` starts blocking proposals "
            "that contradict sealed decisions."
        ),
        partial=(
            "One or two decisions get sealed as a proof of concept. The "
            "serve path opens for those specific queries. The other 449 "
            "remain draft. The ceremony is proven possible but not practiced."
        ),
        fail=(
            "Nobody seals anything. The ceremony remains theoretical. "
            "The tool that insists 'you may propose, you may not confirm' "
            "has never had anything confirmed."
        ),
        botch=(
            "A bulk-seal script runs and marks all 451 decisions as sealed "
            "with a machine verifier. The covenant is destroyed. Sealed now "
            "means nothing, because sealed was never meant to mean 'a machine "
            "said so'. The entire verification model collapses, and the bar "
            "that was supposed to protect the serve path protects nothing."
        ),
    ),

    Issue(
        key="cross_domain",
        title="No cross-domain search between stores",
        where="docs/dogfood/nestor.db vs data/nestor-demo.db — separate databases",
        ability="INT", dc=16,
        skill="Arcana — systems architecture for knowledge that spans domains",
        heat=2,
        evidence=(
            "The dogfood store (product decisions) and the research corpus "
            "(knowledge claims) are separate databases with no bridge. "
            "A question about 'AI governance' can't surface both the product "
            "decision that gates it and the research claim that grounds it. "
            "Nestor has no way to say 'decision 0155 is about the same thing "
            "as the corpus entry on EU AI governance frameworks'."
        ),
        requires="matcher",
        critical=(
            "A federated query mode: `nestor ask --stores dogfood,research "
            "\"AI governance\"` searches both stores and returns results "
            "ranked by relevance, tagged by origin. Cross-store edges: "
            "a decision can cite a corpus entry as evidence, and the corpus "
            "entry links back. The evidence table (decision_evidence, "
            "currently 0 rows in dogfood) becomes the bridge. Evidence "
            "rows can reference pairs in other stores by store+id."
        ),
        full=(
            "A `--stores` flag on `match`/`ask` accepts a comma-separated "
            "list of database paths. Results are interleaved by score. "
            "No cross-store edges yet, but the user can see both domains "
            "in one query."
        ),
        partial=(
            "A wrapper script searches both stores sequentially and prints "
            "combined output. No ranking, no interleaving, no edge support. "
            "Better than nothing; not a product feature."
        ),
        fail=(
            "The stores remain islands. The dogfood decisions don't know "
            "the research exists. The research doesn't know the product "
            "decisions exist. The tool that built both can't search both."
        ),
        botch=(
            "A merge script combines both stores into one database, losing "
            "the domain separation that made them useful. Product decisions "
            "and research claims share a namespace. `decision check` starts "
            "matching against corpus entries instead of product decisions, "
            "and the governance model becomes confused about what it governs."
        ),
    ),

    Issue(
        key="policy_duplication",
        title="'Do not duplicate policy' is stated six times",
        where="CLAUDE.md, AGENTS.md, docs/agent-guide.md, hooks/seat.md",
        ability="WIS", dc=12,
        skill="Insight — seeing that the instruction to not duplicate is itself duplicated",
        heat=0,
        evidence=(
            "The covenant rule — 'you may propose, you may not confirm' — "
            "appears in CLAUDE.md, AGENTS.md, docs/agent-guide.md, hooks/seat.md, "
            "hooks/session_start.py, and hooks/before_propose.py. Each instance "
            "drifts slightly from the others. The instruction 'do not duplicate "
            "policy here — it drifts' is itself stated in multiple places."
        ),
        critical=(
            "One canonical file: `docs/agent-guide.md`. Every other reference "
            "is a one-line pointer — 'see docs/agent-guide.md' — with no "
            "restated policy. The hooks import from the guide's machine-readable "
            "section rather than hardcoding the rules. A `scripts/ci-docs.sh` "
            "check verifies that no other file contains a restated policy "
            "(the check already exists but doesn't cover this). When the "
            "policy changes, it changes in one place."
        ),
        full=(
            "CLAUDE.md and AGENTS.md become pointers only. The policy text "
            "lives in `docs/agent-guide.md` and `hooks/seat.md` (the runtime "
            "surface). Two sources instead of six. Drift is still possible "
            "but the surface area is manageable."
        ),
        partial=(
            "A comment is added to each duplicate: '# canonical: docs/agent-guide.md'. "
            "The duplication is acknowledged but not removed. When someone "
            "updates one, they know to update the other."
        ),
        fail=(
            "The duplication persists. Each file drifts independently. "
            "An agent reads whichever file it encounters first and follows "
            "that version of the rules."
        ),
        botch=(
            "The consolidation removes the hooks' inline rules but doesn't "
            "update the import path. The hooks now reference a file they "
            "can't read at runtime, and the gate stops firing. The governance "
            "ceremony is silently disabled by the cleanup that was supposed "
            "to improve it."
        ),
    ),

    Issue(
        key="verifier_policy",
        title="No per-domain verifier policy",
        where="nestor/memory.py — add_pair accepts any verifier string",
        ability="INT", dc=15,
        skill="Investigation — understanding what the verifier field means",
        heat=1,
        evidence=(
            "`add_pair(status='sealed', verifier='anybody-at-all')` is "
            "accepted. The covenant says 'you may not confirm' but the code "
            "doesn't enforce WHO may. There is no allow-list, no role check, "
            "no domain-scoped verifier registry."
        ),
        requires="seal_gap",
        critical=(
            "A verifier registry: `nestor keys add-verifier rudi193@gmail.com "
            "--domain decision` registers a human verifier for a domain. "
            "`add_pair(status='sealed', verifier='somebody-else')` is "
            "rejected if that verifier isn't registered for the domain. "
            "The keyring (nestor/keyring.py) already handles Ed25519 keys — "
            "the verifier registry is the same pattern for identity. "
            "Seal signatures bind the verifier to the pair cryptographically."
        ),
        full=(
            "An allow-list in the store's metadata table: only listed "
            "verifier strings are accepted for sealed status. The check is "
            "in `add_pair`, not in the hooks. Trying to seal with an "
            "unknown verifier raises `NestorError`."
        ),
        partial=(
            "A warning is emitted when an unrecognized verifier is used. "
            "The seal still goes through. The warning shows up in the "
            "session log but doesn't block."
        ),
        fail=(
            "Any string is accepted as a verifier. The field is cosmetic. "
            "The covenant is enforced by social convention and hooks, not "
            "by the data layer."
        ),
        botch=(
            "A verifier check is added but the existing sealed pairs "
            "(the 8 translations/entities) used a verifier string that "
            "isn't in the new registry. The only sealed content in the "
            "system is retroactively invalidated. `nestor ask` returns "
            "nothing for any query, because nothing passes the new check."
        ),
    ),
]

ISSUES_BY_KEY = {i.key: i for i in ISSUES}


# =========================================================================
# THE LADDER
# =========================================================================

MAX_ATTEMPTS = 3
HEAT_ABORT = 8


def run_ladder(seed: int, verbose: bool = False) -> dict:
    """Yuki works the issues. The dice decide how far she gets."""
    rng = random.Random(seed)
    yuki = make_yuki()

    heat = 0
    solved = {}
    log = []
    aborted = False

    for issue in ISSUES:
        if aborted:
            log.append({"issue": issue, "skipped": True,
                        "reason": "heat abort — she's been noticed"})
            continue

        if issue.requires and issue.requires not in solved:
            log.append({"issue": issue, "skipped": True,
                        "reason": f"needs [{ISSUES_BY_KEY[issue.requires].title}]"})
            continue

        best_degree = FAIL
        attempts = []

        for attempt in range(MAX_ATTEMPTS):
            check = ability_check(
                yuki, issue.ability, issue.dc, rng,
                proficient=(issue.ability in ("INT", "WIS")),
                expertise=(issue.ability == "INT"),
            )
            deg = check["degree"]

            if attempt > 0:
                heat += 1

            if deg == BOTCH:
                heat += issue.heat

            attempts.append({
                "attempt": attempt + 1,
                "roll": check["roll"],
                "mod": check["mod"],
                "total": check["total"],
                "dc": check["dc"],
                "degree": LABEL[deg],
            })

            if deg in (CRIT, FULL):
                best_degree = deg
                break
            if deg == PARTIAL and best_degree in (FAIL, BOTCH):
                best_degree = PARTIAL
                break
            if deg == BOTCH:
                best_degree = BOTCH
                break

            best_degree = FAIL

        resolution = getattr(issue, best_degree if best_degree != BOTCH else "botch")
        solved_level = best_degree if best_degree in (CRIT, FULL, PARTIAL) else None
        if solved_level:
            solved[issue.key] = solved_level

        entry = {
            "issue": issue,
            "attempts": attempts,
            "degree": LABEL[best_degree],
            "resolution": resolution,
            "heat_after": heat,
        }
        log.append(entry)

        if heat >= HEAT_ABORT:
            aborted = True

        if verbose:
            print()
            hdr = f"{'─' * 60}"
            print(hdr)
            print(f"  {issue.title}")
            print(f"  {issue.where}")
            print(f"  Check: {issue.ability} (DC {issue.dc}) — {issue.skill}")
            print(hdr)
            print(f"  Evidence: {issue.evidence[:120]}...")
            for a in attempts:
                print(f"    Attempt {a['attempt']}: d20={a['roll']} + {a['mod']} = "
                      f"{a['total']} vs DC {a['dc']} → {a['degree']}")
            print(f"  Result: {LABEL[best_degree]}")
            print(f"  {resolution[:200]}...")
            if heat > 0:
                print(f"  Heat: {heat}/{HEAT_ABORT}")

    return {
        "seed": seed,
        "solved": solved,
        "heat": heat,
        "aborted": aborted,
        "log": log,
    }


# =========================================================================
# NARRATIVE OUTPUT
# =========================================================================

def narrate(result: dict) -> str:
    """The story of what Yuki did."""
    lines = []
    lines.append("=" * 64)
    lines.append("  NESTOR LADDER — Yuki Tanaka fixes the system")
    lines.append(f"  Seed: {result['seed']}")
    lines.append("=" * 64)
    lines.append("")
    lines.append("She left a $160K PM job because she couldn't explain what")
    lines.append("she did without a slide deck. Now she's looking at a tool")
    lines.append("that can't find its own decisions by name and thinking:")
    lines.append("I have seen this problem before. It was the slide deck.")
    lines.append("")

    full_count = sum(1 for v in result["solved"].values() if v in (CRIT, FULL))
    partial_count = sum(1 for v in result["solved"].values() if v == PARTIAL)
    total = len(ISSUES)
    skipped = sum(1 for e in result["log"] if e.get("skipped"))
    failed = total - full_count - partial_count - skipped

    for entry in result["log"]:
        issue = entry["issue"]

        if entry.get("skipped"):
            lines.append(f"  ⊘ SKIPPED: {issue.title}")
            lines.append(f"    ({entry['reason']})")
            lines.append("")
            continue

        lines.append("─" * 64)
        lines.append(f"  {issue.title}")
        lines.append(f"  {issue.where}")
        lines.append(f"  {issue.ability} DC {issue.dc} — {issue.skill}")
        lines.append("")
        lines.append(f"  What she found:")
        for wrap_line in _wrap(issue.evidence, 56):
            lines.append(f"    {wrap_line}")
        lines.append("")

        for a in entry["attempts"]:
            lines.append(f"    Attempt {a['attempt']}: "
                         f"d20({a['roll']}) + {a['mod']} = {a['total']} "
                         f"vs DC {a['dc']} → {a['degree']}")

        lines.append("")
        lines.append(f"  Outcome: {entry['degree']}")
        for wrap_line in _wrap(entry["resolution"], 56):
            lines.append(f"    {wrap_line}")
        lines.append("")

        if entry["heat_after"] > 0:
            lines.append(f"  [Heat: {entry['heat_after']}/{HEAT_ABORT}]")
            lines.append("")

    lines.append("=" * 64)
    lines.append("  DESTINATION STATE")
    lines.append("=" * 64)
    lines.append("")

    if full_count == total:
        lines.append("  She solved everything. Every issue, every rung.")
        lines.append("  The tool finds its own decisions. The graph has edges.")
        lines.append("  The ceremony has been exercised. The stores talk to")
        lines.append("  each other. The policy lives in one place.")
        lines.append("  The verifier registry means 'sealed' means something.")
        lines.append("")
        lines.append("  This is what Nestor looks like when it works.")
        lines.append("  A human still has to seal it.")
    elif full_count + partial_count == total:
        lines.append("  She fixed everything — some of it cleanly, some of")
        lines.append("  it with duct tape. The partial fixes are better than")
        lines.append("  what was there. They're also not the structural fix.")
        lines.append("  Someone will have to come back.")
    elif full_count > 0:
        lines.append(f"  {full_count} solved cleanly. {partial_count} patched.")
        lines.append(f"  {failed} unchanged. {skipped} never reached.")
        lines.append("  The tool is better than it was. It is not done.")
    else:
        lines.append("  The dice were unkind. The issues remain.")
        lines.append("  The tool still can't find its own decisions.")
        lines.append("  But the issues are named now, and naming is the")
        lines.append("  first thing that matters.")

    lines.append("")
    lines.append("  Covenant: everything above is DRAFT.")
    lines.append("  The machine can open the codebase. It cannot ship the fix.")
    lines.append("  A human still has to sit down and do this.")
    lines.append("")

    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    return lines


# =========================================================================
# DISTRIBUTION MODE
# =========================================================================

def distribution(n: int) -> None:
    """Run N seeds and report how often each issue reaches each degree."""
    from collections import Counter
    counts: dict[str, Counter] = {i.key: Counter() for i in ISSUES}
    full_runs = 0

    for seed in range(n):
        result = run_ladder(seed)
        all_solved = True
        for entry in result["log"]:
            issue = entry["issue"]
            if entry.get("skipped"):
                counts[issue.key]["SKIPPED"] += 1
                all_solved = False
            else:
                counts[issue.key][entry["degree"]] += 1
                if entry["degree"] not in ("CRITICAL", "FULL"):
                    all_solved = False
        if all_solved:
            full_runs += 1

    print(f"\nDistribution over {n} seeds:")
    print(f"Full solve rate: {full_runs}/{n} ({100*full_runs/n:.1f}%)\n")
    print(f"{'Issue':<45} {'CRIT':>5} {'FULL':>5} {'PART':>5} "
          f"{'FAIL':>5} {'BOTCH':>5} {'SKIP':>5}")
    print("─" * 80)
    for issue in ISSUES:
        c = counts[issue.key]
        print(f"{issue.title[:44]:<45} "
              f"{c.get('CRITICAL',0):>5} "
              f"{c.get('FULL',0):>5} "
              f"{c.get('PARTIAL',0):>5} "
              f"{c.get('FAIL',0):>5} "
              f"{c.get('BOTCH',0):>5} "
              f"{c.get('SKIPPED',0):>5}")
    print()


# =========================================================================
# MAIN
# =========================================================================

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--distribution", type=int, metavar="N",
                    help="run N seeds and report degree distribution")
    args = ap.parse_args()

    if args.distribution:
        distribution(args.distribution)
        return 0

    result = run_ladder(args.seed, verbose=args.verbose)
    print(narrate(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
