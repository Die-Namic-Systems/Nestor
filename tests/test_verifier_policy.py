"""Per-domain verifier policy, enforced at seal time (issue #167 piece 3).

Closes two probe items: "the sign-off field accepts any name" and "no
per-domain verifier policy". The policy is opt-in — a domain that has never
recorded a policy row is unrestricted, exactly as before this existed — and
enforcement lives at the API layer (``nestor.memory.add_pair`` /
``supersede_pair``), never merely screened in a page: these tests call the
memory API directly, the same seam a UI, the CLI or an importer all funnel
through.

All verifier names below are obviously-fake test fixtures
("test-verifier-a" etc.), never a real person's name, and nothing here writes
``status="sealed"`` with intent to represent an actual human ratification —
these are refusal/CRUD tests of the *policy*, not seals a person is standing
behind.
"""
from __future__ import annotations

import os

import pytest

from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore

ALLOWED = "test-verifier-a"
OTHER_ALLOWED = "test-verifier-b"
OFF_LIST = "test-verifier-z"


@pytest.fixture()
def store(tmp_path, seal_key):
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    storage.set_store(s)
    return s


# --------------------------------------------------------------------------
# opt-in semantics: no policy rows -> unchanged behavior
# --------------------------------------------------------------------------

def test_no_policy_rows_allows_any_verifier(store):
    """A domain nobody has configured a policy for keeps working exactly as
    it always did — the whole point of an opt-in gate."""
    pair = memory.add_pair("hello", "hola", "en", "es",
                           status="sealed", verifier="anyone-at-all", store=store)
    assert pair["status"] == "sealed"
    assert pair["verifier"] == "anyone-at-all"


def test_policy_on_one_domain_does_not_touch_another(store):
    """Opt-in is per domain: restricting en->es must not restrict en->fr."""
    store.memory_policy_add("en", "es", ALLOWED)

    pair = memory.add_pair("hello", "bonjour", "en", "fr",
                           status="sealed", verifier="anyone-at-all", store=store)
    assert pair["status"] == "sealed"


# --------------------------------------------------------------------------
# refusal: a name off the list is rejected, with a clear error naming the policy
# --------------------------------------------------------------------------

def test_off_list_verifier_is_refused(store):
    store.memory_policy_add("en", "es", ALLOWED)

    with pytest.raises(memory.VerifierNotAllowedError, match="en->es"):
        memory.add_pair("hello", "hola", "en", "es",
                        status="sealed", verifier=OFF_LIST, store=store)

    # Nothing was written: no row at all for this source.
    assert memory.best_sealed("hello", "en", "es", store=store) is None


def test_refusal_names_the_allowed_verifiers(store):
    store.memory_policy_add("en", "es", ALLOWED)
    store.memory_policy_add("en", "es", OTHER_ALLOWED)

    with pytest.raises(memory.VerifierNotAllowedError) as excinfo:
        memory.add_pair("hello", "hola", "en", "es",
                        status="sealed", verifier=OFF_LIST, store=store)
    msg = str(excinfo.value)
    assert ALLOWED in msg and OTHER_ALLOWED in msg and OFF_LIST in msg


def test_allowed_verifier_may_seal(store):
    store.memory_policy_add("en", "es", ALLOWED)

    pair = memory.add_pair("hello", "hola", "en", "es",
                           status="sealed", verifier=ALLOWED, store=store)
    assert pair["status"] == "sealed"
    assert pair["verifier"] == ALLOWED


def test_draft_is_unaffected_by_policy(store):
    """The policy gates SEALING, not proposing — a machine may still propose
    a draft under any name; the covenant already governs who may seal it."""
    store.memory_policy_add("en", "es", ALLOWED)

    pair = memory.add_pair("hello", "hola", "en", "es",
                           status="draft", verifier=OFF_LIST, store=store)
    assert pair["status"] == "draft"


def test_supersede_pair_enforces_policy_too(store):
    """Sealing is not only add_pair — supersede_pair replaces a live sealed
    row and is a seal in every way that matters here."""
    store.memory_policy_add("en", "es", ALLOWED)
    memory.add_pair("hello", "hola", "en", "es",
                    status="sealed", verifier=ALLOWED, store=store)

    with pytest.raises(memory.VerifierNotAllowedError):
        memory.supersede_pair("hello", "hola-revised", "en", "es",
                              verifier=OFF_LIST, store=store)

    # The live row is untouched.
    hit = memory.best_sealed("hello", "en", "es", store=store)
    assert hit["pair"]["target_text"] == "hola"


# --------------------------------------------------------------------------
# policy CRUD
# --------------------------------------------------------------------------

def test_policy_add_is_idempotent(store):
    first = store.memory_policy_add("en", "es", ALLOWED)
    second = store.memory_policy_add("en", "es", ALLOWED)
    assert first["id"] == second["id"]
    rows = store.memory_policy_list("en", "es")
    assert len(rows) == 1


def test_policy_list_scopes_by_domain(store):
    store.memory_policy_add("en", "es", ALLOWED)
    store.memory_policy_add("en", "fr", OTHER_ALLOWED)

    es_rows = store.memory_policy_list("en", "es")
    assert {r["verifier"] for r in es_rows} == {ALLOWED}

    all_rows = store.memory_policy_list()
    assert {r["verifier"] for r in all_rows} == {ALLOWED, OTHER_ALLOWED}


def test_policy_remove_returns_whether_a_row_was_removed(store):
    store.memory_policy_add("en", "es", ALLOWED)

    assert store.memory_policy_remove("en", "es", ALLOWED) is True
    assert store.memory_policy_remove("en", "es", ALLOWED) is False
    assert store.memory_policy_list("en", "es") == []


def test_removing_the_last_row_restores_unrestricted(store):
    store.memory_policy_add("en", "es", ALLOWED)
    store.memory_policy_remove("en", "es", ALLOWED)

    pair = memory.add_pair("hello", "hola", "en", "es",
                           status="sealed", verifier=OFF_LIST, store=store)
    assert pair["status"] == "sealed"


def test_supports_verifier_policy_capability(store):
    assert storage.supports_verifier_policy(store) is True


# --------------------------------------------------------------------------
# CLI surface
# --------------------------------------------------------------------------

def test_cli_policy_add_list_remove(tmp_path, seal_key, capsys):
    from nestor import cli

    db = str(tmp_path / "nestor.db")
    ledger = str(tmp_path / "ledger.jsonl")

    rc = cli.main(["--db", db, "--ledger", ledger, "policy", "add",
                  "--from", "en", "--to", "es", "--verifier", ALLOWED])
    assert rc == cli.EXIT_OK
    capsys.readouterr()

    rc = cli.main(["--db", db, "--ledger", ledger, "--json", "policy", "list",
                  "--from", "en", "--to", "es"])
    assert rc == cli.EXIT_OK
    out = capsys.readouterr().out
    assert ALLOWED in out

    rc = cli.main(["--db", db, "--ledger", ledger, "policy", "remove",
                  "--from", "en", "--to", "es", "--verifier", ALLOWED])
    assert rc == cli.EXIT_OK
    capsys.readouterr()

    rc = cli.main(["--db", db, "--ledger", ledger, "--json", "policy", "list",
                  "--from", "en", "--to", "es"])
    assert rc == cli.EXIT_OK
    out = capsys.readouterr().out
    assert ALLOWED not in out
