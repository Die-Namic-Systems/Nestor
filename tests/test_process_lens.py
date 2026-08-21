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
