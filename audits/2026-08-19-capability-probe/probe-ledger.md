# Nestor ledger/evidence/export/import/db/keys probe

Environment: `/home/user/Nestor`, demo DB at `data/nestor-demo.db` +
`data/nestor-demo.ledger.jsonl` (15 entries, 8 seals). Ran 40+ commands.

## 1. `--db` and `--ledger` are fully independent, unvalidated flags (biggest finding)

`nestor --db X.db ledger ...` (and `evidence`, `export`, `db`, `stats`) does **not**
derive the ledger path from `--db`. Omitting `--ledger` silently falls back to the
hardcoded default `data/ledger.jsonl`, regardless of which `--db` you named.

Reproduced concretely:

```
$ nestor --db data/nestor-demo.db ledger verify
✓ no ledger yet   (data/ledger.jsonl)          # wrong file, and it AUTO-CREATES it
```

Every command that touches the ledger without an explicit `--ledger` quietly
reads/writes/creates `data/ledger.jsonl` — a file totally unrelated to
`nestor-demo.db`. This file accumulated entries across my session (grew from
0 → 22 → 6 → 7 → 9 → 15 lines as different subcommands ran) purely because I
forgot `--ledger` on some invocations; nothing else was writing to it.

**Consequence for the "has a human checked this?" mission**: `nestor stats`
prints a `ledger: ✓ intact — N entries` line that reads as "the chain backing
this database is intact." It is not — it is the chain backing whatever
`data/ledger.jsonl` happens to contain right now, possibly from a different
database entirely. I confirmed this directly: with the default (wrong) ledger,
`stats` reported "✓ intact — 15 entries"; with the correct
`--ledger data/nestor-demo.ledger.jsonl` it *also* said "15 entries" — same
count, **completely different content** (`diff` shows no overlap at all; one
file's first entry is `kind: reconcile, label: q3-revenue`, the other's is
`kind: seal, pair_id: 2338571e...`). Two unrelated hash chains of the same
length are indistinguishable in the summary line. A user or agent who trusts
"ledger: intact" without separately confirming the *path* is being fooled by
a coincidence that is easy to manufacture.

Same independence holds for `nestor db --out X`: the sidecar it copies
(`X.ledger.jsonl` / `X.db.ledger.jsonl`) also comes from `--ledger`'s default,
not from whatever ledger actually documents `--db`'s seals, unless you pass
both flags to match.

**Recommendation**: default `--ledger` from `--db`'s directory/basename (as
the export bundle's naming convention already suggests), or at minimum have
every ledger-touching command print which `--db` it believes that ledger
corresponds to, and refuse silent auto-creation of a ledger file that doesn't
exist yet in non-interactive/no-op read commands like `verify`.

## 2. `--db` pointing at a nonexistent path silently creates an empty DB

```
$ nestor --db /tmp/nope-does-not-exist2.db evidence report
no live sealed pair is missing evidence.
$ ls -la /tmp/nope-does-not-exist2.db
-rw-r--r-- 1 root root 102400 ...    # brand-new empty SQLite file, no warning
```

A typo'd `--db` path produces a valid, empty, silently-created database and a
success-shaped ("no live sealed pair is missing evidence") response instead
of an error — indistinguishable from "this store legitimately has zero
findings." Same for `export` (`counts.pairs: 0`, no error, exit 0). Combined
with finding #1, a single stray keystroke on `--db` can make an agent believe
it audited a full store when it audited nothing.

## 3. Ledger tamper-evidence itself is solid

Directly tested against `data/nestor-demo.ledger.jsonl` (via copies):
- Editing a field in a middle entry → `✗ broken chain at line 4: prev=... expected ...`
- Deleting a middle entry → `✗ broken chain at line 6: prev=... expected ...`
- Appending a non-JSON garbage line → `✗ line 16: not valid JSON`
- `--expect-head <wrong-hash>` → refuses with a clear diagnostic naming the
  actual head and explaining possible causes ("the last entry was edited, or
  entries were added or removed")

All of these were caught correctly — the hash-chain mechanism itself is sound.

**Gap**: truncating the ledger file to 0 bytes is reported as
`✓ intact — 0 entries`, which is *technically* correct (an empty file is a
valid empty chain) but means wholesale replacement of the ledger with an
empty file is indistinguishable from "nothing has ever been sealed here" —
`ledger verify` alone, without a separately-pinned `--expect-head` from
outside the file itself, cannot detect a full-file swap or truncation. This
is a known category of limitation for hash chains without an external
anchor, but the tool doesn't call it out anywhere in `verify`'s output.

## 4. `evidence` — what it tracks

`nestor evidence report` lists sealed pairs with **no evidence reference**
attached — described accurately in its own help text as "a queue for a human,
not a block on sealing." On the demo DB, all 8 sealed pairs had zero evidence
(the demo doesn't attach any). `evidence attach --kind {document,
human_statement, prior_seal, url} --locator ... --reason ... --by ...` adds a
reference and logs an `attach_evidence` ledger entry with a `content_sha` —
itself chained, so evidence attachment is audit-logged, but the CLI is
explicit that a reference "confirms nothing and changes nothing about what is
served" — it's informational, not a second signature.

- `evidence attach <nonexistent-pair-id>` → correctly rejected: `no pair
  '00000000-...' in this store`.
- `evidence for <nonexistent-pair-id>` → **not** rejected — returns the same
  "no evidence attached to <id>" message as a real pair with zero evidence.
  Minor inconsistency: `attach` validates pair existence, `for` doesn't, so
  you can't tell "this pair has no evidence" from "this pair doesn't exist"
  via `evidence for`.

## 5. Export / import round-trip

- `nestor export --format json` embeds a `digest` (SHA-256 over a
  version-gated canonical field set — see `nestor/portable.py:123`), the
  pairs, rejections, evidence, and (unless `--no-ledger`) a `ledger` block
  containing `{"note": "the source instance's chain, for audit; it is not
  merged on import", "entries": [...]}`.
- **The embedded ledger is explicitly advisory only** — confirmed by
  behavior: importing into a fresh DB creates a **brand-new independent
  ledger chain starting at `genesis`**, with a single `bundle_import` entry
  recording `digest=... sealed=8 demoted=0 drafts=1 existing=0 conflicts=0
  rejections=0 evidence=0 source_created_at=...`. **The source chain is not
  preserved, merged, or replayed** — only its summary digest is. So export/
  import round-trips the *data* (pairs, seals, rejections, evidence) but
  deliberately does **not** round-trip the audit chain itself; the target
  starts its own provenance from that one import event forward.
- Every `sealed` row required `NESTOR_SEAL_KEY` to actually verify; unset (as
  here), export/import both warn loudly: *"seal signatures are NOT verified;
  any 'sealed' row is trusted"* (export) and *"N imported seal(s) were
  trusted on the bundle's word alone"* (import) — i.e., with no seal key
  configured, the whole export/import pipeline degrades to trusting the
  bundle's own claims about what was sealed. This is called out clearly in
  the tool's own output (not hidden), but it's a fail-open default worth
  flagging: `NESTOR_REQUIRE_SEAL_KEY=1` exists precisely to convert this into
  a fail-closed mode and is off by default.
- **Digest integrity is genuinely enforced on import**: hand-tampering either
  the `digest` field or any pair's content (`target_text`) and reimporting
  →  `not a usable bundle: digest mismatch: the payload is not the one
  exported (expected ..., computed ...)`, exit code 2. Verified both
  directions (bad digest w/ good payload, and good-looking digest recomputed
  over tampered payload using my own guess at the algorithm — which itself
  didn't match, since the real canonicalization is more selective than plain
  `json.dumps(sort_keys=True)`, per the code comments about being
  version-gated so old digests stay byte-identical).
- Dry run (no `--apply`) is a true no-op: "nothing was written — re-run with
  --apply to commit," verified by absence of the target DB file before
  `--apply`.
- Re-importing an already-imported bundle is idempotent for data (`9 already
  present`, 0 sealed/demoted/draft) but **still appends a new `bundle_import`
  ledger entry** even when nothing changed — i.e., every import attempt is
  logged, successful or not, which is good audit hygiene but means replaying
  the same bundle N times grows the ledger by N no-op entries.
- CSV export is lossy as documented (drops `seal_sig`, adds a computed
  `servable` column) and cannot itself carry a seal on reimport.

## 6. `nestor db` — SQLite maintenance

- `nestor db` / `nestor db checkpoint` (no `--out`): in-place WAL checkpoint,
  reports `checkpointed <path>`.
- `nestor db --out X`: `VACUUM INTO` a consistent copy, plus copies the
  ledger sidecar to `X.ledger.jsonl` unless `--no-ledger` — but (see finding
  #1) that sidecar comes from `--ledger`'s default unless you pass it
  explicitly, so `nestor db --db real.db --out copy.db` alone silently
  bundles the *wrong* ledger with the copy.
- Refuses to clobber an existing destination without `--force`: "refusing to
  overwrite ... (pass --force)" — confirmed, and `--force` does overwrite.
- `--no-ledger` correctly produces a DB-only copy with no sidecar file at
  all — the help text's own framing ("seals without audit chain") is
  accurate and worth taking seriously: such a copy has seals with no way to
  audit who/when without the paired ledger.

## 7. Nonexistent-file behavior, summarized

| Flag | Command family | Result |
|---|---|---|
| `--db` nonexistent | `ledger verify/head/entries` | Ignored entirely — ledger commands don't touch `--db` at all |
| `--db` nonexistent | `evidence report`, `export`, `stats` | Silently creates an empty 102400-byte SQLite file, reports success with zero rows |
| `--ledger` nonexistent | any ledger command | Treated as "no ledger yet" / empty chain (`head genesis`), not an error |
| `--keyring` nonexistent | `keys list` | Correctly errors: `KeyringError: no keyring at ... Create one with 'nestor keys add NAME'` |

None of the DB/ledger paths error on a missing file — they all auto-vivify or
report an empty/`genesis` state. Only the keyring path treats "doesn't exist"
as a hard error rather than "empty."

## 8. `nestor keys` — who can seal, key formats

- Two key types: `hmac` (shared secret, `NESTOR_SEAL_KEY`) and `ed25519`
  (asymmetric; `--type ed25519` generates a keypair locally, or `--public
  HEX` registers a **peer's** public key only — private half never touches
  this instance).
- **Agent governance hook fires correctly**: `nestor keys add NAME --type
  {hmac,ed25519}` (minting a *new*, self-owned signing key) is blocked by a
  repo-level `PreToolUse`/`before_bash` hook
  (`hooks/before_authority.py`) with `Self-grant tripwire: this act would
  mint the power to seal (forge a human's ratification)`. This is
  intentional per `hooks/seat.md`/`docs/agent-guide.md`, not a bug — I did
  not attempt to bypass it. The same hook also blocked `nestor import
  --apply --verifier NAME` (naming yourself as the human verifier of an
  import), while import `--apply` **without** `--verifier` (empty-string
  default) went through fine — so the tripwire is specifically about
  claiming a human identity, not about writing data.
- Consistent with the hook's own stated exceptions, these worked without
  issue: `keys list`, `keys revoke`, and `keys add --public HEX --type
  ed25519` (registering a **peer's** public key, no private key ever
  generated here).
- **Found a real robustness bug** in the keyring: `keys add --public HEX
  --type ed25519` does **not** validate the public key's byte length at
  write time — I added a peer key with a 30-byte (60 hex-char short of 64)
  "public key" and it was accepted and written to the keyring file without
  complaint. But **every subsequent read** (`keys list`) on that keyring now
  throws `KeyringError: the ed25519 public key for 'eve' must be 32 bytes,
  got 30` and refuses to list *any* verifier in the file — including a
  previously valid one added earlier. One malformed `--public` value poisons
  the whole keyring file for all read operations (`list`, presumably
  `revoke` too, since it has to load the file first) until someone manually
  edits the JSON to remove/fix the bad entry. This is a self-inflicted
  denial-of-service: validation happens on load, not on write, so garbage
  can get in cheaply but can't be read/queried back out short of hand-editing
  the keyring JSON.

## 9. Ledger/DB disagreement scenarios

- The clearest disagreement I could produce without bypassing the sealing
  guardrail was exactly finding #1: pointing a real `--db` at an unrelated
  `--ledger` (or the silently-defaulted one). `nestor stats` doesn't
  cross-check that the ledger's `seal`/`baseline_seal`/`entity_seal` entries
  actually correspond to the sealed rows currently in `--db` — it only
  checks that the ledger file's own hash chain is self-consistent, and
  reports pair counts from the DB and entry counts from the ledger as two
  separate, unlinked numbers on adjacent lines. Nothing in `stats` output
  flags "these two numbers describe different stores."
  - Concretely: demo DB (9 pairs, 8 sealed) + the stray unrelated
    `data/ledger.jsonl` (also, coincidentally, ended up at 15 lines) both
    show "✓ intact" with no indication they don't describe each other.
- I deliberately did not try to fabricate a DB row whose `seal_sig`/status
  contradicts its ledger entry (e.g., hand-editing SQLite to mark a pair
  `sealed` without a matching ledger entry) because that's squarely "mint
  the power to seal" territory the repo's tripwire exists to prevent, and
  the task instructions are explicit that this agent may propose findings,
  not confirm/forge seals.

## Commands run (representative, 40+ total)

`ledger {verify,head,entries}` with/without `--expect-head`, `--kind`,
`--limit` (incl. `0` and `-1`, which fall back to "show everything" via
Python slice semantics rather than erroring); `evidence {report,for,attach}`
incl. nonexistent pair IDs; `export --format {json,csv}` with/without
`--no-ledger`/`--out`; `import` dry-run and `--apply`, idempotent re-import,
digest-tamper attempts (bad digest, tampered payload); `db`, `db checkpoint`,
`db --out` with/without `--force`/`--no-ledger`; `keys {list,add,revoke}`
with `hmac`/`ed25519`/`--public`, malformed public key; ledger corruption
(field edit, entry deletion, garbage append, truncation); nonexistent
`--db`/`--ledger`/`--keyring` paths; `--json` global flag (works for
`evidence report`, is silently ignored — no error, just plain text — for
`ledger verify`, and errors with a helpful message about flag ordering when
placed after the subcommand instead of before it).

## Files used

- Demo store: `data/nestor-demo.db`, `data/nestor-demo.ledger.jsonl`
  (untouched/original, verified intact throughout with the correct
  `--ledger` flag)
- Scratch copies/exports/keyrings:
  `/tmp/claude-0/-home-user-Nestor/b2bb32f9-9208-5449-8125-3d3598b210a2/scratchpad/`
  (`test.db`, `fresh*.db`, `export*.json`, `keyring*.json`,
  `tamper*.ledger.jsonl`, `checkpoint*.db`)
- Incidental: `data/ledger.jsonl` — a stray file that did **not** exist
  before this session's default-flag omissions created/grew it; it is
  gitignored (`data/` is in `.gitignore`) so it's harmless, but its
  existence is itself evidence for finding #1.
