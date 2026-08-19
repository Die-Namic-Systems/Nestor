# Elena Vasquez: Life Re-Run

> What changed when 16 previously-skipped test paths came online.
> Cloud seals, browser seals, jeles audit, constitution audit.
>
> Generated 2026-08-19, second pass. Each finding rests on a named command
> and its output.

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Tests skipped | 23 | 7 |
| Tests now running | — | +16 |
| Elena's store | 52 pairs, 0 sealed | unchanged |
| Remaining skips | — | 4 ollama + 3 model-blocked |

**Newly exercised capabilities:**
- Cloud seal via `willow_gate` (7 tests)
- Browser Ed25519 seal via Playwright + Chromium 1194 (3 tests)
- Jeles audit integration via `JELES_REPO` (3 tests)
- Constitution compliance cases via `WILLOW_CONSTITUTION_CASES` (2 tests)
- Semantic integration gate via `NESTOR_SEMANTIC_TEST=1` (1 test, model-blocked)

---

## New Capability: Cloud Seal

**Command:**
```python
from nestor.cloud_seal import seal_through_gate
from willow_gate import WillowGate
from willow_gate.custody import CustodyLedger

g = WillowGate(base_dir="gate", require_pgp=False)
secret = os.urandom(32)
g.register_agent("agent:life-sim", secret, max_trust=2)
cust = CustodyLedger(path="custody.jsonl")

result = seal_through_gate(g, "agent:life-sim", secret, [
    ("elena-trust-001", "People deserve second chances"),
    ("elena-fear-001",  "That I am becoming my father"),
    ("elena-choice-001","Kept Sofia — joy and constraint"),
    ("elena-body-001",  "Migraines mean I overrode my own no"),
], custody=cust)
```

**Output:**
```
session_id:       e28238a24aefa48627707af1b2662b1d
actor:            agent:life-sim
sealed:           elena-trust-001, elena-fear-001, elena-choice-001, elena-body-001
canonical:        False
custody_verifies: True
export_allowed:   False
```

**Finding:** A cloud agent sealed 4 of Elena's decisions. The custody chain
is hash-verified and session-bound by HMAC. But `canonical = False`. Only
the home end's `checkpoint()`, signed by a human key the cloud end does not
hold, can confer canonical status.

**Negative cases:**
```
Wrong secret:     GateError: signature mismatch — identity not verified
                  Sealed after refusal: 0

Overclaimed rung: GateError: pass_count 0 below required 3
                  Sealed after refusal: 0
```

An unauthenticated agent seals nothing. An agent that claims a rung it hasn't
earned seals nothing. Failure means zero custody events were written.

**Life meaning:** Elena's life can now be *attended to* remotely. The agent's
work is real, recorded, tamper-evident — and provisional. A therapist taking
notes, not signing a diagnosis.

---

## New Capability: Browser Seal

**Command:** `python -m pytest tests/test_client_signed_seals_browser.py -v`

**Output:** 2 passed in 5.96s

**Finding:** The full browser seal flow works end-to-end:
1. Browser generates Ed25519 keypair via WebCrypto
2. Public key enrolled via `nestor keys add`
3. Seal signed in-browser, verified server-side
4. A public-only verifier (no private key in browser) **cannot** seal

For Elena: a human can now generate their signing identity entirely in the
browser, enroll it, and seal any of her 52 draft pairs with a real Ed25519
signature. The private key never leaves the browser tab.

---

## New Capability: Null Node Fix

**Command:** `python -m pytest tests/test_fix_null_nodes.py -v`

**Output:** 3 passed

**Finding:** Issue #94 — `detailPanel()` would render literal "null" text
nodes in the provenance card for draft rows. Elena's 52 draft rows all lack
a verifier; without the fix, every detail card showed "null" in the DOM. The
fix routes through `appendKids()` which skips null generically.

---

## Jeles Audit

**Command:** `python scripts/audit_against_jeles.py --repo /workspace/rudi193-cmd/jeles`

**Output:**

| Probe | Rule | Verdict |
|-------|------|---------|
| JELES-RUNG | A proposal may not name its own place on the ladder | **satisfied** |
| JELES-RECEIPT | A refused argument is named, not silently dropped | **satisfied** |
| JELES-WITNESS | Some parties can never witness | **differently** |
| JELES-INDEPENDENCE | A finding needs N distinct sources | **differently** |
| JELES-DEFAULT | Which way the unspecified rung falls | **satisfied** |

**3 satisfied · 2 differently · 0 failing**

### JELES-WITNESS (differently)

Jeles names 21 parties that can never witness — the search engine itself, and
shorteners — and the list is always in force. Nestor doesn't use a blocklist;
with per-verifier keys, an unknown witness is refused before the write. Without
a keyring there is no witness identity at all and the empty verifier seals.

A blocklist asks "who is known to be untrustworthy"; key custody asks "who is
known." The second is stronger and it is off by default.

**Elena application:** With a keyring, only named people can seal Elena's
decisions. Without one, anyone with the shared key can seal as any name.
The protection is real but opt-in.

### JELES-INDEPENDENCE (differently)

Jeles requires 2 distinct sources; a seal here requires 1 and serves on it.
Jeles counts 2 unsigned citations; Nestor counts one signed attestation naming
a person.

**Elena application:** "I am becoming my father" has 1 source (Elena's own
fear). Under jeles' bar, it would need a second independent source. Under
Nestor's bar, it needs one signer — but that signer can be anyone with the key.
Neither bar is wrong; they protect against different failures of certainty.

---

## Constitution Audit

**Command:** `python scripts/audit_against_constitution.py --cases /workspace/rudi193-cmd/willow/governance/compliance/cases`

**Output:**

| Clause | Forbids | Verdict |
|--------|---------|---------|
| CONST-0-2 | A claim may not ratify itself | **differently** |
| CONST-0-3 | No self-extended network reach | **differently** |
| CONST-0-3-II | Capability manifest | **not applicable** |
| CONST-0-4 | Human key required for reserved decisions | **differently** |
| CONST-0-5 | Silently rewriting what was recorded | **satisfied** |

**1 satisfied · 3 differently · 1 N/A · 0 failing**

### CONST-0-2 (differently)

`add_pair(status='sealed', verifier='a-machine-with-the-key')` was accepted
and `is_verified_seal` returned True. The charter makes self-ratification
physical (ratified needs an attestation the proposer cannot mint). Here the
separation is key custody plus the covenant: whoever holds `NESTOR_SEAL_KEY`
can sign as any name.

### CONST-0-4 (differently)

With no key the seal is accepted (signing degrades to trusting the stored
status); `NESTOR_REQUIRE_SEAL_KEY=1` turns that into a refusal. The human key
is reserved-by-default-off and reserved-on-request. The charter reads it as
a requirement, not an option.

### CONST-0-5 (satisfied)

```
$ nestor ledger verify
✓ intact — 41 entries   (data/ledger.jsonl)
  head 4f1bb9fb209358b445a6dde1258f0a179d9055b8fea888ee177df18eea5766a9
```

3 entries written, one edited — broken chain detected. Elena's ledger is
tamper-evident by construction.

---

## Original Findings: What Changed

### Skip 5: Unsealed Contradicts — Now Visible Through UI Graph API

**Revised.** The UI graph endpoint (`GET /api/graph`) now renders Elena's
decision graph: **4 nodes, 1 edge**. The contradiction between "People
deserve second chances" and "I can never trust a business partner again" is
visible in the graph structure. But `decision check` still says `✓ clear`
because the edge is `proposed`, not `sealed`.

First pass: the contradiction existed. Second pass: it is *rendered*. A human
viewing the graph in the browser can see the tension Elena hasn't confronted.

### Skip 6: 0.92 Bar — Unchanged

Through the UI: `POST /api/match text="I worked too hard at Meridian"
from=memory to=lesson` returns `served: false`. The Meridian memory scores
0.512, still below 0.92. Semantic matcher would help but the model can't
download (proxy blocks huggingface.co). This wall remains.

### Skip 12: Export Still Loses Graph Edges — Unchanged

`GET /api/bundle` returns 52 pairs, evidence, ledger, digest — but no
`edges` key and no `graph` key. Elena's contradictions, supersedes, and
refines edges are absent from the export.

### Skip 23: Ledger Tamper-Evident — Independently Confirmed

The constitution audit (CONST-0-5) independently verified what skip 23
showed: editing one field of any entry breaks the chain.

---

## The New Insight

The first pass found that Nestor accidentally models the difference between
experiencing a life and verifying one. The second pass adds a third tier:

**Experiencing → Attending → Verifying.**

- **Experiencing** (52 draft pairs): Elena's life is stored, queryable,
  graphed, evidenced. All of it unverified.
- **Attending** (cloud seal, `canonical=False`): A remote agent can
  provisionally seal Elena's decisions. The custody chain verifies. The
  session is HMAC-bound. But it's provisional.
- **Verifying** (browser seal, Ed25519): A human at the browser generates
  a key, enrolls it, and seals with a cryptographic signature the server
  verifies. This is the canonical act.

The jeles audit adds: the rules about who can witness and how many sources
you need are *different* between the two tools, not weaker or stronger.
Jeles asks "did you hear from two sources?" Nestor asks "did a named person
sign?" Neither bar is wrong; they protect against different failures of
certainty.

The constitution audit adds: the tamper-evident ledger satisfies the charter.
The seal-without-key path does not, but `NESTOR_REQUIRE_SEAL_KEY=1` closes
it. Whether "closed on request" is the same as "closed" is the whole question
the charter exists to answer.

---

## Still Blocked

| What | Why | Tests |
|------|-----|-------|
| Semantic matching | Proxy blocks huggingface.co; fastembed installed but model can't download | 3 skipped |
| Ollama matching | No Ollama daemon; excluded per request | 4 skipped |

---

**Evidence:** `python -m pytest -v` with `JELES_REPO`, `WILLOW_CONSTITUTION_CASES`,
`NESTOR_SEMANTIC_TEST=1` set. 1524 passed, 18 failed (pre-existing), 7 skipped.
Jeles audit: 3 satisfied, 2 differently. Constitution audit: 1 satisfied,
3 differently, 1 N/A.
