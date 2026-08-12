# IDEAS.md, loaded into a Nestor

[`../../IDEAS.md`](../../IDEAS.md) fed into a fresh store, **one draft pair per
section heading** — the whole document partitioned with no gaps.

```
143 pair(s): 0 sealed, 143 draft
  domains: idea→idea (143)
```

- **The piece** — every `#`/`##`/`###` heading starts a row. `source_text` is
  the heading title (the query surface; the § number is kept so rows can't
  collide and each traces back); `target_text` is the entry body; `reason` is
  the entry's own status tag (*measured / shipped / open / …*), pulled from the
  bold tail of the heading.
- **All draft, nothing sealed.** A machine loaded these. Per the standing rule —
  *you may propose, you may not confirm* — sealing is a human in `nestor ui`,
  not this script. 143 rows and 143 things a person has not yet checked.
- **This is the case IDEAS.md keeps asking for.** §6.14 fed one session's
  decisions in as drafts; §6.33 records that *"the memory has never been given
  the project's decisions"*; §6.106 measures where retrieval over them actually
  fails. This is that corpus, standing.

It already shows the mechanic. Querying the seam over the `idea` domain:

```bash
nestor --db docs/ideas-store/nestor.db match \
  "the threshold should be calibrated not constant" --from idea --to idea
# → matched at 0.969 … but nothing sealed; above the bar there is only draft.
```

The right entry (§1.3) is found at 0.969 and **still not served**, because
nobody has verified it. That is the product, not a bug: *close is not the
problem here, unverified is.*

- **The store is derived.** [`nestor.bundle.json`](nestor.bundle.json) is the
  reviewable source; `nestor.db` is a gitignored, regenerable artifact — rebuild
  with `nestor import docs/ideas-store/nestor.bundle.json --apply`.
- **Retrieval caveat, in IDEAS.md's own words (§6.106):** rank is good for
  content-bearing questions and collapses for question-shaped ones, and the
  character matcher (`StringMatcher`) is the binding constraint (§3.4). For real
  use, calibrate and consider `--matcher semantic`/`ollama`.

To seal or reject any of these, as a human:

```bash
nestor --db docs/ideas-store/nestor.db ui
```
