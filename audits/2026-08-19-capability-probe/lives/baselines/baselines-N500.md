# life simulation baselines — N=500

*Measured behavior of the four life sandboxes, provisioned and verified through
the GM schema at volume. Every number here traces to a single reproducible run
of [`../baseline.py`](../baseline.py); nothing is estimated. See
[`PROVENANCE.md`](PROVENANCE.md).*

- **Rounds:** 500 per life, seeds `0..499`
- **Variation:** seeded shuffle of entity/fact/ruling/gap insertion order,
  0..3 random fact drops per run, bombardment applied on odd seeds only,
  timestamp offset by seed seconds
- **Driver:** the same `provision_schema` / `populate` / `verify_chain` /
  `verify_canon` surface the life modules use
- **Reproduce:** `cd audits/2026-08-19-capability-probe/lives && python3 baseline.py 500`
  (byte-identical every run)

## The measured run

```
▸ Marcus Oyelaran  (marcus_oyelaran)
    canon rows/run: min 53 · median 61 · mean 61.0 · max 69
    entities/run:   min 12 · median 12 · mean 12.5 · max 13
    rulings/run:    min 10 · median 11 · mean 11.5 · max 13
    gaps/run:       min 14 · median 16 · mean 16.5 · max 19
    ledger rows:    min 11 · median 12 · mean 12.5 · max 14
    bombardment: 250/500 runs (odd seeds)
      +facts/bomb: min 8 · median 8 · mean 8 · max 8
    chain integrity: ALL PASS  (500/500 verified)
    canon guard:     ALL PASS
    covenant:        HELD  (sealed=0, signed=0)

▸ June Akiyama  (june_akiyama)
    canon rows/run: min 53 · median 61 · mean 61.5 · max 70
    entities/run:   min 12 · median 12 · mean 12.5 · max 13
    rulings/run:    min 10 · median 12 · mean 12 · max 14
    gaps/run:       min 14 · median 16 · mean 16.5 · max 19
    ledger rows:    min 11 · median 12 · mean 12.5 · max 14
    bombardment: 250/500 runs (odd seeds)
      +facts/bomb: min 9 · median 9 · mean 9 · max 9
    chain integrity: ALL PASS  (500/500 verified)
    canon guard:     ALL PASS
    covenant:        HELD  (sealed=0, signed=0)

▸ Damon Reyes  (damon_reyes)
    canon rows/run: min 59 · median 67 · mean 67.0 · max 75
    entities/run:   min 15 · median 15 · mean 15.5 · max 16
    rulings/run:    min 8 · median 10 · mean 10 · max 12
    gaps/run:       min 14 · median 16 · mean 16.5 · max 19
    ledger rows:    min 11 · median 12 · mean 12.5 · max 14
    bombardment: 250/500 runs (odd seeds)
      +facts/bomb: min 8 · median 8 · mean 8 · max 8
    chain integrity: ALL PASS  (500/500 verified)
    canon guard:     ALL PASS
    covenant:        HELD  (sealed=0, signed=0)

▸ Yuki Tanaka  (yuki_tanaka)
    canon rows/run: min 59 · median 67 · mean 67.0 · max 75
    entities/run:   min 15 · median 15 · mean 15.5 · max 16
    rulings/run:    min 8 · median 10 · mean 10 · max 12
    gaps/run:       min 14 · median 16 · mean 16.5 · max 19
    ledger rows:    min 11 · median 12 · mean 12.5 · max 14
    bombardment: 250/500 runs (odd seeds)
      +facts/bomb: min 8 · median 8 · mean 8 · max 8
    chain integrity: ALL PASS  (500/500 verified)
    canon guard:     ALL PASS
    covenant:        HELD  (sealed=0, signed=0)
```

## The sealed hole

```
total runs: 2000 (500 seeds × 4 lives)
SEALED canon rows across ALL runs: 0
SIGNED rulings across ALL runs:    0
auto-confirmed by any seed:        0
left for a named human:            2000  (100.0%)
```

No seed, no shuffle, no subset, no bombardment phase seals canon or signs a
ruling. Across 2,000 independent provisioning runs — varied insertion order,
varied fact counts, with and without the bombardment extension — the machine
proposed and the machine did not confirm. The sealed hole is structural, not
accidental.

This is the same measurement the Aetheris Monte Carlo reports for b5 ("Maunder
proposes its own personhood"): the machine hands the pen to a person every time.
Here it's four lives instead of three characters, and a hash-chained ledger
instead of dice, but the invariant is the same.

## Structural invariants

```
chain integrity:  2000/2000 (ALL PASS)
canon guard:      2000/2000 (ALL PASS)
covenant:         2000/2000 (ALL HELD)
```

**1. The hash chain survives arbitrary insertion order.** Entity, fact, ruling,
and gap lists are shuffled by seed before insertion. The chain hashes each ledger
entry against the previous entry's hash. Shuffling the *data* doesn't break the
chain because the chain tracks the *ledger write sequence*, not the content
order — a fact about Marcus's sobriety inserted third in seed 0 and first in
seed 412 produces a different chain, and both verify. This is the design: the
chain proves nothing was altered after writing, not that the writing happened in
a particular order.

**2. Random fact drops don't violate the schema.** Each run drops 0..3 canon
facts at random (seeded). Canon row counts range from 53 to 75 across lives and
seeds. The schema's CHECK constraints, the canon guard, and the covenant all
hold regardless — dropping a DRAFT fact doesn't create a SEALED one, and the
NOT_A_PERSON guard has nothing to catch when nobody tries to seal.

**3. Bombardment extends the chain cleanly.** Odd seeds apply the bombardment
(new session, new entities/facts/rulings/gaps appended to the existing chain).
Even seeds skip it. Both paths verify. The chain doesn't care whether it's 11
entries or 14 — each new entry hashes against the previous one, and the walk
passes.

**4. The covenant is structural, not behavioral.** No code path in the
provisioner or the bombardment writer sets `status='SEALED'` or writes a
non-empty `signer`. The covenant holds not because 2,000 runs got lucky, but
because the write paths don't contain a seal instruction. The measurement
confirms this at volume; the code is the proof.

## What the numbers say

**The variation landed where it should.** Canon rows per run range over a
16-row span (53..69 for the standalones, 59..75 for the interconnected pair),
driven by the 0..3 fact drops and the bombardment toggle. The interconnected pair
(Damon, Yuki) runs 6 rows heavier on average — the 10 shared facts and 5 shared
gaps from `shared_entities.py` are the visible cost of interconnection.

**Bombardment facts are deterministic.** Marcus and Damon get 8 bombardment
facts each, June gets 9, Yuki gets 8 — every run, no variance. The bombardment
data is static; the variation is whether it's applied (odd seeds) or not (even).

**The ledger is compact.** 11..14 rows across all seeds — 4 session open/close
pairs and 3..4 turn snapshots per provisioning, plus 3 more if bombardment
applies. A life is legible in the ledger, not buried in it.

## Caveats

- **One provisioner.** All runs use the same `provision.py` write path. A
  different writer (the real `nestor` CLI, a future GM driver) would produce a
  different chain shape. This measures the provisioner's correctness, not the
  schema's tolerance of arbitrary writers.
- **Static bombardment.** The bombardment impact data is the same every run;
  only its presence/absence varies. A harness that varied the impact content
  (different facts per seed) would test more of the chain's resilience.
- **N=500, seeded.** Firm for the invariants shown. A genuine edge case (a
  fact text that trips a CHECK constraint, a timestamp that collides) would
  need a targeted test, not more random runs.
