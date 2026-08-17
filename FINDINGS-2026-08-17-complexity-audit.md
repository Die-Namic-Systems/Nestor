# FINDINGS 2026-08-17 — full-scope complexity audit

Four read-only Sonnet auditors were run in parallel over non-overlapping slices
of the tree, on the `claude/overwhelm-discussion-gmtbjg` branch, right after the
README trim (decision 0146). The brief: find what is **overly complicated** and
might interfere with **human usability** and/or **agent usability** — full scope.
Slices: (1) docs & narrative, (2) CLI/UI/MCP surfaces, (3) core library & seams,
(4) governance ritual & agent machinery.

This is a record of what was found and how it was argued — not a set of sealed
decisions. Nothing here is committed as a change. Effort tags: S/M/L. Audience:
HUMAN / AGENT / BOTH.

---

## Cross-cutting themes (the same defect showing up in several slices)

**A. Fleet/Willow machinery has leaked into a "standalone, zero-dependency" product.**
The README's headline claim is *no upward dependency on any host*, yet:
- `nestor ui` with **no flag** probes `~/github/.willow` and a dated one-off file
  `~/github/willow/governance/decisions/nestor-phase1-gate-seals-2026-08-06.json`
  on startup, and the single-page UI carries permanent "Fleet gate" bands,
  `Hanuman ✓` pills, and gap-title regex parsing (`ui.py:440-475,1722-1728`,
  `ui_page.py:1653-1802`). `nestor ui --help` says "Hanuman dispatches" with no
  definition. **BOTH. M.**
- Docs scatter unmarked proper nouns (jeles, FRANK, willow SOIL, Hanuman, Grove,
  Kart) and links to private repos across ~6 files; `frank.md`'s "*Fleet-only*"
  banner is the right pattern, applied inconsistently. **BOTH. M.**
- `docs/home-paths.md` (93 ln) and `docs/roots-willow-and-homestead.md` (121 ln)
  substantially duplicate each other (same env-var table, same refusal argument).
  **BOTH. M.**

**B. The same sentences live in many places (drift risk + reading burden).**
- "You may propose. You may not confirm." appears verbatim in `hooks/seat.md:31`,
  `AGENTS.md:51`, `docs/agent-guide.md:77`, `hooks/reinject.py:39` (constant),
  and paraphrased in `before_authority.py:71` — **six copies**, and
  `reinject.py:47-60` carries drift-detection to police its own copy against
  seat.md. `CLAUDE.md` explicitly says "Do not duplicate policy here — it drifts,"
  then does. **BOTH. S.**
- The three-state concept (sealed/draft/pending) is re-derived **4× inside the
  README** (state table, "The mechanic", "The category", the recipe tier table).
  **BOTH. M.**
- `TODO.md` / `QUESTIONS.md` / `IDEAS.md` each carry paragraph-length recaps of
  the same open items (sync, erasure, seal staleness); TODO.md's own disclaimer
  ("if this disagrees with those, they're right and this is stale") admits the
  drift. **BOTH. M.**

**C. Governance ceremony taxes a well-behaved agent (the "overwhelm").**
- The **review-desk write-gate** (`before_write.py:42-124`) hard-blocks edits to
  nearly all Python in the tree (`GATED_DIRS = nestor, recipes, demo, tests,
  scripts, hooks`) until `demo/review_desk.py … bearing "…"` is run. It is
  disclosed **only in the denial** — nothing at SessionStart warns you (I hit
  this exact wall editing a test today). And it is cleared by a **content-blind
  rote call** (`review_desk.py:117-129` records before the lookup runs, never
  checks the bearing text relates to the change), so it is both surprising *and*
  not forcing the reflection it is named for. Its content (product-matching
  findings from agent-log §6.N) has no bearing on, e.g., fixing a hook typo.
  **AGENT. S** (narrow `GATED_DIRS` to `nestor, recipes`; surface at SessionStart).
- Seat rules are **re-injected into every prompt unconditionally**
  (`reinject.py`, `hook_runner.py:181`), unlike `before_build`/`before_propose`
  which are intent-gated. **AGENT. S.**
- Every Write/Edit and every Bash spawns **two** hook subprocesses
  (`before_write`+`before_authority`, `before_bash`+`before_authority` —
  `.claude/settings.json:58-84`); every prompt spawns **three**
  (`reinject`+`before_build`+`before_propose`). Latency tax per action. **BOTH. M.**
- `before_stop.py:101-110` counts only digits/exit-codes/`file:line` as evidence;
  a truthful "I ran the tests and they passed" with no number can trip a one-time
  hard block (`_HARD_CLAIM_PATTERNS`). Honest agent still stalls. **AGENT. M.**

**D. Surprising first-contact footguns (cheap to fix, high frequency).**
- **Global `--db`/`--ledger`/`--json` must precede the subcommand.** `nestor ask
  "hi" --db x.db` → `error: unrecognized arguments: --db x.db`, no hint that
  reordering fixes it. Worse, `ui`/`serve` *do* accept them after the subcommand
  (special-cased), so the learned pattern breaks on the other 15 commands.
  `cli.py:742-745,926-952`. **BOTH. S.** — *the single highest-frequency failure
  any new human or agent will hit; cheapest fix; no design tradeoff.*
- `--abs-tol`/`--pct-tol` are **silently ignored** by the CLI for non-numeric
  matchers (`answer.build_matcher:32-67`), while `nestor serve` **refuses** the
  same situation as an error (`serve.py:126-167`). Confident-wrong shape the MCP
  surface was built to avoid, reintroduced one surface over. **BOTH. S.**
- `translate_segment` probes an engine's signature with `except TypeError`
  (`cascade.py:484-492`) — **swallows genuine TypeErrors inside a custom engine**
  and silently retries with fewer args (extra side-effecting calls). Use
  `inspect.signature`. **AGENT. S.**
- `ensure_home_layout(home=…)` **mutates process-global `os.environ`**
  (`home_init.py:50-60`) as a side effect of a path parameter. **BOTH. S.**
- `Curator.list()` **shadows the builtin**, forcing `builtins.list[dict]` on every
  later method (`curator.py:138-158`); a future method that forgets it gets a
  confusing mypy error. Rename `browse()`. **HUMAN/AGENT. S.**
- `nestor decision` / `nestor db` require a single-choice verb spelled out
  (`decision check`, `db checkpoint`) — make it `nargs="?"` with a default.
  **BOTH. S.**
- `--json` silently dropped for `ui`/`serve` (`cli.py:946`) — print a one-line
  note instead. **AGENT. S.**

**E. Capability / API sprawl (integrator & extender overwhelm).**
- The Storage docstring says **six** optional capabilities; the code has **nine**
  (`supports_edges`, `supports_evidence`, `supports_embedding_store` added
  without updating it). Each ships its own all-or-nothing tuple + cast-Protocol +
  `_require_*` wrapper, duplicated across `memory/decision/evidence/curator`.
  `storage.py:23-46`. **BOTH. S** (docstring) **/ M** (consolidate into one
  table-driven `require_capability(store, name)`). — *highest integrator leverage.*
- `add_pair` is **270 lines / 15 params** encoding 6+ conflict paths
  (`memory.py:305-577`); `import_bundle` similarly (`portable.py:406-675`). The
  *behavior* is earned by real incidents — the *packaging* is the problem; extract
  named guard/step helpers, ~40-line orchestrators. **BOTH. M.**
- **Eight process-global injection points** (`set_store/set_matcher/
  set_bilingual_loader/set_ledger_path/set_ledger_verify_interval/set_keyring/
  set_glossary_path/set_forwarder`), each with subtly different caching/precedence.
  A doc table + "prefer explicit `store=`/`matcher=`" would help; parallel tests
  stepping on globals is a live footgun. **BOTH. S** (doc).
- **14 refusal exceptions, no common base** to catch (`memory/curator/portable/
  keyring/signing/sqlite_store/home_paths`). Add `NestorError`/`NestorRefusalError`
  base, no message/identity change. **BOTH. S.**
- `Matcher` Protocol declares **2** methods; the real contract is **4** (`score`,
  `similarity_bound` are duck-typed and carry an uncheckable soundness rule).
  A new matcher can type-check and still corrupt `best_sealed` pruning. Fold into
  a documented optional extension Protocol or ship `matcher.self_check(...)`.
  **AGENT. M.**

**F. Doc-surface volume & taxonomy.**
- ~10 "design memo" files are **linked from nowhere** but `project-layout.md`'s
  manifest (`carried-strings`, `seal-staleness-and-quorum`, `detection-kit-as-
  gates`, `decision-rewording-bench`, `embedder-stand-in`, `evidence-edge`,
  `two-stores`, `covenant-lineage`, `corpus-order`, `decision-memory`). Growing
  one-file-per-idea, unbounded, no index separating "reference" from "argument".
  **BOTH. M/L.**
- `IDEAS.md` (2126 ln) + `docs/agent-log.md` (6657 ln, ~59k words) — larger in
  prose than the product's source; the CI-gated Map helps, but agent-guide tells
  every session to keep appending. Consider "grep, don't read" + age-based split.
  **AGENT. L.**
- Demo-store artifacts pollute the reference-doc namespace: `docs/llm-only-joke/`
  (dir) vs `docs/llm-only-jokes.md` (file), `docs/ideas-store/` (500KB bundle),
  binary `docs/dogfood/nestor.db` (688KB). Move under `demo/`/`docs/examples/`.
  **BOTH. S.**
- `docs/felt-cost.md` (141 ln essay on operator mood) and
  `docs/live-forever-verse.md` (a song) sit unlinked at the same level as
  `storage-protocol.md`; both are self-aware they don't belong. Move to a
  `docs/journal/`. **HUMAN. S.**
- `docs/agent-guide.md` (360 ln, the one file every session reads) interleaves
  rules with incident narrative; split into a scannable rules-first reference +
  a "why" appendix. **AGENT. M.**

---

## Leave as-is — intentional safety, not accidental complexity

- Ledger locking, tail-checkpointing, chain verification, `ledger_preflight`,
  fail-closed appends (`cascade.py`) — each traces to a measured concurrency/
  tamper bug; the audit-trail promise requires it.
- `signing.py`/`keyring.py` domain-separated message encodings + per-verifier key
  resolution — proportional to the forgery threat model (Nestor#2/#17).
- `before_authority.py`'s self-grant tripwire (deny `keys add`, seal-key env
  assignment, `--verifier` imports, raw SQL seal writes) — this *is* the product
  boundary the whole apparatus protects. Do not weaken.
- `add_pair`'s conflict/countersign/race-retry **behavior** (only its packaging is
  flagged); `cloud_seal`'s "provisional" concept (opt-in, clearly labelled).
- The MCP surface (`serve.py`) is the best-designed piece in scope: greppable
  `WITHHELD` list, "cannot seal" explained at three points, refusals that read as
  refusals. Its only nits are the custom-matcher enum (E) and shared with D.

---

## Recommended sequence (leverage = impact ÷ effort, safe first)

**Batch 1 — pure wins, no policy/behaviour tradeoff (all S):**
CLI global-flag error hint (D); Storage docstring six→nine (E); `Curator.list`→
`browse` (E); engine `inspect.signature` probe (D); `ensure_home_layout` env
mutation (D); tolerance-ignored warning (D); single-choice verb defaults (D);
`--json` ignored note (D); `NestorError` base class (E).

**Batch 2 — dedup, no behaviour change (S–M):**
Governance rule to one home + pointers (B); README three-state dedup (B); merge
home-paths/roots docs (A); move journal essays + demo-store artifacts out of
docs/ (F); TODO.md → index (B).

**Batch 3 — opinionated, YOUR call (touch policy or behaviour):**
Narrow the review-desk `GATED_DIRS` + surface it at SessionStart + require the
bearing to name the target (C); gate `reinject` on turn-count/intent (C); collapse
doubled hook subprocesses (C); put the Willow/Hanuman UI behind an explicit opt-in
with no default path probing (A); capability `require_capability` consolidation (E);
`add_pair`/`import_bundle` decomposition (E).

Batch 3 items change either governance policy (yours to set) or the fleet
integration (may be deliberate for your deployment) — so they need your steer, not
a unilateral edit.
