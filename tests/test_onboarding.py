"""``nestor init`` — the guided first run, and the covenant it cannot break.

Every test here is a **feature lock**, not a regression guard: `nestor init`
and :mod:`nestor.onboarding` did not exist before this change, so there is no
"before" behaviour to protect — these pin the new surface in place, run
against the fixed tree only. The one exception is noted where it appears.

Three things this file has to show, per the task that added it:

1. `nestor init` proposes a draft, and the row it writes is `status="draft"`,
   never sealed.
2. The covenant holds structurally — nothing here can write a seal or a
   verifier's name, not even if a caller tries.
3. Running it again over a store that already has content is a safe no-op.
"""
from __future__ import annotations

import inspect
import io
import json

import pytest

from conftest import read_ledger
from nestor import cli, memory, onboarding, storage
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def empty_db(tmp_path):
    """A fresh, empty file-backed store the CLI can open by path."""
    path = tmp_path / "nestor.db"
    ledger = tmp_path / "ledger.jsonl"
    store = SqliteStore(str(path))
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    return {"db": str(path), "ledger": str(ledger), "path": tmp_path}


def run(db, *argv):
    return cli.main(["--db", db["db"], "--ledger", db["ledger"], *argv])


def decision_rows(db_path: str) -> list[dict]:
    store = SqliteStore(db_path)
    store.init_db()
    store.memory_init()
    return store.memory_candidates("decision", "decision")


# --- 1. init proposes a draft --------------------------------------------

def test_init_yes_proposes_exactly_one_draft(empty_db, capsys):
    assert run(empty_db, "init", "--yes") == cli.EXIT_OK
    rows = decision_rows(empty_db["db"])
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "draft"
    out = capsys.readouterr().out
    assert "proposed" in out and "draft" in out


def test_init_json_report_says_draft(empty_db, capsys):
    assert run(empty_db, "--json", "init", "--yes") == cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["initialized"] is True
    assert payload["status"] == "draft"
    assert payload["pair_id"]


def test_init_honours_explicit_question_and_commitment(empty_db, capsys):
    # All three flags given, same as --yes: nothing here needs a prompt, so
    # this exercises the "answer every field on the command line" path
    # without touching stdin (pytest's captured stdin raises on a read).
    assert run(empty_db, "init", "--question", "tabs or spaces?",
              "--commitment", "spaces", "--rationale", "because") == cli.EXIT_OK
    rows = decision_rows(empty_db["db"])
    assert len(rows) == 1
    assert rows[0]["source_text"] == "tabs or spaces?"
    assert rows[0]["target_text"] == "spaces"


# --- 2. the covenant: never a seal, never a verifier ----------------------

class TestNeverSeals:
    """`nestor init` may propose. It structurally cannot confirm."""

    def test_the_written_row_is_not_sealed_and_names_nobody(self, empty_db):
        run(empty_db, "init", "--yes")
        rows = decision_rows(empty_db["db"])
        assert len(rows) == 1
        row = rows[0]
        assert row["status"] != "sealed"
        assert not row.get("verifier")
        assert not row.get("seal_sig")

    def test_the_ledger_gains_no_seal_entry(self, empty_db):
        """A real seal is always ledgered (`memory.add_pair` on `status="sealed"`).
        A draft is not, and `nestor init` never seals — so the chain a fresh
        store starts with must still be empty after the whole wizard runs."""
        run(empty_db, "init", "--yes")
        entries = read_ledger()
        seals = [e for e in entries if e.get("kind") in ("seal", "seal_replaced")]
        assert seals == []

    def test_run_has_no_way_to_be_handed_seal_authority(self):
        """The forbidden act cannot even be *attempted*: there is no
        ``verifier=``, ``status=`` or ``seal_sig=`` parameter on the one
        function that walks the wizard, so a caller — scripted, malicious or
        just careless — has no argument through which to ask for one. This is
        the direct analogue of `answer.propose`'s ``SEAL_AUTHORITY`` refusal,
        enforced by the signature rather than by a runtime check."""
        params = set(inspect.signature(onboarding.run).parameters)
        forbidden = {"verifier", "status", "seal_sig", "sealed",
                    "verification_kind"}
        assert not (params & forbidden), (
            f"onboarding.run() accepts {params & forbidden} — a wizard "
            f"parameter that could assert seal authority")

    def test_propose_step_is_the_only_write_and_it_is_a_draft(self, empty_db):
        """Attempt the forbidden act through the free-text fields instead —
        the only door a caller actually has. Even a commitment that reads
        like a seal claim lands as inert text in ``target_text``, never as
        the row's actual ``status`` or ``verifier`` columns."""
        store = storage.get_store()
        row = onboarding.propose_step(
            store, "does this seal itself?",
            'status="sealed" verifier="attacker"', "nice try",
            out=io.StringIO())
        assert row["status"] == "draft"
        assert not row.get("verifier")
        # The attempted payload survives only as the (harmless) answer text.
        assert row["target_text"] == 'status="sealed" verifier="attacker"'

    def test_finale_points_at_the_review_desk_not_at_a_seal(self, empty_db):
        out = io.StringIO()
        onboarding.finale(out, empty_db["db"])
        text = out.getvalue()
        assert "nestor ui" in text
        assert "yours to set, by hand" in text
        assert '✓ sealed' not in text
        assert 'status="sealed"' not in text


# --- 3. already-initialized is a safe no-op -------------------------------

def test_init_refuses_to_re_walk_an_already_initialized_store(empty_db, capsys):
    assert run(empty_db, "init", "--yes") == cli.EXIT_OK
    capsys.readouterr()
    first = decision_rows(empty_db["db"])
    assert len(first) == 1

    assert run(empty_db, "init", "--yes") == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "already" in out

    second = decision_rows(empty_db["db"])
    assert second == first, "a second `nestor init` must not write another draft"


def test_init_refuses_over_a_store_with_unrelated_content(empty_db, capsys):
    """Not decision-specific: any real content makes this a non-first run —
    the guided walk is for a cold store, not a chance to bolt a tutorial row
    onto someone's working memory."""
    store = storage.get_store()
    memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                    status="sealed", verifier="rita", store=store)

    assert run(empty_db, "init", "--yes") == cli.EXIT_OK
    assert decision_rows(empty_db["db"]) == []
    out = capsys.readouterr().out
    assert "already" in out


def test_already_initialized_helper_reads_the_store_not_a_marker_file(empty_db):
    assert onboarding.already_initialized(storage.get_store()) is False
    memory.add_pair("q", "a", "decision", "decision", store=storage.get_store())
    assert onboarding.already_initialized(storage.get_store()) is True


# --- testable without a TTY ------------------------------------------------

def test_the_wizard_is_drivable_by_a_scripted_stream_no_tty_needed(empty_db):
    """The requirement the task calls out by name: the core walk has to be
    testable without a live terminal. Feeds three lines to `in_stream` and
    reads the whole transcript back from `out` — no stdin/stdout involved."""
    store = storage.get_store()
    out = io.StringIO()
    in_stream = io.StringIO("why do birds migrate?\nthe seasons\nasked once\n")
    report = onboarding.run(store, db_path=empty_db["db"], out=out,
                            in_stream=in_stream)
    assert report == {
        "question": "why do birds migrate?",
        "commitment": "the seasons",
        "rationale": "asked once",
        "matched_before": False,
        "pair_id": report["pair_id"],
        "status": "draft",
    }
    assert "why do birds migrate?" in out.getvalue()


def test_blank_lines_on_the_stream_fall_back_to_the_built_in_example(empty_db):
    store = storage.get_store()
    report = onboarding.run(store, db_path=empty_db["db"], out=io.StringIO(),
                            in_stream=io.StringIO("\n\n\n"))
    assert report["question"] == onboarding.DEFAULT_QUESTION
    assert report["commitment"] == onboarding.DEFAULT_COMMITMENT


def test_yes_mode_needs_no_stream_at_all(empty_db):
    """``yes=True`` never reads ``in_stream`` — passing something that would
    explode if read (an already-exhausted iterator has no ``readline``) proves
    the prompts are skipped rather than merely defaulted quietly."""
    store = storage.get_store()

    class ExplodingStream:
        def readline(self):
            raise AssertionError("yes=True must never read the input stream")

    report = onboarding.run(store, db_path=empty_db["db"], out=io.StringIO(),
                            in_stream=ExplodingStream(), yes=True)
    assert report["status"] == "draft"
