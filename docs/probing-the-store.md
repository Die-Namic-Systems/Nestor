# Probing the store — running the whole meaning suite over a list of prompts

**One command, every read-only lens, one report.** Written to answer *"what
does Nestor's own store say about a topic when every lens gets a turn?"* — the
question that surfaced on 2026-08-25 when a single-lens sweep of the open
issues concluded "nothing there" while another lens had a match at 0.578 on
the same store, same prompt.

```
python scripts/issue_probe.py \
    --db docs/dogfood/nestor.db \
    --prompts scripts/corpus/open_issues.txt \
    --snapshot \
    --out docs/archive/probes/open_issues.md \
    --out-json docs/archive/probes/open_issues.json
```

Defaults: `--db docs/dogfood/nestor.db`, `--prompts scripts/corpus/open_issues.txt`,
`--from decision --to decision`, `--resolve-domain entity`. Report writes to
stdout unless `--out` is passed.

**Use `--snapshot` on a git-tracked store.** `ask` and `resolve` append audit
rows to the ledger on every call — that is the ledger doing its job — so
probing a shipped store like `docs/dogfood/nestor.db` without `--snapshot`
adds a diff on the ledger every time. `--snapshot` runs against a SQLite
`VACUUM INTO` copy in a tempdir and leaves the source ledger untouched.
Omit it when you *want* the consultation on record (a live keep, an ephemeral
scratch store).

## What each lens sees

The runner shells out to the `nestor` CLI on `PATH` — the exact code path a
user runs — and groups the calls into two kinds.

### Per-prompt (called once per line in the prompts file)

| Lens | What it looks for | Silent when |
| --- | --- | --- |
| `nestor ask` (offline engine) | Cascade over the store; served target above the seal bar (default 0.92) | Nothing above the bar; a paraphrase below it reads as "no answer" |
| `nestor resolve` | Surface form → canonical entity | The corpus has no rows in the resolve domain (default `entity`; the dogfood store is `decision`-only, so this is expected to be quiet there) |
| `nestor match` | Bare seam — every row scored, top hits shown | The prompt has no lexical overlap with any source text |
| `nestor decision check` | Recorded rejections, contradictions, live proposals | No decision text within the fuzzy bar (default 0.45, seal bar 0.92) |

`nestor ask` is pinned to `--engine offline` for determinism — a re-run without
network access has to produce the same numbers. A user who wants the LLM
cascade calls `nestor ask` themselves; the report is honest about which engine
it used.

**Non-zero exits are signals, not failures.** `nestor ask`, `resolve`, and
`match` exit 1 when nothing served above the seal bar; `decision check`
exits non-zero on a recorded rejection or contradiction
([docs/decision-memory.md N9](decision-memory.md)). The runner records the
exit code on every invocation (`exit=N` in the report) and keeps going —
`exit 1` next to a lens block is the *answer*, not the script tripping.

### Corpus-level (called once, at the top of the report)

| Lens | What it says |
| --- | --- |
| `nestor stats` | Pair count, sealed/draft split, domain histogram, seal-signature policy, ledger intactness |
| `nestor rejections` | Aggregated `no`s — a query refused ≥2 times, a pair refused for ≥2 queries |
| `nestor triage` | Themed groups, proposed supersede/contradict/refine edges, resolved-vs-open split |
| `nestor calibrate` | Where the seal bar sits for this corpus — degrades gracefully to *"nothing sealed here yet"* rather than inventing a number |
| `nestor evidence report` | Sealed pairs with no evidence attached |

## What none of the lenses can see

- **The runner shells out to whatever `nestor` is on `PATH`.** A different
  venv, an older wheel, a shim — the report is about *that* Nestor and the
  environment header names the binary so a reader catches the mismatch. If
  no `nestor` is on `PATH`, the runner refuses to produce a report rather
  than write one about nothing.
- **A missing DB is a hard failure.** An empty report reads identical to
  a store with nothing to say (the exact defect [#95](https://github.com/die-namic-systems/nestor/issues/95)
  is filed for), so the runner refuses to run when `--db` does not exist.
- **`resolve` defaults to `--domain entity`.** A `decision`-only corpus
  (the dogfood store) genuinely has no entity candidates. That is reported
  as `candidates: 0`, not as a broken lens. Pass `--resolve-domain decision`
  to point it at what is actually there.
- **`calibrate` on an unsealed corpus** cannot measure a bar and says so in
  prose. The runner quotes the prose verbatim rather than making up a
  number.
- **`stderr` warnings are captured.** `NESTOR_SEAL_KEY not set — seal
  signatures are NOT verified` and its siblings are answers about the
  seat, not noise; every invocation carries a `stderr_warnings` list, and
  the Markdown report renders them under each lens block.

## Refreshing the prompts

`scripts/corpus/open_issues.txt` is a hand-maintained snapshot: one prompt
per non-blank, non-`#` line. To probe a different set — a design doc, a
review checklist, a new issue batch — point `--prompts` at any text file
following the same convention:

```
# your comment
first prompt
second prompt
```

The runner treats an empty prompts file as a hard error for the same reason
it treats a missing DB as one.

## Reproducing the open-issues sweep

The report archived at [`docs/archive/probes/open_issues.md`](../archive/probes/open_issues.md)
was produced by:

```
python scripts/issue_probe.py --snapshot \
                              --out docs/archive/probes/open_issues.md \
                              --out-json docs/archive/probes/open_issues.json
```

That snapshot is **historical** (520-draft dogfood store, cloud CI path). Re-run
against a current checkout to refresh; commit under `docs/archive/probes/` with
a dated name if the sweep is worth keeping.
