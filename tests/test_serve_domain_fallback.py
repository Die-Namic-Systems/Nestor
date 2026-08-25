"""MCP server ``nestor_ask`` / ``nestor_match``: same store-aware domain
fallback the CLI has (issue #203, sibling to decision 0184 which extended it
from ``cmd_ask`` to ``cmd_match``).

The rule, unchanged from the CLI half: the configured ``en → es`` default
wins when the store holds it, or when either the model *or* the operator
named a domain explicitly; otherwise the largest domain the store actually
holds wins. An empty store keeps the configured default.

On the MCP surface the operator's startup flag plays the CLI human's role.
A server built without ``source_lang_explicit`` behaves as "the operator
accepted the built-in default", so a store seeded only in
``decision → commitment`` answers a bare ``nestor_ask`` the same as
``nestor ask`` without ``--from``/``--to`` does today.
"""
from __future__ import annotations

import json
import os

import pytest

from nestor import cascade, domain, memory, serve, storage
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path, seal_key):
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    s.memory_init()
    storage.set_store(s)
    return s


def call(server, name, **args):
    reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": args}})
    payload = reply["result"]["content"][0]["text"]
    if reply["result"].get("isError"):
        return {"error": payload}
    return json.loads(payload)


# --- Server._domain_for_read, the unit ---------------------------------------


def test_the_operator_accepted_default_defers_to_the_stores_largest_domain(store):
    memory.add_pair("may we ship?", "yes", "decision", "commitment",
                    status="sealed", verifier="rita", store=store)
    memory.add_pair("may we ship again?", "yes", "decision", "commitment",
                    status="sealed", verifier="rita", store=store)
    server = serve.Server(store=store)  # no explicit flags
    assert server._domain_for_read({}) == ("decision", "commitment")


def test_operator_pinned_domain_is_honoured_even_when_the_store_lacks_it(store):
    memory.add_pair("may we ship?", "yes", "decision", "commitment",
                    status="sealed", verifier="rita", store=store)
    server = serve.Server(store=store, source_lang="en", target_lang="es",
                          source_lang_explicit=True, target_lang_explicit=True)
    # The operator asked for en→es; the fallback must not second-guess them
    # even though the store holds only decision→commitment.
    assert server._domain_for_read({}) == ("en", "es")


def test_model_explicit_domain_wins_over_the_operator_default(store):
    memory.add_pair("may we ship?", "yes", "decision", "commitment",
                    status="sealed", verifier="rita", store=store)
    server = serve.Server(store=store)
    assert server._domain_for_read({"source_lang": "fr", "target_lang": "de"}) == ("fr", "de")


def test_empty_store_keeps_the_built_in_default(store):
    server = serve.Server(store=store)
    assert server._domain_for_read({}) == (domain.DEFAULT_SOURCE_LANG,
                                            domain.DEFAULT_TARGET_LANG)


def test_store_holds_the_default_so_the_default_wins(store):
    memory.add_pair("hello", "hola", "en", "es",
                    status="sealed", verifier="rita", store=store)
    for i in range(5):
        memory.add_pair(f"decision {i}?", "yes", "decision", "commitment",
                        status="sealed", verifier="rita", store=store)
    server = serve.Server(store=store)
    # Membership beats size: en→es is present, so en→es keeps winning.
    assert server._domain_for_read({}) == ("en", "es")


# --- end to end through nestor_ask -------------------------------------------


def test_nestor_ask_finds_a_decision_only_store_without_domain_args(store):
    memory.add_pair("may we ship?", "yes", "decision", "commitment",
                    status="sealed", verifier="rita", store=store)
    server = serve.Server(store=store)
    out = call(server, "nestor_ask", text="may we ship?")
    # Before the fix this returned pending, because the built-in en→es default
    # was silently used against a store that had nothing there.
    assert out["verified"] is True
    assert out["passage"]["state"] == "sealed"
    assert out["passage"]["target"] == "yes"


def test_nestor_match_finds_a_decision_only_store_without_domain_args(store):
    memory.add_pair("may we ship?", "yes", "decision", "commitment",
                    status="sealed", verifier="rita", store=store)
    server = serve.Server(store=store)
    out = call(server, "nestor_match", text="may we ship?")
    assert out["served"] is True
    assert out["target"] == "yes"


def test_operator_pinned_default_stays_pinned_on_nestor_ask(store):
    memory.add_pair("may we ship?", "yes", "decision", "commitment",
                    status="sealed", verifier="rita", store=store)
    server = serve.Server(store=store, source_lang="en", target_lang="es",
                          source_lang_explicit=True, target_lang_explicit=True)
    out = call(server, "nestor_ask", text="may we ship?")
    # The operator asked for en→es explicitly; the fallback must not switch
    # domains behind their back. Nothing in en→es → pending.
    assert out["verified"] is False
    assert out["passage"]["state"] == "pending"


# --- main() wires the parser defaults into the explicit flags ---------------


def test_main_parser_defaults_read_as_not_explicit(tmp_path, monkeypatch):
    """A ``nestor serve`` invocation with no ``--source-lang``/``--target-lang``
    must produce a Server whose ``*_explicit`` flags are False, so the
    store-aware fallback engages.
    """
    captured: dict = {}

    def spy(**kwargs):
        captured.update(kwargs)
        # Return something that keeps main() from hanging on stdio.
        raise SystemExit(0)

    monkeypatch.setattr(serve, "Server", spy)
    # Give main() a scratch DB path; it never gets far enough to open it here
    # because our spy exits before server.run().
    scratch = tmp_path / "nestor.db"
    with pytest.raises(SystemExit):
        serve.main(["--db", str(scratch)])
    assert captured["source_lang_explicit"] is False
    assert captured["target_lang_explicit"] is False
    assert captured["source_lang"] == domain.DEFAULT_SOURCE_LANG
    assert captured["target_lang"] == domain.DEFAULT_TARGET_LANG


def test_main_records_operator_flags_as_explicit(tmp_path, monkeypatch):
    captured: dict = {}

    def spy(**kwargs):
        captured.update(kwargs)
        raise SystemExit(0)

    monkeypatch.setattr(serve, "Server", spy)
    scratch = tmp_path / "nestor.db"
    with pytest.raises(SystemExit):
        serve.main(["--db", str(scratch),
                    "--source-lang", "decision", "--target-lang", "commitment"])
    assert captured["source_lang_explicit"] is True
    assert captured["target_lang_explicit"] is True
    assert captured["source_lang"] == "decision"
    assert captured["target_lang"] == "commitment"
