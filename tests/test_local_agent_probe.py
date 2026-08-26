"""The live local-agent probe refuses to manufacture its own prerequisite."""
from __future__ import annotations

import argparse

from scripts import local_agent_probe


def test_probe_stops_before_ollama_when_no_human_seal_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("NESTOR_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("NESTOR_DB", raising=False)
    monkeypatch.delenv("NESTOR_LEDGER", raising=False)
    monkeypatch.setattr(
        local_agent_probe.serve.Server,
        "call",
        lambda self, name, args: {
            "served": False,
        } if name == "nestor_match" else (_ for _ in ()).throw(
            AssertionError("the probe must stop before local drafting")),
    )
    args = argparse.Namespace(
        sealed_query="guidance", task="review", excerpt=[],
        model="small-code", propose=False,
        source_lang="decision", target_lang="decision")

    code, result = local_agent_probe.run(args)

    assert code == 2
    assert result["status"] == "prerequisite-missing"
    assert result["state"] == "pending"
    assert result["store"] == str(tmp_path / "home" / "keep" / "nestor.db")
    assert (tmp_path / "home" / "keep").is_dir()
