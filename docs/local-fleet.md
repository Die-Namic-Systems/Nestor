# Local fleet integration

Wire nestor to the repos and branches named in
[`fleet-integration-map.md`](fleet-integration-map.md) **on this machine** before
opening cross-repo PRs. Everything here is paths and commands; no cloud required.

## Layout

Assume a sibling checkout tree:

```text
~/github/
  nestor/                 # this repo (editable: pip install -e .)
  terpsi-music/           # bench corpus + Nestor host app (coat-hat branch)
  safe-app-store-public/  # promote_check, lineage doc, App Forge design
  oakenscrolls-office/    # cite-and-grade → Nestor pairs
  willow-mcp/             # FRANK, egress_authorization (§5.8 borrow)
```

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

FRANK forwarding: see README `NESTOR_FRANK_*` and willow-mcp `frank_append` when
a shared governance chain is up.

## What stays nestor-only

§1.4 quorum policy and §5.8 Ed25519 implementation — no fleet branch implements
these in this repo; track in [`IDEAS.md`](../IDEAS.md). §6.8 `memory_init` skip
was on this list and shipped 2026-08-06, nestor-local exactly as the map
predicted; §6.25 (`init_db` on a pre-lineage database) was found doing it and
joins the list.
