# Local fleet integration

Wire nestor to the repos and branches named in
[`fleet-integration-map.md`](fleet-integration-map.md) **on this machine** before
opening cross-repo PRs. Everything here is paths and commands; no cloud required.

## Layout

After the 2026-08-10 org-folder layout, checkouts are one directory per GitHub
org (not a flat `~/github/{nestor,jeles,willow-mcp}`). On this machine:

```text
~/github/
  Die-Namic-Systems/nestor/          # this repo (editable: pip install -e .)
  hornbook-knowledge/Jeles/          # verified-nugget corpus (recipes/jeles_bridge.py)
  willow-memory/willow-mcp/          # FRANK, the gate, the shared SOIL store
  willow-memory/.willow/             # WILLOW_HOME (fleet state; ~/.willow → here)
  terpsi-programs/terpsi-music/      # bench corpus + Nestor host app
  hornbook-knowledge/oakenscrolls-office/  # cite-and-grade → Nestor pairs (own repo)
  safe-app-store-public/             # promote_check, lineage doc, App Forge design
```

## The three-repo stand-up (nestor + jeles + willow-mcp)

Nestor, jeles and willow-mcp are the part of the tree that has to be **running**
together, not just checked out together — one venv, one SOIL store, one gate,
one hash chain. willow-mcp owns that script, because it is the hub the other two
attach to. Pass the org-folder paths explicitly (the script's sibling defaults
no longer resolve after the move). Point `WILLOW_HOME` at the live fleet home,
not a fresh repo-local `.willow`:

```bash
export WILLOW_HOME=~/github/willow-memory/.willow
cd ~/github/willow-memory/willow-mcp
NESTOR_REPO=~/github/Die-Namic-Systems/nestor \
JELES_REPO=~/github/hornbook-knowledge/Jeles \
bash scripts/fleet-standup.sh
. "$WILLOW_HOME/fleet.env"        # the path it prints at the end
```

If PGP enforcement is on (`WILLOW_PGP_FINGERPRINT` set), seat and sign the
operator-local `nestor` manifest after stand-up
(`willow-mcp sign-manifest nestor`), and refresh the jeles registry for
`gap_write` when an older home lacks it (`WILLOW_FLEET_REFRESH_REGISTRY=1`).
Unsigned manifests under `$WILLOW_HOME/mcp_apps/` refuse the server boot and
every MCP seam fails as a closed connection.

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

## Standing one Nestor with every seam attached (no fleet hub)

The section above stands up three repos that have to be *running* together. This
one is the smaller case and the one a cloud container actually gets: a single
checkout where every optional seam is attached, nothing needs Postgres, and the
measure of "attached" is the skip count rather than a claim.

**The skip list is the map.** `python -m pytest -q -rs` on a `.[dev,keys]`
install reports the unattached seams by name, and every skip reason is a thing
that can be wired:

```bash
JELES_REPO=~/github/hornbook-knowledge/Jeles \
WILLOW_CHARTER_REPO=~/github/willow-memory/willow \
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
python -m pytest -q -rs
```

`tests/_fleet_paths.py` resolves the first two; both accept an env override
ahead of the org-folder defaults, which is what makes a flat container layout
(`/home/user/Jeles`) work without moving anything. `pip install -e <path>` for
jeles and willow-gate attaches the rest: jeles clears eight skips (border,
bridge, verification, two audits), the charter three, willow-gate one
(`nestor.cloud_seal` fail-closes on import without it).

Measured on a 2026-08-12 container, same tree: **944 passed / 24 skipped** at the
`.[dev,keys]` baseline, **972 passed / 4 skipped** with the seams above attached.

**Playwright: match the version to the image, never download.** The browser
suite asks Playwright where Chromium is and skips if that path is empty
(`tests/test_client_signed_seals_browser.py`), so a version mismatch reads as a
missing browser. An image shipping `chromium-1194` (Chromium 141.0.7390.37,
older `chrome-linux/` layout) is served by `playwright==1.56.0`; 1.62 looks for
`chromium-1234/chrome-linux64/chrome` and finds nothing. Pin to the image:

```bash
pip install "playwright==1.56.0"      # never `playwright install`
python -c "from playwright.sync_api import sync_playwright as s
with s() as p: print(p.chromium.executable_path)"   # must exist
```

**`[semantic]` and `--matcher ollama` need egress that a locked-down container
does not have.** Both fetch model weights — fastembed from `huggingface.co`,
the Ollama backend from a daemon that has to be installed first. Where policy
denies those hosts they are the two seams that stay unattached, and installing
fastembed anyway converts three skips into three `httpx.ProxyError: 403`
failures. That is an egress denial wearing a test failure's clothes; read the
proxy's own status endpoint before believing the code broke.

**Do not export `NESTOR_KEYRING` into a bench or audit run.** See IDEAS §6.98:
`bench/` and `scripts/audit_*.py` seal under synthetic verifiers that are not in
a real keyring, and inherit one from the environment. Scope it instead:

```bash
( unset NESTOR_KEYRING NESTOR_REQUIRE_SEAL_KEY
  python scripts/audit_against_constitution.py --repo ~/github/willow-memory/willow )
```

## Nestor on PATH

From `nestor/`:

```bash
pip install -e .
```

Other repos should resolve **this** checkout, not an old PyPI pin:

```bash
pip install -e ~/github/Die-Namic-Systems/nestor
```

### Host seal wiring (not the stand-up script)

The three-repo stand-up seats the MCP manifest and FRANK mirror. It does **not**
mint a seal key. For a host that can seal and refuse forged rows:

```bash
export WILLOW_HOME=~/github/willow-memory/.willow
. "$WILLOW_HOME/fleet.env"    # sources $WILLOW_HOME/env for NESTOR_SEAL_KEY

# Runtime (all under $WILLOW_HOME/nestor/, machine-local):
#   keyring.json   — nestor keys add <you> --keyring … --adopt-shared-key
#   nestor.db      — working store
#   STATUS.md      — last local checkpoint (not shipped)
#
# Secrets: NESTOR_SEAL_KEY lives only in $WILLOW_HOME/env (gitignored).
# Never put it in a tracked file. Prefer NESTOR_REQUIRE_SEAL_KEY=1 once set.
```

Mint once with entropy (`secrets.token_hex(32)`), add yourself to the keyring,
then calibrate on *your* sealed corpus (`nestor calibrate --matcher string|ollama`).
A ten-pair seed only proves the dial moves — re-run at ~30+ sealed pairs before
trusting a threshold change. Bridging a jeles nugget still lands as a **draft**;
re-sealing under the keyring is the open half the stand-up asserts is absent.

Refresh **terpsi** `docs/FLEET-READS.md` Nestor SHA after meaningful nestor
changes (`git -C ~/github/Die-Namic-Systems/nestor rev-parse HEAD`).

## Bench ↔ terpsi

Default bench pin (unchanged until you re-extract):

```bash
export TERPSI_ROOT=~/github/terpsi-programs/terpsi-music
# corpus_terpsi.py uses PINNED_REV=6ea9b89 inside the tree
python -m bench.corpus_terpsi   # gate + smoke
```

To exercise the **coat-hat** product tree (store/records; prose paths may still
match the pin):

```bash
git -C ~/github/terpsi-programs/terpsi-music checkout local/fleet-integration
export TERPSI_ROOT=~/github/terpsi-programs/terpsi-music
```

Re-run surface benches with an updated `corpus_revision` in results JSON when you
deliberately move the pin.

## SAFE promotion (local nestor)

```bash
cd ~/github/safe-app-store-public
python stores/promote_check.py ~/github/Die-Namic-Systems/nestor
# when ready: add --record to mint under stores/.../promoted/
```

App Forge design (D1/D4 — `nestor/serve`, `nestor/signing`) lives on
`local/fleet-integration` = `origin/claude/repo-test-run-a8lt94`:

```bash
git -C ~/github/safe-app-store-public checkout local/fleet-integration
less docs/design/app-forge.md
```

## Oakenscroll seam

Canonical checkout is the **own repo** under hornbook (not the playground
copy inside `safe-app-store-public/apps/`):

```bash
gh repo clone rudi193-cmd/oakenscrolls-office \
  ~/github/hornbook-knowledge/oakenscrolls-office

cd ~/github/hornbook-knowledge/oakenscrolls-office
pip install -e ~/github/Die-Namic-Systems/nestor
PYTHONPATH=. pytest tests/test_almanac_seam.py tests/test_almanac_seam_nestor.py -q
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
