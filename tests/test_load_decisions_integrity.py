"""Corpus integrity for ``dogfood_common.load_decisions`` — the forbidden acts.

The rule these tests lock: *absence is a recorded value, not a missing row.* A
decision file that is truncated, malformed, or collides with another must fail
LOUD — it must not drop out of the corpus while the build reports green on the
rows that happened to survive. The refusal tests are the acceptance; the
happy-path test only proves the guard did not seize the door shut on good input.

Each refusal test writes the forbidden thing into a temp decisions dir and
asserts :func:`load_decisions` *raises* — a guard that cannot be shown to fail
has not been shown to work.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dogfood_common


def _write(dir_: pathlib.Path, name: str, decisions: list[dict], **top) -> None:
    payload = {"pr": top.pop("pr", 100), "date": top.pop("date", "2026-08-13"),
               "decisions": decisions, **top}
    (dir_ / name).write_text(json.dumps(payload), encoding="utf-8")


def _pair(q: str = "Should the store read local?", c: str = "No.",
          w: str = "A local read is not an audit trail.") -> dict:
    return {"question": q, "commitment": c, "why": w}


# --- happy path: the guard does not block good input -------------------------

def test_valid_corpus_loads_in_stable_file_order(tmp_path):
    _write(tmp_path, "0002-second.json", [_pair("Q-b", "C-b", "W-b")], pr=2)
    _write(tmp_path, "0001-first.json",
           [_pair("Q-a0", "C-a0", "W-a0"), _pair("Q-a1", "C-a1", "W-a1")], pr=1)

    rows = dogfood_common.load_decisions(tmp_path)

    assert [r.file for r in rows] == ["0001", "0001", "0002"]
    assert [r.question for r in rows] == ["Q-a0", "Q-a1", "Q-b"]
    assert rows[0].origin == "pr:1" and rows[2].origin == "pr:2"


# --- refusal: a truncated / malformed file fails loud, does not vanish -------

def test_truncated_json_file_raises_not_skipped(tmp_path):
    _write(tmp_path, "0001-good.json", [_pair()], pr=1)
    # A half-written file: valid up to the point the writer died.
    (tmp_path / "0002-truncated.json").write_text(
        '{"pr": 2, "date": "2026-08-13", "decisions": [', encoding="utf-8")

    with pytest.raises(dogfood_common.DecisionCorpusError) as excinfo:
        dogfood_common.load_decisions(tmp_path)
    assert "0002-truncated.json" in str(excinfo.value)


def test_malformed_json_file_raises(tmp_path):
    _write(tmp_path, "0001-good.json", [_pair()], pr=1)
    (tmp_path / "0009-garbage.json").write_text("{not json at all", encoding="utf-8")

    with pytest.raises(dogfood_common.DecisionCorpusError):
        dogfood_common.load_decisions(tmp_path)


# --- refusal: a duplicate collides ids and must be refused, not deduped ------

def test_duplicate_pr_number_files_raise(tmp_path):
    # Two files sharing a PR number ("0007") collide the '<number>#<index>'
    # identity; the old loader silently kept both.
    _write(tmp_path, "0007-alpha.json", [_pair("Q-alpha")], pr=7)
    _write(tmp_path, "0007-beta.json", [_pair("Q-beta")], pr=7)

    with pytest.raises(dogfood_common.DecisionCorpusError) as excinfo:
        dogfood_common.load_decisions(tmp_path)
    msg = str(excinfo.value)
    assert "0007" in msg
    assert "alpha" in msg and "beta" in msg


def test_duplicate_error_subclasses_valueerror(tmp_path):
    """Callers catching ValueError still catch the refusal."""
    _write(tmp_path, "0007-alpha.json", [_pair()], pr=7)
    _write(tmp_path, "0007-beta.json", [_pair()], pr=7)
    with pytest.raises(ValueError):
        dogfood_common.load_decisions(tmp_path)
