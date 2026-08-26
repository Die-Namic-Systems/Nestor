#!/usr/bin/env python3
"""Exercise the shared Nestor → Ollama → review-queue path without sealing.

The probe requires a phrase already sealed by a human in the household store.
That prerequisite is deliberate: manufacturing a seal to make this demo green
would disprove the boundary it is intended to exercise.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from nestor import cascade, home_init, home_paths, serve, storage
from nestor.sqlite_store import SqliteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sealed-query", required=True,
                        help="phrase a human already sealed in the household store")
    parser.add_argument("--task", required=True, help="bounded task for local drafting")
    parser.add_argument("--excerpt", action="append", default=[],
                        help="inert source excerpt; repeat up to eight times")
    parser.add_argument("--model", default="llama3.2:3b",
                        help="installed loopback Ollama model tag")
    parser.add_argument("--propose", action="store_true",
                        help="explicitly queue the returned draft for human review")
    parser.add_argument("--source-lang", default="decision")
    parser.add_argument("--target-lang", default="decision")
    return parser


def run(args: argparse.Namespace) -> tuple[int, dict]:
    root = Path(os.environ.get("NESTOR_HOME", "~/.nestor")).expanduser()
    os.environ["NESTOR_HOME"] = str(root)
    home_init.ensure_home_layout(root)
    db = Path(os.environ.get("NESTOR_DB", root / "keep" / "nestor.db")).expanduser()
    ledger = Path(os.environ.get(
        "NESTOR_LEDGER", root / "keep" / "ledger.jsonl")).expanduser()
    os.environ["NESTOR_DB"] = str(db)
    os.environ["NESTOR_LEDGER"] = str(ledger)
    cascade.set_ledger_path(ledger)

    store = SqliteStore(db)
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    server = serve.Server(
        store=store,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        source_lang_explicit=True,
        target_lang_explicit=True,
        engine_name="ollama",
        ollama_model=args.model,
        client="local-agent-probe",
    )

    # Match, do not ask: ask would invoke the configured Ollama engine on a
    # miss and turn the prerequisite check into the drafting step it gates.
    sealed = server.call("nestor_match", {
        "text": args.sealed_query,
        "source_lang": args.source_lang,
        "target_lang": args.target_lang,
    })
    if not sealed.get("served"):
        return 2, {
            "status": "prerequisite-missing",
            "store": str(db),
            "ledger": str(home_paths.ledger_for(db)),
            "sealed_query": args.sealed_query,
            "state": "pending",
            "next": "seal this guidance as a human in nestor ui, then rerun",
        }

    drafted = server.call("nestor_draft", {
        "task": args.task,
        "excerpts": args.excerpt,
        "source_lang": args.source_lang,
        "target_lang": args.target_lang,
    })
    sealed_pair = sealed["matches"][0]
    result = {
        "status": "drafted",
        "store": str(db),
        "ledger": str(home_paths.ledger_for(db)),
        "sealed": {
            "state": "sealed",
            "pair_id": sealed_pair["id"],
            "verifier": sealed_pair["verifier"],
        },
        "draft": drafted,
    }
    if args.propose:
        result["proposal"] = server.call("nestor_propose", {
            "source_text": args.task,
            "candidate": drafted["draft"],
            "source_lang": args.source_lang,
            "target_lang": args.target_lang,
            "title": "local-agent-prototype",
        })
    return 0, result


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    code, result = run(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
