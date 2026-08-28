"""Serving Nestor to a model — MCP over stdio, and one refusal.

A model can ask this server anything Nestor knows. It cannot seal, unseal,
reject, override a conflict, or import a bundle. Those tools are not gated
behind a permission flag or a config option that ships disabled: **they do not
exist in this file**. There is no argument to `nestor_ask` that seals, and no
sequence of calls that ends in a verified pair.

That is the product, not a precaution. Nestor's answer to "has a human checked
this?" is worth exactly as much as the difficulty of getting a machine's output
marked as checked. A server that let a model seal — even carefully, even with a
confirmation string — would be a system where the machine grades its own work,
which is the thing the ledger, the signatures and the three states are all built
to prevent. So the one write a model gets is :func:`~nestor.answer.propose`: put
a candidate in the queue where a human will see it, marked `draft`, exactly
where a tier-2 engine's output lands.

What the model gets back is the *state*, not just a string — ``verified``, the
verifier's name, the confidence, the candidates and what they scored. An agent
holding that can say "verified by rita" and mean it, quote a pair id an auditor
can look up later, or decline to answer because nothing was sealed. Handing back
only the text would make Nestor an ordinary cache.

Run it::

    nestor serve --db data/nestor.db          # MCP over stdio
    python -m nestor.serve --db data/nestor.db

Wire it into a client (Claude Desktop, Claude Code, any MCP host)::

    {"mcpServers": {"nestor": {"command": "nestor",
                               "args": ["serve", "--db", "data/nestor.db"],
                               "env": {"NESTOR_SEAL_KEY": "…"}}}}

Stdlib only: MCP over stdio is newline-delimited JSON-RPC 2.0, which is a
``json.loads`` per line. No SDK, so the zero-dependency core is preserved.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, TextIO

from . import (
    answer,
    cascade,
    config,
    corpus,
    domain,
    engine,
    home_paths,
    keyring,
    memory,
    signing,
    storage,
)
from . import ledger as ledger_mod
from .matcher import Matcher, matcher_audit_fields
from .sqlite_store import SqliteStore
from .storage import Storage

SERVER_NAME = "nestor"
SERVER_VERSION = "0.1.0"
# Versions of the MCP spec this server knows how to speak. A client asking for
# one of these gets it back; anything else is answered with the newest we know,
# which is what the spec prescribes for an unknown version.
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

MAX_MESSAGE = 1 << 20       # 1 MiB — a tool call is never larger than this
MAX_AUTO_CORPUS_EXCERPTS = 4

# What a model may never do here, kept as data so the refusal is greppable and
# so `describe()` can state it to whoever is wiring the server up.
WITHHELD = ("seal", "unseal", "reject", "override a conflicting seal",
            "import a bundle", "edit the ledger")

# The only arguments nestor_propose reads. Anything else on the wire is
# discarded — and a discarded seal-authority field (status=, verifier=,
# verification_kind=, sealed=, seal_sig=) is exactly the covenant boundary a
# model is not allowed to cross. It is not enough to drop those keys silently;
# the reply has to name them, or a caller asking to seal reads an unqualified
# success where it should read a refusal.
PROPOSE_KEYS = frozenset({"source_text", "candidate", "source_lang",
                          "target_lang", "title"})
DRAFT_KEYS = frozenset({"task", "excerpts", "source_lang", "target_lang"})

MAX_CORPUS_SEARCH_LIMIT = 50


def _citation_report(draft: str, contexts: list[dict]) -> dict:
    """Report whether a corpus-backed draft used only supplied short tokens."""
    available = [str(context["citation_token"]) for context in contexts]
    observed = sorted(
        {f"C{number}" for number in re.findall(r"\[C(\d+)\]", draft)},
        key=lambda token: int(token[1:]),
    )
    cited = [token for token in observed if token in available]
    unknown = [token for token in observed if token not in available]
    uncited = [token for token in available if token not in cited]
    required = bool(available)
    return {
        "citations_required": required,
        "citation_compliant": not required or (bool(cited) and not unknown),
        "available_tokens": available,
        "cited_tokens": cited,
        "unknown_tokens": unknown,
        "uncited_tokens": uncited,
    }


def _grounding_note(report: dict) -> str:
    if report["citation_compliant"]:
        return (
            "local model suggestion only — Cursor or Claude must inspect, "
            "apply, and verify it"
        )
    return (
        "local model suggestion lacks a valid supplied corpus citation — do not "
        "apply it as grounded; inspect the basis or redraft"
    )


_NEGATIONS = frozenset({
    "can't", "cannot", "doesn't", "isn't", "neither", "never", "no", "nor",
    "not", "without", "won't",
})


def _negated_terms(text: str) -> set[str]:
    raw = re.findall(r"[\w']+", text.casefold())
    negated: set[str] = set()
    for index, token in enumerate(raw):
        if token in _NEGATIONS:
            negated.update(corpus.meaningful_tokens(" ".join(raw[index + 1:index + 4])))
    return negated


def _split_sentences(text: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(
            r"(?<=[.!?])\s+(?=(?:[-*]\s+|#{1,6}\s+|[A-Z`\[]))",
            text.strip(),
        )
        if part.strip()
    ]


def _draft_sentences(draft: str) -> list[tuple[int, str]]:
    sentences: list[tuple[int, str]] = []
    for paragraph_index, paragraph in enumerate(
        re.split(r"\n\s*\n", draft), start=1
    ):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        sentences.extend(
            (paragraph_index, part) for part in _split_sentences(paragraph)
        )
    return sentences


def _pattern_support_report(draft: str, contexts: list[dict]) -> dict:
    """Sentence-level candidate matches only; overlap is not entailment."""
    rows: list[dict[str, Any]] = []
    unsupported: list[int] = []
    polarity_mismatches: list[int] = []
    for index, (paragraph_index, sentence) in enumerate(
        _draft_sentences(draft), start=1
    ):
        sentence_terms = set(corpus.meaningful_tokens(sentence))
        sentence_negated = _negated_terms(sentence)
        candidates: list[dict[str, Any]] = []
        for context in contexts:
            basis_sentences = (
                _split_sentences(str(context.get("source_text") or ""))
                + _split_sentences(str(context.get("target_text") or ""))
            )
            basis_matches = []
            for basis_sentence in basis_sentences:
                basis_terms = set(corpus.meaningful_tokens(basis_sentence))
                matched_terms = sorted(sentence_terms & basis_terms)
                basis_matches.append((
                    len(matched_terms),
                    len(matched_terms) / max(1, len(basis_terms)),
                    matched_terms,
                    basis_terms,
                    basis_sentence,
                ))
            if not basis_matches:
                continue
            _, _, matched, context_terms, context_sentence = max(
                basis_matches, key=lambda item: (item[0], item[1])
            )
            sentence_coverage = len(matched) / max(1, len(sentence_terms))
            if len(matched) < 2 or sentence_coverage < 0.2:
                continue
            context_negated = _negated_terms(context_sentence)
            if sentence_negated:
                negation_mismatch = not bool(sentence_negated & context_negated)
            else:
                negation_mismatch = bool(context_negated & set(matched))
            candidates.append({
                "token": str(context["citation_token"]),
                "authority": str(context.get("authority") or "none"),
                "matched_terms": matched,
                "sentence_coverage": round(sentence_coverage, 4),
                "negation_mismatch": negation_mismatch,
                "sentence_negated_terms": sorted(sentence_negated),
                "basis_negated_terms": sorted(context_negated),
                "_context_terms": context_terms,
            })
        candidates.sort(
            key=lambda candidate: (
                candidate["negation_mismatch"],
                -len(candidate["matched_terms"]),
                -candidate["sentence_coverage"],
                candidate["token"],
            )
        )
        if not candidates:
            unsupported.append(index)
        elif all(candidate["negation_mismatch"] for candidate in candidates):
            polarity_mismatches.append(index)
        unmatched = sorted(
            sentence_terms - (
                candidates[0]["_context_terms"] if candidates else set()
            )
        )
        for candidate in candidates:
            candidate.pop("_context_terms")
        rows.append({
            "sentence": index,
            "paragraph": paragraph_index,
            "text_excerpt": sentence[:200],
            "unmatched_terms": unmatched,
            "candidates": candidates[:3],
        })
    return {
        "method": "sentence-meaningful-token-overlap",
        "candidate_only": True,
        "sentences": rows,
        "unsupported_sentences": unsupported,
        "negation_mismatch_sentences": polarity_mismatches,
    }


@dataclass
class Server:
    """The tool surface. ``read_only`` removes even the proposal."""

    store: Storage
    source_lang: str = "en"
    target_lang: str = "es"
    #: Whether the operator named a domain at startup, or accepted the built-in
    #: ``en → es``. Same distinction the CLI draws between ``nestor ask``
    #: (parser default ``None`` → store-aware fallback engages) and
    #: ``nestor ask --from en`` (explicit → honoured verbatim); on this server
    #: the operator's startup flag plays the CLI human's role. Decision 0184
    #: is the CLI half; this is the MCP half (issue #203).
    source_lang_explicit: bool = False
    target_lang_explicit: bool = False
    engine_name: str = "offline"
    ollama_model: str = engine.OLLAMA_DRAFT_MODEL
    matcher: Matcher | None = None
    #: The spec ``matcher`` was built from, when it came from ``--matcher``.
    #: Kept because throwing it away costs two things: a caller naming the same
    #: shipped matcher the server is using gets refused (the tool schema offers
    #: exactly those names, so the only value a conforming model can send is the
    #: one that fails), and per-call tolerances stop working, because
    #: ``answer.match`` can only apply them while it still has a *name* to
    #: rebuild from. Both were live defects; see `_resolve_matcher`.
    matcher_spec: str = ""
    read_only: bool = False
    corpus_retriever: corpus.CorpusRetriever | None = None
    client: str = "unknown-client"
    _initialized: bool = field(default=False, repr=False)
    # Cache of the taxonomy nestor_corpus_search checks its ``repository``
    # argument against. Populated on first scoped call; stable for the life
    # of the process, since ``corpus.sync`` runs only at server start
    # (nestor/serve.py::main). If a future refresh path lands, this cache
    # is what would need invalidating.
    _corpus_repositories: tuple[str, ...] | None = field(default=None, repr=False)

    def _draft_sealed_context(
        self, task: str, source_lang: str, target_lang: str,
    ) -> list[dict]:
        """Related verified statements for drafting, never a verdict on the task."""
        matches = memory.lookup(
            task,
            source_lang,
            target_lang,
            limit=50,
            store=self.store,
            matcher=self.domain_matcher(source_lang, target_lang),
            context_threshold=0.0,
        )
        query_terms = set(corpus.meaningful_tokens(task))
        related = []
        for match in memory.verified_sealed(matches):
            pair = match["pair"]
            pair_terms = set(corpus.meaningful_tokens(
                f"{pair.get('source_text', '')} {pair.get('target_text', '')}"
            ))
            overlap = sorted(query_terms & pair_terms)
            if len(overlap) < 2 and float(match["similarity"]) < 0.55:
                continue
            contextual = dict(match)
            contextual["context_matched_terms"] = overlap
            contextual["context_relevance"] = round(
                len(overlap) / max(1, len(query_terms)), 4
            )
            contextual["context_only"] = True
            related.append(contextual)
        related.sort(
            key=lambda match: (
                -len(match["context_matched_terms"]),
                -float(match["similarity"]),
            )
        )
        return related[:3]

    def domain_matcher(self, source_lang: str, target_lang: str) -> Matcher | None:
        """This server's matcher — but only for the domain it describes.

        Same rule as ``ui.App``, and it is here for the same reason: a matcher
        keys one domain, every tool below takes per-call domain tags, and lending
        this one to a call about some other domain is the category error §6.40
        was about. ``None`` defers to the process-wide matcher.

        Same exception too (§6.92 finding 2): tags that agree with this
        server's under case-folding but not exactly — a model sending
        ``Incident`` against a server started ``--source-lang incident`` — are
        a typo, not a different domain, and deferring one of those answers
        `pending` for a phrase that may be sealed, silently. Refused instead.
        Both tags have to match case-insensitively for that; one matching and
        the other genuinely different is a different domain and still defers.
        """
        if self.matcher is None:
            return None
        if source_lang == self.source_lang and target_lang == self.target_lang:
            return self.matcher
        if (source_lang.casefold() == self.source_lang.casefold()
                and target_lang.casefold() == self.target_lang.casefold()):
            raise ValueError(
                f"{source_lang!r}/{target_lang!r} is not a domain this server "
                f"knows — it differs from {self.source_lang!r}/"
                f"{self.target_lang!r} only in case. Did you mean "
                f"{self.source_lang!r}/{self.target_lang!r}?")
        return None

    def _resolve_matcher(self, source_lang: str, target_lang: str, named: str,
                         tolerances: bool = False) -> str | Matcher:
        """What `nestor_match` should score with, or a refusal saying why not.

        Three things have to come out right at once, and the first version got
        two of them wrong:

        * A name that **agrees** with what is in force is honoured. The tool
          schema offers `string | numeric | semantic | ollama`, so on a server started
          with `--matcher numeric` those are the only values a conforming model
          can send — and comparing against the matcher's *class* name refused
          every one of them while accepting `NumericMatcher`, which is advertised
          nowhere. Comparing against the spec fixes it.
        * A shipped name resolves to the **name**, not the object, so
          `answer.match` can still rebuild it with per-call `abs_tol`/`pct_tol`.
          Passing the object made those arguments silently inert: the same call
          on the same store answered `served: True` without `--matcher numeric`
          and `served: False` with it.
        * Tolerances that **cannot** be honoured are refused rather than ignored.
          A custom matcher owns its own notion of nearness; accepting a number
          that changes nothing is the confident-wrong-answer shape this whole
          entry is about.
        """
        own = self.domain_matcher(source_lang, target_lang)
        if own is None:
            return named or "string"

        spec = self.matcher_spec or matcher_audit_fields(own)["matcher"]
        if named and named not in (spec, matcher_audit_fields(own)["matcher"]):
            raise ValueError(
                f"this server keys {source_lang!r}→{target_lang!r} with {spec!r}; "
                f"it cannot score {named!r} as well")
        # A shipped name is re-resolvable, so hand the name over and let
        # `answer.match` apply the tolerances to a freshly built matcher.
        if spec in answer.MATCHERS:
            return spec
        if tolerances:
            raise ValueError(
                f"this server keys {source_lang!r}→{target_lang!r} with {spec!r}, "
                f"which defines its own notion of nearness — abs_tol and pct_tol "
                f"cannot be applied to it")
        return own

    # -- the tools --------------------------------------------------------

    def tools(self) -> list[dict]:
        """MCP tool descriptors. Every write-shaped verb is absent by design."""
        domain = {"source_lang": {"type": "string",
                                  "description": f"source domain tag (default {self.source_lang!r})"},
                  "target_lang": {"type": "string",
                                  "description": f"target domain tag (default {self.target_lang!r})"}}
        out = [
            {
                "name": "nestor_ask",
                "description":
                    "Ask Nestor for a verified answer to a phrase. Returns one of three "
                    "states: 'sealed' (a human verified it — serve it verbatim and cite "
                    "the verifier), 'draft' (a machine produced it — do NOT present it as "
                    "verified), 'pending' (nothing verified matched — say so rather than "
                    "improvising). Also returns the ranked candidates and their scores.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string", "description": "the phrase to look up"},
                                   **domain},
                    "required": ["text"],
                },
            },
            {
                "name": "nestor_resolve",
                "description":
                    "Resolve a surface form (an alias, a spelling, a ticker) to its canonical "
                    "entity using a human-sealed alias graph. Returns the canonical entity only "
                    "when a human verified that mapping; below the threshold it returns an "
                    "unsealed suggestion, which is a candidate for review and not an answer.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"surface": {"type": "string"},
                                   "domain": {"type": "string",
                                              "description": "entity domain, e.g. 'company'"}},
                    "required": ["surface"],
                },
            },
            {
                "name": "nestor_check",
                "description":
                    "Check a figure against the human-sealed baseline for a label. Returns "
                    "within_tolerance / flagged with the exact absolute and proportional "
                    "variation, or baseline=null when no verified baseline exists. Use this "
                    "instead of asserting that two numbers agree.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "description": "e.g. 'ceiling'"},
                        "observed": {"type": "string", "description": "the figure to check"},
                        "domain": {"type": "string"},
                        "abs_tol": {"type": "number"}, "pct_tol": {"type": "number"},
                    },
                    "required": ["label", "observed"],
                },
            },
            {
                "name": "nestor_match",
                "description":
                    "The bare mechanic over any domain: normalize a value, score it against the "
                    "sealed pairs, and report whether it would be served as verified. Omit "
                    "`matcher` to score with whatever keys this domain — this server may have "
                    "been given a matcher of its own, in which case naming a different one is "
                    "refused rather than silently substituted.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}, **domain,
                                   "matcher": {"type": "string", "enum": list(answer.MATCHERS)},
                                   "abs_tol": {"type": "number"}, "pct_tol": {"type": "number"}},
                    "required": ["text"],
                },
            },
            {
                "name": "nestor_provenance",
                "description":
                    "Who verified a pair, when, with what origin, every rejection recorded "
                    "against it, the evidence it points at, and the warrants that say why a "
                    "stranger should believe it. Quote this instead of asserting confidence. "
                    "A warrant is a claim that a warrant exists and how to check it — never a "
                    "report that anyone checked it.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"pair_id": {"type": "string"}},
                    "required": ["pair_id"],
                },
            },
            {
                "name": "nestor_ledger_verify",
                "description":
                    "Verify the hash-chained audit ledger and report the memory's counts. A "
                    "broken chain means the trail has been tampered with; say so plainly.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "nestor_prefs",
                "description":
                    "Read the user's preferences (read-only from MCP). Returns per-user, "
                    "cross-session preferences such as output format and UI theme. "
                    "Writing preferences is CLI-only (nestor prefs set).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string",
                                "description": "dotted preference key, or omit for all"},
                    },
                },
            },
        ]
        if self.corpus_retriever is not None:
            out.extend([
                {
                    "name": "nestor_corpus_map",
                    "description":
                        "Enumerate what the household corpus lane holds: repositories, "
                        "per-repository claim counts, source/target languages, and the "
                        "snapshot sha. Nobody has verified any of it — the corpus is a "
                        "read-only extractor lane, not a seal. Use this to discover the "
                        "'repository' argument nestor_corpus_search accepts.",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "nestor_corpus_search",
                    "description":
                        "Look up unverified corpus excerpts by query, optionally scoped to "
                        "one repository. Returns attributed pointers into corpus stores "
                        "(repository, origin, source_status, matched_terms, "
                        "query_coverage) with authority='none' on every row and no answer "
                        "field, no state, no verdict. A row here is a place to look, not a "
                        "checked answer — never quote it as verified. Feed rows to "
                        "nestor_draft or nestor_propose; do not present them directly.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string",
                                      "description": "phrase or terms to look up"},
                            "repository": {"type": "string",
                                           "description": "one of the names nestor_corpus_map returns; "
                                                          "an unknown name is refused with the whole list"},
                            "limit": {"type": "integer",
                                      "description": f"1..{MAX_CORPUS_SEARCH_LIMIT}; default 8",
                                      "minimum": 1, "maximum": MAX_CORPUS_SEARCH_LIMIT},
                        },
                        "required": ["query"],
                    },
                },
            ])
        if self.engine_name == "ollama":
            out.append({
                "name": "nestor_draft",
                "description":
                    "Ask a loopback-only local model for a bounded analysis or patch "
                    "suggestion using separately labelled human-verified guidance and "
                    "unverified local corpus excerpts. The result is always "
                    "state='draft' and verified=false. It has no filesystem, shell, nested "
                    "tool, sealing, or approval authority; use nestor_propose separately "
                    "if the draft belongs in the human review queue.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string",
                                 "maxLength": engine.MAX_DRAFT_TASK_CHARS},
                        "excerpts": {
                            "type": "array",
                            "maxItems": engine.MAX_DRAFT_EXCERPTS,
                            "items": {"type": "string"},
                            "description": "caller-supplied inert source excerpts",
                        },
                        **domain,
                    },
                    "required": ["task"],
                },
            })
        if not self.read_only:
            out.append({
                "name": "nestor_propose",
                "description":
                    "Queue YOUR answer for a human to review. This is the only write available: "
                    "the candidate lands as a 'draft' in the review queue and is never served as "
                    "verified. You cannot seal it — a human does that, or nobody does.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_text": {"type": "string", "description": "what was asked"},
                        "candidate": {"type": "string", "description": "your proposed answer"},
                        **domain,
                        "title": {"type": "string", "description": "optional queue grouping"},
                    },
                    "required": ["source_text", "candidate"],
                },
            })
        return out

    def _domain_for_read(self, args: dict) -> tuple[str, str]:
        """The domain a read tool should query, mirroring the CLI's rule.

        Priority: the model's own ``source_lang``/``target_lang`` wins when it
        sent one; else the operator's explicit startup flag wins; else the
        store-aware fallback in :func:`nestor.domain.resolve_domain` picks the
        largest domain the store actually holds (or the built-in ``en → es``
        default when the store is empty). Reads only — a write (``propose``)
        must not silently switch domains and stays on the effective default.
        """
        sl_arg = args.get("source_lang")
        tl_arg = args.get("target_lang")
        sl_req: str | None
        if sl_arg is not None:
            sl_req = str(sl_arg)
        else:
            sl_req = self.source_lang if self.source_lang_explicit else None
        tl_req: str | None
        if tl_arg is not None:
            tl_req = str(tl_arg)
        else:
            tl_req = self.target_lang if self.target_lang_explicit else None
        return domain.resolve_domain(self.store, sl_req, tl_req)

    def call(self, name: str, args: dict) -> dict:
        """Run one tool. Unknown or withheld names get a clear refusal."""
        store = self.store
        # The effective default when the model omits domain args and the
        # operator did not pin one at startup — kept for the write path
        # (``nestor_propose``), which must not fall back to a domain the
        # operator did not name. Reads use ``_domain_for_read`` instead.
        sl = str(args.get("source_lang") or self.source_lang)
        tl = str(args.get("target_lang") or self.target_lang)
        if name == "nestor_ask":
            sl, tl = self._domain_for_read(args)
            return answer.ask(store, str(args.get("text", "")), sl, tl,
                              engine_name=self.engine_name,
                              matcher=self.domain_matcher(sl, tl))
        if name == "nestor_resolve":
            # The entity domain is its own tag, so this gets the server's matcher
            # only when the server was pointed at that domain. Without this the
            # same server contradicted itself: nestor_ask honoured the matcher
            # and nestor_resolve did not.
            entity_domain = str(args.get("domain") or "entity")
            return answer.resolve(store, str(args.get("surface", "")), entity_domain,
                                  matcher=self.domain_matcher(entity_domain,
                                                              entity_domain))
        if name == "nestor_check":
            return answer.check(store, str(args.get("label", "")),
                                str(args.get("observed", "")),
                                domain=str(args.get("domain") or "value"),
                                abs_tol=float(args.get("abs_tol") or 0.0),
                                pct_tol=float(args.get("pct_tol") or 0.05))
        if name == "nestor_match":
            sl, tl = self._domain_for_read(args)
            chosen = self._resolve_matcher(sl, tl, str(args.get("matcher") or ""),
                                           tolerances=("abs_tol" in args
                                                       or "pct_tol" in args))
            return answer.match(store, str(args.get("text", "")), sl, tl,
                                matcher=chosen,
                                abs_tol=float(args.get("abs_tol") or 0.0),
                                pct_tol=float(args.get("pct_tol") or 0.05),
                                # A match is a read. The semantic matcher would
                                # like to cache its vectors, and --read-only did
                                # not agree to that. Honoured only on the name
                                # path — an injected matcher was constructed by
                                # the operator, who chose its persistence when
                                # they built it (and `serve.main` builds one with
                                # persist=False under --read-only for exactly
                                # this reason).
                                persist=not self.read_only)
        if name == "nestor_provenance":
            found = answer.provenance(store, str(args.get("pair_id", "")))
            if found is None:
                raise ValueError("no such pair")
            return found
        if name == "nestor_ledger_verify":
            ok, detail = ledger_mod.verify()
            return {"intact": ok, "detail": detail, "path": str(cascade._ledger_path()),
                    "signing_enabled": signing.signing_enabled(),
                    "memory": memory.stats(store=store)}
        if name == "nestor_prefs":
            from . import preferences
            key = str(args.get("key") or "")
            if key:
                return {"key": key, "value": preferences.get(key)}
            return {"preferences": preferences.load()}
        if name == "nestor_corpus_map":
            if self.corpus_retriever is None:
                raise PermissionError(
                    "nestor_corpus_map requires --corpus-dir; this server has no "
                    "consolidated corpus attached")
            mapping = self.corpus_retriever.repositories()
            return {
                "snapshot_sha256": mapping.snapshot_sha256,
                "consolidated_at": mapping.consolidated_at,
                "sources_total": mapping.sources_total,
                "claims_total": mapping.claims_total,
                "authority": "none",
                "repositories": [asdict(repository)
                                 for repository in mapping.repositories],
            }
        if name == "nestor_corpus_search":
            if self.corpus_retriever is None:
                raise PermissionError(
                    "nestor_corpus_search requires --corpus-dir; this server has no "
                    "consolidated corpus attached")
            query = str(args.get("query", "")).strip()
            if not query:
                raise ValueError("query must not be empty")
            # A limit that is not an integer is a refusal, not an int()
            # cast: bare int("abc") raises an unnamed ValueError out of the
            # tool call, and int(3.7) truncates silently to 3. Both were
            # bypasses of the same named refusal the bounds check uses.
            # ``bool`` is a subclass of ``int``, so exclude it explicitly.
            limit_raw = args.get("limit")
            if limit_raw is None:
                limit = 8
            elif isinstance(limit_raw, bool) or not isinstance(limit_raw, int):
                raise ValueError(
                    f"limit must be an integer 1..{MAX_CORPUS_SEARCH_LIMIT}")
            else:
                limit = limit_raw
            if limit < 1 or limit > MAX_CORPUS_SEARCH_LIMIT:
                raise ValueError(
                    f"limit must be 1..{MAX_CORPUS_SEARCH_LIMIT}")
            # Presence, not truthiness — a whitespace-only value like "   "
            # is truthy pre-strip and blank post-strip. The earlier version
            # gated on the raw truthiness ("if repository_raw:") and then
            # skipped the taxonomy check on the stripped blank, silently
            # returning unscoped results while the caller thought they had
            # scoped. Gate on presence, treat blank-after-strip as unknown.
            repository = ""
            if args.get("repository") is not None:
                repository = str(args["repository"]).strip()
                # Taxonomy refusal at the edge — same posture WARRANT_KINDS
                # uses in nestor/warrant.py. A typo becomes a refusal that
                # names the whole list, not silent zero results.
                if self._corpus_repositories is None:
                    mapping = self.corpus_retriever.repositories()
                    self._corpus_repositories = tuple(
                        repo.repository for repo in mapping.repositories)
                known = self._corpus_repositories
                if repository not in known:
                    raise ValueError(
                        f"unknown repository {repository!r}; "
                        f"nestor_corpus_map lists: {', '.join(known) or '(none)'}")
            # Widen the shortlist relative to the requested ``limit`` so a
            # ceiling of 50 is achievable on unscoped searches. The default
            # shortlist of 50 in CorpusRetriever.search caps unscoped
            # selection at (per-repo cap * repository count) minus dedup
            # collisions — for the household's 24 repositories that is 48
            # before dedup, so a limit=50 request could never return 50
            # rows. Scoped searches disable the per-repo cap and don't
            # need the widening, but the extra candidates are cheap.
            search_result = self.corpus_retriever.search(
                query, limit=limit,
                shortlist=max(50, limit * 4),
                repository=repository or None)
            return {
                "mode": search_result.mode,
                "query_sha256": search_result.query_sha256,
                "snapshot_sha256": search_result.snapshot_sha256,
                "candidate_count": search_result.candidate_count,
                "eligible_count": search_result.eligible_count,
                "selected_count": len(search_result.claims),
                "repository": repository or None,
                "semantic_error": search_result.semantic_error,
                "claims": [
                    {**asdict(claim), "authority": "none"}
                    for claim in search_result.claims
                ],
            }
        if name == "nestor_draft":
            if self.engine_name != "ollama":
                raise PermissionError(
                    "nestor_draft requires --engine ollama; no local model was "
                    "explicitly selected and there is no cloud fallback")
            raw_excerpts = args.get("excerpts") or []
            if not isinstance(raw_excerpts, list) or not all(
                    isinstance(value, str) for value in raw_excerpts):
                raise ValueError("excerpts must be an array of strings")
            sl, tl = self._domain_for_read(args)
            task = str(args.get("task", ""))
            if not task.strip() or len(task) > engine.MAX_DRAFT_TASK_CHARS:
                raise ValueError(
                    f"task must contain 1..{engine.MAX_DRAFT_TASK_CHARS} characters"
                )
            if len(raw_excerpts) > engine.MAX_DRAFT_EXCERPTS:
                raise ValueError(
                    f"context accepts at most {engine.MAX_DRAFT_EXCERPTS} excerpts"
                )
            if sum(len(value) for value in raw_excerpts) > engine.MAX_DRAFT_CONTEXT_CHARS:
                raise ValueError(
                    f"context exceeds {engine.MAX_DRAFT_CONTEXT_CHARS} characters"
                )
            nearby = self._draft_sealed_context(task, sl, tl)
            retrieval = (
                self.corpus_retriever.search(
                    task,
                    limit=min(
                        MAX_AUTO_CORPUS_EXCERPTS,
                        max(0, engine.MAX_DRAFT_EXCERPTS - len(raw_excerpts)),
                    ),
                )
                if self.corpus_retriever is not None
                else None
            )
            corpus_claims = list(retrieval.claims) if retrieval else []
            corpus_context = []
            for index, claim in enumerate(corpus_claims, start=1):
                context = asdict(claim)
                context["citation_token"] = f"C{index}"
                corpus_context.append(context)
            sealed_basis = [
                {
                    "pair_id": str(match["pair"].get("id") or ""),
                    "source_text": str(match["pair"].get("source_text") or ""),
                    "target_text": str(match["pair"].get("target_text") or ""),
                    "verifier": str(match["pair"].get("verifier") or ""),
                    "similarity": float(match["similarity"]),
                    "context_matched_terms": match["context_matched_terms"],
                    "context_relevance": match["context_relevance"],
                    "context_only": True,
                    "citation_token": f"S{index}",
                    "authority": "human-sealed-statement",
                }
                for index, match in enumerate(nearby, start=1)
            ]
            local = engine.OllamaEngine(model=self.ollama_model)
            draft = local.draft_task(
                task,
                excerpts=raw_excerpts,
                sealed_context=nearby,
                corpus_context=corpus_context,
            )
            grounding = _citation_report(draft.text, corpus_context)
            pattern_support = _pattern_support_report(
                draft.text, [*sealed_basis, *corpus_context]
            )
            ignored = sorted(key for key in args if key not in DRAFT_KEYS)
            result = {
                "state": "draft",
                "verified": False,
                "draft": draft.text,
                "engine": draft.engine,
                "provenance": asdict(draft.provenance),
                "basis": {
                    "sealed_guidance": sealed_basis,
                    "unverified_corpus_excerpts": corpus_context,
                },
                "retrieval": (
                    {
                        "mode": retrieval.mode,
                        "query_sha256": retrieval.query_sha256,
                        "snapshot_sha256": retrieval.snapshot_sha256,
                        "candidate_count": retrieval.candidate_count,
                        "eligible_count": retrieval.eligible_count,
                        "selected_count": len(retrieval.claims),
                        "semantic_error": retrieval.semantic_error,
                    }
                    if retrieval is not None
                    else {
                        "mode": "disabled",
                        "candidate_count": 0,
                        "selected_count": 0,
                    }
                ),
                "grounding": grounding,
                "pattern_support": pattern_support,
                "note": _grounding_note(grounding),
            }
            if ignored:
                result["ignored_fields"] = ignored
                refused = [key for key in ignored if key in answer.SEAL_AUTHORITY]
                if refused:
                    result["seal_authority_refused"] = refused
            return result
        if name == "nestor_propose":
            if self.read_only:
                raise PermissionError("this server is running --read-only; even a "
                                      "proposal is refused.")
            ignored = sorted(k for k in args if k not in PROPOSE_KEYS)
            return answer.propose(store, str(args.get("source_text", "")),
                                  str(args.get("candidate", "")), sl, tl,
                                  title=str(args.get("title") or ""),
                                  origin=f"mcp:{self.client}",
                                  ignored=ignored)
        if name.startswith("nestor_"):
            raise PermissionError(
                f"{name!r} is not available to a model. This server deliberately "
                f"withholds: {', '.join(WITHHELD)}. Verification is a human act — "
                f"use nestor_propose to put an answer in front of one.")
        raise ValueError(f"unknown tool {name!r}")

    # -- JSON-RPC ---------------------------------------------------------

    def handle(self, request: Any) -> dict | None:
        """One JSON-RPC message in, one response out (``None`` for notifications)."""
        if not isinstance(request, dict):
            return _error(None, -32600, "invalid request: not an object")
        rid = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        is_notification = "id" not in request

        try:
            if method == "initialize":
                want = str(params.get("protocolVersion") or "")
                info = params.get("clientInfo") or {}
                self.client = str(info.get("name") or self.client)
                self._initialized = True
                return _result(rid, {
                    "protocolVersion": want if want in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "instructions": describe(self),
                })
            if method in ("notifications/initialized", "notifications/cancelled"):
                return None
            if method == "ping":
                return _result(rid, {})
            if method == "tools/list":
                return _result(rid, {"tools": self.tools()})
            if method == "tools/call":
                name = str(params.get("name", ""))
                args = params.get("arguments") or {}
                if not isinstance(args, dict):
                    return _error(rid, -32602, "arguments must be an object")
                try:
                    payload = self.call(name, args)
                except (ValueError, PermissionError, RuntimeError) as exc:
                    # A refusal is a tool result, not a protocol error: the model
                    # needs to read it and change what it does, and a JSON-RPC
                    # error is not shown to it in most clients.
                    return _result(rid, {"content": [{"type": "text",
                                                      "text": f"{type(exc).__name__}: {exc}"}],
                                         "isError": True})
                return _result(rid, {"content": [{"type": "text",
                                                  "text": json.dumps(payload, indent=2,
                                                                     ensure_ascii=False,
                                                                     default=str)}]})
            if is_notification:
                return None
            return _error(rid, -32601, f"method not found: {method}")
        except Exception as exc:                    # noqa: BLE001 — never kill the loop
            if is_notification:
                return None
            return _error(rid, -32603, f"{type(exc).__name__}: {exc}")

    def run(self, stdin: TextIO, stdout: TextIO) -> None:
        """Read newline-delimited JSON-RPC from ``stdin`` until EOF."""
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            if len(line) > MAX_MESSAGE:
                # The browser surface caps its bodies; this one is spoken to by
                # a model, which is the caller most likely to send something
                # enormous by accident.
                _write(stdout, _error(None, -32600,
                                      f"message too large ({len(line)} bytes; "
                                      f"limit {MAX_MESSAGE})"))
                continue
            try:
                request = json.loads(line)
            except ValueError as exc:
                _write(stdout, _error(None, -32700, f"parse error: {exc}"))
                continue
            for req in (request if isinstance(request, list) else [request]):
                response = self.handle(req)
                if response is not None:
                    _write(stdout, response)


def describe(server: Server) -> str:
    """The instructions a client shows its model. Says what is withheld, and why."""
    # A named absence is a refusal; a silent absence looks like "no such path".
    # The consumer session that motivated this (2026-08-28) never reached for
    # nestor_provenance or nestor_match though they were present, and never
    # learned that nestor_propose was absent because --read-only was set — the
    # withholding was invisible. Listing both what is here and what is
    # withheld with a named reason is the cheapest fix that scales.
    present = [tool["name"] for tool in server.tools()]
    withheld: list[str] = []
    if server.read_only:
        withheld.append("nestor_propose (--read-only)")
    if server.engine_name != "ollama":
        withheld.append("nestor_draft (engine is not ollama)")
    if server.corpus_retriever is None:
        withheld.append("nestor_corpus_map, nestor_corpus_search (no --corpus-dir)")
    return (
        "Nestor answers one question about an answer: has a human checked it?\n"
        "Every result carries a state — 'sealed' (verified by a named human; serve it "
        "verbatim and cite them), 'draft' (machine-produced; never present it as "
        "verified), 'pending' (nothing verified matched; say so rather than "
        "improvising). Prefer a sealed answer over your own; when nothing is sealed, "
        "say what is missing and offer nestor_propose so a human can verify it.\n"
        f"This server cannot {', '.join(WITHHELD)}. Verification is a human act, and "
        "a model marking its own output as verified would empty the word.\n"
        f"Tools available: {', '.join(present)}."
        + (f" Withheld here: {'; '.join(withheld)}." if withheld else "")
        + "\n"
        "Reach for nestor_provenance when a caller asks who verified a pair or "
        "why they should believe it. Reach for nestor_match to test whether a "
        "phrase or number would be served, without asking. Corpus verbs (when "
        "available) return unverified pointers — a place to look, not an "
        "answer; never quote a corpus row as verified.\n"
        # Named here because nothing else tells a model what keys this domain,
        # and nestor_match's `matcher` argument is otherwise a guess. The browser
        # surface publishes the same fact via /api/state; this is serve's
        # equivalent, and without it a refusal is unrecoverable rather than
        # informative.
        f"This server keys {server.source_lang!r}→{server.target_lang!r} with "
        f"{matcher_audit_fields(memory.get_matcher(server.matcher))['matcher']!r}"
        + (" (its own)." if server.matcher is not None else " (the default).")
    )


def _result(rid: Any, payload: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": payload}


def _error(rid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _write(stdout: TextIO, message: dict) -> None:
    stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nestor serve",
        description="Serve Nestor's verified memory to a model over MCP (stdio). "
                    "The model can ask and propose; it cannot seal.")
    # $NESTOR_DB / $NESTOR_HOME win over the cwd default — one resolver shared
    # by cli, serve and ui (home_paths.cli_db_default). `serve` is the surface an
    # MCP client launches, so an unpinned default here means every project
    # serves a different, usually empty corpus while its config looks correct.
    p.add_argument("--db", default=home_paths.cli_db_default(),
                   help=("SQLite database (default: $NESTOR_DB, else "
                         "$NESTOR_HOME/keep/nestor.db, else data/nestor.db)"))
    p.add_argument("--ledger", default="", help="ledger path (default: NESTOR_LEDGER or alongside --db)")
    # Defaults are ``None`` so we can distinguish "the operator named a domain"
    # from "the operator accepted the built-in default". A read against a store
    # that holds nothing in the built-in domain then falls back to the store's
    # largest domain, same as ``nestor ask`` with no ``--from``/``--to``.
    # See :meth:`Server._domain_for_read` and :func:`nestor.domain.resolve_domain`.
    p.add_argument("--source-lang", default=None, help="default source domain tag "
                                                       "(default: en, or the store's "
                                                       "largest domain if en→es holds nothing)")
    p.add_argument("--target-lang", default=None, help="default target domain tag "
                                                       "(default: es, or the store's "
                                                       "largest domain if en→es holds nothing)")
    p.add_argument("--engine", default="offline",
                   choices=("offline", "auto", "claude", "ollama"),
                   help="draft engine for nestor_ask (default: offline)")
    p.add_argument("--ollama-model", default=engine.OLLAMA_DRAFT_MODEL,
                   help=("local model tag used by --engine ollama and nestor_draft "
                         f"(default: {engine.OLLAMA_DRAFT_MODEL})"))
    p.add_argument(
        "--corpus-dir",
        default=config.load().get_str("corpus_dir", ""),
        help=(
            "operator-selected directory of extracted .db stores; when set, "
            "they are consolidated as unverified context before serving "
            "(default: NESTOR_CORPUS_DIR)"
        ),
    )
    p.add_argument(
        "--no-corpus-sync",
        action="store_true",
        help="use the last consolidated corpus snapshot without refreshing sources",
    )
    p.add_argument(
        "--corpus-semantic",
        action="store_true",
        help=(
            "rerank only the bounded FTS shortlist with local Ollama embeddings; "
            "lexical retrieval remains the explicit fallback"
        ),
    )
    p.add_argument("--matcher", default="string",
                   help="the matcher that keys this domain: a shipped name "
                        f"({', '.join(answer.MATCHERS)}) or a custom one as "
                        "'module:attribute'. A model asking about a domain keyed "
                        "by a matcher this server was not given is told 'pending' "
                        "for phrases a human has sealed")
    p.add_argument("--read-only", action="store_true",
                   help="withhold nestor_propose too — pure lookup")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ledger:
        cascade.set_ledger_path(args.ledger)
    else:
        # The chain follows the corpus. Without this, a pinned store ran against
        # whatever cascade's default was, and `stats` reported "no ledger yet"
        # against an intact chain.
        cascade.set_ledger_path(home_paths.ledger_for(args.db))
    # Before the protocol stream opens: a KeyringError raised mid-session would
    # surface to the model as a broken tool call rather than as a configuration
    # problem somebody can fix.
    try:
        keyring.preflight()
    except keyring.KeyringError as exc:
        print(f"refusing to start: {exc}", file=sys.stderr)
        return 2
    # Resolved before the store is opened and before the stream does: a matcher
    # that cannot be loaded is a configuration problem, and a traceback out of
    # main() on a stdio server is a broken pipe to whatever launched it.
    #
    # `redirect_stdout` because this line runs somebody else's module. stdout is
    # the JSON-RPC channel and the handshake has not happened yet, so an ordinary
    # `print()` in a user's matcher module would land in front of it and most
    # hosts drop the connection on a non-JSON line. This is a hazard the
    # --matcher spec introduces — before it, no third-party code ran here — so
    # the containment belongs at the point that introduced it. stderr is where
    # this file already says human-facing output goes.
    try:
        with contextlib.redirect_stdout(sys.stderr):
            chosen_matcher = answer.load_matcher(args.matcher,
                                                 persist=not args.read_only)
    except ValueError as exc:
        print(f"refusing to start: {exc}", file=sys.stderr)
        return 2
    store = SqliteStore(args.db)
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    corpus_retriever = None
    if args.corpus_dir:
        try:
            if not args.no_corpus_sync:
                corpus.sync(args.corpus_dir, args.db)
            corpus_retriever = corpus.CorpusRetriever(
                args.db, semantic=args.corpus_semantic
            )
            corpus_retriever.count()
        except corpus.CorpusError as exc:
            print(f"refusing to start: corpus sync failed: {exc}", file=sys.stderr)
            return 2
    server = Server(store=store,
                    source_lang=args.source_lang or domain.DEFAULT_SOURCE_LANG,
                    target_lang=args.target_lang or domain.DEFAULT_TARGET_LANG,
                    source_lang_explicit=args.source_lang is not None,
                    target_lang_explicit=args.target_lang is not None,
                    engine_name=args.engine,
                    ollama_model=args.ollama_model,
                    matcher=chosen_matcher, matcher_spec=args.matcher,
                    read_only=args.read_only,
                    corpus_retriever=corpus_retriever)
    # stdout is the protocol channel; anything human-facing goes to stderr or it
    # corrupts the stream.
    print(f"nestor MCP server on stdio — db={args.db} "
          f"ledger={cascade._ledger_path()} "
          f"matcher={matcher_audit_fields(memory.get_matcher(chosen_matcher))['matcher']} "
          f"{'read-only' if args.read_only else 'ask + propose'}", file=sys.stderr)
    server.run(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(main())
