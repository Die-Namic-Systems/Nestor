# Nestor CLI — Edge-Case / Adversarial Probe

Date: 2026-08-19
Target: `nestor` CLI at `/home/user/Nestor` (venv-installed), tested against a
working copy of `data/nestor-demo.db` (never the original — original db/ledger
md5sums verified unchanged at the end of the run). All tests below ran through
`.venv/bin/nestor` from repo root.

Legend: 🟢 robust / handled well · 🟡 surprising but not dangerous · 🔴 fragile /
worth a fix.

---

## 1. SQL injection — 🟢 robust

```
nestor --db test.db ask "'; DROP TABLE pairs; --"
nestor --db test.db resolve "'; DROP TABLE pairs; --"
```
Both returned normal "no match" responses (`! pending —` / `~ unsealed
suggestion: —`). Confirmed via direct sqlite3 connection afterward that
`tm_pairs` still had all 9 rows — the injection string was never interpreted
as SQL. Queries are parameterized throughout; no evidence of string-built SQL
anywhere reachable from the CLI.

## 2. Extremely long input (5000 chars) — 🟢 robust

`ask`, `resolve`, `check`, `match` all accepted a 5000-character argument with
no crash, no visible slowdown, and sensible truncated output (`check` even
echoed the whole 5000-char label back in its "no sealed baseline" message,
which is harmless but could get spammy in a terminal — cosmetic only).

## 3. Null bytes / lone UTF-16 surrogates — 🟡 not testable at the CLI layer

Both `\x00` in an argv string and a lone surrogate (`\ud83d`) fail before the
process is even exec'd — Python's own `subprocess`/`exec` layer refuses them
(`ValueError: embedded null byte`, `UnicodeEncodeError: surrogates not
allowed`). This is a POSIX argv / UTF-8 constraint, not something Nestor's
code path can be exercised against from a shell. Not a Nestor finding, just
documenting that the obvious attack vector is closed by the OS before Nestor
ever sees it.

## 4. Unicode edge cases — 🟢 robust

RTL (Arabic+Hebrew mixed), ZWJ emoji sequences (👨‍👩‍👧‍👦), and combining-character
strings ("é" as e + combining acute) all round-tripped cleanly through `ask`
with no mangling, no crash, ordinary "pending" responses.

## 5. Concurrent access — 🟢 robust (genuinely good finding)

- 2 simultaneous `ask` writers on the same db+ledger: both completed cleanly.
- 10 simultaneous `ask` writers: all 10 completed, ledger grew from 18→28
  entries (exactly +10), `nestor ledger verify` reported `✓ intact` afterward.
- 20 processes each SIGKILL'd (`kill -9`) ~5ms after launch, repeatedly, on
  the same db+ledger: DB and ledger were left in a fully consistent state
  (`stats` and `ledger verify` both clean, entry count unchanged from before
  the storm — every killed write was cleanly all-or-nothing, no torn writes,
  no WAL corruption). SQLite's WAL mode + Nestor's connection handling is
  holding up well under this kind of abuse.

## 6. Empty database — 🟢 robust

Pointing `--db` at a path that doesn't exist yet auto-creates a valid empty
102400-byte SQLite file (from schema init). `stats`, `ask`, `resolve` on it
all give sane "nothing here" answers rather than errors.

## 7. Non-SQLite file as `--db` — 🔴 fragile (real finding)

```
echo "this is not a sqlite database" > notadb.txt
nestor --db notadb.txt stats
```
This dumps a **raw Python traceback** to stderr:
```
sqlite3.DatabaseError: file is not a database
  ...full traceback through sqlite_store.py:350 conn.execute("PRAGMA journal_mode=WAL")...
```
Same for `--db /dev/urandom` (`sqlite3.OperationalError: disk I/O error`, full
traceback) and for path-traversal targets like `/etc/passwd` (also "file is
not a database", full traceback).

This is inconsistent with the rest of the CLI, which is otherwise careful to
catch exceptions and print a single clean line (e.g. `ValueError: nothing to
ask`, `cannot read X: ...`). A non-SQLite `--db` is a completely foreseeable
user error (wrong path, wrong flag order, tab-completion mistake) and it's the
one case that currently leaks an internal stack trace including absolute
repository file paths. Worth wrapping `_store()`'s `init_db()` call in the CLI
entry point with the same clean-error convention used elsewhere.

## 8. Path traversal in `--db` — 🟡 harmless in practice, but note the side effect

`--db ../../../etc/passwd` and `--db /etc/passwd` both correctly fail (not a
SQLite file, same traceback issue as #7) — no data is read out of `/etc/passwd`
and nothing is written to it (SQLite refuses non-database files at PRAGMA
time before any write is attempted). So traversal itself is not exploitable,
it just surfaces the same fragile-error UX as #7.

**However**, a related and more actionable finding: if `--db` points at a
path in a directory that doesn't exist yet, Nestor **silently creates the
directory** (verified: `--db /nonexistent-dir-xyz/db.sqlite` created
`/nonexistent-dir-xyz/` and a fresh empty db in it, no prompt, no warning).
Combined with no path validation, an operator who fat-fingers `--db` gets a
new directory + database created wherever the process has write permission,
with zero feedback that this happened until they go looking. Not a security
hole (no privilege escalation — it's the invoking user's own filesystem
permissions), but a footgun for scripted/automated invocations with a typo'd
path.

## 9. Every command with no arguments — 🟢 robust, good UX

`nestor` (bare), `ask`, `resolve`, `check`, `match`, `import`, `decision`,
`evidence`, `keys` with missing required args all produce argparse's standard
`usage: ...` + `error: the following arguments are required: X` on stderr
with exit code 2. Clear and actionable. `export`, `db`, `calibrate`,
`rejections` have no required args and just run with sensible defaults
(export dumps the whole store to stdout as JSON; `db` with no subcommand
checkpoints the default db; `calibrate`/`rejections` report "nothing yet").

Note: running any subcommand **without `--db`** silently operates against the
default `data/nestor.db` / `data/ledger.jsonl` (relative to cwd), creating
them if absent. This is documented in `--help` (`default: data/nestor.db`)
but easy to trigger by accident when testing — I did this myself twice and
had to clean up stray `data/nestor.db` / `data/ledger.jsonl` files it created
in the repo (gitignored, so no repo pollution risk, but real files on disk
outside version control).

## 10. `ask` with empty / whitespace / structural inputs — 🟢 robust

| Input | Result |
|---|---|
| `''` | `ValueError: nothing to ask`, exit 2 |
| `' '`, `'   '` | same — whitespace-only is correctly treated as empty |
| `$'\n'`, `$'\t'` | same — newline/tab-only also treated as empty |
| `'12345'` | normal `! pending` |
| `'<script>alert(1)</script>'` | normal `! pending` — no HTML/markup interpretation anywhere in CLI output (plain text throughout) |
| `'**bold** _italic_ [link](...)'` | normal `! pending` — treated as literal text, not rendered |

`check '' ''`, `check 'foo' ''` both correctly error
(`ValueError: a check needs a label and an observed value`). `check 'foo'
'not-a-number'` degrades gracefully (`no sealed baseline for 'foo'`) rather
than crashing on the unparseable number, because label-lookup happens first.

All of these single-line `ValueError` messages go to stderr with **no Python
traceback** — confirmed explicitly by isolating stderr — which is the correct
contrast case to finding #7 (only the DB-open path leaks tracebacks).

## 11. Resource limits / large export — 🟡 architectural note, not exercised at scale

Reading `cmd_export` in `nestor/cli.py`: it builds the *entire* bundle dict in
memory and does `json.dumps(bundle, indent=2, ...)` as one string before
either printing it or writing it to a file — **it does not stream**. For the
9-row demo db this is instant and irrelevant, but for a very large production
store (large `pairs`/`rejections`/ledger tables) this means export peaks at
roughly 2-3x the serialized size in resident memory (Python dict + JSON
string + write buffer) rather than bounded memory. Not a bug at demo scale,
but worth flagging as a scaling limit if `export` is ever pointed at a
multi-GB store.

## 12. Mismatched `--db` / `--ledger` — 🟡 important behavioral note (not a bug, but a footgun)

`--db` and `--ledger` are **fully independent flags** — nothing ties a
ledger file to "the ledger that belongs to this db". Concretely:

- `--db valid.db --ledger /nonexistent-dir/ledger.jsonl` → works fine,
  reports `ledger: ✓ no ledger yet` (auto-vivifies).
- `--db /nonexistent-dir/db.sqlite --ledger valid.ledger.jsonl` → works fine,
  0 pairs (fresh db) but ledger shows the *other* db's 16 entries — i.e. you
  get a real stats readout that mixes an empty db with an unrelated ledger's
  history, with no warning that they're mismatched.
- `--db valid.db --ledger notadb.txt` (ledger pointed at a non-JSONL file) →
  handled gracefully: `ledger: ✗ line 1: not valid JSON (...)` — a clean
  one-line error, no crash, no traceback. (Good contrast with finding #7 —
  the ledger-open path is defensive in a way the db-open path isn't.)
- Forgetting `--ledger` entirely while using a non-default `--db` (very easy
  to do, since only `--db` "feels" required) silently writes every ledger
  entry into the *default* `data/ledger.jsonl`, interleaving audit history
  from whatever unrelated db you're pointed at with previous runs' entries.
  I hit this myself during testing (see #9) — plausible foot-gun for real
  users running scripted per-db workflows without pairing the two flags.

## 13. Signal handling — 🟢 robust (see full detail under #5)

20x rapid SIGKILL mid-`ask` on a shared db+ledger left both files fully
intact and consistent (`ledger verify` clean, entry count exactly matching
pre-storm state — no entry was left half-written). Nestor/SQLite's
write path appears to be properly atomic here.

## 14. Malformed / hostile `--matcher module:attribute` — 🟡 intentional, well-documented, worth flagging anyway

`--matcher` supports a `module:attribute` spec that does a real
`importlib.import_module` + `getattr` + **call** of arbitrary code:

```
nestor ask 'test' --matcher 'os:system'
  → ValueError: calling os:system to build a matcher raised TypeError: system() missing required argument 'command'
nestor ask 'test' --matcher 'subprocess:run'
  → ValueError: calling subprocess:run to build a matcher raised TypeError: ... missing 1 required positional argument: 'args'
```

This **is** documented, deliberately, in the docstring of
`nestor/answer.py:load_matcher` — it explicitly says "This imports and runs
the module named... the same authority the command line already has... not a
new privilege... the spec is a flag and never a value read from a request, a
bundle or a stored row." So this is an acknowledged, scoped design decision,
not an oversight. Confirmed it fails cleanly (no traceback) on bad specs:
nonexistent module, relative-import-style bogus spec, etc. all produce clean
single-line `ValueError`s. **Flagging for the record only**: any future
wrapper (web UI, MCP tool surface, API) that ever accepts `--matcher` from an
untrusted caller rather than an operator's own CLI flag would turn this into
real RCE — the code comment already anticipates and warns against exactly
that misuse, so this is a "keep guarding this boundary" note, not a new bug.

## 15. Numeric edge cases in `check` — 🟢 mostly robust, one cosmetic wart

- `check headcount NaN` / `check headcount Infinity` → correctly **rejected**
  ("no number could be read from 'NaN'") rather than accepted via a bare
  `float()` cast — this is a deliberate, good safety choice, since
  `float("nan")`/`float("inf")` both parse fine in Python and would otherwise
  poison every downstream tolerance calculation.
- `check headcount -0` → accepted, correctly flagged as 100% variation from
  baseline 412.
- `check headcount 999999999999999999999999999999` (10^30) → accepted,
  correctly flagged, computed a valid (if enormous) percentage.
- 🟡 `check headcount 1e308` → accepted, but the printed variation percentage
  is a **~300-digit number** rendered in full (`... 090152288796724942938658
  840554909460500532014780811042619392.00%`). Not a crash, just a UX wart —
  extreme but finite floats aren't clamped/formatted for display.
- Negative `--abs-tol -5` and negative `--pct-tol -0.5` are both accepted by
  argparse (no validation) but effectively ignored / clamped to 0 rather than
  producing a nonsensical "negative tolerance" result — check still fails
  safe (flags rather than silently passing everything).

## 16. Malformed import bundles — 🟢 robust

- Nonexistent file → clean `cannot read X: [Errno 2] No such file or
  directory`, exit 2.
- Non-JSON file (`echo 'not json' > x.json`) → clean `cannot read X:
  Expecting value: line 1 column 1 (char 0)`, exit 2.
- Valid JSON but empty object `{}` → clean `not a usable bundle: unsupported
  bundle version None (this build reads 1, 2, 3 and writes 3)`, exit 2.

No tracebacks anywhere on this path — good contrast with finding #7.

## 17. `db checkpoint --out` collision handling — 🟢 robust

- `--out` pointed at the *same file* as `--db` → refused cleanly:
  `refusing to overwrite <path> (pass --force)`, exit 2 (did not clobber the
  live db).
- `--out` pointed at an existing unrelated file → same clean refusal.
- `--force` → proceeds and overwrites as documented, writes both the `.db`
  and the paired `.ledger.jsonl` sidecar.

## 18. Argparse-level validation — 🟢 robust

Invalid `--engine` choice, invalid subcommand names (`nestor bogus-command`,
`nestor keys bogus-subcommand`), and non-numeric `--abs-tol` all get
standard argparse `usage:` + `error:` messages with the valid choices listed
inline — no custom validation code needed, and it's about as helpful as CLI
error messages get.

---

## Summary

**Most robust areas:** SQL-injection resistance (real parameterized
queries), concurrent-writer safety (SIGKILL storm test), Unicode handling,
empty/whitespace input validation, and the general "single clean stderr
line, no traceback" convention used almost everywhere.

**The one real fragility:** opening a `--db` that isn't a valid SQLite file
(wrong path, `/dev/urandom`, a text file, `/etc/passwd`) is the sole place
that leaks a full Python traceback instead of following the CLI's own clean-
error convention (see #7). This is an easy, low-risk fix: wrap the
`store.init_db()` call in `_store()`/`cmd_*` with a `try/except
sqlite3.DatabaseError` that prints one line and exits like everywhere else.

**Worth a documentation/UX pass, not a bug fix:** `--db` and `--ledger` being
fully independent (#12) is defensible as a design choice (lets you replay one
db's history against another, or export without a ledger) but is an easy
footgun for anyone who assumes pairing them is automatic — a one-line note in
`--help` or a startup warning when the ledger's most recent entries don't
reference the current db's own pair IDs could help.

**Confirmed non-issues:** the `--matcher module:attribute` code-execution
surface (#14) is already deliberately scoped and documented as
operator-only authority, not attacker-reachable input, and the null-
byte/lone-surrogate cases (#3) are closed by the OS before Nestor's code
ever runs.

No test in this pass corrupted the original `data/nestor-demo.db` /
`nestor-demo.ledger.jsonl` — md5sums verified unchanged before and after.
All work was done against throwaway copies in the scratchpad directory.
