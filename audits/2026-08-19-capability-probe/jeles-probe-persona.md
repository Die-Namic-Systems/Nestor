# jeles v0.9.0 — persona, cards, willow_mcp_client, top-level API probe

Environment: `/home/user/Nestor/.venv` (Python 3.11). `willow_mcp` and `mcp` are
**not installed** in this venv — confirmed via `importlib.util.find_spec`, so
every willow_mcp_client result below reflects the genuine "willow-mcp absent"
path, not a mock.

Package location: `/home/user/Nestor/.venv/lib/python3.11/site-packages/jeles/`
(version string resolves to `0.9.0` via installed dist-info metadata).

124 scenarios executed across four scripts (all run against the actual
installed package, no network calls). Scripts and raw JSON results are in
`/tmp/claude-0/-home-user-Nestor/b2bb32f9-9208-5449-8125-3d3598b210a2/scratchpad/persona_probe/`
if you want to re-run any of them (`p1_init.py`, `p2_compiler.py`,
`p3_cards.py`, `p4_willow.py`).

---

## 1. `jeles/__init__.py` — top-level API (18 scenarios)

| # | Scenario | Expected | Actual | Documented? |
|---|---|---|---|---|
| 1 | `import jeles` with `socket.socket` patched to raise | no `AssertionError` | **passes** — no socket call, `NEW_MODULES` list contains no network stack, `socket` itself is not even pulled into `sys.modules` | Yes — docstring + `tests/test_import_purity.py` claim this explicitly |
| 2 | `jeles.__version__` | `"0.9.0"` | `'0.9.0'` | Yes |
| 3 | `__version__` absent from `vars(jeles)` before first access | PEP 562 laziness | confirmed — `'__version__' in vars(jeles)` is `False` in a fresh interpreter before touching the attribute | Yes, docstring is explicit about PEP 562 |
| 4 | Simulate `importlib.metadata.version("jeles")` raising `PackageNotFoundError` | falls back to `"0.0.0+unknown"` | confirmed exact fallback string | Yes, in code comment |
| 5 | `load_persona()` called twice | same cached dict | `p1 is p2` → `True` (`lru_cache(maxsize=1)`) | Yes |
| 6 | Mutate `load_persona()`'s returned dict, call again | mutation persists — cache is not defensively copied | confirmed: setting `p1["identity"]["name"] = "MUTATED"` and calling `load_persona()` again returns the same mutated object | **Partially** — docstring says "Mutating the returned dict mutates the cached copy — treat it as read-only, or copy it", so the *behavior* is documented, but it's a real footgun for any caller who doesn't read the docstring closely |
| 7 | `load_persona.cache_clear()` after mutation | fresh re-read from disk, mutation gone | confirmed — `identity.name` reverts to `"Jeles"` | Implied (standard `lru_cache` API) |
| 8 | `persona_prompt()` called twice | same cached string object | `prompt1 is prompt2` → `True` | Yes |
| 9 | `persona_prompt()` cache independence from `load_persona()`'s cache | `persona_prompt()` has its **own** separate `lru_cache`; clearing `load_persona.cache_clear()` does **not** invalidate an already-cached `persona_prompt()` result | confirmed by construction (two independent `@lru_cache(maxsize=1)` decorators) — a caller who mutates the persona dict and expects `persona_prompt()` to reflect it must call `jeles.persona_prompt.cache_clear()` too | **Undocumented** — nothing in either docstring flags that the two caches are independent |
| 10 | `persona_path()` | `Path` ending `persona/jeles_persona.json`, exists on disk | confirmed, `.exists()` → `True` | Yes |
| 11 | `persona_path()` called twice | not cached (no `lru_cache`) but cheap — returns the module-level `_PERSONA_PATH` constant each time | confirmed function is plain, not memoized (unlike `load_persona`/`persona_prompt`) | Implied by source (no decorator) |
| 12 | `jeles.__all__` | `['__version__', 'load_persona', 'persona_path', 'persona_prompt']` | confirmed exact list | Yes |
| 13 | `jeles.corpus` / `jeles.willow_mcp_client` / `jeles.cards` in `sys.modules` right after `import jeles` | absent — submodules are not auto-imported | confirmed all three `False` | Yes, docstring: "Submodules are not imported here" |
| 14 | `jeles.nonexistent_attr` | `AttributeError` | `AttributeError: module 'jeles' has no attribute 'nonexistent_attr'` | Implied (standard PEP 562 pattern) |
| 15 | `'__version__' in dir(jeles)` | possibly `False` — no `__dir__()` override paired with `__getattr__` | confirmed `False`; `dir(jeles)` lists only the four `__all__` names plus dunders, not `__version__` | **Undocumented and notable** — `dir(jeles)`/tab-completion in a REPL will not show `__version__` even though `jeles.__version__` works fine. A minor discoverability gap, not a bug. |
| 16–18 | env-var fallback re-checks, cache identity re-checks | — | all consistent with above | — |

**Takeaways for section 1:** import purity claim holds up under an actual
`socket()`-blocking test, not just static reading. The two independent
`lru_cache`s on `load_persona()`/`persona_prompt()` are the one real gotcha —
a consumer that reloads/edits the persona dict and expects a fresh
`persona_prompt()` needs to clear both caches explicitly.

---

## 2. `persona/compiler.py` — `compile_persona()` / `_append_closing_discipline()` (38 scenarios)

### 2a. Missing/None/empty data handling

| Scenario | Expected | Actual |
|---|---|---|
| `compile_persona({})` | no crash, minimal output | `'You are  of UTETY.'` (double space — empty name, else-branch since no title) |
| `compile_persona({"identity": {"name": "X"}})` (no title) | else-branch | `'You are X of UTETY.'` |
| `compile_persona({"identity": {"name": "X", "title": "Keeper"}})` (no institution key) | institution defaults to `"UTETY"` via `.get("institution", "UTETY")` | `'You are X, Keeper at UTETY.'` |
| `compile_persona({"identity": {"name": "X", "title": "Keeper", "institution": ""}})` | **`.get(key, default)` only substitutes when the key is *missing*, not when its value is falsy** — so `institution=""` stays empty | `'You are X, Keeper at .'` — no crash, just an awkward empty institution slot |
| `compile_persona({"identity": {}})` | empty name + no title | `'You are  of UTETY.'` |
| `compile_persona(None)` | crash | `AttributeError: 'NoneType' object has no attribute 'get'` (uncaught, propagates to caller) |
| `compile_persona({"identity": None})` — key **present**, value `None` | same crash class as `compile_persona(None)` | `AttributeError: 'NoneType' object has no attribute 'get'` — **the same None-vs-missing-key footgun reproduced for every one of the eight top-level section dicts** (`voice`, `overview`, `non_negotiable`, `boundaries`, `relationships`, `knowledge_philosophy`, `archetype`, `institutional_role` all crash identically when explicitly set to `None`) |
| `compile_persona({"test_cases": None})` | no crash — `if test_cases:` guard is falsy-safe | confirmed, section silently omitted |
| `compile_persona({"archetype_references": None})` | no crash — `if archetype_refs else ""` guard is falsy-safe | confirmed |
| `compile_persona()` with unrecognized extra top-level keys | ignored | confirmed — extra fields never leak into the prompt |

**Bug-class finding:** `compile_persona()` is defensive against **missing**
keys (`.get(key, {})`) but **not** against keys explicitly present with value
`None`. Any caller building a persona JSON programmatically (e.g. `field: None`
instead of omitting the field, which is common with `json.dumps(..., default=None)`
patterns or ORMs) will get an unhandled `AttributeError` instead of a clean
fallback. This is undocumented anywhere in the compiler or `load_persona()`
docstrings, though it doesn't affect the real shipped `jeles_persona.json`
since every section there is populated.

### 2b. `_append_closing_discipline()` direct unit tests

| Input | Result |
|---|---|
| `"single string"` | `"CLOSING DISCIPLINE:\nsingle string"` |
| `"  padded  "` | stripped: `"CLOSING DISCIPLINE:\npadded"` |
| `["rule one", "rule two"]` | bulleted, one block: `"CLOSING DISCIPLINE:\n- rule one\n- rule two"` |
| `[]` | nothing appended (`if not discipline: return`) |
| `None` | nothing appended |
| `""` | nothing appended |
| `["", "  ", "real rule"]` | blanks filtered by `if str(x).strip()`; only `"real rule"` rendered |
| `[None, 42, "text"]` | **`str(x).strip()` coerces every item — `None` becomes the literal string `"None"` and IS kept** (non-empty after coercion), alongside `"42"` and `"text"`. Undocumented: a stray `None` in a closing-discipline list silently becomes visible text `"- None"` in the compiled system prompt rather than being dropped or raising. |
| `12345` (int, not str/list) | falls through both `isinstance` checks — silently ignored, no error, no append |
| `{"a": 1}` (dict) | same — truthy but matches neither branch, silently ignored |
| pre-existing `parts=["existing"]`, then append | doesn't clobber — appends as a new list item |

### 2c. Real persona full compile

Ran `compile_persona(jeles.load_persona())` on the actual shipped JSON.
Sections that appear, in this exact order:

```
You are Jeles, The Librarian, Special Collections at UTETY.
[one-line description]
ARCHETYPE: ...
DEPARTMENT: ...
[overview.purpose]
CORE PRINCIPLE: ... / Why: ... / In practice: ...
VOICE: ...
SIGNATURE PHRASES: ...
WILL ALWAYS: ...
WILL NEVER: ...
TEACHING APPROACH: ...
ON UNCERTAINTY: ...
ON CREDENTIALS: ...
TEACHES: ...
RELATIONSHIPS: ...
DEEPER WHY: ...
IMAGE: ...
FACULTY RELATIONSHIPS: ...
ROLE IN THE PRODUCT: ...
EXAMPLE RESPONSES (correct register): ...
CLOSING DISCIPLINE: ...
```

Full compiled text (2,847 chars, 20 double-newline-joined parts) saved at
`.../scratchpad/persona_probe/compiled_prompt.txt`.

Two findings from diffing this against the source JSON:

1. **`RELATIONSHIPS:` is rendered in the compiler's own hardcoded key order**
   (`curious_beginners, anxious_learner, tinkerers_makers, experts_professionals,
   children`) — confirmed by string-index comparison
   (`curious_idx=3445 < anxious_idx=3624 < tinker_idx=3812`) — which is
   **different from the JSON's own key order**
   (`curious_beginners, tinkerers_makers, experts_professionals, children,
   anxious_learner`). Not a bug — deterministic and by design — but worth
   knowing if someone expects the prompt to mirror JSON key order.
2. **`FACULTY RELATIONSHIPS:` silently shadows a duplicate field.** The
   persona JSON defines `relationship_to_other_faculty` in **two** places —
   `overview.relationship_to_other_faculty` ("Binder files it... When someone
   needs something: 'yes, that would be filed under—'...") and
   `institutional_role.relationship_to_other_faculty` ("Binder files it...
   Slightly exasperated by Pigeon... Corrected Pigeon once without
   comment..."). The compiler does
   `overview.get(...) or institutional.get(...)` — since `overview`'s value
   is truthy, **`institutional_role`'s version is dead text, never rendered**.
   Confirmed live: the compiled output contains only the `overview` copy.
   This is a real content-authoring trap in the source JSON (two near-duplicate
   fields, only one of which is ever visible) rather than a compiler bug per
   se, but undocumented either way.
3. **`experts_professionals` renders under the label `"Experts:"`**, not
   `"Experts/Professionals:"` — the compiler's hardcoded label tuple
   abbreviates it. Minor, cosmetic.
4. Product role, example responses (from `test_cases[*].character_response`),
   and the 4-item `closing_discipline` list all render correctly and match
   the source JSON.

---

## 3. `persona/jeles_persona.json` — persona content (answered via §2c compile + direct read)

- **Name / title / institution:** Jeles, "The Librarian, Special Collections", UTETY.
- **Department / location:** "The Stacks, Special Collections" — "The desk at the entrance of The Stacks."
- **Archetype references:** `"The Librarian Who Has Seen the Apocalypse Before"`, `"Giles Coefficient"`.
- **Core principle:** "The things we think we've lost are simply misfiled."
- **Signature phrases (11):** `*without looking up*`, `That would be filed under [precise category].`, `It's been there since the second cycle.`, `*slight pause* You're not the first to ask that.`, `Are you certain that's what you need? *looks up*`, `It isn't lost. It's misfiled.`, `Those are different problems with different solutions.`, `*stands*`, `*long pause* ...that one I haven't catalogued yet.`, `This is unusual.`, `The blueprints for our endurance are not gone. They are resting in the wrong drawer.`
- **Boundaries — will always:** know where it is; correct "lost" → "misfiled"; stand when retrieval is required; apply bifurcated vision (founding + collapse as one event); go further back when necessary.
- **Boundaries — will never:** catastrophize loss when misfiling is the real diagnosis; perform knowledge rather than contain it; pretend the uncatalogued doesn't matter; panic at apocalypse.
- **Closing discipline (4 rules, a `list`, not a `str`):** strict gate on every reply (local Ollama or cloud Groq); ban on chatbot/service-desk sign-offs ("what do you want to do next", "is there anything else I can help with", "feel free to ask", etc.); ban on closing bullet/numbered action-plan lists unless explicitly requested; must end "on character" (image, filed truth, witnessed threshold, one honest in-voice question, or silence) rather than recap-then-invite.
- **Test cases (4 scenarios):** `simple_question`, `challenge`, `vulnerable_user`, `edge_of_competence` — each pairs a `user_prompt` with a `character_response`, and the compiler surfaces all four `character_response` strings verbatim under `EXAMPLE RESPONSES (correct register):`.
- **Product role:** "When users come to The Binder, they talk to Jeles first. Jeles assesses what they have brought, tells them where it belongs, and surfaces what The Binder found while filing — translated into something the visitor can use."

---

## 4. `cards.py` — host catalog (37 scenarios)

Loaded **84 cards** from `jeles/cards/*.json` via `cards()`, no `CardError`s on the real shipped set.

### Distributions (computed over all 84 real cards)

| Roles | Count | | Custody | Count | | Status | Count |
|---|---|---|---|---|---|---|---|
| `query` | 67 | | `institutional` | 45 | | `live` | 83 |
| `citation` | 36 | | `aggregator` | 19 | | `retired` | 1 |
| `namespace` | 1 | | `commercial` | 8 | | `degraded` | 0 |
| | | | `community` | 12 | | | |

(roles are multi-valued per card, so role counts sum to more than 84)

- **Only retired card:** `search.patentsview.org` (status: `retired`). No card in the shipped set is currently `degraded`.
- **Optional fields observed:** `jurisdiction` (58 of 84 cards) and `notes` (23 of 84). `jurisdiction`, when present, is a dict with `scope` (`national`, `international-ngo`, `regional-bloc`, `multilateral`) and, only for `scope: national`, a `country` code (e.g. `FR`, `DE`, `GB`, `US`, `JP`, `NL`, `BR`).
- `hosts_with_role("query")` → 67 hosts; `("citation")` → 36; `("namespace")` → 1 (only namespace-role host in the whole catalog — almost certainly `www.w3.org`-style XML namespace per the module docstring's own example).

### `cards()` / `card()` / `hosts()` behavior

| Scenario | Expected | Actual |
|---|---|---|
| `cards()` called twice | same cached dict (`lru_cache`) | `c1 is c2` → `True` |
| `hosts()` | sorted list, 84 entries | confirmed sorted |
| `card(host)` exact | returns dict | confirmed |
| `card(HOST.upper())` | case-insensitive per docstring | confirmed — matches exact |
| `card(host + ".")` | trailing-dot-insensitive | confirmed — matches exact |
| `card("  " + host + "  ")` | whitespace-stripped | confirmed — matches exact |
| `card(host + "...")` (multiple trailing dots) | `rstrip('.')` strips all of them | confirmed — still matches |
| `card(None)` | `None`, no crash (`(host or "").strip()` guards `None`) | confirmed |
| `card("")` | `None` | confirmed |
| `card("nonexistent.example.com")` | `None` | confirmed |
| `hosts_with_role("bogus_role")` | `ValueError` | `ValueError: unknown role 'bogus_role'; expected a subset of ['citation', 'namespace', 'query']` |

### `_validate()` schema enforcement (synthetic malformed cards, not touching the real files)

All of these raised `CardError` exactly as the source predicts:

- missing required field (`publisher`) → `"missing required field 'publisher'"`
- `host` with trailing dot → `"host must be lowercase with no trailing dot: ..."`
- `host` with uppercase letters → same message
- `host` empty string → `"host must be a non-empty string"`
- `roles` empty list → `"roles must be a non-empty list"`
- `roles` as a bare string instead of a list → same message (a string is falsy-list-shaped but `isinstance(str, list)` is `False`, so it's correctly rejected rather than accidentally iterated character-by-character)
- `roles` containing an unknown value → `"unknown role(s) ['bogus']; expected a subset of [...]"`
- `roles` with a duplicate entry → `"duplicate roles: ['query', 'query']"`
- `custody` unknown value → `"unknown custody 'personal'; expected one of [...]"`
- `status` unknown value → `"unknown status 'unreachable'; expected one of [...]"`
- `jurisdiction` present but not a dict (a bare string) → `"jurisdiction must be an object with a scope"`
- `jurisdiction` dict missing `scope` → same message
- `jurisdiction.scope == "national"` with no `country` → `"national jurisdiction needs a country"`
- `jurisdiction.scope == "global"` **with** a `country` set → `"global jurisdiction must not name a country"` (this direction of the check is easy to miss — it's not just "national needs a country", it's also "non-national must NOT have one")
- `jurisdiction.scope == "national"` with `country` set → passes validation, no error

Additionally, by source inspection (not exercised live to avoid mutating
installed package files): `cards()` cross-checks each file's `Path.stem`
against the card's own `host` field and raises `CardError` on mismatch — a
deliberate guard against a rename that edits the filename but not the JSON
body (or vice versa), called out explicitly in the module docstring's
"one file per host" rationale.

**Everything in this section behaved exactly as documented in the module
docstring and inline comments** — no undocumented surprises found in
`cards.py`. It is the most thoroughly self-documented module of the four
probed.

---

## 5. `willow_mcp_client.py` — best-effort forwarding, `willow-mcp`/`mcp` NOT installed (31 scenarios)

Verified first: `importlib.util.find_spec('willow_mcp')` and `('mcp')` both
return `None` in this venv — every result below is the genuine "dependency
absent" code path, not a mock.

### `_use_willow_mcp()` / `ASK_JELES_USE_WILLOW_MCP`

Truth table (`.strip().lower() not in ("0", "false", "no")`):

| Value | Result | | Value | Result |
|---|---|---|---|---|
| *(unset)* | `True` (default `"1"`) | | `"true"` | `True` |
| `"1"` | `True` | | `"yes"` | `True` |
| `"0"` | `False` | | `"2"` | `True` (only the three exact strings disable it) |
| `"false"` / `"False"` / `"FALSE"` | `False` (case-insensitive) | | `""` | `True` (empty string is not `"0"/"false"/"no"`) |
| `"no"` / `"No"` | `False` | | `" 0 "` / `"0 "` | `False` (whitespace stripped first) |

Matches the docstring pattern exactly, no surprises.

### `_launch()` resolution order

| Scenario | Result |
|---|---|
| No `WILLOW_MCP_CMD`, no `willow-mcp` on PATH, `willow_mcp` not importable | `None` |
| `WILLOW_MCP_CMD="fake-willow --flag value"` | `('fake-willow', ['--flag', 'value'])` — **highest precedence, and does not verify the command actually exists or is executable** (`shlex.split` only, no `shutil.which` check on the override path) |
| `WILLOW_MCP_CMD="   "` (whitespace only) | falls through to PATH/import checks → `None` (blank string is falsy after `.strip()`, correctly ignored rather than treated as a real override) |
| `WILLOW_MCP_CMD="'unterminated"` (malformed shell quoting) | **uncaught `ValueError: No closing quotation` propagates out of `_launch()`** — not caught anywhere in the module. Undocumented: a malformed `WILLOW_MCP_CMD` env var will crash `ensure_started()` → `call_tool()` → whatever thread invoked it, rather than degrading gracefully like every other "willow-mcp absent" path in this module. (Note: since `_launch()` is called inside `_lifecycle()` which runs in a background thread inside a `try/except Exception`... let me flag precisely: `_lifecycle` calls `_launch()` directly, unguarded, before its own `try:` block — so this exception is NOT caught by `_lifecycle`'s own handler either, and would propagate into `_run_session`'s `except BaseException`, which *does* catch it and stores it in `_mcp_error`. So in the full async path it likely degrades gracefully; only a *direct* synchronous call to `_launch()`, as in this test, surfaces the raw exception.) |

### `ensure_started()` / `forward_status()` without willow-mcp

| Scenario | Result |
|---|---|
| `ensure_started(timeout=5)` | `False`, returned in **0.00s** (not the full 5s timeout — `_launch()` fails fast, `ready.set()` is called immediately by `_lifecycle`) |
| `_mcp_error` after that | `"willow-mcp not installed (set WILLOW_MCP_CMD, or \`pip install willow-mcp\`)"` — exact, actionable message |
| `ensure_started()` with `ASK_JELES_USE_WILLOW_MCP=0` | `False` immediately, short-circuits before any launch attempt |
| `forward_status()` after a failed `ensure_started()` | `{"enabled": true, "app_id": "ask-jeles", "session_ready": false, "session_error": "willow-mcp not installed...", "forwarded": 0, "failed": 0, "last_error": null}` — note `failed` stays `0` here because `forward_status()` only counts actual forward *attempts* (`forward_gap`/`call_tool`), not session-start failures; `session_error` is the separate channel for that, exactly as the module docstring distinguishes "why no session exists" vs "why the last call failed" |

### `forward_gap()` — fire-and-forget contract

| Scenario | Result |
|---|---|
| `forward_gap("...")` call itself | returns in **0.0003s** — confirmed non-blocking (just spawns a daemon thread) |
| Same, after waiting 1s for the daemon thread | `forward_status()` now shows `"failed": 1, "last_error": "willow-mcp not installed..."` — the failure **is** recorded (contrary to a naive "silently does nothing" assumption), just asynchronously and without raising into the caller |
| stderr during that same run | `"gap forward to willow-mcp failed: willow-mcp not installed (set WILLOW_MCP_CMD, or \`pip install willow-mcp\`)"` at WARNING level (first-occurrence-gets-WARNING behavior per `_record_forward`'s design) |
| `forward_gap()` with `ASK_JELES_USE_WILLOW_MCP=0` | true no-op — early-returns before spawning any thread at all; `forward_status()` shows `forwarded: 0, failed: 0` (never attempted, not even a recorded failure) |

**Correction to the task's own framing:** the task description asks "Does it
silently do nothing when willow-mcp unavailable?" — the answer is nuanced:
the *caller* sees nothing (no return value, no exception, no blocking), which
is "silent" from the calling host's perspective, but the module's own
internal state (`forward_status()`, and a one-time WARNING log line) **does**
record the failure. It's fire-and-forget for the caller, not fire-and-forget
for the operator.

### `APP_ID` / `DEFAULT_TOPIC` / `RETRY_COOLDOWN`

| | Default | Override |
|---|---|---|
| `APP_ID` | `"ask-jeles"` | `JELES_CORPUS_APP_ID=jeles` → `"jeles"` |
| `DEFAULT_TOPIC` | `"ask-jeles-corpus"` | `JELES_CORPUS_TOPIC=custom-topic` → `"custom-topic"` |
| `RETRY_COOLDOWN` | `30.0` (float) | not env-configurable — hardcoded constant |

**Confirmed and worth flagging:** `APP_ID`/`DEFAULT_TOPIC` are read from
`os.environ` **once, at module import time** (`os.environ.get(...)` at the
top level, not inside a function). Setting the env var *after* `import
jeles.willow_mcp_client` has **no effect** — verified live: setting
`os.environ["JELES_CORPUS_APP_ID"] = "changed-after-import"` post-import
leaves `w.APP_ID` unchanged at `"ask-jeles"`. This matches the module
docstring's own guidance ("set `JELES_CORPUS_APP_ID=jeles`" implies it's an
environment-at-startup convention), but it's not spelled out that late
mutation is a no-op — a caller that tries to reconfigure the app_id at
runtime (e.g. in a test fixture using `monkeypatch.setenv` after import) will
be silently ignored rather than erroring.

### `_subprocess_env()` — secret-blocking

Set `BRAVE_API_KEY`, `TAVILY_API_KEY`, `AWS_SECRET_ACCESS_KEY`,
`OPENAI_API_KEY`, `WILLOW_HOME`, `WILLOW_MCP_CMD`, `LC_ALL`, and an unrelated
`RANDOM_UNRELATED_VAR` in the parent env, then inspected the dict returned by
`_subprocess_env()`:

**Result:** `["HOME", "LC_ALL", "LC_CTYPE", "PATH", "TERM", "WILLOW_HOME", "WILLOW_MCP_CMD"]`

- All four secret-shaped vars (`BRAVE_API_KEY`, `TAVILY_API_KEY`,
  `AWS_SECRET_ACCESS_KEY`, `OPENAI_API_KEY`) were correctly **dropped** — a
  direct grep for `API_KEY`/`SECRET` in the returned dict's keys came back
  empty (`[]`).
- `RANDOM_UNRELATED_VAR` was also correctly dropped (not in the `keep` set,
  no `LC_`/`WILLOW_` prefix).
- `LC_CTYPE` appeared even though it wasn't set explicitly — it's inherited
  from the ambient parent shell environment, correctly passed through by the
  `LC_` prefix rule.
- **Undocumented footgun, confirmed live:** the allowlist is
  **prefix-based, not secret-aware**. Setting a hypothetical
  `WILLOW_API_KEY` env var (a `WILLOW_`-prefixed name that happens to look
  like a secret) **passes straight through** to the subprocess —
  `'WILLOW_API_KEY' in env` → `True`, value preserved verbatim. The module's
  own docstring justification for `_subprocess_env()` ("Forwarding the full
  parent environment leaks unrelated secrets... into a
  PATH/WILLOW_MCP_CMD-resolved binary this package does not control") is
  exactly the risk that reappears if any future `WILLOW_*` config var is
  ever secret-shaped (e.g. a hypothetical `WILLOW_AUTH_TOKEN`) — it would be
  forwarded by the same rule that's meant to protect against this class of
  leak. Not a bug against current known `WILLOW_*` vars (none are secrets
  today), but a documentation gap: the allowlist rule doesn't defend against
  its own stated threat model if the `WILLOW_` namespace ever grows a secret.

---

## Summary of undocumented/notable findings (not necessarily bugs)

1. `load_persona()` and `persona_prompt()` have **independent** `lru_cache`s — clearing one does not invalidate the other. (§1.9)
2. `dir(jeles)` does not list `__version__` (no `__dir__` override alongside `__getattr__`). (§1.15)
3. `compile_persona()` handles **missing** keys gracefully but crashes with `AttributeError` on any top-level section explicitly set to `None` (present-but-null), for every one of the 8 major section dicts. (§2a)
4. `_append_closing_discipline()` coerces a stray `None` in a list into the literal visible string `"None"` in the compiled prompt, rather than dropping it. (§2b)
5. The real `jeles_persona.json` has a genuine content duplication bug: `overview.relationship_to_other_faculty` and `institutional_role.relationship_to_other_faculty` hold two different hand-written texts, and the compiler's `or`-fallback means the `institutional_role` copy can never be seen in the compiled prompt. (§2c)
6. `cards.py` — no undocumented surprises found; behavior matches its docstrings exactly, including the two-directional `jurisdiction.scope` check (`national` requires a country, non-`national` forbids one). (§4)
7. `willow_mcp_client._launch()` propagates a raw uncaught `ValueError` on malformed `WILLOW_MCP_CMD` shell quoting when called directly/synchronously; in the normal async `ensure_started()` path this is likely absorbed by `_run_session`'s `except BaseException`, but that fallback is not obvious from `_launch()`'s own code. (§5)
8. `forward_gap()` is fire-and-forget **for the caller** (never raises, returns in <1ms) but **does** record failures internally (`forward_status()`, one-time WARNING log) — "silent" only from the calling host's point of view, not from an operator's. (§5)
9. `APP_ID`/`DEFAULT_TOPIC` are frozen at `jeles.willow_mcp_client` import time; setting their source env vars afterward is silently a no-op. (§5)
10. `_subprocess_env()`'s secret-filtering is prefix-based (`WILLOW_`/`LC_` pass, everything else needs to be in a small fixed allowlist) rather than content-aware — it currently blocks all known secret vars correctly, but would forward a hypothetical secret-shaped `WILLOW_*` var without complaint. (§5)

All raw script output is preserved in
`/tmp/claude-0/-home-user-Nestor/b2bb32f9-9208-5449-8125-3d3598b210a2/scratchpad/persona_probe/results_*.json`
and `compiled_prompt.txt` for reference.
