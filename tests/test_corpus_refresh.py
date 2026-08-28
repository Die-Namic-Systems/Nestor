"""The refresh driver reads its plan out of the corpus, and refuses loudly.

Two properties carry this module. The first is that **nothing here is authored**:
which repositories, which extractor, which name and which commit all come out of
``corpus_claims`` provenance, so an operator decision recorded in
``docs/corpus-order.md`` (``mealie`` excluded, ``sean-data-vault`` allowlisted,
forks read as deltas) cannot be reversed by a roster someone typed here. The
second is that every refusal is **fail-closed and named** — the three of them
exist because the quiet version produces a corpus that lies about what it read.

The refusal tests matter more than the happy path: a driver that extracted
anyway would pin rows to a commit that does not contain them, and nothing
downstream could tell.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts" / "corpus"))

import refresh


def _household(path: pathlib.Path, rows: list[tuple[str, str]]) -> pathlib.Path:
    """A minimal household corpus: (repository, origin) pairs are all the plan reads."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE corpus_claims (repository TEXT, origin TEXT)")
    conn.executemany("INSERT INTO corpus_claims VALUES (?, ?)", rows)
    conn.commit()
    conn.close()
    return path


def _git_repo(path: pathlib.Path, dirty: bool = False) -> pathlib.Path:
    path.mkdir(parents=True, exist_ok=True)
    run = lambda *a: subprocess.run(["git", "-C", str(path), *a],
                                    capture_output=True, check=True)
    run("init", "-q")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    (path / "a.txt").write_text("one\n")
    run("add", "-A")
    run("commit", "-qm", "one")
    if dirty:
        (path / "a.txt").write_text("two\n")
    return path


def test_the_plan_is_read_out_of_the_corpus_not_authored(tmp_path):
    """repository, name, commit and toolchain all come from provenance."""
    household = _household(tmp_path / "h.db", [
        ("safe-app-store-public", "safe@01a74be:README.md#Apps [definition/db0312e]"),
        ("safe-app-store-public", "safe@01a74be:docs/x.md#Y [definition/db0312e]"),
        ("nestor", "nestor@193264d:nestor/cli.py::topic [symbol/2e1387d]"),
    ])
    rows = {row.repository: row for row in refresh.plan(household)}

    assert set(rows) == {"safe-app-store-public", "nestor"}
    safe = rows["safe-app-store-public"]
    # The name is NOT the repository — the run passed --name safe.
    assert (safe.name, safe.commit, safe.toolchain) == ("safe", "01a74be", "db0312e")
    assert safe.claims == 2
    assert rows["nestor"].name == "nestor"


def test_a_repository_with_no_rows_is_not_in_the_plan(tmp_path):
    """An exclusion cannot be undone here: the script has nothing to act on.

    ``mealie`` and ``litellm`` are excluded by operator decision in
    docs/corpus-order.md. They are absent from the corpus, so they are absent
    from the plan — no allowlist to keep in sync, and no way for this driver to
    quietly re-admit them.
    """
    household = _household(tmp_path / "h.db", [
        ("nestor", "nestor@193264d:a.py::b [symbol/2e1387d]"),
    ])
    assert [row.repository for row in refresh.plan(household)] == ["nestor"]


def test_every_toolchain_in_the_live_corpus_resolves_to_a_committed_extractor():
    """The digest is only resolvable because §6.53 commits the extractors.

    Computed from the tree, never tabulated: this is the mechanism the plan
    relies on to pick the right extractor per repository (standard vs fork vs
    the bespoke ones) without anyone maintaining a mapping.
    """
    known = refresh.extractors()
    assert known, "no extract_*.py found"
    standard = REPO / "scripts" / "corpus" / "extract_standard.py"
    assert standard in known.values()
    # Digests are content hashes over (extractor, provenance.py) — 7 hex chars.
    assert all(len(digest) == 7 for digest in known)


def test_an_unresolvable_toolchain_is_refused_not_guessed(tmp_path, capsys, monkeypatch):
    """A changed extractor means the rows would mean something else (§6.52)."""
    household = _household(tmp_path / "h.db", [
        ("nestor", "nestor@193264d:a.py::b [symbol/0000000]"),
    ])
    _git_repo(tmp_path / "roots" / "nestor")
    code = _run(monkeypatch, household, tmp_path, "--dry-run")
    out = capsys.readouterr().out
    assert "toolchain 0000000 resolves to no committed extractor" in out
    assert "0 ready, 1 refused" in out
    assert code == 1


def test_a_dirty_checkout_is_refused_because_the_pin_would_lie(tmp_path, capsys, monkeypatch):
    """provenance.commit() reports HEAD whatever the working tree holds."""
    household = _household(tmp_path / "h.db", [
        ("nestor", f"nestor@193264d:a.py::b [symbol/{_a_real_digest()}]"),
    ])
    _git_repo(tmp_path / "roots" / "nestor", dirty=True)
    code = _run(monkeypatch, household, tmp_path, "--dry-run")
    out = capsys.readouterr().out
    assert "has uncommitted changes" in out
    assert "which does not contain them" in out
    assert code == 1


def test_a_missing_checkout_is_refused_rather_than_read_as_empty(tmp_path, capsys, monkeypatch):
    household = _household(tmp_path / "h.db", [
        ("nowhere", f"nowhere@abc1234:a.py::b [symbol/{_a_real_digest()}]"),
    ])
    (tmp_path / "roots").mkdir()
    code = _run(monkeypatch, household, tmp_path, "--dry-run")
    assert "no checkout named 'nowhere'" in capsys.readouterr().out
    assert code == 1


def test_a_refused_repository_with_no_source_db_blocks_the_sync(tmp_path, capsys, monkeypatch):
    """Syncing then would drop the repository, not merely leave it stale.

    ``corpus.sync`` rebuilds the whole snapshot from whatever ``data/corpus/``
    holds, so a refused repository with no existing source database would
    vanish from the corpus entirely. Staleness is acceptable; silent deletion
    is not.
    """
    household = _household(tmp_path / "h.db", [
        ("nowhere", f"nowhere@abc1234:a.py::b [symbol/{_a_real_digest()}]"),
    ])
    (tmp_path / "roots").mkdir()
    (tmp_path / "out").mkdir()
    code = _run(monkeypatch, household, tmp_path)          # no --dry-run
    out = capsys.readouterr().out
    assert "refusing to sync" in out
    assert "would drop them entirely: nowhere" in out
    assert code == 1


def test_find_checkout_prefers_the_repository_then_falls_back_to_the_name(tmp_path):
    """The two diverge — safe-app-store-public was read as `safe`."""
    root = tmp_path / "r"
    _git_repo(root / "safe")
    row = refresh.Row("safe-app-store-public", "safe", "01a74be", "db0312e", 1)
    assert refresh.find_checkout([root], row) == root / "safe"

    _git_repo(root / "org" / "safe-app-store-public")
    assert refresh.find_checkout([root], row) == root / "org" / "safe-app-store-public"


def _a_real_digest() -> str:
    """A toolchain digest that does resolve, so a test can isolate one refusal."""
    return next(iter(refresh.extractors()))


def _run(monkeypatch, household, tmp_path, *extra) -> int:
    monkeypatch.setattr(sys, "argv", [
        "refresh.py", "--household", str(household),
        "--repos-root", str(tmp_path / "roots"),
        "--out", str(tmp_path / "out"), *extra,
    ])
    return refresh.main()


def _tombstone_file(path: pathlib.Path, record: dict) -> pathlib.Path:
    path.write_text(json.dumps({"version": 1, "tombstones": {"gone": record}}))
    return path


def test_a_tombstoned_repository_reports_retired_not_refused(tmp_path, capsys, monkeypatch):
    """RETIRED means "nothing to look at, and here is where it went".

    Without this a retired repository refuses on every run forever, beside
    conditions an operator can actually fix, until the refusal list stops being
    read. That is the same failure as an advisory that fires every turn (0221).
    """
    household = _household(tmp_path / "h.db", [
        ("gone", f"gone@abc1234:a.py::b [symbol/{_a_real_digest()}]"),
    ])
    (tmp_path / "roots").mkdir()
    monkeypatch.setattr(refresh, "TOMBSTONES", _tombstone_file(
        tmp_path / "t.json",
        {"ended": "rebuilt", "successor": "gone-successor", "reason": "x"}))
    code = _run(monkeypatch, household, tmp_path, "--dry-run")
    out = capsys.readouterr().out

    assert "RETIRED (rebuilt)" in out
    assert "gone-successor" in out
    assert "REFUSED" not in out
    assert "0 ready, 0 refused, 1 retired" in out
    # Retired is not a failure: nothing here is a condition anyone can act on.
    assert code == 0


def test_a_tombstone_without_its_required_forward_is_refused(tmp_path, monkeypatch):
    """"A merge with nowhere to point is a deletion wearing an archive."

    The convention's own rule, enforced. Raising rather than skipping matters:
    a tombstone that silently did not apply would put the repository back in
    the refusal list with nothing to say anyone had tried to retire it.
    """
    for record in ({"ended": "merged"},
                   {"ended": "rebuilt", "successor": "  "},
                   {"ended": "retired"}):
        path = _tombstone_file(tmp_path / "t.json", record)
        with pytest.raises(ValueError, match="requires"):
            refresh.tombstones(path)


def test_an_end_shape_outside_the_enum_is_refused(tmp_path):
    """`ended` is closed for the same reason `status` is — never invented."""
    path = _tombstone_file(tmp_path / "t.json",
                           {"ended": "archived", "successor": "x"})
    with pytest.raises(ValueError, match="ended must be one of"):
        refresh.tombstones(path)


def test_the_committed_tombstones_are_valid_and_name_real_repositories():
    """The shipped file must parse under the same rules a test file does.

    A tombstone naming a repository the corpus does not hold is a record that
    can never apply — it would read as retired-and-handled while the real
    repository went on refusing.
    """
    records = refresh.tombstones()
    assert records, "expected at least one committed tombstone"
    household = pathlib.Path.home() / ".nestor" / "keep" / "nestor.db"
    if household.is_file():
        known = {row.repository for row in refresh.plan(household)}
        assert set(records) <= known, (
            f"tombstoned but not in the corpus: {set(records) - known}")
