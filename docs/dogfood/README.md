# The decision memory

Nestor's own decisions, in Nestor. This grows one merged PR at a time.

```bash
python scripts/dogfood_store.py --rebuild   # after adding a decision file
python scripts/dogfood_store.py --verify    # gate: matches the files, seals nothing
nestor --db docs/dogfood/nestor.db ui       # the queue
```

## The rule

Every PR that makes a decision worth keeping adds **one file** to
`decisions/`, named `<pr>-<slug>.json`, and re-runs `--rebuild`. `--verify` is
a test, so a PR that adds a decision and forgets to rebuild fails.

One file per PR rather than one growing bundle, because separate files cannot
collide and `nestor.db` is *derived* rather than merged — a binary artifact that
two branches both edited is a conflict nobody can resolve, and this one can
always be regenerated from text somebody reviewed.

## Remote to local, never local to remote

The builder reads the decision files **in this checkout** and nothing else. Not
your `data/nestor.db`, not the process-wide store, not `NESTOR_DB`.

That is a gate rather than a promise:
`tests/test_dogfood_store.py::test_a_local_store_cannot_reach_the_committed_one`
installs a poisoned ambient store and proves none of it arrives. The reason is
the reason for all of this — a memory whose rows came from somewhere nobody can
see is not an audit trail, and every row here is traceable to a file in a merged
PR.

Note the asymmetry with the glossary (`IDEAS.md` §6.27) and the ledger, which
*are* configurable per deployment. Those describe where a running instance keeps
its own state. This is the artifact of a merged PR, so its location is a
repository path and not a setting.

## Everything here is a draft

Zero sealed, asserted twice — once while building, once against the committed
file, so a row sealed by any route at all is caught rather than assumed
impossible. The machine may propose. The queue at `nestor.ui` is where that
changes, and it belongs to a human.

Several of these rows deserve a no.

## What this is for

`IDEAS.md` §6.33: the memory had 21 rows against a codebase whose distinguishing
feature is that almost every line is argued, and the reasoning lived in
docstrings and `QUESTIONS.md` where nothing could retrieve it. Growing the store
per PR is the answer that does not involve scraping — every row is here because
somebody decided to put it here, which is the only thing that makes it worth
having.

§6.33 also measured the limit, and it is not the corpus size: retrieval works
when a question names code and fails when it names a practice. Most decisions
here are practices. Growing the store does not fix that, and this file should
not be read as claiming it does.
