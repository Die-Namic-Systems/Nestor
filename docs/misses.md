# Misses — what was asked and had no verified answer

> `nestor/misses.py`, the `query_misses` table, and `meta.miss_seen` on a
> `pending` answer. Landed 2026-08-28.

A `pending` answer means nothing verified matched. This package's architecture
rests on that set shrinking — every seal retires a question from the inference
path permanently — and until now nothing measured whether it was.

The ledger holds **599 seals against 4 recorded passages**, and 5.7% of what
the store knows is sealed. The question a human actually faces is *"which of
these should I seal next?"*. It has a correct answer — the ones missed most
often — and it had no data behind it. Sealing in the order things happen to be
written is the least efficient possible ordering for a cache.

## Two tiers, and the threshold is not a compromise

A question asked **once** is noise. A question asked **twice** is a gap.

You would not want singletons in a seal queue anyway: a one-off is exactly what
is not worth a human's scarce seal. So the `k >= 2` gate makes the queue *more*
useful and, at the same time, means no question asked once is ever written down
in readable form. The privacy property falls out of the correct design rather
than costing anything.

| sighting | stored |
|---|---|
| 1st | `sha256(source_norm)`, a count, timestamps. **No readable text.** |
| 2nd+ | the normalized query text, alongside the count |

Same shape as `homestead`'s `cover_counts`, where a category that does not
survive `k >= 2` is **absent** from the result rather than reported as zero.

**Hashing everything would defeat the purpose.** A miss log exists to tell a
human what to answer; `sha256 + count` says *"something was asked twelve
times"* with no referent. That is Nestor's own `llm-only-joke` failure — a row
correct, dated, evidenced, and unfindable by its own subject. Readability is
the point at the tier where action happens, which is why only the singleton
tier withholds it.

### Honest scope

A singleton row **still confirms a guess**. Someone holding the exact
normalized query can test whether it was asked. It cannot be enumerated back to
text, and that is the whole of what it hides. Stated here rather than implied,
the way `corpus-lens`'s `CoarseTime` declares that `day_offset % 7` still leaks
weekly cadence.

## A miss is not a proposal

`nestor.answer.propose` writes a **draft**, and the cascade serves drafts at
tier 2. A miss recorded as a proposal with an empty target would put an *empty
answer* in the servable tier — strictly worse than the honest `pending` it
replaced, and a direct breach of *"nothing to offer, said plainly rather than
improvised"*.

- A **proposal** says: a machine produced an answer and wants review.
- A **miss** says: nobody has an answer.

Different tables, deliberately. `tests/test_misses.py::test_a_miss_never_becomes_a_pair`
pins it.

## It does not travel

Bundles carry sealed answers — the portable asset. The record of what was *not*
known stays home. `portable.py` draws the same line for warrants: an import may
carry a warrant and may never carry a conclusion about it. A miss log on a
portable drive is a record of the operator's questions leaving the house.

## Fail-open, not fail-silent

A failure to record must not turn an answer into an outage — an odometer is not
worth failing a serve over. It must also not vanish: the reason lands in
`meta["miss_log_error"]` where the caller can see it.

This box has paid for the other posture. An expired `ENGINE_PROPAGATION_TOKEN`
stopped eleven verticals for three and a half weeks with no signal; a Grove
sender wrapped in `except Exception: pass` has sent zero messages since it was
written. Both were fail-open by a defensible local decision, and the sum of
defensible local silences is a box where nothing that breaks says so.

## Reading it

```python
from nestor import misses
misses.queue(store)      # gaps, most-missed first — every row readable
misses.coverage(store)   # totals, including `withheld`: singletons not shown
```

`coverage()` reports `withheld` as a number so the readout is honest about how
much it is not showing — an absence with a stated size, rather than a queue
that quietly looks shorter than the truth.

## What this does not measure

The log attests to what was asked **through Nestor**, never to what was needed.
A question nobody thought to ask leaves no trace, so the queue is a floor on the
gap and not a measure of it — the same limit `terpsi-music` states for anchored
logs: *an anchor attests to what a log contained, never to what the world
contained.*
