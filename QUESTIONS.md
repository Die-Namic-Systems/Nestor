# The questions this gets asked

Kept in the repo because they keep coming, and because a question answered in a
conversation is answered once. Each one says **where the answer lives** — a
module, a command, a measured number — or admits there isn't one yet. An honest
"no" is worth more here than a hedge: this is a package about the difference
between *verified* and *plausible*.

Statuses match [`IDEAS.md`](IDEAS.md): **shipped** (it's in the code, with
tests), **partly** (some of it), **not yet** (with what it would take), **never**
(with why).

---

### 1. Is there an export? — **shipped**

Three, for three different questions.

```bash
nestor export --out memory.json          # a portable, re-importable bundle
nestor export --format csv               # the spreadsheet a reviewer asks for
```

`nestor.portable.export_bundle` carries pairs, rejections, **signatures** and a
canonical `digest`, plus the source chain for reading. `Curator.export()` is the
human-facing dump (provenance and rejections per pair). The CSV is deliberately
lossy — it drops `seal_sig`, so a CSV round-trip cannot carry a verifiable seal,
and the docstring says so where you'd reach for it.

### 2. Can I get it back in — into a *different* instance? — **shipped**

```bash
nestor import memory.json                # reports; writes nothing
nestor import memory.json --apply --verifier rita
```

The interesting half. A bundle is a file, and a file claiming `"status":
"sealed"` is making exactly the claim a signature exists to distrust — the same
claim a forged database row makes. So import applies the serve path's rule
rather than a softer one:

| Incoming row | What happens |
|---|---|
| sealed, signature verifies **here** | imported sealed — this is what sharing a `NESTOR_SEAL_KEY` buys you |
| sealed, signature does not verify | imported as a **draft**, into the review queue, counted and warned |
| draft | imported as a draft |
| same source, different target | **conflict** — listed, never resolved silently (`--override-conflicts` is the deliberate way) |
| a pair **rejected here** | listed and skipped; `--override-conflicts` cannot reach it, because a rejection is not a competing answer |
| sealed and verified, over a local draft | the draft is upgraded — the bundle carries a verification this instance lacks |

Dry run by default, in the library and the CLI both.

### 3. Can a model use it? — **shipped**

```bash
nestor serve --db data/nestor.db         # MCP over stdio, stdlib only
```

`nestor_ask`, `nestor_resolve`, `nestor_check`, `nestor_match`,
`nestor_provenance`, `nestor_ledger_verify`, `nestor_propose` — and
`--read-only` withholds even the proposal, for an agent that should read and
write nothing. Every answer carries the **state**, not just a string: `verified`, the verifier's name, the
confidence, the candidates and what they scored. An agent holding that can cite
a human, quote a pair id an auditor can look up, or decline.

### 4. Can the model seal? — **never**

There is no sealing tool, no flag that adds one, and no argument to any existing
tool that produces one. A name that sounds like one gets a refusal explaining
why. A model's only write is `nestor_propose`, which puts a candidate in the
review queue as a `draft` — where a tier-2 engine's output already lands.

This is the product, not a precaution. "Has a human checked this?" is worth
exactly as much as the difficulty of getting a machine's output marked as
checked. `tests/test_serve.py` pins it as a property: after a model calls every
tool this server has, the sealed memory is unchanged.

### 5. What stops a person forging a seal in the database? — **shipped**

`NESTOR_SEAL_KEY`. Seals are HMAC'd over `(source_norm, target_text, verifier)`
with a key the store does not hold, so a row edited to `status='sealed'` will not
verify and will not be served. `Curator.unverifiable()` and the UI's
"unverifiable" filter list rows that *say* sealed and would not serve.
`NESTOR_REQUIRE_SEAL_KEY=1` fails closed instead of degrading.

### 6. Who is "rita"? Does the UI authenticate anyone? — **not yet**

No. The verifier is **typed, not proven** — the same trust model as calling
`memory.add_pair(verifier="rita")` yourself. Hence loopback by default,
`--allow-remote` to leave it, and `--read-only` to show without granting.

Real multi-user auth means an identity per verifier and a per-verifier signing
key, so a seal proves *who*, not just *that the key was present*. The signing
seam already takes an injected key (`signing.sign_seal(..., key=)`); what's
missing is a key-per-verifier resolver and a session on the UI. That is the
biggest single gap between this and a system a regulated buyer deploys.

### 7. How do I know the ledger wasn't edited? — **shipped, with a caveat now stated**

```bash
nestor ledger verify                       # exit 1 on a broken chain
nestor ledger head                         # the tip — pin it somewhere else
nestor ledger verify --expect-head <sha>   # and check against it
```

Each line's `prev` is the SHA-256 of the previous line, so editing any past entry
breaks the walk — **except the newest one**, which nothing follows and nothing
vouches for. Found while writing a CLI test. `--expect-head` closes it for anyone
who kept the previous tip; `nestor.frank` closes it properly by mirroring every
entry, with its `local_hash`, into a ledger somebody else holds.

### 8. Two instances, two teams. Can they sync? — **partly**

Export → import is one direction and it is honest about conflicts (Q2). The
`digest` makes "are these the same memory?" a one-line comparison. What does not
exist: continuous replication, three-way merge, or a shared identity for a pair
across instances (ids are per-instance uuids; matching is by normalized source).
A pull-based sync would be `import` in a loop plus a conflict queue in the UI.

### 9. What happens when two people seal the same thing differently? — **shipped**

`ConflictingSealError`, with both names and both answers in the message. It fires
on a different verifier asserting a different target; a same-verifier restatement
is treated as a self-correction and proceeds. The UI turns it into a confirm
dialog, the second click is recorded as `seal_override`, and `seal_replaced` in
the ledger keeps what the previous answer was — the store keeps one row per
source, so the ledger is the only place the overwritten decision survives.

### 10. Can I delete something? GDPR? — **never, as currently designed**

There is no `memory_delete`, deliberately. Rejection and unsealing preserve the
trail; hard deletion punches a hole in a hash chain by construction. An erasure
path has to be *designed against* the ledger — tombstones plus a documented
re-anchoring, or key destruction for encrypted fields — not bolted on. Until
someone does that work, the honest answer is: don't put personal data in the
source text.

### 11. How fast is it, and how big can it get? — **measured**

Linear in corpus size, and ~97% of the time is Python-side scoring, not SQL:
293 ms @ 2k pairs, 4.4 s @ 32k, projecting ~135 s @ 1M
([`IDEAS.md`](IDEAS.md) §2). Nestor is built for high-value reviewed decisions,
not high-volume serving. Fixes exist and are measured, not guessed: a lossless
difflib prefilter (§2.1) is the one that pays.

### 12. How accurate is the matching? — **measured, and it is a trade, not a score**

At the default 0.92 threshold: 16.4% false seals on homogeneous boilerplate,
23.6% recall on real rewrites. At 0.96: 0.4% and 2.4%. No threshold is good at
both jobs — that is a limit of character similarity, which is why the dial is
exposed rather than tuned for you. `bench/` measures it against *your* corpus.
Ask any benchmark whether it reports surface variation or meaning-preserving
rewrites; against surface variation alone recall reads 100% and means nothing.

### 13. Does it only do translation? — **no, and the UI says so**

Translation is one instance of: *normalize → fuzzy-match against sealed pairs →
serve above a threshold or queue for a human → ledger it*. Shipped recipes:
translation, entity resolution, numeric reconciliation, and the bare seam over
any domain with either shipped matcher. A date matcher and a CSV-header mapper
have been built against the package without modifying it.

### 14. What if my store is Postgres, or my company's own schema? — **shipped**

Implement `nestor.storage.Storage`. Nestor imports nothing from a host: the core
Protocol is documents, segments and the memory table; rejection, curation and the
review queue are **optional all-or-nothing capabilities** (`supports_rejection`,
`supports_curation`, `supports_queue`) so an older store keeps working and every
surface degrades by *saying so* rather than showing an empty list.

### 15. Can I run it as a service for my whole team? — **not yet**

The UI is a single-operator local tool: no auth (Q6), SQLite by default, and one
process. What it would take, in order: identity + per-verifier keys, a store that
handles concurrent writers (the Protocol already allows it), and a decision about
whether the ledger is per-tenant or shared. None of it is blocked by the design;
none of it is written.

### 16. What does a seal cost? Does anything call an API? — **shipped**

Nothing calls out unless you ask it to. Runtime dependencies: zero. The draft
engine defaults to offline (a TM-composite), the UI's `--engine` defaults to
`offline` so a click never triggers a paid call, and `ClaudeEngine` is imported
lazily and only used with `--engine claude` or credentials plus `auto`. A tier-1
hit is free and local: a SQLite scan and some `difflib`.

### 17. What breaks first, and what happens when it does? — **shipped, mostly**

The failure modes, and the direction each fails in:

| Failure | What Nestor does |
|---|---|
| No store configured | `RuntimeError` — never a hidden default database |
| Ledger unwritable / a symlink / not a regular file | refuses to append; the trail cannot be redirected or suppressed |
| Ledger chain broken | refuses to append (once per process — §5.3), `verify()` reports it, exit 1 from CI |
| `NESTOR_SEAL_KEY` unset | warns once and trusts stored status; `NESTOR_REQUIRE_SEAL_KEY=1` refuses instead |
| Store can't record a rejection | raises rather than dropping a human's "no" |
| Engine down / no credentials | falls back to the offline engine; a segment goes `pending`, not wrong |
| FRANK mirror down | best-effort, local ledger is the source of truth (`NESTOR_FRANK_STRICT` to change that) |
| A model tries to seal | refused, with the reason (Q4) |
| Two reviewers seal the same phrase at once | one wins, the other gets `ConflictingSealError`; the store enforces one row per source |
| The ledger cannot be written or its chain is broken | the decision is refused **before** the store is touched — no sealed row without a trail |
| A FRANK mirror accepts and then stops answering | the forward times out, the subprocess is dropped, the local entry stands |

The one that fails *soft* and shouldn't: inside a long-lived process (the UI, the
MCP server) the chain is verified on first append and trusted thereafter
(§5.3). Tampering that happens mid-shift is caught by the next `verify()`, not by
the next append.

---

**Question 18 is yours.** Open an issue, or add it here with an honest status —
including **not yet**, which is a real answer and the one this file exists to
make sayable.
