"""The standing rule: the decision memory grows from the repository only.

`scripts/dogfood_store.py` rebuilds `docs/dogfood/nestor.db` from the files in
`docs/dogfood/decisions/`. These gates exist because the value of that store is
entirely in where its rows came from — a memory whose contents arrived from
somewhere nobody can see is not an audit trail, it is a pile.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from nestor import memory, storage
from nestor.sqlite_store import SqliteStore

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dogfood_store.py"
STORE = ROOT / "docs" / "dogfood" / "nestor.db"
DECISIONS = ROOT / "docs" / "dogfood" / "decisions"


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=str(ROOT))


# --- the committed artifact ------------------------------------------------

def test_the_committed_store_matches_the_decision_files():
    """The gate a PR trips when it adds a decision and forgets to rebuild.

    Run as a subprocess deliberately: this is the command a contributor types,
    and a test that exercised the functions instead would pass while the CLI
    somebody actually uses was broken."""
    done = _run("--verify")
    assert done.returncode == 0, done.stdout + done.stderr


def test_nothing_in_the_committed_store_is_sealed():
    """The covenant, checked against the artifact rather than the builder.

    `assert_nothing_sealed` runs during a build; this asks the file itself, so a
    row sealed by any route at all — a hand edit, a bad merge, a future script —
    is caught rather than assumed impossible."""
    store = SqliteStore(str(STORE))
    try:
        store.memory_init()
        stats = memory.stats(store=store)
    finally:
        store.close()
    assert stats["sealed"] == 0, (
        f"{stats['sealed']} sealed row(s) in the committed store — the machine "
        f"may propose and may not confirm, and a seal belongs to a human at "
        f"nestor.ui")
    assert stats["draft"] > 0, "an empty store would pass every other gate here"


def test_every_row_is_traceable_to_a_decision_file():
    """No row without a provenance. `origin` carries the PR that added it, and a
    row whose origin names no file is a row nobody can audit."""
    known = set()
    for path in sorted(DECISIONS.glob("*.json")):
        known.add(f"pr:{json.loads(path.read_text(encoding='utf-8')).get('pr', '?')}")

    store = SqliteStore(str(STORE))
    try:
        store.memory_init()
        rows = store.memory_list(limit=10_000)
    finally:
        store.close()
    orphans = sorted({r["origin"] for r in rows} - known)
    assert not orphans, f"rows whose origin matches no decision file: {orphans}"


# --- the shared reader -------------------------------------------------------

def test_dogfood_common_reads_the_real_corpus():
    """`dogfood_common.load_decisions` is the one reader `dogfood_store.py` (and,
    separately, `demo/the_dogfooding.py`) build on. Read here directly, not
    through either caller, so this fails on the shared function itself rather
    than on whichever caller happens to exercise it first."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import dogfood_common

    known = {p.name.split("-")[0] for p in DECISIONS.glob("*.json")}
    rows = dogfood_common.load_decisions()

    assert rows, "the shared reader found no rows in the real corpus"
    for row in rows:
        assert row.file in known, (
            f"row {row.question[:40]!r} names file {row.file!r}, which matches "
            f"no decision file in {DECISIONS}")
        assert row.question and row.commitment and row.why, (
            "a row with an empty field is not traceable to what the file said")
        assert row.origin.startswith("pr:"), row.origin


def test_dogfood_store_still_verifies_after_the_extraction():
    """The refactor this test module was extended for: `dogfood_store.py` now
    calls the shared reader instead of parsing the corpus itself. `--verify`
    is the behavioral contract that must not move — same digest, same store."""
    done = _run("--verify")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "matches the decision files, and seals nothing" in done.stdout


# --- the direction ---------------------------------------------------------

def test_a_local_store_cannot_reach_the_committed_one(tmp_path, monkeypatch):
    """**Remote to local, never local to remote** — as a gate, not a promise.

    A process-wide store is installed and poisoned with a row that exists
    nowhere in the repository. The builder is then run in-process. If any code
    path in it consulted the ambient store — `get_store()` with no argument, an
    env var, a relative `data/nestor.db` — the poison would land in the build.
    """
    poison = SqliteStore(str(tmp_path / "local.db"))
    poison.memory_init()
    memory.add_pair("a decision made on somebody's laptop",
                    "and never written into a file anybody reviewed",
                    "decision", "decision", status="draft", store=poison)
    storage.set_store(poison)

    sys.path.insert(0, str(ROOT / "scripts"))
    import dogfood_store
    try:
        rows = dogfood_store.load_decisions()
    finally:
        poison.close()

    sources = {question for question, _c, _w, _o in rows}
    assert "a decision made on somebody's laptop" not in sources, (
        "the ambient store reached the build; the memory can now grow from a "
        "place nobody can review")
    assert sources, "the build read nothing at all, so this proves nothing"


def test_the_builder_reads_the_repository_and_not_a_configured_path(monkeypatch):
    """`NESTOR_DB` and friends must not redirect what gets committed.

    The store's location is a repository path, not a setting — the opposite
    posture to the glossary (§6.27) and the ledger, and deliberately so. Those
    are per-deployment; this is the artifact of a merged PR."""
    monkeypatch.setenv("NESTOR_DB", "/tmp/somewhere-else.db")
    monkeypatch.setenv("NESTOR_LEDGER", "/tmp/somewhere-else.jsonl")
    done = _run("--verify")
    assert done.returncode == 0, done.stdout + done.stderr


# --- the rule stays visible ------------------------------------------------

@pytest.mark.parametrize(
    "doc",
    ["CLAUDE.md", "docs/agent-guide.md", ".github/pull_request_template.md"],
)
def test_the_standing_rule_is_written_where_somebody_will_meet_it(doc):
    """A rule only an agent's memory carries is a rule that lasts one session.

    `CLAUDE.md` is back in this list on purpose. When the guide was split out it
    was retargeted from `CLAUDE.md` to `docs/agent-guide.md` — necessary, since
    the thin pointer no longer carried the string, but it swapped a *mechanical*
    encounter for a voluntary one. `CLAUDE.md` is auto-loaded; the guide is
    reached by choosing to follow a pointer, and the guide's own opening records
    an agent who did not follow the pointers. Both, then: the file that is read
    by construction and the file that holds the rule in full.
    """
    text = (ROOT / doc).read_text(encoding="utf-8")
    assert "docs/dogfood/decisions" in text, (
        f"{doc} does not mention where decisions go")


def test_the_thin_pointer_still_points():
    """`CLAUDE.md` forwards to the guide, and nothing else checked that it does.

    Measured on the split: replacing `CLAUDE.md` with three lines naming neither
    file left the whole suite green. The chain is auto-load -> pointer -> guide,
    and the only mechanically enforced link in it was the auto-load — landing on
    a file whose entire job is to forward. An edit that drops the forward breaks
    the chain in silence, and the file that says *do not duplicate policy here*
    is exactly the one nobody thinks to test.

    The assertion is on the **link form**, not on the filename appearing. The
    first version checked `target in text` and stayed green when the markdown
    link was replaced by the words "the guide", because `CLAUDE.md` names the
    file again further down in prose. A mention is not a pointer, and this test
    is named for the pointer.
    """
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for target in ("docs/agent-guide.md", "AGENTS.md"):
        assert f"]({target})" in text, (
            f"CLAUDE.md has no markdown link to {target} — it is the one file "
            f"an agent is made to read, so a pointer that has rotted is silent")
