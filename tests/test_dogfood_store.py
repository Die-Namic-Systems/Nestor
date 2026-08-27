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
                          capture_output=True, text=True, cwd=str(ROOT),
                          check=False)


# --- the committed artifact ------------------------------------------------

def test_the_committed_store_matches_the_decision_files():
    """The gate a PR trips when it adds a decision and forgets to rebuild.

    Run as a subprocess deliberately: this is the command a contributor types,
    and a test that exercised the functions instead would pass while the CLI
    somebody actually uses was broken."""
    done = _run("--verify")
    assert done.returncode == 0, done.stdout + done.stderr


def test_nothing_in_the_committed_store_is_sealed_without_seal_files():
    """Sealed rows in git must trace to ``docs/dogfood/seals/*.json``."""
    seal_dir = ROOT / "docs" / "dogfood" / "seals"
    seal_ids = {p.stem for p in seal_dir.glob("*.json")} if seal_dir.is_dir() else set()

    store = SqliteStore(str(STORE))
    try:
        store.memory_init()
        stats = memory.stats(store=store)
        rows = store.memory_list(limit=10_000)
    finally:
        store.close()

    sealed = [r for r in rows if r.get("status") == "sealed"]
    assert stats["sealed"] == len(seal_ids), (
        f"{stats['sealed']} sealed row(s) in store vs {len(seal_ids)} seal file(s)")
    assert {r["id"] for r in sealed} == seal_ids, (
        "every sealed row must have a matching seal file, and vice versa")
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


def test_archived_decision_files_are_not_in_the_committed_store():
    """``docs/archive/decisions/`` is audit record only — not part of the rebuild."""
    archive = ROOT / "docs" / "archive" / "decisions"
    archived_questions = set()
    for path in archive.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("decisions", []):
            archived_questions.add(row["question"])

    store = SqliteStore(str(STORE))
    try:
        store.memory_init()
        active_questions = {r["source_text"] for r in store.memory_list(limit=10_000)}
    finally:
        store.close()
    leaked = sorted(archived_questions & active_questions)
    assert not leaked, (
        f"{len(leaked)} archived decision question(s) still in the committed store")


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
    assert ("matches the decision files" in done.stdout
            and ("seals nothing" in done.stdout or "seal file(s)" in done.stdout))


# --- reproducibility -------------------------------------------------------

def test_the_rebuild_is_deterministic(tmp_path):
    """A rebuild that adds no decision must produce byte-identical output.

    Before ids and timestamps were pinned, every rebuild minted fresh uuid4s and
    a ``now()`` envelope, so a no-op run churned ~560 lines of ``decisions.json``
    and the committed store re-dirtied on any process that merely opened it —
    burying a real one-line change and tripping the git-clean hook.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import dogfood_store

    from nestor import portable

    def build_bundle(path):
        s = SqliteStore(str(path))
        s.memory_init()
        dogfood_store.build(s)
        bundle = portable.export_bundle(s)
        dogfood_store._pin_bundle_time(bundle)
        s.close()
        return json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True)

    assert build_bundle(tmp_path / "a.db") == build_bundle(tmp_path / "b.db"), (
        "the rebuild is not reproducible — a row id or a timestamp still churns")


def test_row_ids_and_timestamps_are_derived_from_the_decision(tmp_path):
    """Determinism from the decision, not from luck: the id is uuid5 over
    (file, question, commitment) and created_at is the file's own date."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import dogfood_common
    import dogfood_store

    from nestor.matcher import StringMatcher

    s = SqliteStore(str(tmp_path / "d.db"))
    s.memory_init()
    dogfood_store.build(s)
    d = dogfood_common.load_decisions(dogfood_store.DECISIONS_DIR)[0]
    row = s.memory_find(StringMatcher().normalize(d.question), "decision", "decision")
    s.close()
    assert row["id"] == dogfood_store._row_id(d)
    assert row["created_at"] == f"{d.date}T00:00:00+00:00"


# --- the digest covers origin and reason (IDEAS 6.43) ----------------------

def test_digest_changes_when_origin_moves(tmp_path):
    """A digest that does not go red when origin moves is the whole defect.

    Before the fix, ``_bundle_digest`` hashed ``(source_text, target_text,
    status)`` and omitted ``origin`` and ``reason``. A decision file could
    change where its rows claimed to have come from and ``--verify`` still
    exited 0. Mutating ``origin`` on one row must change the digest.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import dogfood_store

    s = SqliteStore(str(tmp_path / "a.db"))
    s.memory_init()
    dogfood_store.build(s)
    before = dogfood_store._bundle_digest(s)

    # Mutate origin on the first row — the digest must move.
    rows = s.memory_list(limit=1)
    assert rows, "the build must produce at least one row"
    with s._db() as conn:
        conn.execute("UPDATE tm_pairs SET origin='pr:forged' WHERE id=?",
                     (rows[0]["id"],))
    after = dogfood_store._bundle_digest(s)
    s.close()
    assert before != after, (
        "the digest did not change when origin moved — the defect §6.43 is "
        "about: a decision file can change where its rows claim to have come "
        "from and --verify still exits 0")


def test_digest_changes_when_reason_moves(tmp_path):
    """Same defect as origin: reason was omitted from the digest."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import dogfood_store

    s = SqliteStore(str(tmp_path / "b.db"))
    s.memory_init()
    dogfood_store.build(s)
    before = dogfood_store._bundle_digest(s)

    rows = s.memory_list(limit=1)
    assert rows, "the build must produce at least one row"
    with s._db() as conn:
        conn.execute("UPDATE tm_pairs SET reason='forged rationale' WHERE id=?",
                     (rows[0]["id"],))
    after = dogfood_store._bundle_digest(s)
    s.close()
    assert before != after, (
        "the digest did not change when reason moved — same class of defect "
        "as origin: the rationale can be rewritten and --verify stays green")


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


# --- seal files (§6.123) ---------------------------------------------------

def _seal_fixture(tmp_path):
    """One decision file, a draft build, and a client-signed seal for it."""
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    sys.path.insert(0, str(ROOT / "scripts"))
    import dogfood_common
    import dogfood_store

    from nestor import keyring, signing

    decisions = tmp_path / "decisions"
    seals = tmp_path / "seals"
    verifiers = tmp_path / "verifiers.json"
    decisions.mkdir()
    seals.mkdir()

    decision_path = decisions / "0999-seal-file-fixture.json"
    decision_path.write_text(json.dumps({
        "pr": "fixture",
        "date": "2026-08-27",
        "decisions": [{
            "question": "May a human seal travel in git as reviewable JSON?",
            "commitment": "Yes, when a seal file verifies against the public keyring.",
            "why": "Fixture for §6.123.",
        }],
    }, indent=2) + "\n", encoding="utf-8")

    private = Ed25519PrivateKey.generate()
    pub_bytes = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ring = keyring.Keyring()
    ring.add("rita", key=pub_bytes, kind="ed25519")
    ring.save(str(verifiers))

    store = SqliteStore(str(tmp_path / "store.db"))
    store.memory_init()
    dogfood_store.DECISIONS_DIR = decisions
    dogfood_common.DECISIONS_DIR = decisions
    dogfood_store.build(store)
    row = store.memory_list(limit=1)[0]
    sig = private.sign(
        signing._message(row["source_norm"], row["target_text"], "rita")).hex()

    seal_path = seals / f"{row['id']}.json"
    seal_path.write_text(json.dumps({
        "pair_id": row["id"],
        "verifier": "rita",
        "sealed_at": "2026-08-27T12:00:00+00:00",
        "seal_sig": sig,
    }, indent=2) + "\n", encoding="utf-8")

    return {
        "decisions": decisions,
        "seals": seals,
        "verifiers": verifiers,
        "store": store,
        "row": row,
        "sig": sig,
        "dogfood_common": dogfood_common,
        "dogfood_store": dogfood_store,
    }


def test_rebuild_folds_a_verified_seal_file(tmp_path, monkeypatch):
    fx = _seal_fixture(tmp_path)
    monkeypatch.setattr(fx["dogfood_store"], "DECISIONS_DIR", fx["decisions"])
    monkeypatch.setattr(fx["dogfood_store"], "SEALS_DIR", fx["seals"])
    monkeypatch.setattr(fx["dogfood_common"], "DECISIONS_DIR", fx["decisions"])
    monkeypatch.setattr(fx["dogfood_common"], "SEALS_DIR", fx["seals"])
    monkeypatch.setattr(fx["dogfood_common"], "VERIFIERS_PATH", fx["verifiers"])

    fresh = SqliteStore(str(tmp_path / "fresh.db"))
    fresh.memory_init()
    stats = fx["dogfood_store"].build(fresh)
    sealed = fresh.memory_get(fx["row"]["id"])
    fresh.close()

    assert stats["sealed"] == 1
    assert sealed["status"] == "sealed"
    assert sealed["verifier"] == "rita"
    assert sealed["seal_sig"] == fx["sig"]


def test_rebuild_refuses_a_forged_seal_file(tmp_path, monkeypatch):
    fx = _seal_fixture(tmp_path)
    monkeypatch.setattr(fx["dogfood_store"], "DECISIONS_DIR", fx["decisions"])
    monkeypatch.setattr(fx["dogfood_store"], "SEALS_DIR", fx["seals"])
    monkeypatch.setattr(fx["dogfood_common"], "DECISIONS_DIR", fx["decisions"])
    monkeypatch.setattr(fx["dogfood_common"], "SEALS_DIR", fx["seals"])
    monkeypatch.setattr(fx["dogfood_common"], "VERIFIERS_PATH", fx["verifiers"])

    seal_path = fx["seals"] / f"{fx['row']['id']}.json"
    bad = json.loads(seal_path.read_text(encoding="utf-8"))
    bad["seal_sig"] = "00" * 64
    seal_path.write_text(json.dumps(bad, indent=2) + "\n", encoding="utf-8")

    fresh = SqliteStore(str(tmp_path / "bad.db"))
    fresh.memory_init()
    with pytest.raises(fx["dogfood_common"].SealFileError, match="does not verify"):
        fx["dogfood_store"].build(fresh)
    fresh.close()


def test_verify_fails_when_store_is_sealed_without_a_seal_file(tmp_path, monkeypatch):
    """A hand-sealed committed store must not pass --verify."""
    fx = _seal_fixture(tmp_path)
    store_path = tmp_path / "committed.db"
    empty_seals = tmp_path / "empty-seals"
    empty_seals.mkdir()

    fresh = SqliteStore(str(store_path))
    fresh.memory_init()
    monkeypatch.setattr(fx["dogfood_store"], "DECISIONS_DIR", fx["decisions"])
    monkeypatch.setattr(fx["dogfood_store"], "SEALS_DIR", fx["seals"])
    monkeypatch.setattr(fx["dogfood_common"], "DECISIONS_DIR", fx["decisions"])
    monkeypatch.setattr(fx["dogfood_common"], "SEALS_DIR", fx["seals"])
    monkeypatch.setattr(fx["dogfood_common"], "VERIFIERS_PATH", fx["verifiers"])
    fx["dogfood_store"].build(fresh)
    fresh.close()

    monkeypatch.setattr(fx["dogfood_store"], "STORE_PATH", store_path)
    monkeypatch.setattr(fx["dogfood_store"], "SEALS_DIR", empty_seals)
    monkeypatch.setattr(fx["dogfood_store"], "BUNDLE_PATH", tmp_path / "bundle.json")
    monkeypatch.setattr(sys, "argv", ["dogfood_store.py", "--verify"])
    assert fx["dogfood_store"].main() != 0
