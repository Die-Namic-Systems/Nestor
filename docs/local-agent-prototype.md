# Unified local-agent prototype

Cursor, Claude, and a loopback Ollama model share one household Nestor memory.
They do not share authority. Every model process can read human-signed guidance,
produce a bounded draft, and explicitly propose that draft for review. Only the
human browser session can sign a seal.

## One store, one chain

Every generated client configuration pins the same paths:

```bash
export NESTOR_HOME="$HOME/.nestor"
export NESTOR_DB="$NESTOR_HOME/keep/nestor.db"
export NESTOR_LEDGER="$NESTOR_HOME/keep/ledger.jsonl"
python -m nestor.home_init
```

The explicit ledger pin matters. `ledger_for(nestor.db)` and `bind_ledger()`
have different backwards-compatible defaults; a household deployment must not
leave two plausible chains.

The repository's `docs/dogfood/nestor.db` remains a reproducible all-draft
artifact. It is not the live household memory and rebuilding it cannot erase a
household seal.

## Human key, model verifier

Use the browser's non-extractable Ed25519 mode. The private key remains in the
human's browser storage. Enrol only its public half in a mode-0600 keyring and
give that public-only keyring to the UI and model servers:

```bash
export NESTOR_KEYRING="$NESTOR_HOME/keep/verifiers.json"
export NESTOR_REQUIRE_SEAL_KEY=1
nestor ui --db "$NESTOR_DB" --ledger "$NESTOR_LEDGER"
```

The browser prints the exact `nestor keys add NAME --type ed25519 --public HEX`
command after creating its key. A model or agent must not run that enrolment
command, choose the name, or perform the seal. Those are human acts.

## Agent contract

Every client follows the same sequence:

1. Load the repository seat and deterministic hooks.
2. Ask Nestor before drafting. Serve a sealed hit verbatim and cite its verifier.
3. When no seal covers the task, call `nestor_draft` only if the MCP server was
   explicitly started with `--engine ollama`.
4. Treat the response as a suggestion. Cursor or Claude inspects it, applies any
   change, and runs the repository's real gates.
5. Call `nestor_propose` only when the result is reusable guidance worth a human
   reviewing. A proposal remains a draft.
6. Escalate uncertainty; never manufacture a verifier, status, signature, or
   successful test result.

`nestor_draft` receives task text and caller-supplied excerpts. It has no
filesystem, shell, nested-tool, or non-loopback network access. It retrieves
nearby signed Nestor guidance, sends that bounded context to Ollama, and returns
model/prompt/input provenance without storing the raw prompt.

Future clients implement this contract through the client-neutral hook manifest
in `hooks/wiring.json`; client-specific JSON is generated output, not policy.

## Live probe

The probe refuses to create the seal it needs:

```bash
python scripts/local_agent_probe.py \
  --sealed-query "the guidance you signed in the UI" \
  --task "review this bounded change" \
  --excerpt "the relevant source excerpt"
```

Add `--propose` only when the returned draft should enter the human queue. If
Ollama is absent, its model is missing, or the sealed prerequisite does not
exist, the probe reports that state and exits non-zero.

## Measuring the hypothesis

For each accepted task, record:

- whether Nestor served a seal;
- whether a local draft was accepted or reworked;
- whether a cloud model was used, and why;
- elapsed time and the exact local model tag;
- the sealed context pair IDs and prompt/input hashes.

The prototype observes those outcomes. It does not automatically route to a
large model yet. Evidence should determine that escalation policy.
