"""Serving a model — and the one thing it cannot do.

The tests that matter here are absence tests. A model can ask Nestor anything;
it cannot seal, and that must not depend on a flag being set correctly, a
prompt being obeyed, or a client being well behaved. So: no sealing tool is
advertised, no name that sounds like one is accepted, and after a model has
called every tool this server has, the sealed memory is exactly as it was.
"""
from __future__ import annotations

import io
import json
import os

import pytest

from nestor import cascade, engine, memory, serve, storage
from nestor.curator import Curator
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def server(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'test-key'
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                    status="sealed", verifier="rita", store=store)
    from nestor.entity import EntityResolver
    from nestor.reconcile import Reconciler
    EntityResolver(store, domain="company").seal("AMZN", "Amazon", verifier="analyst")
    Reconciler(store, domain="contract", pct_tol=0.05).seal_baseline(
        "ceiling", "$1,000,000", verifier="auditor")
    return serve.Server(store=store)


def call(server, name, **args):
    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": name, "arguments": args}})
    result = response["result"]
    text = result["content"][0]["text"]
    if result.get("isError"):
        return {"error": text}
    return json.loads(text)


# --- protocol --------------------------------------------------------------

def test_initialize_answers_with_a_version_and_says_what_it_withholds(server):
    out = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": "2024-11-05",
                                    "clientInfo": {"name": "some-agent"}}})["result"]
    assert out["protocolVersion"] == "2024-11-05", "echo a version we speak"
    assert out["serverInfo"]["name"] == "nestor"
    assert "cannot seal" in out["instructions"]
    assert server.client == "some-agent"


def test_an_unknown_protocol_version_gets_the_newest_we_know(server):
    out = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": "1999-01-01"}})["result"]
    assert out["protocolVersion"] == serve.PROTOCOL_VERSIONS[0]


def test_notifications_get_no_reply_and_unknown_methods_do(server):
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    err = server.handle({"jsonrpc": "2.0", "id": 2, "method": "nope"})["error"]
    assert err["code"] == -32601


def test_the_stdio_loop_reads_lines_and_survives_junk(server):
    stdin = io.StringIO(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
        + "{ not json\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}) + "\n")
    stdout = io.StringIO()
    server.run(stdin, stdout)
    replies = [json.loads(x) for x in stdout.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [1, None, 2]
    assert replies[1]["error"]["code"] == -32700, "a bad line is reported, not fatal"


# --- what a model can do ---------------------------------------------------

def test_ask_returns_the_state_not_just_the_string(server):
    out = call(server, "nestor_ask", text="good evening",
               source_lang="en", target_lang="es")
    assert out["verified"] is True
    assert out["passage"]["state"] == "sealed"
    assert out["passage"]["meta"]["verifier"] == "rita", "a model can cite who verified it"

    nothing = call(server, "nestor_ask", text="something nobody has verified")
    assert nothing["verified"] is False and nothing["passage"]["state"] == "pending"


def test_the_other_recipes_are_reachable_too(server):
    assert call(server, "nestor_resolve", surface="AMZN", domain="company")["canonical"] == "Amazon"
    flagged = call(server, "nestor_check", label="ceiling", observed="$1,250,000",
                   domain="contract", pct_tol=0.05)
    assert flagged["flagged"] is True and flagged["variation"] == 250_000.0
    assert call(server, "nestor_match", text="GOOD EVENING", source_lang="en",
                target_lang="es")["served"] is True
    chain = call(server, "nestor_ledger_verify")
    assert chain["intact"] is True and chain["signing_enabled"] is True


def test_provenance_is_quotable(server):
    pair = server.store.memory_list(contains="evening")[0]
    out = call(server, "nestor_provenance", pair_id=pair["id"])
    assert out["verifier"] == "rita" and out["servable"] is True
    assert "no such pair" in call(server, "nestor_provenance", pair_id="nope")["error"]


def test_propose_queues_a_draft_for_a_human(server):
    out = call(server, "nestor_propose", source_text="Good afternoon.",
               candidate="Buenas tardes.")
    assert out["verified"] is False and out["state"] == "draft"
    seg = server.store.get_segment(out["segment_id"])
    assert seg["candidate"] == "Buenas tardes." and seg["status"] == "pending"
    # It is a proposal, not an answer: asking still refuses to serve it.
    assert call(server, "nestor_ask", text="Good afternoon.")["verified"] is False


def test_ollama_server_offers_a_bounded_draft_not_a_verdict(server, monkeypatch):
    provenance = engine.DraftProvenance(
        provider="ollama", model="small-code:latest", prompt_sha256="p",
        input_sha256="i", context_pair_ids=(), endpoint_scope="loopback",
        transport="ollama:/api/chat", temperature=0.0, max_output_tokens=1024,
        input_chars=12, truncated=False, created_at="now")

    class FakeOllama:
        def __init__(self, model):
            assert model == "small-code"

        def draft_task(self, task, *, excerpts, sealed_context, corpus_context):
            assert task == "Review this"
            assert excerpts == ["def f(): pass"]
            assert all(hit["pair"]["status"] == "sealed" for hit in sealed_context)
            assert corpus_context == []
            return engine.TaskDraft("Suggested change", "ollama:small-code:latest",
                                    provenance)

    monkeypatch.setattr(engine, "OllamaEngine", FakeOllama)
    server.engine_name = "ollama"
    server.ollama_model = "small-code"

    assert "nestor_draft" in [tool["name"] for tool in server.tools()]
    out = call(server, "nestor_draft", task="Review this",
               excerpts=["def f(): pass"], verifier="forged",
               corpus_dir="/etc")

    assert out["state"] == "draft" and out["verified"] is False
    assert out["draft"] == "Suggested change"
    assert out["ignored_fields"] == ["corpus_dir", "verifier"]
    assert out["seal_authority_refused"] == ["verifier"]
    assert "verifier" not in out["provenance"]


def test_draft_tool_requires_the_explicit_local_engine(server):
    assert "nestor_draft" not in [tool["name"] for tool in server.tools()]
    out = call(server, "nestor_draft", task="Review this")
    assert "requires --engine ollama" in out["error"]


def test_oversized_draft_is_refused_before_retrieval(server):
    class ForbiddenRetriever:
        def search(self, *_args, **_kwargs):
            raise AssertionError("invalid input must not reach corpus retrieval")

    server.engine_name = "ollama"
    server.corpus_retriever = ForbiddenRetriever()

    with pytest.raises(ValueError, match="task"):
        server.call(
            "nestor_draft",
            {"task": "x" * (engine.MAX_DRAFT_TASK_CHARS + 1)},
        )


# --- what a model cannot do ------------------------------------------------

def test_no_tool_can_seal_unseal_or_reject(server):
    names = [t["name"] for t in server.tools()]
    assert len(names) == len(set(names)), "no duplicate tool names"
    for verb in ("seal", "unseal", "reject", "graduate", "override", "import"):
        assert not any(verb in n for n in names), f"{verb!r} must not be offered to a model"
    assert "nestor_propose" in names


@pytest.mark.parametrize("name", ["nestor_seal", "nestor_unseal", "nestor_reject_pair",
                                  "nestor_graduate_segment", "nestor_import"])
def test_a_plausible_sealing_name_is_refused_with_the_reason(server, name):
    out = call(server, name)
    assert "not available to a model" in out["error"]
    assert "Verification is a human act" in out["error"]


def test_after_every_tool_the_sealed_memory_is_untouched(server):
    """The property, stated once: a model cannot verify anything."""
    before = Curator(server.store).summary()
    for name in [t["name"] for t in server.tools()]:
        call(server, name, text="Good evening.", surface="AMZN", label="ceiling",
             observed="1", pair_id="whatever", source_text="x", candidate="y",
             domain="company")
    after = Curator(server.store).summary()
    assert after["sealed"] == before["sealed"]
    assert after["verifiers"] == before["verifiers"]


def test_read_only_withholds_even_the_proposal(server):
    server.read_only = True
    assert "nestor_propose" not in [t["name"] for t in server.tools()]
    assert "read-only" in call(server, "nestor_propose", source_text="a", candidate="b")["error"]


def test_a_bad_argument_comes_back_as_a_readable_tool_error(server):
    """The model must be able to read the refusal and change what it does."""
    assert "nothing to ask" in call(server, "nestor_ask", text="  ")["error"]
    assert "unknown matcher" in call(server, "nestor_match", text="x", matcher="vector")["error"]
    bad = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                         "params": {"name": "nestor_ask", "arguments": "not-an-object"}})
    assert bad["error"]["code"] == -32602
