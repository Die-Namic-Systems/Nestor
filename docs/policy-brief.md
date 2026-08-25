# Nestor — an AI a ministry can defend using

*Written for a chief-of-staff, a procurement officer, or a policy analyst.
Not the engineer's guide. Every claim below is either checkable in the
source or explicitly marked as opinion.*

## The one question this answers

**If a ministry adopts AI, how does it not lose the ability to say what it
said?**

Nestor is a small tool that keeps a memory of the phrases, translations,
entity names, and figures your office has *checked* — and refuses to serve
the ones it has not. Every checked entry carries who checked it and when.
The record is tamper-evident: any later change breaks a chain that any
reviewer can verify.

The one sentence it makes true, checkable by running one command:

> *A default install of Nestor, running any of its read commands, opens no
> socket to any non-loopback address.*

See [`docs/sovereign-deployment.md`](sovereign-deployment.md) and the
14-assertion test file
[`tests/test_no_network_by_default.py`](../tests/test_no_network_by_default.py)
that gates it.

## The demo, in three commands

```
pipx install nestor-meaning        # or: pip install nestor-meaning
nestor demo --seed policy          # a policy-shaped fixture
nestor ui --db data/nestor-demo.db # opens at http://127.0.0.1:8765
```

What you'll see, on a fresh browser tab:

- **Memory** — five sealed translations of policy-register sentences (English
  ↔ Spanish), four organisation aliases (UN, IMF, WHO, OECD), two numeric
  baselines with tolerances, and one *draft* translation with no signature.
- **Ask** — type any of the five sealed sentences in the source language;
  Nestor returns the target with the human verifier's name attached.
- **Queue** — three sentences the machine drafted from a set of meeting
  minutes but a human has not yet signed. Nothing here serves as verified.
- **Ledger** — every seal, every draft, every consultation, one line per
  entry, each linked to the previous by a SHA-256 hash. Break any one line
  and the chain refuses to verify.

The **draft** row is the demonstration the whole thing rests on: type the
draft sentence, and `ask` returns *pending* — the machine proposed a
translation, the store keeps it for review, and nothing serves as verified
until a human seals it. **A machine may propose. It may not confirm.**

## What "checked" means in this tool

Three properties, all gated by tests you can read in the repository:

1. **Human attribution.** Every sealed row carries a `verifier` — the name
   of the person who signed it. The name comes from a keyring the ministry
   controls; a name not on the keyring cannot seal.
   ([`nestor/keyring.py`](../nestor/keyring.py),
   [`tests/test_asymmetric_seals.py`](../tests/test_asymmetric_seals.py).)
2. **Tamper-evident ledger.** Every seal, every serve, every consultation
   is appended to a hash-chained log. Editing any one entry — or trying to
   fabricate a signature — breaks the chain, and Nestor refuses to serve
   from a broken chain.
   ([`nestor/ledger.py`](../nestor/ledger.py),
   [`tests/test_review_ledger.py`](../tests/test_review_ledger.py).)
3. **Refuse-to-serve-what-isn't-verified.** The cascade returns *sealed*
   (a human signed), *draft* (a machine proposed, waiting on a human), or
   *pending* (nothing above the confidence bar). It does not return a
   confident answer that no human backed.
   ([`nestor/cascade.py`](../nestor/cascade.py),
   [`nestor/answer.py`](../nestor/answer.py).)

## What Nestor does not do

Stated explicitly so the reader is not left inferring:

- **It does not decide anything.** It records what a named human decided,
  and refuses to serve what nobody decided.
- **It does not phone home.** No default read command opens a socket to any
  non-loopback address — gated by
  [`tests/test_no_network_by_default.py`](../tests/test_no_network_by_default.py).
- **It does not require a cloud model.** The default matcher is offline
  (character-similarity on the stored corpus); an LLM cascade is available
  as an opt-in extra (`pip install 'nestor-meaning[cloud]'`) and requires
  the operator to set an API key.
- **It does not require an internet connection at all** for the core recipes,
  after install. See "air-gap" in
  [`docs/sovereign-deployment.md`](sovereign-deployment.md#air-gap-what-still-works).
- **It does not overwrite a signed record.** A row sealed by verifier A
  cannot be silently replaced; the operator has to *explicitly* re-seal
  with a second signature, and the ledger keeps both.

## How to adopt

1. **Install:** [`docs/install.md`](install.md) — `pipx install nestor-meaning`
   is the whole story for a single operator; the same package installs
   into a shared environment the same way.
2. **Understand what runs:** [`docs/sovereign-deployment.md`](sovereign-deployment.md)
   names the four opt-in surfaces that CAN reach the network (Anthropic
   engine, semantic matcher, Ollama daemon, willow-gate cloud path) and
   what has to be true for each to fire.
3. **Try the policy demo:** the three-command sequence above.
4. **See the operator guide** when your team is ready to write to their
   own store: [`docs/agent-guide.md`](agent-guide.md).

## What this brief does NOT claim

- **Not an audit.** Nothing here is a certification. The tests gate what
  they gate; a full security assessment is something the ministry commissions
  from a reviewer of its choosing. Nestor is designed to make that
  assessment tractable, not to substitute for it.
- **Not a policy claim about any government.** The demo fixture uses
  fictional-shaped labels and round-fictional figures; it does not quote
  any real treaty, regulation, or statistic. See the module docstring at
  [`nestor/seed_policy.py`](../nestor/seed_policy.py).
- **Not a promise the extras stay on-box.** The `[cloud]` extra reaches
  Anthropic; the `[semantic]` extra downloads a model on first use; the
  `[gate]` extra crosses a willow-gate. Turning any of them on means
  turning on that network. The default install leaves them off.

## What to send back

If your office is evaluating this, the most useful thing you can send
back is a note from a *live* meeting where a Nestor demo either did or
did not answer a question the room actually had — not a note from a
reviewer who read the source. Nestor's own record of how it goes gets
committed under
[`docs/dogfood/probes/`](dogfood/probes/) — every session's questions,
verbatim answers, and where the store's memory helped or fell short.
