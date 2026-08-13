# Ideas

A running list, kept in the repo so it outlives the conversation that produced
it. Nothing here is a commitment; several entries argue against each other.

Each entry carries a status, because the difference matters:

| Status | Means |
|--------|-------|
| **measured** | There are numbers in `bench/results/`, or a run reproduced in this repo |
| **verified** | The mechanism was demonstrated working, without a full measurement |
| **hypothesis** | Plausible, untested — do not cite as fact |
| **open** | A question, not yet a proposal |

**Agent log (§6).** Follow-ups proposed during implementation sessions (IDE
agents included) go in §6 — now [`docs/agent-log.md`](docs/agent-log.md) — with
the same status vocabulary. When something
ships, mark it **shipped** there (and fold the substance into the numbered
section it belongs to if it isn't already). Agents: when you suggest a follow-up
to the operator, add it to §6 in the same change or immediately after — do not
leave it only in chat.

**Review lessons.** Durable checklist from PR review rounds (persistence, audit,
threading, config): [`docs/code-review-lessons.md`](docs/code-review-lessons.md).

**Fleet map.** Open IDEAS items vs existing repos (willow-mcp, SAFE store,
oakenscrolls, bench corpora): [`docs/fleet-integration-map.md`](docs/fleet-integration-map.md).
Local checkout and commands: [`docs/local-fleet.md`](docs/local-fleet.md).

---

## Map — every section, checked in CI

The whole document at a glance: every subsection, its status, and where it
lives. §6 (the agent log) is in [`docs/agent-log.md`](docs/agent-log.md); the
rest is here. This table is **generated from the headings and gated by
`tests/test_docs.py`** — if a subsection is added, renamed, or retagged and
this map is not, CI fails. It cannot drift.

| § | Entry | Status |
|---|---|---|
| [1.1](#11-margin-not-just-magnitude--measured-mostly-falsified) | Margin, not just magnitude | measured; mostly falsified |
| [1.2](#12-negative-seals--shipped) | Negative seals | shipped |
| [1.3](#13-the-threshold-should-be-calibrated-not-constant--measured-the-calibration-shipped) | The threshold should be calibrated, not constant | measured; the calibration shipped |
| [1.4](#14-seal-staleness-and-quorum--measured-design-open) | Seal staleness and quorum | measured, design open |
| [1.5](#15-a-numeric-label-could-hold-several-baselines--shipped) | A numeric label could hold several baselines | shipped |
| [1.6](#16-a-seal-could-be-made-without-being-ledgered--shipped) | A seal could be made without being ledgered | shipped |
| [1.7](#17-an-import-could-revive-a-pair-a-human-had-rejected--shipped) | An import could revive a pair a human had rejected | shipped |
| [1.8](#18-two-threads-could-seal-the-same-phrase-and-both-won--shipped) | Two threads could seal the same phrase, and both won | shipped |
| [1.9](#19-the-numeric-matcher-takes-the-first-number-it-finds--shipped) | The numeric matcher takes the first number it finds | shipped |
| [2.1](#21-lossless-prefilter-via-difflibs-own-bounds--shipped) | Lossless prefilter via difflib's own bounds | shipped |
| [2.2](#22-trigram-blocking--measured-disappointing) | Trigram blocking | measured, disappointing |
| [2.3](#23-index-source_norm--shipped) | Index `source_norm` | shipped |
| [2.4](#24-connection-per-operation--shipped-file-backed-reuse) | Connection-per-operation | shipped (file-backed reuse) |
| [3.1](#31-the-seam-is-lossy-by-construction--shipped) | The seam is lossy by construction | shipped |
| [3.2](#32-recipes-the-seam-already-supports--verified) | Recipes the seam already supports | verified |
| [3.3](#33-semantic-matcher--shipped-optional-extra) | Semantic matcher | shipped (optional extra) |
| [3.4](#34-model-authored-surfaces--measured-four-stages-and-the-matcher) | Model-authored surfaces | measured; four stages, and the matcher |
| [4.1](#41-lead-with-the-mechanic-not-translation--shipped) | Lead with the mechanic, not translation | shipped |
| [4.2](#42-the-category-is-ai-verification-not-translation-memory--shipped) | The category is AI verification, not translation memory | shipped |
| [4.3](#43-the-60-second-demo--shipped-except-the-recording) | The 60-second demo | shipped, except the recording |
| [4.4](#44-the-bench-is-a-marketing-asset--shipped) | The bench is a marketing asset | shipped |
| [5.1](#51-there-is-no-cli--shipped) | There is no CLI | shipped |
| [5.2](#52-the-memory-is-write-only--shipped) | The memory is write-only | shipped |
| [5.3](#53-ledger-verification-is-once-per-process--verified-the-tail-closed) | Ledger verification is once per process | verified; the tail closed |
| [5.4](#54-there-was-nowhere-for-the-human-to-sit--shipped) | There was nowhere for the human to sit | shipped |
| [5.5](#55-the-newest-ledger-entry-is-vouched-for-by-nothing--shipped-mitigated) | The newest ledger entry is vouched for by nothing | shipped (mitigated) |
| [5.6](#56-nothing-could-leave--shipped) | Nothing could leave | shipped |
| [5.7](#57-a-model-had-no-way-in--shipped) | A model had no way in | shipped |
| [5.8](#58-a-verifier-was-a-string-anybody-could-type--shipped) | A verifier was a string anybody could type | shipped |
| [6.1](docs/agent-log.md#61-semantic-smoke-test-behind-nestor_semantic_test--shipped) | Semantic smoke test behind NESTOR_SEMANTIC_TEST | shipped |
| [6.2](docs/agent-log.md#62-batch-embed-in-lookup--best_sealed--shipped) | Batch-embed in `lookup` / `best_sealed` | shipped |
| [6.3](docs/agent-log.md#63-bench-token-matchers-score--harness-match_similarity--shipped) | Bench token matchers: `score` + harness `match_similarity` | shipped |
| [6.4](docs/agent-log.md#64-persisted-row-embeddings-tm_embeddings--shipped) | Persisted row embeddings (`tm_embeddings`) | shipped |
| [6.5](docs/agent-log.md#65-file-backed-sqlite-a-bounded-wal-connection-pool--shipped) | File-backed SQLite: a bounded WAL connection pool | shipped |
| [6.6](docs/agent-log.md#66-ttld-ledger-re-verification-on-append--shipped) | TTL'd ledger re-verification on append | shipped |
| [6.7](docs/agent-log.md#67-hot-checkpoint--backup-while-the-store-is-open--shipped) | Hot checkpoint / backup while the store is open | shipped |
| [6.8](docs/agent-log.md#68-skip-redundant-memory_init-schema-replay--shipped) | Skip redundant ``memory_init`` schema replay | shipped |
| [6.9](docs/agent-log.md#69-subprocess-test-ui-refuses-bad-ledger-interval-env--shipped) | Subprocess test: UI refuses bad ledger interval env | shipped |
| [6.10](docs/agent-log.md#610-seal-age-in-provenance-display-only--shipped) | Seal age in provenance (display only) | shipped |
| [6.11](docs/agent-log.md#611-decision-memory--lineage-joined-to-rejection--shipped-all-steps-landed-see-trailer) | Decision memory — lineage joined to rejection | shipped (all steps landed; see trailer) |
| [6.12](docs/agent-log.md#612-the-detection-kit-as-gates-not-advice--measured-build-open) | The detection kit as gates, not advice | measured, build open |
| [6.13](docs/agent-log.md#613-ground-rule-2b-made-executable--shipped) | Ground rule 2b made executable | shipped |
| [6.14](docs/agent-log.md#614-dogfood-this-sessions-decisions-fed-through-nestor--measured) | Dogfood: this session's decisions fed through Nestor | measured |
| [6.15](docs/agent-log.md#615-both-614-findings-fixed--shipped) | Both §6.14 findings fixed | shipped |
| [6.16](docs/agent-log.md#616-the-audit-of-615-and-what-a-first-fix-misses--shipped) | The audit of §6.15, and what a first fix misses | shipped |
| [6.17](docs/agent-log.md#617-the-second-audit-a-second-regression-and-the-shape-that-caused-both--shipped) | The second audit, a second regression, and the shape that caused both | shipped |
| [6.18](docs/agent-log.md#618-what-nestor-says-about-the-615617-rounds--measured) | What Nestor says about the §6.15–§6.17 rounds | measured |
| [6.19](docs/agent-log.md#619-the-loop-run-twice--partly-one-verb-still-missing) | The loop, run twice | partly (one verb still missing) |
| [6.20](docs/agent-log.md#620-revise_draft--the-third-verb--shipped) | `revise_draft` — the third verb | shipped |
| [6.21](docs/agent-log.md#621-the-third-audit-two-criticals-in-the-verb-and-the-first-fix-for-one-of-them-was-wrong-too--shipped) | The third audit: two criticals in the verb, and the first fix for one of them was wrong too | shipped |
| [6.22](docs/agent-log.md#622-a-name-is-not-a-word-the-proper-noun-case-has-no-field--measured-design-open) | A name is not a word: the proper-noun case has no field | measured, design open |
| [6.23](docs/agent-log.md#623-the-refusal-voice-three-sentences-rewritten-one-bug-two-rules--shipped) | The refusal voice: three sentences rewritten, one bug, two rules | shipped |
| [6.24](docs/agent-log.md#624-personapy--installed-and-the-two-gates-that-bit-me--shipped) | `persona.py` — installed, and the two gates that bit me | shipped |
| [6.25](docs/agent-log.md#625-init_db-on-a-pre-lineage-database-raises--shipped) | `init_db` on a pre-lineage database raises | shipped |
| [6.26](docs/agent-log.md#626-a-countersignature-is-discarded-without-a-word--shipped) | A countersignature is discarded without a word | shipped |
| [6.27](docs/agent-log.md#627-the-glossary-is-addressed-relative-to-the-working-directory--shipped) | The glossary is addressed relative to the working directory | shipped |
| [6.28](docs/agent-log.md#628-concurrent-writers-the-known-limit-quantified--measured-fix-open) | Concurrent writers: the known limit, quantified | measured, fix open |
| [6.29](docs/agent-log.md#629-two-of-the-three-refusals-are-exported-the-third-is-not--shipped) | Two of the three refusals are exported; the third is not | shipped |
| [6.30](docs/agent-log.md#630-a-recipe-for-patches--built-measured-and-it-does-not-serve--measured-and-qualified-by-632) | A recipe for patches — built, measured, and it does not serve | measured, and qualified by §6.32 |
| [6.31](docs/agent-log.md#631-nothing-that-persists-carries-a-version--measured-fix-open) | Nothing that persists carries a version | measured, fix open |
| [6.32](docs/agent-log.md#632-the-loop-fourth-turn--and-it-found-the-recipes-caveat-was-right--measured) | The loop, fourth turn — and it found the recipe's caveat was right | measured |
| [6.33](docs/agent-log.md#633-the-memory-has-never-been-given-the-projects-decisions--measured-fix-open) | The memory has never been given the project's decisions | measured, fix open |
| [6.34](docs/agent-log.md#634-a-ledger-line-that-cannot-exist-was-ignored-by-every-reader--shipped) | A ledger line that cannot exist was ignored by every reader | shipped |
| [6.35](docs/agent-log.md#635-the-solo-verifier-two-records-kept-carefully-and-shown-to-nobody--measured-fix-open) | The solo verifier: two records kept carefully and shown to nobody | measured, fix open |
| [6.36](docs/agent-log.md#636-nestor-keys-add-prints-the-wrong-key-and-calls-it-the-only-copy--measured-fix-open) | `nestor keys add` prints the wrong key and calls it the only copy | measured, fix open |
| [6.37](docs/agent-log.md#637-the-entity-graph-destroys-what-the-numeric-recipe-keeps-and-has-no-word-for-an-ambiguous-name--measured-fix-open) | The entity graph destroys what the numeric recipe keeps, and has no word for an ambiguous name | measured, fix open |
| [6.38](docs/agent-log.md#638-locks_in_text-is-a-raw-substring-so-a-short-lock-fires-inside-longer-words--measured-fix-open) | `locks_in_text` is a raw substring, so a short lock fires inside longer words | measured, fix open |
| [6.39](docs/agent-log.md#639-the-entity-graph-has-only-the-verb-a-machine-may-not-use--measured-fix-open) | The entity graph has only the verb a machine may not use | measured, fix open |
| [6.40](docs/agent-log.md#640-nestor-ui-can-be-aimed-at-a-custom-domain-and-cannot-be-told-its-matcher--measured-fix-shipped) | `nestor ui` can be aimed at a custom domain and cannot be told its matcher | measured, fix shipped |
| [6.41](docs/agent-log.md#641-an-optional-method-on-the-matcher-seam-is-what-decides-whether-seals-survive--measured-design-answered-everywhere) | An optional method on the Matcher seam is what decides whether seals survive | measured, design answered, everywhere |
| [6.42](docs/agent-log.md#642-the-quorum-memos-step-2-has-been-unrunnable-and-its-zero-would-have-been-unreadable--measured-question-open) | The quorum memo's step 2 has been unrunnable, and its zero would have been unreadable | measured, question open |
| [6.43](docs/agent-log.md#643-dogfood_storepy---verify-says-the-store-matches-the-decision-files-and-does-not-check-where-a-row-came-from--measured-fix-open) | `dogfood_store.py --verify` says the store matches the decision files, and does not check where a row came from | measured, fix open |
| [6.44](docs/agent-log.md#644-nestor_propose-discards-a-forbidden-argument-without-saying-so--measured-fix-open) | `nestor_propose` discards a forbidden argument without saying so | measured, fix open |
| [6.45](docs/agent-log.md#645-two-repositories-hit-a-condition-checked-outside-the-write-separately-and-both-wrote-down-what-it-cost--verified-lesson-shipped) | Two repositories hit "a condition checked outside the write", separately, and both wrote down what it cost | verified, lesson shipped |
| [6.46](docs/agent-log.md#646-the-empty-run-discipline-was-in-four-scripts-and-not-in-the-fifths-absent-branch--measured-fix-shipped) | The empty-run discipline was in four scripts and not in the fifth's absent branch | measured, fix shipped |
| [6.47](docs/agent-log.md#647-a-claims-own-source-counts-as-an-independent-witness--measured-fix-open-and-it-may-not-have-one) | A claim's own source counts as an independent witness | measured, fix open (and it may not have one) |
| [6.48](docs/agent-log.md#648-both-hypotheses-647s-feed-raised-were-measurable-and-neither-was-right-as-written--measured-filed-as-jeles53) | Both hypotheses §6.47's feed raised were measurable, and neither was right as written | measured, filed as jeles#53 |
| [6.49](docs/agent-log.md#649-the-staleness-memos-2-names-the-wrong-timestamp-as-unmovable-by-one-entry--measured-listing-shipped-caveat-open) | The staleness memo's §2 names the wrong timestamp as unmovable, by one entry | measured, listing shipped, caveat open |
| [6.50](docs/agent-log.md#650-minimal_output-is-a-parameter-on-one-tool-of-fifty-five-and-the-group-it-belongs-to-decides-what-a-repo-corpus-costs--measured-corpus-build-open) | `minimal_output` is a parameter on one tool of fifty-five, and the group it belongs to decides what a repo corpus costs | measured, corpus build open |
| [6.51](docs/agent-log.md#651-the-oldest-repository-extracted-229-drafts-eight-self-contradictions-and-three-things-nestor-has-no-field-for--measured-corpus-design-open) | The oldest repository, extracted: 229 drafts, eight self-contradictions, and three things Nestor has no field for | measured, corpus design open |
| [6.52](docs/agent-log.md#652-willow-extracted-the-first-bilingual-rows-a-constitution-that-is-56-human-and-a-generic-extractor-that-buried-its-own-best-content--measured-extractor-design-open) | Willow extracted: the first bilingual rows, a constitution that is 56% human, and a generic extractor that buried its own best content | measured, extractor design open |
| [6.53](docs/agent-log.md#653-origin-now-says-what-produced-the-row-which-forced-the-extractors-into-the-repository--shipped-visibility-field-still-open) | `origin` now says what produced the row, which forced the extractors into the repository | shipped, visibility field still open |
| [6.54](docs/agent-log.md#654-aionic-extracted-a-linter-that-passes-none-of-its-own-subjects-and-the-discovery-that-silence-from-the-store-means-nothing--measured-extractor-coverage-open) | Aionic extracted: a linter that passes none of its own subjects, and the discovery that silence from the store means nothing | measured, extractor coverage open |
| [6.55](docs/agent-log.md#655-willow-seed-extracted-ten-drafts-coverage-28-and-a-promise-the-document-keeps-once--measured-coverage-now-shipped) | willow-seed extracted: ten drafts, coverage 2/8, and a promise the document keeps once | measured, coverage now shipped |
| [6.56](docs/agent-log.md#656-openclaw-sap-gate-extracted-the-first-code-rung-two-coverage-denominators-and-thirty-rows-recovered-from-the-declined-pile--measured) | openclaw-sap-gate extracted: the first code rung, two coverage denominators, and thirty rows recovered from the declined pile | measured |
| [6.57](docs/agent-log.md#657-willow-19-extracted-1340-drafts-two-coverage-ratios-that-match-across-an-80-size-gap-and-a-key-that-was-wrong-in-a-second-domain--measured) | willow-1.9 extracted: 1,340 drafts, two coverage ratios that match across an 80× size gap, and a key that was wrong in a second domain | measured |
| [6.58](docs/agent-log.md#658-willow-nest-extracted-the-first-repository-that-declares-nothing-new-and-a-ratio-that-survived-its-third-test--measured) | willow-nest extracted: the first repository that declares nothing new, and a ratio that survived its third test | measured |
| [6.59](docs/agent-log.md#659-hermes-agent-extracted-as-a-delta-2-commits-of-4766-and-a-headline-number-that-was-somebody-elses--measured-per-file-attribution-open) | hermes-agent extracted as a delta: 2 commits of 4,766, and a headline number that was somebody else's | measured, per-file attribution open |
| [6.60](docs/agent-log.md#660-python-sdk-zero-and-the-attribution-fix-that-made-zero-trustworthy--measured) | python-sdk: zero, and the attribution fix that made zero trustworthy | measured |
| [6.61](docs/agent-log.md#661-litellm-zero-again-and-what-two-zeroes-in-a-row-are-worth--measured) | litellm: zero again, and what two zeroes in a row are worth | measured |
| [6.62](docs/agent-log.md#662-willow-bot-a-generic-runner-that-demoted-itself-within-one-run-a-rule-shape-and-the-ratios-fourth-point-breaking-the-band--measured) | willow-bot: a generic runner that demoted itself within one run, a rule shape, and the ratio's fourth point breaking the band | measured |
| [6.63](docs/agent-log.md#663-claude_code_rlm-the-third-bookmark-and-the-pairing-that-gives-it-meaning--measured) | claude_code_RLM: the third bookmark, and the pairing that gives it meaning | measured |
| [6.64](docs/agent-log.md#664-the-archived-app-store-1012-drafts-a-lesson-shape-and-622-arriving-as-a-live-case-in-the-operators-own-fiction--measured-cross-repository-comparison-open) | The archived app store: 1,012 drafts, a lesson shape, and §6.22 arriving as a live case in the operator's own fiction | measured, cross-repository comparison open |
| [6.65](docs/agent-log.md#665-the-comparison-pass-what-thirteen-stores-could-not-see-about-each-other--shipped) | The comparison pass: what thirteen stores could not see about each other | shipped |
| [6.66](docs/agent-log.md#666-safe-app-willow-grove-a-corrections-table-and-the-first-rung-to-run-the-comparison-pass-on-arrival--measured) | safe-app-willow-grove: a corrections table, and the first rung to run the comparison pass on arrival | measured |
| [6.67](docs/agent-log.md#667-claude-deep-review-the-fourth-bookmark--measured) | claude-deep-review: the fourth bookmark | measured |
| [6.68](docs/agent-log.md#668-willow-tech-manual-23-rows-from-46-documents-and-the-bias-the-corpus-has-been-carrying-all-along--measured) | willow-tech-manual: 23 rows from 46 documents, and the bias the corpus has been carrying all along | measured |
| [6.69](docs/agent-log.md#669-tui-scaffold-four-skills-invisible-to-a-parser-choice-and-the-docstring-ratio-finally-withdrawn--measured) | tui-scaffold: four skills invisible to a parser choice, and the docstring ratio finally withdrawn | measured |
| [6.70](docs/agent-log.md#670-willow-20-3680-drafts-and-the-consolidation-test-rung-7-banked--measured) | willow-2.0: 3,680 drafts, and the consolidation test rung 7 banked | measured |
| [6.71](docs/agent-log.md#671-every-fork-number-in-this-file-was-wrong-and-the-fix-is-one-flag--measured-five-entries-corrected-in-place) | Every fork number in this file was wrong, and the fix is one flag | measured, five entries corrected in place |
| [6.72](docs/agent-log.md#672-the-identity-widened-and-the-vetting-mattered-more-than-the-widening--measured) | The identity widened, and the vetting mattered more than the widening | measured |
| [6.73](docs/agent-log.md#673-three-forks-and-the-largest-delta-the-corpus-has-read--measured) | Three forks, and the largest delta the corpus has read | measured |
| [6.74](docs/agent-log.md#674-willow-config-a-third-persona-schema-that-shares-no-names-and-a-refusal-i-nearly-made-from-an-assumption--measured) | willow-config: a third persona schema that shares no names, and a refusal I nearly made from an assumption | measured |
| [6.75](docs/agent-log.md#675-eight-more-forks-and-the-first-quantity-this-file-has-earned-the-right-to-state--measured) | Eight more forks, and the first quantity this file has earned the right to state | measured |
| [6.76](docs/agent-log.md#676-four-repositories-two-of-them-empty-and-a-counter-that-has-been-overstating-every-shape-for-twenty-rungs--measured) | Four repositories, two of them empty, and a counter that has been overstating every shape for twenty rungs | measured |
| [6.77](docs/agent-log.md#677-four-forks-and-nine-namesakes-in-one-repository--measured) | Four forks, and nine namesakes in one repository | measured |
| [6.78](docs/agent-log.md#678-two-before-and-after-pairs-a-redaction-verified-complete-and-a-docstring-diff-that-turns-out-to-be-a-question--measured) | Two before-and-after pairs: a redaction verified complete, and a docstring diff that turns out to be a question | measured |
| [6.79](docs/agent-log.md#679-the-june-pile-thirteen-forks-and-a-writing-repository-that-the-corpus-cannot-read--measured) | The June pile: thirteen forks, and a writing repository that the corpus cannot read | measured |
| [6.80](docs/agent-log.md#680-the-almanac-org-eleven-repositories-with-zero-divergence-and-a-template-that-has-walked-away-from-all-of-them--measured) | The almanac org: eleven repositories with zero divergence, and a template that has walked away from all of them | measured |
| [6.81](docs/agent-log.md#681-the-early-july-batch-five-repositories-no-new-shapes-and-the-ratios-full-spread--measured) | The early-July batch: five repositories, no new shapes, and the ratio's full spread | measured |
| [6.82](docs/agent-log.md#682-the-corpus-reads-nestor-and-finds-it-nearly-unreadable--measured) | The corpus reads Nestor, and finds it nearly unreadable | measured |
| [6.83](docs/agent-log.md#683-the-first-real-bookmark-and-a-whole-category-of-authorship-the-method-cannot-see--measured-attribution-open) | The first real bookmark, and a whole category of authorship the method cannot see | measured, attribution open |
| [6.84](docs/agent-log.md#684-delegation-counts-and-the-inference-i-made-about-it-was-wrong--shipped-one-fork-open) | Delegation counts, and the inference I made about it was wrong | shipped, one fork open |
| [6.85](docs/agent-log.md#685-litellm-dropped-and-the-record-remembers-three-where-the-operator-remembers-one--measured) | litellm dropped, and the record remembers three where the operator remembers one | measured |
| [6.86](docs/agent-log.md#686-the-late-july-batch-and-three-kinds-of-nothing--measured) | The late-July batch, and three kinds of nothing | measured |
| [6.87](docs/agent-log.md#687-the-homestead-batch-three-more-empty-repositories-and-three-the-session-cannot-read-at-all--measured-three-repositories-blocked) | The homestead batch, three more empty repositories, and three the session cannot read at all | measured, three repositories blocked |
| [6.88](docs/agent-log.md#688-willow-mcp-a-fourth-persona-schema-and-twenty-documents-that-exist-twice--measured) | willow-mcp: a fourth persona schema, and twenty documents that exist twice | measured |
| [6.89](docs/agent-log.md#689-yggdrasil-a-corpus-already-in-pair-form-of-which-29002-rows-are-refused--measured) | yggdrasil: a corpus already in pair form, of which 29,002 rows are refused | measured |
| [6.90](docs/agent-log.md#690-sean-data-vault-under-an-allowlist--and-the-chronology-closes-at-100-of-105--measured) | sean-data-vault, under an allowlist — and the chronology closes at 100 of 105 | measured |
| [6.91](docs/agent-log.md#691-the-log-fed-to-the-thing-it-is-about--119-claims-and-a-status-the-legend-defines-and-nobody-has-ever-used--measured) | The log, fed to the thing it is about — 119 claims, and a status the legend defines and nobody has ever used | measured |
| [6.92](docs/agent-log.md#692-three-findings-from-the-640641-audits-that-were-deferred-and-were-living-only-in-merged-pr-prose--measured-fix-shipped) | Three findings from the §6.40/§6.41 audits that were deferred, and were living only in merged-PR prose | measured, fix shipped |
| [6.93](docs/agent-log.md#693-the-browser-signer-and-a-same-day-bug-it-was-possible-to-write-while-wiring-it--shipped) | The browser signer, and a same-day bug it was possible to write while wiring it | shipped |
| [6.94](docs/agent-log.md#694-the-decision-store-answers-its-own-questions-well-except-where-its-matcher-cannot-tell-two-decisions-apart--measured-fix-open) | The decision store answers its own questions well, except where its matcher cannot tell two decisions apart | measured, fix open |
| [6.95](docs/agent-log.md#695-nestor-calibrate-warns-about-a-too-small-corpus-in-the-readmes-prose-not-in-the-output-a-parser-reads--measured-fix-shipped) | `nestor calibrate` warns about a too-small corpus in the README's prose, not in the output a parser reads | measured, fix shipped |
| [6.96](docs/agent-log.md#696-local-ollama-embeddings-as-a-shipped-matcher---matcher-ollama--shipped) | Local Ollama embeddings as a shipped matcher (`--matcher ollama`) | shipped |
| [6.97](docs/agent-log.md#697-detailpanel-renders-two-literal-null-text-nodes-into-the-provenance-card--verified-fix-open) | `detailPanel` renders two literal `null` text nodes into the provenance card | verified, fix open |
| [6.98](docs/agent-log.md#698-bench-and-scriptsaudit_py-inherit-the-ambient-keyring-and-report-a-false-fails--measured-fix-open) | `bench/` and `scripts/audit_*.py` inherit the ambient keyring, and report a false `FAILS` | measured, fix open |
| [6.99](docs/agent-log.md#699-an-llm-standing-in-for-the-embedder-is-self-consistent-inside-a-conversation-and-drifts-between-them--measured-fix-open) | An LLM standing in for the embedder is self-consistent inside a conversation and drifts between them | measured, fix open |
| [6.100](docs/agent-log.md#6100-one-gate-for-every-change-class-and-what-that-costs-a-session-with-a-human-waiting-in-it--measured-fix-open) | One gate for every change class, and what that costs a session with a human waiting in it | measured, fix open |
| [6.101](docs/agent-log.md#6101-the-corpus-extractors-do-not-fail-closed-and-the-test-named-for-them-covers-a-different-family--verified-fix-open) | The corpus extractors do not fail closed, and the test named for them covers a different family | verified, fix open |
| [6.102](docs/agent-log.md#6102-the-extractors-walk-the-working-tree-so-following-this-repos-own-setup-instructions-poisons-its-corpus--verified-fix-open) | The extractors walk the working tree, so following this repo's own setup instructions poisons its corpus | verified, fix open |
| [6.103](docs/agent-log.md#6103-a-model-survey-of-vendors-got-two-licences-exactly-backwards-in-the-same-row--verified-fix-open) | A model survey of vendors got two licences exactly backwards, in the same row | verified, fix open |
| [6.104](docs/agent-log.md#6104-the-jeles-source-registrys-gaps-live-in-a-feeders-stdout-and-i-misreported-one-by-reading-the-top-of-it--measured-fix-open) | The jeles source registry's gaps live in a feeder's stdout, and I misreported one by reading the top of it | measured, fix open |
| [6.105](docs/agent-log.md#6105-the-fleets-own-decision-record-is-invisible-to-every-corpus-extractor--verified-fix-open) | The fleet's own decision record is invisible to every corpus extractor | verified, fix open |
| [6.106](docs/agent-log.md#6106-where-the-decision-stores-retrieval-actually-fails-rank-is-fine-for-content-bearing-questions-and-collapses-for-question-shaped-ones--measured-fix-open) | Where the decision store's retrieval actually fails: rank is fine for content-bearing questions and collapses for question-shaped ones | measured, fix open |
| [6.107](docs/agent-log.md#6107-the-ui-was-built-for-an-operator-who-read-the-docstrings-the-audience-it-is-about-to-meet-has-not--shipped-one-follow-up-open-js-test-harness) | The UI was built for an operator who read the docstrings; the audience it is about to meet has not | shipped, one follow-up open (JS test harness) |
| [6.108](docs/agent-log.md#6108-the-web-sessionstart-hook-depends-on-an-env-var-the-runtime-did-not-set-fails-silently-and-the-seat-policy-that-would-have-caught-the-miss-fails-through-the-same-door--verified-fix-shipped-residual-parent-rooted-multi-repo) | The web SessionStart hook depends on an env var the runtime did not set, fails silently, and the seat policy that would have caught the miss fails through the same door | verified, fix shipped (residual: parent-rooted multi-repo) |
| [7.1](#71-skills--shipped-83) | Skills | shipped (#83) |
| [7.2](#72-hooks--shipped-87-88-105) | Hooks | shipped (#87, #88, #105) |
| [7.3](#73-rubrics--open-the-criterion-the-brain-scored-against-first) | Rubrics | open (the criterion the brain scored against first) |
| [7.4](#74-the-list-goes-on--open-the-loop-is-the-catalog) | The list goes on | open (the loop is the catalog) |
| [7.5](#75-the-gaps--open-standard-parts-the-loop-doesnt-have-yet) | The gaps | open (standard parts the loop doesn't have yet) |
| [8.1](#81-what-the-industry-is-trying-to-build--hypothesis) | What the industry is trying to build | hypothesis |
| [8.2](#82-what-im-trying-to-build--hypothesis) | What I'm trying to build | hypothesis |
| [8.3](#83-where-the-two-cross--hypothesis) | Where the two cross | hypothesis |

---

## 1. Correctness — the seal that shouldn't have served

The thing that makes Nestor Nestor is that a tier-1 answer is served verbatim,
marked verified, with no review queue. So the failure mode that matters is a
phrase which was never verified being served as though it were. Everything in
this section is downstream of that.

### 1.1 Margin, not just magnitude — **measured; mostly falsified**

*The hypothesis was: a false seal happens when many sealed rows resemble the
probe about equally, so the gap between best and second-best should separate a
genuine match from a coincidental one — attacking false seals without the recall
cost of raising the threshold. I called it the highest-value change on this list.
It is not.*

`bench_margin.py`, threshold 0.92, false-seal % / recall %
(`bench/results/margin.json`):

| margin | boil 2k | boil 8k | boil 24k | prose 2k | prose 4k |
|-------:|--------:|--------:|---------:|---------:|---------:|
| 0.00 | 1.6 / 100 | 8.0 / 100 | 16.0 / 100 | 4.8 / 99.6 | 6.8 / 100 |
| 0.03 | 1.6 / 100 | 6.0 / 100 | 10.0 / 99.2 | 4.4 / 99.2 | 6.4 / 98.0 |
| 0.05 | 1.6 / 99.6 | 3.2 / 98.4 | **4.0 / 96.8** | 4.4 / 96.8 | 6.0 / 93.6 |
| 0.10 | 0.0 / 91.2 | 0.4 / 70.8 | 0.0 / **44.4** | 3.6 / 91.6 | 5.2 / 88.4 |

**On homogeneous text it half-works.** Boilerplate 24k at margin 0.05 cuts false
seals 16.0% → 4.0% for 3.2 points of recall. Real, but not free, and nowhere near
the clean separation the hypothesis predicted — pushing to 0.10 eliminates false
seals and destroys recall (44%).

**On prose it does nothing but cost recall.** 6.8% → 6.0% at margin 0.05 while
recall falls 100% → 93.6%. Strictly worse than simply raising the threshold.

The distributions overlap, which is the real verdict. Gap between true-match p10
and false-seal p90 — positive means separable:

| | boil 2k | boil 8k | boil 24k | prose 2k | prose 4k |
|---|---:|---:|---:|---:|---:|
| gap | +0.018 | −0.001 | +0.012 | −0.050 | −0.103 |

**Why it fails, which is the part worth keeping.** The hypothesis assumed false
seals arise from *crowding* — many near-equal candidates. That is true only in
templated corpora. In prose a false seal comes from a **genuine near-duplicate**:
one sentence that really is nearly identical to the probe, with nothing else
close. So the margin is *wide* precisely when the answer is wrong, and the signal
inverts. Crowding is an artifact of homogeneous text, not a property of false
seals.

Not worth shipping as a global rule. Possibly worth it as a per-domain option for
templated corpora, where it beats raising the threshold — but §1.3's calibration
work should decide that, not this idea on its own.

Caveat on the recall column here: `bench_margin.py` still uses the **surface**
perturbations, where most probes score exactly 1.0, so its margin is
`1.0 − second` and the recall cliff at 0.10 is partly an artifact of how close
the rest of the corpus sits to an exact match. Re-running it against the
paraphrase tier would only make the verdict more negative — paraphrase probes
score lower, so their margins are narrower — so it was not worth re-running to
overturn a conclusion that is already "no". The false-seal column never depended
on the perturbation set.

**What the failures actually look like, and why no scalar rule catches them.**
Every worst-case collision differs from the phrase it was served *only in the
identifier*:

```
asked : the joint term triggers any joint breach under section 5386
served: the joint term triggers any joint breach under section 756    sim=0.974
```

A character-ratio matcher is blind to *which* characters carry the meaning. 0.974
clears any cutoff that preserves recall, and the margin measurements above show
the runner-up gap does not reliably collapse either. So neither threshold nor
margin — the two knobs available on top of a scalar similarity — can separate
these. The fix has to change what is being *compared*: weight identifier-like
tokens, or go semantic (§3.1/§3.3).

### 1.2 Negative seals — **shipped**

*Was: a human could seal "this match is right" but never record "this match is
wrong," so a bad fuzzy hit came back identically forever and human attention
leaked out of the system.*

Implemented as two distinct refusals, because collapsing them would have been a
bug:

* **`reject_pair(pair_id, …)`** — the mapping itself is wrong. Sets
  `status='rejected'`; never served, never offered as engine context again.
* **`reject_match(source_text, …, pair_id=/target_text=)`** — *this pair is the
  wrong answer for this query*. The pair stays valid for its own source text.

The second is the false-seal case from the bench, and it is the one that had no
home in the schema. A false seal is a **correct** pair matched to the wrong
input, so rejecting the pair would destroy a good verification. It needed a new
table (`tm_rejections`) keyed on the query, not on the pair.

Design decisions worth remembering:

* **Enforcement lives in `lookup()`**, not `best_sealed()`. Every serve path —
  `best_sealed`, engine TM context, the entity resolver, the reconciler — goes
  through `lookup`. Filtering one level up would have left a rejected pair still
  reaching the engine's system prompt as authoritative reference material.
* **Rejections are honored even when their signature does not verify**, which is
  the opposite of how seals are treated. The two fail in opposite directions:
  honoring a forged seal serves unverified content as verified, whereas honoring
  a forged rejection merely withholds an answer and degrades to human review —
  the defined safe state. It grants an attacker nothing either, since writing a
  forged rejection needs store write access, and anyone with that could delete
  the sealed row instead. Validity is still recorded and surfaced via
  `rejection_signature_report` for the curator.
* **Rejection signatures are domain-separated** from seal signatures (a literal
  `"rejection"` tag as element 0 of the signed message), so one can never be
  replayed as the other.
* **The capability is optional and all-or-nothing.** A host store predating it
  keeps working; `supports_rejection()` reports partial implementations as no
  support, because writing rejections nobody reads back is worse than not having
  the feature. `reject_*` raises rather than silently dropping a human's "no".

**Reading them back — shipped.** For a while the remaining line here was that
nothing consumed rejections as *signal*. `Curator.rejection_signals()`,
`nestor rejections` and the UI's Signals tab now do: a query refused several
times over is evidence about the **threshold** in that domain (§1.3), and a pair
refused against many unrelated queries is evidence about the **pair**. Read from
the ledger rather than the store — `memory_rejections` answers "what was refused
for this query", which is what serving needs, and there is no enumerate call;
adding one would change the Storage Protocol every host implements, for a
reporting feature. The number of entries read is reported, so a rotated chain
shows as a smaller sample rather than as a clean bill of health.

It deliberately stops short of proposing a threshold. The score a rejected match
was made at is not recorded, so this says the dial is wrong here and hands over
to §1.3's calibration.

### 1.3 The threshold should be calibrated, not constant — **measured; the calibration shipped**

`SEAL_THRESHOLD = 0.92` is a single global constant across every domain, and no
single value works. Complete sweep, 250 probes per cell, false-seal rate
(`bench/results/accuracy.json`):

| threshold | boil 500 | boil 2k | boil 8k | boil 24k | prose 500 | prose 2k | prose 4k |
|-----------|---------:|--------:|--------:|---------:|----------:|---------:|---------:|
| 0.90 | 2.8% | 10.8% | 36.4% | 56.4% | 2.4% | 5.6% | 10.0% |
| **0.92** (shipped) | 0.4% | 1.6% | 8.0% | **16.4%** | 2.0% | 4.8% | 6.8% |
| 0.94 | 0.0% | 0.4% | 1.6% | 4.8% | 0.8% | 4.0% | 3.6% |
| 0.96 | 0.0% | 0.0% | 1.2% | 0.4% | 0.0% | 1.2% | 1.6% |
| 0.98 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.4% | 0.8% |

**The "free six points" claim this section used to make is dead.** It rested on a
recall column measured with perturbations that normalization erased. With a real
paraphrase tier (`bench_accuracy` now reports `recall_surface` and
`recall_paraphrase` separately), raising the threshold is expensive:

| threshold | boil 24k false-seal | boil 24k paraphrase recall | prose 4k false-seal | prose 4k paraphrase recall |
|-----------|--------------------:|---------------------------:|--------------------:|---------------------------:|
| 0.90 | 56.4% | 38.4% | 10.0% | 62.4% |
| **0.92** | 16.4% | **23.6%** | 6.8% | **60.0%** |
| 0.94 | 4.8% | 6.8% | 3.6% | 56.0% |
| 0.96 | 0.4% | 2.4% | 1.6% | 43.6% |
| 0.98 | 0.0% | 0.0% | 0.8% | 15.6% |

Surface recall reads 100% in every one of those cells. That gap *is* the finding:
the old column measured whether near-identical input still matches, which was
never in question.

**There is no threshold that is simultaneously safe and useful.** At 0.96 the
24k boilerplate case is clean (0.4% false seals) and effectively dead (2.4%
paraphrase recall). At 0.92 it serves more real rewrites and gets one in six
answers wrong. Every cutoff is bad at one of the two jobs, on both corpora.

That is a limit of character-ratio matching, not of threshold choice, and it is
now the strongest argument on this list for §3.1/§3.3 — widening the seam so a
semantic matcher can be used at all. Tuning `SEAL_THRESHOLD` cannot fix it.

Note the two corpora are not equally stressed: a synonym swap in an 11-word
boilerplate phrase changes ~9% of its tokens, while dropping one stopword from a
long prose sentence changes far less (paraphrase score p50 is 0.0 — i.e. below
the 0.80 floor — for boilerplate, versus 0.95 for prose). The direction holds on
both; the magnitudes are not comparable across corpora.

**Two separate scaling stories, and the prose one is worse than it looks.**
Boilerplate degrades faster with size (0.4% → 16.4%) but is a synthetic worst
case. Prose is real English and still reaches 6.8% at only 4,000 pairs, with a
score distribution whose p50 is ~0.48 — i.e. the *average* probe is nowhere near
danger and the tail still clears 0.98. A diverse corpus feels safe and is not,
because real corpora contain genuine near-duplicates.

The paraphrase tier that settles this was added in `corpora.py`: meaning-
preserving rewrites (synonym substitution from a curated table, clause
reordering, contraction, and a guaranteed stopword-drop fallback) that survive
normalization. 0% of boilerplate and 5% of prose paraphrases normalize to an
identical key, against 80% for the surface tier.

**The calibration mode now exists** — `nestor.calibrate` / `nestor calibrate`.
It does not import these corpora; it measures the memory a deployment actually
has, by asking the one question that needs no probe set: for each sealed pair,
which *other* sealed pair scores highest against it **and has a different
target**? That is a false seal by definition, already present, between two
things a human deliberately verified. It reports the rate at every cutoff in
this same sweep, recommends the lowest one meeting a target rate, and says so
when none does — that last case being a corpus problem rather than a dial
problem, and worth naming as such.

Two limits it states in its own output. It is a **lower bound**: real queries
include text the memory has never held, and this can only see collisions the
corpus already contains. And it cannot see recall — a memory holds no record of
the paraphrases nobody has asked yet — so the trade above still has to be read
from the bench. It changes nothing on its own: moving the threshold is a
decision about how much unverified content you will serve, and that belongs to
a person.

That is also the honest marketing story (§4.2): not "we are accurate," but "here
is your false-verification rate, measured on your corpus, and here is the dial."

### 1.4 Seal staleness and quorum — **measured**, design **open**

Every seal is equally authoritative forever, and one verifier is enough. Neither
is obviously right for a regulated buyer. Worth considering: seal age surfaced
in provenance; a `weight` that decays; N-of-M verification for high-stakes
domains. ~~The ledger already records who sealed what and when, so the data is
there — nothing consumes it.~~

> **Corrected in place, 2026-08-06**, by trying to argue the entry through:
> [`docs/seal-staleness-and-quorum.md`](docs/seal-staleness-and-quorum.md). The
> ledger records who sealed what and when for the **first** seal. It records
> nothing about agreement. Two verifiers sealing one source with the same target
> produces one row, one chain entry, and no trace of the second person —
> measured, on a file-backed store with signing on. `memory.py:374` writes only
> when the row is not already sealed *or* the target differs, so concurrence
> satisfies neither arm and returns the stored row to the caller as if it were
> theirs.
>
> So the premise "the data is there" is false for quorum specifically, and it is
> the load-bearing premise: N-of-M cannot be computed from a history that was
> never written, and no migration can backfill countersignatures that were
> discarded. See §6.26.

The memo's three conclusions, in brief:

* **Decay must not live in `weight`.** The column is written by every seal path,
  read by nothing in ranking, and absent from `signing._message` — so a decayed
  weight is unsigned mutable state anyone with write access can reset while
  every signature still verifies. Age should be derived from the ledger's
  timestamp, which the chain covers, not stored beside the data it governs.
* **Neither staleness nor quorum should change what is served silently.** A
  decay multiplier turns "a human checked this" back into a confidence score —
  the exact thing the README's first paragraph refuses — and withdraws a
  verified answer on a date nobody chose, leaving the ledger with no decision to
  point at. Staleness belongs in the curator queue, shaped like `reopen_when`.
* **Sub-quorum is not a weaker seal; it is a draft.** That keeps the guard in
  the one place a row becomes sealed rather than in every serving path, and
  avoids inventing a "70% sealed".

Still open, and named as open in the memo: how old is too old, and whether any
buyer actually asks for either. The third item this once named — that a quorum of
HMACs is a quorum only against outsiders — has since closed: per-verifier Ed25519
signing landed (decisions `0074`/`0077`/`0078`, `signing.py`), so a
countersignature can no longer be forged by anyone holding a shared key. What
stays open is deeper and unchanged by that: a quorum is still not *recorded* at
all (§6.26), so N-of-M has no history to compute from regardless of the signature
scheme.

### 1.5 A numeric label could hold several baselines — **shipped**

*Was: `Reconciler.seal_baseline` let a label accumulate baselines, and `check`
scored an observation against whichever it sat nearest.*

Found while building the numeric view of the UI (§5.4). The conflicting-seal
guard in `add_pair` keys on the **normalized source**, and under a
`NumericMatcher` every figure is its own key — so a second baseline for a label
was never an overwrite to catch, it was an insert. Both stayed sealed. Then
`check` ranked by similarity, i.e. by nearness to the observation, which is
precisely the wrong tie-break: the figure most likely to excuse an observation
is the one closest to it. Reproduced —

```
seal_baseline("ceiling", "$5,000,000", verifier="auditor")   # superseded
seal_baseline("ceiling", "$1,000,000", verifier="auditor")   # the standing one
check("ceiling", "$4,900,000")  ->  flagged: False           # against the old ceiling
```

A recipe whose entire job is to flag a deviation must not let a caller add the
baseline that excuses it. `seal_baseline` now raises `ConflictingSealError` when
a different verifier restates a label's figure, retires the superseded baseline
on a self-correction or explicit override, and ledgers `baseline_replaced`.
`check` uses the **newest** baseline, not the nearest, and reports `ambiguous`
with a count when more than one stands — which is what a store that cannot
retire (no curation capability) now degrades to, loudly, instead of silently.

Worth noting what this is an instance of: **the shared guards protect a recipe
only as far as the matcher's notion of identity reaches.** The entity recipe is
fine — two canonicals for one alias collide on the same normalized surface, so
`add_pair` catches it. Any future matcher whose normalization makes distinct
values distinct keys needs its own uniqueness rule, and §3.1's warning about the
seam being lossy has a second edge here: what the normalizer *separates* matters
as much as what it collapses.

### 1.6 A seal could be made without being ledgered — **shipped**

*Was: `memory.add_pair(status="sealed")` wrote nothing to the chain.*

Found by a CLI test that filtered the ledger for `seal` entries and got none,
against a database that had two sealed pairs in it. The seal entries in the chain
came from the *callers* that happened to write one — `graduate_segment`, the
recipes, the UI — so the shortest path to a sealed row, and the one every
importer and host integration takes, produced a verified answer with no trail.
Meanwhile the README's first paragraph promised every seal was appended.

The entry is written from `add_pair` now, which is the one function that turns a
pair into a sealed one, so the promise holds regardless of entry point.
`graduate_segment`'s own entry became `segment_sealed` — which segment, in which
document, a human decided — so the trail carries both facts and says "seal" once.
`seed_from_corpus` passes `audit=False` and writes a single `corpus_seed` entry
instead, because a 10k-pair curated import is one act by one non-human verifier
and burying every human decision under ten thousand lines would be its own kind
of unauditable.

**A follow-up found the same fix had inverted the priorities.** Routing the entry
through `_log_seal_event` — which swallows ledger failures so a bulk import
cannot half-write — meant a seal onto a *broken chain* was accepted, served, and
recorded nowhere, while `reject_pair` and `unseal` on the same chain raised and
refused. Granting trust failed open; withdrawing it failed closed. Exactly
backwards, and invisible because both paths "worked".

`cascade.ledger_preflight()` now applies the append's refusals *before* the store
is touched, so a decision that cannot be audited is refused rather than made, and
the post-write append warns instead of passing silently. A draft still lands on a
broken chain, which is the right line: a draft is not a verification.

Worth naming the pattern, because it is the second instance: **a guarantee
enforced by convention at call sites is not enforced.** The first was
`is_verified_seal` (§1.2's regression — a bare `status == "sealed"` filter one
file over). Both were fixed the same way: move the rule into the single function
that cannot be bypassed.

### 1.7 An import could revive a pair a human had rejected — **shipped**

*Was: `portable.import_bundle(override_conflicts=True)` wrote through
`store.memory_seal` directly, so `RejectedPairError` — which `add_pair` raises
for exactly this — was structurally unreachable. A pair rejected as fraudulent
came back sealed and serving, and the report said "sealed: 1".*

Found by an adversarial read of the docs against the code, and it is §5.2's bug
wearing a different coat: a guarantee enforced at one call site, and a second
path into the store that never passes it. The first time it was
`graduate_segment`; this time it was a file.

The fix is a second switch, not a stronger one. `override_conflicts` means
"their answer wins where we disagree", and a rejection is **not** a competing
answer — it is a decision that the mapping is wrong. So rejected rows get their
own bucket in the report, their own warning, their own CLI line, and their own
`override_rejections` flag, mirroring the two `add_pair` has had all along. The
UI deliberately has no checkbox for it: reviving a rejection through a file
import should cost a considered command, and `Curator.restore` is the documented
way back.

### 1.8 Two threads could seal the same phrase, and both won — **shipped**

*Was: `add_pair` read, decided, then wrote, with nothing making that atomic and
no key constraint behind it. Two concurrent seals of the same new source each
found nothing and each inserted — two sealed rows for one normalized source, no
`ConflictingSealError`, and no answer to which one serves.*

Reachable the moment the UI existed: it serves from a thread pool, so two
reviewers pressing **Seal** on the same phrase is all it takes. The guard was
written when every caller was a REPL.

Fixed in two places, because a check and an invariant are different things. The
reference store now carries a unique index on `(source_norm, source_lang,
target_lang)` — the invariant the curator, the exporter and every serve path
already assumed, now enforced by something no caller can talk past. And
`add_pair` catches the collision, re-reads, and takes the existing-row path, so
the loser gets the `ConflictingSealError` it should have had. A pre-existing
database holding duplicates cannot take the index; that degrades with a warning
naming the count rather than failing every later call.

**The ledger had the same disease, and worse consequences.** `_ledger_append`
read the tail and wrote the next line unsynchronized: eight threads appending
concurrently wrote all 160 entries and left a chain `verify()` rejects. Not a
lost entry — a trail that indicts itself, on the one file whose integrity is the
product. It is now `ledger_append` (public, since six modules import it), holding
a process lock and an advisory file lock, with the FRANK forward moved outside
both so a slow mirror cannot stall a review queue.

### 1.9 The numeric matcher takes the first number it finds — **shipped**

`NumericMatcher.parse` strips `$ , %` and then *searches* for a number, so
`"1,00o,000"` — one typo — parses as **100**, and `"12/31/2024"` parses as 12.
Its docstring says "extract a number … or None", so this is the documented
behavior, not a bug against its own contract.

Whether it is the right contract for a reconciler is the open question. The
failure direction is currently safe: a typo produces a wildly wrong figure, which
gets *flagged*, and a human looks. But the reverse exists — a stray leading token
in an otherwise correct figure is silently dropped — and "the number I compared
was not the number you typed" is a bad sentence to have to say in an audit.
Requiring the whole cleaned string to parse was the other option, and it is
wrong: it breaks `"$1,000,000 USD"`, which is an ordinary way to write a figure.
So the signal shipped is not "was anything left over" but **"was a *digit* left
over"** — `"USD"` is decoration, `"o000"` and `"/31/2024"` are the rest of a
number that never reached the comparison. That separates the two failures above
from the legitimate case exactly, with no false alarm on currency or units.

`NumericMatcher.parse_detail` returns the figure with what it had to ignore;
`check()` carries `observed_text` / `observed_partial` and the same pair for the
baseline; `seal_baseline` warns, because a partially-read *baseline* is the one
case where the discrepancy is permanent — the row says `"$1,00o,000"` forever
and every future check runs against 100. The ledger records the flags and not
the raw strings, since `nestor.frank` mirrors entries verbatim into somebody
else's ledger.

Reporting beat refusing: a reconciler that rejected every partially-parsed
figure would refuse real inputs, and the person who can tell a typo from a unit
suffix is the human this package exists to keep in the loop.

---

## 2. Performance — the scan

**measured** (`fill.py`, session of 2026-07-25; to be folded into a bench):
lookup is linear in corpus size — 293 ms @ 2k pairs, 4.4 s @ 32k, projecting to
~135 s @ 1M. **97% of that is Python-side `difflib`, not SQL** (112 ms fetch vs
4,260 ms scoring at 32k). The database is not the bottleneck; the scoring loop is.

### 2.1 Lossless prefilter via difflib's own bounds — **shipped**

`SequenceMatcher` exposes `real_quick_ratio()` (length-based) and
`quick_ratio()` (multiset-based) as progressively tighter upper bounds on
`ratio()`. Confirmed in-repo on 20,000 random pairs:
`ratio() <= quick_ratio() <= real_quick_ratio()`, no violations.

So candidates whose upper bound cannot beat the incumbent best can be skipped
**without computing `ratio()` at all, and without changing a single result.**
Implemented as `bench.bench_accuracy.best_match_fast` and measured against the
naive scan over 120 probes, **0 disagreements** on both corpora:

| Corpus | Rows | Naive | Pruned | Speedup |
|--------|------|-------|--------|---------|
| boilerplate | 3,000 | 39.1 s | 10.1 s | **3.9x** |
| prose | 2,991 | 52.6 s | 50.9 s | **1.0x** |

**The prose result is the interesting one.** Pruning only bites once a *high*
incumbent exists — on diverse prose the best score stays low (p50 ≈ 0.49), the
bound almost never falls below it, and nothing gets skipped. So as a general
speedup this is corpus-dependent and worth much less than it first looks.

**But `best_sealed` doesn't need the argmax — it needs "anything ≥ threshold."**
Seeding the incumbent at the threshold instead of `0.0` makes every candidate
below it skippable from the first row rather than only after a good match turns
up. Implemented as `best_match_fast(..., floor=)` and measured on *absent*
probes — the case that previously pruned worst:

| Corpus | Naive | floor=0.0 | floor=0.80 |
|--------|------:|----------:|-----------:|
| prose 4,000 | 22.1 s | 18.9 s (1.2x) | **2.5 s (8.8x)** |
| boilerplate 24,000 | 94.2 s | 15.3 s (6.1x) | 15.5 s (6.1x) |

Zero disagreements above the floor in both. The floor is what rescues prose,
exactly as predicted; boilerplate gains nothing extra because every probe there
already scores above 0.80, so nothing is censored. This turned a 24k row that
had failed to finish in 53 minutes into ~5 minutes, and made the complete
7-row sweep possible.

**Ship this in `best_sealed`.** `lookup()` cannot use it — it must return
sub-threshold candidates as engine context — so it wants to be a distinct fast
path, not a change to the shared scan.

Two caveats found while implementing it, both easy to get wrong:

* **`ratio()` is not symmetric.** `StringMatcher` computes
  `SequenceMatcher(None, probe, row)`. Swapping the operands to let difflib
  cache its `b2j` index across candidates measures a different function.
* **`autojunk` changes results** on sequences of 200+ elements, so it must be
  left at the default.

Both would produce a plausible, slightly-wrong benchmark. The equivalence check
(`--equiv`) exists because of them.

**Shipped**, as `StringMatcher.similarity_bound` plus `best_sealed`'s own scan.
Re-measured on landing: 4,000 sealed rows, 40 absent probes, 35.6 s → 2.4 s
(**14.7x**), identical answers. The bound is a matcher method rather than a
difflib call inside `memory` — the seam is where domain knowledge lives — and it
is deliberately *not* in the `Matcher` Protocol: `NumericMatcher` gains nothing
from a bound on two floats, and requiring it would break every custom matcher
already injected. No bound offered, no pruning, same answer. The length bound is
inlined rather than taken from a `SequenceMatcher`, because constructing one
indexes the second sequence, which costs more than the cheap question is worth.

Writing it turned up something the performance work was not looking for.
`best_sealed` filtered `lookup()`'s result, and `lookup` defaults to `limit=5`.
Six drafts scoring above a sealed row is not exotic — the engine writes a draft
for every near miss — and they pushed a human's verification off the end of the
list, so tier 1 answered "nothing verified, here is a fresh draft" while the
seal sat in the memory matching at 0.933. There is no top-N to fall out of now.

Do this before anything lossy — and there is still nothing lossy.

### 2.2 Trigram blocking — **measured, disappointing**

A 4-gram prefilter gave only **2.4x** (4,372 ms → 1,818 ms) because 43% of
candidates survived it. That number is from the homogeneous boilerplate corpus,
which is the worst case for blocking — on diverse prose it should do far better,
and that is worth measuring before judging the idea. Lossy, unlike §2.1.

### 2.3 Index `source_norm` — **shipped**

`memory_find` runs on every `add_pair`. Fresh reference databases get
``idx_tm_pairs_key_live`` on ``(source_norm, source_lang, target_lang)`` — a
**partial** unique index (``WHERE superseded_by = ''``, live rows only; the old
full ``idx_tm_pairs_key`` is dropped, since a full one could never keep a
superseded predecessor) — the same unique index §1.8 added for concurrent seals,
which also satisfies the measured ~2.3× ingest win (bench session 2026-07-25). If duplicates already exist and the
unique index cannot be created, ``idx_tm_pairs_find`` on the same columns is
installed so lookups stay indexed while the operator resolves the dupes.

### 2.4 Connection-per-operation — **shipped (file-backed reuse)**

`SqliteStore._db()` used to open and close a fresh connection for every call on
file-backed databases, and `add_pair` additionally calls `memory_init()`, which
replays the whole schema script each time. I hypothesised this dominated ingest
and **was wrong** — stubbing `memory_init` out made things marginally *slower*,
i.e. it is noise at this scale. Recorded here so nobody re-derives the same dead
end.

**There is now a threaded consumer.** `nestor.ui` serves from a thread pool; the
in-memory store keeps one shared connection behind an ``RLock``. File-backed
stores keep a **bounded pool of idle connections** (``_POOL_MAX``, 8) under
``PRAGMA journal_mode=WAL``, so concurrent reviewers reuse connections instead of
paying connect/teardown on every API call. Measured, 3000 single-row reads:

| | time |
|---|---|
| a fresh connection per operation | 0.857s |
| a persistent connection per thread | 0.042s |
| a bounded idle pool | 0.045s |

The pool exists rather than a connection per thread because of how the threads
arrive. `ThreadingHTTPServer` under HTTP/1.1 keep-alive makes one thread per TCP
connection — a reload, a reconnect, a monitoring probe — and a connection bound
to a thread outlives it: `sqlite3.Connection` sits in reference cycles, so it is
freed by the *cyclic* collector rather than promptly, and nothing about running
out of file descriptors makes Python collect. Under ``ulimit -n 256`` the
per-thread version failed after **340 requests** with ``unable to open database
file`` where connection-per-operation ran 2000 clean; that also refuses seals,
because the ledger needs to open a file too. The pool keeps essentially all the
speed and caps descriptors at the pool size: anything borrowed beyond it is
closed on return, not accumulated.

``close()`` checkpoints the WAL into the main file and retires the store; using
one afterwards raises ``StoreClosedError`` rather than quietly reopening, which
for ``:memory:`` used to mean answering "0 sealed" from a fresh empty database.

~~Still open: skipping redundant ``memory_init`` schema replay per connection
(measured as noise for ingest; may matter only at huge table counts).~~
**Shipped (§6.8).** Measured a second time, the replay was *not* noise: a
``schema_ready`` latch on the connection (``sqlite_store.py``) cut 0.556 → 0.395
ms/op, −28.9%. "Noise does not survive being measured a second time."

---

## 3. The Matcher seam

### 3.1 The seam is lossy by construction — **shipped**

`normalize(value) -> str` is the dedup key in `memory_find` and what gets
persisted as ``source_norm``. Scoring used to go only through
``similarity(a_norm, b_norm)`` on those keys, so anything that did not survive
normalization was gone by scoring time (the acronym case below).

**Optional ``score(raw_a, raw_b)``** — when a matcher implements it,
``memory.lookup``, ``memory.best_sealed``, and ``nestor.calibrate`` compare the
query's raw text to each row's ``source_text`` via ``score``. ``similarity`` on
norms remains for matchers that do not offer ``score``. ``similarity_bound``
prefiltering is disabled when ``score`` is present (bounds are on norms only).

The original failure mode: I lost an acronym match (`AWS` → `Amazon Web
Services`) purely because my normalizer sorted its tokens, and the information
needed to recover it no longer existed by scoring time. Worse, that same string
is simultaneously the store's exact-match dedup key in `memory_find`. Scoring
wants rich structure; deduplication wants aggressive collapse. **These two jobs
pull in opposite directions, and one string served both** — until ``score``
split them.

This is the change that unblocks embedding/semantic matchers without smuggling a
vector through a SQL key: ``normalize`` stays the dedup key; ``score`` (or a
matcher that implements it with embeddings) sees the originals.

### 3.2 Recipes the seam already supports — **verified**

Written from outside the package, with **zero changes to `nestor/`**:

- **`DateMatcher`** — normalizes `Q3 2025`, `September 30, 2025` and
  `30/09/2025` to one ordinal; scores by day-window tolerance. A temporal
  alignment engine with sealed provenance, for ~30 lines.
- **Schema mapping** — messy CSV headers → canonical field names, using
  `EntityResolver` **unchanged**, just with a token matcher. `'TOTAL DUE'` →
  `amount_due` at 1.0; `'Name of Customer'` correctly queued for review at 0.667.

The README advertised three recipes; the seam supports a category. The UI's Ask
view narrowed that gap by exposing the seam itself as a fourth choice — any two
domain tags, either shipped matcher, showing the normalized key and every
candidate's score — so a custom recipe is drivable without writing a surface for
it. What is still true is that a matcher written outside the package cannot be
selected from a UI or an MCP call, because a name off a wire cannot conjure one;
it has to be injected in code (`memory.set_matcher`). The rest is positioning
(§4.1).

### 3.3 Semantic matcher — **shipped (optional extra)**

``pip install nestor[semantic]`` pulls in `fastembed` only — core stays
zero-dependency. :class:`~nestor.semantic_matcher.SemanticMatcher` keeps
:class:`~nestor.matcher.StringMatcher` normalization for dedup and implements
``score(raw_a, raw_b)`` with cosine similarity on a small bi-encoder (default
``BAAI/bge-small-en-v1.5``). Wired as ``matcher="semantic"`` on
``nestor match``, the UI Ask → Match view, and ``nestor_match`` over MCP.

Serving thresholds calibrated for character ``StringMatcher`` do not transfer;
re-run ``nestor calibrate`` on the corpus you intend to serve.

### 3.4 Model-authored surfaces — **measured; four stages, and the matcher
mattered more than the surfaces**

*The hypothesis: the acronym/synonym miss class is answerable by sealing several
lexically different **surfaces** for one meaning — the shape `entity.py` already
uses — rather than by a semantic matcher (§3.3) and the dependency §3.3 is
reluctant to take. §3.1's own example is the case: `AWS` → `Amazon Web Services`
was lost because the information needed to recover it did not survive
normalization. Sealed as two surfaces, it never has to survive normalization,
because it was indexed in its own right.*

The mechanism is already in the package — `EntityResolver.seal` writes one row
per surface, N surfaces → one canonical target. So the missing piece is not a
matcher; it is **something to author the surfaces**, which a model does at seal
time having just read the sentence. That is a write-side one-to-many expansion,
`surfaces(raw) -> list[str]`, and neither `normalize` (1→1) nor §3.1's proposed
`score(raw_a, raw_b)` (2→float) can express it. §3.1 and §3.4 are different seam
changes, not the same one arrived at twice.

#### The result

`bench/bench_surfaces.py` on `corpora.aliased`, 1500 rows, 250 probes, seed 7
(`bench/results/surfaces.json`). Every arm holds **the same 1500 rows** — K
meanings × surfaces held constant — so index size and scan cost are equal and
only structure varies.

| K | meanings | recall @0.92 | false seals @0.92 | recall @0.96 | false seals @0.96 |
|--:|---------:|-------------:|------------------:|-------------:|------------------:|
| 1 | 1500 | 0.056 | 0.004 | 0.044 | 0.000 |
| 3 |  500 | 0.440 | 0.024 | 0.344 | 0.000 |
| 5 |  300 | 0.652 | 0.036 | 0.492 | 0.000 |

**At 0.96 the lift is 11× and it is free.** Recall 0.044 → 0.492 with zero false
seals at every K. §1.3 concluded there is no threshold that is simultaneously
safe and useful; on this corpus, surfaces move the safe threshold into
usefulness rather than trading one for the other. At 0.92 the lift is 12× for 9×
the false seals — real, but not free, and 0.96 is the better operating point.

> **Superseded by stage 3, and left standing.** The paragraph above is correct
> about `aliased` and wrong to have implied it generalizes. On human prose the
> entire score distribution tops out at 0.878 and recall at 0.96 is 0.000 in
> every arm. The claim is kept verbatim because *which* sentence overreached, and
> on what evidence, is the part worth being able to check later.

**Why the budget control mattered.** The naive reading holds meanings constant
and lets rows grow:

| K | budget | rows | recall @0.92 | false seals @0.92 |
|--:|--------|-----:|-------------:|------------------:|
| 5 | fixed-rows | 1500 | 0.652 | 0.036 |
| 5 | fixed-meanings | 7500 | 0.652 | **0.084** |

Recall is *identical* — it depends only on whether the probe's surface family
was sealed, not on how many other meanings share the index. False seals are
**2.3× higher**, and all of that is the corpus-size penalty (accuracy.json:
boilerplate 2k → 1.6%, 24k → 16.0%), not the surfaces. Measured the naive way,
surfaces look considerably more expensive than they are.

**Coverage, not bridging — the negative finding that matters.** Recall is
*always below* the fraction of the query distribution whose surface family was
sealed (0.056 vs 0.21; 0.440 vs 0.59; 0.652 vs 1.00), never above. Sealing
`Amazon Web Services` does **not** help you match `AWS`. There is no free
bridging between disjoint surfaces, which is precisely why the surfaces have to
be authored — and precisely the gap a semantic matcher would otherwise fill.
This is the strongest evidence for §3.4 and it arrives as a negative result.

#### Two blind harnesses, found and fixed — the reusable part

Both looked like clean results at the time. Recording them because the lesson
generalizes past this entry.

**Blind #1 — the corpus could not contain the case.** Run against
`boilerplate`/`prose`, recall was identical to three decimals across K and the
canonical surface won **117 matches out of 117**. That reads as a crisp
falsification. It was a property of `corpora.perturb`:

```
sim(original, paraphrase_A)     = 0.738
sim(paraphrase_A, paraphrase_B) = 0.624
```

Independent one-step perturbations of one phrase sit further from each other
than from the original, so the centroid is always the best bridge and extra
points around it are redundant. Meanwhile the target class sits at 0.27–0.50
(`AWS`/`Amazon Web Services` = 0.273). Those corpora cannot express it. Hence
`corpora.aliased`, whose intra-meaning dispersion (p50 **0.407**) is measured
into every result rather than asserted.

**Blind #2 — the probes were exact matches.** `perturb` does not bite on short
name-like surfaces: no company vocabulary in the synonym tables, no clauses to
reorder, no function words to drop, and a typo rule requiring >12 characters. So
88% of surface-tier and **100%** of paraphrase-tier probes normalized
*identically* to the row they were meant to find. "Recall" was measuring whether
the exact string had been sealed — a lookup test wearing a fuzzy-match costume,
and it produced a flattering `K=5 → 1.000 recall at 0.000 false seals` that was
one edit away from this entry. `corpora.aliased_query` replaces it with noise a
person actually introduces (suffix abbreviation, acronym dotting, word drop,
typo); `aliased_query_bite` measures the result — 31% still exact, p50 0.947 —
and the bench prints it every run and warns above 50%.

**The rule both times:** measure the property the harness depends on, *in the
harness, every run*. A corpus property asserted in a docstring is not a control.
Two of the three controls in this bench exist because a confident number turned
out to be an artifact.

#### Stage 2 — model-authored surfaces

A model saw **only the canonical form** and authored four alternates
(`bench/bench_surfaces_llm.py`, surfaces in `bench/results/authored_surfaces.json`).
A prediction was recorded before the run (`bench/STAGE2-PREDICTION.md`) and was
**wrong**: predicted 0.52 recall @0.92 at K=5, measured 0.377 against the
generator's probe families.

It was wrong for a reason worth keeping. Per-family recall @0.92:

| family | generator | model-authored |
|--------|----------:|---------------:|
| full | 0.94 | **1.00** |
| short | 0.45 | **0.82** |
| acronym | 1.00 | 0.00 |
| ticker | 0.58 | 0.00 |
| legacy | 0.56 | 0.00 |

The model produced an acronym for **every** meaning — `JRG 0`, `QFL 1`, `PMC 2`
— arguably better than the generator's, which uses place+trade initials only and
jams the tag on unspaced (`JR0`). `sim("JRG 0","JR0") = 0.750`, under threshold,
scores zero. `acronym = 0.00` is a **corpus artifact, not a model failure**.

**Stage 1 and stage 2 need different corpora**, which nothing about `aliased`
reveals until a second author is introduced. The generator authoring both the
sealed surfaces and the probe families makes it self-consistent; the moment
someone else supplies one side, every invented convention becomes an unguessable
barrier and the bench measures convention-matching.

Re-scored with probes from an author independent of both — an agent asked what a
hurried employee would type into a search box, which had seen neither the
generator's families nor the sealing model's output:

| arm | K | rows | recall@0.92 | recall@0.96 |
|-----|--:|-----:|------------:|------------:|
| canonical only | 1 | 300 | 0.117 | 0.023 |
| generator families | 5 | 1500 | 0.430 | 0.293 |
| model-authored | 5 | **1402** | **0.670** | **0.570** |

Model surfaces beat the generator's own families, on fewer rows.

#### Stage 3 — a person authored both sides, on a real corpus

`bench/bench_surfaces_human.py` over `corpus_terpsi`, on `terpsi-music` at
`6ea9b89` — 120 extracted spans, 96 surviving the gate, 14 referents
(`bench/results/surfaces_human.json`). Every surface and every probe is a
**verbatim span of one person's prose**, written across fourteen documents and
twenty-four survey notes (seven extraction agents, three waves) before any of it was going to be
matched against anything. A model only *labelled* which existing phrase points at
which file; `corpus_terpsi.gate` re-reads the source and drops anything that is
not a literal substring — 7 of 120 rejected as NOT VERBATIM, including a span an
agent had helpfully re-capitalised.

The referent is a **file path**, so ground truth owes nothing to string
similarity and the labels cannot be circular with the thing being measured. The
split is by **source document, run in both directions**, and any probe whose
normalized form is already in the sealed set is dropped and counted, so recall
is never measuring lookup.

This corpus reaches the case `aliased` is structurally incapable of expressing.
`aliased` tests **derivation** — manipulate the canonical string. These are
**knowledge**:

```
"the sensitivity ladder"     -> docs/SENSITIVITY.md   sim 0.615
"the eight text-only checks" -> craft/                sim 0.067
```

**The result, and it is not the one stage 2 pointed at.** rank@1 is the
threshold-free measure — how often the correct referent is the argmax.

| cut | split | arm | n | rank@1 | recall @0.80 | @0.92 |
|---|---|---|--:|--:|--:|--:|
| inclusive | A→B | canonical only | 14 | 0.714 | 0.000 | 0.000 |
| inclusive | A→B | **+ human surfaces** | 14 | **0.786** | 0.000 | 0.000 |
| inclusive | A→B | + WRONG surfaces | 14 | 0.500 | 0.000 | 0.000 |
| inclusive | B→A | canonical only | 41 | 0.780 | 0.000 | 0.000 |
| inclusive | B→A | **+ human surfaces** | 41 | **0.805** | **0.585** | 0.000 |
| inclusive | B→A | + WRONG surfaces | 41 | 0.000 | 0.000 | 0.000 |
| strict | A→B | canonical only | 4 | 0.000 | 0.000 | 0.000 |
| strict | A→B | **+ human surfaces** | 4 | **0.250** | 0.000 | 0.000 |
| strict | B→A | canonical only | 12 | 0.250 | 0.000 | 0.000 |
| strict | B→A | **+ human surfaces** | 12 | **0.333** | 0.000 | 0.000 |
| strict | both | + WRONG surfaces | — | 0.000 | 0.000 | 0.000 |

**Recall at every shipped threshold is 0.000, in every arm, in both cuts.** The
highest similarity any probe achieves against any sealed row *anywhere in this
corpus* is 0.878. Nestor's sweep starts at 0.80 and the distribution lives below
it. This is not "surfaces underperformed" — nothing is served at all, with or
without them. The only recall above zero anywhere is 0.585 at 0.80, one arm, one
split, and 0.80 is not an operating point anyone proposed.

**Why two cuts, and why neither is "the" number.** The inclusive cut counts
every probe. The strict cut additionally drops any probe that *contains* a sealed
surface or is contained by one — `§14 of the capability map` against a sealed
`The capability map` is not the matcher bridging two phrasings, the answer is
sitting inside the query. But the same rule also drops `the sensitivity ladder`
against canonical `SENSITIVITY`, which is genuinely what the human calls that
file. Substring inclusion is the *easy half* of real aliasing, not a fake version
of it. So the inclusive cut flatters the mechanism and the strict cut selects for
cases a character matcher structurally cannot do — a benchmark that would report
its own conclusion. Both are printed; the truth is between them, and the arm
ordering is the same in both.

Two narrower rules were tried and rejected on the way, and the failures are kept
in `corpus_terpsi.template_key`: a regex for `§N of the ...` caught
`§8.1 of the architecture` and missed `CLAUDE.md #17` for no reason but which
form was noticed first; and "drop anything containing its own canonical" turned
out to be the strict cut, arrived at by accident and nearly applied by default.

**What surfaces actually buy on real prose is rank, not service.** rank@1 rises
in all four split × cut cells, and the negative control — same referents, same
row count, each referent given *another* referent's surfaces — is worse than
canonical-only in all four, collapsing to 0.000 in three. So the lift is the
surfaces carrying meaning, not more rows in the index buying more chances. But
the correct answer being first at 0.84 does not help a mechanic whose threshold
is 0.92.

**Underpowered on the strict cut, and the direction is not.** n=4 and n=12
there; a 0.250 → 0.333 lift on twelve probes is one probe. What is *not*
fragile: the arm ordering is 4/4 consistent across both cuts and both splits, and
0.000 recall at 0.92 rests on the maximum score over the whole corpus, which no
sample-size argument touches.

**Two harness faults, both found only because the result was implausible.**
`best_match_fast(floor=FLOOR)` censors scores below the lowest threshold, so the
first run reported zeros with no way to distinguish "cannot see it" from
"threshold is above it" — rescored at `floor=0.0`, and rank@1 added. And
`normalize` collapses `CAPABILITY-MAP` to `capabilitymap`, one token where the
probe has two, costing the *baseline* arm +0.0195 mean similarity for punctuation
reasons; the canonical is now de-slugged, which makes the comparison harder for
the hypothesis. An artifact that points the way you want is the one to remove
first.

#### Stage 4 — the matcher was the binding constraint, not the corpus

Three stages varied the surfaces and never varied the tool comparing them. Every
0.000 above is `StringMatcher`, which is character difflib. `bench/token_matchers.py`
adds two token matchers behind the same seam — `TokenJaccard` (|A∩B|/|A∪B|) and
`TokenOverlap` (|A∩B|/min) — and stage 3 reruns unchanged. All matchers answer
**one probe list**, with the lookup drop computed with `StringMatcher` every
time; letting each matcher's own `normalize` decide the drop gave the token runs
17 probes where the string run had 41, two numbers that must never be compared.

| matcher | split | arm | rank@1 | recall @0.92 | LOO false seal @0.92 |
|---|---|---|--:|--:|--:|
| string | B→A (41) | canonical | 0.780 | 0.000 | 0.000 |
| string | B→A | + human | 0.805 | 0.000 | 0.000 |
| jaccard | B→A | canonical | 0.732 | 0.000 | 0.000 |
| jaccard | B→A | + human | 0.756 | 0.049 | 0.000 |
| **overlap** | B→A | canonical | 0.732 | **0.707** | 0.000 |
| **overlap** | B→A | + human | 0.756 | **0.707** | 0.000 |
| overlap | B→A | + WRONG | 0.732 | 0.707 | **0.683** |

**Recall at Nestor's shipped 0.92 goes from 0.000 to 0.707 on identical probes,
by changing the matcher.** Stage 3's "no threshold in the shipped range is
reachable" is a fact about difflib, not about human aliasing. That conclusion
needed one afternoon's work to reach and I should have reached it before running
three benches, not after — *the failure is never in the step you are watching.*

**And most of that win is not the surfaces.** `+ WRONG surfaces` scores the same
0.707 as `canonical only`. Under token containment the canonical row alone does
the serving; surfaces add ~0.02–0.07 of rank@1 and nothing to recall. The one
place they carry it is the strict cut A→B — canonical 0.000, human 0.250, WRONG
0.000 — on n=4.

**The number that decides §3.3.** 17.1% of probes (7/41) share **no token** with
any sealed surface; on the strict cut, 58.3%. That is the lexical floor — no
character, token or n-gram method reaches it at any threshold — and it, not the
whole problem, is what a semantic matcher has to justify itself against.

**Two harness faults, and the second was nearly a published result.**

- `best_match_fast` accepts a `matcher` and ignores it for scoring, pruning with
  difflib's own upper bounds. Its docstring says so outright: *"Only valid for
  StringMatcher … callers must fall back to best_match for any other matcher."*
  I passed token matchers to it and read the output. The tell was that
  `TokenJaccard` and `TokenOverlap` — which share a `normalize` and differ only
  in `similarity` — returned byte-identical numbers in all 24 cells. Discarded
  and rerun through `best_match`. **The warning was written down, in the
  function, and being written down did not help** — the same shape as the README
  that accurately recorded a limitation nobody acted on.
- The false-seal rate was measured on whatever probes happened to have an
  unsealed referent — eleven of them — and reported 0.000 for `TokenOverlap`,
  the matcher most likely to false-seal, which saturates at 1.0 on a single
  shared token and had `p50 = 1.000`. Replaced with leave-one-out: rebuild the
  store without each probe's own referent, so the right answer is absent by
  construction, and score all 41. The legitimate arms hold at 0.000; the WRONG
  arm goes to **0.683**, which is the measure showing what it will do when the
  index does not contain the answer. Fourteen referents with distinct
  vocabularies is a friendly test and 0.000 should not be read as safe at scale.

#### What is established, and what is not

**Established, now across three corpora and four authorship regimes — one
surface per meaning is not enough.** Canonical-only scores 0.056 against
generator probes, 0.117 against independent agent probes, and on human prose it
produces **nothing at any threshold down to 0.55** once the templated family is
removed. Every multi-surface arm beats it in every framing. That is §3.4's
load-bearing claim and it survived the corpus that was supposed to break it.

**Not established — how good model-authored aliases are.** Stage 2's two
framings disagree by ~1.8× (0.377 vs 0.670) and *neither is the answer*: against
the generator the model is punished for not guessing arbitrary conventions,
against another agent it is rewarded for agreeing with itself. Stage 3 does not
settle this, because it measures *human*-authored surfaces. It removes the
question's urgency instead — see below.

**Overturned by stage 3 — that surfaces move the safe threshold into
usefulness.** Stage 1's *"At 0.96 the lift is 11× and it is free"* is a property
of `aliased`, whose intra-meaning dispersion happens to leave sibling surfaces
close enough to clear 0.92. Real human prose does not sit there. The whole
distribution tops out at 0.878, canonical and multi-surface alike, so §1.3's
conclusion — no threshold simultaneously safe and useful — is the correct
description of this corpus and **surfaces do not repair it.** The sentence
should not have been written in a form that implied it would generalize.

**Established by stage 3, and it points somewhere else — surfaces buy rank, not
service.** rank@1 improves in 4/4 cells with the negative control collapsing to
0.024–0.167, while served recall stays flatly zero. That is not a weaker version
of the original claim; it is a different mechanic. Nestor already has a place
where "the right answer, first, at 0.84" is worth something and a served match is
not required: **the review queue.** Ordering a human's queue is the use these
measurements support. Auto-serving is the one they refuse.

**Established — authored surfaces waste slots.** 98 of 300 meanings (33%)
received a variant identical to the canonical after normalization; a third of the
budget bought nothing. Measurable before sealing, so a dedup check at authoring
time recovers it.

#### Still untested

- **Human-authored probes against *model*-authored surfaces.** Stage 3 pairs
  human with human; stage 2 pairs model with model. The cell that resolves the
  0.377/0.670 gap — a person's queries against Claude's aliases — is still empty,
  and it is now one bench run away rather than a research project.
- **Name-shaped human aliasing.** `terpsi-music`'s aliases are *definite
  descriptions* — "the sensitivity ladder", "the eight text-only checks" —
  which is a different linguistic object from `AWS`/`Amazon Web Services`, §3.1's
  motivating case. Descriptions share almost no characters with the canonical, so
  a character-similarity matcher is close to the worst possible tool for them.
  **The 0.000 recall may be a fact about descriptions rather than about human
  aliasing**, and a corpus of human-written *name* variants would separate the
  two. Until then stage 3's negative result is scoped to the case it measured.
- **Whether ranking is enough.** If the mechanic is queue ordering rather than
  serving, the number to measure is not recall at a threshold — it is how far a
  reviewer scrolls. Nothing here measures that.
- **Who pays.** Authoring costs a model call, and if a human seals anyway,
  surfaces are review surface too — five rows to check instead of one. Sharper
  now that the payoff is ranking rather than avoided review.

**Cost if it holds:** a paragraph of prompt at seal time, `entity.py` unchanged,
no new dependency, no vector smuggled through a SQL key. §3.3 becomes optional
rather than blocking — **for the ranking use.** For serving at a safe threshold
on prose-shaped aliases, stage 3 says surfaces are not a substitute for §3.3 and
the two are no longer alternatives to each other.

---

## 4. Positioning

### 4.1 Lead with the mechanic, not translation — **shipped**

*Was: the README opened on a translation demo and reached the general mechanic a
section later, so the first screen said "translation memory" to anyone skimming.*

The mechanic is now the first section: the loop, then the recipe table, then one
line placing translation as the origin story rather than the boundary. The quick
start runs the loop **twice** — once in translation, once as an alias graph with
no translation in it — because "domain-agnostic" is a claim, and two runnable
files are evidence. Both are executed by `tests/test_docs.py` and diffed against
the output printed beneath them, so the second one cannot quietly rot while the
first is the only one anybody runs.

The entity example ends on the line worth arriving at: a near miss comes back
**unsealed with a suggestion**, not as an answer with a lower score. That is the
same three-state answer the translation demo gives, in a domain where nobody
would call it translation memory — which is the whole argument of §4.2 made
without asserting it.

Still open, and deliberately separate: §4.2's positioning line, and §4.3's
recorded demo.

### 4.2 The category is AI verification, not translation memory — **shipped**

Tier 2 is an AI draft explicitly queued for review; tier 3 is a human sealing it;
tier 1 is that seal served forever — all in a tamper-evident chain. That is a
direct answer to "which model outputs did a human actually check," which nobody
has solved and every regulated buyer is being asked.

The economic shape is the strong part: each human verification is **permanent
capital**. Cost per answer falls as trust rises — an unusual curve worth leading
with. Candidate line: *"Verified once. Served forever."*

Where it wins: high-value, low-volume decisions — contracts, clinical notes,
regulatory filings. Where it loses: high-volume chat, per §2 numbers. Don't
pitch into the second; the demo would lose.

**Shipped 2026-08-06** as a README section, *The category — verification, not
translation memory*, placed directly after *The mechanic* and linked from
Contents. It carries the TM-is-a-cache contrast, the permanent-capital curve,
"Verified once, served forever", and both halves of the wins/loses pair with the
losing half pointing at the §2 numbers rather than glossing them.

**One clause from this entry was deliberately not shipped:** *"which nobody has
solved."* It is a claim about every other system in the category, it was not
checked, and there is no way to check it — which makes it precisely the kind of
sentence this repo spent 2026-08-05 learning not to publish. The README makes
the checkable claim instead: that this is a question regulated buyers are being
asked. What Nestor answers is a fact about Nestor; what everyone else has failed
to answer is not.

### 4.3 The 60-second demo — **shipped, except the recording**

Highest-leverage missing artifact. An AI gets something wrong; a human corrects
it **once**; it is right forever after, with a receipt that cannot be forged.
Then tamper with the ledger and watch the chain refuse. That is the entire
product in one loop, and it lands on an engineer and a compliance officer for
different reasons.

No longer blocked on §5.1 — `nestor ui`, `nestor ask` and `nestor serve` all
exist, and two screens carry the loop with no explaining: a near-match returning
`~ draft` because it is under the cutoff, and a forged row scoring **1.000**
returning `! pending`.

`demo/sixty_seconds.py` is the script: eight beats, the exact phrases that
produce each outcome, paced for a recording and `--fast` for CI. What is left is
literally the screen capture.

One beat is worth defending, because it is the one a demo usually leaves out.
Between the near miss and the forgery, the script asks for "sixty days" against
a phrase sealed for "thirty days" — which scores 0.96 and **is served, wrongly**.
Showing it is the point: §4.4's argument is that admitting a measured failure
rate is stronger than claiming accuracy, and a demo that only shows the good
case is exactly what a compliance buyer has learned to distrust. It lands
pointing at `bench/`, `nestor calibrate` and the rejection signals — the three
things that exist to answer it.

Every beat asserts what it narrates and the script exits non-zero if a claim
does not hold, so it cannot rot into a lie between recordings. A test runs it.

### 4.4 The bench is a marketing asset — **shipped**

"We are accurate" is a claim a compliance buyer knows is a lie. "Here is our
measured false-verification rate, here is the dial that sets it, here is the
harness — run it yourself" is stronger *because* it admits a failure rate.
Publishing `bench/results/` is a differentiator, not an exposure.

**Shipped 2026-08-06** as *Why the numbers are published*, a subsection closing
*Accuracy, and how to measure yours* — which is where the argument belongs,
because by that point the reader has just been shown a table where the default
threshold false-seals 16.4% of the time. The section says that was on purpose.

Each of the three things the pitch names is a path in the repository, and the
section says which: the harness is `bench/`, the dial is `SEAL_THRESHOLD` plus
`nestor calibrate`, the numbers are the committed `bench/results/*.json` with
parameters, environment and git revision attached. It also keeps
`"complete": false` in view — a prefix is not an answer, and a marketing number
would not bother to preserve the distinction.

**No landing page, and no new bench code**, which is what the fleet map's
"one landing page **or** README section" left open. The README section was the
cheaper half and it is the one a buyer already reading the repo will reach. The
recording in §4.3 is still the missing asset, and it is still nobody's code
change.

---

## 5. Missing surface

### 5.1 There is no CLI — **shipped**

*Was: no `console_scripts`, no entry point, nothing to run without writing
Python.*

`nestor` (`nestor.cli`): `ask`, `resolve`, `check`, `match`, `export`, `import`,
`ledger verify|entries|head`, `stats`, and delegation to `ui` and `serve`, which
own their own flags rather than having them mirrored and left to drift.

Two decisions worth keeping. **Exit codes carry the answer** — 0 for a verified
one, 1 for an unverified answer, a flagged figure, a broken chain or an import
with conflicts, 2 for usage — so `nestor ledger verify` is a CI gate and `nestor
ask` works in a shell conditional. That is the difference between a CLI and a
pretty-printer. And **`import` is a dry run until `--apply`**, like every other
decision here that changes what gets served as verified.

Sealing is deliberately *not* a subcommand. It would be the one place in the
codebase where a verification could be made by something with no face — a script,
a cron job, a CI runner — and `--verifier "$USER"` is not a human checking
anything. Seals are made in the UI or in code that a person is driving.

### 5.2 The memory is write-only — **shipped**

*Was: `Storage` had no list, unseal, delete or export. A pair could be sealed but
never browsed, inspected, revoked or exported — so for a system whose whole value
is human verification, the human could not see what they had verified.*

`nestor.curator.Curator` is that surface: `list` (filter by status / verifier /
substring, paginated), `get` (full provenance plus every rejection recorded
against the pair), `unverifiable`, `unseal`, `restore`, `export`, `summary`.
Backed by an optional all-or-nothing `Storage` capability
(`supports_curation`), on the same terms as rejection.

Three decisions worth keeping:

* **Every row reports `servable`, not just `status`.** That column runs the same
  `is_verified_seal` predicate the serve path uses, so it answers "would Nestor
  actually serve this?" rather than "does the row say sealed?". `unverifiable()`
  lists the difference — with signing on, those are rows written by something
  that never held the seal key. Nothing else surfaces them.
* **Unseal is not reject.** Unsealing returns a pair to `draft` for
  re-verification; rejecting retires it as wrong. A curator who is merely unsure
  should not have to choose between destroying a mapping and leaving a seal
  standing they no longer trust. Unseal clears `seal_sig` — a `draft` row still
  carrying a valid signature is a seal waiting to be reactivated by anything
  that flips the status column back.
* **Revocation is ledgered** (`unseal`, `restore`). A trail that records every
  grant of trust and no withdrawal of it is not an audit trail.

**Building this found a real bug in §1.2.** `add_pair` resurrected rejected
pairs: a curator rejected a bad mapping and the next `graduate_segment` over the
same source text silently re-sealed it — precisely the leak rejection existed to
close. `add_pair` now raises `RejectedPairError` instead, so a host driving a
review queue can surface it as what it is: one human asserting the opposite of
another's recorded decision. `Curator.restore` is the deliberate way back, and it
returns to `draft` rather than `sealed`, because a mapping someone once called
wrong should be re-verified rather than reinstated.

Still missing: no `memory_delete`. Deliberate for now — rejection and unsealing
preserve the audit trail, and hard deletion would punch a hole in it. A GDPR-style
erasure path would need to be designed against the ledger, not bolted on.

### 5.3 Ledger verification is once per process — **verified; the tail closed**

`cascade._verified_ledgers` caches by path, so the chain is checked on first
append and never again. I watched an append succeed after mid-run tampering. The
cache is a deliberate cost trade, but a long-lived process will not notice
tampering that happens while it runs. Options: periodic re-verification, verify
the tail only, or make the cache TTL'd. Related: `verify()` cost grows linearly
with ledger length, so checkpointing may be needed before re-verification is
affordable.

**The UI makes this sharper, not worse.** `nestor.ui` is the first long-lived
Nestor process in the repo: a REPL session or a batch run exits, a review server
stays up for a shift. It verifies the chain on the first append and then trusts
it for as long as the reviewer keeps working. The Ledger view calls `verify()`
on every render, so the *reading* is live — but nothing refused an append after
the first one, and that was a realistic window rather than a theoretical one.

**The tail half is closed.** Each append now records where its own line landed
and that line's hash; the next one re-reads from there, requires its own last
entry to still be present and unchanged, and requires anything appended since —
by this process or another — to chain onto it. The cost is the bytes written
since the last append, not the file, so this is affordable in a way
re-verification is not. It runs in the preflight as well as under the append
lock, because a refusal that arrives *after* the caller's store write leaves a
sealed row with no trail.

What it does not cover, and the docstring says so: an edit to a line older than
the checkpoint. That still needs the full walk. The checkpoint is the cheap
guard on the part of the chain being written right now, not a replacement for
``verify()`` — a periodic or TTL'd full re-verification is now available via
``NESTOR_LEDGER_VERIFY_INTERVAL_SEC`` and :func:`~nestor.cascade.ledger_verify_interval_sec`.
``0`` keeps the original once-per-process cache (batch jobs). Positive values
re-walk on append/preflight after that many seconds; negative values walk every
time. ``nestor.ui`` defaults to five minutes when the env var is unset, because
it is the long-lived process this gap was written for.

One subtlety worth recording, because it was a flake before it was a fix: the
preflight holds no lock (it cannot — its job is to answer before the caller
commits), so it must not read a line another thread is flushing and call the
chain broken. It checks only the checkpoint line, whose bytes were fsynced
before its offset was recorded; the full tail walk runs again under the lock.

### 5.4 There was nowhere for the human to sit — **shipped**

*Was: every surface was a library surface. The reviewer worked the tier-2 queue
by typing `graduate_segment` into a REPL; the curator browsed the memory through
`Curator`. For a system whose entire claim is that a human checked the answer,
being the human meant writing Python.*

`nestor.ui` — stdlib only (`http.server` plus one inlined page), so the zero
runtime dependencies hold — with five views: **Queue** (the segments the cascade
left for review), **Memory** (the curator's list, provenance and revocation),
**Ask** (run the cascade and see the state that came back, with the ranked
candidates behind it), **Signals** (below), **Ledger** (`verify()`'s verdict
beside the chain).

Decisions worth keeping:

* **Ask is the demo.** Two screens carry the product with no explaining: a
  near-match scoring 0.875 comes back `~ draft` because the cutoff is 0.92, and
  a forged row scoring **1.000** comes back `! pending` — sealed, not servable,
  by mallory. §4.3's 60-second demo is that second screen.
* **The Memory list admits it has a second page.** It stopped at 50 rows with
  nothing to say it had. "No pairs match" and "no more pairs on this page" read
  identically when the page is the only thing you can see, so a curator whose
  memory is larger than one page was looking at an arbitrary slice of it and had
  no way to know. It asks for one row more than it shows, which is how it learns
  there is a next page — the Storage Protocol has no count, and adding one for a
  pager would be the wrong trade.
* **Signals is for the questions no single row answers.** Seals somebody
  overwrote (which the store keeps no trace of at all — only the ledger does,
  and `add_pair` refuses a different verifier's overwrite, so an entry there
  means a human overruled another human), plus §1.2's two rejection aggregates.
  Three findings the package recorded and nothing displayed.
* **An empty verifier is refused, not defaulted.** `memory._same_verifier`
  treats `""` as *unknown* rather than as a person, so a UI that quietly sent it
  would file every decision under an actor who is nobody and turn every
  anonymous re-seal into a conflict. The API asks who is deciding.
* **The library's refusals reach the human verbatim.** A `ConflictingSealError`
  comes back as a 409 carrying its own message — *"pair … was sealed by 'rita'
  as 'Buenas noches.'; 'sam' is now asserting …"* — and the override is a second,
  deliberate click. Declining leaves the memory untouched.
* **No authentication, said out loud.** The verifier is typed, not proven. Hence
  loopback by default, `--allow-remote` to leave it, a custom-header requirement
  so another tab cannot POST a seal in, `default-src 'none'` so the page cannot
  ship the memory anywhere, and `--read-only` for showing without granting.

**All four recipes, not just translation.** The Ask view is a recipe picker —
Translate (the cascade), Entity (alias → canonical), Numeric (figure → baseline,
with tolerance and variation) and Match (the bare seam: any two domain tags,
either shipped matcher, showing the normalized key and every candidate's score).
Each seals from the same screen, into the same memory, through the same ledger.
The Memory view's domain picker lists every tag pair in the store with its size,
so several disjoint graphs in one database are visible rather than assumed.

The UI does **not** infer a recipe from a domain's tags. `("company","company")`
is probably an entity graph and `("en","es")` probably a translation, but nothing
enforces either, and a surface that guessed wrong would mislabel someone's data
with total confidence. The human picks; the UI reports what exists. §4.1's "lead
with the mechanic, not translation" now has a screen that does it.

**Building it found three real bugs.** `graduate_segment` never marked its
segment decided, so a sealed segment stayed `pending` and the queue offered it
forever — the accept-side twin of the attention tax §1.2's rejection work removed
from the reject side; invisible until something rendered the queue.
`SqliteStore`'s shared `:memory:` connection was single-threaded, which no test
caught because nothing had ever served Nestor from more than one thread. And the
third is its own entry — §1.5.

The Queue view lets a reviewer **correct** a draft before sealing it, not only
accept or reject it, because review is usually "nearly" — right apart from one
term. Without that, correcting meant rejecting the segment and sealing the fixed
text somewhere else, and the trail recorded a refusal where a correction
happened. A corrected seal is ledgered with `edited: true` and the digest of the
draft that was *not* sealed, so "a human accepted the machine's answer" and "a
human wrote the answer" stay distinguishable.

Sealing by hand picks its domain from the ones the store actually holds (or
opens a new one), rather than the language pair the process started with — the
last place in the UI that still assumed translation, and the reason to keep
asking "which surface here is quietly single-recipe?"

Memory paginates (``/api/pairs`` with ``offset`` / ``limit+1``; UI pager) and the
Signals tab surfaces ``Curator.replaced_seals`` via ``/api/replaced-seals``.

### 5.5 The newest ledger entry is vouched for by nothing — **shipped (mitigated)**

Every line is verified by the line *after* it, so the last one has nothing
following it: edit it and `verify()` still walks clean. Found while writing a CLI
test that tampered with a one-entry ledger and could not make it fail.

It is a property of hash chains rather than a bug, but it is not marginal: the
newest entry is the one that just recorded who sealed what, so "the most recent
decision is the editable one" is a bad thing to leave unwritten. `ledger.head()`
returns the tip and `verify(expected_head=…)` refuses one that moved
unexpectedly; `nestor ledger head` / `nestor ledger verify --expect-head` put it
in CI. That only helps a caller who kept the value *outside* the file, which is
the honest framing — the fix is not local, it is "someone else remembers."
`nestor.frank` is that taken to its conclusion, mirroring every entry with its
`local_hash` into a ledger somebody else holds.

**The in-process half shipped** (§5.3): every append remembers the line it
wrote and refuses to continue if that line has changed, so while an entry is the
tip, the process that wrote it still knows what it said. That is the closest
thing to a local fix there is — it survives the entry being newest, but not the
process restarting.

Still open: a checkpoint written to a sidecar the ledger's writer does not own,
which is the only version that survives a restart, and which is `nestor.frank`
again in miniature — the fix is not local, it is "someone else remembers."

### 5.6 Nothing could leave — **shipped**

*Was: `Curator.export()` produced a human-readable dump and there was no way back
in. A memory could be read and never moved.*

`nestor.portable`: `export_bundle` (pairs, rejections, signatures, a canonical
`digest`, the source chain for reading), `verify_bundle`, `import_bundle`,
`pairs_csv`. CLI and UI both.

The design question is import, not export. A bundle is a file, and a file saying
`"status": "sealed"` is making exactly the claim a seal signature exists to
distrust — the same claim a forged database row makes, which Nestor already
refuses to serve. So import applies the identical rule: a seal is honored only if
it verifies **here**, and one that does not lands as a `draft` in the review
queue, counted and warned about. Two instances sharing a `NESTOR_SEAL_KEY` move
verified pairs between them and the verification survives, because it was never
in the row to begin with. Two instances that do not share a key move *candidates*
— which is the correct answer, not a degraded one.

Three smaller decisions: conflicts are listed rather than resolved (a bundle
asserting a different target for a source this instance sealed is two humans
disagreeing through a file); the chain does **not** merge, because splicing
another instance's entries in would produce a chain that verifies while
describing events that never happened here, so only the import event is appended;
and the CSV drops signatures on purpose, so nobody mistakes a spreadsheet
round-trip for a way to carry a seal.

### 5.7 A model had no way in — **shipped**

*Was: every surface assumed a human. The obvious deployment — an agent that
consults verified answers before improvising — required writing an integration.*

`nestor serve` speaks MCP over stdio (newline-delimited JSON-RPC, so stdlib only
and the zero-dependency core holds). Seven tools: ask, resolve, check, match,
provenance, ledger_verify, propose.

**The load-bearing decision is what is absent.** There is no sealing tool, no
flag that adds one, and no argument to an existing tool that produces one; a
plausible name gets a refusal that explains why. A model's only write is
`propose`, which queues a candidate as a `draft` exactly where a tier-2 engine's
output lands. This is not caution — it is the whole proposition. "Has a human
checked this?" is worth precisely as much as the difficulty of getting a
machine's output marked as checked, and a server that let a model seal, however
carefully, would be a system where the machine grades its own work.
`tests/test_serve.py` pins it as a property rather than a policy: after a model
calls every tool the server has, the sealed memory is unchanged.

The other half is what comes *back*. Every answer carries the state, the
verifier, the confidence and the candidates with their scores — so an agent can
say "verified by rita", quote a pair id an auditor can look up, or decline
because nothing was sealed. Returning only the text would have made Nestor an
ordinary cache. This is also why `nestor.answer` exists: the browser, the
terminal and the model now share one definition of what Nestor answers, because a
system that tells a model "verified" while showing a curator "draft" has already
lost the argument.

### 5.8 A verifier was a string anybody could type — **shipped**

*Was: everything about trust here was rigorous except the name. A seal was bound
to a key the store does not hold — but ONE key for the whole deployment, so a
valid signature proved the key was present and nothing about who used it.
`verifier="rita"` was a string anyone who could reach the process could type,
and "a human checked this" meant "somebody with access typed a name."*

`nestor.keyring` gives each verifier their own key. A seal's signature verifies
under the key of the verifier it *names*, or not at all — so moving a real
signature onto a more senior name in the database stops working, and a name the
keyring does not know cannot seal, raised from `sign_seal` before `add_pair`
touches the store. The UI's "acting as" box becomes a sign-in: a verifier
presents their key, and the typed name is then ignored entirely, because a field
that must match something already known is only a way to produce confusing
errors.

**Revocation is the part that needed a decision, and the decision was not to
guess.** An HMAC carries no timestamp, so a signature cannot distinguish "sealed
by rita last March" from "forged last night by whoever took rita's key". So the
operator says which happened. A *rotated* key makes no new seals and keeps its
old ones — nobody else ever held it, so they are still that person's
verifications. A *compromised* one makes no new seals and loses its old ones,
which land in `Curator.unverifiable()` for re-verification rather than being
deleted. Picking either automatically is wrong every time: one silently retires
a departed colleague's entire body of work, the other serves a thief's
forgeries as human-verified.

Opt-in throughout, and the shared-key deployment is byte-for-byte unchanged
without it. Migration is `nestor keys add NAME --adopt-shared-key`, after which
pre-keyring seals keep serving and report as `legacy` — verified by somebody
here, not attributable to a person, which is what they always were.

A rejection by an unregistered name is still recorded and honored, and reported
as unsigned; refusing to record a "no" is the one direction rejection must not
fail in, and it is the same asymmetry §1.2 already argues for signatures.

Corrected in place, twice now. First: this used to say the asymmetric upgrade
was still open. It shipped (Ed25519, `[keys]` extra, decision `0074`) — a
keyring holding only a peer's **public** key can verify their seals while
being structurally unable to sign as them, which a shared secret can never
do. What Ed25519 alone left open was that the *signing* instance still holds
every one of its verifiers' private keys, so its operator could still forge
as anyone whose key lives there. The server-side half of closing that shipped
next (decision `0077`, Nestor#17): `memory.add_pair(..., seal_sig=...)`
accepts a signature a client already produced and only verifies it, never
signs it, so a public-only entry can still seal, given a valid signature.

Second: this then said the remaining piece was the browser page itself. It
has shipped too (`nestor/ui_page.py`, decision `0078`, §6.93) — WebCrypto
Ed25519 generated non-extractable in the browser, enrolled by printing the
`nestor keys add ... --public HEX` command for a human to run, and a seal
signed client-side against a message the human has actually seen before
signing it. Nestor#17's four-cell table is now fully closed.

---

## 6. Agent log — moved to [`docs/agent-log.md`](docs/agent-log.md)

The agent log — §6.1 through §6.107 and *The chronology, closed* — outgrew
this file at 6,400+ lines and now lives in its own document:
[`docs/agent-log.md`](docs/agent-log.md). **Every §6.N number is unchanged**,
so `IDEAS §6.40` in the code and prose still resolves; only the file moved.
The Map above indexes every §6 entry with its status and a direct link.

## 7. Standard parts — five hundred components, one method

**Status: open.** There are, on the order of, five hundred component-classes that
run the same way as everything built in the session that opened this section:
**skills**, **hooks**, **rubrics** — and the list goes on (output styles and
personas, statuslines, MCP servers, evals and LLM-as-judge harnesses, prompt and
template libraries, subagent orchestration, permission and sandbox policy,
retrieval). Each is an industry-standard building block, which is the whole
point: the fleet already holds a partial, drifting copy of it, the outside world
holds a mature and often permissively-licensed one, and each yields to **one
repeated method** — survey both ways (what's in the box, what's on the open
internet), re-land the cream **clean-room** under a hard license gate, **prove it
can fail** before trusting it, and record the choice as a **draft** for a human
to seal. Skills and hooks have already been through it this session; the rest are
a backlog.

The method is not ad hoc. It is itself a rubric — a graph of criteria that
constrain each other (§7.3 makes the case, because rubrics is the one entry whose
shape *is* the method's) — which is why a single section can hold parts as
different as a bash guard and a classroom assessment: they are rows scored
against the same rubric. This section is that catalog, one sub-section per part,
the shipped ones first.

### 7.1 Skills — shipped (#83)

The first run of the method. The dev-skills — `verification`, `testing`,
`debugging`, `autonomous-work-boundaries`, `security-review` — were re-landed into
`.claude/skills/` after a two-lens survey (the fleet's willow-mcp skill plugin;
the open-internet `synapse` suite), clean-room in Nestor's own voice so no
vendored pair could drift, with the held set (the `gh` / auto-PR skills) named
rather than dropped. **Status: shipped.**

### 7.2 Hooks — shipped (#87, #88, #105)

The same method, wider. The in-session hook surface — the MCP, write and bash
gates, the self-grant tripwire, the Stop gate, the UserPromptSubmit/PreCompact
re-injection, and the SessionEnd cleanup — was surveyed both ways (willow-mcp's
seven-guard `pre_tool_use` and its `session_stop_hook`; the internet's
cc-safety-net, vibeguard, retro-skill, and the official hooks docs), re-landed
clean-room behind one CLI-agnostic runner, and each gate **proven to deny on the
wire** by `scripts/hook_guard.py`. The self-grant guard shipped named honestly — a
*tripwire, not a boundary* — because a project hook demonstrably cannot enforce
against config edits (anthropics/claude-code#11226).

The newest is **`before_build`** (#105), the sibling of the write gate: where
`before_write` makes an agent consult before *editing*, `before_build` fires on a
build-shaped `UserPromptSubmit` and injects the anti-rediscovery reminder — *check
the box, then the web, before writing* — because this fleet's largest tax is
rebuilding an organ that already existed (`the-house-already-knew.md`). It is
advisory, silent on non-build turns, its one count derived from the tree, and — a
worked instance of its own rule — it was written only after two look-sees
confirmed no such hook existed. Named honestly (a tripwire, so it sits in
`hook_guard`'s non-gates, not its blocking proof). **Status: shipped.**

### 7.3 Rubrics — open (the criterion the brain scored against first)

**Status: open.** A rubric is a set of named criteria, each resolving to a
verdict — `check → status`, `criterion → score`. The operator's claim, worth
testing rather than asserting: the whole decision loop started here. Scoring an
input against fixed criteria to a verdict, and holding that verdict as a *draft
until a human agrees*, is not adjacent to Nestor's seal-and-matcher machinery —
it may be the same machine, met first in a different domain. This section opens
that inquiry the way the dev-skills and the hook suite were opened — survey what
the fleet already has, survey what the outside world has, re-land the cream
clean-room — but first it has to settle whether a rubric is a *domain* the
existing recipe already answers or a shape that needs its own.

**The footprint inside the tree is already load-bearing.** The corpus extractors
treat a rubric as a first-class document shape, not prose: the "standing security
rubric" — one row per check, `# | check | status | notes` — is pulled out
alongside `findings` and `rules` and counted as its own kind (§6.51 onward: the
standing security rubric holds at 15 rows, while other repos surfaced
rubric-shaped draft counts of 35 and then 17 as the corpus widened — a spread
across repos, not one rubric growing). More telling than that it is *parsed*
is that it can be *wrong in a checkable way*: a rubric that contradicted itself
had its diagnosis survive a fresh-context read even where the surface scores did
not (§6, ~§7253/§7275) — two clauses that both applied, resolved the same way
both times. The fleet's embedder stand-in met the same defect from the other side
(decision `0084`): a similarity rubric scored a look-alike-names pair 0.500/0.600
where its own rule said ≤0.35, because a second clause ("same family, different
subject") applied equally — a rubric defect, confirmed by a fresh control, not
agent drift. And the seal covenant is itself rubric-shaped: *has a human checked
this against the criteria* is one row of a rubric; the matcher's bar is a rubric
threshold; a decision is a draft until it is scored and sealed. If that reading
holds, Nestor has been building a rubric engine and calling it a decision store.

**The footprint outside the tree is wide and, unusually, license-clean.** The
assessment-visibility framework — `DispatchesFromReality/education/assessment-visibility-v1.1`,
mirrored into `quiet-corner` and downstream of `terpsi-music` — is rubrics end to
end: classroom-signals vocabularies, expressive-pathway rubrics, the E4 "explain
this to your principal" translation, all CC BY 4.0 with the author named. That is
a large, permissively-licensed corpus of *how humans build and defend rubrics*,
sitting in the operator's own repos and pointed outward. Past it, the open world
has two more bodies: the education-assessment literature (rubric design,
inter-rater reliability — the exact precision/recall-of-a-human-judgment problems
the matcher work keeps rediscovering), and the LLM-as-judge / scoring-rubric
practice now standard in evaluation. Both are the "wide context in the outside
world" the operator flagged; both want the same survey-and-re-land discipline the
skills and hooks got, with the same license gate.

**Open questions, before anything is built.**

1. **Is a rubric a domain, or a new recipe?** A rubric row is `criterion →
   verdict`, sealed — question → commitment with a threshold, which the decision
   recipe may already answer, making a rubric a *view* rather than new machinery.
   But if a rubric's rows constrain each other (the self-contradiction above), it
   is a *graph* of criteria, closer to the decision-edge covenant than to a flat
   key-value. **Status: open.** Settle this first; everything downstream forks on
   it.
2. **Should "a rubric contradicts itself" be a check Nestor runs?** The
   contradiction reproduced across models and across two domains (the security
   rungs, the embedder stand-in). A `conflict_scan` over a rubric's criteria — does
   clause A ever fire where clause B forbids — is the same *search-for-what-refutes*
   Jeles already does for prior art. **Status: hypothesis.**
3. **Is assessment-visibility the first re-land target?** Widest, cleanest-licensed,
   already in-repo — but also the most sensitive (minors' education records govern
   `terpsi-music`), so re-landing its rubric *machinery* must not drag its *data*
   or its domain nouns. **Status: open.**

The one-line thesis to keep or kill: *the brain did not begin as retrieval; it
began as scoring against a rubric, and retrieval was the part that came second.*
Everything above is evidence for testing it, not yet for believing it.

**The method this session ran is itself a rubric — which is the strongest
evidence, and it settles question 1.** Everything built here — the dev-skills,
the four decision gates, the five in-session hooks, the self-grant tripwire, the
session-end cleanup — passed through the *same fixed criteria* before it was
allowed to land, and nobody wrote those criteria down as a rubric; they emerged
as one, which is the tell. Named after the fact, they were: **provenance** (in
the box, in the wide world, or both — the two-lens survey run for every
candidate); **license** (permissive → re-land the text, share-alike or none →
idea-only, clean-room); **hardening** (official / adopted / tested, not a gist);
**applicability** (a specific Nestor gap, not generic good practice);
**already-have-it** (does the house already do this, better — the rediscovery
tax); **falsifiability** (can it be shown to fail — a guard nobody watched fail
is a description); **honest naming** (enforcement or ledger, boundary or
tripwire, guarantee or best-effort); and the **confirmation boundary** (propose
or confirm — everything lands draft, only a human seals).

**Those criteria are not a checklist; they constrain each other, which makes the
rubric a graph.** License gated re-landability no matter how hardened a source
was (Trail of Bits' mutation-testing idea was excellent and CC-BY-SA, so it
landed clean-room with none of its text, decision `0099`). Already-have-it vetoed
candidates no matter their applicability (matcher precision was already measured
four ways in the tree, so the "gap" shrank to one derived rate, `0104`;
constant-time was already `compare_digest`, so the build became a guard to lock
it in, not new code, `0103`). Falsifiability gated trust independent of
everything else — nothing was believed until a test attempted the forbidden act
and the block landed (the mutation guard, the hook-guard on the wire, every
can-fail test). Honest naming overrode ambition (the self-grant guard is a
*tripwire, not a boundary*; session-end is *best-effort, not a guarantee* —
because a project hook demonstrably cannot enforce either). A criterion firing
changed what the others were allowed to conclude. That is a graph of
mutually-constraining criteria, not a flat scorecard.

**Which answers question 1, against the flat reading.** A rubric whose rows
constrain each other is not a *view* the decision key-value already covers; it is
the decision **graph** — the sealed-edge covenant is a rubric's mutual-constraint
structure, and `constraints_on(question)` is already "score this proposal against
the criteria that touch it." So a rubric is not machinery bolted beside the
decision store; it is the decision store *read as what it always was*. **Status:
the graph claim moves from open to verified-by-construction** — this session is
its worked example, more than twenty merged PRs deep. What stays **hypothesis**
is the larger line, that this is where the brain *began*: the session shows the
shape is the same, not the history.

**The recursion the operator named is one shape at three scales.** A model scores
tokens against learned patterns; Nestor scores a proposal against sealed
decisions; this session scored candidates against the re-land rubric. A rubric is
what a pattern-making machine's judgment looks like once the criteria are written
down and a human is made to seal them — Nestor's whole thesis (*has a human
checked this?*) met from the rubric side rather than the retrieval side. The
checkable core, kept separate from the frame so it stays honest: the build
criteria formed a constraint-graph, and that graph is isomorphic to the
decision-edge covenant the store already enforces. The rest — that judgment, all
the way down from the token to the seal, is one recurring rubric — is the frame
this section exists to test, not a claim to bank.

**What it opens.** If a rubric is the decision graph, the rubrics survey is not
"what new thing do we build" but "which sealed-edge structures does the fleet
already have, unrecognized" — and the assessment-visibility corpus stops being an
external dataset and becomes a **library of human-built constraint-graphs**,
rubrics authored and defended by teachers, waiting to be re-landed as decision
graphs with their criteria as edges. That reframes question 3: the first re-land
target is not the corpus's *content* (minors' records — refused) but its
*structure*, the shape of a well-formed rubric. **Status: open**, and the
sharpest single next bite the rubrics entry names.

### 7.4 The list goes on — open (the loop is the catalog)

The five hundred is not a number pulled from the air. Walk the wiring a proposal
actually runs through in Nestor as it stands today, and every seam is a standard
part with two copies — a drifting one in the fleet, a mature and usually
permissively-licensed one in the world — each re-landable by the one method. The
flat backlog (output styles and personas, statuslines, prompt and template
libraries, subagent orchestration) is real but unordered; the *ordered* catalog
is the loop itself, read in the order a proposal is processed:

1. **In — the surface.** A proposal enters through a CLI verb, the `serve` MCP
   seam, or the `ui` front door. Parts: CLI frameworks, the **MCP-server**
   standard (`mcp-builder`), tool/agent interfaces. Box: `cli.py`'s sixteen verbs,
   `serve`, `ui`.
2. **Normalize and match — the matcher seam (§3).** Scored against a domain's
   store by a pluggable matcher. Parts: **embeddings, rerankers, lexical search**
   (sentence-transformers, cross-encoders, BM25). Box: `matcher.py`,
   `semantic_matcher.py` / `ollama_embed.py` (the stub the box can't reach),
   `bench/token_matchers.py`. The part §3 already circles.
3. **Threshold — calibration.** The score meets a bar or abstains. Parts:
   **calibration, conformal prediction, abstention**. Box: `calibrate.py`,
   `SEAL_THRESHOLD`, the matcher-precision gate.
4. **The recipe — a domain.** The match runs inside a recipe keyed by
   `(from, to)`. Parts: **structured extraction, typed output, task templates**.
   Box: `decision.py`, `entity.py`, `answer.py`, `glossary.py`, the numeric
   check — *a domain is its matcher*.
5. **The relations — the graph.** Decisions constrain each other through sealed
   edges. Parts: **knowledge graphs, policy / constraint graphs**. Box:
   `constraints_on`, the decision-edge covenant — where §7.3's rubric-as-graph
   lands.
6. **The store.** Rows persist. Parts: **embedded vector / kv stores** (sqlite-vec,
   LanceDB, DuckDB). Box: `storage.py` / `sqlite_store.py`, WAL, `portable.py`
   bundles.
7. **The seal — a human confirms.** Ratified at the review desk. Parts:
   **human-in-the-loop review, annotation, preference capture** (Label Studio and
   kin). Box: `ui.py` / `ui_page.py`, the covenant, `before_authority` guarding
   the mint.
8. **Provenance — signing.** The seal is a signature. Parts: **signing,
   attestation, supply-chain provenance** (sigstore, in-toto, SLSA). Box:
   `signing.py` (HMAC / ed25519), `keyring.py`, `cloud_seal.py` provisional.
9. **The ledger.** The act is appended, hash-chained, never overwritten. Parts:
   **transparency logs, append-only audit, Merkle logs**. Box: `cascade.py` /
   `ledger.py`.
10. **Measure the loop — the bench.** All of the above is measured, not asserted.
    Parts: **eval harnesses, LLM-as-judge** — which §7.3 argues *is* a rubric. Box:
    `bench/retrieval_quality.py`, `bench_decision_n1.py`, `matcher_precision.py`.
11. **Feed the loop — corpus.** The store is filled from real documents. Parts:
    **document parsing, chunking, ETL, rubric extraction**. Box: `scripts/corpus/`
    — already parsing the rubric shape §7.3 names.
12. **Govern the loop — hooks.** Shipped, §7.2.
13. **Record the loop — dogfood.** Every change is a reviewed file, then a
    deterministic rebuild. Parts: **reproducible builds, provenance-from-source**.
    Box: `scripts/dogfood_store.py`, `docs/dogfood/decisions/`.

Two parts do not sit on the loop but cut across every seam of it, and both are
already load-bearing — which is the tell that they belong on the list, not proof
that they are too mundane for it. **Documentation** is a standard part whose box
copy has teeth: the doc-consistency gate (`tests/test_docs.py`) that failed this
entry's own first push and made these headings carry a status; `IDEAS.md`'s
status vocabulary; the `AGENTS.md` / `CLAUDE.md` / `docs/agent-guide.md` seat; and
the dogfood decision records as documentation-that-is-source. The world has doc
generators, ADRs, docs-as-tests, doc linters. **Templates** is its sibling: the
`.github` PR template filled on every PR here, the dogfood decision JSON shape,
willow-mcp's `CLOSEOUT.template.md` and `handoff.schema.json`; the world has
PR/issue templates, cookiecutter-style scaffolding, ADR templates. The flat
backlog above says "prompt and template libraries" and step 4 says "task
templates", but that undercounts both — documentation-as-a-tested-artifact and
templates-as-scaffolding are parts in their own right, and the doc gate that just
stopped this PR is the least deniable member of the whole catalog.

So the catalog is not a wishlist bolted onto Nestor; it is Nestor **read as a
chain of standard parts**, each with a fleet copy that drifts and a world standard
that does not, each re-landable by the survey-both-ways method. The count stays
the operator's estimate; the *ordering* is derived — it is the order a proposal is
actually processed. And the loop closes on itself: step 10 measures with a rubric,
step 5 stores relations as the graph a rubric is, step 11 feeds on rubrics pulled
from documents — §7.3 is not one entry among thirteen, it is the shape the whole
loop keeps returning to. **Status: open** — thirteen seams named, each a
sub-section waiting for its turn, and the loop is the thing that says how many
there are.

### 7.5 The gaps — open (standard parts the loop doesn't have yet)

§7.4 read the loop for what each seam already holds. This is the honest
complement — the standard parts *absent* from it, verified by a sweep of the tree
(2026-08-12), not guessed. Present, and therefore **not** gaps, so the list keeps
its credibility: `CHANGELOG.md`, `.pre-commit-config.yaml`, the `.github` PR
template, coverage with a floor, the CI matrix, and the local `http.server`
behind `nestor ui`. Absent, each a part the same method would re-land:

- **Type checking.** `scripts/ci-lint.sh` runs `ruff` and `bandit`; there is no
  `mypy` or `pyright`. A typed decision store with no type gate leaves the seam
  between recipes — the place most likely to drift — unguarded. **Status: open**,
  and the cheapest of these to add.
- **Dependency-vulnerability scanning.** `detect-secrets` guards the trust root;
  nothing checks the *dependency set* for known CVEs (`pip-audit`, `osv`). A
  dependency-light repo has the fewest deps to audit and the least excuse not to.
  **Status: open.**
- **Central configuration.** The sixteen `NESTOR_*` env vars the sweep found are
  read ad hoc across `signing`, `keyring`, `frank`, `ollama_embed`, `ledger`,
  `glossary` — no `config.py`, no schema, no validation, no one place that lists
  them. The self-grant pin (`0110`) had to *rediscover* the key-material subset by
  scanning source; a config schema is where that list should live.
  **Status: open**, and the most in-grain.
- **Structured logging / observability.** The loop speaks in `print` and
  `warnings.warn`; no `logging`, no telemetry, no metric. Defensible for a local
  CLI — but the bench and the hooks already emit findings a structured log would
  make queryable. **Status: hypothesis** — worth it only once the loop runs
  unattended (cron, CCR, the fleet).
- **Schema migrations.** `memory_init` creates the schema; a store from before a
  change is handled by ad-hoc "migration" prose (`keyring.py`, `curator.py`), not
  a versioned path (`user_version`, an Alembic-shaped ladder). The portable bundle
  is the current escape hatch. **Status: open** — it bites the day a store on disk
  outlives a schema change.
- **Property-based testing.** The suite is example-based; no `hypothesis`. The
  matcher, the normalizer, and the frozen sign-message encoding are exactly the
  surfaces where a property test (round-trips, invariants under permutation) earns
  its keep. **Status: open.**
- **Contributor onboarding.** A PR template and pre-commit exist; `CONTRIBUTING.md`
  and `.github/ISSUE_TEMPLATE` do not. Low-stakes, high-standard. **Status: open.**
- **Reproducible dev environment.** No `Dockerfile`, no devcontainer; the venv is
  the whole story. **Status: hypothesis** — the CCR session-start bootstrap already
  does most of what a devcontainer would, so the fleet may answer this a different
  way.
- **Onboarding and install — the first five minutes.** Present as raw materials: a
  `nestor` console entry point (`pyproject.toml` `[project.scripts]`), a `nestor
  demo` that seeds a live store for `nestor ui`, and a tested README quick-start.
  Absent is the thing those three gesture at and none delivers — an *actual*
  first-run. No one-line install beyond `pip install -e .` (no `pipx` recipe, no
  `curl | sh`, no Homebrew tap), and no playful, guided onboarding: a `nestor init`
  that walks a newcomer through asking, resolving, and **sealing their first
  decision**, rather than a seeded store they have to already know to open. This is
  the *user's* on-ramp — distinct from the contributor row above, which is the
  developer's. It is also the one gap on this list a user meets before any of the
  others, and the industry standard for it is loud and well-loved (`create-*-app`
  scaffolders, `gh auth login`, the deliberate delight of a good first-run).
  **Status: open** for the install story — concrete, standard, cheap. **Status:
  hypothesis** for *how playful* to make the onboarding: a propose-never-confirm
  governance tool that greets a newcomer with a wizard is a real tonal question —
  the seal is the one moment the tour cannot fake, since only a human may set it —
  so this is built small and tested against the covenant, not assumed.
- **Tooling — the surface exists; its standard parts are half-finished.** Present:
  a `nestor` CLI (sixteen verbs) and a `nestor serve` MCP server (`tools/list` +
  `call`, seven tools), with `--json` on some verbs. Absent are the conventions
  that make a CLI and an MCP server read as *finished*: no `--version`; no shell
  completions (`argcomplete` / `shtab`); `--json` on some verbs but not all, so a
  script cannot rely on machine-readable output. And on the MCP side the server
  exposes **tools only** — no **resources** (the sealed store, the ledger, and the
  decision graph are all natural read-only resources), no **prompts** (the
  propose → resolve → seal flow is a natural one), and no published **manifest** for
  discovery or packaging. The CLI/MCP split is itself the standard-parts method in
  miniature — one core, two surfaces (§5.1, §5.7) — so the gap here is not a missing
  surface but the missing *finish* on the two that exist. **Status: open** for the
  mechanical parts (`--version`, completions, uniform `--json`); **hypothesis** for
  MCP resources/prompts — worth adding only once a consumer needs the store *as a
  resource* rather than through the tool verbs.
- **Cross-session collision awareness — notice another agent is in the room (#111).**
  The sibling of the anti-rediscovery hook (#105): where that one asks *what
  already exists* before you build, this one asks *who else is building right now*.
  Both are reading the room; #105 looks at the past, this at the concurrent
  present. It has a worked instance — two sessions ran this repo at once, both
  minted decision `0118` off the same master, both rebuilt the derived store, and
  the model read the other PR number as an opaque token until the operator pointed
  at it. The signal was structural and present: another open PR on the same base,
  a duplicate decision number in flight (the hazard `0054` names), the same
  derived files rebuilt on a sibling branch. A guard would surface those before a
  number is minted or a PR opened — advisory, best-effort, part seat-reminder
  (*you may not be the only agent*), part concrete scan (open PRs, next-number,
  changed files). The fleet already holds the stance (`safe-app-willow-grove`:
  *another instance may have already designed it*); Nestor has no guard for it.
  **Status: open** — recorded, not built, by the operator's call.

None of these is a crisis: a store that refuses to serve a near-miss does not fall
over for want of `mypy`. But each is a row the catalog was always going to reach,
and naming them verified-absent — with the present ones named too, so the gap-list
cannot be accused of padding — is the same discipline as the rest of §7: what is
missing is derived from the tree, not asserted.

## 8. The speculation — what the industry is building, and what this is

**Status: hypothesis — and labeled so on purpose.** Everything above this line is
held to the tree: a claim is `measured`, `shipped`, or `open` because someone can
run the thing that settles it. This section is deliberately not that. It is the
operator's read of where the field is going and where Nestor sits against it — a
bet, not a finding. Every heading under it carries **hypothesis** because that is
the honest status of a claim about the future, and putting it in its own numbered
section keeps the speculation from leaking upward into the parts that earned their
tags. Read §1–§7 for what is true. Read this for what is being wagered.

### 8.1 What the industry is trying to build — hypothesis

Three races are running at once, and only two of them are loud. The **loud** one
is *agent memory* — persistent state so a model stops forgetting you between
sessions. The frameworks converging on it (Letta out of MemGPT, Mem0, Zep, and the
memory features baking into every agent platform) mostly take the unit of memory
to be a **fact**, an **entity**, or a **summarized conversation**, and the pitch
is continuity: the agent that remembers costs you fewer repetitions. The second
loud race is *long-horizon autonomy* — agents that run unattended for hours on
real coding, research, and ops work, self-correcting against a benchmark; the pitch
there is leverage. The **quiet** third race is *provenance and oversight* — audit
logs, human-in-the-loop approval, model cards, the regulatory pressure to say who
decided what — and it is quiet because it is mostly sold as compliance, a cost
center bolted to the side of the first two. **Status: hypothesis** — this is a read
of the field as of early 2026, not a survey with a denominator; the shape is a
claim, and the claim is that memory-plus-autonomy is where the noise and the money
are, and accountability is the afterthought.

### 8.2 What I'm trying to build — hypothesis

An inversion of the loud race's unit. Nestor's memory is not a store of facts an
agent recalls; it is a store of **decisions** — a question, the commitment made,
the reasons, the doors that commitment closed, and the conditions under which to
reopen them. That choice of unit changes what memory is *for*. The industry builds
memory to make the agent do **more** on its own; the whole architecture here exists
to make sure that when something is decided, a **human** decided it, and the
decision is recoverable later with its reasoning intact — including the roads not
taken. Hence the primitives are not a vector index and a summarizer but a covenant
(*propose, never confirm*; only a human seals in `nestor ui`), an **append-only
ledger**, a **cryptographic witness**, and a matcher tuned to *refuse a near-miss*
rather than to retrieve the closest thing. Local-first and dependency-light is not
a limitation to grow out of; it is the opposite shape to a cloud memory service on
purpose. Memory here is a **brake and a record**, not an accelerator. **Status:
hypothesis** — the covenant and the ledger are shipped and tested (that much is in
§1), but the claim that *this is the right unit of memory* is a wager the tree
cannot settle.

### 8.3 Where the two cross — hypothesis

The bet that makes this more than a contrarian preference: the two loud races
**manufacture** the problem the quiet one is trying to solve, and they are mostly
being built by different people. An agent that remembers more and acts longer makes
"who decided this, why, and what had we already ruled out" the load-bearing
question — exactly when the memory being accumulated is facts and conversations,
which cannot answer it. A fact store can tell you what the agent knew; it cannot
tell you what the agent *chose*, on whose authority, or which alternatives were
foreclosed and are now quietly re-openable. So the speculation is narrow and
falsifiable in principle: decision-memory-with-a-human-seal is the **missing
middle** of the agent-memory race — not another retrieval store, not another eval
harness, but the ledger of *choices* that both of those assume upstream and neither
keeps. If the field goes the way of this bet, the primitives it will reach for are
the ones §7 keeps re-landing — a hook that can be shown to fail, a seal only a human
can set, a closed door that recall surfaces before the work re-proposes it.
**Status: hypothesis, unfalsified because unshipped-at-scale.** Nestor is one local
CLI on one branch; "the field will need this" is the wager, and naming it a wager —
in its own section, under a status tag that says so — is the same refusal to
overclaim that governs everything above it. The difference between this section and
the rest of the file is not confidence. It is that the rest can be run.
