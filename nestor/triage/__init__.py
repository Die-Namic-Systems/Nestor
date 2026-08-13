"""Decision triage — put the seal queue into groups before a human seals it.

The problem this solves, in the operator's words: there are 200+ draft decisions
to be sealed locally; starting oldest-first fails because many are already
resolved, superseded, or duplicated, and the store's own ``nestor decision
check`` is exact-wording only, so a re-worded resolution reads as "clear". A
human should seal **coherent groups**, told which rows are already answered —
not a flat list, blind.

This package is the assembly the fleet survey said already had all its parts
(``the-house-already-knew.md`` in action): the clustering **shape** is
willow-mcp's ``nest/selflearn``, the scoring bar is the ``docs/decision-rewording
-bench.md`` N1 knee (~0.45, where re-worded resolutions are recovered with zero
false constraints), the refutation stance is Jeles' ``conflict_scan`` ("search
for what refutes, not what resembles"), and the sink is ``nestor.decision``'s
``propose_edge``. Nothing here is invented; it is those shapes re-landed.

Hard constraints, enforced by the tests and true of every module here:

* **Stdlib only, offline.** No numpy / sklearn / networkx (none are installed;
  the core is dependency-light on purpose) and no embeddings (the environment
  cannot reach huggingface/ollama). Scoring rides ``nestor.matcher`` — the same
  character/token matchers the store already uses.
* **Seals nothing.** The output is groups and *proposed* edges. Writing to a
  store goes through ``DecisionMemory.propose_edge`` only — never a seal, never a
  ``verifier``. Propose, don't confirm.
* **Deterministic.** Same decisions in, same groups out — no clock, no random —
  so a run is reviewable and a test can pin it.

The concrete pieces live in sibling modules so they can be built and tested
independently against the types below:

* ``cluster.group(decisions, matcher, bar) -> list[Cluster]``
* ``supersede.find_supersessions(decisions, matcher, bar) -> list[ProposedEdge]``
* ``report.render(report) -> str`` and ``report.emit_edges(report, memory)``
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

from nestor.matcher import Matcher, StringMatcher

#: The triage bar, set by measuring this corpus — not inherited from the bench.
#: ``docs/decision-rewording-bench.md`` measured ~0.45 for rank@1 *recall* (a
#: decision's reword ranking near it), but triage does **all-pairs clustering**, a
#: different task: unrelated question-shaped decisions share a "Should the X be
#: Y?" skeleton and cross 0.45 on character difflib, so 0.45 floods — 687 edges,
#: mostly skeleton false-positives, on the 316-row corpus. A ``--calibrate`` sweep
#: shows the counts stop moving at **0.55** (269 groups / 62 edges; the
#: ``supersedes`` there are genuine 0.92+ rewordings), so that is the knee for
#: *this* task. Still recall over the 0.92 seal bar's precision, still below it,
#: still ``--calibrate`` per corpus — the number changed, the reasoning did not.
DEFAULT_BAR = 0.55

#: Edge kinds a proposal may carry — the subset of ``nestor.decision.EDGE_KINDS``
#: this triage emits. Kept here as the contract; the sink validates against the
#: canonical set so a drift between the two is caught at propose time.
EDGE_KINDS = ("supersedes", "contradicts", "refines")


@dataclass(frozen=True)
class Decision:
    """One (question, commitment, why) record — the unit a human seals.

    ``id`` is ``"<file-number>#<index>"`` (e.g. ``"0046#0"``): stable, sortable,
    and it names both the source file and the pair within it. ``consolidated_onto``
    is the store's existing hand-written supersession note (present on 7 files
    today, consumed by no code — this triage is what would consume it).
    """
    id: str
    file: str
    question: str
    commitment: str
    why: str
    consolidated_onto: str | None


@dataclass(frozen=True)
class Cluster:
    """A themed group a human reviews as one batch."""
    label: str                      # short theme, from the group's shared tokens
    member_ids: tuple[str, ...]     # decision ids, deterministic order
    representative_id: str          # the most central member


@dataclass(frozen=True)
class ProposedEdge:
    """A proposed relation between two decisions — never sealed, only proposed."""
    src_id: str
    dst_id: str
    kind: str                       # one of EDGE_KINDS
    score: float
    evidence: str


@dataclass(frozen=True)
class Report:
    """The whole triage: groups + proposed edges + the bar they were found at."""
    clusters: tuple[Cluster, ...]
    edges: tuple[ProposedEdge, ...]
    bar: float
    n_decisions: int


def decisions_dir(root: pathlib.Path | None = None) -> pathlib.Path:
    root = root or pathlib.Path(__file__).resolve().parents[2]
    return root / "docs" / "dogfood" / "decisions"


def load_decisions(root: pathlib.Path | None = None) -> list[Decision]:
    """Every (question, commitment, why) pair across the dogfood decision files.

    One JSON file is a PR bundle carrying several pairs; each pair is its own
    ``Decision``. Returns them sorted by id, so the whole pipeline downstream is
    deterministic without anyone having to re-sort.
    """
    out: list[Decision] = []
    for path in sorted(decisions_dir(root).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        number = path.name.split("-", 1)[0]
        onto = data.get("consolidated_onto")
        for i, d in enumerate(data.get("decisions", [])):
            out.append(Decision(
                id=f"{number}#{i}",
                file=path.name,
                question=(d.get("question") or "").strip(),
                commitment=(d.get("commitment") or "").strip(),
                why=(d.get("why") or "").strip(),
                consolidated_onto=onto))
    return sorted(out, key=lambda d: d.id)


def triage(decisions: list[Decision] | None = None,
           matcher: Matcher | None = None,
           bar: float = DEFAULT_BAR,
           root: pathlib.Path | None = None) -> Report:
    """Group the queue and find its supersessions — the whole assembly.

    Pure orchestration: load (if not given), cluster, find supersessions, box the
    result. The heavy lifting is in ``cluster`` and ``supersede``; this pins the
    order and the defaults (the offline ``StringMatcher`` and the N1 bar).
    """
    from nestor.triage import cluster as _cluster
    from nestor.triage import supersede as _supersede

    decisions = load_decisions(root) if decisions is None else decisions
    matcher = matcher or StringMatcher()
    clusters = _cluster.group(decisions, matcher, bar)
    edges = _supersede.find_supersessions(decisions, matcher, bar)
    return Report(clusters=tuple(clusters), edges=tuple(edges),
                  bar=bar, n_decisions=len(decisions))
