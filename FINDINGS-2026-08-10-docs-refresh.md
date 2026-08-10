# Findings — 2026-08-10 — a documentation refresh, five days on

The task was open: *"the documentation is due for a refresh."* It was run as two
passes over the docs against the **current** tree, not against memory —

1. **Drift reconciliation.** Every checkable claim in `README.md` and the 15
   `docs/*.md` — function signatures, CLI commands and flags, the MCP tool list,
   the extras, the Storage capability table, cross-references, hardcoded counts,
   and the project-layout tree — checked against the code that is shipped today.
2. **A fresh standup**, in the tradition of
   [`FINDINGS-2026-08-05-docs-standup.md`](FINDINGS-2026-08-05-docs-standup.md):
   execute the README top to bottom as a fresh operator in an arbitrary cwd,
   small-model reader in mind, and record only what was **observed by running**.

The headline is the same one the 08-05 audit earned and this one confirms by
execution: **the docs work.** Every documented command ran; every documented
output matched; every documented refusal refused with the documented message.
The 08-05 audit's seven ranked findings and every batched drift are now closed,
each re-verified here by running it rather than reading it. What this pass found
is the ordinary cost of a fast week — a marquee feature and a new demo that
shipped ahead of their README lines — plus one class of drift that had recurred
because nothing gated it.

Environment: Python 3.11.15, the repo `.venv`, `nestor` on PATH, `[keys]` and
`[semantic]` present. Suite: **937 passed, 19 skipped** (up from 445 on 08-05).

---

## What the drift reconciliation found

Categories checked and **clean** — because `tests/test_docs.py` already gates
them and the suite is green: function/method signatures, CLI subcommands and
flags, the seven `nestor serve` tools, the five extras, the six-row Storage
capability table, sampled cross-references, and the `nestor/*.py` layout tree.
The gate is doing its job; the drift lived exactly where the gate did not reach.

- **The `docs/` and root portion of the layout tree had drifted** — the class
  `FINDINGS-2026-08-05` §8 named, recurred. Seven docs
  (`carried-strings`, `corpus-order`, `detection-kit-as-gates`,
  `live-forever-verse`, `releasing`, `roots-willow-and-homestead`,
  `seal-staleness-and-quorum`), the whole `docs/dogfood/` subtree, `CHANGELOG.md`,
  `bench/retrieval_quality.py`, and `demo/the_dogfooding.py` all existed but had
  no tree entry. The `nestor/*.py` slice is gated and stayed exact; the rest of
  the tree had no gate and drifted. Fixed, and gated (below).
- **`docs/releasing.md` quoted a stale suite count** — `597 passed / 7 skipped`.
  That is a *dated* hand-run snapshot (2026-08-06, four interpreters), so it was
  **not** edited to today's number — rewriting a dated measurement falsifies the
  record. A visible "since grown to 937/19" note was added beside it instead.

## What the fresh standup found (open, in descending small-model-hit order)

The full run — the fixed table and the reproductions — is the substance of the
standup; the residue after this pass:

1. **`nestor calibrate` still recommends from a tiny corpus with no floor in its
   *output*.** The README documents the caveat in prose ("a small memory
   recommends low, and means nothing by it"), and the fix for *applying* a
   threshold shipped. But the command's own machine-parseable `←recommended`
   line carries no minimum-corpus warning, so an agent parsing that line — not
   the prose two sections away — still sets a threshold on noise. This is a
   **code** change to `calibrate.py`'s output, not a documentation fix, so it was
   **not** made in this docs pass. Filed as `IDEAS.md` §6.95, **open**, for a
   change that carries its own test.
2. **The rejection snippet is self-contained but `TypeError`s on an empty
   store** — `best_sealed` returns `None`, and the block dereferences `hit["pair"]`.
   The 08-05 §5 defects (undefined `hit`, undocumented shape) are fixed; this is
   the residual edge. Closed with a one-line caveat in the snippet.

## What was fixed in this pass

All in the docs; each verified before it was called done.

- **The layout tree is complete again** — every `docs/*.md`, the `docs/dogfood/`
  subtree, `CHANGELOG.md`, `bench/retrieval_quality.py`, and
  `demo/the_dogfooding.py` now have entries.
- **A gate so it cannot silently recur** —
  `tests/test_docs.py::test_the_project_layout_lists_every_doc_and_no_ghosts`
  asserts every `docs/*.md` appears in the layout block, the same discipline the
  `nestor/*.py` tree has had since `IDEAS.md` §4.5. Editing that gated file went
  through the review desk, as `hooks/before_write.py` requires. Proven to fail:
  removing a doc's line turns the gate red.
- **"Run it end to end — the real surfaces"** added to Quick start. The existing
  quick-start snippets seal in-process, in one script; nothing showed the
  *product* — three surfaces over one store, where the seal is a person at
  `nestor.ui` and not a function call. The new block walks machine-draft →
  terminal-pending → human-seals-in-browser → terminal-serves → ledger-verifies,
  and names the boundary (there is no `nestor seal` subcommand, on purpose). The
  mechanism was verified: `translate_text` queues one reviewable segment,
  `nestor ask` returns `! pending`.
- **The browser-held key is documented** — the week's marquee feature (decision
  0078) was live in `nestor/ui_page.py` and absent from the README UI section. A
  new "Holding your own key in the browser" subsection describes the
  non-extractable WebCrypto Ed25519 mode, the out-of-band `nestor keys add …
  --public HEX` enrolment, the `/api/normalize` show-before-sign step, and the
  deliberately narrow endpoint scope (decision 0077).
- **A one-line "what it is"** near the top — a zero-dependency library, a
  `nestor` CLI, and a stdlib browser UI over one SQLite store — because the
  opening stated the *idea* well and never the *shape*.
- The `docs/releasing.md` count note, and the rejection-snippet caveat, above.

## The shape of it

The 08-05 method — run the docs adversarially, score against a small model — has
been absorbed into the docs it audited, and the one drift class that recurred
(the layout tree) recurred precisely because it was the half of that tree with
no gate. It has one now. What is left is one honest deferral (a calibrate
output change that belongs in code with a test, not smuggled into a docs pass)
and the standing truth that a fast week ships features ahead of their README
lines. None of it was a lie in the docs; each was a row, a subsection, or a
sentence the README already knew how to write.
