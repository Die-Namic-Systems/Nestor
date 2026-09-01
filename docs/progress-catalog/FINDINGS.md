# Progress Catalog — Findings

Generated **2026-08-31** from MCP inventory (`nest_scan`, `nestor_ledger_verify`, `nestor_check`) plus local `catalog.jsonl`.

## What is real (Tier 1 — present with evidence)

### Nestor retrieval safety (live bench)

Source: [`nestor/bench/results/accuracy.json`](../../bench/results/accuracy.json)

| Metric | Value | nestor_check |
|--------|-------|--------------|
| False-seal rate @ shipped threshold 0.92 (prose corpus, size 4000) | **0.004** (1/250 absent probes) | `no_baseline` |
| Paraphrase recall @ same point | **0.248** | `no_baseline` |

**Finding:** At the shipped bar, false seals are nearly eliminated on absent probes, but paraphrase recall stays low (~25%). The bench argument stands: no threshold is simultaneously safe *and* useful for meaning-preserving rewrites.

Interactive charts: `python bench/serve_ui.py` from nestor repo root.

### Decision memory (live)

| Metric | Value | nestor_check |
|--------|-------|--------------|
| Sealed pairs in Nestor memory | **599** | `no_baseline` |
| Dogfood decision JSON files | **78** | — |
| decision_n1 @ 0.92 (string matcher) | rank1=21/24, **recall=0** on paraphrase | — |
| decision_n1 @ 0.92 (semantic stand-in) | rank1=24/24, **recall=24/24** | — |

**Finding:** String matching finds surface-similar decisions but fails paraphrase; semantic stand-in passes the N1 bench. Matches the product thesis in agent-log and WHAT-EXISTS-ALREADY.

### Corpus scale (live snapshot, draft)

Source: [`forge-play/forge-jig/docs/WHAT-EXISTS-ALREADY.md`](../../../../forge-play/forge-jig/docs/WHAT-EXISTS-ALREADY.md)

| Metric | Value | nestor_check |
|--------|-------|--------------|
| Claims | **33,720** | `no_baseline` |
| Sources | **68** | — |

All corpus rows are **draft** by construction — attributed pointers, not verified answers.

### DPO / training pipeline (archive-only — biggest gap)

Live `~/sean-data-vault` has **no `slm-corpus/`**. Full pipeline exists only in greenfield archive:

`~/github-archive-greenfield-2026-08-10/workshop/sean-data-vault/slm-corpus/`

| Artifact | Lines | Size |
|----------|-------|------|
| dpo.jsonl | 284 | 1.4 MB |
| sft_train.jsonl | 1,228 | 4.1 MB |
| sft_val.jsonl | 57 | 173 KB |
| inputs.jsonl | 1,853 | 4.1 MB |

Training runs present: `kaggle-3b`, `kaggle-3b-v2`, `kaggle-3b-v3`, `kaggle-3b-v4`, `local-1b`.

**nest_scan:** 1,376 files indexed → `nest-dbs/slm-corpus.db` (9 redacted credential fragments flagged in digest).

External yggdrasil (private repo, agent-log §6.89): **137 taken, 29,002 refused** — refusal is the finding (model output must not become operator-authored corpus).

### Local model eval (archive-only)

**LoCoMo** (`.willow-archive/locomo_results/`, latest run 2026-06-24):

| Metric | Value |
|--------|-------|
| judge_correct | 0.610 |
| token_f1 | 0.415 |
| recall@10 | 0.992 |
| MRR | 0.485 |

**Ollama bench** (pikoci-rig, 2026-05-17): archive JSON only; not in live github. Mixed PASS/TIMEOUT across gemma2 probes.

**Stance eval** (`willow-gate/scripts/stance_eval.py`): not re-run this session; prior harness compares blind vs stance-aware friction on 9k sycophancy pairs.

### Fleet simulation (live, Tier 2)

**651** warrant-loop campaign ledgers in `workshop/warrant-loop/box/` (~13k ledger lines). Operational history, not bench-scored.

## What is noise or duplicate (Tier 3)

- **~13 GB duplicate `.willow` snapshots** in greenfield github archive vs `.willow-archive-greenfield`
- **Venvs / llama.cpp / kaggle weights** under slm-corpus/tools (skip for narrative)
- **Legacy-flat prose** — largely ingested into Nestor corpus 2026-08-30; archive holds duplicates
- **Pre-greenfield nestor snapshot** in archive (37 MB) — live nestor is authoritative

## Gaps logged

- `nestor_check` has **no sealed baselines** for headline metrics → PROGRESS-SNAPSHOT marks them **measured, not verified**
- `store_put` to `progress_catalog` denied; catalog mirrored in **`willow_progress_catalog`** (allowed by `willow_*` scope) + local `catalog.jsonl`
- `nestor_corpus_map` withheld on MCP (no `--corpus-dir`) — used tombstones + WHAT-EXISTS-ALREADY instead
- **codebase-memory-mcp eval plan** — specification only, no scores yet

## Threshold calibration (2026-08-31)

Live `nestor calibrate --from decision --to decision` on **599 sealed pairs**:

- @ **0.92**: **0.33%** collision rate (1/300 sampled) — **below 1% target** → serve bar is safe on collision floor
- First **zero-collision** point in sweep: **0.96** (near-duplicate decisions at 0.94 and 0.861)
- **Do not lower serve to 0.45** — that bar is for `constraints_on` / triage, not verified serve

Triage sweep on 223 decisions: knee at **0.55** (208 groups, 1 edge); **0.92** = 223 groups, 0 edges.

Full policy: [`THRESHOLD-POLICY.md`](THRESHOLD-POLICY.md)

## Recommended next bites

1. **Seal [`THRESHOLD-POLICY.md`](THRESHOLD-POLICY.md)** in Nestor memory → `nestor_check` baselines for headline metrics
2. **Promote slm-corpus subset** to live vault if training resumes (operator decision)
2. **Normalize archive LoCoMo + ollama bench** into `nestor/bench/results/archive_runs.json` for unified charts
3. **Seal baseline metrics** in Nestor if these numbers should be shareable as verified
4. **Re-run stance_eval** and file output beside LoCoMo in catalog
