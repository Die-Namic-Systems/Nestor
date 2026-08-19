# Nestor CLI probe — `ask` / `resolve` / `match` / `check`

DB: `data/nestor-demo.db` (9 pairs: 5 en→es, 2 entity→entity, 1 headcount→value,
1 q3-revenue→value; 8 sealed / 1 draft). 70 commands run. Findings below,
most-surprising first. No `status="sealed"` was ever set and no verifier
identity was ever confirmed by me — every command below is read-only
(ask/resolve/match/check never mutate the store).

## 1. `ask` and `match` silently default to the `en→es` domain — contradicts "any domain"

Confirmed in code (`nestor/cli.py`, `domain_args(sp, source="en", target="es")`):
every `ask` and `match` invocation that omits `--from/--to` is hard-scoped to
`en→es`, no matter what domains actually exist in the DB. `match`'s own
subtitle is *"the bare seam over any domain"*, yet without an explicit
`--from/--to` it can only ever see 5 of the 9 pairs.

Consequence — a **verified, exact, sealed** entry is invisible by default:

```
$ nestor --db data/nestor-demo.db ask "412"
! pending  —                                    # looks like "no answer exists"

$ nestor --db data/nestor-demo.db ask "412" --from headcount --to value --matcher numeric
✓ sealed  412   (verified by rita, similarity 1.0)   # it was there all along
```

Same for `match "Big Blue"` (entity domain) and `match "412" --matcher numeric`
(headcount domain): both report "0 candidates found in this domain" framed as
a normal near-miss ("closest of 5 candidates is 0.0/0.345"), with **no
indication that the candidate pool itself was the wrong domain**. `resolve`
has the same trap via `--domain` (see #8).

## 2. Using the default (string) matcher against a numeric domain silently corrupts the score

```
$ nestor --db data/nestor-demo.db ask "412" --from headcount --to value --json
```
gives `"state": "draft"`, `"confidence": 0.6`, `"verified": false`, yet inside
`matches[]` the *same* row shows `"similarity": 0.75`, `"status": "sealed"`,
`"servable": true` — an **exact string match ("412" == "412") scored 0.75**,
not 1.0, because StringMatcher (Jaccard/character-based, not numeric-aware)
is being applied to a numeric pair. Passing `--matcher numeric` on the same
input flips the result to `sealed`/`1.0`/`verified: true`. Nothing in the
non-JSON or JSON output warns that the matcher doesn't match the domain type;
the caller has to already know to override it.

## 3. A typo'd `--db` path is silently created as a fresh, empty, valid database

```
$ nestor --db /tmp/does-not-exist-nestor.db ask "Please hold."
! pending  —
$ ls -la /tmp/does-not-exist-nestor.db
-rw-r--r-- 1 root root 102400 ... /tmp/does-not-exist-nestor.db
```
No warning, no error, no "database not found" — SQLite just creates a
102,400-byte empty schema on first touch. A misspelled `--db data/nestor-deno.db`
would produce indistinguishable "pending, no match" output forever.

## 4. Invalid `--abs-tol` is accepted, silently no-ops, but the JSON echoes the bogus value anyway

```
$ nestor --db data/nestor-demo.db --json check "q3-revenue" "3.9M" --abs-tol -1
```
`tolerance_abs` (the value actually *applied*) comes back as `0.195` (the 5%
pct-based default — i.e. the negative abs-tol was ignored and pct_tol was
used instead), but `tolerance.abs_tol` in the same payload still echoes
`-1.0`, the value that was rejected. Anyone reading the JSON for an audit
trail would conclude a ±1 absolute tolerance was used; it wasn't. `--abs-tol 0`
behaves the same way (falls back to pct), so `0` and negative are
indistinguishable from "unset" — but the echoed field doesn't say that.

## 5. `check` compares raw numbers across incompatible unit conventions without warning

The sealed q3-revenue baseline is stored as text `"3.90M"` → parsed to the bare
number `3.9` (the "M" suffix is *stripped*, not converted — `3.9` means "3.9,
already in millions"). Feeding a same-magnitude but differently-formatted
observation blows up:

```
$ nestor --db data/nestor-demo.db check "q3-revenue" "3.9e6"
✗ flagged   baseline 3.9  observed 3,900,000.0  variation 3,899,996.1 (99999900.00%)  tolerance 195,000.0
```
`"3.9e6"` (i.e. literally 3.9 million) is numerically the *correct* figure,
but because the baseline's unit convention ("M" = already-in-millions,
stripped not multiplied) isn't documented or enforced, the checker reports a
100,000,000%-variance false "flagged". Anyone reconciling exports from a tool
that writes `3.9e6` instead of `3.90M` would get maximally-alarming false
positives.

## 6. Empty/whitespace input raises a raw, unhandled-looking exception — even under `--json`

```
$ nestor --db data/nestor-demo.db ask ""
ValueError: nothing to ask
$ nestor --db data/nestor-demo.db --json ask ""
ValueError: nothing to ask        # NOT valid JSON, exit code 2
```
Same for `resolve ""` → `ValueError: nothing to resolve`. Every other
"no result" case (no match found, no baseline, unknown domain) degrades
gracefully into a structured `pending`/`unsealed`/`no sealed baseline`
response; only the empty-string case breaks the `--json` contract and prints
a bare Python exception name to stdout/stderr.

## 7. Normalization silently strips punctuation, case, *and* emoji/unicode before comparing

```
$ nestor --db data/nestor-demo.db ask "Please hold. 🎉🎉"
✓ sealed  Espere, por favor.   (verified by rita, similarity 1.0)
$ nestor --db data/nestor-demo.db ask "PLEASE HOLD."       → similarity 1.0
$ nestor --db data/nestor-demo.db ask "Please hold!!!"      → similarity 1.0
```
Trailing emoji, full case changes, and swapped terminal punctuation are all
scored as a *perfect* 1.0 match against "Please hold." — the normalizer
appears to discard non-alphanumeric content wholesale (including emoji)
rather than just lowercasing/trimming whitespace. Not documented anywhere in
`--help`; could be surprising for anyone assuming punctuation-sensitive
matching in a domain where it matters (e.g. legal phrasing, "not guilty" vs
"not, guilty").

## 8. `resolve` has no `--matcher` flag — numeric/custom domains can never resolve correctly from the CLI

`resolve --help` only exposes `--domain`, no `--matcher`. So even knowing
about finding #2, there is no way to make `resolve` numeric-aware:

```
$ nestor --db data/nestor-demo.db resolve "412" --domain headcount
~ unsealed suggestion: —   (confidence 0.0 — nothing verified matched)
```
despite an exact sealed `"412"→"412"` pair existing. `resolve` is silently
unusable for any non-string-typed domain.

Related: `resolve --domain fictional_domain_xyz` (a domain that doesn't
exist in the DB at all) does not error — it returns the same
"unsealed suggestion: —" as a genuine near-miss, so a typo'd `--domain` is
indistinguishable from "nothing matched."

## 9. Sub-threshold matches still populate a "translation" in the output, marked only by `~`

```
$ nestor --db data/nestor-demo.db ask "$(printf 'Please hold.\nExtra line')"
~ draft  Espere, por favor.
```
JSON: `similarity: 0.667` (below the 0.92 serve threshold), `verified: false`,
but the `target`/`passage.target` field is still filled with
`"Espere, por favor."` — the same text a genuinely verified match would show.
Only the leading glyph (`✓` vs `~`) and the word "draft" distinguish a real
answer from a 67%-confidence guess; a scripted consumer of the plain-text
output that just great the second column would get an unverified string with
no signal.

## Positive / well-designed behaviors worth noting (not bugs)

- **Helpful misplaced-flag hint**: `nestor ask "..." --db data/nestor-demo.db`
  (global flag placed *after* the subcommand) doesn't just give argparse's
  generic "unrecognized arguments" — it appends
  `"global flags (--db, --ledger, --json) go BEFORE the subcommand — e.g. ..."`,
  a deliberate `_HintingParser` override.
- **Tolerance-ignored warning**: `match "Please hold." --abs-tol 5 --pct-tol 0.5`
  (tolerances passed to the string matcher, which doesn't use them) emits an
  explicit `RuntimeWarning: abs_tol/pct_tol are ignored by the 'string'
  matcher ... had no effect` — contrast this with the *silent* domain-scoping
  problem in #1; the codebase clearly knows how to warn when it wants to.
- **`calibrate` is epistemically honest about small corpora**: on this
  4-pair sample it explicitly flags its own recommendation as noise
  ("4 sampled pair(s) is below the ~30 this measure needs to mean anything
  ... Treat any recommendation here as noise").
- `--matcher semantic` / `--matcher ollama` fail with clear, actionable
  install/config instructions rather than opaque stack traces.
- `export` requires `--out` (a bare positional path is rejected with
  "unrecognized arguments") — consistent and documented via `--help`, just
  easy to trip on the first try.
- Negative numbers as `check` observed values work fine once you know to use
  `--` (`check "headcount" -- "-5"`) — argparse's normal negative-number-vs-flag
  ambiguity, not Nestor-specific, but worth remembering when scripting.
- `check`'s human-readable output leaks raw float noise for some inputs
  (`variation 0.010000000000000231 (0.26%)`) — cosmetic only, `--json`'s
  `variation_pct` is already rounded.

## Command log (representative subset of the 70 run)

| # | Command | Result |
|---|---|---|
| 1 | `ask "Please hold."` | ✓ sealed, similarity 1.0 |
| 2 | `ask "Please hld."` (typo) | ✓ sealed, similarity 0.952 |
| 3 | `ask ""` | `ValueError: nothing to ask`, exit 2 |
| 4 | `ask "Ship it."` (draft pair) | `~ draft  Envíalo.` |
| 6 | `ask` 500x-repeated string | `! pending` (no match) |
| 14 | `ask "412"` (no domain) | `! pending` — wrong default domain, see #1 |
| 16 | `ask "412" --from headcount --to value` | draft/0.6 conf, string-matcher miscoring, see #2 |
| 21 | `ask "412" --from headcount --to value --matcher numeric` | ✓ sealed, 1.0 |
| 27 | `resolve "412" --domain headcount` | unsealed, 0.0 conf — no `--matcher` flag, see #8 |
| 31 | `resolve "WINDY CITY"` (missing "the") | unsealed suggestion Chicago, 0.833 |
| 37 | `match "412" --matcher numeric` (no domain) | wrong pool (en→es), 0.0, see #1 |
| 39 | `match "412" --matcher numeric --from headcount --to value` | served, 1.0 |
| 41–50 | `check "q3-revenue" ...` variants (exact, ±, sci-notation, tolerances) | see #4, #5 |
| 51 | `check "q3-revenue" "not-a-number"` | clean structured refusal, no crash |
| 63 | `--db /tmp/does-not-exist-nestor.db ask ...` | silently creates empty DB, see #3 |
| 64 | `calibrate` | honest small-sample caveat |
| 69 | `match "1000" --matcher numeric --pct-tol 1.5` (150%) | served — no upper-bound validation on pct-tol, accepted as-is |
| 70 | `ask "..." --db data/nestor-demo.db` (flag after subcommand) | helpful hint, see positives |

Full export of the demo store used to build this map is at
`/tmp/claude-0/-home-user-Nestor/b2bb32f9-9208-5449-8125-3d3598b210a2/scratchpad/export.json`.
