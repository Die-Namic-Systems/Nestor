"""The report pass — deterministic view, and the one guard that carries the
covenant: emit_edges proposes and never seals.

render() is pinned to be a pure function of the report (diffable, testable) that
surfaces the group labels, the edge evidence, and the open/resolved split. The
load-bearing test ingests real decisions into a real store, proposes every edge,
and asserts the store sealed nothing and every proposed edge is a draft — because
"it only proposes" is the whole reason this is allowed to write at all. Written
during the audit; the builder produced the modules but not this test.
"""
from __future__ import annotations

from nestor.triage import Cluster, Decision, ProposedEdge, Report
from nestor.triage.report import emit_edges, render


def _d(id_: str, q: str, c: str, onto=None) -> Decision:
    return Decision(id=id_, file=id_.split("#")[0] + ".json",
                    question=q, commitment=c, why="because", consolidated_onto=onto)


def _fixture_report() -> tuple[Report, list[Decision]]:
    ds = [_d("0001#0", "Should the gate fail closed?", "yes it fails closed"),
          _d("0002#0", "Should the gate fail closed?", "yes it fails closed"),
          _d("0003#0", "How is drive access enforced?", "by egress policy", onto="claude/x")]
    report = Report(
        clusters=(Cluster(label="gate closed", member_ids=("0001#0", "0002#0"),
                          representative_id="0002#0"),
                  Cluster(label="drive egress", member_ids=("0003#0",),
                          representative_id="0003#0")),
        edges=(ProposedEdge(src_id="0002#0", dst_id="0001#0", kind="supersedes",
                            score=1.0, evidence="same question; commitments align"),),
        bar=0.55, n_decisions=3)
    return report, ds


def test_render_is_deterministic_and_surfaces_the_load_bearing_parts():
    report, ds = _fixture_report()
    text = render(report, ds)
    assert text == render(report, ds)                 # pure function of its input
    assert "gate closed" in text                      # a group label
    assert "commitments align" in text                # an edge's evidence
    assert "STILL OPEN" in text                       # the open/resolved section
    assert "nothing here is sealed" in text.lower() or "not confirm" in text.lower()


def test_render_counts_a_supersededed_and_consolidated_row_as_resolved():
    report, ds = _fixture_report()
    text = render(report, ds)
    # 0001#0 (dst of a supersedes) and 0003#0 (consolidated_onto) are resolved;
    # only 0002#0 remains open.
    assert "likely resolved : 2" in text
    assert "still open       : 1" in text


def test_render_works_with_only_a_report_the_contract_form():
    report, _ = _fixture_report()
    render(report)                                    # must not require the decisions list


def test_emit_edges_proposes_and_never_seals():
    """The covenant, as a test: propose every edge into a real store, then assert
    nothing sealed and every edge is a draft (edge_sig / verifier empty)."""
    from nestor import memory as _memory
    from nestor.decision import DecisionMemory
    from nestor.sqlite_store import SqliteStore

    report, ds = _fixture_report()
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    try:
        for d in ds:                                  # endpoints must exist first
            # id-prefixed source: the fixture's 0001#0/0002#0 share a question,
            # and the store's (source_norm, lang, lang) uniqueness would collide
            # them — the same collision the CLI's --propose handles the same way.
            _memory.add_pair(source_text=f"{d.id}: {d.question}",
                             target_text=d.commitment,
                             source_lang="decision", target_lang="decision",
                             status="draft", reason=d.why, origin="test",
                             pair_id=d.id, store=store)
        rows = emit_edges(report, DecisionMemory(store))
        assert rows, "no edges proposed"
        assert all(r.get("edge_sig", "") == "" for r in rows)   # every edge a draft
        assert all(r.get("verifier", "") == "" for r in rows)
        assert store.memory_stats()["sealed"] == 0             # nothing sealed
    finally:
        store.close()
