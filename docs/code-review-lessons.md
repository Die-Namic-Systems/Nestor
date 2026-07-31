# Code review lessons (Nestor)

Distilled from PR #22–#24 and follow-up review rounds (2026-07-31). Use as a
pre-merge checklist for persistence, audit, threading, and config — not as style
nits.

## The recurring gap

We tend to ship the **happy path** and the **unit test**; reviewers live in
**operations**: long-lived `nestor.ui`, `cp` while the server runs, typo’d env
vars, Ctrl-C in `finally`, dead thread pools and `ulimit -n`. Failures are often
“correct in Python, wrong for someone running the thing.”

## Lessons

### 1. Persistence mode is a product decision

Turning on SQLite **WAL** without an operator story broke backup/rsync: committed
rows can live in `nestor.db-wal` until checkpoint. A plain copy of `nestor.db`
while the process holds connections open may be **incomplete**.

**Do:** document limits; checkpoint on clean shutdown where it helps; tests that
contrast **live copy** vs **after close** (e.g. sealed row counts 0 vs N).
**Don’t:** assume “the database file” is the whole store.

### 2. Refuse bad security-ish config; don’t silently weaken

A malformed `NESTOR_LEDGER_VERIFY_INTERVAL_SEC` (e.g. `5m`) parsed as `0` was
**stricter than unset** for batch jobs but **weaker than unset** for `nestor.ui`
(which only applies the 300s default when the variable is **absent**).

**Do:** parse or **refuse at startup** with a message that names the value and
the fix (plain float seconds). Match `build_matcher` / `NESTOR_REQUIRE_SEAL_KEY`
posture for trust knobs.

### 3. Test the branch you ship

Three-way semantics (`0` / `>0` / `<0`) need a test per mode that matters in
production. The UI ships **positive TTL**; sabotaging “cache never stale” left
the suite green until a dedicated test existed.

**Do:** one test per shipped default path; occasionally break the implementation
to prove the test isn’t decorative.

### 4. Ledger and byte-level fixtures

Tampering ledger JSON with `json.dumps` changes line length, shifts byte offsets,
and can exercise the **tail checkpoint** instead of the **full walk**.

**Do:** length-preserving edits (see `tests/test_ledger.py`,
`test_the_checkpoint_does_not_replace_the_walk`). Name tests after the mechanism
they prove.

### 5. Threading and “tidy shutdown”

Closing every SQLite connection from `close()` hit `check_same_thread` on UI
shutdown. A registry of all connections **pinned** them and leaked FDs after
threads died.

**Do:** one `PRAGMA wal_checkpoint(TRUNCATE)` flushes the whole WAL from **any**
connection; checkpoint from **this thread** only; don’t close other threads’
connections. Document non-reentrant `_db()` if introduced.

### 6. Process hygiene that paid off

- `CONFIGURED_BY_ENV` for knobs that change trust behaviour.
- Hermetic tests; subprocess CLI; monkeypatch only for fault injection.
- README accuracy over stronger-than-true claims (ledger refusal window).

### 7. Sabotage the guard you care about

For security- or audit-sensitive branches (TTL cache stale, positive interval,
prefilter short-circuit), **break the implementation once** and confirm exactly
one test fails. A test that stays green when the branch is nop’d is decoration.

### 8. Two paths in; one guard

Four 2026-07-31 defects were the same shape: a guarantee at call sites and a
second path into the store that never passed it (import vs `add_pair`, UI vs
playground). Pre-PR question: **can this rule be reached around?** If yes, move
the rule to the one place that cannot be bypassed. See `TODO.md` and IDEAS
§1.6–§1.8.

### 9. Answers a narrower question

Nothing was bypassed, but the code answered the wrong question — e.g. tier-1
ranking that only considered the top *k* candidates while a verified seal sat
sixth. Ask what happens when the easy case does not hold, not only “did we call
the guard.”

### 10. Running backup (WAL)

Clean shutdown checkpoints help; **rsync/cp while the UI is up** still needs an
operator story beyond “stop the server.” Until a first-class command exists,
document SQLite `VACUUM INTO` or `nestor export`; see IDEAS §6.7.

### 11. Pre-PR operator checklist

Before opening a PR that touches store, ledger, or long-lived surfaces:

| Question | Example failure |
|----------|-----------------|
| Backup/copy while running? | WAL incomplete `cp` |
| Clean shutdown vs kill? | no checkpoint |
| Bad env var? | typo disables UI TTL |
| Concurrent / pooled threads? | FD leak, cross-thread `close` |
| Entrypoint-specific defaults? | UI 300s vs CLI 0 |
| Audit/serve decision path? | refuse vs degrade |
| Second write path? | import, UI, CLI divergence |
| Guard only on happy ranking? | top-k hides valid seal |

## References

- IDEAS §1.4, §1.6–§1.8, §2.4, §5.3, §6.5–§6.7
- `TODO.md` — queue and “how this repo finds things”
- PR #24 review threads (WAL, TTL env, `close()` threading)
- `tests/test_sqlite_store.py` (WAL snapshot, threaded `close`)
- `tests/test_ledger_verify_interval.py` (TTL, env parse)
