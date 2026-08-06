# This session's own build decisions, in Nestor

A Nestor store holding the thirteen decisions made while building six open
`IDEAS.md` entries on 2026-08-06 — §6.8, §4.2, §4.4, §1.4, §6.22 and §6.12 — in
a cloud container with no access to the operator's corpus.

Regenerate it, byte-for-byte content, with:

```bash
python scripts/dogfood_sandbox_build.py --keep docs/dogfood/2026-08-06-sandbox-build
```

Read it the way any store is read:

```bash
nestor --db docs/dogfood/2026-08-06-sandbox-build/nestor.db stats
nestor --db docs/dogfood/2026-08-06-sandbox-build/nestor.db ui     # the queue
```

## Everything in here is a draft

Thirteen rows, zero sealed. That is asserted, not hoped: the script exits
non-zero if a run ever produces a sealed row, and the assertion lives in
`scripts/dogfood_common.py` so a second dogfood script cannot get its own copy
to forget.

Two of the thirteen were the operator's calls rather than mine — which tranche
of ideas to build, and where this store should live. They are drafts too. A
choice made in conversation is not a signature, and the only place a seal
happens is a human at `nestor.ui`.

Several of these rows deserve a no.

## There is no ledger here, and that is correct

A sibling `ledger.jsonl` is missing because nothing in this store is a ledger
event. Checked rather than assumed: `scripts/dogfood_session_decisions.py`, run
with 8 drafts and 4 rejections, produces a chain containing
`Counter({'reject_match': 4})` — four entries, none of them for its eight
drafts.

The ledger records **decisions**: seals, rejections, supersessions. A machine
proposal is not a decision, so a store of pure drafts has an empty chain by
construction. If these rows are ever sealed or rejected at `nestor.ui`, that is
when the chain starts, and from then on the store and its chain must be backed
up and restored together.

This is the same asymmetry `docs/detection-kit-as-gates.md` ends up naming from
another direction: Nestor records decisions thoroughly and the process that
produced them not at all.

## Why it is committed at all

`.gitignore` blocks `data/` and `*.db`, and this file is here rather than
force-added past that rule. The two negation lines at the bottom of `.gitignore`
say so explicitly, mirroring the distinction `bench/results/` already draws — a
store a run happens to write is an artifact, a store committed here is evidence.

The container this was built in is ephemeral and reclaimed after inactivity. A
store left in `/tmp` would have been a demonstration nobody could open.
