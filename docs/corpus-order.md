# The order the corpus takes the repositories

*The sequence for the corpus-from-a-corpus exercise (IDEAS §6.40–§6.45). Written
2026-08-06. This file exists because the order has exceptions now, and an
exception agreed in conversation and not written down is one a later session
will silently undo.*

## The rule

**Oldest first, by GitHub `created_at`** — the chronology measured in §6.40, not
the last-push order the repository listing returns by default. One repository
per rung, each rung branched from the one below it (`corpus/NN-<repo>`), so a
rung carries every rung beneath it and a low rung has to be right before
anything is built on it.

## The exceptions

| repository | position by date | taken | why |
|---|---|---|---|
| `yggdrasil-training-data` | 5th (2026-04-15) | near the end | operator's decision |
| `sean-data-vault` | 34th (2026-05-25) | near the end | operator's decision |

Both are **data archives rather than source** — a behavioural corpus and an
operator archive of fleet snapshots and knowledge bases. Taking them late means
the extractor shapes are mature by the time they are read, which matters more
for repositories whose content *is* the payload than for ones whose content is
documents about a payload.

## Open, and it arrives at rung 7

**Forks are still unresolved.** 44 of the 105 are forks of other people's
projects. Extracting one measures its *upstream author's* structure, not this
operator's, so the rows would be provenance-correct and subject-wrong — a corpus
about somebody else filed under this chronology. `hermes-agent` (2026-04-18) is
the first, and the question wants an answer before it, not after.

## Where a rung's results go

Findings to `IDEAS.md` §6, one entry per rung. Extracted rows stay in gitignored
`data/corpus/`, and for a private source nothing extracted is committed at all —
see §6.41. The extractors themselves are committed, under `scripts/corpus/`,
because a row whose `origin` names a toolchain nobody can fetch is not provenance
(§6.43).
