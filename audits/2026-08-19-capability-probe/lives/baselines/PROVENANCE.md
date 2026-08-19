# Provenance

*How every number in [`baselines-N500.md`](baselines-N500.md) was produced.*

## One command

```
cd audits/2026-08-19-capability-probe/lives
python3 baseline.py 500
```

Deterministic: round `i` uses `random.Random(i)` for all shuffling and subset
selection. Same `i` → same DB → same measurements, on any machine with Python
3.10+ and the four DDL scripts + `verify_ledger.py` in the scratchpad.

## What `baseline.py` does per round

1. Loads the life module's data (protagonist, entities, canon facts, rulings,
   gaps) — pure Python dicts, no I/O.
2. Deep-copies and shuffles all four lists using `random.Random(seed)`.
3. Drops 0..3 canon facts at random (seeded).
4. Creates a fresh `campaign.db` in a temporary directory — runs the four DDL
   scripts, writes entities/facts/rulings/gaps across four ledger sessions with
   hash-chained entries.
5. On odd seeds: applies the bombardment (new session, new data appended to the
   existing chain).
6. Runs `verify_chain()` and `verify_canon()` against the DB.
7. Queries the DB for counts: ledger rows, canon rows (by status), entities,
   rulings, gaps, sealed count, signed count.
8. Deletes the temporary directory.

The DB never touches disk outside the tempdir. No global state carries between
rounds.

## What produces the variation

| Axis | Mechanism | Effect |
|------|-----------|--------|
| Insertion order | `rng.shuffle(entities)`, etc. | Chain hashes differ per seed |
| Fact count | `rng.randint(0, 3)` facts dropped | Canon total varies 53..75 |
| Bombardment | Applied on odd seeds only | +entities, +facts, +rulings, +gaps on odd |
| Timestamp | Base ts offset by `seed` seconds | Chain hashes differ per seed |

## What does NOT vary

- The schema (four DDL scripts, identical every run)
- The verify logic (`verify_chain`, `verify_canon`)
- The bombardment content (same impact dicts for each life, every run)
- The covenant constraint (no code path writes SEALED or non-empty signer)

## The numbers are not

- **A test suite.** `baseline.py` measures; it does not assert. The invariants
  (chain passes, covenant holds) happen to be 100% because the code doesn't
  contain a seal path, not because a test enforced it. A proper test would
  inject a seal attempt and verify refusal.
- **A benchmark.** The 38-second runtime is incidental to this machine and this
  Python; the harness is not optimized and the measurement is not timing.
- **A proof of the schema.** The schema's CHECK constraints are tested by the
  DDL, not by this harness. A fact text containing a SQL injection payload would
  not be caught here.

## Source files that determine these numbers

```
audits/2026-08-19-capability-probe/lives/baseline.py
audits/2026-08-19-capability-probe/lives/provision.py
audits/2026-08-19-capability-probe/lives/marcus_oyelaran.py
audits/2026-08-19-capability-probe/lives/june_akiyama.py
audits/2026-08-19-capability-probe/lives/shared_entities.py
audits/2026-08-19-capability-probe/lives/damon_reyes.py
audits/2026-08-19-capability-probe/lives/yuki_tanaka.py
audits/2026-08-19-capability-probe/lives/global_event_meteoroids.py
<scratchpad>/verify_ledger.py
<scratchpad>/01_ledger.sql .. 04_rulings.sql
```

A change to any of these changes the numbers. The DDL scripts and
`verify_ledger.py` are the GM schema from `safe-app-store/apps/ai-game-master/`,
copied to the session scratchpad at provision time.
