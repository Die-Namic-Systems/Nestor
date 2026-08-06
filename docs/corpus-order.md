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
| `yggdrasil-training-data` | 5th (2026-04-15) | near the end | operator's decision — data archive |
| `willow-mcp` | 7th (2026-04-18) | near the end | operator's decision — **active production** |
| `sean-data-vault` | 34th (2026-05-25) | near the end | operator's decision — data archive |

Two are **data archives rather than source** — a behavioural corpus and an
operator archive of fleet snapshots and knowledge bases. Taking them late means
the extractor shapes are mature by the time they are read, which matters more
for repositories whose content *is* the payload than for ones whose content is
documents about a payload.

`willow-mcp` is held for a different and stronger reason: it is **under active
development**. An extraction pins `repo@commit` into every row's origin (§6.43),
and against a moving head that pin describes a state that no longer exists by
the time the entry is written. A corpus of a live repository is a corpus of a
particular afternoon, mislabelled as a corpus of the repository.

## Forks — default applied, reversible

44 of the 105 are forks. Extracting one measures its *upstream author's*
structure rather than this operator's: provenance-correct and subject-wrong, a
corpus about somebody else filed under this chronology.

**Default, unless the operator says otherwise: forks are skipped in sequence and
revisited at the end with the other held repositories.** If any carries local
modifications worth reading, the honest unit is the *diff against upstream*, not
the tree — and that is a different extractor, not a flag on this one.
`hermes-agent` (2026-04-18) is the first affected and is skipped under this rule.

## Where a rung's results go

Findings to `IDEAS.md` §6, one entry per rung. Extracted rows stay in gitignored
`data/corpus/`, and for a private source nothing extracted is committed at all —
see §6.41. The extractors themselves are committed, under `scripts/corpus/`,
because a row whose `origin` names a toolchain nobody can fetch is not provenance
(§6.43).
