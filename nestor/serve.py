"""Serving Nestor to a model — MCP over stdio, and one refusal.

A model can ask this server anything Nestor knows. It cannot seal, unseal,
reject, override a conflict, or import a bundle. Those tools are not gated
behind a permission flag or a config option that ships disabled: **they do not
exist in this file**. There is no argument to `nestor_ask` that seals, and no
sequence of calls that ends in a verified pair.

That is the product, not a precaution. Nestor's answer to "has a human checked
this?" is worth exactly as much as the difficulty of getting a machine's output
marked as checked. A server that let a model seal — even carefully, even with a
confirmation string — would be a system where the machine grades its own work,
which is the thing the ledger, the signatures and the three states are all built
to prevent. So the one write a model gets is :func:`~nestor.answer.propose`: put
a candidate in the queue where a human will see it, marked `draft`, exactly
where a tier-2 engine's output lands.

What the model gets back is the *state*, not just a string — ``verified``, the
verifier's name, the confidence, the candidates and what they scored. An agent
holding that can say "verified by rita" and mean it, quote a pair id an auditor
can look up later, or decline to answer because nothing was sealed. Handing back
only the text would make Nestor an ordinary cache.

Run it::

    nestor serve --db data/nestor.db          # MCP over stdio
    python -m nestor.serve --db data/nestor.db

Wire it into a client (Claude Desktop, Claude Code, any MCP host)::

    {"mcpServers": {"nestor": {"command": "nestor",
                               "args": ["serve", "--db", "data/nestor.db"],
                               "env": {"NESTOR_SEAL_KEY": "…"}}}}

Stdlib only: MCP over stdio is newline-delimited JSON-RPC 2.0, which is a
``json.loads`` per line. No SDK, so the zero-dependency core is preserved.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Optional, TextIO

from . import answer, cascade, ledger as ledger_mod, memory, signing, storage
from .sqlite_store import SqliteStore
from .storage import Storage

SERVER_NAME = "nestor"
SERVER_VERSION = "0.1.0"
# Versions of the MCP spec this server knows how to speak. A client asking for
# one of these gets it back; anything else is answered with the newest we know,
# which is what the spec prescribes for an unknown version.
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

MAX_MESSAGE = 1 << 20       # 1 MiB — a tool call is never larger than this

# What a model may never do here, kept as data so the refusal is greppable and
# so `describe()` can state it to whoever is wiring the server up.
WITHHELD = ("seal", "unseal", "reject", "override a conflicting seal",
            "import a bundle", "edit the ledger")


@dataclass
class Server:
    """The tool surface. ``read_only`` removes even the proposal."""

    store: Storage
    source_lang: str = "en"
    target_lang: str = "es"
    engine_name: str = "offline"
    read_only: bool = False
    client: str = "unknown-client"
    _initialized: bool = field(default=False, repr=False)

    # -- the tools --------------------------------------------------------

    def tools(self) -> list[dict]:
        """MCP tool descriptors. Every write-shaped verb is absent by design."""
        domain = {"source_lang": {"type": "string",
                                  "description": f"source domain tag (default {self.source_lang!r})"},
                  "target_lang": {"type": "string",
                                  "description": f"target domain tag (default {self.target_lang!r})"}}
        out = [
            {
                "name": "nestor_ask",
                "description":
                    "Ask Nestor for a verified answer to a phrase. Returns one of three "
                    "states: 'sealed' (a human verified it — serve it verbatim and cite "
                    "the verifier), 'draft' (a machine produced it — do NOT present it as "
                    "verified), 'pending' (nothing verified matched — say so rather than "
                    "improvising). Also returns the ranked candidates and their scores.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string", "description": "the phrase to look up"},
                                   **domain},
                    "required": ["text"],
                },
            },
            {
                "name": "nestor_resolve",
                "description":
                    "Resolve a surface form (an alias, a spelling, a ticker) to its canonical "
                    "entity using a human-sealed alias graph. Returns the canonical entity only "
                    "when a human verified that mapping; below the threshold it returns an "
                    "unsealed suggestion, which is a candidate for review and not an answer.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"surface": {"type": "string"},
                                   "domain": {"type": "string",
                                              "description": "entity domain, e.g. 'company'"}},
                    "required": ["surface"],
                },
            },
            {
                "name": "nestor_check",
                "description":
                    "Check a figure against the human-sealed baseline for a label. Returns "
                    "within_tolerance / flagged with the exact absolute and proportional "
                    "variation, or baseline=null when no verified baseline exists. Use this "
                    "instead of asserting that two numbers agree.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "description": "e.g. 'ceiling'"},
                        "observed": {"type": "string", "description": "the figure to check"},
                        "domain": {"type": "string"},
                        "abs_tol": {"type": "number"}, "pct_tol": {"type": "number"},
                    },
                    "required": ["label", "observed"],
                },
            },
            {
                "name": "nestor_match",
                "description":
                    "The bare mechanic over any domain: normalize a value, score it against the "
                    "sealed pairs, and report whether it would be served as verified. Use for a "
                    "custom domain built on the string or numeric matcher.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}, **domain,
                                   "matcher": {"type": "string", "enum": list(answer.MATCHERS)},
                                   "abs_tol": {"type": "number"}, "pct_tol": {"type": "number"}},
                    "required": ["text"],
                },
            },
            {
                "name": "nestor_provenance",
                "description":
                    "Who verified a pair, when, with what origin, and every rejection recorded "
                    "against it. Quote this instead of asserting confidence.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"pair_id": {"type": "string"}},
                    "required": ["pair_id"],
                },
            },
            {
                "name": "nestor_ledger_verify",
                "description":
                    "Verify the hash-chained audit ledger and report the memory's counts. A "
                    "broken chain means the trail has been tampered with; say so plainly.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
        if not self.read_only:
            out.append({
                "name": "nestor_propose",
                "description":
                    "Queue YOUR answer for a human to review. This is the only write available: "
                    "the candidate lands as a 'draft' in the review queue and is never served as "
                    "verified. You cannot seal it — a human does that, or nobody does.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_text": {"type": "string", "description": "what was asked"},
                        "candidate": {"type": "string", "description": "your proposed answer"},
                        **domain,
                        "title": {"type": "string", "description": "optional queue grouping"},
                    },
                    "required": ["source_text", "candidate"],
                },
            })
        return out

    def call(self, name: str, args: dict) -> dict:
        """Run one tool. Unknown or withheld names get a clear refusal."""
        store = self.store
        sl = str(args.get("source_lang") or self.source_lang)
        tl = str(args.get("target_lang") or self.target_lang)
        if name == "nestor_ask":
            return answer.ask(store, str(args.get("text", "")), sl, tl,
                              engine_name=self.engine_name)
        if name == "nestor_resolve":
            return answer.resolve(store, str(args.get("surface", "")),
                                  str(args.get("domain") or "entity"))
        if name == "nestor_check":
            return answer.check(store, str(args.get("label", "")),
                                str(args.get("observed", "")),
                                domain=str(args.get("domain") or "value"),
                                abs_tol=float(args.get("abs_tol") or 0.0),
                                pct_tol=float(args.get("pct_tol") or 0.05))
        if name == "nestor_match":
            return answer.match(store, str(args.get("text", "")), sl, tl,
                                matcher=str(args.get("matcher") or "string"),
                                abs_tol=float(args.get("abs_tol") or 0.0),
                                pct_tol=float(args.get("pct_tol") or 0.05))
        if name == "nestor_provenance":
            found = answer.provenance(store, str(args.get("pair_id", "")))
            if found is None:
                raise ValueError("no such pair")
            return found
        if name == "nestor_ledger_verify":
            ok, detail = ledger_mod.verify()
            return {"intact": ok, "detail": detail, "path": str(cascade._ledger_path()),
                    "signing_enabled": signing.signing_enabled(),
                    "memory": memory.stats(store=store)}
        if name == "nestor_propose":
            if self.read_only:
                raise PermissionError("this server is running --read-only; even a "
                                      "proposal is refused.")
            return answer.propose(store, str(args.get("source_text", "")),
                                  str(args.get("candidate", "")), sl, tl,
                                  title=str(args.get("title") or ""),
                                  origin=f"mcp:{self.client}")
        if name.startswith("nestor_"):
            raise PermissionError(
                f"{name!r} is not available to a model. This server deliberately "
                f"withholds: {', '.join(WITHHELD)}. Verification is a human act — "
                f"use nestor_propose to put an answer in front of one.")
        raise ValueError(f"unknown tool {name!r}")

    # -- JSON-RPC ---------------------------------------------------------

    def handle(self, request: Any) -> Optional[dict]:
        """One JSON-RPC message in, one response out (``None`` for notifications)."""
        if not isinstance(request, dict):
            return _error(None, -32600, "invalid request: not an object")
        rid = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        is_notification = "id" not in request

        try:
            if method == "initialize":
                want = str(params.get("protocolVersion") or "")
                info = params.get("clientInfo") or {}
                self.client = str(info.get("name") or self.client)
                self._initialized = True
                return _result(rid, {
                    "protocolVersion": want if want in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "instructions": describe(self),
                })
            if method in ("notifications/initialized", "notifications/cancelled"):
                return None
            if method == "ping":
                return _result(rid, {})
            if method == "tools/list":
                return _result(rid, {"tools": self.tools()})
            if method == "tools/call":
                name = str(params.get("name", ""))
                args = params.get("arguments") or {}
                if not isinstance(args, dict):
                    return _error(rid, -32602, "arguments must be an object")
                try:
                    payload = self.call(name, args)
                except (ValueError, PermissionError, RuntimeError) as exc:
                    # A refusal is a tool result, not a protocol error: the model
                    # needs to read it and change what it does, and a JSON-RPC
                    # error is not shown to it in most clients.
                    return _result(rid, {"content": [{"type": "text",
                                                      "text": f"{type(exc).__name__}: {exc}"}],
                                         "isError": True})
                return _result(rid, {"content": [{"type": "text",
                                                  "text": json.dumps(payload, indent=2,
                                                                     ensure_ascii=False,
                                                                     default=str)}]})
            if is_notification:
                return None
            return _error(rid, -32601, f"method not found: {method}")
        except Exception as exc:                    # noqa: BLE001 — never kill the loop
            if is_notification:
                return None
            return _error(rid, -32603, f"{type(exc).__name__}: {exc}")

    def run(self, stdin: TextIO, stdout: TextIO) -> None:
        """Read newline-delimited JSON-RPC from ``stdin`` until EOF."""
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            if len(line) > MAX_MESSAGE:
                # The browser surface caps its bodies; this one is spoken to by
                # a model, which is the caller most likely to send something
                # enormous by accident.
                _write(stdout, _error(None, -32600,
                                      f"message too large ({len(line)} bytes; "
                                      f"limit {MAX_MESSAGE})"))
                continue
            try:
                request = json.loads(line)
            except ValueError as exc:
                _write(stdout, _error(None, -32700, f"parse error: {exc}"))
                continue
            for req in (request if isinstance(request, list) else [request]):
                response = self.handle(req)
                if response is not None:
                    _write(stdout, response)


def describe(server: Server) -> str:
    """The instructions a client shows its model. Says what is withheld, and why."""
    return (
        "Nestor answers one question about an answer: has a human checked it?\n"
        "Every result carries a state — 'sealed' (verified by a named human; serve it "
        "verbatim and cite them), 'draft' (machine-produced; never present it as "
        "verified), 'pending' (nothing verified matched; say so rather than "
        "improvising). Prefer a sealed answer over your own; when nothing is sealed, "
        "say what is missing and offer nestor_propose so a human can verify it.\n"
        f"This server cannot {', '.join(WITHHELD)}. Verification is a human act, and "
        "a model marking its own output as verified would empty the word."
    )


def _result(rid: Any, payload: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": payload}


def _error(rid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _write(stdout: TextIO, message: dict) -> None:
    stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nestor serve",
        description="Serve Nestor's verified memory to a model over MCP (stdio). "
                    "The model can ask and propose; it cannot seal.")
    p.add_argument("--db", default="data/nestor.db", help="SQLite database (default: data/nestor.db)")
    p.add_argument("--ledger", default="", help="ledger path (default: NESTOR_LEDGER or data/ledger.jsonl)")
    p.add_argument("--source-lang", default="en", help="default source domain tag")
    p.add_argument("--target-lang", default="es", help="default target domain tag")
    p.add_argument("--engine", default="offline", choices=("offline", "auto", "claude"),
                   help="draft engine for nestor_ask (default: offline)")
    p.add_argument("--read-only", action="store_true",
                   help="withhold nestor_propose too — pure lookup")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ledger:
        cascade.set_ledger_path(args.ledger)
    store = SqliteStore(args.db)
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    server = Server(store=store, source_lang=args.source_lang,
                    target_lang=args.target_lang, engine_name=args.engine,
                    read_only=args.read_only)
    # stdout is the protocol channel; anything human-facing goes to stderr or it
    # corrupts the stream.
    print(f"nestor MCP server on stdio — db={args.db} "
          f"ledger={cascade._ledger_path()} "
          f"{'read-only' if args.read_only else 'ask + propose'}", file=sys.stderr)
    server.run(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(main())
