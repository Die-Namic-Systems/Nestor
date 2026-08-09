# What is left

The short list, in the order I would do it. Longer arguments live in
[`IDEAS.md`](IDEAS.md) (each entry tagged **measured / verified / hypothesis /
open / shipped**) and [`QUESTIONS.md`](QUESTIONS.md) (what this gets asked, and
the honest "not yet"s). This file is only the queue — if an item here disagrees
with one of those, they are right and this is stale.

---

## 1. The one that changes what can be claimed

**Asymmetric seal signatures — shipped, corrected in place: this entry used to
say Ed25519 was still future work. It landed** (`nestor.keyring`, `[keys]`
extra, decision `0074`). Per-verifier identity shipped first: each verifier
has their own key, a seal's signature verifies under the key of the verifier
it *names*, and the UI is a sign-in rather than a text box. Ed25519 shipped on
top of that: a keyring holding only a peer's **public** key can verify their
seals while being structurally unable to sign as them — the property an HMAC
shared secret can never have — closing the cross-instance/cross-organisation
cell (`QUESTIONS.md` §6, Q2, Q8).

What Ed25519 alone did not close is that the SIGNING instance still holds
every one of its own verifiers' private keys, so its operator can forge as
anyone whose key lives there. **The server-side half of that is now shipped
too** (decision `0077`): `memory.add_pair(..., seal_sig=...)` accepts a
signature a client already produced and only *verifies* it — never signs —
so a public-only ed25519 entry can seal here without the private key ever
touching this process. `signing._message` is now a documented, frozen wire
contract for exactly this reason.

**Closed — corrected in place: this entry used to say the browser page was
the real remaining piece.** It shipped (`nestor/ui_page.py`, decision `0078`):
the "acting as" box's third mode generates a non-extractable Ed25519 key with
WebCrypto directly in the browser (or imports one minted elsewhere, as raw
hex), persists it in IndexedDB or only for the tab, and prints the exact
`nestor keys add NAME --type ed25519 --public HEX` enrolment command for a
human to run out of band — the private key never leaves the browser, and
never touches this server. Sealing signs client-side against a message the
human has seen (a new read-only `/api/normalize` endpoint supplies
`source_norm`, displayed before signing, so a compromised server cannot steer
a signature onto bytes nobody looked at), reproducing the frozen
`signing._message` encoding in JavaScript and proven byte-identical to
Python's against a live Chromium tab
(`tests/test_client_signed_seals_browser.py`). Nestor#17's four-cell table
(README/QUESTIONS §6) is now fully closed: an instance can hold, verify, and
seal against a verifier's key it structurally never possesses.

Deliberately still narrow: only `/api/seal`, `/api/seal-draft` and the edited
path of `/api/queue/seal` accept a client signature, matching decision
`0077`'s scope exactly — a browser-key verifier cannot yet unseal, reject,
restore, or seal an entity/numeric answer from this UI, because those
endpoints have no signature to authenticate against.

## 2. Bigger, and still not argued through

* **Sync between instances.** Export → import is a transfer: no continuous
  replication, no three-way merge, and pair ids are per-instance. A pull-based
  sync is `import` in a loop plus a conflict queue in the UI. `QUESTIONS.md` §8.
* **Three deferred audit findings — §6.92.** All three now **shipped**: a
  bundle records the matcher that keyed it and `/api/import` warns on a mismatch
  instead of landing rows in a key space it never computes (decision 0073),
  `add_pair`'s race retry forwards `reason=`, and `_domain_matcher`/
  `domain_matcher` now refuse a case-only near-miss (`Incident` against a
  surface keyed `incident`) instead of silently falling back to the
  process-wide matcher — the tags are not folded, so a store holding two
  domains that differ only in case is untouched, and a genuinely different
  domain still defers exactly as before (decision 0076). Regressions for all
  three in `test_findings_2026_08_07_deferred.py`.
* **An erasure path.** There is no `memory_delete`, deliberately — deletion
  punches a hole in a hash chain by construction. It has to be *designed against*
  the ledger (tombstones plus documented re-anchoring, or key destruction for
  encrypted fields). Until then: do not put personal data in the source text.
  `QUESTIONS.md` §10.
* **Semantic matching.** Would fix the acronym/synonym miss class outright, and
  costs the first runtime dependency in a zero-dependency package — which is a
  positioning decision, not an engineering one. §3.3, and read §3.4 first: it
  measured the alternative across four stages and found the matcher, not the
  corpus, was the binding constraint. `nestor calibrate` now makes the cost of
  *not* doing this measurable per deployment, which is the strongest argument
  for it that exists.
* **A store that takes concurrent writers.** The Protocol allows one; the
  reference `SqliteStore` is not it, and the ledger's locking covers threads in
  one process and processes on one box. This is the remaining half of "run it
  for a team" (`QUESTIONS.md` §15).

## 3. Smaller, and known

* **A checkpoint somebody else holds.** The append-time checkpoint lives in
  process memory, so it does not survive a restart. The version that does is a
  sidecar the ledger's writer cannot reach — which is `nestor.frank`'s argument
  again in miniature. §5.5.
* **Hot backup while WAL is open.** ``nestor db checkpoint`` and ``--out`` shipped
  (§6.7); see ``docs/local-fleet.md`` for fleet-side paths.
* **Seal staleness and quorum.** A seal is true forever and one person's seal is
  enough. Neither is obviously right for a regulated buyer, and neither has been
  argued through. §1.4.
* ~~**The UI cannot be told its domain's matcher.**~~ Shipped 2026-08-07:
  `ui.App(matcher=)` and `nestor ui --matcher`, threaded through every decision
  the surface makes. §6.40, and it answers §6.41. Worth keeping visible here for
  one reason — it was found by pointing a fixture at the Matcher seam *from the
  human surface* rather than from the library, and nothing else in this queue has
  been looked at that way yet.
* **Record the sixty seconds.** `demo/sixty_seconds.py` is the script — eight
  beats, self-asserting, `--fast` for CI. Nobody has pointed a screen recorder
  at it. §4.3.
* **A terminal `nestor seal`** is deliberately absent — `--verifier "$USER"` in a
  cron job is not a human checking anything. Listed here so nobody adds it by
  accident. §5.1.

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
worked examples. [`docs/code-review-lessons.md`](docs/code-review-lessons.md)
collects the pre-PR checklist from the PR #22–#24 review rounds.

The same test retired the held-back bench branch: it carried a second review
surface, weaker than `nestor.ui`, that could seal into the same store. The
dashboard landed and the playground did not. Two paths in, one of them
unguarded, is the defect — it does not stop being one because it is a UI.

And a variant worth naming separately, from the same day's work: **a guarantee
that only holds where somebody thought to look.** `best_sealed` filtered
`lookup()`'s top five, so a verified seal ranked sixth was invisible to tier 1.
Nothing was bypassed and no rule was missed; the code just answered a narrower
question than the one it was asked. That one is only found by asking what the
code does when the easy case does not hold.
