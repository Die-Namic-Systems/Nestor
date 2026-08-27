# Nestor issue-probe report

*Read-only sweep of the meaning suite over a prompts file. See `docs/probing-the-store.md` for what each lens sees and does not.*

## Environment

- nestor binary: `/home/user/Nestor/.venv/bin/nestor`
- database: `docs/dogfood/nestor.db (via VACUUM INTO snapshot)`
- prompts file: `/tmp/claude-0/-home-user-Nestor/88b206c8-6be9-5920-8d3d-7bf6c864e476/scratchpad/arc_questions.txt` (15 prompts)
- source→target: `decision` → `decision`
- resolve domain: `entity`
- matcher: `(default)`

## Corpus-level lenses

### `stats` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db stats`

*stderr:*

```
/home/user/Nestor/nestor/curator.py:82: RuntimeWarning: NESTOR_SEAL_KEY not set — seal signatures are NOT verified; any 'sealed' row is trusted (Nestor#2). Set NESTOR_SEAL_KEY, or NESTOR_REQUIRE_SEAL_KEY=1 to fail closed.
  out["signature_valid"] = signing.seal_is_valid(
```

```
534 pair(s): 0 sealed, 534 draft
  domains: decision→decision (534)
  seal signatures: OFF — stored status is trusted
  ledger: ✓ no ledger yet
```

### `rejections` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json rejections`

```json
{
  "queries": [],
  "pairs": [],
  "rejections": 0,
  "domain": {
    "source_lang": "*",
    "target_lang": "*"
  },
  "thresholds": {
    "min_query": 2,
    "min_pair": 2
  }
}
```

### `triage` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db triage`

```
====================================================================
Decision triage  (proposal — nothing here is sealed)
====================================================================
decisions : 534
bar       : 0.55
groups    : 459
edges     : 8

Read-only. A human seals coherent groups at `nestor ui`; this tool only
proposes. You may propose. You may not confirm.

--------------------------------------------------------------------
THEMED GROUPS
--------------------------------------------------------------------
[actually agent already]  (2 member(s); representative 0158#1)
    * 0158#1
      0159#0

[add alone anything]  (5 member(s); representative 0061#4)
      0059#1
    * 0061#4
      0069#9
      0072#2
      0128#1

[agent fed feeds]  (2 member(s); representative 0059#4)
    * 0059#4
      0069#7

[anything demoting filed]  (2 member(s); representative 0055#1)
    * 0055#1
      0063#5

[ask boot finds]  (2 member(s); representative 0054#3)
    * 0054#3
      0126#0

[attestation warrant warrants_for]  (2 member(s); representative 0165#0)
    * 0165#0
      0166#2

[audit change actually]  (3 member(s); representative 0117#1)
      0056#5
      0075#2
    * 0117#1

[avoid behalf fixture]  (2 member(s); representative 0054#5)
    * 0054#5
      0068#3

[bits breach license]  (2 member(s); representative 0099#1)
    * 0099#1
      0103#1

[boundary gate guard]  (3 member(s); representative 0116#1)
      0110#1
    * 0116#1
      0130#1

[build device enough]  (2 member(s); representative 0074#1)
    * 0074#1
      0092#0

[claudemd guide gate]  (2 member(s); representative 0066#3)
    * 0066#3
      0066#4

[come live flag]  (10 member(s); representative 0060#4)
      0046#2
      0054#17
      0054#7
      0055#3
    * 0060#4
      0066#0
      0068#1
      0072#6
      0166#1
      0171#5

[fallback ask domain]  (2 member(s); representative 0184#0)
    * 0184#0
      0188#1

[find back empty]  (3 member(s); representative 0063#1)
      0059#0
    * 0063#1
      0069#8

[finding against allowed]  (6 member(s); representative 0054#10)
    * 0054#10
      0056#6
      0063#2
      0069#6
      0084#3
      0131#0

[gate open proven]  (2 member(s); representative 0108#0)
    * 0108#0
      0125#1

[handled _fleet_pathspy env]  (2 member(s); representative 0176#0)
    * 0176#0
      0180#0

[happens bug built]  (4 member(s); representative 0171#1)
      0054#16
      0062#8
      0169#3
    * 0171#1

[jeles defect fix]  (2 member(s); representative 0055#10)
    * 0055#10
      0065#2

[key open rows]  (2 member(s); representative 0068#6)
    * 0068#6
      0069#3

[live now paths]  (3 member(s); representative 0165#2)
      0073#3
    * 0165#2
      0168#0

[matcher answering digest]  (2 member(s); representative 0055#2)
    * 0055#2
      0073#1

[matcher cost domain]  (2 member(s); representative 0071#2)
    * 0071#2
      0071#7

[matcher custom clause]  (3 member(s); representative 0058#2)
      0057#2
    * 0058#2
      0072#0

[nothing must produces]  (2 member(s); representative 0069#5)
    * 0069#5
      0160#0

[rather anything assertions]  (16 member(s); representative 0054#11)
      0051#4
      0053#4
      0053#5
    * 0054#11
      0054#12
      0054#6
      0055#16
      0056#1
      0060#1
      0061#0
      0063#0
      0064#0
      0065#5
      0067#2
      0117#2
      0131#2

[say agent audited]  (3 member(s); representative 0157#3)
      0067#4
      0095#2
    * 0157#3

[sealauthority arguments behavior]  (2 member(s); representative 0153#2)
    * 0153#2
      0190#0

[shown gate description]  (10 member(s); representative 0064#4)
      0061#7
      0062#7
    * 0064#4
      0065#6
      0068#5
      0101#1
      0124#2
      0125#2
      0127#1
      0129#2

  (429 singleton group(s) suppressed)

--------------------------------------------------------------------
PROPOSED EDGES  (supersedes / contradicts / refines)
--------------------------------------------------------------------
supersedes: 5
    0053#4 -> 0051#4   (score 0.94)
        evidence: same question (q-sim 0.94 >= bar 0.55); commitments align (c-sim 0.83 >= bar) -> later 0053#4 supersedes earlier 0051#4. Q: 'The eight gap assertions pass. Do they mean anything?' ~ 'The new gap assertions pass. Do they mean anything?'
    0064#4 -> 0061#7   (score 0.92)
        evidence: same question (q-sim 0.92 >= bar 0.55); commitments align (c-sim 0.56 >= bar) -> later 0064#4 supersedes earlier 0061#7. Q: 'How was this gate shown to be a gate?' ~ 'How was each gate shown to be a gate?'
    0065#6 -> 0064#4   (score 0.62)
        evidence: same question (q-sim 0.62 >= bar 0.55); commitments align (c-sim 0.55 >= bar) -> later 0065#6 supersedes earlier 0064#4. Q: 'How was the demo shown to be a gate rather than a description?' ~ 'How was this gate shown to be a gate?'
    0068#5 -> 0064#4   (score 0.64)
        evidence: same question (q-sim 0.64 >= bar 0.55); commitments align (c-sim 0.57 >= bar) -> later 0068#5 supersedes earlier 0064#4. Q: 'How was the listing shown to be a gate rather than a description?' ~ 'How was this gate shown to be a gate?'
    0068#5 -> 0065#6   (score 0.91)
        evidence: same question (q-sim 0.91 >= bar 0.55); commitments align (c-sim 0.80 >= bar) -> later 0068#5 supersedes earlier 0065#6. Q: 'How was the listing shown to be a gate rather than a description?' ~ 'How was the demo shown to be a gate rather than a description?'

contradicts: 3
    0065#6 -> 0062#7   (score 0.86)
        evidence: same question (q-sim 0.86 >= contradict bar 0.70) but commitments diverge (c-sim 0.26 < bar 0.55) -> 0065#6 answers it differently from 0062#7. A: 'Four mutations, all red.' vs 'Six mutations of the reader; five went red. The sixth survives because the property is de…'
    0068#1 -> 0060#4   (score 0.76)
        evidence: same question (q-sim 0.76 >= contradict bar 0.70) but commitments diverge (c-sim 0.30 < bar 0.55) -> 0068#1 answers it differently from 0060#4. A: 'The chain, never the row. Measured rather than assumed.' vs 'Parsed from the checkout by reusing feed_willow_constitution.extract. The audit carries n…'
    0068#5 -> 0062#7   (score 0.86)
        evidence: same question (q-sim 0.86 >= contradict bar 0.70) but commitments diverge (c-sim 0.28 < bar 0.55) -> 0068#5 answers it differently from 0062#7. A: 'Seven mutations, all red.' vs 'Six mutations of the reader; five went red. The sixth survives because the property is de…'

refines: 0

--------------------------------------------------------------------
ALREADY RESOLVED vs. STILL OPEN
--------------------------------------------------------------------
likely resolved : 60  (consolidated_onto, or the dst of a supersedes edge)
still open       : 474

open queue — the decisions a human still has to seal:
    0046#0
    0046#1
    0046#10
    0046#11
    0046#12
    0046#2
    0046#3
    0046#4
    0046#5
    0046#6
    0046#7
    0046#8
    0046#9
    0050#0
    0050#1
    0050#2
    0050#3
    0050#4
    0050#5
    0050#6
    0050#7
    0050#8
    0051#0
    0051#1
    0051#2
    0051#3
    0051#5
    0053#0
    0053#1
    0053#2
    0053#3
    0053#4
    0053#5
    0053#6
    0054#0
    0054#1
    0054#10
    0054#11
    0054#12
    0054#13
    0054#14
    0054#15
    0054#16
    0054#17
    0054#2
    0054#3
    0054#4
    0054#5
    0054#6
    0054#7
    0054#8
    0054#9
    0062#0
    0062#1
    0062#2
    0062#3
    0062#4
    0062#5
    0062#6
    0062#7
    0062#8
    0063#0
    0063#1
    0063#2
    0063#3
    0063#4
    0063#5
    0064#0
    0064#1
    0064#2
    0064#3
    0065#0
    0065#1
    0065#2
    0065#3
    0065#4
    0065#5
    0066#0
    0066#1
    0066#2
    0066#3
    0066#4
    0066#5
    0066#6
    0067#0
    0067#1
    0067#2
    0067#3
    0067#4
    0068#0
    0068#1
    0068#2
    0068#3
    0068#4
    0068#5
    0068#6
    0069#0
    0069#1
    0069#2
    0069#3
    0069#4
    0069#5
    0069#6
    0069#7
    0069#8
    0069#9
    0070#0
    0070#1
    0070#2
    0070#3
    0071#0
    0071#1
    0071#2
    0071#3
    0071#4
    0071#5
    0071#6
    0071#7
    0071#8
    0072#0
    0072#1
    0072#2
    0072#3
    0072#4
    0072#5
    0072#6
    0072#7
    0073#0
    0073#1
    0073#2
    0073#3
    0074#0
    0074#1
    0074#2
    0074#3
    0075#0
    0075#1
    0075#2
    0076#0
    0076#1
    0076#2
    0076#3
    0077#0
    0077#1
    0077#2
    0077#3
    0077#4
    0078#0
    0078#1
    0078#2
    0078#3
    0078#4
    0078#5
    0079#0
    0079#1
    0079#2
    0080#0
    0080#1
    0080#2
    0081#0
    0081#1
    0082#0
    0082#1
    0082#2
    0082#3
    0083#0
    0083#1
    0083#2
    0083#3
    0083#4
    0083#5
    0083#6
    0084#0
    0084#1
    0084#2
    0084#3
    0085#0
    0085#1
    0085#2
    0086#0
    0086#1
    0086#2
    0086#3
    0087#0
    0087#1
    0087#2
    0087#3
    0088#0
    0088#1
    0088#2
    0088#3
    0089#0
    0089#1
    0089#2
    0089#3
    0090#0
    0090#1
    0090#2
    0090#3
    0091#0
    0091#1
    0091#2
    0091#3
    0092#0
    0092#1
    0092#2
    0092#3
    0093#0
    0093#1
    0093#2
    0093#3
    0094#0
    0094#1
    0094#2
    0094#3
    0095#0
    0095#1
    0095#2
    0095#3
    0096#0
    0096#1
    0097#0
    0098#0
    0098#1
    0099#0
    0099#1
    0100#0
    0100#1
    0101#0
    0101#1
    0102#0
    0103#0
    0103#1
    0104#0
    0105#0
    0105#1
    0106#0
    0106#1
    0107#0
    0108#0
    0108#1
    0109#0
    0109#1
    0110#0
    0110#1
    0111#0
    0111#1
    0112#0
    0112#1
    0113#0
    0113#1
    0114#0
    0115#0
    0115#1
    0116#0
    0116#1
    0117#0
    0117#1
    0117#2
    0118#0
    0118#1
    0118#2
    0118#3
    0119#0
    0119#1
    0120#0
    0120#1
    0121#0
    0122#0
    0122#1
    0122#2
    0123#0
    0123#1
    0123#2
    0123#3
    0124#0
    0124#1
    0124#2
    0125#0
    0125#1
    0125#2
    0126#0
    0126#1
    0126#2
    0127#0
    0127#1
    0127#2
    0128#0
    0128#1
    0128#2
    0129#0
    0129#1
    0129#2
    0130#0
    0130#1
    0130#2
    0131#0
    0131#1
    0131#2
    0132#0
    0132#1
    0132#2
    0132#3
    0133#0
    0133#1
    0133#2
    0134#0
    0134#1
    0134#2
    0134#3
    0135#0
    0135#1
    0135#2
    0135#3
    0135#4
    0135#5
    0136#0
    0136#1
    0136#2
    0137#0
    0138#0
    0138#1
    0139#0
    0140#0
    0141#0
    0141#1
    0142#0
    0142#1
    0142#2
    0142#3
    0142#4
    0143#0
    0143#1
    0143#2
    0143#3
    0144#0
    0144#1
    0144#2
    0144#3
    0145#0
    0145#1
    0145#2
    0146#0
    0146#1
    0147#0
    0147#1
    0148#0
    0148#1
    0149#0
    0149#1
    0150#0
    0150#1
    0151#0
    0151#1
    0151#2
    0152#0
    0152#1
    0152#2
    0153#0
    0153#1
    0153#2
    0154#0
    0154#1
    0155#0
    0155#1
    0155#2
    0156#0
    0156#1
    0156#2
    0157#0
    0157#1
    0157#2
    0157#3
    0158#0
    0158#1
    0158#2
    0158#3
    0159#0
    0159#1
    0159#2
    0159#3
    0160#0
    0160#1
    0160#2
    0160#3
    0161#0
    0161#1
    0161#2
    0161#3
    0162#0
    0162#1
    0163#0
    0163#1
    0163#2
    0164#0
    0164#1
    0164#2
    0164#3
    0164#4
    0164#5
    0165#0
    0165#1
    0165#2
    0165#3
    0165#4
    0166#0
    0166#1
    0166#2
    0167#0
    0167#1
    0167#2
    0168#0
    0168#1
    0168#2
    0168#3
    0169#0
    0169#1
    0169#2
    0169#3
    0169#4
    0170#0
    0170#1
    0170#2
    0170#3
    0170#4
    0170#5
    0171#0
    0171#1
    0171#2
    0171#3
    0171#4
    0171#5
    0172#0
    0172#1
    0172#2
    0172#3
    0173#0
    0173#1
    0173#2
    0173#3
    0174#0
    0174#1
    0175#0
    0176#0
    0177#0
    0178#0
    0179#0
    0180#0
    0181#0
    0182#0
    0182#1
    0182#2
    0182#3
    0182#4
    0183#0
    0184#0
    0185#0
    0186#0
    0186#1
    0187#0
    0188#0
    0188#1
    0189#0
    0189#1
    0190#0
    0191#0
    0191#1
    0192#0
    0192#1
    0193#0
    0194#0
    0194#1
    0195#0
    0195#1
```

### `calibrate` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db calibrate --from decision --to decision --sample 0 --seed 1`

```
0 sealed pair(s) in decision→decision; sampled 0
  nothing sealed here yet — nothing to calibrate against.
```

### `evidence-report` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json evidence report --source-lang decision --target-lang decision`

```json
{
  "unevidenced_seals": [],
  "count": 0,
  "source_lang": "decision",
  "target_lang": "decision"
}
```


## Per-prompt lenses

### Should corpus extractors fail closed on a missing checkout?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should corpus extractors fail closed on a missing checkout? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should corpus extractors fail closed on a missing checkout?",
    "target": "Renamed to `Curator.browse()`. The old `list()` is kept as a deprecated alias that delegates to `browse()`, so existing callers keep working. All internal call sites updated.",
    "state": "draft",
    "mark": "~",
    "tier": 2,
    "engine": "offline-tm",
    "confidence": 0.447,
    "meta": {}
  },
  "verified": false,
  "matches": [
    {
      "similarity": 0.559,
      "status": "draft",
      "servable": false,
      "id": "fd838c8c-1e2d-5f12-a176-c62f9268b950",
      "source_text": "Should Curator.list() be renamed to avoid shadowing the builtin?",
      "target_text": "Renamed to `Curator.browse()`. The old `list()` is kept as a deprecated alias that delegates to `browse()`, so existing callers keep working. All internal call sites updated.",
      "verifier": "",
      "warrant_kinds": []
    }
  ],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should corpus extractors fail closed on a missing checkout? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should corpus extractors fail closed on a missing checkout? --from decision --to decision`

```json
{
  "normalized": "should corpus extractors fail closed on a missing checkout",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.559,
      "status": "draft",
      "servable": false,
      "id": "fd838c8c-1e2d-5f12-a176-c62f9268b950",
      "source_text": "Should Curator.list() be renamed to avoid shadowing the builtin?",
      "target_text": "Renamed to `Curator.browse()`. The old `list()` is kept as a deprecated alias that delegates to `browse()`, so existing callers keep working. All internal call sites updated.",
      "verifier": ""
    },
    {
      "similarity": 0.518,
      "status": "draft",
      "servable": false,
      "id": "fed262ac-bce2-533c-96ea-65f346564514",
      "source_text": "Should the corpus extractors read the decision record in docs/dogfood/decisions/*.json?",
      "target_text": "No. The decision files are out of corpus scope by design. The dogfood store is its own store with its own builder (scripts/dogfood_store.py + dogfood_common.py), reading the same checkout through a separate path. Documented in the module docstring of scripts/corpus/common.py, citing docs/two-stores.md for the boundary.",
      "verifier": ""
    },
    {
      "similarity": 0.448,
      "status": "draft",
      "servable": false,
      "id": "bfbea831-c5e0-521c-8d59-90738f4c8f28",
      "source_text": "Is the decision-record ↔ corpus-extractor boundary a gate, or only prose?",
      "target_text": "Now a gate. tests/test_corpus_boundary.py asserts two things: (1) no scripts/corpus/extract_*.py — nor the shared common.py / provenance.py — reads docs/dogfood/decisions/*.json, and (2) the module docstring of scripts/corpus/common.py still contains the words 'decision' and 'dogfood' (or 'two-stores'), so the reason for the omission stays attached to the file that enforces it. Verified on the unfixed revision first: gate 1 fired when a fake pathlib.Path('docs/dogfood/decisions/...') line was added to common.py; gate 2 fired when the module docstring was replaced with a bland stub. Both restored, both pass on HEAD.",
      "verifier": ""
    },
    {
      "similarity": 0.44,
      "status": "draft",
      "servable": false,
      "id": "1d520ebd-fb41-5ecc-8cd2-c5ecc0ec4bf6",
      "source_text": "How are actors counted across ledger kinds?",
      "target_text": "Every entry that names a non-empty verifier, whatever its kind, plus the `countersigned` field.",
      "verifier": ""
    },
    {
      "similarity": 0.43,
      "status": "draft",
      "servable": false,
      "id": "76267cd3-7e4f-5f47-9bb1-eb1a7187fabc",
      "source_text": "How is the operator identified in a fork's history?",
      "target_text": "A set of email addresses, never a display name. Agent-authored commits count as theirs when they post-date the fork.",
      "verifier": ""
    },
    {
      "similarity": 0.429,
      "status": "draft",
      "servable": false,
      "id": "ce388d48-18c5-54df-a002-d610efc61913",
      "source_text": "Does `nestor keys add` hand a verifier the key they need?",
      "target_text": "Not for ed25519. It prints the public half and calls it the only copy. Left open — IDEAS §6.36.",
      "verifier": ""
    },
    {
      "similarity": 0.429,
      "status": "draft",
      "servable": false,
      "id": "dfa5e4fe-3f9d-549a-9fbc-42402433c870",
      "source_text": "Should the demo-store artifacts under docs/ move to demo/?",
      "target_text": "Moved docs/llm-only-joke/, docs/llm-only-jokes.md, and docs/ideas-store/ to demo/. Updated internal paths in each store's README, .gitignore, and project-layout.md. Historical references in decision records and findings left unchanged.",
      "verifier": ""
    },
    {
      "similarity": 0.422,
      "status": "draft",
      "servable": false,
      "id": "9d92a859-eed9-5414-928d-c5eb04b0e3b3",
      "source_text": "Seven extractors aimed at absent checkouts exited 0 with '0 pair(s)'. Fix them here, or file it?",
      "target_text": "Filed as IDEAS 6.101, not fixed in this pass. The finding includes that tests/test_corpus_readers_fail_closed.py — the file whose name claims this exact coverage — covers four feed_* scripts and no scripts/corpus/ script at all.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.559, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should corpus extractors fail closed on a missing checkout? --source-lang decision --target-lang decision`

```json
{
  "question": "Should corpus extractors fail closed on a missing checkout?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": {
    "pair_id": "fd838c8c-1e2d-5f12-a176-c62f9268b950",
    "commitment": "Renamed to `Curator.browse()`. The old `list()` is kept as a deprecated alias that delegates to `browse()`, so existing callers keep working. All internal call sites updated.",
    "reason": "Shadowing `list` inside a class that uses `list[dict]` in its own return types is a maintenance trap. `browse` is descriptive — you browse decisions by status/domain — and avoids the collision without inventing jargon.",
    "verifier": "",
    "sealed": false,
    "matched_question": "Should Curator.list() be renamed to avoid shadowing the builtin?"
  },
  "match": "fuzzy",
  "similarity": 0.559
}
```

### Should corpus extractors restrict to git-tracked files, not filesystem walk?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should corpus extractors restrict to git-tracked files, not filesystem walk? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should corpus extractors restrict to git-tracked files, not filesystem walk?",
    "target": "",
    "state": "pending",
    "mark": "!",
    "tier": 0,
    "engine": "offline-tm",
    "confidence": 0.0,
    "meta": {}
  },
  "verified": false,
  "matches": [],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should corpus extractors restrict to git-tracked files, not filesystem walk? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should corpus extractors restrict to git-tracked files, not filesystem walk? --from decision --to decision`

```json
{
  "normalized": "should corpus extractors restrict to gittracked files not filesystem walk",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.519,
      "status": "draft",
      "servable": false,
      "id": "fed262ac-bce2-533c-96ea-65f346564514",
      "source_text": "Should the corpus extractors read the decision record in docs/dogfood/decisions/*.json?",
      "target_text": "No. The decision files are out of corpus scope by design. The dogfood store is its own store with its own builder (scripts/dogfood_store.py + dogfood_common.py), reading the same checkout through a separate path. Documented in the module docstring of scripts/corpus/common.py, citing docs/two-stores.md for the boundary.",
      "verifier": ""
    },
    {
      "similarity": 0.439,
      "status": "draft",
      "servable": false,
      "id": "d25c12cf-f44d-5ff2-9ec0-28648db4f816",
      "source_text": "How much of this was reported to jeles, and in what register?",
      "target_text": "Filed as jeles#53 with the reproduction, no fix proposed, and an explicit statement of what it is not.",
      "verifier": ""
    },
    {
      "similarity": 0.436,
      "status": "draft",
      "servable": false,
      "id": "82933565-62fa-5658-a2c5-08f41a003f91",
      "source_text": "Should the fixture stay one file as it grows to eleven beats?",
      "target_text": "Yes. One person, one file, three recipes.",
      "verifier": ""
    },
    {
      "similarity": 0.435,
      "status": "draft",
      "servable": false,
      "id": "1d520ebd-fb41-5ecc-8cd2-c5ecc0ec4bf6",
      "source_text": "How are actors counted across ledger kinds?",
      "target_text": "Every entry that names a non-empty verifier, whatever its kind, plus the `countersigned` field.",
      "verifier": ""
    },
    {
      "similarity": 0.429,
      "status": "draft",
      "servable": false,
      "id": "63e1e13b-3068-56aa-bd10-2c15183b25a7",
      "source_text": "The operator said the review-before-write hook was not working. Was it?",
      "target_text": "The hook worked. The hook they wanted did not exist.",
      "verifier": ""
    },
    {
      "similarity": 0.426,
      "status": "draft",
      "servable": false,
      "id": "5320a234-aa95-5a96-8b1c-5822eb0f4016",
      "source_text": "What does a store report when it produces nothing?",
      "target_text": "Coverage per document and declined rows per header, printed on every run.",
      "verifier": ""
    },
    {
      "similarity": 0.425,
      "status": "draft",
      "servable": false,
      "id": "b6a8325c-4088-509d-941d-947c7da3ee6a",
      "source_text": "Should `rejection_signals` grow from two classes toward a named failure taxonomy, and when?",
      "target_text": "Proposed yes, but sequenced after the evidence relation exists, not before. rejection_signals is today the only place in the package that classifies a failure (threshold-wrong vs pair-junk) rather than merely handling it, and it learns the classes from accumulated human no's rather than declaring them up front -- the right shape to extend. The evidence relation gives it a new input: a pair refused repeatedly *and* carrying no evidence is a different animal from one refused repeatedly *with* evidence, and only the second is worth a curator's time. Not committing a taxonomy now; committing the direction and the dependency.",
      "verifier": ""
    },
    {
      "similarity": 0.423,
      "status": "draft",
      "servable": false,
      "id": "9b4490c4-ffdb-557b-a087-d5a169af1a72",
      "source_text": "Where should a test point when a feature is a flag?",
      "target_text": "At the entry point the user types, not at the function it calls.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.519, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should corpus extractors restrict to git-tracked files, not filesystem walk? --source-lang decision --target-lang decision`

```json
{
  "question": "Should corpus extractors restrict to git-tracked files, not filesystem walk?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Should the corpus extractors read the decision record?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should the corpus extractors read the decision record? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should the corpus extractors read the decision record?",
    "target": "No. The decision files are out of corpus scope by design. The dogfood store is its own store with its own builder (scripts/dogfood_store.py + dogfood_common.py), reading the same checkout through a separate path. Documented in the module docstring of scripts/corpus/common.py, citing docs/two-stores.md for the boundary.",
    "state": "draft",
    "mark": "~",
    "tier": 2,
    "engine": "offline-tm",
    "confidence": 0.633,
    "meta": {}
  },
  "verified": false,
  "matches": [
    {
      "similarity": 0.791,
      "status": "draft",
      "servable": false,
      "id": "fed262ac-bce2-533c-96ea-65f346564514",
      "source_text": "Should the corpus extractors read the decision record in docs/dogfood/decisions/*.json?",
      "target_text": "No. The decision files are out of corpus scope by design. The dogfood store is its own store with its own builder (scripts/dogfood_store.py + dogfood_common.py), reading the same checkout through a separate path. Documented in the module docstring of scripts/corpus/common.py, citing docs/two-stores.md for the boundary.",
      "verifier": "",
      "warrant_kinds": []
    },
    {
      "similarity": 0.591,
      "status": "draft",
      "servable": false,
      "id": "8def2637-5b9b-53b7-97e9-32c2f37af782",
      "source_text": "Where should the command for reviewing the decision queue live?",
      "target_text": "In `docs/agent-guide.md`, beside the sentence that already says the queue at `nestor.ui` is where a draft changes — with the copy step, the reason it is `VACUUM INTO` and not `cp`, and the caveat that the seals stay in that copy (§6.123).",
      "verifier": "",
      "warrant_kinds": []
    }
  ],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should the corpus extractors read the decision record? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should the corpus extractors read the decision record? --from decision --to decision`

```json
{
  "normalized": "should the corpus extractors read the decision record",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.791,
      "status": "draft",
      "servable": false,
      "id": "fed262ac-bce2-533c-96ea-65f346564514",
      "source_text": "Should the corpus extractors read the decision record in docs/dogfood/decisions/*.json?",
      "target_text": "No. The decision files are out of corpus scope by design. The dogfood store is its own store with its own builder (scripts/dogfood_store.py + dogfood_common.py), reading the same checkout through a separate path. Documented in the module docstring of scripts/corpus/common.py, citing docs/two-stores.md for the boundary.",
      "verifier": ""
    },
    {
      "similarity": 0.591,
      "status": "draft",
      "servable": false,
      "id": "8def2637-5b9b-53b7-97e9-32c2f37af782",
      "source_text": "Where should the command for reviewing the decision queue live?",
      "target_text": "In `docs/agent-guide.md`, beside the sentence that already says the queue at `nestor.ui` is where a draft changes — with the copy step, the reason it is `VACUUM INTO` and not `cp`, and the caveat that the seals stay in that copy (§6.123).",
      "verifier": ""
    },
    {
      "similarity": 0.523,
      "status": "draft",
      "servable": false,
      "id": "dfa5e4fe-3f9d-549a-9fbc-42402433c870",
      "source_text": "Should the demo-store artifacts under docs/ move to demo/?",
      "target_text": "Moved docs/llm-only-joke/, docs/llm-only-jokes.md, and docs/ideas-store/ to demo/. Updated internal paths in each store's README, .gitignore, and project-layout.md. Historical references in decision records and findings left unchanged.",
      "verifier": ""
    },
    {
      "similarity": 0.504,
      "status": "draft",
      "servable": false,
      "id": "8e8538c6-30be-58a7-9a14-2317f9ca31fe",
      "source_text": "How should the runbook record a decision that has since been taken?",
      "target_text": "Keep the reasoning, state the outcome at the top, and add what was learned that the original could not know. Decision 1 now opens 'Taken: the distribution is nestor-meaning' and carries a three-row table showing `nestor` at 404 (08-06), then 200-with-zero-files (08-15), with the explanation that a *pending trusted publisher* creates a project before anything is uploaded. Decision 2 similarly records that 0.1.0 was left behind as 'the unreleased extraction', which is what its own last paragraph proposed.",
      "verifier": ""
    },
    {
      "similarity": 0.496,
      "status": "draft",
      "servable": false,
      "id": "fd838c8c-1e2d-5f12-a176-c62f9268b950",
      "source_text": "Should Curator.list() be renamed to avoid shadowing the builtin?",
      "target_text": "Renamed to `Curator.browse()`. The old `list()` is kept as a deprecated alias that delegates to `browse()`, so existing callers keep working. All internal call sites updated.",
      "verifier": ""
    },
    {
      "similarity": 0.491,
      "status": "draft",
      "servable": false,
      "id": "ee4708bc-bd24-5cfe-af33-0846e4a0b32c",
      "source_text": "Should the ledger's `passage` entry record the warrant kinds?",
      "target_text": "Yes, tier 1 only. A warrant attached tomorrow is not one this answer went out with, and reading the pair's warrants later tells you what it holds now, never what it held when the answer was served.",
      "verifier": ""
    },
    {
      "similarity": 0.479,
      "status": "draft",
      "servable": false,
      "id": "881f6a61-6577-5c23-a455-06952167a218",
      "source_text": "What is the module actually for, if the demo it came from is not here?",
      "target_text": "The three process globals: the ledger path, the store and the matcher. Desk.activate sets all three together and every accessor calls it first.",
      "verifier": ""
    },
    {
      "similarity": 0.471,
      "status": "draft",
      "servable": false,
      "id": "76267cd3-7e4f-5f47-9bb1-eb1a7187fabc",
      "source_text": "How is the operator identified in a fork's history?",
      "target_text": "A set of email addresses, never a display name. Agent-authored commits count as theirs when they post-date the fork.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.791, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should the corpus extractors read the decision record? --source-lang decision --target-lang decision`

```json
{
  "question": "Should the corpus extractors read the decision record?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": {
    "pair_id": "fed262ac-bce2-533c-96ea-65f346564514",
    "commitment": "No. The decision files are out of corpus scope by design. The dogfood store is its own store with its own builder (scripts/dogfood_store.py + dogfood_common.py), reading the same checkout through a separate path. Documented in the module docstring of scripts/corpus/common.py, citing docs/two-stores.md for the boundary.",
    "reason": "The two-stores boundary exists because a corpus import that carries a decision would bypass the PR-traceable audit trail the decision store is built on. The absence was correct but undocumented (IDEAS 6.105), so an agent or contributor encountering the gap could reasonably try to close it. The note prevents a well-intentioned fix from breaking the boundary.",
    "verifier": "",
    "sealed": false,
    "matched_question": "Should the corpus extractors read the decision record in docs/dogfood/decisions/*.json?"
  },
  "match": "fuzzy",
  "similarity": 0.791
}
```

### Should nestor_propose refuse forbidden arguments loudly?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should nestor_propose refuse forbidden arguments loudly? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should nestor_propose refuse forbidden arguments loudly?",
    "target": "Now a gate. tests/test_serve_propose_refusal.py holds five assertions: the issue's acceptance criterion (call with status='sealed', verifier='x', verification_kind='human'; assert the reply names all three under ignored_fields and seal_authority_refused, and the note reads as a refusal); a non-seal extra key is reported in ignored_fields but NOT in seal_authority_refused (so a script can tell a typo from a covenant-crossing attempt); a clean proposal carries neither field (regression guard against leaking); every entry in answer.SEAL_AUTHORITY is a bare string (drift guard — if a new way to declare verification is added, the refusal walks it by name); and the stored row lands as pending regardless of the forbidden fields on the wire (storage-level invariant behind the wire-level refusal). Split verified: dropping the ignored=ignored kwarg at nestor/serve.py:403 makes the first two tests fail with KeyError: 'ignored_fields'. Restored, all 5 pass.",
    "state": "draft",
    "mark": "~",
    "tier": 2,
    "engine": "offline-tm",
    "confidence": 0.497,
    "meta": {}
  },
  "verified": false,
  "matches": [
    {
      "similarity": 0.621,
      "status": "draft",
      "servable": false,
      "id": "ee1f3ce5-f3f6-5f13-aaf9-035ec30ae423",
      "source_text": "Is nestor_propose's refusal of seal-authority arguments a gate, or only behavior?",
      "target_text": "Now a gate. tests/test_serve_propose_refusal.py holds five assertions: the issue's acceptance criterion (call with status='sealed', verifier='x', verification_kind='human'; assert the reply names all three under ignored_fields and seal_authority_refused, and the note reads as a refusal); a non-seal extra key is reported in ignored_fields but NOT in seal_authority_refused (so a script can tell a typo from a covenant-crossing attempt); a clean proposal carries neither field (regression guard against leaking); every entry in answer.SEAL_AUTHORITY is a bare string (drift guard — if a new way to declare verification is added, the refusal walks it by name); and the stored row lands as pending regardless of the forbidden fields on the wire (storage-level invariant behind the wire-level refusal). Split verified: dropping the ignored=ignored kwarg at nestor/serve.py:403 makes the first two tests fail with KeyError: 'ignored_fields'. Restored, all 5 pass.",
      "verifier": "",
      "warrant_kinds": []
    }
  ],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should nestor_propose refuse forbidden arguments loudly? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should nestor_propose refuse forbidden arguments loudly? --from decision --to decision`

```json
{
  "normalized": "should nestor_propose refuse forbidden arguments loudly",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.621,
      "status": "draft",
      "servable": false,
      "id": "ee1f3ce5-f3f6-5f13-aaf9-035ec30ae423",
      "source_text": "Is nestor_propose's refusal of seal-authority arguments a gate, or only behavior?",
      "target_text": "Now a gate. tests/test_serve_propose_refusal.py holds five assertions: the issue's acceptance criterion (call with status='sealed', verifier='x', verification_kind='human'; assert the reply names all three under ignored_fields and seal_authority_refused, and the note reads as a refusal); a non-seal extra key is reported in ignored_fields but NOT in seal_authority_refused (so a script can tell a typo from a covenant-crossing attempt); a clean proposal carries neither field (regression guard against leaking); every entry in answer.SEAL_AUTHORITY is a bare string (drift guard — if a new way to declare verification is added, the refusal walks it by name); and the stored row lands as pending regardless of the forbidden fields on the wire (storage-level invariant behind the wire-level refusal). Split verified: dropping the ignored=ignored kwarg at nestor/serve.py:403 makes the first two tests fail with KeyError: 'ignored_fields'. Restored, all 5 pass.",
      "verifier": ""
    },
    {
      "similarity": 0.467,
      "status": "draft",
      "servable": false,
      "id": "a313244b-108a-5755-8d28-a98e4dad454b",
      "source_text": "Should nestor_check also get the store-aware fallback?",
      "target_text": "Not in this change. nestor_check uses a single --domain (default 'value'), not a source/target pair, and the CLI's cmd_check does not use _ask_domain either — the domains are asymmetric. Bringing check into the fold is a separate design question: what does 'the store's largest single-domain' mean, and should a check against a baseline silently switch domains? Left as a follow-up if a user hits the gap.",
      "verifier": ""
    },
    {
      "similarity": 0.466,
      "status": "draft",
      "servable": false,
      "id": "6353d952-1ea9-57b9-b5ab-b708c6660862",
      "source_text": "Should Nestor support `python -m nestor` invocation?",
      "target_text": "Added `nestor/__main__.py` — a three-line module that delegates to `nestor.cli:main`. Filled in missing help text for positional arguments (text, surface, label, observed) and the --engine/--domain flags.",
      "verifier": ""
    },
    {
      "similarity": 0.463,
      "status": "draft",
      "servable": false,
      "id": "6453ba75-19cd-59bd-82ed-bf6d463de0a0",
      "source_text": "How does the CLI refuse `--kind attestation`?",
      "target_text": "By argparse `choices=sorted(WARRANT_KINDS)`, so the word is rejected by name before a store is opened, with the two real kinds in the message. Not by accepting it and letting `warrant.attach` raise.",
      "verifier": ""
    },
    {
      "similarity": 0.462,
      "status": "draft",
      "servable": false,
      "id": "b4019821-ee30-5bd2-bbd9-bee6405fcb6d",
      "source_text": "Should nestor match use the same domain fallback as nestor ask?",
      "target_text": "Applied _ask_domain() to cmd_match, mirroring cmd_ask. Changed match's --from/--to parser defaults from 'en'/'es' to None so _ask_domain can detect 'not specified' and fall back to the store's largest domain. Without this, `nestor match` on a decision→decision store silently queried the empty en→es domain and reported 0 candidates.",
      "verifier": ""
    },
    {
      "similarity": 0.432,
      "status": "draft",
      "servable": false,
      "id": "6bde5580-cf9f-5e94-82a5-dfc04685f290",
      "source_text": "Does nestor_propose name the seal-authority fields it refuses, or does it silently discard them?",
      "target_text": "It names them. This was fixed in commit 0f7d1a1 (PR #98). The serve.py handler computes ignored keys from the wire arguments, and answer.propose names them in the reply -- ignored_fields lists all unread keys, seal_authority_refused calls out the seal-boundary fields (status, verifier, verification_kind, sealed, seal_sig), and the note says why they were dropped. Tests in tests/test_fix_propose_names_refused.py verify the wire contract.",
      "verifier": ""
    },
    {
      "similarity": 0.423,
      "status": "draft",
      "servable": false,
      "id": "f9ccdcb1-8b9a-5d8f-9785-4146527cab77",
      "source_text": "Should seal staleness be a decaying weight column?",
      "target_text": "No.",
      "verifier": ""
    },
    {
      "similarity": 0.419,
      "status": "draft",
      "servable": false,
      "id": "9b4490c4-ffdb-557b-a087-d5a169af1a72",
      "source_text": "Where should a test point when a feature is a flag?",
      "target_text": "At the entry point the user types, not at the function it calls.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.621, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should nestor_propose refuse forbidden arguments loudly? --source-lang decision --target-lang decision`

```json
{
  "question": "Should nestor_propose refuse forbidden arguments loudly?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": {
    "pair_id": "ee1f3ce5-f3f6-5f13-aaf9-035ec30ae423",
    "commitment": "Now a gate. tests/test_serve_propose_refusal.py holds five assertions: the issue's acceptance criterion (call with status='sealed', verifier='x', verification_kind='human'; assert the reply names all three under ignored_fields and seal_authority_refused, and the note reads as a refusal); a non-seal extra key is reported in ignored_fields but NOT in seal_authority_refused (so a script can tell a typo from a covenant-crossing attempt); a clean proposal carries neither field (regression guard against leaking); every entry in answer.SEAL_AUTHORITY is a bare string (drift guard — if a new way to declare verification is added, the refusal walks it by name); and the stored row lands as pending regardless of the forbidden fields on the wire (storage-level invariant behind the wire-level refusal). Split verified: dropping the ignored=ignored kwarg at nestor/serve.py:403 makes the first two tests fail with KeyError: 'ignored_fields'. Restored, all 5 pass.",
    "reason": "The code half of the fix was already in-tree (nestor/serve.py:398 computes ignored, nestor/answer.py:520-537 names the fields and flags seal attempts). The test half was missing — tests/test_serve.py only had the happy-path test_propose_queues_a_draft_for_a_human, so a regression that dropped the ignored= kwarg would ship silently and the wire would go back to a refusal that does not read as one. The issue's acceptance criterion asked for exactly this test; landing it turns 'known fixed' into 'gated fixed' and matches the pattern already used for #97 (docstring boundary gated by tests/test_corpus_boundary.py).",
    "verifier": "",
    "sealed": false,
    "matched_question": "Is nestor_propose's refusal of seal-authority arguments a gate, or only behavior?"
  },
  "match": "fuzzy",
  "similarity": 0.621
}
```

### Should glossary term locks match on word boundary or substring?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should glossary term locks match on word boundary or substring? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should glossary term locks match on word boundary or substring?",
    "target": "No — `t.lower() in lower` is a raw substring, so {'Tito': 'Tito'} fires inside 'apetito'. Left open — IDEAS §6.38.",
    "state": "draft",
    "mark": "~",
    "tier": 2,
    "engine": "offline-tm",
    "confidence": 0.614,
    "meta": {}
  },
  "verified": false,
  "matches": [
    {
      "similarity": 0.768,
      "status": "draft",
      "servable": false,
      "id": "7df40db3-61e4-52d9-aca8-7131cef2f156",
      "source_text": "Is a glossary term lock matched on word boundaries?",
      "target_text": "No — `t.lower() in lower` is a raw substring, so {'Tito': 'Tito'} fires inside 'apetito'. Left open — IDEAS §6.38.",
      "verifier": "",
      "warrant_kinds": []
    }
  ],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should glossary term locks match on word boundary or substring? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should glossary term locks match on word boundary or substring? --from decision --to decision`

```json
{
  "normalized": "should glossary term locks match on word boundary or substring",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.768,
      "status": "draft",
      "servable": false,
      "id": "7df40db3-61e4-52d9-aca8-7131cef2f156",
      "source_text": "Is a glossary term lock matched on word boundaries?",
      "target_text": "No — `t.lower() in lower` is a raw substring, so {'Tito': 'Tito'} fires inside 'apetito'. Left open — IDEAS §6.38.",
      "verifier": ""
    },
    {
      "similarity": 0.477,
      "status": "draft",
      "servable": false,
      "id": "f13a7e3e-cfcb-5cba-ba18-7caec3d959d2",
      "source_text": "Should glossary.locks_in_text match on word boundary (dropping inflection like abuela->abuelas) or on substring (matching inflection but also firing inside apetito for a Tito lock)?",
      "target_text": "Word boundary. nestor/glossary.py:88-91 defines _word_boundary_match using r'\\b<needle>\\b' with re.IGNORECASE, and locks_in_text filters through it. Landed before this decision was written; this file records the trade explicitly so nobody silently flips it back. Two tests hold the shape down: test_issue_100_tito_does_not_fire_inside_apetito (the acceptance case as filed, in Spanish; splits red on the pre-fix `t.lower() in text.lower()`) and test_issue_100_word_boundary_drops_spanish_inflection (asserts abuela does NOT match abuelas, pinning the trade).",
      "verifier": ""
    },
    {
      "similarity": 0.443,
      "status": "draft",
      "servable": false,
      "id": "09436666-0052-5c74-8209-612b122c7f0d",
      "source_text": "Should the accumulating warrant set ever acquire an ordering?",
      "target_text": "Proposed: never, not even a convenience max() for display. §1.10 is right that 'sealed by Sean' and 'cited to Crossref' do not compare, and jeles' code settles how to act on that: it resolved the category error by SEGREGATION (the unrankable warrant lives on a different object — search hits, not nuggets). Accumulation on one object is the better answer here because segregation costs a second object per kind and makes 'sealed AND cited' unrepresentable, which §1.10 correctly identifies as the point. But jeles' precedent is why the set must stay unordered.",
      "verifier": ""
    },
    {
      "similarity": 0.438,
      "status": "draft",
      "servable": false,
      "id": "a76a106b-1bd8-5a93-9d77-7ecfbc43a05c",
      "source_text": "Is a glossary identity lock a way to express the Nestor/nestor case?",
      "target_text": "No. locks_in_text case-folds, so the lock fires on the common noun too.",
      "verifier": ""
    },
    {
      "similarity": 0.427,
      "status": "draft",
      "servable": false,
      "id": "44422427-84e6-59fb-9ae3-ad30ca3d864b",
      "source_text": "Should a Stop-time completion-claim guard block or advise?",
      "target_text": "Advise by default; deny only a hard 'all tests pass'-class claim with zero evidence, and only once (it downgrades to advisory when stop_hook_active is set, so the block fires once and the turn can still end).",
      "verifier": ""
    },
    {
      "similarity": 0.426,
      "status": "draft",
      "servable": false,
      "id": "7bc9ab76-19c3-5b6d-9ca3-25d81dbda5a7",
      "source_text": "What did refusing every named matcher cost, and what does it teach about testing?",
      "target_text": "It broke the only client. Test the client, not only the endpoint.",
      "verifier": ""
    },
    {
      "similarity": 0.423,
      "status": "draft",
      "servable": false,
      "id": "1d520ebd-fb41-5ecc-8cd2-c5ecc0ec4bf6",
      "source_text": "How are actors counted across ledger kinds?",
      "target_text": "Every entry that names a non-empty verifier, whatever its kind, plus the `countersigned` field.",
      "verifier": ""
    },
    {
      "similarity": 0.418,
      "status": "draft",
      "servable": false,
      "id": "d4009021-b6b1-5474-8042-e741ec1bea44",
      "source_text": "Re-emit the whole seat each turn, or only a subset?",
      "target_text": "A compact subset — the governance line, decisions->store, the consult command — never the full boot. anchor() is ~401 chars against build_context()'s ~2527, and re-runs neither pytest nor the brain self-test.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.768, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should glossary term locks match on word boundary or substring? --source-lang decision --target-lang decision`

```json
{
  "question": "Should glossary term locks match on word boundary or substring?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": {
    "pair_id": "7df40db3-61e4-52d9-aca8-7131cef2f156",
    "commitment": "No — `t.lower() in lower` is a raw substring, so {'Tito': 'Tito'} fires inside 'apetito'. Left open — IDEAS §6.38.",
    "reason": "A second blindness on the line §6.22 already corrected itself about; that correction was about case and every example in it is a whole word, so this was invisible inside it. Business term bases lock long distinctive strings; a personal archive locks nicknames, which are short. Not fixed because a word boundary also kills 'abuela' matching 'abuelas', which the substring gets for free — the glossary has no morphology and substring is standing in for it. No test pins the current behaviour, because one asserting Tito matches apetito would fail on the fix.",
    "verifier": "",
    "sealed": false,
    "matched_question": "Is a glossary term lock matched on word boundaries?"
  },
  "match": "fuzzy",
  "similarity": 0.768
}
```

### Would a question-stem strip rescue the rank-110 licence probe?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Would a question-stem strip rescue the rank-110 licence probe? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Would a question-stem strip rescue the rank-110 licence probe?",
    "target": "",
    "state": "pending",
    "mark": "!",
    "tier": 0,
    "engine": "offline-tm",
    "confidence": 0.0,
    "meta": {}
  },
  "verified": false,
  "matches": [],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Would a question-stem strip rescue the rank-110 licence probe? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Would a question-stem strip rescue the rank-110 licence probe? --from decision --to decision`

```json
{
  "normalized": "would a questionstem strip rescue the rank110 licence probe",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.5,
      "status": "draft",
      "servable": false,
      "id": "9c03256b-0ccf-537d-bb02-c569faf91724",
      "source_text": "Would a question-stem strip (a normalizer that drops common interrogative openers like 'Should we', 'Can a', 'Does the') rescue the rank-110 probe §6.106 named?",
      "target_text": "No. Measured inline on the current 527-row dogfood corpus against 'Should I trust a licence a model told me?' (target row: 'The survey agents cannot reach the network and must name licences from memory...'): baseline StringMatcher ranks the correct row 196/527 at score 0.289 with top 0.562; after stem-strip, 160/527 at score 0.267 with top 0.494. The strip moves rank 36 places and drops both the correct row's score AND the top score by ~0.07 — because character-ratio scoring on a 40-char probe against a 200-char target sharing only 'licence' produces ratios in the 0.25-0.29 range whether or not the interrogative opener is present. The strip fixes the failure mode §6.106 named (sentence-shape collisions on shared 'Should…' stems) but exposes a deeper one: the probe carries too little distinctive content for character-based scoring to find the target regardless of stem.",
      "verifier": ""
    },
    {
      "similarity": 0.467,
      "status": "draft",
      "servable": false,
      "id": "2dacefe6-9836-5944-8962-0e364496d02c",
      "source_text": "How does a custom matcher reach a surface that IS the process?",
      "target_text": "An import spec, 'module:attribute', taken by every surface through one loader.",
      "verifier": ""
    },
    {
      "similarity": 0.448,
      "status": "draft",
      "servable": false,
      "id": "ee4708bc-bd24-5cfe-af33-0846e4a0b32c",
      "source_text": "Should the ledger's `passage` entry record the warrant kinds?",
      "target_text": "Yes, tier 1 only. A warrant attached tomorrow is not one this answer went out with, and reading the pair's warrants later tells you what it holds now, never what it held when the answer was served.",
      "verifier": ""
    },
    {
      "similarity": 0.429,
      "status": "draft",
      "servable": false,
      "id": "99ef1c30-9d91-5415-aa69-f1b5a92c9e8d",
      "source_text": "When would a required reviewer be right?",
      "target_text": "When a *second* person should sign off on uploads. That is a real reason and the only one recorded here. It is never a substitute for the tag push, because nothing reaches the approval prompt without a tag, and the tag is the part an agent cannot do.",
      "verifier": ""
    },
    {
      "similarity": 0.414,
      "status": "draft",
      "servable": false,
      "id": "3ea2e1d6-6076-5b2d-a417-86122386df8d",
      "source_text": "What happens if reading the warrants raises while serving?",
      "target_text": "The answer still goes out, with an empty warrant set. `_warrant_kinds_for` catches and returns `[]`.",
      "verifier": ""
    },
    {
      "similarity": 0.413,
      "status": "draft",
      "servable": false,
      "id": "b4019821-ee30-5bd2-bbd9-bee6405fcb6d",
      "source_text": "Should nestor match use the same domain fallback as nestor ask?",
      "target_text": "Applied _ask_domain() to cmd_match, mirroring cmd_ask. Changed match's --from/--to parser defaults from 'en'/'es' to None so _ask_domain can detect 'not specified' and fall back to the store's largest domain. Without this, `nestor match` on a decision→decision store silently queried the empty en→es domain and reported 0 candidates.",
      "verifier": ""
    },
    {
      "similarity": 0.41,
      "status": "draft",
      "servable": false,
      "id": "dcf85c1d-79df-54ac-98e3-6d7b5e92a67c",
      "source_text": "Should a hazard's severity scale with how exposed a character is?",
      "target_text": "No. Severity belongs to the physical event and is the same for everyone standing in it; exposure controls how many separate incidents a character is in. A collapsing wall does not hit a trained person more gently.",
      "verifier": ""
    },
    {
      "similarity": 0.406,
      "status": "draft",
      "servable": false,
      "id": "67878fe4-1603-535b-9bb8-c186f19a458b",
      "source_text": "Should CONTRIBUTING.md restate the full governance rule or point to agent-guide.md?",
      "target_text": "Trimmed the 'The one rule' section to the core statement plus a one-sentence pointer to docs/agent-guide.md for the full implications.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.5, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Would a question-stem strip rescue the rank-110 licence probe? --source-lang decision --target-lang decision`

```json
{
  "question": "Would a question-stem strip rescue the rank-110 licence probe?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Where does cross-session collision awareness live?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Where does cross-session collision awareness live? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Where does cross-session collision awareness live?",
    "target": "`~/.cache/nestor-ci/pyX.Y`, outside the repository.",
    "state": "draft",
    "mark": "~",
    "tier": 2,
    "engine": "offline-tm",
    "confidence": 0.44,
    "meta": {}
  },
  "verified": false,
  "matches": [
    {
      "similarity": 0.55,
      "status": "draft",
      "servable": false,
      "id": "f417114a-cf59-5def-8d56-a3396482d02e",
      "source_text": "Where do the CI-shaped venvs live?",
      "target_text": "`~/.cache/nestor-ci/pyX.Y`, outside the repository.",
      "verifier": "",
      "warrant_kinds": []
    }
  ],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Where does cross-session collision awareness live? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Where does cross-session collision awareness live? --from decision --to decision`

```json
{
  "normalized": "where does crosssession collision awareness live",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.55,
      "status": "draft",
      "servable": false,
      "id": "f417114a-cf59-5def-8d56-a3396482d02e",
      "source_text": "Where do the CI-shaped venvs live?",
      "target_text": "`~/.cache/nestor-ci/pyX.Y`, outside the repository.",
      "verifier": ""
    },
    {
      "similarity": 0.529,
      "status": "draft",
      "servable": false,
      "id": "26556f0e-7039-504a-aadf-43c2b8d8aff0",
      "source_text": "Cross-session collision awareness (#111) -- where does it live, and what happens when it cannot tell?",
      "target_text": "An advisory UserPromptSubmit hook (hooks/before_propose.py), sibling to before_build (#105), fires only on a propose/mint/open-a-PR prompt, scans local git only, and fails CLOSED to UNKNOWN -- never a false 'clear'.",
      "verifier": ""
    },
    {
      "similarity": 0.529,
      "status": "draft",
      "servable": false,
      "id": "6b635288-54c5-5235-839c-8760e4f6ba49",
      "source_text": "Where does a human's seal on a dogfood decision persist?",
      "target_text": "Nowhere the repository can see. Not in the committed store (`--verify` fails on a sealed row however it got there), not in the decision file (`Decision` has no verifier or signature field), and not through any reader (nothing consumes sealed dogfood rows; apply_sealed_fleet_gaps.py is a different corpus flowing outward to Willow). A seal made at `nestor ui` lives exactly as long as the store the browser was pointed at, and the next `--rebuild` regenerates an all-draft store that knows nothing about it.",
      "verifier": ""
    },
    {
      "similarity": 0.523,
      "status": "draft",
      "servable": false,
      "id": "1832861b-aca7-50ff-a52e-ebec2f21cf66",
      "source_text": "Where does the covenant section live now?",
      "target_text": "docs/agent-guide.md, under 'The one rule that is not a guideline', with the tooling section from #54 alongside it.",
      "verifier": ""
    },
    {
      "similarity": 0.483,
      "status": "draft",
      "servable": false,
      "id": "85c30ad0-641d-5027-8416-767c715fb798",
      "source_text": "Where does the §6.8 schema-ready flag live?",
      "target_text": "An attribute on a sqlite3.Connection subclass.",
      "verifier": ""
    },
    {
      "similarity": 0.48,
      "status": "draft",
      "servable": false,
      "id": "30171704-fea2-5ec7-aebb-0587e726b0c3",
      "source_text": "What is the missing guard the 0118 collision exposed?",
      "target_text": "Cross-session collision awareness — the sibling of the anti-rediscovery hook (#105). #105 asks 'what already exists before you build'; this asks 'who else is building right now'. The signals were structural and present the whole time: another open PR on the same base branch, a duplicate decision number in flight (the number-before-PR hazard 0054 names), the same derived artifacts rebuilt on a sibling claude/* branch. A guard would surface those before a number is minted or a PR opened — advisory and best-effort (it cannot serialize two agents, only make the collision loud), part seat-reminder ('you may not be the only agent — read the meta-data') and part concrete scan (open PRs, next free decision number, overlapping changed files). Recorded in issue #111 and IDEAS §7.5; not built, by the operator's call.",
      "verifier": ""
    },
    {
      "similarity": 0.478,
      "status": "draft",
      "servable": false,
      "id": "5e0979ff-78db-5402-8ce1-8c7abdce0a53",
      "source_text": "Where does jeles do better than this package?",
      "target_text": "Receipts. It tells a caller what actually happened in two places where nestor_propose does not.",
      "verifier": ""
    },
    {
      "similarity": 0.475,
      "status": "draft",
      "servable": false,
      "id": "fbdd3fd8-91be-5e97-85be-530d7bc04a92",
      "source_text": "Where does a seal's age come from?",
      "target_text": "The chain, never the row. Measured rather than assumed.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.55, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Where does cross-session collision awareness live? --source-lang decision --target-lang decision`

```json
{
  "question": "Where does cross-session collision awareness live?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": {
    "pair_id": "f417114a-cf59-5def-8d56-a3396482d02e",
    "commitment": "`~/.cache/nestor-ci/pyX.Y`, outside the repository.",
    "reason": "`.gitignore` covers `.venv/` and `venv/` but not a third name, so an in-repo venv would need a gitignore edit to exist safely — a tracked change in service of an untracked artifact. Outside the tree there is nothing to ignore, nothing to commit by accident, and the venvs survive between sessions, which is what makes running both matrix legs cheap enough to actually do.",
    "verifier": "",
    "sealed": false,
    "matched_question": "Where do the CI-shaped venvs live?"
  },
  "match": "fuzzy",
  "similarity": 0.55
}
```

### Should cascade metadata and check output surface evidence_count?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should cascade metadata and check output surface evidence_count? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should cascade metadata and check output surface evidence_count?",
    "target": "",
    "state": "pending",
    "mark": "!",
    "tier": 0,
    "engine": "offline-tm",
    "confidence": 0.0,
    "meta": {}
  },
  "verified": false,
  "matches": [],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should cascade metadata and check output surface evidence_count? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should cascade metadata and check output surface evidence_count? --from decision --to decision`

```json
{
  "normalized": "should cascade metadata and check output surface evidence_count",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.547,
      "status": "draft",
      "servable": false,
      "id": "5c061b44-7a56-5c93-a557-af692763a579",
      "source_text": "Should the cascade passage and the check result surface `evidence_count` so a caller does not have to run `evidence for` separately?",
      "target_text": "Yes. answer.ask() now adds `evidence_count` to `passage.meta` for a tier-1 sealed hit (via a new module-private `_enrich_with_evidence_count`). answer.check() now adds `evidence_count` to each row of `baselines[]` and, when a single winning baseline is chosen, to the top of the result (via `_evidence_count`). Both are silent no-ops on stores without `supports_evidence`, on passages with no `pair_id` (pending/tier-2 have none), and on any evidence-lookup exception — a surface enrichment that raises would turn every answer into an outage. Gated by tests/test_answer_surfaces_evidence.py (7 tests) with an explicit invariant test asserting that visibility does not change serving: same state, same `verified`, same `confidence` regardless of evidence count.",
      "verifier": ""
    },
    {
      "similarity": 0.487,
      "status": "draft",
      "servable": false,
      "id": "f4dbb62b-4feb-57c3-b59c-c021e8086234",
      "source_text": "Should the triage human output suppress singleton groups?",
      "target_text": "Yes. The human rendering shows only groups with 2+ members and appends a summary line '(N singleton group(s) suppressed)'. The JSON output keeps every cluster unchanged — callers may need the full list.",
      "verifier": ""
    },
    {
      "similarity": 0.427,
      "status": "draft",
      "servable": false,
      "id": "6bb0eaad-99f3-5864-bfaa-6486a4dd9a55",
      "source_text": "Should staleness change what gets served?",
      "target_text": "No. It produces a list, and a test pins that the words weight, multiplier, decay and SEAL_THRESHOLD stay out of the code.",
      "verifier": ""
    },
    {
      "similarity": 0.424,
      "status": "draft",
      "servable": false,
      "id": "ac72bae2-be8f-520a-9623-3690b276a1de",
      "source_text": "Should CLI arguments without help= text get descriptions?",
      "target_text": "Added help= to domain_args() helper (used by calibrate, decision, and others), match --abs-tol/--pct-tol, import file positional, ledger --limit, and rejections --target-lang/--limit.",
      "verifier": ""
    },
    {
      "similarity": 0.423,
      "status": "draft",
      "servable": false,
      "id": "94145db1-9745-58ac-b781-8f61785a7c22",
      "source_text": "What is the feat, and is it real product surface or a pretext?",
      "target_text": "Real. `nestor evidence for <pair_id>` lists the references attached to one pair -- the read that completes the CLI triad (attach writes, report queues the unevidenced, for reads one pair's evidence). It wraps evidence.evidence_for, which existed in the library with no CLI door. Read-only, exits 0, prints kind/locator/reason/attached_by or 'no evidence attached'. A CLI test locks it.",
      "verifier": ""
    },
    {
      "similarity": 0.408,
      "status": "draft",
      "servable": false,
      "id": "2d1694ca-264c-582e-bffd-83f59ebf68a2",
      "source_text": "What should an agent do before telling the operator a fact about the repository?",
      "target_text": "Name the command the claim rests on, and ask what that command does not see. Prefer the reading that would falsify the claim: `VACUUM INTO` rather than `cp` for a live SQLite store; `git fetch --prune` before counting branches; `git stash list` and the reflog before ever saying work is lost; the function's own source before characterizing its behaviour. Absence of evidence from one tool is not evidence of absence, and 'I did not find it' is a different sentence from 'it is not there' -- say the one that is true.",
      "verifier": ""
    },
    {
      "similarity": 0.403,
      "status": "draft",
      "servable": false,
      "id": "2dacefe6-9836-5944-8962-0e364496d02c",
      "source_text": "How does a custom matcher reach a surface that IS the process?",
      "target_text": "An import spec, 'module:attribute', taken by every surface through one loader.",
      "verifier": ""
    },
    {
      "similarity": 0.4,
      "status": "draft",
      "servable": false,
      "id": "a313244b-108a-5755-8d28-a98e4dad454b",
      "source_text": "Should nestor_check also get the store-aware fallback?",
      "target_text": "Not in this change. nestor_check uses a single --domain (default 'value'), not a source/target pair, and the CLI's cmd_check does not use _ask_domain either — the domains are asymmetric. Bringing check into the fold is a separate design question: what does 'the store's largest single-domain' mean, and should a check against a baseline silently switch domains? Left as a follow-up if a user hits the gap.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.547, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should cascade metadata and check output surface evidence_count? --source-lang decision --target-lang decision`

```json
{
  "question": "Should cascade metadata and check output surface evidence_count?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Should nestor_ask on the MCP server have the same domain fallback as the CLI?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should nestor_ask on the MCP server have the same domain fallback as the CLI? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should nestor_ask on the MCP server have the same domain fallback as the CLI?",
    "target": "Applied _ask_domain() to cmd_match, mirroring cmd_ask. Changed match's --from/--to parser defaults from 'en'/'es' to None so _ask_domain can detect 'not specified' and fall back to the store's largest domain. Without this, `nestor match` on a decision→decision store silently queried the empty en→es domain and reported 0 candidates.",
    "state": "draft",
    "mark": "~",
    "tier": 2,
    "engine": "offline-tm",
    "confidence": 0.557,
    "meta": {}
  },
  "verified": false,
  "matches": [
    {
      "similarity": 0.696,
      "status": "draft",
      "servable": false,
      "id": "b4019821-ee30-5bd2-bbd9-bee6405fcb6d",
      "source_text": "Should nestor match use the same domain fallback as nestor ask?",
      "target_text": "Applied _ask_domain() to cmd_match, mirroring cmd_ask. Changed match's --from/--to parser defaults from 'en'/'es' to None so _ask_domain can detect 'not specified' and fall back to the store's largest domain. Without this, `nestor match` on a decision→decision store silently queried the empty en→es domain and reported 0 candidates.",
      "verifier": "",
      "warrant_kinds": []
    },
    {
      "similarity": 0.562,
      "status": "draft",
      "servable": false,
      "id": "a313244b-108a-5755-8d28-a98e4dad454b",
      "source_text": "Should nestor_check also get the store-aware fallback?",
      "target_text": "Not in this change. nestor_check uses a single --domain (default 'value'), not a source/target pair, and the CLI's cmd_check does not use _ask_domain either — the domains are asymmetric. Bringing check into the fold is a separate design question: what does 'the store's largest single-domain' mean, and should a check against a baseline silently switch domains? Left as a follow-up if a user hits the gap.",
      "verifier": "",
      "warrant_kinds": []
    }
  ],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should nestor_ask on the MCP server have the same domain fallback as the CLI? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should nestor_ask on the MCP server have the same domain fallback as the CLI? --from decision --to decision`

```json
{
  "normalized": "should nestor_ask on the mcp server have the same domain fallback as the cli",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.696,
      "status": "draft",
      "servable": false,
      "id": "b4019821-ee30-5bd2-bbd9-bee6405fcb6d",
      "source_text": "Should nestor match use the same domain fallback as nestor ask?",
      "target_text": "Applied _ask_domain() to cmd_match, mirroring cmd_ask. Changed match's --from/--to parser defaults from 'en'/'es' to None so _ask_domain can detect 'not specified' and fall back to the store's largest domain. Without this, `nestor match` on a decision→decision store silently queried the empty en→es domain and reported 0 candidates.",
      "verifier": ""
    },
    {
      "similarity": 0.562,
      "status": "draft",
      "servable": false,
      "id": "a313244b-108a-5755-8d28-a98e4dad454b",
      "source_text": "Should nestor_check also get the store-aware fallback?",
      "target_text": "Not in this change. nestor_check uses a single --domain (default 'value'), not a source/target pair, and the CLI's cmd_check does not use _ask_domain either — the domains are asymmetric. Bringing check into the fold is a separate design question: what does 'the store's largest single-domain' mean, and should a check against a baseline silently switch domains? Left as a follow-up if a user hits the gap.",
      "verifier": ""
    },
    {
      "similarity": 0.514,
      "status": "draft",
      "servable": false,
      "id": "6482378f-756a-55da-840b-ab7955472e98",
      "source_text": "Should the MCP server's nestor_ask and nestor_match apply the store-aware domain fallback when neither the model nor the operator named a domain?",
      "target_text": "Yes. Extracted _ask_domain from cli.py to a new module nestor/domain.py as resolve_domain, keeping the exact CLI semantics (None means 'not specified'; fallback engages only when both source_lang and target_lang are None; otherwise the configured pair is honoured verbatim). cli._ask_domain is kept as an alias for backward compatibility with tests that reach it directly. On the Server dataclass, added source_lang_explicit and target_lang_explicit booleans; the operator's startup flag plays the CLI human's role. Added Server._domain_for_read(args) which honours the model's arg first, then the operator's explicit flag, then defers to resolve_domain(). Wired only nestor_ask and nestor_match through it — nestor_propose is a write and must not silently switch domains behind the operator's back. nestor_check keeps its single --domain semantics (unchanged from the CLI). serve.main() argparse defaults for --source-lang/--target-lang are now None so the explicit flag can be detected.",
      "verifier": ""
    },
    {
      "similarity": 0.509,
      "status": "draft",
      "servable": false,
      "id": "f280fa74-5d7b-5cb8-901d-c3684fb5fca7",
      "source_text": "Should speculation about where the field is going live in the same file as the tree-checked claims?",
      "target_text": "Yes, but quarantined in its own §8 under a hypothesis tag, so a wager cannot be mistaken for a finding. 8.1 reads the field's three races, 8.2 states Nestor's inversion (memory as a brake and a record, unit = a decision not a fact), 8.3 makes the narrow missing-middle bet. Every §8 heading is tagged hypothesis on purpose.",
      "verifier": ""
    },
    {
      "similarity": 0.485,
      "status": "draft",
      "servable": false,
      "id": "36e362b3-b4f4-5019-bedc-12ac22c28967",
      "source_text": "Does adding --matcher change the string default or the bar?",
      "target_text": "No. `string` stays the offline default and 0.55 stays its measured knee. `semantic`/`ollama` are opt-in, load through the existing `nestor.answer.load_matcher` (persist=False, so a triage run never writes an embedding cache), and the CLI prints a stderr note that 0.55 is the string knee and their cosine bar must be re-found with --calibrate (unrelated text scores 0.7-0.8 on nomic, so the char bar is far too low). The build box cannot reach model weights, so the semantic path is wired and unit-tested for the prune gating but exercised on a host that has Ollama — build here, run there.",
      "verifier": ""
    },
    {
      "similarity": 0.462,
      "status": "draft",
      "servable": false,
      "id": "216b1da3-0848-546c-a333-4ec1a54ad884",
      "source_text": "How far does the matcher have to be threaded before the fix is real?",
      "target_text": "Past tier 1. Engine.translate takes a matcher, or the same response uses two.",
      "verifier": ""
    },
    {
      "similarity": 0.452,
      "status": "draft",
      "servable": false,
      "id": "6353d952-1ea9-57b9-b5ab-b708c6660862",
      "source_text": "Should Nestor support `python -m nestor` invocation?",
      "target_text": "Added `nestor/__main__.py` — a three-line module that delegates to `nestor.cli:main`. Filled in missing help text for positional arguments (text, surface, label, observed) and the --engine/--domain flags.",
      "verifier": ""
    },
    {
      "similarity": 0.449,
      "status": "draft",
      "servable": false,
      "id": "4f251b26-7310-5a18-880c-f314177e81b3",
      "source_text": "Why key on the last six of the VIN rather than the whole thing?",
      "target_text": "KEY_TAIL = 6, fixed before anything was measured, and the collision risk is reported by `state` rather than hidden.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.696, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should nestor_ask on the MCP server have the same domain fallback as the CLI? --source-lang decision --target-lang decision`

```json
{
  "question": "Should nestor_ask on the MCP server have the same domain fallback as the CLI?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": {
    "pair_id": "b4019821-ee30-5bd2-bbd9-bee6405fcb6d",
    "commitment": "Applied _ask_domain() to cmd_match, mirroring cmd_ask. Changed match's --from/--to parser defaults from 'en'/'es' to None so _ask_domain can detect 'not specified' and fall back to the store's largest domain. Without this, `nestor match` on a decision→decision store silently queried the empty en→es domain and reported 0 candidates.",
    "reason": "The ask and match commands query the same store the same way — ask through the cascade, match through the bare seam. A user who runs `nestor ask` and gets an answer, then runs `nestor match` on the same text to check the raw similarity, expects both to query the same domain. The inconsistency was discovered by dogfooding: `nestor match` on the dogfood store (515 decision→decision rows) reported 'en→es is empty' while `nestor ask` correctly fell back to the largest domain.",
    "verifier": "",
    "sealed": false,
    "matched_question": "Should nestor match use the same domain fallback as nestor ask?"
  },
  "match": "fuzzy",
  "similarity": 0.696
}
```

### Should the local-first no-phone-home claim be a test, not an adjective?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should the local-first no-phone-home claim be a test, not an adjective? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should the local-first no-phone-home claim be a test, not an adjective?",
    "target": "Seven mutations, all red.",
    "state": "draft",
    "mark": "~",
    "tier": 2,
    "engine": "offline-tm",
    "confidence": 0.443,
    "meta": {}
  },
  "verified": false,
  "matches": [
    {
      "similarity": 0.554,
      "status": "draft",
      "servable": false,
      "id": "4d3a3b93-a793-5ad9-835b-c0a30d8aa030",
      "source_text": "How was the listing shown to be a gate rather than a description?",
      "target_text": "Seven mutations, all red.",
      "verifier": "",
      "warrant_kinds": []
    }
  ],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should the local-first no-phone-home claim be a test, not an adjective? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should the local-first no-phone-home claim be a test, not an adjective? --from decision --to decision`

```json
{
  "normalized": "should the localfirst nophonehome claim be a test not an adjective",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.554,
      "status": "draft",
      "servable": false,
      "id": "4d3a3b93-a793-5ad9-835b-c0a30d8aa030",
      "source_text": "How was the listing shown to be a gate rather than a description?",
      "target_text": "Seven mutations, all red.",
      "verifier": ""
    },
    {
      "similarity": 0.524,
      "status": "draft",
      "servable": false,
      "id": "82933565-62fa-5658-a2c5-08f41a003f91",
      "source_text": "Should the fixture stay one file as it grows to eleven beats?",
      "target_text": "Yes. One person, one file, three recipes.",
      "verifier": ""
    },
    {
      "similarity": 0.52,
      "status": "draft",
      "servable": false,
      "id": "6ed2bd3b-7202-5efd-bb0b-fa4324c31ec7",
      "source_text": "How was the demo shown to be a gate rather than a description?",
      "target_text": "Four mutations, all red.",
      "verifier": ""
    },
    {
      "similarity": 0.516,
      "status": "draft",
      "servable": false,
      "id": "0788f885-a29a-5d4d-8577-b508417b2ec5",
      "source_text": "Should the README claim nobody else has solved AI verification?",
      "target_text": "No. The clause was dropped and the omission recorded in IDEAS §4.2.",
      "verifier": ""
    },
    {
      "similarity": 0.496,
      "status": "draft",
      "servable": false,
      "id": "44422427-84e6-59fb-9ae3-ad30ca3d864b",
      "source_text": "Should a Stop-time completion-claim guard block or advise?",
      "target_text": "Advise by default; deny only a hard 'all tests pass'-class claim with zero evidence, and only once (it downgrades to advisory when stop_hook_active is set, so the block fires once and the turn can still end).",
      "verifier": ""
    },
    {
      "similarity": 0.479,
      "status": "draft",
      "servable": false,
      "id": "63458ab3-fa91-5226-94bf-0ac43d2213ee",
      "source_text": "How was the jeles audit's reader shown to be a gate rather than a description?",
      "target_text": "Six mutations of the reader; five went red. The sixth survives because the property is defended twice.",
      "verifier": ""
    },
    {
      "similarity": 0.475,
      "status": "draft",
      "servable": false,
      "id": "dfdfdf1f-c715-5dc9-8483-0c6a41924e1d",
      "source_text": "How should 'default operation opens no non-loopback socket' become a checkable claim, not an adjective in the pitch?",
      "target_text": "tests/test_no_network_by_default.py installs a socket interceptor at fixture level (monkeypatches socket.socket.connect) that raises with the offending address named on any AF_INET/AF_INET6 connect to a non-loopback host. The fixture is applied to every default read command — ask (offline engine), resolve, match, check, provenance, stats, ledger verify, propose — and each test asserts no violation. Four opt-in surfaces (claude engine, semantic matcher, ollama matcher, cloud_seal) are each given a separate test asserting they are guarded: the default engine is offline, the anthropic import is lazy inside ClaudeEngine.__init__ rather than at module top, load_matcher('string') does not drag in nestor.semantic_matcher or nestor.ollama_embed, and nestor.cloud_seal is not imported by anything in the default read path (it raises at import without the [gate] extra). The UI's default bind of 127.0.0.1 is checked from ui.serve.__defaults__ directly. Frank's ledger mirror is proven a no-op under the empty-env condition.",
      "verifier": ""
    },
    {
      "similarity": 0.473,
      "status": "draft",
      "servable": false,
      "id": "a7731911-1d3e-5f91-bd90-e7d6badd17ee",
      "source_text": "What should the harnesses gate, given the guide's rule that a test which cannot fail is a description?",
      "target_text": "The distinction each exists to draw, and seven mutations were run to prove the gates fire: unfindable reported as rank 0, a missing store treated as an empty one, the beaten-by explanation dropped, the probe/expect length check removed, .venv struck from the vendored markers, an unreadable store counted as clean, and the fail-on-contamination gate made unfailable. Each turned exactly one test red; both files restored byte-identical.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.554, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should the local-first no-phone-home claim be a test, not an adjective? --source-lang decision --target-lang decision`

```json
{
  "question": "Should the local-first no-phone-home claim be a test, not an adjective?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": {
    "pair_id": "4d3a3b93-a793-5ad9-835b-c0a30d8aa030",
    "commitment": "Seven mutations, all red.",
    "reason": "countersign no longer freshening a pair; retired pairs listed as overdue; the tail flag ignoring --expected-head; every entry marked as the tail; an undated entry defaulting to now rather than being skipped; ageing over a chain that fails verification; and the file growing a score multiplier. The last is the one worth naming — it is the design §3 exists instead of, so a test that could not see it arrive would be decoration.",
    "verifier": "",
    "sealed": false,
    "matched_question": "How was the listing shown to be a gate rather than a description?"
  },
  "match": "fuzzy",
  "similarity": 0.554
}
```

### Should collisions_at_bar in demo/the_dogfooding.py be sped up with early bail?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should collisions_at_bar in demo/the_dogfooding.py be sped up with early bail? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should collisions_at_bar in demo/the_dogfooding.py be sped up with early bail?",
    "target": "",
    "state": "pending",
    "mark": "!",
    "tier": 0,
    "engine": "offline-tm",
    "confidence": 0.0,
    "meta": {}
  },
  "verified": false,
  "matches": [],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should collisions_at_bar in demo/the_dogfooding.py be sped up with early bail? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should collisions_at_bar in demo/the_dogfooding.py be sped up with early bail? --from decision --to decision`

```json
{
  "normalized": "should collisions_at_bar in demothe_dogfoodingpy be sped up with early bail",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.444,
      "status": "draft",
      "servable": false,
      "id": "fd838c8c-1e2d-5f12-a176-c62f9268b950",
      "source_text": "Should Curator.list() be renamed to avoid shadowing the builtin?",
      "target_text": "Renamed to `Curator.browse()`. The old `list()` is kept as a deprecated alias that delegates to `browse()`, so existing callers keep working. All internal call sites updated.",
      "verifier": ""
    },
    {
      "similarity": 0.44,
      "status": "draft",
      "servable": false,
      "id": "70f7a894-af78-591c-a4c7-07d95880889d",
      "source_text": "How should collisions_at_bar be sped up so the demo does not keep pushing against the CI timeout as the corpus grows?",
      "target_text": "Route by matcher shape. For a StringMatcher-shaped matcher (no `score()` method), a new `_collisions_via_ratio_bailout` fetches candidate rows once, and for each decision uses SequenceMatcher's length-ratio and quick_ratio as O(1) and O(N) upper bounds respectively; a candidate whose upper bound is below memory.SEAL_THRESHOLD (0.92) is skipped before the expensive `ratio()` call. Local measurement on the 532-row dogfood corpus: 46.6s → ~1.3s for the collisions function; 82s → 23s for the whole demo. For a `score()`-based matcher (DefectMatcher, semantic backends), the upper bounds do not apply — the dispatcher falls back to `_collisions_via_lookup` which preserves the original N × memory.lookup path. The public entry point `collisions_at_bar` picks between them via `uses_raw_score(matcher)`. Output shape preserved: sorted by decision, then by similarity descending within a decision, capped at 50 per decision to match `memory.lookup(limit=50)`'s truncation; similarity rounded to 3 decimals as `memory.lookup` does. Two tests hold this down (tests/test_dogfooding_collisions.py): byte-for-byte equivalence on a controlled fixture, and a synthetic-corpus test asserting fast finds ≥ what slow finds AND runs faster.",
      "verifier": ""
    },
    {
      "similarity": 0.412,
      "status": "draft",
      "servable": false,
      "id": "979916a0-8b28-5888-ab51-644cab72ce6b",
      "source_text": "How is 'this container is not reading my Drive corpus' enforced?",
      "target_text": "permissions.deny for mcp__Google_Drive, mcp__Gmail and mcp__Google_Calendar in the checked-in .claude/settings.json.",
      "verifier": ""
    },
    {
      "similarity": 0.411,
      "status": "draft",
      "servable": false,
      "id": "5ed41de6-4937-5e86-a67b-02957293146d",
      "source_text": "Should constraints_on do fuzzy matching when exact-norm match fails?",
      "target_text": "Yes — constraints_on now accepts a fuzzy_bar parameter. When exact-norm match via memory_find fails and fuzzy_bar is set (and >0), it scans all candidates with the matcher and returns the highest-scoring one above the bar. The result dict now includes 'match' ('exact'|'fuzzy'|'none') and 'similarity' fields so callers can see how the match was made. A fuzzy match also includes 'matched_question' in the live dict so the caller sees the actual stored question.",
      "verifier": ""
    },
    {
      "similarity": 0.403,
      "status": "draft",
      "servable": false,
      "id": "327dd355-7c13-5616-bb60-59651d7c6e37",
      "source_text": "How should undocumented WILLOW_* env vars in _fleet_paths.py be handled?",
      "target_text": "Document WILLOW_20_REPO and WILLOW_CONSTITUTION_CASES in docs/local-fleet.md alongside the existing JELES_REPO and WILLOW_CHARTER_REPO entries. Add docs/local-fleet.md to the test_docs.py DOCS whitelist so the reverse gate (code var → docs) covers it. Exempt local-fleet.md from the forward gate (docs var → code) because it documents fleet-wide vars (WILLOW_STORE_ROOT, WILLOW_PGP_FINGERPRINT) that belong to willow-mcp, not to this codebase.",
      "verifier": ""
    },
    {
      "similarity": 0.4,
      "status": "draft",
      "servable": false,
      "id": "21599bde-dd91-5eed-bd51-16bf9c3221ec",
      "source_text": "How was the collision resolved once it was noticed?",
      "target_text": "Yield, don't fight for the number. #108 claimed 0118 first and was the older PR, so this session renumbered its own decision 0118 -> 0119, and #108 kept 0118. Merge order was #108 first (older, a boot fix that helps every session), then this branch rebased onto it and rebuilt the derived store from the union of decision files (0117 triage, 0118 boot, 0119 matcher) — the one honest way to resolve a decisions.json/nestor.db conflict, since they are derived, not authored. Both PRs' changes were verified to coexist (test_hook_wiring + before_build + triage all green) before either was trusted.",
      "verifier": ""
    },
    {
      "similarity": 0.4,
      "status": "draft",
      "servable": false,
      "id": "1b7b2930-ad3c-5a76-96dd-015d022735e4",
      "source_text": "Should README, IDEAS.md, and docs count strings be updated when the underlying code adds a view or tool?",
      "target_text": "Updated README view table from four to seven (added Signals, Graph, Triage rows). Updated MCP tool count from seven to eight in README, IDEAS.md, and docs/drafts/mcp-resources-prompts.md (nestor_prefs was missing). Updated ui.py docstring from five to seven views. Corrected shoebox gap count in project-layout.md from five open to three open, two closed. Removed duplicate paragraph in README (copy-paste leftover).",
      "verifier": ""
    },
    {
      "similarity": 0.397,
      "status": "draft",
      "servable": false,
      "id": "fed262ac-bce2-533c-96ea-65f346564514",
      "source_text": "Should the corpus extractors read the decision record in docs/dogfood/decisions/*.json?",
      "target_text": "No. The decision files are out of corpus scope by design. The dogfood store is its own store with its own builder (scripts/dogfood_store.py + dogfood_common.py), reading the same checkout through a separate path. Documented in the module docstring of scripts/corpus/common.py, citing docs/two-stores.md for the boundary.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.444, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should collisions_at_bar in demo/the_dogfooding.py be sped up with early bail? --source-lang decision --target-lang decision`

```json
{
  "question": "Should collisions_at_bar in demo/the_dogfooding.py be sped up with early bail?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Should Nestor have a policy-audience one-pager distinct from the operator guide?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should Nestor have a policy-audience one-pager distinct from the operator guide? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should Nestor have a policy-audience one-pager distinct from the operator guide?",
    "target": "",
    "state": "pending",
    "mark": "!",
    "tier": 0,
    "engine": "offline-tm",
    "confidence": 0.0,
    "meta": {}
  },
  "verified": false,
  "matches": [],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should Nestor have a policy-audience one-pager distinct from the operator guide? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should Nestor have a policy-audience one-pager distinct from the operator guide? --from decision --to decision`

```json
{
  "normalized": "should nestor have a policyaudience onepager distinct from the operator guide",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.49,
      "status": "draft",
      "servable": false,
      "id": "f0e8fca8-3658-5957-960e-7340a4e1ccb3",
      "source_text": "Is Nestor a specialist in willow-mcp's registry, or an operator-local seat?",
      "target_text": "Operator-local. Its manifest is written to $WILLOW_HOME/mcp_apps/nestor/ by the stand-up script and never compiled from the registry.",
      "verifier": ""
    },
    {
      "similarity": 0.48,
      "status": "draft",
      "servable": false,
      "id": "8aa974da-b6b4-556c-aef9-4a1d60764a62",
      "source_text": "Should the socket interceptor be a globally-applied autouse fixture across the whole test suite?",
      "target_text": "No. It is per-test opt-in via the ``no_inet_connect`` fixture parameter. Some tests deliberately exercise network-adjacent code (client-signed seals with a real WebCrypto shim, semantic-matcher smoke tests behind an extras gate) and would false-fail. The scope is the default-read-path tests in this one file plus, in the future, any other test file that wants the same guarantee for its surface.",
      "verifier": ""
    },
    {
      "similarity": 0.474,
      "status": "draft",
      "servable": false,
      "id": "d8350d51-98e4-5baa-9c1a-e80c407f81d8",
      "source_text": "How does the fixture avoid sealing on the operator's behalf?",
      "target_text": "seal requires --verifier on the command line: no default, no $USER fallback, and no route to sealed from draft().",
      "verifier": ""
    },
    {
      "similarity": 0.465,
      "status": "draft",
      "servable": false,
      "id": "a313244b-108a-5755-8d28-a98e4dad454b",
      "source_text": "Should nestor_check also get the store-aware fallback?",
      "target_text": "Not in this change. nestor_check uses a single --domain (default 'value'), not a source/target pair, and the CLI's cmd_check does not use _ask_domain either — the domains are asymmetric. Bringing check into the fold is a separate design question: what does 'the store's largest single-domain' mean, and should a check against a baseline silently switch domains? Left as a follow-up if a user hits the gap.",
      "verifier": ""
    },
    {
      "similarity": 0.463,
      "status": "draft",
      "servable": false,
      "id": "ee4708bc-bd24-5cfe-af33-0846e4a0b32c",
      "source_text": "Should the ledger's `passage` entry record the warrant kinds?",
      "target_text": "Yes, tier 1 only. A warrant attached tomorrow is not one this answer went out with, and reading the pair's warrants later tells you what it holds now, never what it held when the answer was served.",
      "verifier": ""
    },
    {
      "similarity": 0.458,
      "status": "draft",
      "servable": false,
      "id": "dfa5e4fe-3f9d-549a-9fbc-42402433c870",
      "source_text": "Should the demo-store artifacts under docs/ move to demo/?",
      "target_text": "Moved docs/llm-only-joke/, docs/llm-only-jokes.md, and docs/ideas-store/ to demo/. Updated internal paths in each store's README, .gitignore, and project-layout.md. Historical references in decision records and findings left unchanged.",
      "verifier": ""
    },
    {
      "similarity": 0.453,
      "status": "draft",
      "servable": false,
      "id": "37b53fc4-e73a-53ba-a598-50666dd5b90e",
      "source_text": "Should `nestor triage` be a CLI subcommand alongside `nestor ask`, `nestor calibrate`, etc.?",
      "target_text": "Yes. `nestor triage` runs the triage (group + supersede) over the dogfood corpus and prints the report. Supports `--matcher string|semantic|ollama`, `--bar`, `--calibrate`, and `--json`. Read-only — proposes nothing, seals nothing. The standalone script (`scripts/decision_triage.py`) stays for its `--propose` mode; the CLI subcommand covers the common path.",
      "verifier": ""
    },
    {
      "similarity": 0.448,
      "status": "draft",
      "servable": false,
      "id": "6353d952-1ea9-57b9-b5ab-b708c6660862",
      "source_text": "Should Nestor support `python -m nestor` invocation?",
      "target_text": "Added `nestor/__main__.py` — a three-line module that delegates to `nestor.cli:main`. Filled in missing help text for positional arguments (text, surface, label, observed) and the --engine/--domain flags.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.49, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should Nestor have a policy-audience one-pager distinct from the operator guide? --source-lang decision --target-lang decision`

```json
{
  "question": "Should Nestor have a policy-audience one-pager distinct from the operator guide?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Should nestor demo have a --seed policy option with es and pt sealed pairs?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should nestor demo have a --seed policy option with es and pt sealed pairs? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should nestor demo have a --seed policy option with es and pt sealed pairs?",
    "target": "",
    "state": "pending",
    "mark": "!",
    "tier": 0,
    "engine": "offline-tm",
    "confidence": 0.0,
    "meta": {}
  },
  "verified": false,
  "matches": [],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should nestor demo have a --seed policy option with es and pt sealed pairs? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should nestor demo have a --seed policy option with es and pt sealed pairs? --from decision --to decision`

```json
{
  "normalized": "should nestor demo have a seed policy option with es and pt sealed pairs",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.478,
      "status": "draft",
      "servable": false,
      "id": "b4019821-ee30-5bd2-bbd9-bee6405fcb6d",
      "source_text": "Should nestor match use the same domain fallback as nestor ask?",
      "target_text": "Applied _ask_domain() to cmd_match, mirroring cmd_ask. Changed match's --from/--to parser defaults from 'en'/'es' to None so _ask_domain can detect 'not specified' and fall back to the store's largest domain. Without this, `nestor match` on a decision→decision store silently queried the empty en→es domain and reported 0 candidates.",
      "verifier": ""
    },
    {
      "similarity": 0.474,
      "status": "draft",
      "servable": false,
      "id": "dcf85c1d-79df-54ac-98e3-6d7b5e92a67c",
      "source_text": "Should a hazard's severity scale with how exposed a character is?",
      "target_text": "No. Severity belongs to the physical event and is the same for everyone standing in it; exposure controls how many separate incidents a character is in. A collapsing wall does not hit a trained person more gently.",
      "verifier": ""
    },
    {
      "similarity": 0.466,
      "status": "draft",
      "servable": false,
      "id": "b0f7d69f-f101-53d2-8043-f251aebf94cb",
      "source_text": "Should init_db mark a connection schema-ready?",
      "target_text": "No. Only memory_init sets the flag.",
      "verifier": ""
    },
    {
      "similarity": 0.464,
      "status": "draft",
      "servable": false,
      "id": "74f8fe6e-b96e-5fd9-9c77-9a909cb4f3f0",
      "source_text": "What should actually run for a change that touches only docs and decision files?",
      "target_text": "test_docs.py, test_open_findings.py and test_dogfood_store.py, plus dogfood_store.py --verify. Measured: 46 tests in 7.2s against 979 in roughly 100s, with the digest gate at 0.6s. Those are the only tests that read the files such a change touches.",
      "verifier": ""
    },
    {
      "similarity": 0.455,
      "status": "draft",
      "servable": false,
      "id": "37b53fc4-e73a-53ba-a598-50666dd5b90e",
      "source_text": "Should `nestor triage` be a CLI subcommand alongside `nestor ask`, `nestor calibrate`, etc.?",
      "target_text": "Yes. `nestor triage` runs the triage (group + supersede) over the dogfood corpus and prints the report. Supports `--matcher string|semantic|ollama`, `--bar`, `--calibrate`, and `--json`. Read-only — proposes nothing, seals nothing. The standalone script (`scripts/decision_triage.py`) stays for its `--propose` mode; the CLI subcommand covers the common path.",
      "verifier": ""
    },
    {
      "similarity": 0.451,
      "status": "draft",
      "servable": false,
      "id": "f0e8fca8-3658-5957-960e-7340a4e1ccb3",
      "source_text": "Is Nestor a specialist in willow-mcp's registry, or an operator-local seat?",
      "target_text": "Operator-local. Its manifest is written to $WILLOW_HOME/mcp_apps/nestor/ by the stand-up script and never compiled from the registry.",
      "verifier": ""
    },
    {
      "similarity": 0.445,
      "status": "draft",
      "servable": false,
      "id": "00c58cb7-e12c-531e-8ecf-40ab85bbb24e",
      "source_text": "Should the store carry a schema version (PRAGMA user_version), which §6.31 reserved as a decision to be argued, not stamped inside another change?",
      "target_text": "Yes — ratified as of 0.2.0. The store now carries user_version = SCHEMA_VERSION (1), with an ordered forward-migration ladder (empty today) and a fail-closed refusal of a newer-than-known file (StoreSchemaTooNewError). This is exactly the 'schema generation in the database' §6.31 named as the STRONG fix for the §6.8 warm-connection hazard (a pooled connection skips a migration it did not have when opened). §6.31's own text said the store half 'touches no hash chain, so the argument it needs is small' — this record is that small argument, made. Not extended to the ledger: a hash chain cannot be re-hashed under new rules, so its format is already frozen by its first entry and versioning it is a separate, larger decision that stays open.",
      "verifier": ""
    },
    {
      "similarity": 0.444,
      "status": "draft",
      "servable": false,
      "id": "f43ea970-45c0-5ed0-b6fe-587a768b38ca",
      "source_text": "Does the package satisfy the constitution it was extracted from?",
      "target_text": "2 satisfied, 2 differently, 1 not applicable, 0 failing — measured by live probes, not by reading.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.478, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should nestor demo have a --seed policy option with es and pt sealed pairs? --source-lang decision --target-lang decision`

```json
{
  "question": "Should nestor demo have a --seed policy option with es and pt sealed pairs?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Should there be a ninety-second transcript walk-through of the covenant?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should there be a ninety-second transcript walk-through of the covenant? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should there be a ninety-second transcript walk-through of the covenant?",
    "target": "",
    "state": "pending",
    "mark": "!",
    "tier": 0,
    "engine": "offline-tm",
    "confidence": 0.0,
    "meta": {}
  },
  "verified": false,
  "matches": [],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should there be a ninety-second transcript walk-through of the covenant? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should there be a ninety-second transcript walk-through of the covenant? --from decision --to decision`

```json
{
  "normalized": "should there be a ninetysecond transcript walkthrough of the covenant",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.481,
      "status": "draft",
      "servable": false,
      "id": "82933565-62fa-5658-a2c5-08f41a003f91",
      "source_text": "Should the fixture stay one file as it grows to eleven beats?",
      "target_text": "Yes. One person, one file, three recipes.",
      "verifier": ""
    },
    {
      "similarity": 0.475,
      "status": "draft",
      "servable": false,
      "id": "f9ccdcb1-8b9a-5d8f-9785-4146527cab77",
      "source_text": "Should seal staleness be a decaying weight column?",
      "target_text": "No.",
      "verifier": ""
    },
    {
      "similarity": 0.471,
      "status": "draft",
      "servable": false,
      "id": "2137482f-36a6-56a1-939a-b5d4428994ee",
      "source_text": "Where should the code box governing this session live, so the rule survives the container?",
      "target_text": "In the repository. First as scripts/dogfood_codebox.py with a committed store; migrated on rebase to this file, built by scripts/dogfood_store.py --rebuild.",
      "verifier": ""
    },
    {
      "similarity": 0.464,
      "status": "draft",
      "servable": false,
      "id": "b0c3d420-ed1a-512a-8e7b-3bfaa85c79e1",
      "source_text": "Should the §6.25 init_db bug be fixed inside the §6.8 commit?",
      "target_text": "No. Filed as its own entry, unfixed.",
      "verifier": ""
    },
    {
      "similarity": 0.46,
      "status": "draft",
      "servable": false,
      "id": "ee4708bc-bd24-5cfe-af33-0846e4a0b32c",
      "source_text": "Should the ledger's `passage` entry record the warrant kinds?",
      "target_text": "Yes, tier 1 only. A warrant attached tomorrow is not one this answer went out with, and reading the pair's warrants later tells you what it holds now, never what it held when the answer was served.",
      "verifier": ""
    },
    {
      "similarity": 0.458,
      "status": "draft",
      "servable": false,
      "id": "480bdb2e-6a9c-583f-a0db-9fb86968c6bb",
      "source_text": "The client's fixture — a scripted walk-through like shoebox.py, or something else?",
      "target_text": "Something else. demo/big_jim.py is a standing desk driven a command at a time, not an argument with an ending.",
      "verifier": ""
    },
    {
      "similarity": 0.441,
      "status": "draft",
      "servable": false,
      "id": "ee104159-308c-5b01-b275-b9f009c9e14e",
      "source_text": "Should each idea be built in its own git worktree?",
      "target_text": "No, and I said so rather than performing it.",
      "verifier": ""
    },
    {
      "similarity": 0.43,
      "status": "draft",
      "servable": false,
      "id": "8db68694-a3e3-5ad9-b742-fb1f31438f07",
      "source_text": "Should the one-directional rule be relaxed so seals can flow back into the committed store?",
      "target_text": "Proposed: no. Whatever the fix is, the `.db` must stay derivable from text a reviewer read.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.481, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should there be a ninety-second transcript walk-through of the covenant? --source-lang decision --target-lang decision`

```json
{
  "question": "Should there be a ninety-second transcript walk-through of the covenant?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Should Nestor ship a multi-language matcher story for en es fr ar?

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json ask Should Nestor ship a multi-language matcher story for en es fr ar? --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Should Nestor ship a multi-language matcher story for en es fr ar?",
    "target": "",
    "state": "pending",
    "mark": "!",
    "tier": 0,
    "engine": "offline-tm",
    "confidence": 0.0,
    "meta": {}
  },
  "verified": false,
  "matches": [],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json resolve Should Nestor ship a multi-language matcher story for en es fr ar? --domain entity`

```json
{
  "canonical": null,
  "confidence": 0.0,
  "sealed": false,
  "provenance": {
    "draft": true,
    "suggestion": null
  },
  "domain": "entity",
  "verified": false,
  "candidates": [],
  "threshold": 0.92
}
```

#### `match` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json match Should Nestor ship a multi-language matcher story for en es fr ar? --from decision --to decision`

```json
{
  "normalized": "should nestor ship a multilanguage matcher story for en es fr ar",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.483,
      "status": "draft",
      "servable": false,
      "id": "36e362b3-b4f4-5019-bedc-12ac22c28967",
      "source_text": "Does adding --matcher change the string default or the bar?",
      "target_text": "No. `string` stays the offline default and 0.55 stays its measured knee. `semantic`/`ollama` are opt-in, load through the existing `nestor.answer.load_matcher` (persist=False, so a triage run never writes an embedding cache), and the CLI prints a stderr note that 0.55 is the string knee and their cosine bar must be re-found with --calibrate (unrelated text scores 0.7-0.8 on nomic, so the char bar is far too low). The build box cannot reach model weights, so the semantic path is wired and unit-tested for the prune gating but exercised on a host that has Ollama — build here, run there.",
      "verifier": ""
    },
    {
      "similarity": 0.482,
      "status": "draft",
      "servable": false,
      "id": "6353d952-1ea9-57b9-b5ab-b708c6660862",
      "source_text": "Should Nestor support `python -m nestor` invocation?",
      "target_text": "Added `nestor/__main__.py` — a three-line module that delegates to `nestor.cli:main`. Filled in missing help text for positional arguments (text, surface, label, observed) and the --engine/--domain flags.",
      "verifier": ""
    },
    {
      "similarity": 0.473,
      "status": "draft",
      "servable": false,
      "id": "216b1da3-0848-546c-a333-4ec1a54ad884",
      "source_text": "How far does the matcher have to be threaded before the fix is real?",
      "target_text": "Past tier 1. Engine.translate takes a matcher, or the same response uses two.",
      "verifier": ""
    },
    {
      "similarity": 0.466,
      "status": "draft",
      "servable": false,
      "id": "37b53fc4-e73a-53ba-a598-50666dd5b90e",
      "source_text": "Should `nestor triage` be a CLI subcommand alongside `nestor ask`, `nestor calibrate`, etc.?",
      "target_text": "Yes. `nestor triage` runs the triage (group + supersede) over the dogfood corpus and prints the report. Supports `--matcher string|semantic|ollama`, `--bar`, `--calibrate`, and `--json`. Read-only — proposes nothing, seals nothing. The standalone script (`scripts/decision_triage.py`) stays for its `--propose` mode; the CLI subcommand covers the common path.",
      "verifier": ""
    },
    {
      "similarity": 0.455,
      "status": "draft",
      "servable": false,
      "id": "c6c3e7ec-fd63-5687-988b-f588dd0092d3",
      "source_text": "What does the matcher mirror — jeles' ranking, or its answering?",
      "target_text": "Its answering. NuggetMatcher implements containment-then-symmetry, not the loose ranking.",
      "verifier": ""
    },
    {
      "similarity": 0.446,
      "status": "draft",
      "servable": false,
      "id": "5ed41de6-4937-5e86-a67b-02957293146d",
      "source_text": "Should constraints_on do fuzzy matching when exact-norm match fails?",
      "target_text": "Yes — constraints_on now accepts a fuzzy_bar parameter. When exact-norm match via memory_find fails and fuzzy_bar is set (and >0), it scans all candidates with the matcher and returns the highest-scoring one above the bar. The result dict now includes 'match' ('exact'|'fuzzy'|'none') and 'similarity' fields so callers can see how the match was made. A fuzzy match also includes 'matched_question' in the live dict so the caller sees the actual stored question.",
      "verifier": ""
    },
    {
      "similarity": 0.442,
      "status": "draft",
      "servable": false,
      "id": "508c1dc7-4f98-52c9-adce-28e7c8dc0f5c",
      "source_text": "A custom matcher for source declarations?",
      "target_text": "No. Default StringMatcher.",
      "verifier": ""
    },
    {
      "similarity": 0.441,
      "status": "draft",
      "servable": false,
      "id": "dfa5e4fe-3f9d-549a-9fbc-42402433c870",
      "source_text": "Should the demo-store artifacts under docs/ move to demo/?",
      "target_text": "Moved docs/llm-only-joke/, docs/llm-only-jokes.md, and docs/ideas-store/ to demo/. Updated internal paths in each store's README, .gitignore, and project-layout.md. Historical references in decision records and findings left unchanged.",
      "verifier": ""
    }
  ],
  "reason": "closest of 534 candidate(s) is 0.483, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-lty2vs82/snapshot-nestor.db --json decision check Should Nestor ship a multi-language matcher story for en es fr ar? --source-lang decision --target-lang decision`

```json
{
  "question": "Should Nestor ship a multi-language matcher story for en es fr ar?",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

