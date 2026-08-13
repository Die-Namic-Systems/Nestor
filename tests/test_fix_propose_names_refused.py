"""nestor_propose names the seal-authority fields it refuses (issue #98).

The covenant is: a model may propose, it may not confirm. Before the fix, a
model that called ``nestor_propose`` with ``status="sealed"``,
``verifier="…"`` and ``verification_kind="human"`` got back an unqualified
"queued for human review" note. The write did the right thing — the row landed
as a draft and nothing sealed — but the *reply* said nothing about the fields
that tried to cross the boundary. A refusal that does not read as one.

These tests assert the wire now names the refused keys and says why, while the
underlying guarantee is unchanged: still a draft, still nothing sealed.
"""
from __future__ import annotations

import json
import os

import pytest

from nestor import cascade, memory, serve, storage
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
    return serve.Server(store=store)


def call(server, name, **args):
    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": name, "arguments": args}})
    result = response["result"]
    text = result["content"][0]["text"]
    if result.get("isError"):
        return {"error": text}
    return json.loads(text)


SEAL_ATTEMPT = dict(source_text="Good afternoon.", candidate="Buenas tardes.",
                    status="sealed", verifier="x", verification_kind="human")


def test_a_seal_attempt_is_named_in_the_reply(server):
    """The regression guard: the response must NAME the refused keys.

    Before the fix this returned a generic draft note with no mention of
    status/verifier/verification_kind — so this assertion was red.
    """
    out = call(server, "nestor_propose", **SEAL_ATTEMPT)
    blob = json.dumps(out)
    for key in ("status", "verifier", "verification_kind"):
        assert key in blob, f"the refused field {key!r} must be named in the reply"
    # And named apart as seal authority, with the reason it was dropped.
    assert set(out["seal_authority_refused"]) == {"status", "verifier",
                                                  "verification_kind"}
    assert "propose, not confirm" in out["note"]


def test_the_row_still_lands_as_a_draft_and_nothing_seals(server):
    """Naming the refusal must not change what actually happens: still a draft."""
    before = Curator(server.store).summary()
    out = call(server, "nestor_propose", **SEAL_ATTEMPT)
    assert out["verified"] is False and out["state"] == "draft"
    seg = server.store.get_segment(out["segment_id"])
    assert seg["candidate"] == "Buenas tardes." and seg["status"] == "pending"
    after = Curator(server.store).summary()
    assert after["sealed"] == before["sealed"], "no new seal from a proposal"
    assert after["verifiers"] == before["verifiers"], "no verifier recorded"


def test_a_clean_proposal_names_nothing(server):
    """No unknown keys → no refusal noise; the note stays the plain draft note."""
    out = call(server, "nestor_propose", source_text="Good afternoon.",
               candidate="Buenas tardes.")
    assert "ignored_fields" not in out
    assert "seal_authority_refused" not in out
    assert out["state"] == "draft"
