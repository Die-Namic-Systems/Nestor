[NESTOR REPO — LOCAL-FIRST SEAT]

**Cloud / fresh session:** `git fetch origin` then checkout the PR branch (`gh pr
checkout <n>` or `git pull` on your branch) *before* editing — otherwise you
reintroduce lint fixes the remote already has. Run `bash scripts/ci-lint.sh` before
push.

You are in the **Nestor product source** (`nestor/` package, tests, docs, dogfood).
This is not the willow charter seat and not an operator Jarvis desk.

## Do here (default)

- Edit code and markdown **in this repository** with normal IDE tools.
- Use the repo **`.venv`** and documented commands (`docs/agent-guide.md` → Environment).
- Verify with **`bash scripts/ci-lint.sh`** and **`python -m pytest -q`** (see `AGENTS.md`).
- Use **`nestor` CLI** against local paths (`--db`, `nestor ui`, export/import) when exercising the product.
- Record product decisions in **`docs/dogfood/decisions/`** and rebuild with **`python scripts/dogfood_store.py --rebuild`** (see `docs/agent-guide.md` → Decisions go in the store).

## Do not use for routine Nestor work

- **willow-mcp** / **willow** fleet MCP (`store_*`, `knowledge_*`, `task_submit`, Kart, `dispatch_*`, SOIL, FRANK, …).
- **Nestor exposed as MCP** (`nestor serve`) to drive changes in *this* tree — write the code here first.
- Treating dogfood or README edits as fleet KB atoms before they are reviewed in git.

Fleet wiring (SOIL gap import, charter rollup, Hanuman handoffs) is **after** the code and docs exist — see `docs/local-fleet.md`, `scripts/import_willow_gaps.py`, `scripts/apply_sealed_fleet_gaps.py`.

**Household hosts:** Nestor ledger and keep state belong under **`~/.nestor`** (`NESTOR_HOME`) — see `docs/home-paths.md` and `nestor.home_paths.bind_ledger()`. A host embedding Nestor in another face pins the root explicitly (`NESTOR_HOME="$HOMESTEAD_HOME"`); setting the old var alone is refused, not guessed.

## Governance (unchanged)

**You may propose. You may not confirm.** No `status="sealed"` and no `verifier=` with a human name unless they signed in `nestor ui` (`docs/agent-guide.md`).
