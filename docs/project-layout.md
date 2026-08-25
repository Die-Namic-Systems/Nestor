# Project layout

*The full annotated manifest — every module, bench, demo, recipe and doc, with a
line on what each is for. The [README](../README.md#project-layout) carries a
short top-level tree and points here for the rest.*

```
nestor/
├── __init__.py       public surface — the cascade, the recipes, the curator, the matchers
├── __main__.py       `python -m nestor` entry point — delegates to cli.main
├── cascade.py        the three tiers, and the hash-chained ledger append
├── memory.py         tier 1 — the sealed pair memory, ranking, seal/reject/serve rules
├── matcher.py        the domain seam — Matcher protocol, StringMatcher, NumericMatcher
├── semantic_matcher.py  optional SemanticMatcher (fastembed extra or Ollama backend)
├── ollama_embed.py   stdlib client for local Ollama embeddings (nomic-embed-text)
├── curator.py        the curator surface — browse, audit, unseal, export
├── calibrate.py      where the seal threshold should sit for *your* corpus
├── answer.py         what Nestor answers — one definition, shared by every surface
├── persona.py        how Nestor speaks when Nestor is the speaker (never the translation)
├── ui.py             the browser surface — queue, memory, ask, signals, ledger (stdlib only)
├── ui_page.py        the single self-contained page ui.py serves
├── seed.py           a small demo store across all three recipes, so a cold `ui --demo` lands live
├── onboarding.py     `nestor init` — ask, watch the matcher refuse, propose a first draft; never seals
├── cli.py            the terminal surface — ask, export, import, ledger verify
├── serve.py          the model surface — MCP over stdio; it cannot seal
├── cloud_seal.py     optional cloud-path seam — an agent provisionally seals through willow-gate (nestor[gate]); never canonical
├── portable.py       export/import a memory without laundering trust
├── entity.py         recipe — alias → canonical entity resolution
├── reconcile.py      recipe — figure → sealed baseline, with tolerance and variation
├── decision.py       recipe — decisions and the signed edges between them (docs/decision-memory.md N6/N8)
├── evidence.py       what a sealed claim rests on — the evidence relation and the unevidenced-seals report (docs/evidence-edge.md)
├── warrant.py       why a stranger should believe a claim — citation and construction warrants, composed with the seal (docs/warrants.md)
├── engine.py         tier 2 — draft engines (ClaudeEngine, OfflineEngine)
├── embedding_store.py  optional tm_embeddings blob helpers (SqliteStore + semantic)
├── storage.py        the persistence seam — Storage protocol, set_store/get_store
├── sqlite_store.py   reference Storage impl; owns documents/segments/tm_pairs/tm_rejections/tm_embeddings/decision_edges/decision_evidence
├── errors.py         NestorError — the shared base every policy refusal subclasses
├── ledger.py         verify() the hash chain — the fail-closed audit check
├── signing.py        bind a seal (and a rejection) to a key the store does not hold
├── staleness.py      age_seals() and the kind constants — one definition for the API and the CLI listing
├── keyring.py        a key per verifier — so a seal names a person, not a deployment
├── frank.py          mirror the ledger into willow-mcp's shared governance ledger
├── home_paths.py     ~/.nestor/keep paths for household hosts (see docs/home-paths.md)
├── home_init.py      idempotent scaffolder for the Nestor home — creates the keep tree if absent, never clobbers
├── preferences.py    per-user, cross-session preference store (~/.nestor/preferences.json) — not config, not a decision
├── config.py         one layered config resolver (env > file > default); a broken file raises rather than degrading to defaults
├── glossary.py       per-language-pair term locks — tier 2's constraint
├── langid.py         stopword-profile language identification
├── segment.py        sentence/segment splitting
├── triage/           decision triage — cluster, supersede, and report over the seal queue before a human seals it
└── vendor/           vendored third-party assets (Cytoscape.js for the decision-graph view)

bench/                measuring where the seal threshold stops holding — see bench/README.md
├── bench_accuracy.py   false-seal rate vs recall, swept across thresholds
├── bench_margin.py     does the gap to the runner-up separate a true match? (mostly: no)
├── bench_surfaces.py   which surface variations survive normalization
├── bench_surfaces_human.py   the same probes, authored by a human rather than generated
├── bench_surfaces_llm.py     and by a model, scored against both
├── corpora.py          seeded corpora at both ends of the diversity spectrum
├── corpus_terpsi.py    a real-prose corpus, with its span/split checks
├── token_matchers.py   token-weighted matchers tried against the identifier collisions
├── retrieval_quality.py  recall/precision at a threshold — the half `nestor calibrate` does not measure
├── harness.py          timing, environment capture, JSON result recording
├── serve_ui.py         the threshold trade-off as a chart — read-only, stdlib (serves bench/ui/)
├── bench_decision_n1.py  N1 — does the matcher recognize a re-worded decision? (docs/decision-rewording-bench.md)
├── matcher_precision.py  precision and recall for the decision matcher — the rate the gate turns on
└── results/            committed measurements — parameters, git rev, raw numbers

demo/                 scripted and self-asserting — a claim that fails the build when it stops being true
├── sixty_seconds.py    the whole loop in eight beats — see Quick start
├── record_demo.py      captures sixty_seconds.py as an asciicast — see 60-second demo below
├── recordings/          the captured .cast and .txt from the last record_demo.py run
├── the_dogfooding.py   Nestor's own decision store asked its own questions — retrieval measured three ways (IDEAS §6.94)
├── shoebox.py          one verifier, her own archive, across all three recipes — five open gaps (IDEAS §6.35, §6.37-§6.39)
├── two_desks.py        a client's intake and the review of Nestor itself, both on custom matchers — what the human surface does to a domain that brought its own (IDEAS §6.40, §6.41)
├── desks.py            scaffolding: several deployments in one interpreter, and the three process globals that makes you own
├── big_jim.py          a standing desk for a used-car lot, keyed on VIN — driven a command at a time
├── review_desk.py      the other desk: patch_review over this repo's own open findings, seeded from IDEAS.md
├── filing_cabinet.py   one man's papers against his own lot's disclosures — three open gaps (§6.22, §6.39, and the verifier policy that does not exist)
├── the_border.py       a verification crossing jeles ⇄ nestor in both directions, and losing something each way — needs jeles importable
├── the_verification.py four real claims past jeles' two-source bar and into this store — all four land as drafts — needs jeles importable
├── llm-only-jokes.md   three jokes only an LLM would get — a session's first ask, kept as a store's first draft
├── llm-only-joke/      a fresh store stood up with one piece (the jokes); bundle + regenerable .db
├── ideas-store/        IDEAS.md loaded as 143 draft rows, and four stand-in retrieval measurements over it
├── the_dispatches_audit.py  Nestor's loop proved on someone else's corpus
└── dispatches_audit_corpus.json  the corpus the dispatches audit runs against

recipes/              the seam's "yours" row, built against the shipped package
├── patch_review.py       defect description → proposed fix; DefectMatcher weights identifiers
├── bench_patch_review.py what it retrieves, against StringMatcher and TokenJaccard
├── jeles_bridge.py       a jeles nugget → the same answer under a signature; every one crosses as a draft, because `verified_by` is an unsigned claim
└── process_lens.py       a measured process observation → the rubric grade it earns
scripts/              dogfood, fleet-checkout, and two_instances.py — the export/import
                      trust boundary across two genuinely separate deployments
tests/                no outbound network (one test binds a loopback socket), no fixtures on disk
AGENTS.md             cold-start for any agent — git sync, ci-lint, hook pointers
CHANGELOG.md          releases, newest first — "Unreleased" until the first tag (docs/releasing.md)
CONTRIBUTING.md       the single path from clone to merged PR — setup, gates, conventions, the one rule
docs/agent-guide.md   participant-neutral operating rules (seals, tests, dogfood)
IDEAS.md              running list of ideas, each tagged measured/verified/hypothesis/open; opens with a CI-gated Map of every subsection
docs/agent-log.md     §6, the implementation-session log, lifted out of IDEAS.md; numbers preserved
TODO.md               the queue — what is left, in order; IDEAS/QUESTIONS hold the arguments
QUESTIONS.md          the questions this gets asked, answered or admitted
docs/findings/        dated audits, kept as records of what was found and how it was argued
docs/dogfood/         Nestor's own decisions, one file per merged PR; the .db is derived (docs/decision-memory.md)
docs/code-review-lessons.md  pre-merge checklist from PR review rounds (§2.4, §5.3, WAL, TTL)
docs/decision-memory.md  decisions as a Nestor recipe — the design carried in from SAFE
docs/releasing.md     the release runbook — the decisions before a first release, and the publish workflow
docs/install.md        the install story, verified — pipx/pip, from PyPI or a checkout, wired to the first run (§7.5)
docs/seal-staleness-and-quorum.md  design memo (§1.4): does a seal expire, and is one enough — an argument, unimplemented
docs/evidence-edge.md  what a sealed claim rests on, distinct from who sealed it — memo + landed core relation/report/CLI (decision 0142/0143)
docs/warrants.md  the three warrants a claim can hold — attestation, citation, construction — and why only the first is Nestor's; memo, unimplemented (IDEAS §1.10, decision 0164)
docs/carried-strings.md  design memo (§6.22): a name is not a word — unimplemented, no reporter yet
docs/detection-kit-as-gates.md  design memo (§6.12): Sagan's baloney-detection kit as exit codes, not advice
docs/corpus-order.md  the order the corpus-from-a-corpus exercise took the repos (§6.50–§6.55)
docs/fleet-integration-map.md  open IDEAS ↔ fleet repos (what to wire, not new invention)
docs/local-fleet.md   wiring nestor to the fleet repos on one machine — paths and commands
docs/home-paths.md  ~/.nestor ledger/keep paths vs the repo's ./data/ (household hosts)
docs/roots-willow-and-homestead.md  ~/.willow fleet root vs ~/.nestor household root — audience, not brand
docs/covenant-lineage.md  where "you may propose, you may not confirm" came from — willow-1.9, willow-2.0's §0.2, Jeles, here
docs/two-stores.md    jeles' corpus and this store on the same problem — read with citations, not run
docs/embedder-stand-in.md  a language model in place of the embedder (§6.99) — an instrument, never a cache key or a seal
docs/decision-rewording-bench.md  N1 — does the matcher recognize a re-worded decision? (the gate under `nestor decision check`)
docs/the-name.md      where "Nestor" comes from — the nest, the Homeric counsellor, and Asimov's NS-2 line
docs/accuracy.md      why the measured false-verification rate is published rather than an adjective
docs/matcher-seam.md  the domain seam in depth — the signed embedding cache, and why a domain is its tags *and* its matcher
docs/frank.md         mirroring the ledger into willow-mcp's shared governance ledger, plus the fleet/home env vars
docs/storage-protocol.md  the persistence seam in full — core operations and the optional capabilities
docs/project-layout.md  this file — the full annotated manifest the README's short tree points at
docs/drafts/          design drafts not yet landed — MCP resources, schema migrations, templates, preferences
docs/journal/         not reference docs — kept writing the reference tree should not mix in
├── felt-cost.md        one operator sentence about friction, read closely — what it implies, and what it cannot
└── live-forever-verse.md  a verse the operator asked to be written down and attributed — not a design memo
```
