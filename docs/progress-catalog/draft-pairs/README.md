# Draft pairs — threshold policy (ready for seal)

These are **draft** artifacts. The machine may propose; a human must seal.

## Decision pairs (dogfood path) — **sealed 2026-08-31**

Primary source: [`../../dogfood/decisions/0228-three-threshold-bars-operating-policy.json`](../../dogfood/decisions/0228-three-threshold-bars-operating-policy.json)

All six 0228 pairs sealed by **sean campbell** in `docs/dogfood/nestor.db`. Seal files exported; `docs/dogfood/verifiers.json` updated; `python3 scripts/dogfood_store.py --verify` passes (229/229 sealed).

```bash
cd Die-Namic-Systems/nestor
python3 scripts/dogfood_store.py --verify
```

Seal via `nestor ui` (review queue) or export seals:

```bash
python3 -m nestor.cli ui --db docs/dogfood/nestor.db --verifier "<you>" --open
python scripts/dogfood_seal_export.py --decision 0228 --from-db docs/dogfood/nestor.db
# add verifier key to docs/dogfood/verifiers.json if needed
python scripts/dogfood_store.py --rebuild
```

Deterministic pair ids are in [`decision-pairs.json`](decision-pairs.json) — use them to attach evidence or find rows in UI.

## Numeric baselines (nestor_check path) — **still open**

[`numeric-baselines.json`](numeric-baselines.json) lists labels for `nestor check` / MCP `nestor_check`.

These live in **`~/.nestor/keep`**, not dogfood. Seal in live UI:

```bash
python3 -m nestor.cli ui --open
# Numeric reconcile tab — use labels from numeric-baselines.json exactly
```

After sealing, verify (`observed` is a **positional** argument, not `--observed`):

```bash
# From repo root — nestor shim not required:
python3 -m nestor.cli check false_seal_rate_prose_4000_at_092 0.004
python3 -m nestor.cli check decision_collision_rate_at_092 0.00333

# Or install the CLI once:
pip install -e .
nestor check false_seal_rate_prose_4000_at_092 0.004
```

## Live memory pairs (599 decision domain)

To seal into `~/.nestor/keep` (operator household store), propose then seal the same question/commitment text from `decision-pairs.json` with domain `decision→decision`. Dogfood rebuild does **not** write to `~/.nestor/keep` — that is a separate operator action.
