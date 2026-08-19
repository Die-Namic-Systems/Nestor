# Probing `nestor serve` (MCP) and `nestor ui` beyond documented usage

All testing done against a scratch copy of the demo DB
(`/tmp/probe-demo.db` + `/tmp/probe-demo.ledger.jsonl`, copied from
`data/nestor-demo.db` / `data/nestor-demo.ledger.jsonl`) so nothing in the
repo's tracked demo data was mutated. Source reviewed:
`/home/user/Nestor/nestor/serve.py` (536 lines) and
`/home/user/Nestor/nestor/ui.py` (1815 lines).

## 1. `nestor serve --help`

```
--db DB               (default: data/nestor.db)
--ledger LEDGER       (default: NESTOR_LEDGER or data/ledger.jsonl)
--source-lang / --target-lang   default domain tags (default en/es)
--engine {offline,auto,claude}  draft engine for nestor_ask (default: offline)
--matcher MATCHER      string|numeric|semantic|ollama, or 'module:attribute'
--read-only            withhold nestor_propose too
```

## 2/3. MCP handshake and tool discovery

`initialize` → advertises `protocolVersion` (echoes the client's if it is one
of `PROTOCOL_VERSIONS = ("2025-06-18","2025-03-26","2024-11-05")`, else falls
back to the newest, `2025-06-18` — spec-correct unknown-version handling),
`capabilities: {"tools": {"listChanged": false}}` (no `resources`, `prompts`,
or `logging` capability declared), `serverInfo`, and an `instructions` string
that states what is withheld and which domain/matcher this instance keys.

`tools/list` returns exactly 7 tools (6 under `--read-only`):

1. `nestor_ask` (text, source_lang, target_lang) — cascade lookup, 3-state
   answer (`sealed`/`draft`/`pending`).
2. `nestor_resolve` (surface, domain) — alias → canonical entity.
3. `nestor_check` (label, observed, domain, abs_tol, pct_tol) — figure vs.
   sealed baseline.
4. `nestor_match` (text, source_lang, target_lang, matcher enum, abs_tol,
   pct_tol) — the bare matcher mechanic over any domain.
5. `nestor_provenance` (pair_id) — verifier/origin/rejections for a pair.
6. `nestor_ledger_verify` () — hash-chain verify + memory stats.
7. `nestor_propose` (source_text, candidate, source_lang, target_lang, title)
   — **only write**, always lands `status=draft`. Absent entirely under
   `--read-only` (not just refused — not in the list).

No MCP **resources**, **prompts**, or **completion** capability exists.
Verified directly: `resources/list`, `prompts/list`, `resources/subscribe`,
`completion/complete` all come back `-32601 method not found`. `ping` is
handled (`{}`). No `notifications/*` are emitted by the server itself (only
`notifications/initialized` / `notifications/cancelled` are *accepted*, and
silently swallowed — no ack, per JSON-RPC notification semantics).

## 4. Exercising tools beyond the CLI — findings

- **Seal-injection is explicitly caught and named, not just ignored.**
  `nestor_propose` only reads `{source_text, candidate, source_lang,
  target_lang, title}` (`PROPOSE_KEYS`). Sending `status`, `verifier`,
  `sealed`, `seal_sig` alongside a proposal gets them listed back verbatim in
  the response under `seal_authority_refused` / `ignored_fields`, e.g.:
  ```json
  "seal_authority_refused": ["sealed", "status", "verifier"]
  ```
  so a model reading the result sees the refusal, not a silent drop.
- **Calling a withheld verb by name** (`nestor_seal`, or anything else
  prefixed `nestor_` that isn't in the tool list) returns a structured
  `tools/call` result with `isError: true` and names every withheld verb:
  `seal, unseal, reject, override a conflicting seal, import a bundle, edit
  the ledger`.
- **No `initialize` gate.** `tools/call` (and `tools/list`) work perfectly
  fine even if `initialize` was never sent first — the server has no
  session/handshake enforcement; it just answers each line independently.
  Not a security issue here (nothing sensitive is gated), but worth knowing
  if a client's lifecycle assumptions differ.
- **Domain mismatch refusals actually fire.** Started with `--matcher
  numeric` (keys `en`→`es`), calling `nestor_ask` with
  `source_lang=En, target_lang=ES` (a same-domain but different-case pair)
  is refused outright rather than silently deferring to a different matcher:
  `ValueError: 'En'/'ES' is not a domain this server knows — it differs from
  'en'/'es' only in case. Did you mean 'en'/'es'?`. A genuinely different
  domain (e.g. `Entity`/`entity` on an `en`/`es` server) is *not* an error —
  it just defers to the process-wide default matcher and returns `pending`,
  matching the code comments.
- **`nestor_match` refuses to score with a different matcher than the one
  configured.** `--matcher numeric` + `{"matcher": "semantic"}` →
  `ValueError: this server keys 'en'→'es' with 'numeric'; it cannot score
  'semantic' as well`.
- **`--engine claude` fails cleanly, not with a traceback**, when the
  `anthropic` package isn't installed: `RuntimeError: ClaudeEngine needs the
  anthropic SDK: pip install anthropic (or use --engine offline)`, delivered
  as a normal `isError` tool result.
- Confirmed real answers against the demo data: `nestor_ask("The meeting is
  adjourned.")` → sealed, verifier `rita`; `nestor_resolve("Big Blue",
  domain="entity")` → canonical `IBM`, sealed; `nestor_check("412","415",
  domain="headcount")` → `baseline: null` (demo DB's headcount baseline is
  keyed oddly — label `"412"` has no baseline row; this is a data quirk of
  the seeded demo, not a server bug); `nestor_provenance` on a sealed pair id
  returns full audit detail including `signature_valid` and `rejections`.
- **Protocol-level robustness**, all confirmed:
  - Malformed JSON on a line → `-32700 parse error`, loop continues.
  - A line over 1 MiB (`MAX_MESSAGE`) → `-32600 message too large (...)`,
    loop continues (does not crash or hang).
  - JSON-RPC **batch** (`[...]`) requests are supported — each element
    dispatched and answered independently.
  - Every tool refusal (`ValueError`/`PermissionError`/`RuntimeError`) comes
    back as a normal JSON-RPC **result** with `isError: true`, not a
    JSON-RPC protocol error — deliberate, per the code comment, "so the
    model can read it and change what it does."

## 5. `nestor ui --help`

Far more surface than `serve`:
```
--db, --ledger, --host (default 127.0.0.1), --port (default 8765)
--source-lang, --target-lang, --matcher, --engine {offline,auto,claude}
--verifier VERIFIER        prefill 'acting as' (unproven unless --keyring)
--keyring KEYRING          per-verifier seal keys (NESTOR_KEYRING) -> sign-in
--session-hours (default 8)
--demo                     seed demo store if empty
--read-only                refuse every decision; browse/audit only
--allow-remote             permit non-loopback bind (no auth otherwise)
--open                     open browser
--gate-rollup GATE_ROLLUP  path to gate-rollup JSON (fleet integration, docs/frank.md)
```

## 6. Running `nestor ui --port 0`

**Confirmed defect (cosmetic but real):** `--port 0` asks the OS for an
ephemeral port. The server *does* bind correctly and listens (verified with
`lsof -p <pid> -a -i`: actually bound to `127.0.0.1:41503` in one run), but
the startup banner prints the URL from the `--port` argument verbatim rather
than reading back `httpd.server_address`:
```
Nestor UI  →  http://127.0.0.1:0/
```
This is actively misleading for `--port 0` usage — the only way to discover
the real port is external (`lsof`/`ss`), not from the tool's own output.
Root cause in `nestor/ui.py::main`: `url = f"http://{args.host or
'127.0.0.1'}:{args.port}/"` is built from `args.port`, not from
`httpd.server_address[1]`, before `httpd.serve_forever()`.

Other logged startup lines confirmed live (fixed port 18765/18766/18767 runs):
```
Nestor UI  →  http://127.0.0.1:<port>/
  store    <db>
  ledger   <ledger>
  engine   offline
  verifier typed, not proven — anyone reaching this port can seal as any name (set NESTOR_KEYRING for per-verifier keys)
  WARNING  NESTOR_SEAL_KEY is not set: seals are trusted on stored status alone, and this UI cannot tell a real one from a forged row.
```

## 7. Undocumented capabilities found by reading `nestor/ui.py`

`--help` says nothing about the actual HTTP API surface. Full route table
(`_ROUTES` in `nestor/ui.py`), **20 endpoints**, most never mentioned in any
`--help` text:

GET:
- `/api/state` — read-only snapshot (identity/session, signing status,
  domain+matcher, capabilities, memory stats, ledger head/verify).
- `/api/pairs`, `/api/pair` — curator browse/detail (filters: status,
  verifier, contains, an `unverifiable=1` filter for sealed-but-not-servable
  rows).
- `/api/queue` — pending review segments grouped by document.
- `/api/ledger` — chain verify + entries + `unreadable` count, joined.
- `/api/due-for-reverification` — staleness listing (age-based re-check
  candidates), `older_than` days param.
- `/api/replaced-seals` — seals one human overwrote another human's decision
  on (the store itself keeps no other trace of this).
- `/api/rejections` — aggregate signal from recorded "no"s.
- `/api/export`, `/api/bundle` — portable JSON exports (bundle includes
  signatures, served with `Content-Disposition: attachment`).
- `/api/domains` — every (source_lang, target_lang) pair + row counts in the
  store, so a human can see what domains actually exist without guessing tag
  names.
- `/api/graph` — **the whole decision graph** (nodes = decisions, edges =
  contradicts/supersedes/refines/…), entirely read-only, no write path at
  all reachable through it.
- `/api/triage` — decision triage clustering + proposed edges (same engine
  as `nestor.triage`), memoized per-store-signature since clustering is
  O(n²).
- `/api/gate-echo` — opt-in "fleet" integration reading a
  `--gate-rollup`/`NESTOR_GATE_ROLLUP` JSON file and cross-referencing
  `~/github/.willow/dispatch/<id>/handoff.json` files on disk (off by
  default; confirmed `{"rollup": "", "entries": []}` when unset).

POST (mutating unless in `_NO_DECISION`):
- `/api/session`, `/api/session/end` — keyring sign-in/out (only meaningful
  with `--keyring`; survives `--read-only`).
- `/api/normalize` — read-only preview of the exact `source_norm` a seal for
  a phrase would bind to (needed by the browser-side WebCrypto signer to
  build the message it signs). Survives `--read-only` since it writes
  nothing. Confirmed live: `{"text":"Big Blue","domain":"entity"} →
  {"source_norm":"big blue",...}`.
- `/api/import` — bundle import, `dry_run` defaults **true**.
- `/api/ask`, `/api/match` — same mechanics as the MCP tools, but writable
  (ask ledgers a passage) and richer (match/ask here can take an explicit
  `matcher=` when the App has no domain-matcher of its own).
- `/api/entity/resolve`, `/api/entity/seal` — entity alias sealing, with
  `override` for conflicting/rejected overrides.
- `/api/reconcile/check`, `/api/reconcile/seal` — numeric baseline
  check/seal.
- `/api/seal`, `/api/seal-draft` — direct seal / seal-a-queued-draft-in-place
  (the latter distinguishes "sealed as drafted" vs. "sealed as edited," and
  records a `draft_sha` of the *unsealed* candidate in the ledger).
- `/api/edge/seal` — confirm/seal a proposed decision-graph edge
  (contradicts/supersedes/refines), the one write path this close to the
  trust root; requires either a session or a client-supplied `edge_sig`.
- `/api/unseal`, `/api/restore`, `/api/reject-pair`, `/api/reject-match` —
  full curator lifecycle.
- `/api/queue/seal`, `/api/queue/reject` — review-queue decisions, with an
  "edited" branch that can seal a *corrected* target text rather than the
  machine's draft verbatim.

**Client-side signing support (Nestor#17):** every seal-shaped endpoint
(`/api/seal`, `/api/seal-draft`, `/api/queue/seal`, `/api/edge/seal`) accepts
an optional `seal_sig`/`edge_sig` field. With a keyring installed and a
signature present, the *payload's* `verifier` field is trusted (because the
signature is checked downstream by `memory.add_pair`/`seal_edge`), bypassing
the session-token requirement — this exists specifically for verifiers whose
keyring entry is an ed25519 **public**-key-only record, who can never get a
`Sessions.open()` token (no server-held secret to check against) and instead
sign client-side via WebCrypto in the browser.

Confirmed behaviorally (fixed-port runs, `/tmp/probe-demo.db`):
- With no `--keyring`, `/api/seal` happily sealed a brand-new pair under
  `"verifier": "totally-fake-name"` — exactly the printed startup warning
  ("anyone reaching this port can seal as any name"), by design, not a bug.
- CSRF is enforced on every POST: missing `X-Nestor-UI: 1` header →
  `403 {"code":"csrf"}`; a mismatched `Origin` header (e.g.
  `http://evil.example.com` against `Host: 127.0.0.1:18766`) → `403` with a
  message naming both values. No cookies are used at all — the design
  deliberately relies on the custom header + Origin check instead.
- `--read-only`: `/api/normalize` still works (writes nothing — listed in
  `_NO_DECISION`), but `/api/seal` is flatly refused with
  `403 {"code":"read_only"}` before the handler even runs (checked in
  `dispatch()`, not per-handler).
- Every response carries `Cache-Control: no-store`, `X-Content-Type-Options:
  nosniff`, `Referrer-Policy: no-referrer`, and a strict
  `Content-Security-Policy: default-src 'none'; ...` — confirmed present on
  every request in this session (checked via curl `-i`, not shown above for
  brevity but present on `/api/state` and the root page).

## 8. Notifications / subscriptions

- **MCP side (`serve.py`):** no push notifications and no resource
  subscriptions exist. The server is purely request/response over stdio; it
  never writes an unsolicited line to stdout. Only two *inbound*
  notification methods are recognized and both are no-ops on receipt
  (`notifications/initialized`, `notifications/cancelled` — swallowed,
  return `None`, nothing is cancelled server-side since every tool call
  already runs synchronously to completion in one `handle()` call).
- **UI side (`ui.py`):** no WebSocket/SSE/long-poll anywhere — plain
  request/response `http.server`. The "Signals" tab data
  (`/api/due-for-reverification`, `/api/replaced-seals`, `/api/rejections`)
  is all pull-based; a client has to poll `/api/state`/`/api/ledger` for
  freshness. `Sessions` tokens are purely in-memory (`Sessions._tokens`) — a
  UI restart silently signs everyone out, which the module docstring calls
  out as "also how a revocation takes effect."

## Summary of the most notable findings

1. **MCP tool surface is exactly 7 tools** (6 read-only + 1 propose), no
   resources/prompts/completion capabilities — a much smaller surface than
   the UI's ~20 HTTP endpoints. The MCP server is deliberately narrow; the
   HTTP UI is the "real" API surface and none of its ~20 endpoints appear in
   `nestor ui --help`.
2. **The seal-authority boundary is actively enforced and self-reporting** —
   attempts to smuggle `status`/`verifier`/`sealed`/`seal_sig` through
   `nestor_propose` are caught, named in the response (`ignored_fields`,
   `seal_authority_refused`), never silently dropped.
3. **`nestor ui --port 0` prints a broken URL** (`http://127.0.0.1:0/`)
   while actually binding to a real ephemeral port — a confirmed, reproducible
   defect in `nestor/ui.py::main`'s banner (uses `args.port` instead of the
   bound socket's actual port).
4. **Without `--keyring`, the UI's "acting as" verifier is fully unauthenticated**
   by design (confirmed: sealed a pair as a made-up name over plain HTTP) —
   loudly warned about at startup, and the intended mitigation
   (`--keyring`) turns it into real per-verifier signature auth with a
   client-side WebCrypto signing path for public-key-only verifiers.
5. `/api/graph` and `/api/triage` expose the entire decision-memory graph
   and its clustering/triage engine over HTTP — substantial functionality
   with zero mention in `--help`.

## Files referenced

- `/home/user/Nestor/nestor/serve.py` — MCP server implementation.
- `/home/user/Nestor/nestor/ui.py` — HTTP UI + API implementation.
- `/home/user/Nestor/data/nestor-demo.db`,
  `/home/user/Nestor/data/nestor-demo.ledger.jsonl` — source demo data (not
  mutated; testing used copies at `/tmp/probe-demo.db` /
  `/tmp/probe-demo.ledger.jsonl`).
