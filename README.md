# Nestor

**Meaning infrastructure. *In medio, fides* — in the middle, trust.**

[![Tests](https://github.com/Die-Namic-Systems/Nestor/actions/workflows/tests.yml/badge.svg)](https://github.com/Die-Namic-Systems/Nestor/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Dependencies](https://img.shields.io/badge/runtime%20deps-none-lightgrey)](pyproject.toml)

Nestor answers one question about a machine-generated answer: **has a human
checked this?**

Not as a confidence score — as a structural fact you can audit. Every answer
Nestor serves is in exactly one of three states, and the state is never a guess:

| | State | What it means |
|---|-------|---------------|
| ✓ | **sealed** | A human verified this, and the seal still verifies. Served verbatim, instantly, forever. |
| ~ | **draft** | A machine produced it. Queued for review, never served as verified. |
| ! | **pending** | Nothing to offer. Said plainly rather than improvised. |

Read the first row precisely: *and the seal still verifies*. A row that merely
**says** `sealed` in the database is not served — a seal is bound to a key the
store does not hold, and one that does not verify is surfaced to a curator
instead of answering anyone ([seal signatures](#seal-signatures),
[the curator](#the-curator--seeing-what-was-verified)). A human seals an answer
once and can **reject** one just as durably, so a wrong match is never served
again. Both decisions are signed, both are appended to a hash-chained ledger.

In concrete terms it is a zero-dependency Python library, a `nestor` command
line, and a stdlib browser UI, all over one SQLite-backed store —
[Quick start](#quick-start) has the whole loop, machine draft to human seal to
served answer, in five commands.

**Contents** — [The mechanic](#the-mechanic) ·
[The category](#the-category--verification-not-translation-memory) ·
[Install](#install) · [Quick start](#quick-start) ·
[Project layout](#project-layout) · [The Matcher seam](#the-matcher-seam) ·
[The recipes](#the-recipes) · [Rejection](#rejection--the-reviewers-no) ·
[The curator](#the-curator--seeing-what-was-verified) ·
[The UI](#the-ui--where-the-human-sits) · [The CLI](#the-cli) ·
[Export & import](#export-and-import--taking-the-memory-elsewhere) ·
[Serving a model](#serving-a-model--and-the-one-thing-it-cannot-do) ·
[The ledger](#the-ledger) · [Injected storage](#injected-storage) ·
[Accuracy](#accuracy-and-how-to-measure-yours) · [Development](#development)

Frequently asked, honestly answered — including the "not yet"s:
[**QUESTIONS.md**](QUESTIONS.md). The story behind the name — the nest, Homer,
and Asimov's forged-seal-in-1947 — is [`docs/the-name.md`](docs/the-name.md).

---

## The mechanic

One loop, and it knows nothing about language:

> **normalize an input → fuzzy-match it against a memory of _sealed_ (verified)
> pairs → serve the match above a threshold, else queue it for a human seal →
> append every step to a hash-chained ledger.**

That loop is the product. What it compares — sentences, aliases, figures, dates,
column headers — is decided by a `Matcher`, a two-method seam holding the only
domain-specific code in the system. Everything the value depends on is on the
other side of it: what counts as verified, who verified it, what gets served,
what gets queued, and what the audit trail records.

| Recipe | Matcher | "source → target" means | Module |
|--------|---------|--------------------------|--------|
| Translation | `StringMatcher` | phrase → translation | `nestor.memory` + `nestor.cascade` |
| Entity resolution | `StringMatcher` | alias/surface → canonical entity | `nestor.entity` |
| Numeric reconciliation | `NumericMatcher` | figure → labelled baseline | `nestor.reconcile` |
| *yours* | *yours* | *whatever you can normalize and score* | — |

Translation is where Nestor was extracted from, and the examples below use it
most because it needs no setup to read. It is the origin story, not the
boundary — a date matcher and a CSV-header-to-schema mapper have both been built
against the shipped package without modifying it. Nestor has **no upward
dependency on any host**: persistence, the matcher, the draft engine and the
governance forwarder are all injected.

---

## The category — verification, not translation memory

Translation memory is where Nestor was extracted from. It is not what Nestor is
for, and reading it as a TM gets the economics backwards. A translation memory
is a cache: its value is the work it skips. Nestor's three states are not a cache
tier — they answer a different question, one being put to anyone shipping model
output into a regulated process:

> **Which model outputs did a human actually check?**

**Each verification is permanent capital.** The curve runs the opposite way to
inference: cost per answer *falls* as the proportion of verified answers rises,
and it never un-falls, because a seal does not expire and costs nothing to serve
again. Spending review time buys down a recurring cost rather than renting a
result. Verified once, served forever.

**Where it wins:** high-value, low-volume decisions where somebody is already
reading the output — contract clauses, clinical notes, regulatory filings,
anything with a named reviewer and a retention requirement. The review was
happening anyway; Nestor is the difference between it happening and it being
provable. **Where it loses, stated plainly:** high-volume serving. Lookup is
linear in corpus size and about 97% of that time is Python-side scoring, so this
is not a chat backend — see [Accuracy](#accuracy-and-how-to-measure-yours). The
design target is decisions worth a person's attention, not throughput.

---

## Install

Python 3.10+, no runtime dependencies. The published package is
**`nestor-meaning`** (the shorter `nestor` is unclaimed on PyPI; `import nestor`
is unaffected either way). The blessed one-liner is
[`pipx`](https://pypa.github.io/pipx/), which isolates the `nestor` console
script in its own environment:

```bash
pipx install nestor-meaning          # or: pip install nestor-meaning
```

From a checkout instead of the index, same tool: `pipx install .` (or
`pip install .`). All four paths were run clean into empty environments before
this was written; the transcripts, and the `nestor init` → `nestor demo` →
`nestor ui` first run, are in [docs/install.md](docs/install.md). What this does
*not* solve: no Homebrew tap, no `curl | sh` — `pipx`/`pip` is the whole install
story for now.

Optional extras add capability without moving the core:

```bash
pip install "nestor-meaning[keys]"      # ed25519 per-verifier signing
pip install "nestor-meaning[cloud]"     # the Anthropic draft engine
pip install "nestor-meaning[semantic]"  # embedding matcher (fastembed)
pip install "nestor-meaning[gate]"      # the willow-gate seam
```

---

## Quick start

The core loop fits in one script. Save this as `demo.py` and run it, in the
translation recipe:

```python
from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore

storage.set_store(SqliteStore(":memory:"))

# 1. Nothing is known yet. Nestor says so rather than improvising.
p = cascade.translate_segment("Good evening.", "en", "es")
print(p.mark, p.state, repr(p.target))

# 2. A human verifies it — once.
memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                status="sealed", verifier="rudi")

# 3. Forever after, including when it is retyped differently.
p = cascade.translate_segment("good evening", "en", "es")
print(p.mark, p.state, repr(p.target), p.confidence, p.meta["verifier"])
```

```
! pending ''
✓ sealed 'Buenas noches.' 1.0 rudi
```

One human verification, and the answer is free, instant and attributed from then
on — both steps recorded in a tamper-evident ledger. That ledger is a file even
when the store is not: the run appends to `./data/ledger.jsonl`. (The run also
prints a `RuntimeWarning` about `NESTOR_SEAL_KEY` — Nestor telling you seals are
trusted on stored status alone; see [Seal signatures](#seal-signatures) before
using it for anything real.)

**The product is three separate surfaces over one store** — a machine drafts, a
**human** seals, a model or a terminal serves — and the seal is a person sitting
down, not a function call. Here is that loop across all three, file-backed:

```bash
# 1. A machine draft enters the review queue (tier 2). Nobody has checked it yet.
python - <<'EOF'
from nestor import cascade, storage
from nestor.sqlite_store import SqliteStore
storage.set_store(SqliteStore("data/nestor.db"))   # the CLI's default store
cascade.translate_text("Good evening.", "es", source_lang="en")   # drafts, queues
EOF

nestor ask "Good evening."                 # 2. ! pending — a draft is not verified
python -m nestor.ui --db data/nestor.db    # 3. a human seals it under their own name
nestor ask "Good evening."                 # 4. ✓ sealed  Buenas noches.  (verified by you)
nestor ledger verify                       # 5. ✓ intact
```

Step 3 is the point, not an inconvenience. There is no `nestor seal` subcommand
and no way to seal from a script, because `--verifier "$USER"` in a cron job is
not a human checking anything. A model can draft (`nestor serve`), the terminal
can serve, but only a person at `nestor.ui` turns a draft into a sealed answer.

**The whole argument in sixty seconds**, against a scratch store it deletes
afterwards — eight beats, each asserting its own claim (the script exits non-zero
rather than narrate something that did not happen, and a test runs it):

```bash
python demo/sixty_seconds.py            # --fast to skip the pauses
python demo/record_demo.py              # capture it as an asciicast under demo/recordings/
```

From source, for development:

```bash
git clone https://github.com/Die-Namic-Systems/Nestor.git && cd Nestor
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                 # + pytest, ruff, bandit
bash scripts/ci-test.sh core            # fast, deterministic, no live services
```

The bundled `SqliteStore` owns every table Nestor needs, so the whole cascade
runs end-to-end with no host application. It uses **WAL** mode, so a plain `cp`
of `nestor.db` is not a backup of a running server — use `nestor export`, SQLite
`VACUUM INTO`, or stop `nestor.ui` (which checkpoints on exit).

---

## Project layout

```
nestor/       the package — cascade, memory, matchers, curator, ui, cli, serve, ledger, signing
bench/        measuring where the seal threshold stops holding (bench/README.md)
demo/         scripted, self-asserting demos — a claim that fails the build when it stops being true
recipes/      the seam's "yours" row, built against the shipped package
tests/        no outbound network (one test binds a loopback socket), no fixtures on disk
docs/         design memos, operating rules, and the moved-out reference material
AGENTS.md · IDEAS.md · TODO.md · QUESTIONS.md · CHANGELOG.md
```

The full annotated manifest — every module, bench, demo and doc with a line on
what each is for — is [`docs/project-layout.md`](docs/project-layout.md).

---

## The Matcher seam

A `Matcher` (`nestor.matcher`) is the domain-specific half of the mechanic —
everything else (sealing, thresholds, the ledger, storage inversion) is shared:

```python
@runtime_checkable
class Matcher(Protocol):
    def normalize(self, value) -> str: ...              # canonical key
    def similarity(self, a_norm, b_norm) -> float: ...  # [0.0, 1.0], 1.0 == verified
    # optional: score(raw_a, raw_b) -> float — memory prefers this when present
```

Two core matchers ship with zero dependencies; a third is optional:

- **`StringMatcher`** — the module-wide default: lowercase, strip punctuation,
  collapse whitespace, then `difflib.SequenceMatcher` ratio. Translation scoring
  is reproduced bit-for-bit.
- **`NumericMatcher(abs_tol=0.0, pct_tol=0.05)`** — parses a number out of a
  str/int/float into a canonical float key; `similarity` is `1.0` inside the
  tolerance band and decays exponentially outside it.
- **`SemanticMatcher`** *(optional)* — `pip install -e ".[semantic]"` adds
  `fastembed`; `score` compares embeddings. Or **`ollama`**, the same seam over
  stdlib HTTP to a local daemon. Re-calibrate thresholds — embedding scores are
  not comparable to character-ratio ones.

The domain tags (`source_lang` / `target_lang`) are treated as generic labels,
so one store holds several disjoint graphs without cross-talk. Two things that
had to be learned the hard way — **the embedding cache is signed for the same
reason a seal is**, and **a domain is its tags *and* its matcher** (hand every
surface the matcher that keys it, or it files under the default's key silently) —
are written up in [`docs/matcher-seam.md`](docs/matcher-seam.md).

---

## The recipes

### Translation — the cascade

For each text segment, Nestor tries three tiers in order:

| Tier | Name | What it is | State |
|------|------|-----------|-------|
| 1 | **Nestor's ledger** | A sealed TM hit (fuzzy match ≥ `SEAL_THRESHOLD`, default `0.92` — [a dial, not a default](#accuracy-and-how-to-measure-yours)) | `sealed` |
| 2 | **The draft** | A glossary-constrained LLM (or offline TM-composite) draft | `draft` |
| 0 | *(no candidate)* | The engine declined / returned nothing | `pending` |

A tier-2 draft is written into the host's review queue. Tier 3 — **the seal** —
happens when a human verifies a segment (`graduate_segment(...)`); the verified
pair enters the sealed memory and serves future tier-1 hits. A reviewer's **no**
is recorded too (`reject_segment(...)`), so a wrong candidate is never offered
for that input again — see [Rejection](#rejection--the-reviewers-no).

```python
from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore

store = SqliteStore(":memory:")
storage.set_store(store)
memory.add_pair("Please sign the form.", "Firme el formulario.", "en", "es",
                status="sealed", verifier="rita")

# Tier 2: nothing sealed is close enough, so the engine drafts and queues.
doc, passages = cascade.translate_text("Please sign the attached form.",
                                       target_lang="es", source_lang="en")
passages[0].state                     # 'draft' — queued, not served as verified

# Tier 3: a human works the queue. Accept or refuse; either way it sticks.
for seg in store.list_segments(doc["id"]):
    cascade.graduate_segment(seg["id"], verifier="rita")
    # or: cascade.reject_segment(seg["id"], verifier="rita", reason="…")

# From now on, the same request is a tier-1 hit with rita's name on it.
memory.best_sealed("Please sign the attached form.", "en", "es")
# {'pair': {...'verifier': 'rita'...}, 'similarity': 1.0}
```

**Changing an answer keeps the answer it replaces.** `supersede_pair(...)`
retires a live sealed pair behind its successor — verifier required, because
replacing a sealed decision is itself a decision — and `revise_draft(...)` does
the same for a machine's own draft, taking no verifier. Both keep the old row
with the reason it was replaced; `memory_lineage` walks the chain back. Both need
the lineage capability and raise without it rather than overwriting.

### Entity resolution — `nestor.entity`

```python
from nestor.entity import EntityResolver

r = EntityResolver(store, domain="company")
for surface in ["Amazon", "Amazon.com Inc", "AMZN", "AWS"]:
    r.seal(surface, "Amazon", verifier="analyst", origin="sec-filing")

r.resolve("amazon.com  inc.")
# {'canonical': 'Amazon', 'confidence': 1.0, 'sealed': True, 'provenance': {...}}
r.resolve("Alphabet Inc")
# {'canonical': None, 'confidence': 0.0, 'sealed': False, 'provenance': {'draft': True, ...}}
```

A match at/above the seal threshold returns the canonical entity with the sealed
mapping's provenance; below it, the top candidate comes back as an **unsealed
suggestion** the caller can queue for a human seal — not an answer with a lower
score, because "probably Amazon" is not a thing a human checked.

### Numeric reconciliation — `nestor.reconcile`

```python
from nestor.reconcile import Reconciler

rc = Reconciler(store, domain="contract", pct_tol=0.05)
rc.seal_baseline("ceiling", "$1,000,000", verifier="auditor")

rc.check("ceiling", "$1,030,000")
# {..., 'within_tolerance': True,  'variation': 30000.0,  'variation_pct': 0.03, 'flagged': False}
rc.check("ceiling", 1_250_000)
# {..., 'within_tolerance': False, 'variation': 250000.0, 'variation_pct': 0.25, 'flagged': True}
```

`check` compares an observation to the sealed baseline via the tolerance band,
reports absolute and proportional variation, and flags deviations. **A label has
exactly one baseline** — a differing figure from a different verifier raises
`ConflictingSealError` rather than sitting as a second sealed row that a later
check could score against (a `$4,900,000` spend once passed cleanly against a
superseded `$5,000,000` ceiling while the standing `$1,000,000` one went
unconsulted). A same-verifier restatement retires the superseded baseline and
ledgers the replacement.

All three recipes are driven from [the UI](#the-ui--where-the-human-sits) — same
memory, same threshold, same ledger, four buttons.

---

## Rejection — the reviewer's "no"

Sealing records that an answer is right. Rejection records that one is **wrong**,
so it is never served again. Both are verification decisions by a human, both are
signed, both land in the ledger — otherwise the audit trail only ever records
agreement. There are two different refusals, and the distinction matters:

```python
# 1. The mapping itself is wrong — retire it everywhere.
memory.reject_pair(pair_id, verifier="rita", reason="wrong time of day")

# 2. This pair is the wrong answer FOR THIS QUERY — it stays valid for its own
#    source text. This is what a false seal actually is.
hit = memory.best_sealed("the penalty under section 900026", "en", "es")
memory.reject_match("the penalty under section 900026", "en", "es",
                    pair_id=hit["pair"]["id"], verifier="rita",
                    reason="different section")
```

A false seal is a *correct* pair matched to the wrong input, so rejecting the
pair would destroy a good verification. Rejecting the **match** suppresses it for
that one query and leaves the seal intact. Enforcement lives in `memory.lookup()`,
which every serve path goes through, so a rejected pair is hidden from tier-1
serving *and* from the engine's reference context.

> **For hosts:** rejection is an **optional** Storage capability
> (`storage.supports_rejection`). A store predating it keeps working; implement
> all three operations or none. A rejection is honored **even if its signature
> does not verify** — the reverse of how seals are treated, because suppressing
> an answer degrades to human review, which is the safe state.

---

## The curator — seeing what was verified

Sealing without a way to review it is write-only trust. `nestor.curator.Curator`
is the surface for whoever owns the memory: browse it, inspect provenance, spot
seals that do not verify, and revoke.

```python
from nestor.curator import Curator

c = Curator(store, source_lang="en", target_lang="es")
c.browse(status="sealed", contains="invoice")  # browse, filter, paginate
c.get(pair_id)                                # provenance + every rejection against it
c.unverifiable()                              # says "sealed", would NOT be served
c.unseal(pair_id, verifier="rita", reason="terminology changed")
c.export()                                    # the whole memory, JSON-ready
```

Every row carries **`servable`** alongside `status`, because they are not the
same question. `servable` runs the identical check the serve path uses, so a row
marked `sealed` whose signature does not verify shows up as `servable=False` —
written by something that never held the seal key, and exactly what
`unverifiable()` finds.

**Unsealing is not rejecting.** Unsealing returns a pair to `draft` for
re-verification; [rejecting](#rejection--the-reviewers-no) retires it as wrong. A
curator who is merely unsure shouldn't have to choose between destroying a
mapping and leaving a seal standing they no longer trust. Both are written to the
ledger. Re-sealing a rejected pair raises `RejectedPairError`; `Curator.restore`
is the deliberate way back, returning the pair to `draft` so it gets
re-verified. (Curation is an optional Storage capability,
`storage.supports_curation`.)

---

## The UI — where the human sits

Everything above is a library surface. Nestor's whole claim is that *a human
checked this*, and until `nestor.ui` that human had to write Python to do it.

```bash
python -m nestor.ui --db data/nestor.db          # http://127.0.0.1:8765
nestor-ui --db data/nestor.db --open             # same, via the console script
```

Stdlib only — `http.server` and one inlined page — so the runtime dependency
count stays zero. Seven views, each one a surface the package already had and
nobody could see:

| View | What it is |
|------|-----------|
| **Queue** | The segments the cascade left for review. Seal, correct-then-seal, or reject each one; it leaves the queue and the decision is signed and ledgered. |
| **Memory** | The curator's view over any domain: filter, inspect provenance and rejections, unseal, reject, restore, seal one by hand, export and import. Every row shows `servable` beside `status`. |
| **Ask** | The mechanic, in whichever recipe you pick — translate, resolve, reconcile, or the bare seam. Each answer comes with the ranked candidates and what they scored. |
| **Signals** | Three things the package records that no single row shows: overwritten seals, queries the reviewers keep refusing, and pairs refused against many unrelated queries. |
| **Graph** | The decision graph drawn — nodes are decisions, edges are the typed relations between them (`requires`, `supersedes`, `supports`, `conflicts`). Read-only. |
| **Triage** | Group the decision queue and find supersessions — clusters of similar questions and edges proposed by similarity. |
| **Ledger** | `verify()`'s verdict and the chain itself, so the audit trail can be read where the decisions are made. |

The Ask view is the one to open first, because it shows the product rather than
describing it. Asking for a phrase whose only match is a row that *claims* to be
sealed but was written without the seal key:

```
! pending   tier 0
—
Nothing to offer. Said plainly rather than improvised.

✓  1.000   wire the funds to the new account → transfiera los fondos a la cuenta nueva
           sealed · NOT SERVABLE · by mallory
```

A perfect match, and the answer is still *pending*. That is the whole product in
one screen.

**What the UI does not do is authenticate anybody.** The verifier is typed, not
proven — the same trust model as calling `memory.add_pair(verifier="rita")`
yourself. So it binds to loopback and refuses a public bind unless you pass
`--allow-remote`, mutating requests must carry the page's own header (so another
tab cannot POST a seal), and the page is served with a strict
Content-Security-Policy (`default-src 'none'`) — an audit surface should not be
able to ship the memory it displays anywhere.

There *is* one way to make the verifier proven: the "acting as" box's third mode
generates a **non-extractable Ed25519 key with WebCrypto in the browser** (or
imports one as raw hex). The private key lives in IndexedDB and **never leaves
the page**; enrolment is out of band (the page prints the exact
`nestor keys add 'NAME' --type ed25519 --public HEX` to run), and a seal is
signed client-side against a message the human actually saw. Initialize the
public-only trust root first with `nestor keys init --keyring PATH`; that command
creates an empty keyring once and never overwrites an existing one. This is the property a
shared `NESTOR_SEAL_KEY` can never have — the store verifies and seals under a
verifier's key while being structurally unable to forge as them. It is
deliberately narrow (only the seal endpoints accept a client signature); see
[Seal signatures](#seal-signatures) and
[decision 0077](docs/archive/decisions/0077-verify-not-sign-the-client-seal.json).

`--read-only` refuses every decision at the API layer, for showing the memory to
someone without handing them the ability to change it. `--engine` defaults to
`offline`, because a click in a browser should not silently call a paid API.

---

## The CLI

The CLI is its own process, so it does not see a store your Python snippet set
in memory — it reads `--db` (default `./data/nestor.db`) and `--ledger`. Both are
global flags and work in either position: `nestor --db mydb.db ask "…"` and
`nestor ask "…" --db mydb.db` are equivalent.

```bash
nestor ask "Good evening."               # ✓ sealed  Buenas noches.  (verified by rita)
nestor resolve AMZN --domain company     # the entity graph
nestor check ceiling '$1,030,000' --domain contract
nestor evidence for PAIR_ID              # what a sealed claim rests on (also: attach, report)
nestor warrant for PAIR_ID               # why a stranger should believe it (also: attach)
nestor export --out memory.json          # a portable bundle
nestor import memory.json                # dry run; --apply commits
nestor ledger verify                     # exit 1 on a broken chain
nestor init                              # the guided first run; --yes for CI
nestor calibrate --from en --to es       # where the threshold belongs for this corpus
nestor rejections                        # what the recorded "no"s say in aggregate
nestor keys add rita --keyring keys.json # a key per verifier; keys list / revoke
nestor ui                                # the browser surface
nestor serve                             # MCP over stdio, for a model
```

**Exit codes mean something.** `0` is the good answer, `1` is the bad one — an
unverified answer, a flagged figure, a broken chain, an import with conflicts —
and `2` is a usage error. So `nestor ledger verify` is a CI gate and `nestor ask`
belongs in a shell conditional:

```bash
nestor ask "$phrase" >/dev/null || echo "nothing verified for that — ask a human"
```

## Export and import — taking the memory elsewhere

```bash
nestor export --out memory.json          # pairs, rejections, signatures, digest
nestor import memory.json                # reports what would happen
nestor import memory.json --apply --verifier rita
```

Export is easy. Import is the half worth explaining, because **a bundle is a
file, and a file claiming `"status": "sealed"` is making exactly the claim a seal
signature exists to distrust.** So import applies the serve path's rule rather
than a softer one:

| Incoming row | What happens |
|---|---|
| sealed, and its signature verifies **here** | imported sealed — what sharing a `NESTOR_SEAL_KEY`, or holding the signer's ed25519 **public** key, buys you |
| sealed, signature does not verify | imported as a **draft**, into the review queue — counted, warned about, never served |
| sealed, and **this instance has no key configured** | imported sealed on stored status alone — the serve path would trust the same row for the same reason. `NESTOR_REQUIRE_SEAL_KEY=1` refuses it |
| same source, a *different* target | **conflict**: listed for a human, never resolved silently (`--override-conflicts`) |
| a pair **rejected here** | listed and skipped — a rejection is not a competing answer (`--override-rejections`, or `Curator.restore`, is the way back) |

Dry run by default, in the library and the CLI both, because an import decides
what an instance will serve as human-verified. **The ledger does not merge** — a
hash chain has one history by construction, so the import itself is what gets
appended locally. This is a transfer, not a sync: no continuous replication, no
three-way merge, and a pair's id is per-instance. Bundles carry evidence (what a
claim rests on) from version 3 on. `--format csv` is deliberately lossy — it
drops signatures, so use it to read a memory, not to move one.

## Serving a model — and the one thing it cannot do

```bash
nestor serve --db data/nestor.db         # MCP over stdio, stdlib only
```

That command is the server; it is not self-registering. A model reaches it only
once its client is told the server exists, and where the store and the seal key
live. In Claude Code:

```bash
claude mcp add nestor \
  -e NESTOR_SEAL_KEY="$NESTOR_SEAL_KEY" \
  -- nestor serve --db data/nestor.db
```

`--scope` decides who gets it: `local` (default) is this machine only, `user`
spans your machines, `project` writes `.mcp.json` in the repo — shared with
whoever clones it. Prefer `local` or `user` here. `--db` is a path, so a project
entry is a path that has to be right on someone else's disk, and the seal key
would be a secret in a tracked file.

A client configured by file rather than by command takes the same three facts:

```json
{"mcpServers": {"nestor": {"command": "nestor",
                           "args": ["serve", "--db", "data/nestor.db"],
                           "env": {"NESTOR_SEAL_KEY": "..."}}}}
```

Where that file lives is the client's business, not Nestor's — check its own
docs. What Nestor cares about is the shape: **the key is passed to the server,
never written into the store.**

Leaving `NESTOR_SEAL_KEY` out does not fail loudly. The server starts, answers,
and degrades to trusting `status="sealed"` on the stored row alone — it warns
once and serves. That is the wrong way round for a model-facing surface, because
the one thing this server exists to protect is the difference between a human
sealed this and a row says so. Set the key, or set `NESTOR_REQUIRE_SEAL_KEY=1`
to turn the degrade into a refusal — see [Seal signatures](#seal-signatures).

A model gets `nestor_ask`, `nestor_resolve`, `nestor_check`, `nestor_match`,
`nestor_provenance`, `nestor_ledger_verify`, `nestor_prefs` — and
`nestor_propose`, which queues its answer for a human as a `draft`.
Starting the server explicitly with `--engine ollama` also exposes
`nestor_draft`: a bounded, loopback-only analysis or patch suggestion carrying
model and prompt provenance. When `--corpus-dir` (or `NESTOR_CORPUS_DIR`) names
extracted per-project stores, startup consolidates them into the household DB
and automatically retrieves relevant context:

```bash
nestor corpus sync --source-dir data/corpus
nestor serve --engine ollama --corpus-dir data/corpus
```

Those rows live in `corpus_claims`, never `tm_pairs`. Even a source row claiming
`status="sealed"` is returned under `basis.unverified_corpus_excerpts` with
`authority="none"`; only independently verified household pairs appear under
`basis.sealed_guidance`, marked `context_only` because retrieval does not verify
the current task. Long queries must match at least two meaningful terms, and
each excerpt reports those terms and its query coverage. Drafts cite short
`[C1]` tokens; `grounding.citation_compliant` reports missing or invented tokens
without pretending the model obeyed. When it does not, `pattern_support`
deterministically names candidate sealed/corpus sources for each sentence,
lists unmatched terms and unsupported sentences, and flags negation-polarity
mismatches; those are lexical candidates, not fabricated citations or
entailment. `--corpus-semantic` optionally reranks the bounded FTS
shortlist with local Ollama embeddings and reports `fts+semantic`; lexical FTS
remains the fallback. The draft engine cannot read files, run tools, or queue itself;
`nestor_propose` remains the separate explicit review step. See
[`docs/local-agent-prototype.md`](docs/local-agent-prototype.md) for one signed
household store shared by Cursor, Claude, and Ollama.

**It cannot seal.** Not "sealing is disabled by default" — there is no sealing
tool, no flag that adds one, and no argument to any existing tool that produces
one. A plausible-sounding name gets a refusal that explains why:

```
PermissionError: 'nestor_seal' is not available to a model. This server
deliberately withholds: seal, unseal, reject, override a conflicting seal,
import a bundle, edit the ledger. Verification is a human act — use
nestor_propose to put an answer in front of one.
```

That is the product, not a precaution. `tests/test_serve.py` pins it as a
property: after a model has called every tool this server has, the sealed memory
is unchanged. What comes back is the **state**, not just a string, so an agent
can cite a human or decline — a perfect-scoring row written without the seal key
is still reported `verified=False`. `--read-only` withholds even the proposal.

---

## The ledger

Every passage, seal, rejection, unseal, resolution and check is appended to a
hash-chained ledger (`data/ledger.jsonl` by default). Each line records
`prev = sha256(previous line)`, so the audit trail is tamper-evident — and all
recipes share one chain.

Nestor fails closed on it. Appending refuses if the ledger is a symlink or not a
regular file (the trail must not be redirectable), and the chain is verified
before it is first extended in a process. **A decision that cannot be recorded is
not made** — those refusals run *before* the store is written
(`cascade.ledger_preflight`), so a seal, rejection or unseal onto a broken chain
is refused outright rather than committed and regretted. A draft still lands — a
draft is not a verification. Appends are serialized across threads and processes.

**The walk cannot vouch for the newest entry.** Every line is verified by the
line after it, so the last one — the one that just recorded who sealed what — has
nothing following it. That is a property of hash chains, not a bug. Pin the tip
somewhere the ledger's writer cannot reach:

```bash
head=$(nestor ledger head)                    # store this in CI, a monitor, anywhere else
nestor ledger verify --expect-head "$head"    # exit 1 if the tip moved unexpectedly
```

**Nothing is ever deleted, and that is a design decision with a cost.** Rejecting
and unsealing preserve the trail; there is no `memory_delete`, because hard
deletion punches a hole in a hash chain by construction. Until an erasure path is
designed *against* the ledger: do not put personal data in the source text
([QUESTIONS.md §10](QUESTIONS.md)). Configure the ledger path with
`NESTOR_LEDGER`, and term-lock storage with `NESTOR_GLOSSARY` — set one in any
deployment whose working directory is not where the terms were entered from.

### Seal signatures

Set `NESTOR_SEAL_KEY` and every seal is bound to a key the store does not hold,
so a row edited to `status='sealed'` directly in the database will not verify and
will not be served. Without the variable Nestor warns and trusts stored status —
set `NESTOR_REQUIRE_SEAL_KEY=1` to fail closed instead. The key is an arbitrary
HMAC secret; generate one with entropy:

```bash
export NESTOR_SEAL_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
# keep it out of source control; every seal made under it verifies only where it is set
```

### Who verified it — per-verifier keys

One `NESTOR_SEAL_KEY` proves *the key was present*, not **who**. A keyring
(`nestor.keyring`) gives each verifier their own key, so a valid signature over
`(source_norm, target_text, "rita")` is evidence about rita:

```bash
nestor keys init --keyring keys.json         # empty trust root; safe to repeat
nestor keys add rita --keyring keys.json     # prints the key once; the file is 0600
export NESTOR_KEYRING=keys.json
nestor ui --db data/nestor.db                # "acting as" becomes a sign-in
```

With a keyring in force, a name the keyring does not know **cannot seal**
(`UnknownVerifierError`), the UI stops taking a typed name, and moving a real
signature onto a different name no longer works. A **rejection** by an
unregistered name is still recorded and honored, reported as unsigned — refusing
to record a "no" is the one direction rejection must not fail in.

**Revoking a key asks one question, because the answer genuinely differs.** An
HMAC carries no timestamp, so a signature cannot tell "sealed by rita last March"
from "forged last night by whoever took rita's key":

| | new seals | seals it already made |
|---|---|---|
| rotated (`--reason`) | refused | **keep serving** — nobody else held the key |
| `--compromised` | refused | **stop serving** — indistinguishable from the thief's; surface in `unverifiable()` for re-verification |

The asymmetric upgrade lives behind the `[keys]` extra: an **ed25519** entry
signs with a private key and verifies with the public half, so a keyring holding
only a peer's **public** key can verify their seals while being structurally
unable to sign as them — what makes an imported bundle's seals checkable without
sharing a secret. And `memory.add_pair(..., seal_sig=...)` accepts a signature a
*client* already produced and only verifies it, so a public-only entry — or a
browser doing WebCrypto — can seal here without the private key ever touching
this process.

The ledger can also mirror into shared infrastructure. **FRANK**
(`nestor.frank`) forwards every entry into willow-mcp's append-only governance
ledger — opt-in, best-effort, local-first. It is fleet-specific; the setup, the
seat-ordering footgun, and the cross-linking `local_hash` are in
[`docs/frank.md`](docs/frank.md).

---

## Injected storage

Nestor imports **nothing** from a host application. It defines a
`typing.Protocol` — `nestor.storage.Storage` — capturing exactly the persistence
operations the cascade and memory need. A host (or the bundled reference store)
supplies a concrete implementation.

```python
storage.set_store(SqliteStore("data/nestor.db"))                          # process-wide
doc, passages = translate_text("Hola.", target_lang="en", store=store)    # or per call
```

If neither a global store nor an explicit `store=` is present, Nestor raises a
clear `RuntimeError` — it never silently falls back to a hidden database.

The protocol has a **core** every store must implement (documents, segments, and
the translation-memory operations — `memory_insert` MUST refuse a duplicate
`(source_norm, source_lang, target_lang)`, which is what makes "one row per
source" hold under concurrent sealers) and a set of **optional capabilities**,
each all-or-nothing and reported by a `supports_*` predicate so a surface that
needs one says so rather than showing an empty list. The full
operation-by-operation reference — core signatures and all optional
capabilities — is [`docs/storage-protocol.md`](docs/storage-protocol.md).

**Other injected seams.** The **draft engine**
(`nestor.engine.get_engine("auto"|"claude"|"offline")`) imports the Anthropic SDK
lazily: without credentials or the `anthropic` package, `auto` falls back to the
deterministic offline engine — silently, so an unset `ANTHROPIC_API_KEY` is the
first thing to check if you expected a Claude draft. A **bilingual corpus loader**
(`memory.set_bilingual_loader(fn)`) defaults to returning `[]`.

---

## Accuracy, and how to measure yours

A tier-1 hit is served verbatim and marked verified, with **no review queue**. So
the failure that matters is the inverse of the usual one: not a missed match, but
a phrase that was never verified being served as though it were. Both are
governed by `SEAL_THRESHOLD` (default `0.92`), and **no value of it is good at
both jobs.** Measured, 250 probes per cell:

| threshold | false seals (24k boilerplate) | recall on real rewrites |
|-----------|------------------------------:|------------------------:|
| 0.92 (default) | 16.4% | 23.6% |
| 0.96 | 0.4% | 2.4% |

Raise it and unverified answers stop being served, but so do genuine ones. That
is a limit of character-similarity matching, not a tuning problem, and it is why
the threshold is exposed rather than tuned for you. (Recall here is against
**meaning-preserving rewrites** — synonym swaps, clause reordering. Against
surface variation only — case, punctuation, a typo — it reads 100%, because
normalization erases those before scoring. Ask which one a benchmark reports.)

**So measure it rather than trusting the default.** `bench/` sweeps the threshold
against corpora at both ends of the diversity spectrum:

```bash
python bench/bench_accuracy.py --probes 400    # ~10 min; --resume continues an interrupted run
python bench/serve_ui.py --open                # the trade-off as a chart, stdlib, no build
```

Results land in `bench/results/*.json` with parameters, environment and git
revision attached, so a result can be cited and re-derived rather than quoted.

**And then calibrate against the memory you actually have.** `nestor calibrate`
measures *your* corpus, by asking the only question that needs no probe set — for
each sealed pair, the other sealed pair whose source scores highest and whose
target is **different**, which is exactly a false seal already sitting in your
memory:

```bash
nestor calibrate --from en --to es --target 0.01
```

It reports the rate at every cutoff, recommends the cheapest one that meets your
target, and says so plainly when none does (a corpus problem, not a dial
problem). It changes nothing — moving the threshold is a decision about how much
unverified content you will serve, and it belongs to a person. Two consequences
stated rather than implied: **a small memory recommends low and means nothing by
it** (below ~30 sampled pairs the command flags its own recommendation
`(unstable — too few pairs)`), and **applying the result is deliberately manual**
(pass `seal_threshold=` per call, or rebind `SEAL_THRESHOLD` at process start —
there is no env var, because moving the dial should be findable in code review).

Everything above admits a failure rate, in public, on purpose — the argument for
*why* a measured number beats a better adjective is
[`docs/accuracy.md`](docs/accuracy.md). Known limits are recorded in
[`IDEAS.md`](IDEAS.md): lookup is linear in corpus size (§2.1), and the threshold
wants calibrating per corpus rather than trusting (§1.3).

---

## Development

```bash
pip install -e ".[dev]"
bash scripts/ci-test.sh core       # fast iteration: trust/core tests
bash scripts/ci-test.sh full       # pre-push suite; run in background
ruff check nestor tests            # enforced in CI
bandit -r nestor -ll -q            # enforced in CI
python bench/bench_accuracy.py     # measurements -> bench/results/
```

Optional integrations never activate merely because their dependency or daemon
is present. Run them deliberately with `scripts/ci-test.sh semantic`, `ollama`,
`browser`, or `external`; scale/corpus checks are the `slow` lane. The
`semantic`, `ollama`, and `external` lanes set their opt-in environment flags
themselves. Serial wall-clock assertions live in `performance`, because xdist
or coverage contention makes those numbers meaningless.

**Returning to an existing clone:** the install persists, the activation does
not — run `source .venv/bin/activate` in each new shell. The failure mode is
quiet if you forget: the package imports from the repo root without any install,
so snippets keep working while `nestor` and `pytest` are missing or stale. If
commands are half-working, check `which python` first. (Sessions on Claude Code
on the web skip this — a `SessionStart` hook builds `.venv` and puts it on `PATH`.)

CI runs lint and the test matrix (Python 3.10 and 3.12) on every pull request,
plus a daily scheduled run to catch drift. Ideas, open questions and measured
dead ends live in [`IDEAS.md`](IDEAS.md) — each entry tagged
**measured / verified / hypothesis / open**.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
