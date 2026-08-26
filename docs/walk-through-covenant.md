# A ninety-second walk-through — the covenant, at the UI

*Written for the same reader as [`docs/policy-brief.md`](policy-brief.md): a
chief-of-staff, a policy analyst, a procurement officer. Six beats that end
at the moment a machine's proposal becomes a human's decision. The
engineer's version is [`demo/sixty_seconds.py`](../demo/sixty_seconds.py),
which asserts every claim it narrates against a live store and exits
non-zero if any of them ever stops holding.*

This is a doc, not a script. It exists because a walk-through of a UI is
what a policy reader clicks through, not what they run. Every literal
string below was captured against `nestor demo --seed policy` on the same
build a reader would install; a bench that re-runs the transcript is
[`tests/test_walk_through_covenant.py`](../tests/test_walk_through_covenant.py).

## Set up (three commands, from the brief)

```
pipx install nestor-meaning        # or: pip install nestor-meaning
nestor demo --seed policy          # a policy-shaped fixture
nestor ui --db data/nestor-demo.db # opens at http://127.0.0.1:8765
```

You now have twelve sealed rows (five translations, four organisation
aliases, two numeric baselines) and one draft translation. Every seal is
signed by `elena` — a fictional persona so a reviewer never mistakes the
demo signature for a real one.

## Beat 1 — ask something a human has sealed

In a second terminal:

```
$ nestor --db data/nestor-demo.db ask "The agreement enters into force on ratification." --from en --to es
✓ sealed  El acuerdo entra en vigor tras la ratificación.   (verified by elena, similarity 1.0)
```

The green `✓ sealed` is the shape of every verified serve: the target
string, the name of the person who signed it, and the similarity score
that got the row across the seal bar. `elena` is not the machine and not
the operator — she is a named human whose key signed this row.

## Beat 2 — ask the row a machine drafted but no human signed

```
$ nestor --db data/nestor-demo.db ask "The measure takes effect immediately." --from en --to es
~ draft  La medida entra en vigor de inmediato.
```

The amber `~ draft` is the covenant made visible. A machine did produce a
translation. The store keeps it. Nothing serves it as verified. The
sentence returns *draft* — not a lower-confidence answer buried in a
field nobody reads, but a state a caller has to explicitly accept.

**This is the row the ninety seconds turn on.** Every claim in the brief
about *refuse-to-serve-what-isn't-verified* is this row's behaviour.

## Beat 3 — ask a rewrite of a sealed sentence

```
$ nestor --db data/nestor-demo.db ask "The agreement is in force after ratification." --from en --to es
~ draft  El acuerdo entra en vigor tras la ratificación.
```

The English sentence means the same thing as beat 1's; the target string
Nestor found is beat 1's exact sealed answer. It still comes back as
`~ draft`, because the *input* did not match a sealed source string
closely enough to cross the seal bar. The machine's best guess is
offered — the operator can accept it in the UI with one click, which
records their name against it — but nothing serves as verified until
they do.

The engineer's demo names one further failure mode out loud: a swap of
*thirty days* for *sixty days* scores above the bar and serves anyway,
because a character-ratio matcher does not read.
See [`demo/sixty_seconds.py`](../demo/sixty_seconds.py) beat 5 for that
argument, and [`docs/probing-the-store.md`](probing-the-store.md) for
the sweep tool that measures where the bar belongs for a real corpus.

## Beat 4 — open the UI and seal the draft

The tab already open at `http://127.0.0.1:8765` shows a **Queue** with the
drafted rows. Click into *"The measure takes effect immediately."*, read
the Spanish, sign in as *elena* (the seed's verifier), and press
**seal**. That's the whole act. The store now holds a sealed row where a
moment ago there was a draft; the ledger has a new `seal` entry naming
`elena` and the time.

*No agent — including this walk-through's writer — can perform this
step. The tree's covenant refuses machine sealing: only a human at the
UI, signed against a keyring the ministry controls, can put a name on a
row. That is why beat 4 is the beat this tour is built around.*

## Beat 5 — ask again

```
$ nestor --db data/nestor-demo.db ask "The measure takes effect immediately." --from en --to es
✓ sealed  La medida entra en vigor de inmediato.   (verified by elena, similarity 1.0)
```

The amber `~ draft` from beat 2 has become the green `✓ sealed` of beat 1.
Same store, same command, one human action between them.

Right forever after, for anyone who asks — a person at the UI, the CLI,
or a model over MCP. **One human, one time.**

## Beat 6 — the ledger holds it, and one edit breaks the chain

```
$ nestor --db data/nestor-demo.db ledger verify
✓ intact — 24 entries
```

Every seal, every serve, every consultation from the six beats above is
in the ledger. Each entry carries the hash of the previous entry; editing
any one field in any one past entry breaks every link after it, and Nestor
refuses to seal or serve from a broken chain until a reviewer resolves
what changed and why.

The engineer's demo shows this beat by editing the trail and watching
the next seal be refused — [`demo/sixty_seconds.py`](../demo/sixty_seconds.py)
beats 7 and 8, and the tests that gate it,
[`tests/test_review_ledger.py`](../tests/test_review_ledger.py).

## What this walk-through claims and does not claim

- **Claims.** Every command above was run on the current build. Every
  literal string is what a reader will see when they run the same three
  install commands on the same version. The bench at
  [`tests/test_walk_through_covenant.py`](../tests/test_walk_through_covenant.py)
  re-runs beats 1, 2, 3, and 5 and asserts the strings exactly, so this
  file cannot drift out of the code without a test failing.
- **Does not claim.** That the seed's sentences are what any real
  ministry translates, that `elena` is a real person, or that the
  ninety-second tour is a substitute for the *audit* a ministry
  commissions before adoption. See §"What this brief does NOT claim" in
  [`docs/policy-brief.md`](policy-brief.md).

## Where to go from here

- **The brief:** [`docs/policy-brief.md`](policy-brief.md) — the same
  argument for a reader who has not yet installed anything.
- **The engineer's tour:** [`demo/sixty_seconds.py`](../demo/sixty_seconds.py)
  — the eight-beat version that asserts every claim it makes and
  exits non-zero if any of them stops holding. Runs in about a minute
  with `--fast`.
- **The default seed:** `nestor demo` without `--seed policy` — the same
  covenant demonstration on an office-register fixture (`"Good night."`,
  `"IBM"`) rather than a policy one. Same shape, different vocabulary.
- **The sovereign-deployment claim:**
  [`docs/sovereign-deployment.md`](sovereign-deployment.md) and the
  fourteen-assertion test file
  [`tests/test_no_network_by_default.py`](../tests/test_no_network_by_default.py).
