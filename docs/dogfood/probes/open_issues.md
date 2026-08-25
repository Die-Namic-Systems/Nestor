# Nestor issue-probe report

*Read-only sweep of the meaning suite over a prompts file. See `docs/probing-the-store.md` for what each lens sees and does not.*

## Environment

- nestor binary: `/home/user/Nestor/.venv/bin/nestor`
- database: `/home/user/Nestor/docs/dogfood/nestor.db (via VACUUM INTO snapshot)`
- prompts file: `/home/user/Nestor/scripts/corpus/open_issues.txt` (16 prompts)
- source→target: `decision` → `decision`
- resolve domain: `entity`
- matcher: `(default)`

## Corpus-level lenses

### `stats` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db stats`

*stderr:*

```
/home/user/Nestor/nestor/curator.py:82: RuntimeWarning: NESTOR_SEAL_KEY not set — seal signatures are NOT verified; any 'sealed' row is trusted (Nestor#2). Set NESTOR_SEAL_KEY, or NESTOR_REQUIRE_SEAL_KEY=1 to fail closed.
  out["signature_valid"] = signing.seal_is_valid(
```

```
520 pair(s): 0 sealed, 520 draft
  domains: decision→decision (520)
  seal signatures: OFF — stored status is trusted
  ledger: ✓ no ledger yet
```

### `rejections` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json rejections`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db triage`

```
====================================================================
Decision triage  (proposal — nothing here is sealed)
====================================================================
decisions : 520
bar       : 0.55
groups    : 447
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

  (419 singleton group(s) suppressed)

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
still open       : 460

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
```

### `calibrate` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db calibrate --from decision --to decision --sample 0 --seed 1`

```
0 sealed pair(s) in decision→decision; sampled 0
  nothing sealed here yet — nothing to calibrate against.
```

### `evidence-report` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json evidence report --source-lang decision --target-lang decision`

```json
{
  "unevidenced_seals": [],
  "count": 0,
  "source_lang": "decision",
  "target_lang": "decision"
}
```


## Per-prompt lenses

### MCP server nestor_ask lacks store-aware domain fallback

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask MCP server nestor_ask lacks store-aware domain fallback --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "MCP server nestor_ask lacks store-aware domain fallback",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve MCP server nestor_ask lacks store-aware domain fallback --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match MCP server nestor_ask lacks store-aware domain fallback --from decision --to decision`

```json
{
  "normalized": "mcp server nestor_ask lacks storeaware domain fallback",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.534,
      "status": "draft",
      "servable": false,
      "id": "b4019821-ee30-5bd2-bbd9-bee6405fcb6d",
      "source_text": "Should nestor match use the same domain fallback as nestor ask?",
      "target_text": "Applied _ask_domain() to cmd_match, mirroring cmd_ask. Changed match's --from/--to parser defaults from 'en'/'es' to None so _ask_domain can detect 'not specified' and fall back to the store's largest domain. Without this, `nestor match` on a decision→decision store silently queried the empty en→es domain and reported 0 candidates.",
      "verifier": ""
    },
    {
      "similarity": 0.389,
      "status": "draft",
      "servable": false,
      "id": "79bc0de0-db30-552a-9d19-61f3bfc1c0d9",
      "source_text": "Which synapse skills are landed now, and which are held?",
      "target_text": "Landed four: verification, testing, debugging, autonomous-work-boundaries -- the ones that map 1:1 onto Nestor's load-bearing disciplines (don't overclaim, prove a guard can fail, fix surgically with evidence, know the propose/confirm line) and need the least adaptation. Held: finishing-branches, bug-capture, goal-oriented-development, worktree-cleanup -- they shell gh (this environment is GitHub-MCP only) and/or auto-open PRs (Nestor's standing rule is no PR unless asked), so they must be adapted before landing. Skipped: asset-churn-audit (game-asset tool, Nestor ships no binary art). thinking / writing-plans / executing-plans / code-review are a possible next tranche.",
      "verifier": ""
    },
    {
      "similarity": 0.387,
      "status": "draft",
      "servable": false,
      "id": "3b7efb9f-a844-5d6b-afeb-362bed858f05",
      "source_text": "How is 'never a conclusion' actually kept?",
      "target_text": "By the schema, not by the importer. `WARRANT_FIELDS` has no column a verdict could go in — no `verified`, no `verified_at`, no `holds` — so there is nothing for an import to set and nothing for a bundle to assert. The test asserts the absence over the landed row's own keys, so a future column that did hold a verdict fails it.",
      "verifier": ""
    },
    {
      "similarity": 0.385,
      "status": "draft",
      "servable": false,
      "id": "3e2c596f-a8dd-5155-acca-478ac7ef2606",
      "source_text": "§1.10(b): can a `constructed` warrant be minted locally at all?",
      "target_text": "Proposed: no. A constructed warrant stores a RECIPE and an EXPECTED DIGEST — what to run, against what input, what it must produce — and Nestor never marks it satisfied. It reports 'recomputable: here is how'; the reader who cares runs it. Nestor holds the recipe and not the verdict.",
      "verifier": ""
    },
    {
      "similarity": 0.384,
      "status": "draft",
      "servable": false,
      "id": "4eb307eb-438d-52d1-9a8d-6587ac7800e3",
      "source_text": "What can a Nestor SessionEnd hook actually do?",
      "target_text": "Warn and flush, never gate. Confirmed from the Claude Code hooks docs and the fleet's own code: SessionEnd cannot block termination and cannot inject context (exit 2 only shows stderr to the user; there is no next turn). So session_end.py does two side-effect/advisory jobs: `dogfood_store.py --verify` and, on drift, a stderr reminder to rebuild before pushing (which also fails on a sealed row, doubling as a covenant check); and a WAL checkpoint of the gitignored dev store (never the committed dogfood store, whose checkpoint the rebuild script owns). It always exits 0, warnings to stderr. Anything that must block stays on the Stop turn-gate (before_stop.py). It is excluded from the gate-proving harness's coverage pin because it is not a gate.",
      "verifier": ""
    },
    {
      "similarity": 0.379,
      "status": "draft",
      "servable": false,
      "id": "eb127497-6b67-538b-8499-8f18a862e9a1",
      "source_text": "Bump the bundle version to 4, or add `warrants` beside the digest?",
      "target_text": "Bump, and fold `warrants` into the digest gated on version >= 4, exactly as evidence was gated at 3 and `reopen_when` at 2. The three bundles checked into this repository keep verifying byte-for-byte, and they are not all one version — docs/research-corpus is v3, docs/llm-only-joke and docs/ideas-store are v2, which is the point: two gates, both still holding, and each verified by running verify_bundle over the actual file rather than by assuming.",
      "verifier": ""
    },
    {
      "similarity": 0.373,
      "status": "draft",
      "servable": false,
      "id": "6353d952-1ea9-57b9-b5ab-b708c6660862",
      "source_text": "Should Nestor support `python -m nestor` invocation?",
      "target_text": "Added `nestor/__main__.py` — a three-line module that delegates to `nestor.cli:main`. Filled in missing help text for positional arguments (text, surface, label, observed) and the --engine/--domain flags.",
      "verifier": ""
    },
    {
      "similarity": 0.368,
      "status": "draft",
      "servable": false,
      "id": "809f89a9-1469-52c4-b99b-8ca2102c8b16",
      "source_text": "Is there enough in the store for Nestor to help build Nestor's own ideas?",
      "target_text": "Not a single answer — it depends on the question's shape, which is what the measurement showed and the first answer missed. For a probe carrying distinctive vocabulary ('embedder', 'extractor', 'zero rows') the correct row already ranks 1 of 263 and is waiting only on a human signature and a calibrated bar. For a short generic question ('Should I trust a licence a model told me?') the correct row sits at rank 110 and no threshold rescues it.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.534, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check MCP server nestor_ask lacks store-aware domain fallback --source-lang decision --target-lang decision`

```json
{
  "question": "MCP server nestor_ask lacks store-aware domain fallback",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### turn the capability probe's findings into runnable code

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask turn the capability probe's findings into runnable code --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "turn the capability probe's findings into runnable code",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve turn the capability probe's findings into runnable code --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match turn the capability probe's findings into runnable code --from decision --to decision`

```json
{
  "normalized": "turn the capability probes findings into runnable code",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.467,
      "status": "draft",
      "servable": false,
      "id": "160add96-955e-55dc-be9b-8138c6b7bcad",
      "source_text": "Should the test suite depend on jeles being installed?",
      "target_text": "No. Eight tests run on plain dicts; the live-corpus one uses importorskip.",
      "verifier": ""
    },
    {
      "similarity": 0.449,
      "status": "draft",
      "servable": false,
      "id": "4b8f411a-f89f-5457-887c-93fe16af1838",
      "source_text": "How should the env-var pinning in home_init be handled?",
      "target_text": "Moved the `os.environ` mutation from the private `_resolve_home` (now a pure resolver) to the public `ensure_home_layout`, where the pinning is documented in the docstring and visible to callers. Internal calls thread the `home` parameter explicitly.",
      "verifier": ""
    },
    {
      "similarity": 0.442,
      "status": "draft",
      "servable": false,
      "id": "97750f35-7494-58b2-8433-3b6b61a70dbd",
      "source_text": "Did the sweep find anything, or was it a clean bill?",
      "target_text": "It found a real drift on its first run, in the script whose docstring exists to explain that exact distinction.",
      "verifier": ""
    },
    {
      "similarity": 0.426,
      "status": "draft",
      "servable": false,
      "id": "4988f34f-0393-59b1-9391-1112325e5c84",
      "source_text": "What is the finding, as against the story?",
      "target_text": "There is no per-domain verifier policy. Measured: add_pair(status='sealed', verifier='anybody-at-all') is accepted and is_verified_seal returns True.",
      "verifier": ""
    },
    {
      "similarity": 0.421,
      "status": "draft",
      "servable": false,
      "id": "2aa45d12-ce68-5257-b588-ea0a17121e85",
      "source_text": "When the agent log itself was fed to Nestor, what was the key?",
      "target_text": "The claim, with the entry number in `origin` pinned to a commit.",
      "verifier": ""
    },
    {
      "similarity": 0.418,
      "status": "draft",
      "servable": false,
      "id": "b8217e9a-42ce-5392-bb89-5ba92a03bb37",
      "source_text": "The remaining two feeds — what are they?",
      "target_text": "willow-2.0's 11 migrations (change -> stated intent) and willow-1.9's 35 plans (plan -> what it committed to).",
      "verifier": ""
    },
    {
      "similarity": 0.41,
      "status": "draft",
      "servable": false,
      "id": "4240bc21-46ef-55be-8664-f5eed0aabaea",
      "source_text": "Both halves in one table?",
      "target_text": "Yes — chat IS authority, chat IS NOT evidence, side by side.",
      "verifier": ""
    },
    {
      "similarity": 0.408,
      "status": "draft",
      "servable": false,
      "id": "09496732-bda9-574a-995c-7d60f46e1e91",
      "source_text": "The move rewrote the guide's opening. Restored?",
      "target_text": "Yes. The 2026-08-05 incident sentence is back, and a paragraph saying plainly that this file is not auto-loaded.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.467, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check turn the capability probe's findings into runnable code --source-lang decision --target-lang decision`

```json
{
  "question": "turn the capability probe's findings into runnable code",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Evidence subsystem is inert: nothing in cascade, provenance, or check reads it

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask Evidence subsystem is inert: nothing in cascade, provenance, or check reads it --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Evidence subsystem is inert: nothing in cascade, provenance, or check reads it",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve Evidence subsystem is inert: nothing in cascade, provenance, or check reads it --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match Evidence subsystem is inert: nothing in cascade, provenance, or check reads it --from decision --to decision`

```json
{
  "normalized": "evidence subsystem is inert nothing in cascade provenance or check reads it",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.457,
      "status": "draft",
      "servable": false,
      "id": "383a1615-ac21-5b21-9d0a-1739d515da5e",
      "source_text": "Is evidence inside the integrity digest, or beside it?",
      "target_text": "Inside, for version 3 and up only. digest() gains an evidence argument and folds evidence rows into the hashed payload when version >= 3; for versions 1 and 2 the payload is byte-identical to before, so an old bundle recomputes to the same hash. A test tampers an exported evidence row and asserts verify_bundle reports a digest mismatch.",
      "verifier": ""
    },
    {
      "similarity": 0.443,
      "status": "draft",
      "servable": false,
      "id": "3766698c-6368-5ab9-8cf6-0bb84d5076e9",
      "source_text": "Does anything this exercise produced get sealed?",
      "target_text": "No. 18,924 rows, every one a draft, including 880 rejections the operator themselves recorded.",
      "verifier": ""
    },
    {
      "similarity": 0.411,
      "status": "draft",
      "servable": false,
      "id": "cfbb12bf-e1b6-5e7e-8895-43758d03ca4e",
      "source_text": "How wide is the net, given a false positive gets the whole guard deleted?",
      "target_text": "Narrow on purpose. rm -r denies only broad targets (/, ~, ., *, a shallow system path); rm -rf .worktrees/tmp passes. git push --force-with-lease passes (Nestor uses it) and only a bare --force is denied. pytest, ruff, cat README.md, > /dev/null all pass, each pinned by an allow-test.",
      "verifier": ""
    },
    {
      "similarity": 0.41,
      "status": "draft",
      "servable": false,
      "id": "a85f5f75-7a2a-5c65-81ab-9fa2ead6d888",
      "source_text": "How is 'running under coverage' detected reliably?",
      "target_text": "By coverage's own `Coverage.current()` API when the module is present, with `sys.gettrace() is not None` as a fallback. gettrace alone is not enough: coverage's C tracer can leave it None, so the API check is primary and gettrace covers debuggers and the pure-Python tracer. When coverage is not installed (the local .venv), neither fires and the timing assertion runs as before — verified: `_instrumented()` is False bare and True under `sys.settrace`, and the smoke passes locally in ~18s with the assertion live.",
      "verifier": ""
    },
    {
      "similarity": 0.405,
      "status": "draft",
      "servable": false,
      "id": "12b33aeb-0a9d-51d3-a96c-085883a59378",
      "source_text": "Two desks in one process share cascade's ledger path. Does the fixture care?",
      "target_text": "Yes — at_desk() switches it at every crossing, and a test reads both files.",
      "verifier": ""
    },
    {
      "similarity": 0.405,
      "status": "draft",
      "servable": false,
      "id": "378a12ae-4b12-59a1-98c8-52cf14beda7d",
      "source_text": "Before building the grouping, was the box searched for what already exists?",
      "target_text": "Yes — and only after the operator stopped a first attempt that jumped straight to building. Two look-sees (the fleet on disk; the open internet) ran first, exactly the discipline the before_build hook (#105) now enforces. They converged: grouping is an assembly of shipped parts (~100 lines), not a new capability, and building the clustering primitive fresh would have repeated the rediscovery `the-house-already-knew.md` documents. The triage re-lands the shapes over Nestor's own matchers rather than importing willow-mcp (unavailable, and heavy).",
      "verifier": ""
    },
    {
      "similarity": 0.404,
      "status": "draft",
      "servable": false,
      "id": "e05b512d-995a-5119-bdc2-a9a973a0f7bc",
      "source_text": "Making a single-choice subcommand verb optional broke `nestor decision`. Keep the convenience or the safety?",
      "target_text": "Safety. The `db` verb stays optional (`nestor db` == `nestor db checkpoint`) because `db` has no other positional. `decision` reverts to a required verb, because it has a trailing required `question`: with the verb optional, argparse gives a lone token to `question`, so `nestor decision check` parsed as question='check' and silently ran a real check on the literal word instead of erroring for the missing question -- defeating cmd_decision's own 'a question is required' guard. A test now pins that `nestor decision check` (verb, no question) errors rather than runs.",
      "verifier": ""
    },
    {
      "similarity": 0.4,
      "status": "draft",
      "servable": false,
      "id": "97750f35-7494-58b2-8433-3b6b61a70dbd",
      "source_text": "Did the sweep find anything, or was it a clean bill?",
      "target_text": "It found a real drift on its first run, in the script whose docstring exists to explain that exact distinction.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.457, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check Evidence subsystem is inert: nothing in cascade, provenance, or check reads it --source-lang decision --target-lang decision`

```json
{
  "question": "Evidence subsystem is inert: nothing in cascade, provenance, or check reads it",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Missing guard: cross-session collision awareness — notice another agent is in the room

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask Missing guard: cross-session collision awareness — notice another agent is in the room --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Missing guard: cross-session collision awareness — notice another agent is in the room",
    "target": "An advisory UserPromptSubmit hook (hooks/before_propose.py), sibling to before_build (#105), fires only on a propose/mint/open-a-PR prompt, scans local git only, and fails CLOSED to UNKNOWN -- never a false 'clear'.",
    "state": "draft",
    "mark": "~",
    "tier": 2,
    "engine": "offline-tm",
    "confidence": 0.45,
    "meta": {}
  },
  "verified": false,
  "matches": [
    {
      "similarity": 0.563,
      "status": "draft",
      "servable": false,
      "id": "26556f0e-7039-504a-aadf-43c2b8d8aff0",
      "source_text": "Cross-session collision awareness (#111) -- where does it live, and what happens when it cannot tell?",
      "target_text": "An advisory UserPromptSubmit hook (hooks/before_propose.py), sibling to before_build (#105), fires only on a propose/mint/open-a-PR prompt, scans local git only, and fails CLOSED to UNKNOWN -- never a false 'clear'.",
      "verifier": "",
      "warrant_kinds": []
    }
  ],
  "threshold": 0.92
}
```

#### `resolve` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve Missing guard: cross-session collision awareness — notice another agent is in the room --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match Missing guard: cross-session collision awareness — notice another agent is in the room --from decision --to decision`

```json
{
  "normalized": "missing guard crosssession collision awareness notice another agent is in the room",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.563,
      "status": "draft",
      "servable": false,
      "id": "26556f0e-7039-504a-aadf-43c2b8d8aff0",
      "source_text": "Cross-session collision awareness (#111) -- where does it live, and what happens when it cannot tell?",
      "target_text": "An advisory UserPromptSubmit hook (hooks/before_propose.py), sibling to before_build (#105), fires only on a propose/mint/open-a-PR prompt, scans local git only, and fails CLOSED to UNKNOWN -- never a false 'clear'.",
      "verifier": ""
    },
    {
      "similarity": 0.434,
      "status": "draft",
      "servable": false,
      "id": "708c5afa-d1bf-5897-b23e-fede34daca2b",
      "source_text": "The action publishes no release tags. Pin it how?",
      "target_text": "Referenced at @main, with a comment in the workflow stating the residual risk and that it should be pinned to a reviewed commit SHA once one is chosen. actions/checkout is pinned at @v7 to match the existing tests.yml rather than introduce a second version.",
      "verifier": ""
    },
    {
      "similarity": 0.419,
      "status": "draft",
      "servable": false,
      "id": "5699d3b2-6a21-5ae1-aeba-ce3691768d11",
      "source_text": "Its gap() assertions are about somebody else's code. Is that different?",
      "target_text": "Yes, and the message says so: 'CHANGED ON THEIR SIDE — re-read jeles and update both'.",
      "verifier": ""
    },
    {
      "similarity": 0.418,
      "status": "draft",
      "servable": false,
      "id": "30171704-fea2-5ec7-aebb-0587e726b0c3",
      "source_text": "What is the missing guard the 0118 collision exposed?",
      "target_text": "Cross-session collision awareness — the sibling of the anti-rediscovery hook (#105). #105 asks 'what already exists before you build'; this asks 'who else is building right now'. The signals were structural and present the whole time: another open PR on the same base branch, a duplicate decision number in flight (the number-before-PR hazard 0054 names), the same derived artifacts rebuilt on a sibling claude/* branch. A guard would surface those before a number is minted or a PR opened — advisory and best-effort (it cannot serialize two agents, only make the collision loud), part seat-reminder ('you may not be the only agent — read the meta-data') and part concrete scan (open PRs, next free decision number, overlapping changed files). Recorded in issue #111 and IDEAS §7.5; not built, by the operator's call.",
      "verifier": ""
    },
    {
      "similarity": 0.413,
      "status": "draft",
      "servable": false,
      "id": "782fa219-0e20-520d-91fa-7f70a8e22b05",
      "source_text": "Does the matcher label go in the digest?",
      "target_text": "No. It lives in the bundle envelope, outside the payload the digest is taken over.",
      "verifier": ""
    },
    {
      "similarity": 0.403,
      "status": "draft",
      "servable": false,
      "id": "765fc6db-48cb-56bc-94de-97752ac62c7f",
      "source_text": "Was §6.8's 'measured once as noise for ingest' right?",
      "target_text": "No. 0.556 -> 0.395 ms/op, -28.9%, and the entry is corrected in place.",
      "verifier": ""
    },
    {
      "similarity": 0.403,
      "status": "draft",
      "servable": false,
      "id": "b1a6d070-d906-5d11-9352-870db4a86c4a",
      "source_text": "What does it mean to validate a matcher at load time?",
      "target_text": "Every way the load can fail becomes a refusal naming the spec — not just the one you thought of.",
      "verifier": ""
    },
    {
      "similarity": 0.391,
      "status": "draft",
      "servable": false,
      "id": "ab8112c4-ff66-5f0b-9862-801e6e5a4a51",
      "source_text": "Given all of that, what is the standing instruction to the next agent in this repository?",
      "target_text": "The gates here are real and they work on you, not only on your predecessors -- when one fires, stop and say so rather than rephrasing until it passes. And separate what you read from what you concluded, in your own head and in what you tell the operator. This repository exists to refuse asserting what has not been verified; an agent that does not hold itself to that is not qualified to build it.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.563, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check Missing guard: cross-session collision awareness — notice another agent is in the room --source-lang decision --target-lang decision`

```json
{
  "question": "Missing guard: cross-session collision awareness — notice another agent is in the room",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": {
    "pair_id": "26556f0e-7039-504a-aadf-43c2b8d8aff0",
    "commitment": "An advisory UserPromptSubmit hook (hooks/before_propose.py), sibling to before_build (#105), fires only on a propose/mint/open-a-PR prompt, scans local git only, and fails CLOSED to UNKNOWN -- never a false 'clear'.",
    "reason": "A hook cannot serialize two agents; it can only make a visible collision loud. It surfaces the next decision number this checkout would mint against sibling branches that already claim it, and derived files rebuilt elsewhere. Doors closed: a blocking gate (it warns, it does not block -- excluded from hook_guard's blocking-gate proof like before_build), and any network/GitHub-API dependency (a local-first tool reads local git). It states its own blind spot -- a sibling's uncommitted work, or a branch not yet fetched -- because 'silence from the store means nothing' is a lesson already paid for.",
    "verifier": "",
    "sealed": false,
    "matched_question": "Cross-session collision awareness (#111) -- where does it live, and what happens when it cannot tell?"
  },
  "match": "fuzzy",
  "similarity": 0.563
}
```

### Decision-store retrieval collapses for question-shaped queries

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask Decision-store retrieval collapses for question-shaped queries --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Decision-store retrieval collapses for question-shaped queries",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve Decision-store retrieval collapses for question-shaped queries --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match Decision-store retrieval collapses for question-shaped queries --from decision --to decision`

```json
{
  "normalized": "decisionstore retrieval collapses for questionshaped queries",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.463,
      "status": "draft",
      "servable": false,
      "id": "9151099b-ea58-51ac-bc70-c28036f42a63",
      "source_text": "The decision record is absent from the corpus. Fix, or document the boundary?",
      "target_text": "Neither in this pass — recorded as 6.105 with the argument that the exclusion is probably correct and the omission is that nothing says so.",
      "verifier": ""
    },
    {
      "similarity": 0.433,
      "status": "draft",
      "servable": false,
      "id": "3860e2c3-f104-50d0-9388-b4c119a08417",
      "source_text": "Does `nestor warrant` get a `report` subcommand, the way `nestor evidence` has one for unevidenced seals?",
      "target_text": "No. `attach` and `for`, and nothing else. The parallel is tempting and the shape is already written next door, which is exactly why it needed refusing on purpose rather than by omission.",
      "verifier": ""
    },
    {
      "similarity": 0.427,
      "status": "draft",
      "servable": false,
      "id": "816bde63-bbb2-576d-b92e-b3c59c24853e",
      "source_text": "Does §6.41's optional `score()` become mandatory, now that its question is live?",
      "target_text": "No. Stopping the re-keying answers it, and promoting the method would break every matcher written against the documented two.",
      "verifier": ""
    },
    {
      "similarity": 0.423,
      "status": "draft",
      "servable": false,
      "id": "3f19f435-edfa-5f04-8dee-76d2afc6acac",
      "source_text": "Is a rubric a domain the decision recipe already answers, or a shape that needs its own machinery?",
      "target_text": "Neither — it is the decision graph read as what it already is. constraints_on(question) at decision.py:196 is rubric evaluation: 'score this proposal against the criteria that touch it.' The 4 edge types (supersedes, refines, depends_on, contradicts) are the inter-criterion dependencies every graph-shaped rubric in the survey models. A rubric is not new machinery bolted beside the decision store; it is a view of the store. The fleet's assessment-visibility E1→E4 dependency graph (CC BY 4.0), willow-gate's trust ladder (Apache 2.0), prod-readiness's no-go gates (MIT), and the open world's Checkov policy-DAG and OPA/Rego rule-DAG (both Apache 2.0) all model criteria-as-graph — and none combine it with human-sealed verdicts. Nestor already does.",
      "verifier": ""
    },
    {
      "similarity": 0.409,
      "status": "draft",
      "servable": false,
      "id": "5c23bf4c-dc54-51c0-adaf-0b4f37aa03bc",
      "source_text": "How are jeles' rules obtained?",
      "target_text": "Parsed from the checkout by ast — constants, frozensets, dict-of-frozenset, and one function's default argument. Nothing imported, nothing executed.",
      "verifier": ""
    },
    {
      "similarity": 0.407,
      "status": "draft",
      "servable": false,
      "id": "96c3befc-dea4-59c8-8037-222d11c9c028",
      "source_text": "Does the survey strengthen the case for a conflict-scan (§7.3 question 2) and inter-rater reliability integration?",
      "target_text": "Both strengthened, neither built. Conflict-scan: Checkov and OPA both traverse policy graphs to find contradictions — the same operation a contradicts-edge traversal of the decision graph would perform. The rubric-self-contradiction defect documented in decision 0084 is exactly the failure mode this traversal catches. Inter-rater reliability: the education literature's kappa/alpha measures (do two raters applying the same rubric agree?) map directly to Nestor's matcher precision problem. This reframes nestor calibrate as rubric calibration — the same problem with a longer literature and a richer toolkit. Both are downstream build questions; the survey provides evidence, not implementations.",
      "verifier": ""
    },
    {
      "similarity": 0.405,
      "status": "draft",
      "servable": false,
      "id": "8561f2c7-bd22-556b-bb85-553c9d65e896",
      "source_text": "Should contradiction detection require stronger question evidence than supersession detection?",
      "target_text": "Yes — contradictions now require q_sim >= bar + 0.15 (0.70 at the default bar of 0.55). Supersession is unchanged at q_sim >= bar. The uplift is a module constant (_CONTRADICT_UPLIFT = 0.15) derived from the dogfood corpus.",
      "verifier": ""
    },
    {
      "similarity": 0.403,
      "status": "draft",
      "servable": false,
      "id": "2f9bf0d5-dfe0-5daa-80ea-2f83c95c5225",
      "source_text": "How should the README's four re-derivations of sealed/draft/pending be reduced?",
      "target_text": "Kept the state table (lines 16-21) as the single canonical definition. Trimmed 'The category' section to back-reference it instead of re-explaining tiers. Simplified the recipe tier table's 'Result state' column to bare state names.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.463, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check Decision-store retrieval collapses for question-shaped queries --source-lang decision --target-lang decision`

```json
{
  "question": "Decision-store retrieval collapses for question-shaped queries",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### glossary.locks_in_text is a raw substring match — a short lock fires inside longer words

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask glossary.locks_in_text is a raw substring match — a short lock fires inside longer words --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "glossary.locks_in_text is a raw substring match — a short lock fires inside longer words",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve glossary.locks_in_text is a raw substring match — a short lock fires inside longer words --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match glossary.locks_in_text is a raw substring match — a short lock fires inside longer words --from decision --to decision`

```json
{
  "normalized": "glossarylocks_in_text is a raw substring match a short lock fires inside longer words",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.428,
      "status": "draft",
      "servable": false,
      "id": "cee8c43a-6594-59eb-8916-2de73e283cdb",
      "source_text": "What does running third-party code inside a stdio server cost?",
      "target_text": "stdout. Import under redirect_stdout(stderr), at the point that introduced the hazard.",
      "verifier": ""
    },
    {
      "similarity": 0.425,
      "status": "draft",
      "servable": false,
      "id": "df705c9c-966d-5e50-9c14-54e2ed5b0146",
      "source_text": "Nestor's covenant is 'the machine may not confirm'. Is that enforced in-session, or only stated?",
      "target_text": "Only stated, until now — enforced by crypto ONLY in the strong deployment (an ed25519 keyring whose private half never touches the instance, a human signing in nestor ui). In the DEFAULT deployment (signing off, or a shared HMAC key) the covenant was purely advisory. before_authority denies the four minting acts that were ungated: `nestor keys add <name>` (default HMAC signs AS that name; --rotate retakes a key), assigning NESTOR_SEAL_KEY/NESTOR_KEYRING/NESTOR_CACHE_KEY, `nestor import --apply --verifier <human>`, a raw sqlite seal write, and a write to the keyring file. It allows de-escalation and reads (keys list/revoke, registering a peer's --public key, cat/stats/ledger). A pinning test binds the guard's env set to what signing/keyring actually read and its keys-verb knowledge to cli.py's choices, so a new key-env or keys verb cannot ship and skip the guard.",
      "verifier": ""
    },
    {
      "similarity": 0.411,
      "status": "draft",
      "servable": false,
      "id": "a76a106b-1bd8-5a93-9d77-7ecfbc43a05c",
      "source_text": "Is a glossary identity lock a way to express the Nestor/nestor case?",
      "target_text": "No. locks_in_text case-folds, so the lock fires on the common noun too.",
      "verifier": ""
    },
    {
      "similarity": 0.4,
      "status": "draft",
      "servable": false,
      "id": "7df40db3-61e4-52d9-aca8-7131cef2f156",
      "source_text": "Is a glossary term lock matched on word boundaries?",
      "target_text": "No — `t.lower() in lower` is a raw substring, so {'Tito': 'Tito'} fires inside 'apetito'. Left open — IDEAS §6.38.",
      "verifier": ""
    },
    {
      "similarity": 0.398,
      "status": "draft",
      "servable": false,
      "id": "a8fa5388-fdc9-5b0e-9a17-ba094d1461e2",
      "source_text": "`review.db` is the reviewer's own copy. Should it be gitignored, and under what pattern?",
      "target_text": "`review.db*`, verified with `git check-ignore` against the file, the ledger `nestor` writes beside it (`review.db.ledger.jsonl`) and SQLite's `-wal` / `-shm` companions.",
      "verifier": ""
    },
    {
      "similarity": 0.397,
      "status": "draft",
      "servable": false,
      "id": "b4b08a62-bd9a-508f-909a-60dfbcd0fa7e",
      "source_text": "On a matcher mismatch at import, warn or refuse?",
      "target_text": "Warn, and never refuse. The mismatch rides in the report (matcher_mismatch/source_matcher/dest_matcher) as well as a Python warning.",
      "verifier": ""
    },
    {
      "similarity": 0.384,
      "status": "draft",
      "servable": false,
      "id": "1a704d54-f132-5492-a9ba-a4d5a43ed2e5",
      "source_text": "What did running the claims past jeles' independence rule find?",
      "target_text": "Two of the ribbit row's six domains are the article being checked and a post quoting it nearly verbatim. The rule counts them as two independent sources.",
      "verifier": ""
    },
    {
      "similarity": 0.384,
      "status": "draft",
      "servable": false,
      "id": "2dacefe6-9836-5944-8962-0e364496d02c",
      "source_text": "How does a custom matcher reach a surface that IS the process?",
      "target_text": "An import spec, 'module:attribute', taken by every surface through one loader.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.428, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check glossary.locks_in_text is a raw substring match — a short lock fires inside longer words --source-lang decision --target-lang decision`

```json
{
  "question": "glossary.locks_in_text is a raw substring match — a short lock fires inside longer words",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### nestor keys add prints the wrong key for ed25519 and calls it the only copy

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask nestor keys add prints the wrong key for ed25519 and calls it the only copy --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "nestor keys add prints the wrong key for ed25519 and calls it the only copy",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve nestor keys add prints the wrong key for ed25519 and calls it the only copy --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match nestor keys add prints the wrong key for ed25519 and calls it the only copy --from decision --to decision`

```json
{
  "normalized": "nestor keys add prints the wrong key for ed25519 and calls it the only copy",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.496,
      "status": "draft",
      "servable": false,
      "id": "ce388d48-18c5-54df-a002-d610efc61913",
      "source_text": "Does `nestor keys add` hand a verifier the key they need?",
      "target_text": "Not for ed25519. It prints the public half and calls it the only copy. Left open — IDEAS §6.36.",
      "verifier": ""
    },
    {
      "similarity": 0.458,
      "status": "draft",
      "servable": false,
      "id": "5a94b439-33b0-5ed9-b84c-95147106e53f",
      "source_text": "Does the resolver close the hole completely?",
      "target_text": "No, and it says so. A session rooted ABOVE the repo with CLAUDE_PROJECT_DIR unset (the exact multi-repo web layout that produced §6.108) has no anchor pointing into the sibling subdir, so no project-scoped hook command can locate itself from there. Recorded as the residual in §6.108 and left to the runtime, not papered over.",
      "verifier": ""
    },
    {
      "similarity": 0.44,
      "status": "draft",
      "servable": false,
      "id": "0f53098a-90ae-5837-9668-7c7d6e578717",
      "source_text": "agent-log 6.36 says 'fix open', but the wrong-key bug was fixed by Nestor#99 and is tested. Is it closed, and what stays open?",
      "target_text": "Correct the status to 'fix shipped' (agent-log heading and the IDEAS map row, kept in lockstep so the doc gate passes), append a dated trailer naming the fix and its test, and add a peer-path message test so the sentence is read across every value it takes (not just the generate case the existing tests cover). The separate question 6.36 flagged -- whether the generate case should print the private key to a terminal at all -- stays open with TODO 1's key distribution, not resolved here.",
      "verifier": ""
    },
    {
      "similarity": 0.434,
      "status": "draft",
      "servable": false,
      "id": "9733aa0a-e00e-5f60-8595-58410984deab",
      "source_text": "What did the round expect to find, and what did it find?",
      "target_text": "It expected jeles' corpus to vouch for itself. Three of four claims were wrong.",
      "verifier": ""
    },
    {
      "similarity": 0.43,
      "status": "draft",
      "servable": false,
      "id": "9151099b-ea58-51ac-bc70-c28036f42a63",
      "source_text": "The decision record is absent from the corpus. Fix, or document the boundary?",
      "target_text": "Neither in this pass — recorded as 6.105 with the argument that the exclusion is probably correct and the omission is that nothing says so.",
      "verifier": ""
    },
    {
      "similarity": 0.427,
      "status": "draft",
      "servable": false,
      "id": "df705c9c-966d-5e50-9c14-54e2ed5b0146",
      "source_text": "Nestor's covenant is 'the machine may not confirm'. Is that enforced in-session, or only stated?",
      "target_text": "Only stated, until now — enforced by crypto ONLY in the strong deployment (an ed25519 keyring whose private half never touches the instance, a human signing in nestor ui). In the DEFAULT deployment (signing off, or a shared HMAC key) the covenant was purely advisory. before_authority denies the four minting acts that were ungated: `nestor keys add <name>` (default HMAC signs AS that name; --rotate retakes a key), assigning NESTOR_SEAL_KEY/NESTOR_KEYRING/NESTOR_CACHE_KEY, `nestor import --apply --verifier <human>`, a raw sqlite seal write, and a write to the keyring file. It allows de-escalation and reads (keys list/revoke, registering a peer's --public key, cat/stats/ledger). A pinning test binds the guard's env set to what signing/keyring actually read and its keys-verb knowledge to cli.py's choices, so a new key-env or keys verb cannot ship and skip the guard.",
      "verifier": ""
    },
    {
      "similarity": 0.427,
      "status": "draft",
      "servable": false,
      "id": "36e362b3-b4f4-5019-bedc-12ac22c28967",
      "source_text": "Does adding --matcher change the string default or the bar?",
      "target_text": "No. `string` stays the offline default and 0.55 stays its measured knee. `semantic`/`ollama` are opt-in, load through the existing `nestor.answer.load_matcher` (persist=False, so a triage run never writes an embedding cache), and the CLI prints a stderr note that 0.55 is the string knee and their cosine bar must be re-found with --calibrate (unrelated text scores 0.7-0.8 on nomic, so the char bar is far too low). The build box cannot reach model weights, so the semantic path is wired and unit-tested for the prune gating but exercised on a host that has Ollama — build here, run there.",
      "verifier": ""
    },
    {
      "similarity": 0.417,
      "status": "draft",
      "servable": false,
      "id": "4988f34f-0393-59b1-9391-1112325e5c84",
      "source_text": "What is the finding, as against the story?",
      "target_text": "There is no per-domain verifier policy. Measured: add_pair(status='sealed', verifier='anybody-at-all') is accepted and is_verified_seal returns True.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.496, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check nestor keys add prints the wrong key for ed25519 and calls it the only copy --source-lang decision --target-lang decision`

```json
{
  "question": "nestor keys add prints the wrong key for ed25519 and calls it the only copy",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### nestor_propose silently discards a forbidden argument — a refusal that does not read as one

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask nestor_propose silently discards a forbidden argument — a refusal that does not read as one --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "nestor_propose silently discards a forbidden argument — a refusal that does not read as one",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve nestor_propose silently discards a forbidden argument — a refusal that does not read as one --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match nestor_propose silently discards a forbidden argument — a refusal that does not read as one --from decision --to decision`

```json
{
  "normalized": "nestor_propose silently discards a forbidden argument a refusal that does not read as one",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.426,
      "status": "draft",
      "servable": false,
      "id": "0e5b3467-77e7-59fb-8037-7f7d92f23153",
      "source_text": "The write gate makes an agent consult before editing. What makes an agent consult before *building* a new thing?",
      "target_text": "before_build, an advisory UserPromptSubmit hook. On a build-shaped prompt (a strong construction verb, or write/add/make/wire next to a construct noun) it injects the anti-rediscovery reminder and stays silent otherwise, so a status question or a seal costs nothing. Its one number — the count of recorded decisions — is globbed from the tree at emit time, never hardcoded. It is wired into the CLI-agnostic runner and .claude/settings.json alongside reinject, and pinned by a prove-it-can-fail test that asserts both directions (fires on a build prompt, silent on a question) plus the on-the-wire contract.",
      "verifier": ""
    },
    {
      "similarity": 0.413,
      "status": "draft",
      "servable": false,
      "id": "19ef2e23-6f9a-51d5-987e-9ba80b468dcf",
      "source_text": "What kind of test catches a fix command that does not fix anything?",
      "target_text": "One that runs it. test_the_stand_up_command_the_ask_names_actually_satisfies_the_check asserts the check is asking, executes `nestor demo` in the tree, and requires the check to stop asking. Run against the code as it shipped it fails, quoting the ask that survived its own remedy.",
      "verifier": ""
    },
    {
      "similarity": 0.404,
      "status": "draft",
      "servable": false,
      "id": "a7731911-1d3e-5f91-bd90-e7d6badd17ee",
      "source_text": "What should the harnesses gate, given the guide's rule that a test which cannot fail is a description?",
      "target_text": "The distinction each exists to draw, and seven mutations were run to prove the gates fire: unfindable reported as rank 0, a missing store treated as an empty one, the beaten-by explanation dropped, the probe/expect length check removed, .venv struck from the vendored markers, an unreadable store counted as clean, and the fail-on-contamination gate made unfailable. Each turned exactly one test red; both files restored byte-identical.",
      "verifier": ""
    },
    {
      "similarity": 0.403,
      "status": "draft",
      "servable": false,
      "id": "01ed0183-8145-5775-8dc3-f5c3c36e0e75",
      "source_text": "If only one thing changes as a result, what should it be?",
      "target_text": "Not the suite runtime, which is bounded and already filed. The store has never once answered a question for the person who filled it — three hundred rows, none sealed, none served — and the shortest path to a first served answer is one human sealing one row whose right answer already ranks 1, against a bar calibrated for the matcher that keyed it.",
      "verifier": ""
    },
    {
      "similarity": 0.4,
      "status": "draft",
      "servable": false,
      "id": "c29bfadf-5f60-5c25-86b2-c0fbdd76da97",
      "source_text": "How is the 'which sealed rows have no evidence' report computed, and what does it do?",
      "target_text": "A store method memory_unevidenced_seals() runs one SQL join -- live (superseded_by='') sealed pairs whose id is NOT IN decision_evidence -- and nestor/evidence.py + `nestor evidence report` surface it read-only. It never writes, never blocks a seal, and always exits 0; a superseded seal is excluded because it is history, not a live claim.",
      "verifier": ""
    },
    {
      "similarity": 0.4,
      "status": "draft",
      "servable": false,
      "id": "7e02caf8-bc3a-524b-b79d-8ef2c3faa55e",
      "source_text": "A local extra makes a gate fail that CI passes. Which side is wrong?",
      "target_text": "Neither verdict is wrong; the gate is, for letting the environment decide. ignore_missing_imports only speaks to the absent case, so an installed extra sends mypy into that dependency's own stubs. follow_imports = \"skip\" on the same override block makes the four optional integrations Any whether installed or not, so local and CI agree by construction rather than by everyone's venv matching the lint job's. Verified in both environments -- local venv with extras present, and a CI-shaped venv with lint tools only -- each reporting no issues in the same 41 source files, so coverage did not shrink.",
      "verifier": ""
    },
    {
      "similarity": 0.395,
      "status": "draft",
      "servable": false,
      "id": "eb3cf0a7-3522-5764-9b29-5234b3ad3157",
      "source_text": "Where does 'what counts as a freshening decision' live, now that three callers need it?",
      "target_text": "In `nestor.staleness.FRESHENING`, read by the UI queue, the CLI listing and `Curator.get` alike. Not restated in the curator.",
      "verifier": ""
    },
    {
      "similarity": 0.393,
      "status": "draft",
      "servable": false,
      "id": "b87a7591-a083-53c7-a6ef-2c415bd83f48",
      "source_text": "The sweep's first result was a finding against feed_willow19_plans.py. Was it real?",
      "target_text": "No. The fixture was wrong — a bare parent directory is an absent corpus, not an empty one.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.426, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check nestor_propose silently discards a forbidden argument — a refusal that does not read as one --source-lang decision --target-lang decision`

```json
{
  "question": "nestor_propose silently discards a forbidden argument — a refusal that does not read as one",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### The fleet's own decision record is invisible to every corpus extractor

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask The fleet's own decision record is invisible to every corpus extractor --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "The fleet's own decision record is invisible to every corpus extractor",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve The fleet's own decision record is invisible to every corpus extractor --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match The fleet's own decision record is invisible to every corpus extractor --from decision --to decision`

```json
{
  "normalized": "the fleets own decision record is invisible to every corpus extractor",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.545,
      "status": "draft",
      "servable": false,
      "id": "9151099b-ea58-51ac-bc70-c28036f42a63",
      "source_text": "The decision record is absent from the corpus. Fix, or document the boundary?",
      "target_text": "Neither in this pass — recorded as 6.105 with the argument that the exclusion is probably correct and the omission is that nothing says so.",
      "verifier": ""
    },
    {
      "similarity": 0.449,
      "status": "draft",
      "servable": false,
      "id": "3d72f465-d3fb-55b5-9dc3-36c2720b3632",
      "source_text": "Is the Ping World / fleet correspondence itself recorded here as a fact?",
      "target_text": "No -- as a draft proposal with its measurement attached, unsealed. The machine proposed the line-up (faithful-record = ledger; received-signal epistemology = the seal covenant) and Nestor will not confirm it from character overlap. Only the semantic matcher (unavailable in this box) or a human sealing in nestor ui can adjudicate it.",
      "verifier": ""
    },
    {
      "similarity": 0.437,
      "status": "draft",
      "servable": false,
      "id": "a247aa81-4909-552d-a964-b455f67afbf7",
      "source_text": "What does Nestor's own store say about a topic when every read-only lens gets a turn?",
      "target_text": "scripts/issue_probe.py shells out to the nestor CLI on PATH and runs, per prompt: ask (offline engine), resolve, match, decision check; and, once at the top of the report: stats, rejections, triage, calibrate, evidence report. It fails closed on a missing DB (the exact defect #95 is filed for), captures non-zero exits as the lens signals they are (ask/resolve/match's 'not verified', decision check's 'recorded rejection'), and offers --snapshot for a VACUUM INTO copy so probing a shipped store does not append audit rows to its ledger on every run. Ships with tests/test_issue_probe.py and docs/probing-the-store.md; scripts/corpus/open_issues.txt is the hand-maintained prompts snapshot the first run answered against.",
      "verifier": ""
    },
    {
      "similarity": 0.427,
      "status": "draft",
      "servable": false,
      "id": "fed262ac-bce2-533c-96ea-65f346564514",
      "source_text": "Should the corpus extractors read the decision record in docs/dogfood/decisions/*.json?",
      "target_text": "No. The decision files are out of corpus scope by design. The dogfood store is its own store with its own builder (scripts/dogfood_store.py + dogfood_common.py), reading the same checkout through a separate path. Documented in the module docstring of scripts/corpus/common.py, citing docs/two-stores.md for the boundary.",
      "verifier": ""
    },
    {
      "similarity": 0.42,
      "status": "draft",
      "servable": false,
      "id": "4506fdbb-832f-5114-ac52-2fe2698d5d5d",
      "source_text": "Does §1.4's premise hold — is the data there for quorum?",
      "target_text": "No. Concurrence is discarded; two verifiers agreeing leave one row and one ledger entry.",
      "verifier": ""
    },
    {
      "similarity": 0.419,
      "status": "draft",
      "servable": false,
      "id": "2d12621a-0478-50de-84d9-e9318f3e3811",
      "source_text": "The overstatement was corrected within the hour. Record it, or just fix the claim?",
      "target_text": "Recorded in 6.106 in place, naming it as a correction to something asserted three messages earlier in the same session.",
      "verifier": ""
    },
    {
      "similarity": 0.409,
      "status": "draft",
      "servable": false,
      "id": "4c90165e-66b2-5f4e-b994-488b1886a438",
      "source_text": "The session-start script's unbound variable — cosmetic or real?",
      "target_text": "Real, and silent. Fixed by resolving the root once, guarded, in all three places.",
      "verifier": ""
    },
    {
      "similarity": 0.409,
      "status": "draft",
      "servable": false,
      "id": "5db89c4d-2310-5df9-9771-641990352903",
      "source_text": "What happened when this decision file was first built into the store?",
      "target_text": "It was refused. ConflictingDraftError — this file asked a question an earlier decision file had already answered differently.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.545, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check The fleet's own decision record is invisible to every corpus extractor --source-lang decision --target-lang decision`

```json
{
  "question": "The fleet's own decision record is invisible to every corpus extractor",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Corpus extractors walk the working tree — following the repo's own setup poisons its corpus

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask Corpus extractors walk the working tree — following the repo's own setup poisons its corpus --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Corpus extractors walk the working tree — following the repo's own setup poisons its corpus",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve Corpus extractors walk the working tree — following the repo's own setup poisons its corpus --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match Corpus extractors walk the working tree — following the repo's own setup poisons its corpus --from decision --to decision`

```json
{
  "normalized": "corpus extractors walk the working tree following the repos own setup poisons its corpus",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.462,
      "status": "draft",
      "servable": false,
      "id": "fed262ac-bce2-533c-96ea-65f346564514",
      "source_text": "Should the corpus extractors read the decision record in docs/dogfood/decisions/*.json?",
      "target_text": "No. The decision files are out of corpus scope by design. The dogfood store is its own store with its own builder (scripts/dogfood_store.py + dogfood_common.py), reading the same checkout through a separate path. Documented in the module docstring of scripts/corpus/common.py, citing docs/two-stores.md for the boundary.",
      "verifier": ""
    },
    {
      "similarity": 0.449,
      "status": "draft",
      "servable": false,
      "id": "c039f210-242e-59bf-87bd-15af250db6a7",
      "source_text": "Did waiting for CI before merging the release earn its cost?",
      "target_text": "Yes, and not for the reason expected. The wait was justified on the 3.10 leg -- tests/test_version.py had broken that leg once before by importing tomllib, and this branch adds a test to that same file. 3.10 was fine. What actually failed was a test-job/dev-venv difference that both legs shared and that no amount of local running on 3.11 would have surfaced.",
      "verifier": ""
    },
    {
      "similarity": 0.424,
      "status": "draft",
      "servable": false,
      "id": "f9a23c50-9d71-51b4-985f-fdacd9d444df",
      "source_text": "Does this contradict IDEAS 6.94, which says the store answers its own questions well?",
      "target_text": "No — it extends it. 6.94 measured paraphrase recall at 2/10 and first-sentence recall at 4/50, and read the misses as the threshold refusing to serve a decision it was not sure it was asked. For two of three probes that reading is exactly right. 6.106 adds the rank, which 6.94 did not measure.",
      "verifier": ""
    },
    {
      "similarity": 0.412,
      "status": "draft",
      "servable": false,
      "id": "3cfc4739-6da9-5542-9db6-14e7da2f2b67",
      "source_text": "Measuring what the store would serve needs sealed rows. Does the demo seal anything in the store that ships?",
      "target_text": "No. The committed docs/dogfood/nestor.db stays all-draft (dogfood_store.py seals nothing); the demo copies it to a temp directory, asserts the copy has zero sealed rows and serves None, and only seals throwaway copies elsewhere. tests/test_the_dogfooding_never_touches_the_committed_store snapshots docs/dogfood/ and fails if the run changed a byte of it.",
      "verifier": ""
    },
    {
      "similarity": 0.406,
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
      "id": "ab8112c4-ff66-5f0b-9862-801e6e5a4a51",
      "source_text": "Given all of that, what is the standing instruction to the next agent in this repository?",
      "target_text": "The gates here are real and they work on you, not only on your predecessors -- when one fires, stop and say so rather than rephrasing until it passes. And separate what you read from what you concluded, in your own head and in what you tell the operator. This repository exists to refuse asserting what has not been verified; an agent that does not hold itself to that is not qualified to build it.",
      "verifier": ""
    },
    {
      "similarity": 0.4,
      "status": "draft",
      "servable": false,
      "id": "8def2637-5b9b-53b7-97e9-32c2f37af782",
      "source_text": "Where should the command for reviewing the decision queue live?",
      "target_text": "In `docs/agent-guide.md`, beside the sentence that already says the queue at `nestor.ui` is where a draft changes — with the copy step, the reason it is `VACUUM INTO` and not `cp`, and the caveat that the seals stay in that copy (§6.123).",
      "verifier": ""
    },
    {
      "similarity": 0.394,
      "status": "draft",
      "servable": false,
      "id": "deee6af5-7e7b-51ab-8f8f-d4a3f8a7a0fd",
      "source_text": "Bump the pin so the face is on the renamed module?",
      "target_text": "No. It stays at v0.2.0, and what changes at the bump is documented instead.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.462, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check Corpus extractors walk the working tree — following the repo's own setup poisons its corpus --source-lang decision --target-lang decision`

```json
{
  "question": "Corpus extractors walk the working tree — following the repo's own setup poisons its corpus",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Corpus extractors do not fail closed — empty output is indistinguishable from could not look

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask Corpus extractors do not fail closed — empty output is indistinguishable from could not look --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Corpus extractors do not fail closed — empty output is indistinguishable from could not look",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve Corpus extractors do not fail closed — empty output is indistinguishable from could not look --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match Corpus extractors do not fail closed — empty output is indistinguishable from could not look --from decision --to decision`

```json
{
  "normalized": "corpus extractors do not fail closed empty output is indistinguishable from could not look",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.421,
      "status": "draft",
      "servable": false,
      "id": "fed262ac-bce2-533c-96ea-65f346564514",
      "source_text": "Should the corpus extractors read the decision record in docs/dogfood/decisions/*.json?",
      "target_text": "No. The decision files are out of corpus scope by design. The dogfood store is its own store with its own builder (scripts/dogfood_store.py + dogfood_common.py), reading the same checkout through a separate path. Documented in the module docstring of scripts/corpus/common.py, citing docs/two-stores.md for the boundary.",
      "verifier": ""
    },
    {
      "similarity": 0.402,
      "status": "draft",
      "servable": false,
      "id": "9d92a859-eed9-5414-928d-c5eb04b0e3b3",
      "source_text": "Seven extractors aimed at absent checkouts exited 0 with '0 pair(s)'. Fix them here, or file it?",
      "target_text": "Filed as IDEAS 6.101, not fixed in this pass. The finding includes that tests/test_corpus_readers_fail_closed.py — the file whose name claims this exact coverage — covers four feed_* scripts and no scripts/corpus/ script at all.",
      "verifier": ""
    },
    {
      "similarity": 0.397,
      "status": "draft",
      "servable": false,
      "id": "f4dbb62b-4feb-57c3-b59c-c021e8086234",
      "source_text": "Should the triage human output suppress singleton groups?",
      "target_text": "Yes. The human rendering shows only groups with 2+ members and appends a summary line '(N singleton group(s) suppressed)'. The JSON output keeps every cluster unchanged — callers may need the full list.",
      "verifier": ""
    },
    {
      "similarity": 0.388,
      "status": "draft",
      "servable": false,
      "id": "deee6af5-7e7b-51ab-8f8f-d4a3f8a7a0fd",
      "source_text": "Bump the pin so the face is on the renamed module?",
      "target_text": "No. It stays at v0.2.0, and what changes at the bump is documented instead.",
      "verifier": ""
    },
    {
      "similarity": 0.383,
      "status": "draft",
      "servable": false,
      "id": "0d2ef7ff-2897-54de-81c0-41bc77171dff",
      "source_text": "What guarded the pointer from CLAUDE.md to the guide?",
      "target_text": "Nothing. Now test_the_thin_pointer_still_points does, and it asserts the markdown link form rather than the filename appearing.",
      "verifier": ""
    },
    {
      "similarity": 0.383,
      "status": "draft",
      "servable": false,
      "id": "68b96403-2a90-5443-94e3-7c3b2152b2b0",
      "source_text": "extract_data_vault.py reported 0 rows against willow-data-vault. Empty repository, or wrong target?",
      "target_text": "Wrong target, established by reading its own output rather than the row count: 'allowlist: 6 directories, 0 file(s)'. Its allowlist names sean-data-vault's directory layout, and the repository in this box is willow-data-vault.",
      "verifier": ""
    },
    {
      "similarity": 0.379,
      "status": "draft",
      "servable": false,
      "id": "636f39cc-d7c3-5ba2-bf11-6919479c1cf7",
      "source_text": "recipes/jeles_bridge.py run as a script prints nothing and exits 0, including for --help. Defect or design?",
      "target_text": "Design, left alone. It is a library with no __main__, its fifteen tests pass, and the README lists it under recipes/ as something built against the package rather than something an operator runs.",
      "verifier": ""
    },
    {
      "similarity": 0.376,
      "status": "draft",
      "servable": false,
      "id": "5a94b439-33b0-5ed9-b84c-95147106e53f",
      "source_text": "Does the resolver close the hole completely?",
      "target_text": "No, and it says so. A session rooted ABOVE the repo with CLAUDE_PROJECT_DIR unset (the exact multi-repo web layout that produced §6.108) has no anchor pointing into the sibling subdir, so no project-scoped hook command can locate itself from there. Recorded as the residual in §6.108 and left to the runtime, not papered over.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.421, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check Corpus extractors do not fail closed — empty output is indistinguishable from could not look --source-lang decision --target-lang decision`

```json
{
  "question": "Corpus extractors do not fail closed — empty output is indistinguishable from could not look",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### The first five minutes: playful onboarding and a one-line install

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask The first five minutes: playful onboarding and a one-line install --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "The first five minutes: playful onboarding and a one-line install",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve The first five minutes: playful onboarding and a one-line install --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match The first five minutes: playful onboarding and a one-line install --from decision --to decision`

```json
{
  "normalized": "the first five minutes playful onboarding and a oneline install",
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
      "id": "160add96-955e-55dc-be9b-8138c6b7bcad",
      "source_text": "Should the test suite depend on jeles being installed?",
      "target_text": "No. Eight tests run on plain dicts; the live-corpus one uses importorskip.",
      "verifier": ""
    },
    {
      "similarity": 0.463,
      "status": "draft",
      "servable": false,
      "id": "75c51214-9dd4-5cc4-8738-a7ee63b6beb1",
      "source_text": "The first run reported CONST-0-5 FAILING. Was it?",
      "target_text": "No. The probe never tampered, and the false FAIL was against this package's headline claim.",
      "verifier": ""
    },
    {
      "similarity": 0.42,
      "status": "draft",
      "servable": false,
      "id": "b89abc99-e108-53a9-b6f8-829eb7eebeed",
      "source_text": "The listing printed something untrue during testing. What?",
      "target_text": "The per-row tail marker ignored --expected-head, so following the command's own advice changed nothing on screen.",
      "verifier": ""
    },
    {
      "similarity": 0.409,
      "status": "draft",
      "servable": false,
      "id": "f3151b1b-106a-5396-8845-e3b2e6d70b19",
      "source_text": "Did the first version of those assertions actually hold anything?",
      "target_text": "Not all of them. The beat-7 assertion was vacuous and was rewritten.",
      "verifier": ""
    },
    {
      "similarity": 0.408,
      "status": "draft",
      "servable": false,
      "id": "357fc096-89f3-5a4f-8a89-c2b82865624b",
      "source_text": "The operator said five minutes; the suite measures 96-114 seconds. Which number goes in?",
      "target_text": "Both, with the aggregation stated. The suite is not what they waited through — a turn was thinking, four to eight tool calls, a rebuild, a re-import, a commit, a push and a written reply, with the suite somewhere inside it. Three to five minutes is a fair account of that.",
      "verifier": ""
    },
    {
      "similarity": 0.406,
      "status": "draft",
      "servable": false,
      "id": "480bdb2e-6a9c-583f-a0db-9fb86968c6bb",
      "source_text": "The client's fixture — a scripted walk-through like shoebox.py, or something else?",
      "target_text": "Something else. demo/big_jim.py is a standing desk driven a command at a time, not an argument with an ending.",
      "verifier": ""
    },
    {
      "similarity": 0.406,
      "status": "draft",
      "servable": false,
      "id": "8a2bdbce-f1b8-5507-b505-7220e8364e27",
      "source_text": "The role-play session produced a fixture's worth of material. Write it up?",
      "target_text": "Yes — demo/filing_cabinet.py, ten beats, with tests/test_filing_cabinet.py.",
      "verifier": ""
    },
    {
      "similarity": 0.406,
      "status": "draft",
      "servable": false,
      "id": "1e384805-66fa-5341-be1e-2355afa8bf70",
      "source_text": "Three of the four findings are correct and well-sourced. Were any sealed?",
      "target_text": "None. Zero sealed, and a test pins that the demo contains no status='sealed' and no verifier= at all.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.483, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check The first five minutes: playful onboarding and a one-line install --source-lang decision --target-lang decision`

```json
{
  "question": "The first five minutes: playful onboarding and a one-line install",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Property-based tests for the matcher, normalizer, and frozen sign-message

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask Property-based tests for the matcher, normalizer, and frozen sign-message --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Property-based tests for the matcher, normalizer, and frozen sign-message",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve Property-based tests for the matcher, normalizer, and frozen sign-message --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match Property-based tests for the matcher, normalizer, and frozen sign-message --from decision --to decision`

```json
{
  "normalized": "propertybased tests for the matcher normalizer and frozen signmessage",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.467,
      "status": "draft",
      "servable": false,
      "id": "5cd96650-80d6-51da-99c9-af248c5a8cc2",
      "source_text": "Why install the matcher process-wide rather than only passing matcher= to each call?",
      "target_text": "Process-wide, in activate().",
      "verifier": ""
    },
    {
      "similarity": 0.463,
      "status": "draft",
      "servable": false,
      "id": "782fa219-0e20-520d-91fa-7f70a8e22b05",
      "source_text": "Does the matcher label go in the digest?",
      "target_text": "No. It lives in the bundle envelope, outside the payload the digest is taken over.",
      "verifier": ""
    },
    {
      "similarity": 0.455,
      "status": "draft",
      "servable": false,
      "id": "ed910646-682d-540d-801e-f831c87049a3",
      "source_text": "A fourth matcher for clause text?",
      "target_text": "No. Reused patch_review.DefectMatcher.",
      "verifier": ""
    },
    {
      "similarity": 0.435,
      "status": "draft",
      "servable": false,
      "id": "f4fbc5ee-b9c2-5700-9bc9-87d5d82d03b7",
      "source_text": "Grep the raw command string, or normalize first?",
      "target_text": "Normalize. Lex with shlex (quotes stripped, escapes undone), split on ; && || & then on pipes, unwrap sh -c / bash -c and re-scan, strip sudo/env/VAR= wrappers, parse flags into a set so rm -f -r / == rm -rf /. Each rule carries a comment naming what it catches; the test attempts each obfuscation (flag-reorder, sh -c, quote-splitting) and asserts the deny still fires.",
      "verifier": ""
    },
    {
      "similarity": 0.424,
      "status": "draft",
      "servable": false,
      "id": "ac742cd6-4a75-5f47-9ad1-b8464cbddc8c",
      "source_text": "The document was requested after the fact rather than kept as the session ran. Does that limit it?",
      "target_text": "Yes, and it says so in its opening paragraph: it is reconstructed, so the small frictions are under-represented, because the ones routed around in ten seconds are the ones forgotten.",
      "verifier": ""
    },
    {
      "similarity": 0.422,
      "status": "draft",
      "servable": false,
      "id": "c6c3e7ec-fd63-5687-988b-f588dd0092d3",
      "source_text": "What does the matcher mirror — jeles' ranking, or its answering?",
      "target_text": "Its answering. NuggetMatcher implements containment-then-symmetry, not the loose ranking.",
      "verifier": ""
    },
    {
      "similarity": 0.411,
      "status": "draft",
      "servable": false,
      "id": "37b53fc4-e73a-53ba-a598-50666dd5b90e",
      "source_text": "Should `nestor triage` be a CLI subcommand alongside `nestor ask`, `nestor calibrate`, etc.?",
      "target_text": "Yes. `nestor triage` runs the triage (group + supersede) over the dogfood corpus and prints the report. Supports `--matcher string|semantic|ollama`, `--bar`, `--calibrate`, and `--json`. Read-only — proposes nothing, seals nothing. The standalone script (`scripts/decision_triage.py`) stays for its `--propose` mode; the CLI subcommand covers the common path.",
      "verifier": ""
    },
    {
      "similarity": 0.409,
      "status": "draft",
      "servable": false,
      "id": "8c4f4f94-f991-542a-9c9c-42b1761579be",
      "source_text": "Is importing a module named on the command line a new privilege?",
      "target_text": "No — and the boundary is that the spec is a flag, never a value read from a request, a bundle or a stored row.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.467, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check Property-based tests for the matcher, normalizer, and frozen sign-message --source-lang decision --target-lang decision`

```json
{
  "question": "Property-based tests for the matcher, normalizer, and frozen sign-message",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Versioned schema migrations for the on-disk store

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask Versioned schema migrations for the on-disk store --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Versioned schema migrations for the on-disk store",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve Versioned schema migrations for the on-disk store --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match Versioned schema migrations for the on-disk store --from decision --to decision`

```json
{
  "normalized": "versioned schema migrations for the ondisk store",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.491,
      "status": "draft",
      "servable": false,
      "id": "80060540-77e9-5ae8-be8f-e801ef7f03bc",
      "source_text": "The migrations feed contradicted the jeles feed. Which is right?",
      "target_text": "Neither is wrong. There are at least three copies of that source registry and they disagree by design and by drift. Recorded as a qualification of PR 58.",
      "verifier": ""
    },
    {
      "similarity": 0.448,
      "status": "draft",
      "servable": false,
      "id": "bd1c947b-3cbe-5cd9-88ec-066ca1a275d3",
      "source_text": "Two dead men share a nickname. What happens when the second is sealed?",
      "target_text": "The first is destroyed. EntityResolver.seal inherits add_pair's overwrite; the sibling recipe retires and keeps. Left open — IDEAS §6.37.",
      "verifier": ""
    },
    {
      "similarity": 0.436,
      "status": "draft",
      "servable": false,
      "id": "8def2637-5b9b-53b7-97e9-32c2f37af782",
      "source_text": "Where should the command for reviewing the decision queue live?",
      "target_text": "In `docs/agent-guide.md`, beside the sentence that already says the queue at `nestor.ui` is where a draft changes — with the copy step, the reason it is `VACUUM INTO` and not `cp`, and the caveat that the seals stay in that copy (§6.123).",
      "verifier": ""
    },
    {
      "similarity": 0.435,
      "status": "draft",
      "servable": false,
      "id": "09496732-bda9-574a-995c-7d60f46e1e91",
      "source_text": "The move rewrote the guide's opening. Restored?",
      "target_text": "Yes. The 2026-08-05 incident sentence is back, and a paragraph saying plainly that this file is not auto-loaded.",
      "verifier": ""
    },
    {
      "similarity": 0.432,
      "status": "draft",
      "servable": false,
      "id": "4988f34f-0393-59b1-9391-1112325e5c84",
      "source_text": "What is the finding, as against the story?",
      "target_text": "There is no per-domain verifier policy. Measured: add_pair(status='sealed', verifier='anybody-at-all') is accepted and is_verified_seal returns True.",
      "verifier": ""
    },
    {
      "similarity": 0.43,
      "status": "draft",
      "servable": false,
      "id": "92a7ccc4-192d-5322-b577-9ae3c6b709f0",
      "source_text": "If SessionEnd is unreliable, is the drift check worth having?",
      "target_text": "Yes, as a best-effort local reminder, not a guarantee. SessionEnd does not fire on Ctrl+C (suspend, not exit) and is unreliable on /clear (anthropics/claude-code#6428). CI's test_dogfood_store remains the real drift gate; this hook only turns a post-push CI failure into an earlier end-of-session notice for the sessions where it does fire.",
      "verifier": ""
    },
    {
      "similarity": 0.427,
      "status": "draft",
      "servable": false,
      "id": "bc1b9077-a715-559c-a31e-796223262e11",
      "source_text": "Was the isolation shown to be load-bearing?",
      "target_text": "Yes. With the per-case receipt override removed and everything else unchanged, three tests fail -- test_every_wired_gate_denies_on_the_wire and both parametrisations of test_the_guard_ignores_whatever_receipt_the_developer_holds -- reporting the original `expect deny, got allow`. Restoring it returns all seven to green. The regression test drives scripts/hook_guard.py under both an absent and a deliberately fresh ambient receipt and requires exit 0 from each.",
      "verifier": ""
    },
    {
      "similarity": 0.424,
      "status": "draft",
      "servable": false,
      "id": "0e5e714b-b574-5022-b0c9-6c0755186848",
      "source_text": "Which field of a source declaration is worth a seal?",
      "target_text": "The subject list. Not key_required, not hosts.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.491, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check Versioned schema migrations for the on-disk store --source-lang decision --target-lang decision`

```json
{
  "question": "Versioned schema migrations for the on-disk store",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Central config schema: one home for the NESTOR_* knobs

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask Central config schema: one home for the NESTOR_* knobs --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Central config schema: one home for the NESTOR_* knobs",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve Central config schema: one home for the NESTOR_* knobs --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match Central config schema: one home for the NESTOR_* knobs --from decision --to decision`

```json
{
  "normalized": "central config schema one home for the nestor_ knobs",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.434,
      "status": "draft",
      "servable": false,
      "id": "393c3540-5e20-572d-82ef-dd281491a06e",
      "source_text": "What counts as a stood-up Nestor in the product tree -- the default store, or the demo store too?",
      "target_text": "Either. The probe now walks the CLI default (data/nestor.db) and then data/nestor-demo.db, and reports the first that exists. The ask names `nestor demo` and states where it lands, including that it refuses to write the default store and must be opened with `nestor ui --db data/nestor-demo.db`.",
      "verifier": ""
    },
    {
      "similarity": 0.432,
      "status": "draft",
      "servable": false,
      "id": "fd03b121-ef34-58ce-925d-b24dbee8a031",
      "source_text": "Should the fixture seal through the library, where it works, or through nestor.ui, where it does not?",
      "target_text": "Through ui.dispatch, the same call the browser makes.",
      "verifier": ""
    },
    {
      "similarity": 0.426,
      "status": "draft",
      "servable": false,
      "id": "36e362b3-b4f4-5019-bedc-12ac22c28967",
      "source_text": "Does adding --matcher change the string default or the bar?",
      "target_text": "No. `string` stays the offline default and 0.55 stays its measured knee. `semantic`/`ollama` are opt-in, load through the existing `nestor.answer.load_matcher` (persist=False, so a triage run never writes an embedding cache), and the CLI prints a stderr note that 0.55 is the string knee and their cosine bar must be re-found with --calibrate (unrelated text scores 0.7-0.8 on nomic, so the char bar is far too low). The build box cannot reach model weights, so the semantic path is wired and unit-tested for the prune gating but exercised on a host that has Ollama — build here, run there.",
      "verifier": ""
    },
    {
      "similarity": 0.423,
      "status": "draft",
      "servable": false,
      "id": "c73e32a5-c76b-5f2a-a230-19aa81efb51b",
      "source_text": "Which environment variable names the seat Nestor's FRANK mirror calls as?",
      "target_text": "NESTOR_FRANK_APP_ID, read before WILLOW_APP_ID rather than instead of it.",
      "verifier": ""
    },
    {
      "similarity": 0.417,
      "status": "draft",
      "servable": false,
      "id": "09496732-bda9-574a-995c-7d60f46e1e91",
      "source_text": "The move rewrote the guide's opening. Restored?",
      "target_text": "Yes. The 2026-08-05 incident sentence is back, and a paragraph saying plainly that this file is not auto-loaded.",
      "verifier": ""
    },
    {
      "similarity": 0.407,
      "status": "draft",
      "servable": false,
      "id": "816bde63-bbb2-576d-b92e-b3c59c24853e",
      "source_text": "Does §6.41's optional `score()` become mandatory, now that its question is live?",
      "target_text": "No. Stopping the re-keying answers it, and promoting the method would break every matcher written against the documented two.",
      "verifier": ""
    },
    {
      "similarity": 0.407,
      "status": "draft",
      "servable": false,
      "id": "2dacefe6-9836-5944-8962-0e364496d02c",
      "source_text": "How does a custom matcher reach a surface that IS the process?",
      "target_text": "An import spec, 'module:attribute', taken by every surface through one loader.",
      "verifier": ""
    },
    {
      "similarity": 0.406,
      "status": "draft",
      "servable": false,
      "id": "f22a17bc-c40f-5467-9568-6f5e2de0960a",
      "source_text": "What does a 0.300 spread mean for the permitted use recorded in decision 0084?",
      "target_text": "It widens the exposure and does not change the rule. 0084 already bounded the stand-in to a measuring instrument, never a cache key and never behind a seal. At a 0.92 threshold a 0.300 spread exposes roughly 0.62-1.00 rather than the 0.85-0.99 first estimated.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.434, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check Central config schema: one home for the NESTOR_* knobs --source-lang decision --target-lang decision`

```json
{
  "question": "Central config schema: one home for the NESTOR_* knobs",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

### Asymmetric seal signatures: an HMAC proves possession, not attribution

#### `ask` — exit 1

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json ask Asymmetric seal signatures: an HMAC proves possession, not attribution --from decision --to decision --engine offline`

```json
{
  "passage": {
    "source": "Asymmetric seal signatures: an HMAC proves possession, not attribution",
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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json resolve Asymmetric seal signatures: an HMAC proves possession, not attribution --domain entity`

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

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json match Asymmetric seal signatures: an HMAC proves possession, not attribution --from decision --to decision`

```json
{
  "normalized": "asymmetric seal signatures an hmac proves possession not attribution",
  "served": false,
  "verified": false,
  "target": "",
  "verifier": "",
  "confidence": 0.0,
  "threshold": 0.92,
  "matcher": "string",
  "matches": [
    {
      "similarity": 0.443,
      "status": "draft",
      "servable": false,
      "id": "2a767a44-0c1a-53ae-bd6f-2f10d98c5b06",
      "source_text": "The store may hold proposals from several machines. Does v1 resolve where per-agent attribution lives?",
      "target_text": "No, but it records attached_by on every evidence row from the first migration so the column is never a later retrofit. It does not build a multi-agent taxonomy and does not decide whether attribution belongs in Nestor or a sibling package -- that stays the open question 0142 named, to be settled before the schema hardens further.",
      "verifier": ""
    },
    {
      "similarity": 0.442,
      "status": "draft",
      "servable": false,
      "id": "4eb307eb-438d-52d1-9a8d-6587ac7800e3",
      "source_text": "What can a Nestor SessionEnd hook actually do?",
      "target_text": "Warn and flush, never gate. Confirmed from the Claude Code hooks docs and the fleet's own code: SessionEnd cannot block termination and cannot inject context (exit 2 only shows stderr to the user; there is no next turn). So session_end.py does two side-effect/advisory jobs: `dogfood_store.py --verify` and, on drift, a stderr reminder to rebuild before pushing (which also fails on a sealed row, doubling as a covenant check); and a WAL checkpoint of the gitignored dev store (never the committed dogfood store, whose checkpoint the rebuild script owns). It always exits 0, warnings to stderr. Anything that must block stays on the Stop turn-gate (before_stop.py). It is excluded from the gate-proving harness's coverage pin because it is not a gate.",
      "verifier": ""
    },
    {
      "similarity": 0.439,
      "status": "draft",
      "servable": false,
      "id": "4d3a3b93-a793-5ad9-835b-c0a30d8aa030",
      "source_text": "How was the listing shown to be a gate rather than a description?",
      "target_text": "Seven mutations, all red.",
      "verifier": ""
    },
    {
      "similarity": 0.431,
      "status": "draft",
      "servable": false,
      "id": "ea558f66-8f28-5924-8b51-8b42a33cbfd1",
      "source_text": "Is the write gate proven to open, or only to shut?",
      "target_text": "Both. A third before_write case, write-gated-py-allowed-after-consulting, runs the same forbidden payload against a fresh receipt and expects allow; the deny case now explicitly runs against an absent one. tests/test_hook_guard.py pins the pair, so removing either direction fails the suite. Isolating the receipt made this cheap -- both states are already constructed.",
      "verifier": ""
    },
    {
      "similarity": 0.421,
      "status": "draft",
      "servable": false,
      "id": "0d25d226-a144-501d-a03d-5dcee0837559",
      "source_text": "Asymmetric signing needs a library the stdlib does not have. Does that cost the zero-dependency guarantee?",
      "target_text": "No. It lives behind a [keys] optional extra (cryptography>=41). HMAC stays the default, the core stays dependency-free, and an ed25519 keyring without the extra refuses loudly at BOTH sign and verify.",
      "verifier": ""
    },
    {
      "similarity": 0.419,
      "status": "draft",
      "servable": false,
      "id": "6ed2bd3b-7202-5efd-bb0b-fa4324c31ec7",
      "source_text": "How was the demo shown to be a gate rather than a description?",
      "target_text": "Four mutations, all red.",
      "verifier": ""
    },
    {
      "similarity": 0.419,
      "status": "draft",
      "servable": false,
      "id": "4f3e2419-5d36-5406-92cd-68f8d5fc84ae",
      "source_text": "What separates a claim that passes from one that gets flagged?",
      "target_text": "A quoted run: a code span with a command word, 'N passed', an exit code, or file.py:line. Claim present and evidence absent is the only flagged state; the guard fails OPEN when it cannot find the final message.",
      "verifier": ""
    },
    {
      "similarity": 0.403,
      "status": "draft",
      "servable": false,
      "id": "ebcb99e6-7cd3-5b59-a9e1-a3a4d5690ab6",
      "source_text": "What keeps an install hint in shipped code pointing at a distribution that exists?",
      "target_text": "A test, not a habit. test_shipped_install_hints_name_the_distribution_that_exists reads `name` out of pyproject.toml and scans every .py under nestor/ for `<dist>[<extra>]`, failing on any that names something else. Scoped to nestor/ because that is what ships in the wheel; historical records (FINDINGS, agent-log) quote the old name to describe the past and are left alone. Shown to fail: restoring one string in keyring.py reports `nestor/keyring.py:94 nestor[keys]`.",
      "verifier": ""
    }
  ],
  "reason": "closest of 520 candidate(s) is 0.443, below 0.92 (showing 8) — the bar exists because a near miss served as verified is worse than no answer"
}
```

#### `decision-check` — exit 0

`$ /home/user/Nestor/.venv/bin/nestor --db /tmp/nestor-probe-vxt1m16c/snapshot-nestor.db --json decision check Asymmetric seal signatures: an HMAC proves possession, not attribution --source-lang decision --target-lang decision`

```json
{
  "question": "Asymmetric seal signatures: an HMAC proves possession, not attribution",
  "domain": "decision",
  "blocked": false,
  "rejected": [],
  "contradicts": [],
  "live": null,
  "match": "none",
  "similarity": 0.0
}
```

