# MCP resources and prompts — draft

*Filling the gap §7.5 names: the server exposes tools only — no resources,
no prompts, no manifest. The sealed store, the ledger, and the decision
graph are natural read-only resources; the propose → resolve → seal flow
is a natural prompt.*

**Status: draft — proposed, not decided.**

---

## What exists today

`serve.py` declares exactly one capability:

```python
"capabilities": {"tools": {"listChanged": False}}
```

Eight tools, listed in `tools()`. No resources, no prompts, no sampling,
no roots, no logging. The `handle()` method dispatches `tools/list` and
`tools/call`; every other method except `initialize`, `ping`, and the two
notification types returns `method not found`.

Protocol versions spoken: `2025-06-18`, `2025-03-26`, `2024-11-05`.

## What is proposed

Two new capability surfaces, both read-only, both respecting the same
covenant boundary the tools do: **a model may read, it may not seal.**

### Resources

MCP resources are read-only data a client can fetch by URI. They show up
in a client's context window on request — a user attaches them, or an
agent reads them with `resources/read`. Three natural resources:

#### 1. `nestor://store/summary`

The store's vital signs — what a model needs to know before calling any
tool.

```json
{
  "uri": "nestor://store/summary",
  "name": "Store summary",
  "description": "Pair counts by status, matcher type, domain, and seal coverage.",
  "mimeType": "application/json"
}
```

Response payload:

```json
{
  "total": 449,
  "by_status": {"draft": 449, "sealed": 0},
  "domain": {"source_lang": "decision", "target_lang": "decision"},
  "matcher": "StringMatcher",
  "seal_coverage": 0.0,
  "has_ledger": true,
  "ledger_entries": 12,
  "chain_valid": true
}
```

This replaces the current pattern of calling `nestor_ask` with an empty
query to infer store state. A resource is the right shape — it's context,
not a question.

#### 2. `nestor://ledger`

The append-only audit log, as a resource.

```json
{
  "uri": "nestor://ledger",
  "name": "Ledger",
  "description": "The append-only audit log. Each entry is hash-chained to the previous.",
  "mimeType": "application/json"
}
```

Response payload: the full ledger as a JSON array of entries, each with
`session_id`, `turn_id`, `event`, `timestamp`, `hash`, `prev_hash`. Large
stores may produce large ledgers; the resource includes a `_truncated`
flag and a `_total` count when the response exceeds a configurable limit
(default: last 100 entries).

```json
{
  "entries": [
    {
      "session_id": "s1",
      "turn_id": 1,
      "event": "session_open",
      "timestamp": "2026-08-19T12:00:00+00:00",
      "hash": "abc123...",
      "prev_hash": ""
    }
  ],
  "_total": 12,
  "_truncated": false
}
```

#### 3. `nestor://decisions`

The decision graph — pairs with their edges, for a model that needs to
understand what constrains what.

```json
{
  "uri": "nestor://decisions",
  "name": "Decision graph",
  "description": "Pairs and their constraint edges. Shows what was decided, what contradicts, what supersedes.",
  "mimeType": "application/json"
}
```

Response payload:

```json
{
  "pairs": [
    {
      "id": "d7950355-...",
      "question": "Was anything actually harmed?",
      "commitment": "Nothing was published wrongly...",
      "status": "draft",
      "verifier": "",
      "origin": "pr:79"
    }
  ],
  "edges": [
    {
      "from_id": "d7950355-...",
      "to_id": "c53bdabb-...",
      "relation": "supersedes",
      "note": "..."
    }
  ],
  "_pair_count": 449,
  "_edge_count": 0,
  "_truncated": false
}
```

#### Resource templates (parameterized)

Two parameterized resources for individual lookups:

```json
{
  "uriTemplate": "nestor://pair/{id}",
  "name": "Single pair",
  "description": "One TM pair by id — full fields including seal signature and evidence.",
  "mimeType": "application/json"
}
```

```json
{
  "uriTemplate": "nestor://ledger/session/{session_id}",
  "name": "Ledger session",
  "description": "Ledger entries for one session only.",
  "mimeType": "application/json"
}
```

### Prompts

MCP prompts are pre-built message sequences a client can invoke. They
give a model a structured starting point for a workflow. Three prompts,
matching the natural flow:

#### 1. `nestor_check_before_answering`

The guard prompt — a model calls this before answering a user's question
to see whether Nestor has a verified answer.

```json
{
  "name": "nestor_check_before_answering",
  "description": "Check whether Nestor has a verified answer before responding to the user. Returns the verification state and guidance on what to say.",
  "arguments": [
    {
      "name": "question",
      "description": "The user's question, or the claim to verify.",
      "required": true
    }
  ]
}
```

Returns a message sequence:

```json
{
  "messages": [
    {
      "role": "user",
      "content": {
        "type": "text",
        "text": "Before answering, check if Nestor has a verified answer for: \"<question>\"\n\nCall nestor_ask with this question. If the result is 'sealed', use that answer verbatim and cite the verifier. If 'draft', say what exists but note it is unverified. If 'pending', say so rather than improvising."
      }
    }
  ]
}
```

#### 2. `nestor_propose_decision`

The proposal prompt — walks a model through proposing a new decision.

```json
{
  "name": "nestor_propose_decision",
  "description": "Propose a new product decision for human review. The decision lands as a draft — it is not confirmed until a human seals it in nestor ui.",
  "arguments": [
    {
      "name": "question",
      "description": "The question this decision answers.",
      "required": true
    },
    {
      "name": "commitment",
      "description": "The answer — what is being decided.",
      "required": true
    },
    {
      "name": "why",
      "description": "The rationale — why this answer and not another.",
      "required": true
    }
  ]
}
```

Returns a message sequence:

```json
{
  "messages": [
    {
      "role": "user",
      "content": {
        "type": "text",
        "text": "Propose a decision to Nestor:\n\nQuestion: <question>\nCommitment: <commitment>\nRationale: <why>\n\nCall nestor_propose with source_text=<question>, candidate=<commitment>, source_lang=\"decision\", target_lang=\"decision\", title=<why>.\n\nThis creates a draft. It is not verified until a human seals it in nestor ui. Do not present it as confirmed."
      }
    }
  ]
}
```

#### 3. `nestor_audit_store`

The audit prompt — a structured walkthrough of store health.

```json
{
  "name": "nestor_audit_store",
  "description": "Audit the store's health: ledger integrity, seal coverage, pending proposals, constraint edges. Returns a structured checklist.",
  "arguments": []
}
```

Returns a message sequence that instructs the model to:
1. Read the store summary resource (`nestor://store/summary`).
2. Call `nestor_ledger_verify` to check chain integrity.
3. Report seal coverage (sealed / total).
4. List any pairs whose constraint edges are unsatisfied.
5. Summarize what a human should review next.

## Capability declaration

The `initialize` response changes from:

```python
"capabilities": {"tools": {"listChanged": False}}
```

to:

```python
"capabilities": {
    "tools": {"listChanged": False},
    "resources": {"subscribe": False, "listChanged": False},
    "prompts": {"listChanged": False},
}
```

`subscribe: False` because the store does not push updates — a model
polls by re-reading the resource. `listChanged: False` because the
resource list is static (no dynamic registration).

## New JSON-RPC methods

| Method | Purpose |
|--------|---------|
| `resources/list` | Return the resource descriptors above |
| `resources/read` | Return the content of one resource by URI |
| `resources/templates/list` | Return the parameterized resource templates |
| `prompts/list` | Return the prompt descriptors above |
| `prompts/get` | Return the message sequence for one prompt |

All five are read-only. None of them touch the seal path, the covenant
boundary, or the WITHHELD list.

## `handle()` dispatch additions

```python
if method == "resources/list":
    return _result(rid, {"resources": self.resources()})
if method == "resources/read":
    uri = str(params.get("uri", ""))
    return _result(rid, self.read_resource(uri))
if method == "resources/templates/list":
    return _result(rid, {"resourceTemplates": self.resource_templates()})
if method == "prompts/list":
    return _result(rid, {"prompts": self.prompts()})
if method == "prompts/get":
    name = str(params.get("name", ""))
    args = params.get("arguments") or {}
    return _result(rid, self.get_prompt(name, args))
```

## The covenant boundary

Resources and prompts do not cross it:

- **Resources** are read-only by definition. A model reads the store, the
  ledger, the graph. It cannot write through a resource.
- **Prompts** produce message sequences that call existing tools. The
  `nestor_propose_decision` prompt calls `nestor_propose` — a draft, not a
  seal. No prompt calls a WITHHELD operation.
- **No resource or prompt exposes the seal key**, the signing material, or
  any field that would let a model construct a seal.

The same sentence that opens `serve.py` still holds: the server cannot
seal, unseal, reject, override a conflicting seal, import a bundle, or
edit the ledger. Resources and prompts add read surfaces; they do not add
write surfaces.

## What this is NOT

- **Not sampling.** MCP's `sampling` capability lets a server ask the
  client's model to generate text. Nestor has no use for this — it serves
  verified answers, it does not generate new ones through the client.
- **Not roots.** MCP's `roots` capability lets the server discover the
  client's filesystem roots. Nestor operates on its own store, not the
  client's files.
- **Not subscriptions (yet).** `subscribe: False` means a client must
  re-read to see changes. A future version could notify on seal events
  (a human seals in `nestor ui`, the server pushes `notifications/resources/updated`),
  but that requires the UI and the server to share a signaling channel
  that does not exist today.
- **Not a manifest.** MCP does not (as of 2025-06-18) define a discovery
  manifest format. The `initialize` response and `*/list` methods are the
  discovery surface.

## Interaction with `--read-only`

When `serve.py` runs with `--read-only`, the `nestor_propose` tool is
already removed. The prompts that reference it (`nestor_propose_decision`)
should either be omitted from `prompts/list` or return a message sequence
that says "this store is read-only; proposals are not accepted." The
simpler choice: omit the prompt entirely from the list.

Resources are unaffected — they are always read-only.

## Protocol version

No change. Resources and prompts are part of the MCP spec at all three
protocol versions the server speaks (`2025-06-18`, `2025-03-26`,
`2024-11-05`). Adding them is a capability expansion, not a protocol
upgrade.
