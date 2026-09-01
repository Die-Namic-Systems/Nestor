# Threshold policy — operating bars

**Status:** Sealed in dogfood store 2026-08-31 (`0228`, verifier: sean campbell). Seal files under `docs/dogfood/seals/`. Live `~/.nestor/keep` is unchanged (599 pairs) — MCP `nestor_ask` serves household memory, not dogfood unless imported.  
**Evidence:** Live calibrate run + committed bench JSON.

---

## Summary

Nestor uses **three bars**, not one global dial. The serve bar (`0.92`) is for **verified tier-1 serve** only. Lower bars handle **context**, **triage**, and **decision constraint lookup** without claiming verification.

| Bar | Value | Code / path | Job |
|-----|------:|-------------|-----|
| **Serve** | **0.92** | `SEAL_THRESHOLD` in `nestor/memory.py` | Serve a sealed pair as verified (tier 1) |
| **Context** | **0.55** | `CONTEXT_THRESHOLD`; triage `DEFAULT_BAR` | Feed engine / cluster review queue |
| **Constraint** | **0.45–0.55** | `DecisionMemory(fuzzy_bar=…)` | Map re-worded questions to the right decision (`constraints_on`) |

**Do not** lower the serve bar to fix paraphrase recall. `decision_n1.json` shows rank@1 **88–96%** at 0.92 with **recall 0/24** — the correct row is usually first; scores sit below the serve bar. Paraphrase on serve requires a **semantic matcher** (or pending/draft), not a threshold tweak.

---

## Live calibration — decision domain (2026-08-31)

```bash
cd Die-Namic-Systems/nestor
python3 -m nestor.cli calibrate --from decision --to decision
```

**599 sealed pairs** (`decision→decision`); sampled 300.

| Threshold | Collisions (sampled) | Rate |
|-----------|---------------------:|-----:|
| 0.80 | 2 | 0.67% |
| 0.90 | 1 | 0.33% |
| **0.92 (shipped)** | **1** | **0.33%** |
| 0.96 | 0 | 0.00% |

- Target collision rate: **1%**. **0.92 already meets it** (0.33% < 1%).
- Calibrate’s “lowest threshold meeting target” is **0.80** — meaning the corpus could go lower on *collision safety* alone; **recall cost is not measured here**.
- To eliminate known near-duplicate collisions among sealed pairs, **0.96** is the first clean point in this sweep.
- Two worst collisions (both human-sealed, different answers):
  - score **0.940** — “eight gap assertions” vs “new gap assertions”
  - score **0.861** — jeles audit reader vs demo gate question

Full JSON: [`calibrate/decision-decision-string.json`](calibrate/decision-decision-string.json)

**Default `en→es` domain:** 0 sealed pairs in live memory (all 599 pairs are `decision→decision`). Nothing to calibrate there until translation pairs are sealed.

---

## Synthetic bench — why serve stays at 0.92 (StringMatcher)

From [`bench/results/accuracy.json`](../../bench/results/accuracy.json) and IDEAS §1.3:

| Corpus | At 0.92 false-seal | At 0.92 paraphrase recall |
|--------|-------------------:|--------------------------:|
| prose 4000 | 0.4% (measured in catalog) | ~25% |
| boilerplate 24k | 16.4% | 23.6% |

**There is no StringMatcher threshold that is simultaneously safe and useful on both corpora.** Tuning `SEAL_THRESHOLD` alone cannot fix paraphrase; it picks which failure mode you accept.

Interactive charts: `python bench/serve_ui.py`

---

## Decision re-wording bench

From [`bench/results/decision_n1.json`](../../bench/results/decision_n1.json):

| Matcher | @ 0.92 rank@1 | @ 0.92 recall | Clean knee (wrong_key=0) |
|---------|--------------:|--------------:|-------------------------:|
| string | 21/24 | 0/24 | bar **0.45** → 18/24 recall |
| token | 23/24 | 0/24 | bar **0.45** → 15/24 recall |
| semantic stand-in | 24/24 | 24/24 | upper bound (not production matcher) |

**Policy implication:**

- **`constraints_on` / fuzzy lookup:** bar **~0.45** recovers re-wordings with zero wrong-key on the N1 corpus (string matcher).
- **Triage clustering:** bar **0.55**, not 0.45 — audit corpus flooded at 0.45 (`nestor/triage` contract).
- **Verified serve:** stay **0.92** until semantic matcher owns the serve path with its own calibrated bar.

---

## Operating rules

1. **Queries below 0.92 on StringMatcher** → return **pending** or **draft** with top candidate; do not tier-1 serve.
2. **Do not lower global `SEAL_THRESHOLD`** to improve paraphrase — use constraint bar, context bar, or semantic matcher.
3. **Re-calibrate** after significant seal growth (`nestor calibrate --from decision --to decision`).
4. **Near-duplicate decisions** (scores 0.86–0.94 between different answers) → human review / supersede; threshold cannot split them at 0.92.
5. **Before changing serve bar**, re-read collision examples in calibrate output and re-run `bench_accuracy` on held-out probes.

---

## Optional next step — seal this policy

`nestor_ask` for “serve threshold 0.92” returned **pending** (no sealed policy pair yet).

**Draft pairs ready:**

- Dogfood: [`../../dogfood/decisions/0228-three-threshold-bars-operating-policy.json`](../../dogfood/decisions/0228-three-threshold-bars-operating-policy.json) (6 decisions)
- Pair ids + numeric baselines: [`draft-pairs/`](draft-pairs/)

After operator seal → `nestor_check` can verify snapshot metrics.

---

## Files

| Path | Content |
|------|---------|
| [`calibrate/decision-decision-string.json`](calibrate/decision-decision-string.json) | Machine calibrate output |
| [`calibrate/decision-decision-string.txt`](calibrate/decision-decision-string.txt) | Human summary |
| [`calibrate/en-es-string.json`](calibrate/en-es-string.json) | Empty en/es corpus |
| [`calibrate/triage-sweep.txt`](calibrate/triage-sweep.txt) | Triage bar sweep |
