---
name: security-review
description: >-
  A diff-aware security review of Nestor's high-risk surfaces — the asymmetric
  seals, the ledger, the trust-root refusals, and the usual injection/traversal
  paths. Use before finishing a branch that touches signing, the store, hooks, or
  anything that reads external input. Keyless: the reviewer is the session, not an
  API.
---

# Security review (Nestor)

The automated gates catch categories: `bandit` flags known-dangerous calls,
`detect-secrets` refuses a committed trust root, the mutation guard proves the
refusal tests can fail. This is the human-shaped pass over the diff that those
cannot do — read the change for what it *lets happen*, on the surfaces where a
Nestor bug is a breach rather than a crash.

Run it on the diff (`git diff master...HEAD`), not the whole tree — a review
scoped to what changed is one you will actually finish.

## The surfaces that matter here

1. **The asymmetric seals (`nestor/signing.py`).** Does a signature still verify
   only under the key of the verifier *named on it*? Any new path that returns a
   validity `True` without reaching `_verifies_with` reopens the Nestor#2 forgery.
   Watch for: an added early-return, a widened `except`, a comparison that isn't
   constant-time on secret-dependent bytes, a message-construction change that a
   signer can no longer reproduce byte-for-byte.
2. **The ledger (`nestor/ledger.py`, `cascade`).** Is it still append-only and
   hash-chained? A write that can overwrite or reorder history, or a seal event
   that lands without its ledger entry, breaks the audit trail — corrections land
   *beside* the record, never on top.
3. **The trust root.** No key material, keyring file, or grant is ever written
   into the tree or a bundle. Cross-check against `detect-secrets` — but also
   read for a *new path* that could serialize a secret (an export, a log line, an
   error message echoing a key).
4. **The gates (`hooks/`).** Does the MCP/seat gate still deny, and the
   write-review gate still block, after this change? If the diff touches a guard,
   the mutation guard's set (`scripts/mutation_guard.py`) should cover it — if it
   doesn't, add the mutation.
5. **External input.** Anything reading a payload, a file, a bundle, or a
   subprocess arg: injection, path traversal, unvalidated deserialization, an
   `eval`/`exec`/`pickle` that wasn't there before.

## How to review

1. **Scope.** Read the diff top-to-bottom once before forming opinions.
2. **Ask of each hunk:** what does this let an attacker (or a buggy caller) do
   that it couldn't before? Name the concrete misuse, not "looks risky."
3. **Verify, don't assume.** If a guard looks weakened, confirm with a test that
   performs the forbidden act — or add one. A claimed vulnerability you can't
   demonstrate and a guard you can't show failing are the same unverified state.
4. **Report** blocking issues (a real bypass) separately from hardening
   suggestions. Propose; don't confirm — a finding is a draft for a human.

## Provenance

The idea is Anthropic's `claude-code-security-review` action (MIT). Re-landed
keyless: that action sends the diff to a model over an API key; in a Claude Code
session the model is already reviewing, so the same pass runs with no key, no
external action, and no secret to configure — pointed at Nestor's own surfaces.
