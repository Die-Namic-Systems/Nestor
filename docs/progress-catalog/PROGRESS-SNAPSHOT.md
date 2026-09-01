# System Progress Snapshot — 2026-08-31

Shareable summary. Numbers tagged **measured** unless `nestor_check` returned a sealed baseline (none did for headline metrics this session).

## Headline metrics

| Track | Metric | Value | Status |
|-------|--------|-------|--------|
| Nestor safety | False-seal rate @ 0.92 (prose, n=4000) | 0.4% | measured (numeric baseline not sealed in live store) |
| Nestor utility | Paraphrase recall @ 0.92 | 24.8% | measured |
| Decision memory | Collision rate @ 0.92 (live calibrate, n=300) | 0.33% | measured 2026-08-31 |
| Threshold policy | 6 decision pairs (0228) | sealed | dogfood store + seal files |
| Decision memory | Sealed pairs | 599 | measured |
| Decision memory | Dogfood decisions | 78 files | measured |
| Corpus | Claims / sources | 33,720 / 68 | draft inventory |
| DPO (archive) | slm-corpus rows | 284 DPO + 1,228 SFT train | archive-only |
| DPO (external) | yggdrasil harvest | 137 taken / 29,002 refused | measured §6.89 |
| LoCoMo (archive) | judge_correct | 61.0% | measured 2026-06-24 |

## What works

- **Seal-state / propose refusal** — holds unqualified (code-read verdict, WHAT-EXISTS-ALREADY)
- **Decision N1 with semantic matcher** — 24/24 paraphrase recall at shipped bar
- **Corpus consolidation** — 68 sources, refresh pipeline shipped
- **Threshold policy (0228)** — six bars documented and **sealed** in dogfood (`docs/dogfood/seals/`, `--verify` passes)
- **Human verification lane** — 599 sealed pairs in live store; dogfood corpus 229/229 sealed (2026-08-31 UI session)

## What does not (yet)

- **String matcher on paraphrase** — decision_n1 recall 0/24 at 0.92 (use constraint bar 0.45 or semantic for re-wording)
- **Safe + useful on serve** — accuracy bench: StringMatcher cannot do both; policy uses three bars (see THRESHOLD-POLICY.md)
- **Live training artifacts** — slm-corpus absent from live vault; only in greenfield archive
- **159-language codebase-memory eval** — plan written, not executed

## Timeline (selected shipped items)

Distilled from agent-log — full chronology in [`docs/agent-log.md`](../agent-log.md):

- Semantic matcher + batch embed + persisted embeddings — **shipped** (Jul 2026)
- Local Ollama embeddings matcher — **shipped** (Aug 2026)
- Corpus refresh from greenfield legacy-flat — **shipped** (Aug 2026)
- yggdrasil pair corpus measured — **refused at scale** (Aug 2026)

## What's next

From [`FOLLOW-UPS.md`](../../../../FOLLOW-UPS.md), findings, and **[`THRESHOLD-POLICY.md`](THRESHOLD-POLICY.md)**:

- **Threshold policy documented** — serve 0.92, context/triage 0.55, constraints ~0.45 (2026-08-31 calibrate)
- Optional: **seal** threshold policy in Nestor memory for `nestor_check` baselines
- Vault seam / fleet store root decision
- Optional slm-corpus repatriation
- Execute or defer codebase-memory-mcp eval pilot

## Appendix

- Full inventory: [`INVENTORY.md`](INVENTORY.md)
- Analysis: [`FINDINGS.md`](FINDINGS.md)
- **Threshold policy:** [`THRESHOLD-POLICY.md`](THRESHOLD-POLICY.md)
- Nestor bench charts: `python bench/serve_ui.py` in nestor repo
- Catalog browser: open [`ui/index.html`](ui/index.html) (loads `ui/data/catalog.json`)
- SOIL mirror: collection `willow_progress_catalog` (2 summary records)
