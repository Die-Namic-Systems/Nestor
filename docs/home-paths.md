# Nestor household paths

Nestor's **household** state lives under a root Nestor names: **`~/.nestor`**
(`NESTOR_HOME`). A person who installs Nestor and nothing else should not find
another product's brand in their home directory — that is
[`roots-willow-and-homestead.md`](roots-willow-and-homestead.md)'s audience
test applied to Nestor itself, the same way it already argues a household user
should not be handed `WILLOW_*`.

This replaces the earlier arrangement, in which Nestor mirrored the homestead
seat's `~/.homestead` root. Nestor no longer hardcodes a root it does not own;
a host that wants the keep tree under another face's root **pins it**.

For **`.willow` vs household** vocabulary (fleet vs household, same machine),
see [`roots-willow-and-homestead.md`](roots-willow-and-homestead.md).

```text
~/.nestor/                    # or $NESTOR_HOME
  keep/
    ledger.jsonl              # hash chain — bind before any Nestor append
  record/                     # canonical household record
  logs/                       # sealed log (I-22)
  drafts/
  layout.json                 # written once; the "stood up" marker
```

## In this package

```python
from nestor.home_paths import home, keep_dir, ledger_path, bind_ledger

bind_ledger()  # set_ledger_path(~/.nestor/keep/ledger.jsonl)
```

`bind_ledger()` is the product-side counterpart to homestead's
``nestor_seam.bind()`` (draft in safe-app-store
`docs/drafts/nestor_seam.py`, destination `homestead/keep/nestor_seam.py`).

Stand the tree up with `python -m nestor.home_init` — idempotent, creates the
directories and `layout.json`, and clobbers nothing that is already there.

## Environment

| Variable | Meaning |
|----------|---------|
| `NESTOR_HOME` | Household root (default `~/.nestor`) |
| `NESTOR_DB` | Pinned corpus — one **file**, what `nestor` opens without `--db` |

### Pinning the corpus

`NESTOR_HOME` names a root; **`NESTOR_DB` names one file**, and wins over it.

| set | `nestor` opens |
|---|---|
| `NESTOR_DB=/path/corpus.db` | that file |
| `NESTOR_HOME=/path` only | `/path/keep/nestor.db` |
| neither | `./data/nestor.db`, relative to cwd — unchanged |
| `--db` passed | the flag, always. A pin never overrides a person at a terminal. |

The chain follows the corpus: with `NESTOR_LEDGER` unset, `ledger_for()` takes
`<db>.ledger.jsonl` or `<db-without-suffix>.ledger.jsonl`, whichever exists.
Pinning a store while its chain stayed on the old default is how `stats` came to
report *"ledger: no ledger yet"* against an intact one.

**A bad pin raises `PinRefused`; it does not fall back.** A pin naming a
directory, or one whose parent is missing, is an operator mistake — a typo in a
service file, a stale path after a layout move. Reverting to the cwd-relative
default would write a second corpus where nobody looks and report success. Same
argument as `HomeRelocationRefused`: two plausible locations, so refuse and say
which.

> **Why this was needed.** The willow fleet exported `NESTOR_DB` for weeks while
> no code here had heard of the variable. `nestor stats`, from a directory
> without `data/`, reported *"0 pairs, no ledger yet"* against a store holding
> eleven sealed rows and a valid chain. An empty corpus and a wrong location
> printed the same words — this package's own failure mode, in its own path
> resolution.

## Embedding Nestor in another face

A homestead host that already keeps Nestor's state under `~/.homestead` keeps
it there by **naming** the root:

```bash
export NESTOR_HOME="$HOMESTEAD_HOME"   # or ~/.homestead
```

That is the whole migration for a host that does not want to move anything.

## The refusal: `HOMESTEAD_HOME` without `NESTOR_HOME`

`home()` **raises `HomeRelocationRefused`** when the legacy `HOMESTEAD_HOME` is
set and `NESTOR_HOME` is not. It does not fall back to `~/.nestor`, and it does
not quietly keep honouring the old root.

The reason is the ledger. `keep/ledger.jsonl` is a hash chain. If a host has
one under `~/.homestead/keep/` and Nestor starts resolving to `~/.nestor/keep/`
instead, nothing is *moved* — a **second** chain begins. Both halves verify on
their own, and the history between them is simply gone, which is the one
failure this file exists to prevent. A refusal an operator reads at startup is
recoverable; a fork discovered at audit time is not.

Two ways out, both explicit:

```bash
export NESTOR_HOME="$HOMESTEAD_HOME"   # keep the chain where it is
# or, after moving the keep tree:
export NESTOR_HOME="$HOME/.nestor"
```

The session-start hook carries the same refusal as a `[nestor]` ask rather than
reporting on the repo tree, so a host in this state is told at boot instead of
at the first append.

## This repo vs a household host

| Context | DB / ledger |
|---------|-------------|
| **Developing Nestor** (`~/github/nestor`) | `./data/`, `docs/dogfood/` — unchanged |
| **Household host / embedding face** | Under `$NESTOR_HOME` via `bind_ledger()` + explicit store injection |

Fleet charter work (willow SOIL, Hanuman dispatches) uses **`WILLOW_HOME`**
under **`~/.willow`** — see [`roots-willow-and-homestead.md`](roots-willow-and-homestead.md)
and `docs/local-fleet.md`; that is orchestration, not the household record root.
