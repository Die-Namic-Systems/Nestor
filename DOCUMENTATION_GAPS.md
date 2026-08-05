# Documentation Gaps

Based on attempting to set up and use Nestor from just the documentation, this document identifies gaps between what the documentation says and what the code requires.

## 1. Python API Example in README (HIGH PRIORITY)

**Gap:** The Python code example in README (Quick start section, after demo.py) is incorrect and will fail immediately.

### What the README shows:
```python
from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore

storage.set_store(SqliteStore(":memory:"))

# 1. Nothing is known yet.
p = cascade.translate_segment("Good evening.", "en", "es")
print(p.mark, p.state, repr(p.target))
```

### Issues:
1. `cascade.translate_segment()` doesn't accept `engine_name` parameter
2. It requires an `engine` object (or `None`), not a string name
3. The return type is a `Passage` dict, not an object with `.mark`, `.state`, `.target` attributes
4. Without showing how to get/create an engine, the example fails immediately

### Correct approach:
```python
from nestor.answer import ask
from nestor import storage
from nestor.sqlite_store import SqliteStore

storage.set_store(SqliteStore(":memory:"))

# Using the correct high-level API
result = ask(storage.get_store(), "Good evening.", "en", "es", engine_name="offline")
p = result["passage"]
print(p["mark"], p["state"], repr(p["target"]))
```

### Why it matters:
Users following the README example will immediately get a `TypeError` and may assume the library is broken or incomplete.

---

## 2. Storage Setup Not Fully Explained (MEDIUM PRIORITY)

**Gap:** Documentation doesn't clearly explain storage initialization and options.

### Missing guidance on:
- What happens if you forget to call `storage.set_store()` (raises clear RuntimeError, but not shown in docs)
- Whether you can pass `store=` to individual calls instead (you can, but not documented)
- Differences between `:memory:` (in-process) and file-backed stores
- WAL mode implications for concurrent access and backups

### Example of confusion:
The README mentions WAL mode and backup concerns but doesn't show:
```bash
# Recommended backup for live database
sqlite3 nestor.db "VACUUM INTO nestor.db.backup"

# Why plain copy doesn't work:
cp nestor.db nestor.db.backup  # Incomplete with WAL files
```

---

## 3. Ledger Configuration Unclear (MEDIUM PRIORITY)

**Gap:** Ledger initialization and configuration is mentioned but not clearly explained.

### Missing:
- Default ledger path if `NESTOR_LEDGER` environment variable is not set
- How to verify ledger integrity when first connecting to an existing database
- What to do if the ledger file is missing but the database exists
- Recovery procedures for broken hash chains

### Unclear scenarios:
```bash
# What happens with no explicit setup?
nestor ask "phrase"  # Uses data/ledger.jsonl by default — not stated

# How to use a custom path?
NESTOR_LEDGER=/path/to/ledger.jsonl nestor ask "phrase"  # Works, but not shown
```

---

## 4. Matcher Configuration and Usage (MEDIUM PRIORITY)

**Gap:** Matcher seam is well-documented architecturally but practical usage is sparse.

### Missing:
- How to set a different matcher as the default vs per-call
- Example of changing from `StringMatcher` to `NumericMatcher` in practice
- CLI support for matcher selection (only shown in `nestor calibrate --matcher semantic`)
- No example of using matchers in the CLI `ask` command

### Unclear:
- Is matcher choice persisted in the database or per-query?
- When changing matchers, do you need to recalibrate thresholds?
- Example of using `NumericMatcher` with the CLI

---

## 5. Keyring Setup Missing from README (MEDIUM PRIORITY)

**Gap:** Keyring setup and usage is only in QUESTIONS.md §6, not in README.

### Missing from README:
- How to set up a keyring before first use
- Why you might want a keyring (per-verifier authentication) vs no keyring (typed names)
- Example of using the UI with a keyring configured
- Difference between `NESTOR_SEAL_KEY` and `NESTOR_KEYRING`

### Example found only in QUESTIONS.md:
```bash
nestor keys add rita --keyring keys.json
nestor keys add sam --keyring keys.json
export NESTOR_KEYRING=keys.json
nestor ui --db data/nestor.db  # Now shows sign-in instead of typed name
```

### Impact:
Users don't know production-grade identity setup exists.

---

## 6. Seal Key Generation Not Covered (MEDIUM PRIORITY)

**Gap:** `NESTOR_SEAL_KEY` requirement is mentioned but not explained.

### Missing:
- How to generate a seal key for production use
- Where and how to store it securely
- Difference between `NESTOR_SEAL_KEY`, `NESTOR_CACHE_KEY`, and `NESTOR_KEYRING`
- What happens if you lose the key or need to rotate it
- Impact on already-sealed data

### Current state:
- README mentions warnings when unset
- `NESTOR_REQUIRE_SEAL_KEY=1` is shown but not explained
- No setup instructions

---

## 7. UI Usage Not Documented (LOW PRIORITY)

**Gap:** UI startup is shown but not how to use it.

### Shown:
```bash
python -m nestor.ui --db data/nestor.db
nestor-ui --db data/nestor.db --open
```

### Missing:
- What the UI looks like (no screenshots or description)
- How to navigate between Queue, Memory, Ask, and Ledger views
- What "acting as" means and how it relates to keyrings
- How to seal a segment vs reject it
- How to handle conflicting seals

### Impact:
Low — CLI covers core use cases, but UI is a known surface that's under-documented.

---

## 8. MCP Server Configuration Not Explained (LOW PRIORITY)

**Gap:** MCP server is mentioned but not explained.

### Shown:
```bash
nestor serve --db data/nestor.db
```

### Missing:
- JSON configuration example for Claude's `mcpServers` setting
- What each tool (`nestor_ask`, `nestor_resolve`, etc.) does and returns
- Why sealing is not available via MCP (explained in QUESTIONS.md §4 but not README)
- Example of a model using it

---

## 9. CLI Help Text is Sparse (MEDIUM PRIORITY)

**Gap:** `nestor --help` and subcommand help (`nestor ask --help`) provide minimal guidance.

### Examples of missing help:
```bash
nestor ask --help
# Shows options but no examples

nestor resolve --help
# Doesn't show that --domain is required for entity resolution

nestor check --help
# Doesn't explain numeric reconciliation or tolerance
```

---

## 10. Import/Export Workflow Could Be Clearer (LOW PRIORITY)

**Status:** Actually well-documented in QUESTIONS.md §2 and README §Export.

**Minor suggestion:** Add a complete end-to-end example showing:
```bash
# Instance A: Export memory
nestor export --out bundle.json

# Transfer to Instance B
cp bundle.json /remote/path/

# Instance B: Dry run import
nestor import bundle.json

# Instance B: Actually import (with conflicts if any)
nestor import bundle.json --apply --verifier analyst
```

---

## 11. Benchmarking Output Not Interpreted (LOW PRIORITY)

**Gap:** Benchmarking and calibration commands are shown but output isn't explained.

### Shown:
```bash
python bench/bench_accuracy.py --probes 400
nestor calibrate --from en --to es --target 0.01
```

### Missing:
- Example output and what it means
- How to interpret the threshold trade-off chart from `bench/serve_ui.py`
- When to run calibration vs relying on default 0.92 threshold

---

## 12. Custom Storage Implementation Not Shown (LOW PRIORITY)

**Gap:** Storage Protocol is documented as a technical spec, but no implementation example.

### Documented:
```python
@runtime_checkable
class Storage(Protocol):
    def memory_insert(self, pair): ...
    # [more methods]
```

### Missing:
- Minimal working example of a custom Store (e.g., Postgres implementation)
- Which methods are required vs optional capabilities
- How optional capabilities affect available surfaces

---

## Summary

| Issue | Severity | Category | Impact |
|-------|----------|----------|--------|
| Python API example wrong | **HIGH** | Correctness | Users get immediate TypeError |
| Unclear storage setup | **MEDIUM** | Clarity | Users need to read source code |
| Ledger configuration unclear | **MEDIUM** | Clarity | Users may mishandle ledger/backups |
| Matcher configuration sparse | **MEDIUM** | Completeness | Users unaware of matcher options |
| Keyring setup missing from README | **MEDIUM** | Completeness | Production setup not obvious |
| Seal key generation uncovered | **MEDIUM** | Security | Users don't know secure setup |
| CLI help text minimal | **MEDIUM** | Usability | Users struggle with CLI options |
| UI usage undocumented | **LOW** | Completeness | Users prefer CLI anyway |
| MCP configuration missing | **LOW** | Completeness | Niche use case |
| Benchmarking interpretation | **LOW** | Completeness | Advanced usage |
| Custom Storage example | **LOW** | Completeness | Advanced usage |

## Recommendations for Next Steps

### High Priority
1. **Fix the Python API example in README** — change to use `answer.ask()` with correct parameter names and return value access
2. **Add storage setup section** — explain `:memory:` vs file-backed, backup strategy, and the `store=` parameter option

### Medium Priority
3. **Document ledger setup** — explain defaults, verification, and recovery
4. **Add keyring usage section** — show setup and why it matters for production
5. **Improve CLI help** — add examples to `--help` output for each command
6. **Document seal key setup** — explain generation, storage, and rotation

### Low Priority (but easy wins)
7. Add screenshots or descriptions of the UI
8. Add example configuration for MCP server usage
9. Show example custom Storage implementation
10. Interpret benchmark output

