"""Tests for recipes/process_lens.py — the wall, the matcher, the covenant.

The recipe's claim is that Nestor's seam can carry corpus-lens's work while
inheriting the ledger, the three states and the one-live-row rule. These pin the
three places that claim could be false: the wall could leak, the matcher could
confuse two metrics for each other, and the recipe could offer a path to sealed.
"""
from __future__ import annotations

import pytest

from recipes import process_lens as pl

# --- the wall -------------------------------------------------------------

@pytest.mark.parametrize("leaky", [
    "steering_density | day=2026-08-20",          # ISO date
    "steering_density | first_at=14:32",          # wall clock
    "steering_density | first_at=14:32:07",       # wall clock, seconds
    "composition_mix | base_date=unknown",        # quarantined field name
    "composition_mix | local_tz=America/Denver",
    "clarification_pull | ref_map=session.jsonl",
    "clarification_pull | filename=2026-08-20.jsonl",
])
def test_wall_refuses_absolute_anchors(leaky):
    with pytest.raises(pl.WallError):
        pl.check_wall(leaky)


@pytest.mark.parametrize("clean", [
    "steering_density | mid_task_share_pct=62.1 sessions=8",
    "composition_mix | agent_share_pct=71.0 operator_share_pct=29.0",
    "clarification_pull | day_offset=3 delta_prev_s=418.5",
])
def test_wall_passes_relative_time(clean):
    pl.check_wall(clean)  # must not raise


def test_observation_refuses_to_build_a_leaky_row():
    with pytest.raises(pl.WallError):
        pl.observation("steering_density", base_date="2026-08-20")


# --- the matcher ----------------------------------------------------------

def test_metric_key_is_identity():
    m = pl.MATCHER
    a = pl.observation("steering_density", sessions=8)
    b = pl.observation("composition_mix", sessions=8)
    assert m.score(a, b) == 0.0, "two different metrics are never each other"


def test_same_metric_tolerates_drift_within_tolerance():
    m = pl.MATCHER
    a = pl.observation("steering_density", mid_task_share_pct=62.1)
    b = pl.observation("steering_density", mid_task_share_pct=62.4)
    assert m.score(a, b) == 1.0


def test_same_metric_notices_a_real_move():
    m = pl.MATCHER
    a = pl.observation("steering_density", mid_task_share_pct=62.1)
    b = pl.observation("steering_density", mid_task_share_pct=11.0)
    assert m.score(a, b) == 0.0


def test_readings_are_compared_pairwise_by_sorted_name():
    """Same measurement, different emission order, must read as identical."""
    a = pl.observation("steering_density", sessions=8, total_turns=47)
    b = pl.observation("steering_density", total_turns=47, sessions=8)
    assert a == b
    assert pl.MATCHER.score(a, b) == 1.0


def test_normalize_never_returns_empty():
    assert pl.MATCHER.normalize("") == "unkeyed"


# --- the covenant ---------------------------------------------------------

def test_propose_has_no_path_to_sealed():
    """No verifier parameter, and no status= assignment other than draft.

    Checks the CODE, not the prose: the docstring says the word "sealed" in the
    course of explaining that this function cannot reach it, and a test that
    tripped on that would be reading the explanation as the defect.
    """
    import ast
    import inspect
    import textwrap

    sig = inspect.signature(pl.propose)
    assert "verifier" not in sig.parameters

    tree = ast.parse(textwrap.dedent(inspect.getsource(pl.propose)))
    fn = tree.body[0]
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)):
        fn.body = fn.body[1:]          # drop the docstring, keep the code

    statuses = {
        kw.value.value
        for node in ast.walk(ast.Module(body=fn.body, type_ignores=[]))
        if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg == "status" and isinstance(kw.value, ast.Constant)
    }
    assert statuses == {"draft"}, f"propose() can set status to {statuses}"


def test_revise_requires_a_reason():
    with pytest.raises(ValueError):
        pl.revise("steering_density | sessions=8", "grade", "   ")


# --- the bridge: a corpus-lens report → drafts -----------------------------
#
# The fixture is a real `corpuslens run examples/sample-corpus --adapter
# claude-code --format json` (corpus-lens 0.3), not a hand-written stand-in:
# the bridge's claim is that it reads what the tool actually writes.

import copy
import json
import pathlib

from nestor.sqlite_store import SqliteStore

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "corpus_lens" / "sample_report.json"


def _report() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _live(store) -> dict:
    """{scoped metric: pair} for every live process row in the store."""
    rows = store.memory_list(source_lang=pl.DOMAIN, target_lang=pl.DOMAIN, limit=1000)
    return {pl._key_of(r["source_text"]): r for r in rows}


def test_fixture_is_a_real_report_with_one_errored_analyzer():
    doc = _report()
    assert doc["schema_version"] == pl.REPORT_SCHEMA_VERSION
    assert set(doc["results"]) == pl.KNOWN_METRICS
    errored = [k for k, v in doc["results"].items() if "error" in v]
    assert errored == ["signature_plurality"], "the sample corpus is below that analyzer's floor"


def test_from_report_proposes_one_draft_per_analyzer_and_skips_the_errored_one():
    store = SqliteStore(":memory:")
    summary = pl.from_report(_report(), corpus="claude-code", store=store)
    assert sorted(summary["proposed"]) == sorted(
        f"{m}@claude-code" for m in pl.KNOWN_METRICS if m != "signature_plurality")
    assert list(summary["skipped"]) == ["signature_plurality@claude-code"]
    assert "error" in summary["skipped"]["signature_plurality@claude-code"]
    assert summary["rivals"] == [] and summary["revised"] == [] and summary["unknown"] == []
    live = _live(store)
    assert set(live) == set(summary["proposed"])
    row = live["steering_density@claude-code"]
    assert row["status"] == "draft"
    assert row["target_text"].startswith("70.0% of the operator role's prompt turns")
    assert "mid_task_share_pct=70.0" in row["source_text"]
    assert "analyzer_version" not in row["source_text"], "provenance goes in reason, not the reading"
    assert "operator prompt turns with >=12 characters" in row["reason"]
    assert "v1" in row["reason"] and "question 1" in row["reason"] and "adapter=claude-code" in row["reason"]


def test_from_report_never_seals():
    store = SqliteStore(":memory:")
    pl.from_report(_report(), corpus="claude-code", store=store)
    assert {r["status"] for r in _live(store).values()} == {"draft"}


def test_same_report_twice_is_idempotent():
    store = SqliteStore(":memory:")
    pl.from_report(_report(), corpus="claude-code", store=store)
    again = pl.from_report(_report(), corpus="claude-code", store=store)
    assert again["rivals"] == [] and again["proposed"] == []
    assert len(again["unchanged"]) == 7
    assert len(_live(store)) == 7, "one live row per metric, not one per run"


def test_a_moved_reading_under_the_same_headline_is_still_a_rival():
    """nestor.memory conflicts on the target; the bridge must notice the source."""
    store = SqliteStore(":memory:")
    pl.from_report(_report(), corpus="claude-code", store=store)
    moved = _report()
    moved["results"]["tempo"]["median_gap_s"] = 9.0          # headline untouched
    summary = pl.from_report(moved, corpus="claude-code", store=store)
    assert summary["rivals"] == ["tempo@claude-code"]
    assert "median_gap_s=750.0" in _live(store)["tempo@claude-code"]["source_text"]
    summary = pl.from_report(moved, corpus="claude-code", store=store, revise_rivals=True)
    assert summary["revised"] == ["tempo@claude-code"]
    assert "median_gap_s=9.0" in _live(store)["tempo@claude-code"]["source_text"]


def test_a_moved_reading_is_a_rival_by_default_and_a_revision_on_request():
    store = SqliteStore(":memory:")
    pl.from_report(_report(), corpus="claude-code", store=store)
    moved = _report()
    moved["results"]["steering_density"]["mid_task_share_pct"] = 11.0
    moved["results"]["steering_density"]["headline"] = "11.0% of the operator role's prompt turns arrive mid-task."
    summary = pl.from_report(moved, corpus="claude-code", store=store)
    assert summary["rivals"] == ["steering_density@claude-code"]
    assert "mid_task_share_pct=70.0" in _live(store)["steering_density@claude-code"]["source_text"], \
        "a rival never overwrites"
    summary = pl.from_report(moved, corpus="claude-code", store=store, revise_rivals=True)
    assert summary["revised"] == ["steering_density@claude-code"]
    row = _live(store)["steering_density@claude-code"]
    assert "mid_task_share_pct=11.0" in row["source_text"]
    assert row["reason"].startswith("re-run of the same corpus")


def test_two_corpora_are_two_metrics_not_one_rival():
    store = SqliteStore(":memory:")
    pl.from_report(_report(), corpus="claude-code", store=store)
    moved = _report()
    moved["results"]["steering_density"]["mid_task_share_pct"] = 11.0
    summary = pl.from_report(moved, corpus="cursor", store=store)
    assert summary["rivals"] == []
    assert len(_live(store)) == 14


def test_from_report_refuses_a_different_envelope():
    doc = _report()
    doc["schema_version"] = 2
    with pytest.raises(ValueError, match="schema_version"):
        pl.from_report(doc, corpus="c", store=SqliteStore(":memory:"))
    with pytest.raises(ValueError, match="no results"):
        pl.from_report({"schema_version": 1, "results": {}}, corpus="c", store=SqliteStore(":memory:"))
    with pytest.raises(ValueError, match="corpus is required"):
        pl.from_report(_report(), corpus="  ", store=SqliteStore(":memory:"))


def test_from_report_refuses_rather_than_skips_a_leaky_headline():
    """A report carrying an anchor is an upstream bug; hiding it would be worse."""
    doc = _report()
    doc["results"]["tempo"]["headline"] = "the first prompt arrived at 14:32"
    with pytest.raises(pl.WallError):
        pl.from_report(doc, corpus="c", store=SqliteStore(":memory:"))


def test_readings_exclude_provenance_booleans_and_structure():
    got = pl.readings_of({"analyzer_version": 3, "n": 4, "pct": 1.5, "flag": True,
                          "buckets": {"a": 1}, "headline": "x"})
    assert got == {"n": 4, "pct": 1.5}


def test_unknown_analyzer_is_proposed_and_named():
    doc = _report()
    doc["results"]["brand_new"] = {"denominator": "things", "analyzer_version": 1,
                                   "grading_question": "none", "headline": "h", "n": 3}
    summary = pl.from_report(doc, corpus="c", store=SqliteStore(":memory:"))
    assert summary["unknown"] == ["brand_new"]
    assert "brand_new@c" in summary["proposed"]


def test_main_exit_codes(tmp_path, capsys):
    db = str(tmp_path / "pl.db")
    assert pl.main([str(FIXTURE), "--corpus", "claude-code", "--store", db]) == 0
    out = capsys.readouterr().out
    assert out.count("draft    ") == 7 and "skipped  signature_plurality@claude-code" in out
    assert "nothing here can" in out
    moved = copy.deepcopy(_report())
    moved["results"]["tempo"]["median_gap_s"] = 9.0
    p = tmp_path / "moved.json"
    p.write_text(json.dumps(moved), encoding="utf-8")
    assert pl.main([str(p), "--corpus", "claude-code", "--store", db]) == 1
    assert "rival    tempo@claude-code" in capsys.readouterr().out
    assert pl.main([str(p), "--corpus", "claude-code", "--store", db, "--revise"]) == 0
    assert "revised  tempo@claude-code" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": 9}', encoding="utf-8")
    assert pl.main([str(bad), "--corpus", "c", "--store", db]) == 2
    assert pl.main([str(tmp_path / "missing.json"), "--corpus", "c", "--store", db]) == 2
