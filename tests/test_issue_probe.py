"""The runner ships with its tests, per docs/agent-guide.md §"Tooling ...".

Three claims the runner makes that a reader would otherwise have to reproduce:

* it reads a prompts file, skipping blanks and ``#`` lines;
* it calls every lens for every prompt and records the raw stdout;
* it fails closed on a missing DB rather than producing an empty report
  (the exact failure #95 is filed for).

The store fixture from ``conftest.py`` gives a fresh SQLite backing per test.
We seed one memorable pair so a lens has something non-empty to say — if the
runner ever stopped calling the lenses, the test would go quiet in a way the
assertions catch.
"""
from __future__ import annotations

import json
import pathlib
import shutil

import pytest

from nestor import memory

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def probe_module():
    """Import the script by path — it lives under ``scripts/`` (not a package)."""
    import importlib.util
    import sys

    script = REPO_ROOT / "scripts" / "issue_probe.py"
    spec = importlib.util.spec_from_file_location("issue_probe", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["issue_probe"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop("issue_probe", None)
        raise
    return module


@pytest.fixture
def seeded_db(store):
    """Store with two draft rows the sweep can find, then return its path."""
    memory.add_pair(
        "does `nestor keys add` hand a verifier the key they need?",
        "not for ed25519 — the wrong key is printed",
        "decision",
        "decision",
        store=store,
    )
    memory.add_pair(
        "central config schema for NESTOR_* knobs",
        "one home, not a dozen entry points",
        "decision",
        "decision",
        store=store,
    )
    return pathlib.Path(store.db_path)


def _write_prompts(tmp_path: pathlib.Path, lines: list[str]) -> pathlib.Path:
    path = tmp_path / "prompts.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_prompt_file_skips_comments_and_blanks(tmp_path, probe_module):
    path = _write_prompts(
        tmp_path,
        ["# header", "", "first prompt", "  ", "# another comment", "second prompt"],
    )
    assert probe_module.read_prompts(path) == ["first prompt", "second prompt"]


def test_empty_prompt_file_is_a_hard_error(tmp_path, probe_module):
    path = _write_prompts(tmp_path, ["# only comments", ""])
    with pytest.raises(SystemExit, match="no runnable lines"):
        probe_module.read_prompts(path)


def test_missing_db_fails_closed(tmp_path, probe_module):
    prompts = _write_prompts(tmp_path, ["a prompt"])
    with pytest.raises(SystemExit, match="database not found"):
        probe_module.main(
            [
                "--db",
                str(tmp_path / "does-not-exist.db"),
                "--prompts",
                str(prompts),
                "--out",
                str(tmp_path / "report.md"),
            ]
        )


@pytest.mark.slow
def test_report_covers_every_prompt_and_corpus(tmp_path, seeded_db, probe_module):
    if not shutil.which("nestor"):
        pytest.skip("nestor CLI not on PATH")
    prompts = _write_prompts(
        tmp_path,
        [
            "nestor keys add prints the wrong key",
            "an unrelated question the store cannot answer",
        ],
    )
    md_out = tmp_path / "report.md"
    json_out = tmp_path / "report.json"
    rc = probe_module.main(
        [
            "--db",
            str(seeded_db),
            "--prompts",
            str(prompts),
            "--out",
            str(md_out),
            "--out-json",
            str(json_out),
        ]
    )
    assert rc == 0

    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert report["environment"]["prompt_count"] == 2
    assert [entry["prompt"] for entry in report["prompts"]] == [
        "nestor keys add prints the wrong key",
        "an unrelated question the store cannot answer",
    ]
    per_prompt_lenses = {"ask", "resolve", "match", "decision-check"}
    for entry in report["prompts"]:
        assert {inv["lens"] for inv in entry["lenses"]} == per_prompt_lenses

    corpus_lenses = {inv["lens"] for inv in report["corpus"]}
    assert corpus_lenses == {
        "stats",
        "rejections",
        "triage",
        "calibrate",
        "evidence-report",
    }

    md = md_out.read_text(encoding="utf-8")
    assert "Corpus-level lenses" in md
    assert "Per-prompt lenses" in md
    assert "nestor keys add prints the wrong key" in md


@pytest.mark.slow
def test_snapshot_flag_leaves_source_ledger_untouched(
    tmp_path, seeded_db, probe_module
):
    if not shutil.which("nestor"):
        pytest.skip("nestor CLI not on PATH")
    ledger_path = pathlib.Path(str(seeded_db) + ".ledger.jsonl")
    before = ledger_path.read_bytes() if ledger_path.exists() else b""
    prompts = _write_prompts(tmp_path, ["a prompt that will resolve to nothing"])
    rc = probe_module.main(
        [
            "--db",
            str(seeded_db),
            "--prompts",
            str(prompts),
            "--out",
            str(tmp_path / "r.md"),
            "--snapshot",
        ]
    )
    assert rc == 0
    after = ledger_path.read_bytes() if ledger_path.exists() else b""
    assert before == after, "source ledger changed despite --snapshot"


def test_no_corpus_flag_skips_corpus_section(tmp_path, seeded_db, probe_module):
    if not shutil.which("nestor"):
        pytest.skip("nestor CLI not on PATH")
    prompts = _write_prompts(tmp_path, ["a prompt"])
    json_out = tmp_path / "r.json"
    rc = probe_module.main(
        [
            "--db",
            str(seeded_db),
            "--prompts",
            str(prompts),
            "--out",
            str(tmp_path / "r.md"),
            "--out-json",
            str(json_out),
            "--no-corpus",
        ]
    )
    assert rc == 0
    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert report["corpus"] == []
    assert report["environment"]["skip_corpus"] is True
