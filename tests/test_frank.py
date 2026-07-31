import hashlib
import json

import pytest

from nestor import cascade, frank, memory
from nestor.engine import OfflineEngine

from conftest import read_ledger


class RecordingForwarder:
    """Captures (event_type, content) instead of talking to willow-mcp."""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __call__(self, event_type, content):
        self.calls.append((event_type, content))
        if self.fail:
            raise frank.FrankUnavailable("simulated outage")


# ── the seam ──────────────────────────────────────────────────────────────────


def test_no_forwarder_by_default_and_ledger_unchanged(store):
    assert frank.get_forwarder() is None
    cascade.translate_segment("Hello there.", "en", "es",
                              engine=OfflineEngine(), store=store)
    assert len(read_ledger()) == 1


def test_set_forwarder_rejects_non_callable():
    with pytest.raises(TypeError):
        frank.set_forwarder(object())


def test_event_type_namespaces_the_kind():
    assert frank.event_type_for({"kind": "seal"}) == "nestor.seal"
    assert frank.event_type_for({"kind": "passage"}) == "nestor.passage"
    assert frank.event_type_for({}) == "nestor.entry"


# ── forwarding ────────────────────────────────────────────────────────────────


def test_every_ledger_entry_is_forwarded(store):
    fwd = RecordingForwarder()
    frank.set_forwarder(fwd)

    memory.add_pair("Good morning", "Buenos días", "en", "es",
                    status="sealed", verifier="tester", store=store)
    cascade.translate_segment("Good morning", "en", "es",
                              engine=OfflineEngine(), store=store)

    # Two entries, two forwards: the seal itself and the passage that served
    # from it. `add_pair` used to write nothing, so this read `== 1`.
    assert [e for e, _ in fwd.calls] == ["nestor.seal", "nestor.passage"]
    _, sealed = fwd.calls[0]
    assert sealed["verifier"] == "tester" and sealed["source_lang"] == "en"
    _, content = fwd.calls[1]
    assert content["source_lang"] == "en"
    assert content["tier"] == 1


def test_forwarded_content_cross_links_the_local_line(store):
    fwd = RecordingForwarder()
    frank.set_forwarder(fwd)
    cascade.translate_segment("Hello there.", "en", "es",
                              engine=OfflineEngine(), store=store)

    _, content = fwd.calls[0]
    line = json.dumps(read_ledger()[0], ensure_ascii=False)
    assert content["local_hash"] == hashlib.sha256(line.encode("utf-8")).hexdigest()
    # The mirror carries the local chain link too, so FRANK can verify order.
    assert content["prev"] == "genesis"


def test_seal_entries_forward_as_their_own_event(store):
    doc = store.create_document("t", "en", "es")
    seg = store.create_segment(doc["id"], 0, "The quick brown fox",
                               "El zorro marrón rápido", 0.5)
    fwd = RecordingForwarder()
    frank.set_forwarder(fwd)

    cascade.graduate_segment(seg["id"], verifier="tester", store=store)

    # The pair-level seal (from add_pair) and the segment-level decision.
    assert [e for e, _ in fwd.calls] == ["nestor.seal", "nestor.segment_sealed"]


# ── best-effort contract ──────────────────────────────────────────────────────


def test_forwarder_failure_does_not_fail_the_translation(store):
    frank.set_forwarder(RecordingForwarder(fail=True))
    p = cascade.translate_segment("Hello there.", "en", "es",
                                  engine=OfflineEngine(), store=store)
    assert p.state == "pending"
    assert len(read_ledger()) == 1   # local ledger is still the source of truth


def test_strict_mode_surfaces_forwarder_failure(store, monkeypatch):
    monkeypatch.setenv("NESTOR_FRANK_STRICT", "1")
    frank.set_forwarder(RecordingForwarder(fail=True))
    with pytest.raises(frank.FrankUnavailable):
        cascade.translate_segment("Hello there.", "en", "es",
                                  engine=OfflineEngine(), store=store)
    assert len(read_ledger()) == 1   # written before the forward was attempted


# ── the willow-mcp adapter ────────────────────────────────────────────────────


def test_willow_forwarder_speaks_mcp_and_calls_frank_append(monkeypatch, tmp_path):
    """Drive the adapter against a stub MCP server over real pipes."""
    server = tmp_path / "stub_server.py"
    server.write_text(
        "import json, pathlib, sys\n"
        f"log = pathlib.Path({str(tmp_path / 'calls.jsonl')!r})\n"
        "calls = []\n"
        "for line in sys.stdin:\n"
        "    line = line.strip()\n"
        "    if not line:\n"
        "        continue\n"
        "    msg = json.loads(line)\n"
        "    if msg.get('method') == 'initialize':\n"
        "        out = {'jsonrpc': '2.0', 'id': msg['id'],\n"
        "               'result': {'serverInfo': {'name': 'stub'}}}\n"
        "    elif msg.get('method') == 'tools/call':\n"
        "        calls.append(msg['params'])\n"
        "        log.write_text(json.dumps(calls))\n"
        "        body = {'id': 'abc', 'project': msg['params']['arguments']['project'],\n"
        "                'event_type': msg['params']['arguments']['event_type']}\n"
        "        out = {'jsonrpc': '2.0', 'id': msg['id'],\n"
        "               'result': {'content': [{'type': 'text', 'text': json.dumps(body)}]}}\n"
        "    else:\n"
        "        continue\n"
        "    sys.stdout.write(json.dumps(out) + '\\n')\n"
        "    sys.stdout.flush()\n",
        encoding="utf-8",
    )
    import sys

    monkeypatch.setenv("WILLOW_MCP_COMMAND", json.dumps([sys.executable, str(server)]))
    monkeypatch.setenv("WILLOW_APP_ID", "nestor")

    with frank.willow_forwarder() as fwd:
        fwd("nestor.passage", {"kind": "passage", "tier": 1})
        fwd("nestor.seal", {"kind": "seal"})     # one handshake serves many entries
        seen = json.loads((tmp_path / "calls.jsonl").read_text())

    assert [c["name"] for c in seen] == ["frank_append", "frank_append"]
    args = seen[0]["arguments"]
    assert args["app_id"] == "nestor"
    assert args["project"] == "nestor"
    assert args["event_type"] == "nestor.passage"
    assert args["content"] == {"kind": "passage", "tier": 1}


def test_willow_forwarder_raises_on_in_band_tool_error(monkeypatch, tmp_path):
    """A gate denial comes back as {"error": ...} in the tool payload, not as a
    JSON-RPC error — it must still be treated as a failure."""
    import sys

    server = tmp_path / "denying_server.py"
    server.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    line = line.strip()\n"
        "    if not line:\n"
        "        continue\n"
        "    msg = json.loads(line)\n"
        "    if 'id' not in msg:\n"
        "        continue\n"
        "    if msg.get('method') == 'initialize':\n"
        "        result = {'serverInfo': {'name': 'stub'}}\n"
        "    else:\n"
        "        result = {'content': [{'type': 'text',\n"
        "                  'text': json.dumps({'error': 'permission_denied: frank_append'})}]}\n"
        "    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': msg['id'],\n"
        "                                 'result': result}) + '\\n')\n"
        "    sys.stdout.flush()\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("WILLOW_MCP_COMMAND", json.dumps([sys.executable, str(server)]))

    fwd = frank.willow_forwarder()
    try:
        with pytest.raises(frank.FrankUnavailable, match="permission_denied"):
            fwd("nestor.passage", {"kind": "passage"})
    finally:
        fwd.close()


def test_willow_forwarder_reports_an_unstartable_server(monkeypatch):
    monkeypatch.setenv("WILLOW_MCP_COMMAND", json.dumps(["/nonexistent/willow-mcp"]))
    fwd = frank.willow_forwarder()
    with pytest.raises(frank.FrankUnavailable, match="could not start"):
        fwd("nestor.passage", {"kind": "passage"})


def test_willow_mcp_command_accepts_a_plain_string(monkeypatch):
    monkeypatch.setenv("WILLOW_MCP_COMMAND", "python3 -m willow_mcp")
    assert frank._default_command() == ["python3", "-m", "willow_mcp"]
