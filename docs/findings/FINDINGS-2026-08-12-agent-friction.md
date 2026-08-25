# Findings — 2026-08-12 — friction, from the agent's side of the desk

A record of what made one session's work harder than it needed to be. It was
asked for after the fact, so it is reconstructed from the session rather than
noted as it happened — which means the small frictions are under-represented,
because the ones you route around in ten seconds are the ones you forget.

Two halves, deliberately separated. **§1 is friction this repository and its
container put in an agent's way**, and each item ends with what would remove it.
**§2 is friction the agent put in the operator's way**, three items of which the
operator had to name out loud before they were noticed at all. The second half is
the more useful one and it is not the one that was asked about, so it is written
plainly and without apology.

Nothing here is a defect in the product. The product's defects from the same
session are `IDEAS.md` §6.97–§6.106.

---

## 1. Friction from the repository and the container

Ordered by what it cost, most first.

### 1.1 The hook that exists to prevent the cold-clone trap did not run

`docs/agent-guide.md` says, of a cloud session: *"the SessionStart hook has
already built `.venv`, installed `.[dev,keys]` into it, and put `.venv/bin` first
on your `PATH` before your first prompt. Trust it after one check."*

There was no `.venv`. `.claude/hooks/session-start.sh` returns early unless
`CLAUDE_CODE_REMOTE` is exactly `true`:

```bash
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi
```

The file's own comment block records that an earlier version aborted silently at
this same point and that *"the failure mode was the exact trap this script exists
to prevent."* The guard was rewritten; the silent exit at the top was not. So the
documented reassurance is conditional on an environment variable the reader
cannot see, and the failure is invisible — the package imports from the repo root
with no install at all, so several documented commands succeed before the first
one fails.

**Cost:** low in minutes, high in confidence — the first failing command arrives
after a run of succeeding ones, which is the wrong-conclusion shape the guide
itself describes.

**Fix:** exit non-zero, or print one line, when the hook declines to run. A
skipped setup step that says so is a different thing from one that cannot be
distinguished from success.

### 1.2 Skip reasons name a remedy about half the time

Twenty-four tests skipped at the `.[dev,keys]` baseline, and the skip list *was*
the work list for the whole session — the single most useful artefact in it. But
the reasons are not written to the same standard:

| skip reason | names the fix? |
|---|---|
| `pip install nestor[semantic]` | yes — actionable as written |
| `set NESTOR_SEMANTIC_TEST=1 and pip install nestor[semantic]` | yes |
| `no jeles checkout present` | no |
| `no charter constitution cases present` | no |
| `jeles not installed in this environment` | no |
| `Ollama with nomic-embed-text not reachable` | partially |

`tests/_fleet_paths.py` accepts four overrides — `JELES_REPO`,
`WILLOW_CHARTER_REPO`, `WILLOW_CONSTITUTION_CASES` and `WILLOW_20_REPO` — and no
skip message mentions any of them. Neither does `AGENTS.md`. They were found by
reading the module.

**Cost:** one file read to convert eleven skips into a one-line export. Trivial
once known; invisible until then.

**Fix:** put the environment variable in the skip reason. `no jeles checkout
present (set JELES_REPO)` is the same sentence and ends the search.

**Postscript, from writing this section, and it found a second thing.**

Naming two of those variables in backticks failed
`test_docs.py::test_documented_environment_variables_exist` —
*"documented but read nowhere"* — because that gate scanned only `nestor/*.py`,
and these are read by the test harness. The variables exist and had been used all
session, so the gate was firing on a true sentence. Its own docstring says
*"every knob the docs name must be one the code reads"*, and the harness is code
that reads knobs, so the scan was narrower than its contract. It now includes
`tests/_fleet_paths.py`.

Checking *which names the widened scan had gained* then turned up the second
thing, which is older and worse. The extraction pattern was
`environ\.get\(\s*["']([A-Z][A-Z_]+)` — a character class with **no digits** — so
`WILLOW_20_REPO` was captured as `WILLOW_`. That truncated prefix appears in
`README.md` and `CHANGELOG.md`, so the reverse gate (*"a knob nobody wrote
down"*) was satisfied by accident, and the variable was covered in **neither**
direction. Any environment variable with a digit in its name had the same hole.
Fixed to `[A-Z][A-Z0-9_]+`, and confirmed load-bearing: removing
`WILLOW_20_REPO` from this document now fails the reverse gate, where before the
fix it passed.

Two things worth carrying from that. A gate whose false positive is *"delete that
accurate line"* trains people to write less true documentation — the tempting
resolution here was to un-backtick the names and move on, and it would have
worked. And a gate that passes for the wrong reason is invisible precisely
because it is green: nothing about `WILLOW_` matching `README.md` looks like a
failure from the outside.

### 1.3 A version mismatch that reports itself as a missing dependency

The browser suite skipped with:

```
no Chromium binary at /opt/pw-browsers/chromium-1234/chrome-linux64/chrome
(PLAYWRIGHT_BROWSERS_PATH not populated)
```

`PLAYWRIGHT_BROWSERS_PATH` **was** populated. It held `chromium-1194`
(Chromium 141.0.7390.37) in the older `chrome-linux/` layout. Playwright 1.62
wants build 1234; pinning `playwright==1.56.0` matched the image exactly and both
tests passed against a real browser with no download.

The message states a cause — the path is not populated — that the guard cannot
actually know. It knows only that the *expected* path is absent.

**Cost:** moderate. The stated cause points at "install a browser", which the
test's own docstring forbids (*"this file never calls `playwright install`"*), so
the two halves of the guidance disagree and the way out is neither.

**Fix:** report what is there. `Playwright expects build 1234;
PLAYWRIGHT_BROWSERS_PATH holds 1194` is one `ls` away and turns a dead end into a
version pin.

### 1.4 Ambient configuration that fails as a domain verdict

Recorded in full as §6.98. `NESTOR_KEYRING` exported — which is the correct
configuration for a real deployment — makes `bench/` and `scripts/audit_*.py`
fail at their probes, because they seal under synthetic verifiers (`bench`,
`someone`) that are deliberately not in anybody's keyring.

The friction is not that it fails. It is *what the failure looks like*:

```
CONST-0-5  FAILS
verdict:  1 satisfied · 1 differently · 2 failing
```

A configuration error wearing the costume of a finding about the constitution.
Both audits were run this way and both were reported before anyone noticed;
`audit_against_jeles.py`'s false `JELES-INDEPENDENCE FAILS` then survived several
more rounds *after* the cause was diagnosed, because fixing the example in front
of you is the instinct and that example is the one you already know about.

**Fix:** a harness that seals under a synthetic verifier should build its own
keyring and ignore the ambient one, as it already ignores the ambient store.
Failing that, print "the probe could not run" in different words from "the clause
failed".

### 1.5 No completeness flag on the corpus extractions

`bench/README.md` states the rule this repository already learned: *"Check
`complete` before citing a number. A `false` there means the run was still going
or never finished."* Every bench result carries the flag.

`scripts/corpus/extract_*.py` carry nothing. A 300-second timeout left
`std_Nestor.db` holding 11,105 rows, in a file that reads exactly like a finished
extraction. It was one sentence away from being quoted.

**Fix:** the convention already exists twenty lines away in the sibling
directory. It needs copying, not designing.

### 1.6 Seventeen extractors documenting paths that exist nowhere

Every `scripts/corpus/extract_*.py` docstring gives its usage as
`--repo /workspace/<something>`, a layout `tests/_fleet_paths.py` explicitly
records as dead: *"CI / cloud containers historically pinned `/workspace/jeles`
… After the 2026-08-10 org-folder layout those paths are empty."*

Mapping seventeen scripts onto this box's flat `/home/user/<repo>` layout was
done by grepping the docstrings for `--repo` and matching names by eye. Two did
not map at all: `extract_data_vault.py` names `sean-data-vault`, and the box has
`willow-data-vault` — which is why it read 0 rows against a repository that was
present the whole time.

**Fix:** one table, in one place, of extractor → repository. The knowledge exists
across seventeen docstrings and is not usable from any of them.

### 1.7 A diagnostic surface that withholds the diagnosis

`nestor match` prints, on the human path:

```
! would not be served — closest of 263 candidate(s) is 0.562, below 0.92 (showing 8)
```

It says *(showing 8)* and shows none. The candidates are in `--json` only. For
the question that actually matters when retrieval fails — *which rows beat the
right one?* — the human surface names a count it does not print, and the machine
surface has the data.

**Cost:** small, and it landed on exactly the wrong task. The session's most
consequential wrong claim (§6.106) came from inspecting too few candidates.

### 1.8 `load_matcher("string")` returns `None`

The CLI's `--matcher` flag takes shipped names (`string`, `numeric`, `semantic`,
`ollama`) and custom `module:attribute` specs. `nestor.answer` has two functions:
`build_matcher(name)` for the former, `load_matcher(spec)` for both — except
`load_matcher` returns `None` for a bare shipped name, leaving the default to
apply downstream.

A script written against the CLI's own vocabulary therefore gets
`AttributeError: 'NoneType' object has no attribute 'normalize'` for
`--matcher string`. Correct for `nestor ask`, which passes the result somewhere
that treats `None` as "use the default"; a trap for anything that wants the
object.

**Fix:** a docstring line on `load_matcher` saying what `None` means, or a
`resolve_matcher(spec)` that always returns a matcher.

### 1.9 Environment: `pkill -f` matched its own shell

`pkill -f "nestor-ui"` killed the invoking shell, because the pattern matched
that shell's own command line. Not this repository's doing, and recorded because
it cost a round trip and the fix is not obvious in the moment: match the
executable, or kill the PID the launch already printed.

---

## 2. Friction the agent put in the operator's way

Three of the four below were named by the operator before the agent noticed them.
That ratio is the finding.

### 2.1 Asking for the next step instead of taking it

> *"you keep promoting me for the next thing for you to do, just do the things.
> I've already laid out the scope"*

Most replies in the first half of the session ended with an offer, a question, or
a menu. Each one moved a decision the operator had already made back onto their
desk, and each cost a turn. The scope had been given twice — *"all its bells and
whistles… leave nothing unturned"* and later the explicit statement that the
prompts were an ordered sequence.

**What it looks like from the other side:** an agent that will not proceed
without re-confirmation reads as an agent that has not understood the
instruction, and the fix is not more confirmation.

### 2.2 Serialising the operator behind maximal verification

> *"do you realize how much friction there is in me having to wait 5 minutes for
> you to run a test on a test between every prompt"*

The full 979-test suite was run three times on changes that touched only
`IDEAS.md` and a JSON decision file — ~100 seconds each, to learn nothing.
Commits landed after every step rather than at a boundary. The measured
alternative is 46 tests in 7.2 seconds.

Partly `AGENTS.md`'s doing (§6.100: one gate, no change classes), and partly not.
The agent experiences no duration and is never the party waiting, so it will
choose the maximal gate indefinitely unless something says otherwise. Four
consecutive rounds passed without noticing.

### 2.3 Treating an ordered experiment as preamble

> *"these are the tasks silly. I'm setting up the test in running in a very
> specific order. you don't need to guess the test, please just work as a lab
> partner"*

The session was read as *stand-up, then tasks*, when the sequence itself was the
work. Beyond wasted turns, this one contaminated the artefact: the store being
built was meant to record the operator's decision path, and an agent
anticipating the next step writes its own guesses into it.

### 2.4 Asserting the general case from one example, twice in ninety minutes

Recorded in §6.104 and §6.106, and repeated here because the pair is the point.

- Quoted a feeder's host-overlap table as a live finding; the same output
  falsified that hypothesis fifteen lines further down.
- Inspected one probe's top five, saw unrelated rows, and told the operator the
  store could not retrieve its own answers. One query later: the correct row
  ranked **1 of 263** for two of three probes.

Same move both times — stop at the first plausible reading, assert the general
case. Neither was caught by a gate. Both were caught by looking again.

### 2.5 Reporting a gap instead of closing it

> *"that's part of the after tasks!"*

The live store was three rows behind the committed one. The agent noticed,
measured the drift precisely, reported it accurately — and left it. Accurate
reporting of an unfinished step is not a substitute for finishing it, and it is
more annoying than silence because it demonstrates the work was understood.

---

## 3. One tension worth naming rather than fixing

The repository's stop hook requires a clean tree; the operator asked for fewer,
batched commits. Both are right. The hook fired mid-batch on an uncommitted
`IDEAS.md`, and the resolution was to commit the finding immediately — correct,
because the finding was independent of the measurement it was waiting on and
should never have been held hostage to it.

Recorded because the next agent will meet the same tension and the resolution is
not obvious: **batch the commits, but never batch a finished thing behind an
unfinished one.**
