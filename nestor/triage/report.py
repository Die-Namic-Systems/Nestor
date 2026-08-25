"""Report pass — the human-facing triage, and the opt-in edge sink.

Two functions, both read-only in spirit and one of them read-only in fact:

* :func:`render` turns a :class:`~nestor.triage.Report` into deterministic plain
  text — the same groups, edges and open/resolved split a human reads before
  sealing. It touches no store and confirms nothing; it is a view.
* :func:`emit_edges` is the *only* way this module writes, and it writes exactly
  one kind of row: a **proposed** edge, via ``DecisionMemory.propose_edge``. It
  never seals, never sets a verifier, never signs. It is opt-in — ``render`` does
  not call it — so a plain triage run cannot write to a store by accident.

Both obey the covenant the whole package is built under: *the machine may
propose, and may not confirm.* The output is a queue for a human, not a verdict.
"""
from __future__ import annotations

from collections.abc import Sequence

from nestor.triage import EDGE_KINDS, Decision, ProposedEdge, Report

_RULE = "=" * 68
_SUB = "-" * 68


def _population(report: Report,
                decisions: Sequence[Decision] | None) -> set[str]:
    """Every decision id the report knows about.

    The cluster members are the corpus that was grouped; the edge endpoints are
    folded in so a supersession target that landed in no cluster still counts as
    a decision. When the caller hands us the decision list (the CLI does), that
    is the authoritative population and it subsumes both.
    """
    ids: set[str] = set()
    for c in report.clusters:
        ids.update(c.member_ids)
    for e in report.edges:
        ids.add(e.src_id)
        ids.add(e.dst_id)
    if decisions:
        ids.update(d.id for d in decisions)
    return ids


def _resolved(report: Report,
              decisions: Sequence[Decision] | None) -> set[str]:
    """Decisions a human probably does not need to seal fresh.

    Two independent signals, unioned: a decision that carries the store's own
    hand-written ``consolidated_onto`` note (only visible when ``decisions`` is
    supplied), and a decision that is the ``dst`` of a proposed ``supersedes``
    edge — something newer claims to replace it. Everything else is open, and the
    open set is the queue this report exists to hand a person.
    """
    resolved = {e.dst_id for e in report.edges if e.kind == "supersedes"}
    if decisions:
        resolved.update(d.id for d in decisions if d.consolidated_onto)
    return resolved


def render(report: Report,
           decisions: Sequence[Decision] | None = None) -> str:
    """A deterministic, read-only, plain-text triage of ``report``.

    Same report in, same string out — every collection is sorted before it is
    printed and the edge kinds march in the fixed :data:`~nestor.triage.EDGE_KINDS`
    order, so a run is diffable and a test can pin it. Nothing here writes, seals,
    or reaches a store.

    ``decisions`` is optional. Given it (the CLI passes the loaded corpus), the
    open/resolved split also credits the store's ``consolidated_onto`` notes;
    without it, resolution rests on the proposed ``supersedes`` edges alone. The
    single-argument ``render(report)`` form the package contract names always
    works.

    Four sections: (1) a header with the decision count and the bar; (2) the
    themed groups, each with its representative and members; (3) the proposed
    edges grouped by kind, each with its evidence; (4) the resolved-vs-open
    summary, listing the open queue a human actually seals.
    """
    lines: list[str] = []
    add = lines.append

    # (1) header ---------------------------------------------------------------
    add(_RULE)
    add("Decision triage  (proposal — nothing here is sealed)")
    add(_RULE)
    add(f"decisions : {report.n_decisions}")
    add(f"bar       : {report.bar:.2f}")
    add(f"groups    : {len(report.clusters)}")
    add(f"edges     : {len(report.edges)}")
    add("")
    add("Read-only. A human seals coherent groups at `nestor ui`; this tool only")
    add("proposes. You may propose. You may not confirm.")
    add("")

    # (2) themed groups --------------------------------------------------------
    add(_SUB)
    add("THEMED GROUPS")
    add(_SUB)
    if not report.clusters:
        add("  (no groups)")
    multi = [c for c in report.clusters if len(c.member_ids) > 1]
    n_singletons = len(report.clusters) - len(multi)
    for c in sorted(multi,
                    key=lambda c: (c.label, c.representative_id)):
        add(f"[{c.label}]  ({len(c.member_ids)} member(s); "
            f"representative {c.representative_id})")
        for mid in sorted(c.member_ids):
            marker = "*" if mid == c.representative_id else " "
            add(f"    {marker} {mid}")
        add("")
    if n_singletons:
        add(f"  ({n_singletons} singleton group(s) suppressed)")
        add("")

    # (3) proposed edges, grouped by kind --------------------------------------
    add(_SUB)
    add("PROPOSED EDGES  (supersedes / contradicts / refines)")
    add(_SUB)
    by_kind: dict[str, list[ProposedEdge]] = {k: [] for k in EDGE_KINDS}
    for e in report.edges:
        by_kind.setdefault(e.kind, []).append(e)
    for kind in EDGE_KINDS:
        es = sorted(by_kind.get(kind, []),
                    key=lambda e: (e.src_id, e.dst_id, e.kind))
        add(f"{kind}: {len(es)}")
        for e in es:
            add(f"    {e.src_id} -> {e.dst_id}   (score {e.score:.2f})")
            add(f"        evidence: {e.evidence}")
        add("")

    # (4) already resolved vs. still open --------------------------------------
    ids = _population(report, decisions)
    resolved = _resolved(report, decisions) & ids
    open_ids = sorted(ids - resolved)
    add(_SUB)
    add("ALREADY RESOLVED vs. STILL OPEN")
    add(_SUB)
    add(f"likely resolved : {len(resolved)}  "
        f"(consolidated_onto, or the dst of a supersedes edge)")
    add(f"still open       : {len(open_ids)}")
    add("")
    add("open queue — the decisions a human still has to seal:")
    if open_ids:
        for oid in open_ids:
            add(f"    {oid}")
    else:
        add("    (none open)")

    return "\n".join(lines) + "\n"


def emit_edges(report: Report, memory) -> list:
    """Propose every edge in ``report`` into ``memory`` — proposals only.

    Calls ``memory.propose_edge(src_id, dst_id, kind, reason=evidence)`` and
    nothing else: no ``seal``, no ``seal_edge``, no ``verifier``. Each row lands
    as a **draft** edge (``edge_sig=''``, ``verifier=''``), exactly where a
    machine's proposal is allowed to land and no further. Returns the proposed
    rows in report order.

    Opt-in by design — :func:`render` never calls this, so viewing a triage
    cannot mutate a store. A caller that wants the edges written asks for it.
    """
    return [
        memory.propose_edge(e.src_id, e.dst_id, e.kind, reason=e.evidence)
        for e in report.edges
    ]
