# Install

IDEAS.md §7.5 split "the first five minutes" into two halves: the wizard
(`nestor init`, `nestor/onboarding.py`) and the install story. The wizard was
addressed first; this is the other half — the actual commands, verified, not
described.

Every command on this page was run against a **clean, empty environment**
before it was written down. None is aspirational.

## The one-liner

Python 3.10+ (`requires-python` in `pyproject.toml`), no runtime dependencies.
The blessed install is [`pipx`](https://pypa.github.io/pipx/) — it puts the
`nestor` console script (the entry point `[project.scripts]` already declares
in `pyproject.toml`) into its own isolated environment instead of onto
whatever `pip` happens to be active:

```bash
pipx install nestor-meaning
```

`nestor-meaning` is the package's real, published name on PyPI — `pip install
nestor` (the shorter, unclaimed name) is **not** it; typing the bare name
gets "No matching distribution found," not this project. The import name is
unaffected: `import nestor` is what the package has always been called in
code, and stays that way regardless of what it is called on the index.

From a checkout instead of the index — same tool, same one line:

```bash
git clone https://github.com/rudi193-cmd/Nestor.git && cd Nestor
pipx install .
```

No `pipx` on the machine? Plain `pip` installs the same package the same way,
minus the isolated environment:

```bash
pip install nestor-meaning        # from PyPI
pip install .                     # from a checkout — same command either way
```

## What "verified" means here

Four installs were run into throwaway environments (2026-08-17), each ending
in a working `nestor --help`:

1. `pip install -e ".[dev]"` into a fresh venv at the repo root.
2. `pip install .` into `/tmp/nestor-usercheck` (a plain, non-editable
   install — the closest stand-in for what a user who is not developing
   Nestor actually runs).
3. `pipx install nestor-meaning` from the real PyPI index, into an empty
   pipx home.
4. `pipx install .` from this checkout, into a second empty pipx home.

The `pip install .` transcript (2):

```
$ python -m venv /tmp/nestor-usercheck
$ /tmp/nestor-usercheck/bin/pip install -q .
$ /tmp/nestor-usercheck/bin/nestor --help
usage: nestor [-h] [--db DB] [--ledger LEDGER] [--json]
              {ask,resolve,check,match,decision,export,db,import,ledger,calibrate,keys,rejections,stats,demo,init,ui,serve}
              ...
Nestor — meaning infrastructure. Has a human checked this?
```

The `pipx install nestor-meaning` transcript (3), showing the real PyPI
release resolving cleanly:

```
$ pipx install nestor-meaning
installing nestor-meaning...
  installed package nestor-meaning 0.4.0, installed using Python 3.11.15
  These apps are now available
    - nestor
    - nestor-ui
done! ✨ 🌟 ✨
```

**One environment-specific wrinkle, worth knowing generally, not just here:**
pipx's default backend is `uv`, and pipx refuses to proceed if the `uv` on
your `PATH` predates the version it needs (this sandbox's global `uv` was
`0.8.17`; pipx wanted `>=0.9.17`). Either upgrade `uv` (`uv self update`) or
add `--backend pip` to sidestep it — `pipx install nestor-meaning --backend
pip` was verified too, landing the identical `nestor-meaning 0.4.0`. This is
a `pipx`/`uv` compatibility detail, not anything specific to this package.

`nestor --version` does not exist yet — checked, not assumed; there is no
flag for it in `nestor/cli.py`. Do not run it expecting output.

## First run, right after install

```bash
nestor init                          # the guided wizard: ask, watch nothing verify yet, propose a draft
nestor demo                          # a second, already-sealed store, so `nestor ui` has something to show
nestor ui --db data/nestor-demo.db   # open it in a browser
```

Read `nestor init` for what it actually does before repeating a claim about
it: it walks a newcomer through asking a question, watching the matcher say
honestly that nothing has been verified yet, and proposing one decision as a
**draft** (`nestor/onboarding.py`, `DecisionMemory.propose`). It has no
`verifier=` or `status=` parameter anywhere on its call path —
`tests/test_onboarding.py::TestNeverSeals` pins that structurally — so no
amount of running it seals anything. Its own last line says so and names
where sealing actually happens:

> The seal is yours to set, by hand: open `nestor ui --db data/nestor.db`,
> sign in, and look at what you just proposed. If it still reads right, seal
> it there — nowhere else, because nowhere else is a person checking
> anything.

`nestor demo` is a separate, second store (`data/nestor-demo.db`) seeded with
*someone else's* already-sealed memory, so the UI has something sealed to
look at without waiting on a human to seal your own first draft. Both
commands write only under `./data/`, which is `.gitignore`d — running either
one leaves nothing for `git status` to notice.

## What this page does not solve

No Homebrew tap, no `curl | sh` one-liner. `pipx`/`pip` against the published
PyPI name (`nestor-meaning`), or against a checkout, is the whole install
story for now — concrete and cheap, per IDEAS.md §7.5, rather than promising
either of the other two ahead of building them.
