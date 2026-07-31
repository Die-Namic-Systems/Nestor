# What is left

The short list, in the order I would do it. Longer arguments live in
[`IDEAS.md`](IDEAS.md) (each entry tagged **measured / verified / hypothesis /
open / shipped**) and [`QUESTIONS.md`](QUESTIONS.md) (what this gets asked, and
the honest "not yet"s). This file is only the queue — if an item here disagrees
with one of those, they are right and this is stale.

---

## 1. The one that changes what can be claimed

**Per-verifier identity and signing keys.** `verifier="rita"` is a string anyone
who can reach the process can type. Everything else about trust here is
rigorous — the seal is bound to a key the store does not hold, the chain refuses
to launder a tamper, a model structurally cannot seal — and then the *name* on a
verification is unauthenticated. Until this exists, "a human checked this" means
"someone with access typed a name."

The seam is already shaped for it: `signing.sign_seal(..., key=)` takes an
injected key. What is missing is a key-per-verifier resolver and a session on the
UI, plus a decision about what happens to seals signed by a key that is later
revoked. See `QUESTIONS.md` §6 and §15.

This is the gap between Nestor and something a regulated buyer deploys.

## 2. The held-back branch

`claude/good-evening-qvgc23` still carries `c1b3baf` — a bench dashboard and a
review playground — after its three bench commits were landed separately.

Before it can merge:

* **`bench/playground_engine.py` sends what you type to
  `https://api.mymemory.translated.net` by default** (`NESTOR_UI_WEB_DRAFT`
  defaults to `"1"`). In a review playground the text being typed is the material
  under verification, and `README.md` and `QUESTIONS.md` §16 both promise nothing
  calls out unless you ask it to. Default it off.
* It conflicts with `nestor/sqlite_store.py`, which now sets
  `check_same_thread=False` for `:memory:` as part of a larger threading fix
  (a lock, and a uniqueness index). Resolution is "keep master's".
* Decide whether its playground and `nestor.ui`'s queue are one surface or two.
  The **dashboard** — which renders `bench/results/*.json` — has no equivalent in
  the package and is worth having either way.

## 3. Cheap, recorded, unclaimed

* **Report the figure that was actually compared.** `NumericMatcher.parse`
  *searches* for a number, so `"1,00o,000"` parses as `100` and `"12/31/2024"` as
  `12`. That is its documented contract and the failure direction is safe (a typo
  gets flagged and a human looks), but "the number I compared was not the number
  you typed" is a bad sentence in an audit. Returning the parsed figure in
  `check()`'s result is non-breaking and makes it visible. `IDEAS.md` §1.9.
* **A head checkpoint on append.** The chain is verified once per process, so
  tampering mid-shift is caught by the next `verify()` rather than the next
  append. Re-checking just the tip on every append is cheap. §5.3, §5.5.
* **Pagination in the Memory view** past the first 50 rows, and a view over
  `Curator.replaced_seals` — the highest-signal thing the curator surface
  reports, and the one the ledger holds alone. §5.4.
* **The lossless difflib prefilter.** Measured, never shipped; the one
  performance change that pays. §2.1.
* **A terminal `nestor seal`** is deliberately absent — `--verifier "$USER"` in a
  cron job is not a human checking anything. Listed here so nobody adds it by
  accident. §5.1.

## 4. Bigger, and not yet argued through

* **Sync between instances.** Export → import is a transfer: no continuous
  replication, no three-way merge, and pair ids are per-instance. A pull-based
  sync is `import` in a loop plus a conflict queue in the UI. `QUESTIONS.md` §8.
* **An erasure path.** There is no `memory_delete`, deliberately — deletion
  punches a hole in a hash chain by construction. It has to be *designed against*
  the ledger (tombstones plus documented re-anchoring, or key destruction for
  encrypted fields). Until then: do not put personal data in the source text.
  `QUESTIONS.md` §10.
* **Semantic matching.** Would fix the acronym/synonym miss class outright, and
  costs the first runtime dependency in a zero-dependency package. §3.3 — and
  read §3.4 first, which measured the alternative across four stages and found
  the matcher, not the corpus, was the binding constraint.
* **The threshold should be calibrated per corpus, not constant.** Measured, with
  the numbers; nothing consumes them yet. §1.3.
* **Nothing reads the rejections.** Repeated rejections against one query are
  evidence the threshold is wrong for that domain; a pair rejected against many
  queries is probably junk. Both are recorded and unread. §1.2.

## 5. The artifact that would sell it

**A recorded sixty seconds** (§4.3). An answer is wrong; a human corrects it
once; it is right forever after with a receipt that cannot be forged; then tamper
with the ledger and watch the chain refuse. Every screen this needs now exists —
the Ask view returns `~ draft` for a near miss at 0.875 and `! pending` for a
forged row scoring 1.000, and `nestor ledger verify` exits non-zero on a broken
chain. Nobody has recorded it.

---

## A note on how this repo finds things

Four of the six defects fixed on 2026-07-31 were the same shape: **a guarantee
enforced by convention at call sites, and a second path into the store that never
passes it.** Rejection lived in `add_pair` and the import path walked around it.
The seal audit lived in the callers and `add_pair` did not have it. One row per
source was assumed by four modules and enforced by none.

If you add a write path, the question to ask is not "did I remember the guard" —
it is "can this guard be reached around", and then move the rule into the one
place that cannot be bypassed. `IDEAS.md` §1.6, §1.7 and §1.8 are the three
worked examples.
