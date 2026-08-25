# Sovereign deployment — what Nestor does not phone home about

*What a policy reader, procurement officer, or chief-of-staff can check
without running Nestor themselves. The claims here are named,
scoped, and gated by tests — no adjectives, no marketing.*

The load-bearing sentence:

> **A default install of `nestor-meaning`, running any of its read
> commands (ask / resolve / match / check / provenance / stats),
> opens NO socket to any non-loopback address.**

That sentence is a test:
[`tests/test_no_network_by_default.py`](../tests/test_no_network_by_default.py).
14 assertions; it installs a socket interceptor that raises on any
`AF_INET` / `AF_INET6` connect to a non-loopback address, then runs
each default read path against it. A regression turns exactly one test
red and names which one.

---

## What "default install" means, precisely

- `pip install nestor-meaning` — no extras.
- Environment: `ANTHROPIC_API_KEY` unset, `OLLAMA_HOST` unset,
  `NESTOR_FRANK_STRICT` unset, `WILLOW_MCP_COMMAND` unset.
- Command flags left at their defaults (in particular: `--engine
  offline`, `--matcher string`).

Under those conditions, the socket interceptor observes zero
non-loopback `connect()` calls across the read surface.

## The four opt-in surfaces that CAN reach the network

Named here so a reader can look for the flag or extra that turns each on.

| Surface | Trigger | Where the connect goes | Extra required |
|---|---|---|---|
| **`--engine claude` / `--engine auto`** | `ANTHROPIC_API_KEY` set + engine flag | `api.anthropic.com` (via the Anthropic SDK) | `[cloud]` |
| **`--matcher semantic`** | Explicit `--matcher semantic` | The fastembed model download URL on first use; nothing after | `[semantic]` |
| **`--matcher ollama`** | Explicit `--matcher ollama` | `OLLAMA_HOST` (default `http://localhost:11434` — loopback unless overridden) | stdlib only |
| **`nestor.cloud_seal`** (willow-gate cloud path) | Import the module | Via `willow_gate` | `[gate]` |

The `[cloud]`, `[semantic]`, and `[gate]` extras are the off switches.
Without them installed, the corresponding module either does not
resolve (`willow_gate` / `anthropic` are not importable) or is not
loaded by the default read path.

## What the UI does with the network

`nestor ui` is a *server* that binds a socket — a bind, not a connect.
It defaults to `127.0.0.1:8765` (see `nestor/ui.py:1591`, the
`serve(app, host="127.0.0.1", port=8765)` signature). To expose it
off-box, the operator has to pass `--host 0.0.0.0` (or similar) — a
deliberate step visible in the shell history. Test:
`test_ui_server_bind_default_is_loopback`.

That's the "not phone home" half. A bind that stays on loopback is not
a phone-home — nothing outside the machine can reach it. If the
default were `0.0.0.0`, that would be a very different posture, and
the test above would fire.

## What the ledger mirror does with the network

`nestor.frank.forward` is the seam that mirrors ledger events into
willow-mcp's shared governance ledger. It's off by default:
without `NESTOR_FRANK_STRICT` or `WILLOW_MCP_COMMAND` set, the call
is a no-op. When enabled, it opens a **subprocess pipe** to
willow-mcp (`subprocess.Popen` — stdio JSON-RPC), not a socket. Test:
`test_frank_forward_is_a_noop_when_no_mirror_is_configured`.

That distinction matters for an air-gap deployment: no socket ever
opens, mirror on or off. The mirror talks to another process on the
same box; whether *that* process reaches the network is its own
config, not Nestor's.

## Air-gap: what still works

Everything the read surface does. `ask`, `resolve`, `match`, `check`,
`provenance`, `stats`, `ledger verify`, `propose`, `nestor ui` — all
of these work with no network. The `nestor-meaning` package's
runtime dependencies are zero: `hashlib`, `sqlite3`, `http.server`,
`urllib.parse` are stdlib. The seal signatures use HMAC (also
stdlib); asymmetric signatures need the `[keys]` extra, which is
`cryptography` — installable offline from a wheel.

What does not work in an air gap:

- `--engine claude` / `--engine auto` — the Anthropic SDK needs the
  network.
- `--matcher semantic` on the first-ever use — needs to download the
  fastembed model. After that first download, subsequent uses are
  offline.
- `--matcher ollama` — needs an Ollama daemon reachable at
  `OLLAMA_HOST`. Loopback is fine (localhost daemon); an air-gap
  deployment can run Ollama alongside Nestor on the same box.

## The test file, and how to run it

```
$ python -m pytest -q tests/test_no_network_by_default.py
..............                                                           [100%]
14 passed in 0.26s
```

Split against a regression — a top-level `import anthropic` in
`nestor/engine.py` or a `socket.create_connection` inside
`answer.ask` — turns the relevant test red immediately:

```
E   AssertionError: non-loopback socket connect during default operation:
    family=<AddressFamily.AF_INET: 2> address=('93.184.216.34', 80).
    This is the pitch-claim 'default operation opens no non-loopback
    socket' failing — see tests/test_no_network_by_default.py.
```

## What this file does NOT claim

- Not a formal security proof. A sufficiently determined caller can
  monkey-patch anything after import; the test proves what the
  shipped code does out of the box, not what a hostile in-process
  attacker can do to it.
- Not a claim about the operating system. If the OS or another
  process on the box opens a socket, that is not Nestor's connect
  and not this file's concern.
- Not a claim about the extras. If you `pip install nestor-meaning[cloud]`
  and set `ANTHROPIC_API_KEY`, Nestor will call Anthropic — that is
  the whole point of the extra. The claim is bounded to the *default*
  install and the *default* commands.

## Why this file exists

Recorded in `docs/journal/public-sector-audience.md` §3 as one of
three pitch-shape claims that were *asserted, not verified* — and
therefore had no business being in a pitch to a public-sector
audience. This file, together with `tests/test_no_network_by_default.py`,
moves *"local-first, no phone-home"* from an assertion to a checkable
fact. The other two claims from that note — *"air-gap friendly"* and
*"sovereign deployment"* — are supported by the sections above and
the same underlying test.

Decision `0194-sovereign-deployment-socket-boundary.json` records
why this specific shape (interceptor + per-recipe test + opt-in
proofs) is the one that got landed.
