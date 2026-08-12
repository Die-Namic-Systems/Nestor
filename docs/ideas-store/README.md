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

## The measurement thread — can this corpus be *served*, or only ranked?

§6.106's caveat above is a claim; this store was used to measure it. Because
`fastembed` and `ollama` are egress-blocked here, every semantic number below
comes from a **Haiku model standing in for the embedder** as a *measuring
instrument* ([`../embedder-stand-in.md`](../embedder-stand-in.md)) — parallel
subagents scoring on a fixed rubric. The boundary held throughout: **nothing
sealed, no cache keyed, every row still a draft.** Per §6.99 the stand-in drifts
0.150/0.300 between instantiations, so *serve/no-serve* calls are instrument
readings and **rank** movements are the durable signal. Raw scores for every run
are under [`standin-scores/`](standin-scores/).

Five question-shaped probes, correct referent's rank and whether it clears the
0.92 serving bar. Rounds 2–4 use a 29-entry near-neighbour slice (the hard
competitors), stated as scope.

| round | matches against | serves correct referent | rank-1 | doc |
|---|---|---|---|---|
| 1. title (`StringMatcher`) | heading, char-ratio | — | — | *(baseline)* |
| 1. title (semantic stand-in) | heading | 1/5 | 3/5 | [semantic-standin-measurement](semantic-standin-measurement.md) |
| 2. + authored surfaces | heading + 2 aliases | 2/5 | 3/5 | [authored-surfaces-measurement](authored-surfaces-measurement.md) |
| 3. body chunks | entry body (max over chunks) | **5/5** | **4/5** | [body-matching-measurement](body-matching-measurement.md) |
| 4. body, leave-one-out | body, answer removed | **≥2/5 serve a *wrong* entry** | — | [body-matching-loo-control](body-matching-loo-control.md) |

**The arc, in one line each:**

1. **Semantic over titles** lifts *rank* where the title carries meaning (two
   probes recovered from rank 20/143 and 122/143 to the top 3) but serves almost
   nothing — and trades one failure for another where a title is cryptic.
2. **Authored surfaces** (§3.4's mechanic) mostly *failed* — helped 1 probe,
   hurt 2 — because you cannot author an honest alias for a meaning the entry
   does not hold, and the negative control confirmed the one win was real.
3. **Body-matching is the recall fix** — serves the correct referent on 5/5 and
   fixes both stubborn misses, because the answer genuinely lives in the body
   (§5.7's "the machine grades its own work" is chunk 44, not the title).
4. **The leave-one-out control refuses it as a *serving* mechanism** — remove the
   answer and ≥2/5 probes serve a wrong entry at 0.92, every false seal a genuine
   topical neighbour. That is IDEAS §1.1 reproduced: *a false seal is a genuine
   near-duplicate, and the margin signal inverts.*

**Conclusion:** on a corpus this self-similar, a similarity score can **order** a
reviewer's queue but cannot **adjudicate** a served answer at any threshold —
which is not a limitation to fix but §4.2's thesis meeting its corpus: *a machine
drafts and ranks; a human seals.* The store is already that shape.

To seal or reject any of these, as a human:

```bash
nestor --db docs/ideas-store/nestor.db ui
```
