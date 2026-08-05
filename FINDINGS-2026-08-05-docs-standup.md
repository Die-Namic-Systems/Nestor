# Findings — 2026-08-05 — standing Nestor up from the documentation alone

The exercise: treat the README as the only spec, execute it top to bottom as a
fresh operator would, and record every place where the documentation alone is
not enough — with a specific eye on **where a small model would fail**. A small
model following docs does not introspect signatures, does not read source when
a snippet errors, takes table rows as exhaustive, and copies commands verbatim.
Every gap below is scored against that reader.

Environment: Python 3.11.15, fresh venv, `pip install -e ".[dev]"`, no
`NESTOR_SEAL_KEY` unless stated. Everything was actually run; nothing below is
read-only speculation.

## What stood up exactly as documented

The docs are unusually honest, and most of the walkthrough reproduced
**byte-for-byte**. For the record, all of the following worked from the README
alone, with output matching the documented output:

- `pip install -e ".[dev]"` and `pytest -q` — 445 passed, 8 skipped, ~20s.
- `python demo/sixty_seconds.py --fast` — every beat asserts, exit 0.
- The `demo.py` and `entities.py` quick-start snippets — output matches the
  README verbatim, including the `RuntimeWarning` the README itself predicts.
- `nestor export` / `nestor import` — dry run by default, report format as shown.
- `nestor ledger head` + `nestor ledger verify --expect-head` — works as shown.
- `nestor keys add` / `keys list`; sealing as an unregistered name with
  `NESTOR_KEYRING` in force raises `UnknownVerifierError` whose message says
  exactly what to do next.
- `NESTOR_REQUIRE_SEAL_KEY=1` fails closed with `SigningRequiredError`.
- `Reconciler`: a second baseline for a label from a different verifier raises
  `ConflictingSealError`, as §"A label has exactly one baseline" promises.
- `python -m nestor.ui --db data/nestor.db` — binds loopback, serves.
- `nestor serve` over stdio — the tool list is exactly the seven documented
  tools, and calling `nestor_seal` returns the refusal text **verbatim** as
  printed in the README.

Two properties of this repo actively protect a small model and deserve naming:
**exit codes carry the answer** (a model can branch on `$?` instead of parsing
prose), and **error messages teach** (`UnknownVerifierError` and the MCP
refusal both contain the remedy). A model that hits a wall here is told which
wall and where the door is. The gaps below are almost all *omissions* — places
where the docs are silent and the reader must infer — not places where the docs
lie.

---

## Gaps, in descending order of how hard a small model hits them

### 1. The quick-start snippets silently write `data/ledger.jsonl` into the cwd — even with `SqliteStore(":memory:")`

Run the README's `demo.py` from any directory and a `data/` directory appears
there, holding the ledger. The store is in-memory; the ledger is not, and the
Quick start never says so. The default path is documented — but five sections
later, under "The ledger".

**Where a small model fails:** it reads `":memory:"` and concludes the run is
ephemeral. Then either (a) it runs snippets from varying cwds and each gets a
*different* ledger, so `nestor stats` / `nestor ledger verify` report counts
that don't match what it just did, or (b) it "cleans up" a `data/` directory it
believes it created by accident — deleting the audit trail. A model cannot
recover from (a) without already understanding the ledger-path default, which
is exactly what it didn't read yet.

**Fix:** one sentence in Quick start: *"Both snippets also append to a ledger
at `./data/ledger.jsonl` — the store can be in-memory, the audit trail never
is. See The ledger for the path."*

### 2. The CLI section's first example cannot succeed from the documented state, and the CLI's store is never located

```bash
nestor ask "Good evening."               # ✓ sealed  Buenas noches.  (verified by rita)
```

Followed linearly from the README, this returns `! pending  —` and exit 1: the
snippets that sealed anything used `SqliteStore(":memory:")`, which died with
the process, and no documented step seeds the CLI's actual store. Which store
*is* the CLI's? The README's CLI section never says; `--db` (default
`data/nestor.db`) appears only in `--help`.

**Where a small model fails:** two ways, both observed patterns. First, it
diagnoses the mismatch between documented and actual output as a broken
install and starts "fixing" — reinstalling, re-running, or worse, finding some
way to force the expected output. Second and subtler: it never forms the model
that the *library global store* (`storage.set_store(...)`) and the *CLI
process's store* are different things, because nothing in the docs draws that
line. The comment `(verified by rita)` compounds it — rita is sealed nowhere in
any runnable documented step before this line, so the example's precondition is
unconstructible from the docs.

**Fix:** open the CLI section with the store: *"The CLI reads `--db` (default
`./data/nestor.db`); the quick-start snippets above wrote to `:memory:`, so
seed a file-backed store first."* — plus one runnable seeding line.

### 3. The import table has no row for the unsigned case — and that row is the trust-laundering one

The import table's first two rows say: signature verifies here → sealed;
signature does not verify → demoted to draft. Measured behavior with a bundle
exported under no key (`"signing": {"enabled": false}`):

| importing instance | result |
|---|---|
| no `NESTOR_SEAL_KEY` | **imported sealed** — 1 sealed, 0 demoted |
| `NESTOR_SEAL_KEY` set | demoted to draft, as the table predicts |

The first row is *consistent* with the seal-signature section ("without the
variable Nestor warns and trusts stored status") — but the import section
explicitly frames a bundle as "exactly the claim a seal signature exists to
distrust", then presents a table implying the serve path's rule always
applies. Unsigned-to-unsigned, a file claiming `sealed` **is** believed.

**Where a small model fails:** asked "will this bundle be demoted?", it reads
the table, pattern-matches "no valid signature → demoted", and answers wrong.
Worse: a model automating a migration between two keyless instances will move
"sealed" rows wholesale and *report the trust as preserved*, citing this very
section as evidence of the safety property. The table's framing gives it
confidence precisely where it should have none. This is a documentation gap
with the same shape as Nestor#2 — status trusted because nothing was there to
check it — but here the docs actively suggest otherwise.

**Fix:** add the row: *"sealed, importing instance has no key configured —
imported sealed on stored status alone, exactly as the serve path would; set
`NESTOR_REQUIRE_SEAL_KEY=1` to refuse instead"* (and verify that refusal
covers import).

### 4. `pip install nestor[semantic]` does not work in the only documented setup

The Matcher section says `pip install nestor[semantic]` twice. The only
documented installation is from a clone (`pip install -e ".[dev]"`); there is
no `nestor` distribution reachable on the index (`pip index versions nestor` →
no matching distribution). The working incantation is `pip install -e
".[semantic]"`, which appears nowhere.

**Where a small model fails:** it copies the command verbatim, gets a
resolution error, and then improvises: `pip install fastembed` directly
(diverging from the tested extra's version floor, `fastembed>=0.4`), or —
the genuinely bad branch — installs whatever similarly-named package the index
*does* offer. A human recognizes the editable-install context shift; a small
model treats each command as independent.

**Fix:** use the `-e ".[semantic]"` form everywhere the package is documented
as installed from source, or note both forms once.

### 5. The rejection snippet references a variable that does not exist and a shape that is documented nowhere

```python
memory.reject_match("the penalty under section 900026", "en", "es",
                    pair_id=hit["pair"]["id"], ...)
```

`hit` is undefined in the snippet, and the shape — `lookup()` and
`best_sealed()` return `{"pair": {...}, "similarity": float}` — is stated
nowhere in the README. It is only discoverable by introspection.

**Where a small model fails:** `NameError` first. Then it guesses: `hit =
memory.lookup(...)` (a list, so `hit["pair"]` is a `TypeError`), then maybe
`hit[0]["id"]` (`KeyError`). Three failures deep, a small model is as likely
to pass a *wrong but present* id — a segment id, a document id — as the right
one. `reject_match` records a human's "no" against a specific pair; recording
it against the wrong pair is a silent misfire in the one subsystem whose whole
point is that decisions stick.

**Fix:** make the snippet self-contained: `hit = memory.best_sealed(query,
"en", "es")` on the line above, and one sentence stating the hit shape.

### 6. Tier 3 — the seal, the central human act — has no documented call signature

`graduate_segment(...)` and `reject_segment(...)` are named repeatedly; their
signatures appear nowhere. Nor does `translate_text`'s — it surfaces exactly
once, in the Injected-storage section, with no import path and an unpacked
`doc, passages = ...` return that is never explained. The complete
draft → queue → graduate → serve loop — the loop the product *is* — cannot be
assembled from the README without introspection.

Actual signatures, for the record:

```python
cascade.translate_text(text, target_lang, source_lang="", engine_name="auto",
                       title="", store=None) -> tuple[dict, list[Passage]]
cascade.graduate_segment(segment_id, verifier="", weight=1.0, store=None)
cascade.reject_segment(segment_id, verifier="", reason="", store=None)
```

**Where a small model fails:** it invents keyword arguments.
`graduate_segment(segment_id, target_text=...)`, `verifier=` on
`translate_text`, a `lang` kwarg — plausible names in this codebase's idiom,
all wrong. Signature invention is *the* canonical small-model failure, and
here it sits on the tier where a human's verification is recorded. A wrong
`weight`, a defaulted-empty `verifier` — the call succeeds and the record is
subtly poorer (`verifier=""` is accepted keyring-less), which is worse than an
exception.

**Fix:** a short "the review loop, end to end" code block — translate, list
the queue, graduate one segment, reject another — somewhere between "The
recipes" and "Rejection". The UI section demonstrates this loop with buttons;
the library never demonstrates it at all.

### 7. `nestor calibrate` recommends a threshold from a memory too small to mean anything, without saying so

Against a 1-pair memory: `threshold 0.80 — 0 collisions — 0.00% ←recommended`.
Fewer pairs ⇒ fewer collisions ⇒ every cutoff meets any target ⇒ the
*lowest* swept threshold is recommended. The README does say the measure is a
lower bound and that moving the dial belongs to a person — but the command's
output recommends, in a machine-parseable line, with no minimum-corpus caveat,
and the README gives no guidance on how much memory makes the number stable.

**Where a small model fails:** an agent automating setup runs calibrate early
— when the memory is smallest and the recommendation cheapest — reads
`←recommended 0.80`, and sets the serving threshold 0.12 below default with
measured-looking justification. Every later near-miss then serves as
verified. The dangerous part is that the output *format* signals authority;
a small model weights format heavily.

**Fix:** the command should print (and docs should state) a floor — *"n
sealed pairs is below what this measure stabilizes on; the recommendation is
not meaningful"* — the same honesty `stats` and the queue-less store already
practice.

### 8. Smaller drifts, batched

- **The `keys` extra is invisible.** `pyproject.toml` declares
  `keys = ["cryptography>=41"]`; the README's extras list stops at `dev` /
  `cloud` / `semantic`, and the signing section calls asymmetric keys "the
  follow-on". Either the extra is real and undocumented, or it's declared
  ahead of its implementation — a model asked to "enable the cryptography
  support" has one true sentence to find and it isn't in the docs.

- **The top-level README doesn't cross-reference the bench's runtime.** It
  suggests `python bench/bench_accuracy.py --probes 400`; only
  `bench/README.md` says the full sweep takes ~10 minutes, checkpoints after
  every row, and supports `--resume`. A 20-probe run here exceeded 400s
  before being killed. A small model (or a CI timeout) kills it and — without
  the `complete: false` convention in view — may cite a prefix as a result.
  One clause in the main README ("takes minutes, checkpoints, resumable —
  see bench/README.md") closes it.

- **Project-layout drift.** `docs/local-fleet.md`, `docs/decision-memory.md`,
  `TODO.md`, `FINDINGS-2026-07-30.md`, and `bench/serve_ui.py` / `bench/ui`
  exist but are absent from the layout tree (the layout lists other root
  files, so absence reads as nonexistence). Trivial for a human; a small
  model told "read the fleet docs" greps the layout, finds only
  `fleet-integration-map.md`, and stops.

- **Warnings interleave with parseable output.** The `NESTOR_SEAL_KEY`
  RuntimeWarning prints on stderr mid-stream; the documented remedy for
  scripting (`>/dev/null` on stdout) is fine, but a model piping *stderr*
  away to "clean up" output also silences the one warning the README calls
  load-bearing. `--json` mode plus a documented "warnings go to stderr,
  exactly once" contract would let a model keep both.

## Addendum — the same exercise, run by two other models

The same prompt (minus the small-model framing) was given to two other
agents; their reports landed as `claude/documentation-gaps-gtjpbx`
(`DOCUMENTATION_GAPS.md`) and `claude/documentation-gaps-zn6quz`
(`docs/documentation-gaps.md`). Every disputed claim below was re-verified by
execution before being called true or false. The comparison is itself data:
this document *predicted* failure modes; the branches *exhibit* them.

### `gtjpbx` — do not merge without correction

Its single **HIGH**-priority finding — "the Python code example in README …
is incorrect and will fail immediately", claiming a `TypeError`, that
`translate_segment` returns a dict, and that `.mark`/`.state`/`.target` do
not exist — is **false**. The snippet runs verbatim, exits 0, and reproduces
the README's output character-for-character (re-verified today);
`translate_segment(text, source_lang, target_lang, engine=None, …) ->
Passage`, and `Passage` has exactly those attributes. The document shows no
program output anywhere — the failure was inferred from reading, not
observed, then ranked above every real finding. Two more of its gaps claim
the README lacks things it prominently contains: the keyring section
("Who verified it — per-verifier keys", with the exact `nestor keys add` /
`NESTOR_KEYRING` commands the report says exist "only in QUESTIONS.md §6"),
and the `mcpServers` JSON block (README line ~709). Its real contributions —
no seal-key generation guidance, sparse subcommand `--help` — are also in
`zn6quz`, with evidence.

This is §"where a small model fails" enacted: an API failure invented from
signature-reading rather than execution, format (a severity table) lending
authority to the one claim that was never tested, and "missing from docs"
asserted without grepping the docs.

### `zn6quz` — three real gaps this document missed

The report is empirical, shows its run, and separates "worked as documented"
from "gap". Confirmed here by execution, all new relative to the sections
above:

- **`ruff` and `bandit` are not in the `[dev]` extra** — the Development
  section's commands fail after the documented install (`dev = ["pytest"]`
  only). Verified: neither is present in this venv.
- **`--db` must precede the subcommand** — `nestor ask "…" --db mydb.db` is
  an argparse error; only `nestor --db mydb.db ask "…"` works. The README
  never shows `--db` at all, so the first attempt a reader makes is the
  failing form.
- **`nestor calibrate` recommends a threshold nothing documented can
  apply.** No env var, no CLI flag, no README mention of the module global
  or the per-call `seal_threshold=` kwarg. The calibration loop is
  documented end-to-end except its last step. (Compounds §7 above: the
  recommendation is both too confident on a small corpus *and* has no
  documented way to be applied on any corpus.)

Two of its claims did not survive verification: `bench/README.md` *does*
state the ~10-minute runtime and `--resume` (its §10 says the runtime is
addressed nowhere), and the `[cloud]`/`ANTHROPIC_API_KEY` silent fallback
its §8 reports is documented, though tersely, in "Other injected seams"
("without credentials or the `anthropic` package, Nestor uses the …
offline engine") — the fair residue is that the note sits far from the
`--engine` flag it governs.

### What no other report found

The three highest-consequence items in this document appear in neither
branch: the unsigned-bundle import row (§3, trust laundering with doc-backed
false confidence), the cwd-relative ledger side effect (§1), and the
rejection snippet's undefined `hit` (§5). All three require *running* the
docs adversarially rather than checking that the happy path works.

## The shape of the whole

Standing Nestor up from its documentation **works** — rare, and worth saying
plainly. Every documented command ran; every documented output matched; every
documented refusal refused with the documented message. The failures a small
model would actually hit cluster in the connective tissue the docs leave to
inference: which process holds which store (§2), what a snippet's undefined
variable was (§5), what signature a named function has (§6), and which table
row was omitted because it seemed to follow (§3). None of these require new
mechanisms — each is a sentence or a code block the README already knows how
to write, in the same voice that wrote "a decision that cannot be recorded is
not made."
