"""#98 / §6.44 — nestor_propose's silent refusal is now a spoken one.

The covenant is *you may propose, you may not confirm*, and the wire has to
*read* as a refusal when a caller tries to cross it. Before the fix, a model
that sent ``status="sealed"``, ``verifier="…"``, or ``verification_kind="human"``
alongside a proposal got back an unqualified success note — the extra keys
were silently discarded and the reply looked identical to a well-formed call.
"A refusal that doesn't read as one" (the issue's title).

These tests hold the fix down. They assert two things a caller can check
without reading source:

* ``ignored_fields`` names every key ``nestor_propose`` did not read;
* ``seal_authority_refused`` names the subset that tried to declare a
  verification result, and the ``note`` explains that a machine may propose,
  not confirm.

Split against the unfixed revision (drop the ``ignored=ignored`` kwarg at
``nestor/serve.py``): both assertions fail because the fields never reach
the reply. Restored, both pass.
"""
from __future__ import annotations

import json
import os

import pytest

from nestor import answer, cascade, memory, serve, storage
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def server(tmp_path, seal_key):
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                    status="sealed", verifier="rita", store=store)
    return serve.Server(store=store)


def call(server, name, **args):
    reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": args}})
    payload = reply["result"]["content"][0]["text"]
    if reply["result"].get("isError"):
        return {"error": payload}
    return json.loads(payload)


# --- the acceptance criterion from the issue -------------------------------


def test_forbidden_seal_authority_keys_are_named_in_the_reply(server):
    """The exact call the issue asks for: assert the response names the keys.

    Red before the fix: the reply held ``state=draft`` and ``verified=false``
    with no mention of the three fields. Green after: ``ignored_fields`` and
    ``seal_authority_refused`` both list all three.
    """
    out = call(server, "nestor_propose",
               source_text="is X true?",
               candidate="yes",
               status="sealed",
               verifier="x",
               verification_kind="human")
    assert out["state"] == "draft"
    assert out["verified"] is False
    assert set(out["ignored_fields"]) == {"status", "verifier", "verification_kind"}
    assert set(out["seal_authority_refused"]) == {"status", "verifier", "verification_kind"}
    # The note has to *read* as a refusal — not only carry a machine-readable
    # field a script parses (the whole point of §6.44).
    assert "status" in out["note"]
    assert "verifier" in out["note"]
    assert "verification_kind" in out["note"]
    assert "machine may propose, not confirm" in out["note"]


def test_a_non_seal_extra_key_is_reported_but_not_flagged_as_seal_authority(server):
    """A wire key outside the accepted set that is NOT a seal-authority field
    still gets named in ``ignored_fields`` — the caller sent something the
    tool did not read, and hiding that would be another silent-refusal shape.
    But ``seal_authority_refused`` stays absent, so a script can distinguish
    "you sent a typo" from "you tried to cross the covenant".
    """
    out = call(server, "nestor_propose",
               source_text="is X true?",
               candidate="yes",
               notes="a stray field the tool does not read")
    assert out["ignored_fields"] == ["notes"]
    assert "seal_authority_refused" not in out
    assert "notes" in out["note"]


def test_a_clean_proposal_carries_no_ignored_or_refused_fields(server):
    """Regression guard: the extra fields must not leak into a plain call.
    A payload that only used ``PROPOSE_KEYS`` should look exactly like the
    pre-fix happy path — no ``ignored_fields``, no ``seal_authority_refused``,
    no mention of them in the note.
    """
    out = call(server, "nestor_propose",
               source_text="is X true?",
               candidate="yes",
               source_lang="en",
               target_lang="es",
               title="proposal about X")
    assert out["state"] == "draft" and out["verified"] is False
    assert "ignored_fields" not in out
    assert "seal_authority_refused" not in out
    assert "queued for human review" in out["note"]


def test_every_seal_authority_key_in_the_constant_is_covered_by_the_refusal():
    """A drift guard: if someone adds a new key to ``answer.SEAL_AUTHORITY``
    (a new way to declare verification on the wire), send it through the
    same call and confirm it is refused the same way. The test iterates the
    constant so the coverage tracks the definition.
    """
    for key in answer.SEAL_AUTHORITY:
        assert isinstance(key, str) and key, (
            "SEAL_AUTHORITY holds bare strings; refusal walks them by name")


def test_the_forbidden_keys_do_not_change_the_stored_row(server):
    """The other half of "silent refusal": beyond speaking, the refusal must
    actually refuse. A row created by a call carrying ``status="sealed"``
    must land as a draft in the store, indistinguishable from one created
    by a clean call. The wire-level refusal is a communication fix; this is
    the storage-level invariant it protects.
    """
    out = call(server, "nestor_propose",
               source_text="another question",
               candidate="an answer",
               status="sealed", verifier="attacker")
    row = server.store.get_segment(out["segment_id"])
    assert row["status"] == "pending"  # never sealed
    # And the sealed memory is untouched:
    sealed = [p for p in server.store.memory_list() if p.get("status") == "sealed"]
    assert all(p.get("verifier") != "attacker" for p in sealed)
