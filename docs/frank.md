# FRANK — mirroring into shared provenance

*Fleet-only. Nestor runs standalone with a purely local ledger; FRANK is the opt-in
seam that also mirrors every entry into willow-mcp's shared governance ledger.
Linked from the [README](../README.md#the-ledger).*

---

`nestor.frank` mirrors every ledger entry into **FRANK**, willow-mcp's
append-only governance ledger, so the trail also lives in shared infrastructure.
A third injected seam, same shape as the others:

```python
from nestor import frank
frank.set_forwarder(frank.willow_forwarder())   # opt in
frank.set_forwarder(None)                       # local ledger only (the default)
```

A forwarder is any callable `(event_type: str, content: dict) -> None`. The
bundled `WillowForwarder` speaks **MCP over stdio** and calls willow-mcp's
`frank_append` tool, so the write passes through the manifest ACL that makes the
ledger trustworthy — it never touches the governance database directly.

| Variable | Meaning | Default |
|----------|---------|---------|
| `WILLOW_MCP_COMMAND` | server argv, JSON list or plain string | `[sys.executable, "-m", "willow_mcp"]` |
| `NESTOR_FRANK_APP_ID` | app seat to call as (needs `frank_write`) | `nestor` |
| `WILLOW_APP_ID` | fallback for the above — see the note | unset |
| `NESTOR_FRANK_PROJECT` | FRANK project name | `nestor` |
| `NESTOR_FRANK_STRICT` | raise instead of swallowing forward failures | unset |

`WILLOW_APP_ID` is read **second**, and the ordering matters. It is
*client-scoped* — "the seat this client is driving" — so a fleet shell exports
one value and every package in the process inherits it. Read first, it silently
re-seats this forwarder: a shell set up for the orchestrator made Nestor call
`frank_append` as `willow`, which willow-mcp refuses outright (that seat demands
a human-orchestrator host), so a correctly seated Nestor stopped forwarding the
moment a fleet env was sourced. `NESTOR_FRANK_APP_ID` is Nestor's own line and
it wins; the seat it names needs `frank_write` in its willow-mcp manifest.

Local entries are written **first** and stay the source of truth; forwarding is
best-effort, because a governance mirror that is down, denied or absent must
never fail a translation. Each mirrored entry carries a `local_hash` — the
sha256 of the local line as written — so the two chains cross-link.

## Related fleet and home variables

For **fleet-gap** review (willow SOIL imports), `nestor ui` can echo Hanuman
dispatch handoffs from a charter rollup JSON plus files under your willow home.
These are the paths and roots those surfaces read:

| Variable | Meaning | Default |
|----------|---------|---------|
| `NESTOR_GATE_ROLLUP` | path to fleet-gap seals JSON (willow `governance/decisions/*` schema) | unset — override with `nestor ui --gate-rollup` |
| `WILLOW_HOME` | willow **fleet** runtime root (`store/`, `dispatch/`, `mcp_apps/` — see [roots-willow-and-homestead.md](roots-willow-and-homestead.md)) | `~/github/.willow` (alias `~/.willow`) |
| `NESTOR_HOME` | household root for the ledger/keep tree (see [home-paths.md](home-paths.md)) | `<home>/.nestor` |
| `NESTOR_CONFIG` | path to the config file layer (`nestor.config.json`); a path that does not exist is a valid answer, not an error | `./nestor.config.json` in the cwd |
