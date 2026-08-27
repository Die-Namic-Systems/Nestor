# Archive

Historical artifacts — dated audits and one-shot probe reports. Kept for the
record of what was found and argued; not maintained as live operator docs.

| Path | What it is |
|------|------------|
| [`findings/`](findings/) | Dated FINDINGS audits (2026-07 through 2026-08). Fixes cited inside are shipped; the files stay as argument records. |
| [`probes/`](probes/) | `issue_probe.py` snapshots against the all-draft dogfood store at the time they were run. Regenerate with [`docs/probing-the-store.md`](../probing-the-store.md); do not treat counts here as current. |
| [`decisions/`](decisions/) | Superseded dogfood decision files (`consolidated_onto`); excluded from the active rebuild. See [`decisions/README.md`](decisions/README.md). |

Decisions in `docs/dogfood/decisions/` may cite the original paths
(`docs/findings/…`, `docs/dogfood/probes/…`) — that is the path at seal time.
