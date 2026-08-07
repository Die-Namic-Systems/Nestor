# Local fleet integration

Wire nestor to the repos and branches named in
[`fleet-integration-map.md`](fleet-integration-map.md) **on this machine** before
opening cross-repo PRs. Everything here is paths and commands; no cloud required.

## Layout

Assume a sibling checkout tree:

```text
~/github/
  nestor/                 # this repo (editable: pip install -e .)
  jeles/                  # verified-nugget corpus (recipes/jeles_bridge.py)
  willow-mcp/             # FRANK, the gate, the shared SOIL store
  terpsi-music/           # bench corpus + Nestor host app (coat-hat branch)
  safe-app-store-public/  # promote_check, lineage doc, App Forge design
  oakenscrolls-office/    # cite-and-grade → Nestor pairs
```

## The three-repo stand-up (nestor + jeles + willow-mcp)

Nestor, jeles and willow-mcp are the part of the tree that has to be **running**
together, not just checked out together — one venv, one SOIL store, one gate,
one hash chain. willow-mcp owns that script, because it is the hub the other two
attach to:

```bash
cd ~/github/willow-mcp
NESTOR_REPO=~/github/nestor JELES_REPO=~/github/jeles bash scripts/fleet-standup.sh
. "$WILLOW_HOME/fleet.env"        # the path it prints at the end
```

It is idempotent, and it ends by *checking* the seams rather than asserting
them (`scripts/fleet_seams.py`, six of them). Two are Nestor's:

- **FRANK mirror** — `nestor.frank.willow_forwarder()` → `frank_append` →
  the hash chain, and then a `verify()` over the whole chain. The stand-up
  seats `nestor` in the gate itself (`$WILLOW_HOME/mcp_apps/nestor/manifest.json`,
  `frank_write` + `fleet_read` + `gap_read`). That seat is operator-local on
  purpose: Nestor is a package that mirrors a ledger, not a dispatchable agent
  with a persona, so willow-mcp's specialist registry does not — and should not
  — seed it, and `compile-agents` leaves it alone.
- **Nugget bridge** — [`recipes/jeles_bridge.py`](../recipes/jeles_bridge.py):
  a jeles nugget crosses as a **draft** and the check fails if anything arrives
  sealed. That is the whole claim, so it is the thing asserted.

Three things bite in that order, and all three are silent:

1. **`WILLOW_STORE_ROOT` unset.** jeles falls back to `~/.willow/store` and
   willow-mcp serves `$WILLOW_HOME/store`; both halves then work perfectly, on
   two different databases. `fleet.env` pins it.
2. **`WILLOW_APP_ID` exported fleet-wide.** It is *client-scoped* — "the seat
   this client is driving" — and `frank.WillowForwarder` used to read it first.
   A shell set up for the orchestrator re-seated Nestor's mirror as `willow`,
   which willow-mcp refuses outright. Use `NESTOR_FRANK_APP_ID` (it wins);
   `fleet.env` deliberately does not export `WILLOW_APP_ID` at all.
3. **Tagless clones.** jeles and willow-mcp take their versions from git tags
   via hatch-vcs, so a shallow clone builds as `0.1.devN`, which does not
   satisfy willow-mcp's own `jeles>=0.5.1`. It looks like a bad pin and is a
   missing `git fetch --tags`. The stand-up script fetches them first.

Sealing a bridged nugget through `nestor ui` is still the open half — see the
warning at the top of `recipes/jeles_bridge.py` and IDEAS §6.40.

Run after `git fetch` when you want `local/fleet-integration` to track the fleet
remote branches named in `scripts/fleet-local-checkout.sh`:

```bash
./scripts/fleet-local-checkout.sh
```

The script **fast-forwards** `local/fleet-integration` when `origin/<branch>` still
exists; it does **not** reset that branch with `git checkout -B`. Commits you made
only on `local/fleet-integration` stay unless the fast-forward cannot run (you
merged locally — resolve or delete the branch to recreate). The branch you were
**on before the script runs** is unchanged except that the script checks out
`local/fleet-integration` in each repo and prints how to switch back. When a
remote branch has been deleted after merge, the script skips that repo and leaves
your current branch as-is.

## Nestor on PATH

From `nestor/`:

```bash
pip install -e .
export NESTOR_SEAL_KEY=test-key   # dev only
```

Other repos should resolve **this** checkout, not an old PyPI pin:

```bash
pip install -e ~/github/nestor
```

Refresh **terpsi** `docs/FLEET-READS.md` Nestor SHA after meaningful nestor
changes (`git -C ~/github/nestor rev-parse HEAD`).

## Bench ↔ terpsi

Default bench pin (unchanged until you re-extract):

```bash
export TERPSI_ROOT=~/github/terpsi-music
# corpus_terpsi.py uses PINNED_REV=6ea9b89 inside the tree
python -m bench.corpus_terpsi   # gate + smoke
```

To exercise the **coat-hat** product tree (store/records; prose paths may still
match the pin):

```bash
git -C ~/github/terpsi-music checkout local/fleet-integration
export TERPSI_ROOT=~/github/terpsi-music
```

Re-run surface benches with an updated `corpus_revision` in results JSON when you
deliberately move the pin.

## SAFE promotion (local nestor)

```bash
cd ~/github/safe-app-store-public
python stores/promote_check.py ~/github/nestor
# when ready: add --record to mint under stores/.../promoted/
```

App Forge design (D1/D4 — `nestor/serve`, `nestor/signing`) lives on
`local/fleet-integration` = `origin/claude/repo-test-run-a8lt94`:

```bash
git -C ~/github/safe-app-store-public checkout local/fleet-integration
less docs/design/app-forge.md
```

## Oakenscroll seam

```bash
cd ~/github/oakenscrolls-office
pip install -e ~/github/nestor
pytest tests/test_almanac_seam_nestor.py -q
```

## Operator checkpoints (§5.5)

```bash
nestor ledger head
nestor ledger verify --expect-head "$(cat /path/to/pinned-head.txt)"
nestor db checkpoint              # §6.7 — WAL flush without stopping the UI
nestor db checkpoint --out /backup/nestor-$(date +%F).db   # also …$(date +%F).db.ledger.jsonl
nestor export --out /backup/memory.json
```

`--out` writes the database *and* its hash-chained ledger; **restore both
together** — a store without its chain is sealed rows nothing can audit. Re-running
to a name that already exists refuses rather than overwriting; `--force` replaces
both halves. `--no-ledger` copies the database alone, and because a leftover
chain beside a newer database is a mismatched pair rather than a partial one, it
refuses if a sidecar is already sitting at that name (`--force` removes it).
A backup that fails part-way leaves the previous one intact.

FRANK forwarding: see README `NESTOR_FRANK_*` and willow-mcp `frank_append`.
To get a shared governance chain up from nothing, use the three-repo stand-up
above — willow-mcp ships the `frank_ledger` DDL as of 2.4, so the chain no
longer requires a database somebody else already migrated.

## What stays nestor-only

§1.4 quorum policy and §5.8 Ed25519 implementation — no fleet branch implements
these in this repo; track in [`IDEAS.md`](../IDEAS.md). §6.8 `memory_init` skip
was on this list and shipped 2026-08-06, nestor-local exactly as the map
predicted; §6.25 (`init_db` on a pre-lineage database) was found doing it and
joins the list.
