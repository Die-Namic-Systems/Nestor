# Homestead household paths

Nestor’s **household** layout follows the homestead seat on GitHub
([`rudi193-cmd/homestead`](https://github.com/rudi193-cmd/homestead) —
`homestead/keep/paths.py` on remote `main`). There is no separate `~/.nestor`
root: household data lives under **`~/.homestead`**.

For **`.willow` vs `.homestead`** vocabulary (fleet vs household, same machine),
see [`roots-willow-and-homestead.md`](roots-willow-and-homestead.md).

```text
~/.homestead/                 # or $HOMESTEAD_HOME
  keep/
    ledger.jsonl              # hash chain — bind before any Nestor append
  record/                     # homestead canonical record (homestead seat)
  logs/                       # homestead sealed log (I-22)
  drafts/
```

## In this package

```python
from nestor.homestead_paths import home, keep_dir, ledger_path, bind_ledger

bind_ledger()  # set_ledger_path(~/.homestead/keep/ledger.jsonl)
```

`bind_ledger()` is the product-side counterpart to homestead’s
``nestor_seam.bind()`` (draft in safe-app-store
`docs/drafts/nestor_seam.py`, destination `homestead/keep/nestor_seam.py`).

## Environment

| Variable | Meaning |
|----------|---------|
| `HOMESTEAD_HOME` | Override household root (tests, deliberate operator move) |

## This repo vs a homestead host

| Context | DB / ledger |
|---------|-------------|
| **Developing Nestor** (`~/github/nestor`) | `./data/`, `docs/dogfood/` — unchanged |
| **Homestead face / household** | Under `~/.homestead` via `bind_ledger()` + explicit store injection |

Fleet charter work (willow SOIL, Hanuman dispatches) uses **`WILLOW_HOME`**
under **`~/.willow`** — see [`roots-willow-and-homestead.md`](roots-willow-and-homestead.md)
and `docs/local-fleet.md`; that is orchestration, not the household record root.
