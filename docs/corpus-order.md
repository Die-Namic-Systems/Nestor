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
| `willow-mcp` | 7th (2026-04-18) | **taken at rung 33** | held for active production; read on instruction, pin caveat carried in the rows |
| `sean-data-vault` | 34th (2026-05-25) | near the end | operator's decision — data archive |
| `mealie` | 98th (2026-08-01) | **excluded** | operator's decision — a fork taken to read, not to build on |
| `litellm` | 12th (2026-04-23) | **excluded** | operator's decision — contribution never merged |

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

## Forks — included, but the unit is the delta

44 of the 105 are forks. Extracting the *tree* of one measures its upstream
author's structure rather than this operator's: provenance-correct and
subject-wrong, a corpus about somebody else filed under this chronology. That
was the reason for the first, short-lived default of skipping them.

**The operator's correction, 2026-08-06: what was built on the forks matters.**
It does, and it does not change the objection — it identifies the right unit.
A fork's tree is upstream's work; the operator's commits on top are the
contribution, and those are what a corpus of this author should hold.

So forks are read with a **delta extractor** rather than the standard one:

1. Clone with history (`--depth 1` cannot answer this question at all).
2. Select the commits authored by the operator. Those are the delta, and their
   number is itself a measurement — a fork with zero is a bookmark, not a
   contribution, and the corpus should say which is which rather than assume.
3. Take the commit subjects and bodies as pairs — a commit message is a
   declaration written beside the change, the same argument that admits
   docstrings.
4. Run the standard shapes over **only the files those commits touched**.

`hermes-agent` (2026-04-18), skipped under the old rule, is the first read under
this one.

## Where a rung's results go

Findings to `IDEAS.md` §6, one entry per rung. Extracted rows stay in gitignored
`data/corpus/`, and for a private source nothing extracted is committed at all —
see §6.41. The extractors themselves are committed, under `scripts/corpus/`,
because a row whose `origin` names a toolchain nobody can fetch is not provenance
(§6.43).
