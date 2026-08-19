"""The storage seam — Nestor's dependency inversion boundary.

Nestor owns translation logic (the cascade, fuzzy matching, the ledger) but
owns no persistence. Every database touch goes through the ``Storage``
Protocol below, and a concrete implementation is *injected* by the host.

Two ways to supply a store:

  * Globally, once at startup::

        from nestor import storage
        storage.set_store(MyStore())

    After that every public entry point (``translate_text``,
    ``translate_segment``, ``graduate_segment``, and the ``memory`` lookups)
    finds it via ``get_store()``.

  * Per call, explicitly: pass ``store=...`` to any public entry function.
    An explicit argument always wins over the global.

The reference implementation is :mod:`nestor.sqlite_store`.

Beyond the core Protocol there are **ten optional capabilities**, each
all-or-nothing and each reported by a predicate, so a store predating one keeps
working and the surfaces that need it say so rather than showing an empty list.
Seven live here; the last three are declared beside the recipes that use them
(``supports_edges`` and ``supports_evidence`` below, ``supports_embedding_store``
in :mod:`nestor.embedding_store`) — if you add an eleventh, add a row here:

==================  =====================================  =====================================
Capability          Predicate                              Without it
==================  =====================================  =====================================
Rejection           :func:`supports_rejection`             ``reject_*`` raises rather than
                                                           dropping a human's "no"
Curation            :func:`supports_curation`              no ``Curator``, no export or
                                                           import
Review queue        :func:`supports_queue`                 the queue cannot be listed or
                                                           cleared
Rejection listing   :func:`supports_rejection_listing`     export says which rejections a
                                                           bundle ships without
Lineage             :func:`supports_lineage`               ``supersede_pair`` / ``revise_draft``
                                                           raise rather than overwriting
Atomic supersede    :func:`supports_atomic_supersede`      ``revise_draft`` refuses rather
                                                           than racing
Decision edges      :func:`supports_edges`                 decisions still seal, but cannot be
                                                           related — no graph neighbours
Evidence            :func:`supports_evidence`              a sealed claim cannot carry what it
                                                           rests on, and the report is empty
Verifier policy     :func:`supports_verifier_policy`       every verifier name is accepted at
                                                           seal time, for every domain
Embedding store     :func:`nestor.embedding_store.supports_embedding_store`
                                                           the semantic matcher recomputes each
                                                           vector rather than caching it
==================  =====================================  =====================================

Partial implementation counts as none. Writing rejections nobody can read back,
or offering an unseal the store cannot perform, is worse than not having the
feature at all.

One requirement of the *core* Protocol is easy to miss and is not optional:
:meth:`Storage.memory_insert` must refuse a duplicate ``(source_norm,
source_lang, target_lang)`` **among live rows** (rows a lineage-capable store
has marked superseded are history, not competitors for the key). Nestor's
conflict guards read-then-write, so that uniqueness is what makes "one row per
source" hold when two reviewers seal the same phrase at the same moment.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class Storage(Protocol):
    """The exact set of persistence operations Nestor requires.

    Derived from real usage in ``cascade.py`` (documents + segments) and
    ``memory.py`` (the translation-memory table). Row dicts are plain
    ``dict[str, Any]``; the keys named in each contract below are the only
    ones Nestor reads.
    """

    # --- lifecycle -------------------------------------------------------

    def init_db(self) -> None:
        """Ensure the document/segment schema exists. Idempotent.

        Called once at the start of ``translate_text``.
        """

    # --- documents -------------------------------------------------------

    def create_document(self, title: str, source_lang: str,
                        target_lang: str) -> dict:
        """Create a document row and return it.

        The returned dict MUST contain ``"id"`` (a stable unique string).
        ``source_lang`` / ``target_lang`` are stored so ``get_document`` can
        return them later (``graduate_segment`` reads them).
        """

    def get_document(self, document_id: str) -> Optional[dict]:
        """Return the document row, or ``None`` if absent.

        When present, the dict MUST expose ``"source_lang"`` and
        ``"target_lang"`` (read by ``graduate_segment``).
        """

    def update_document_status(self, document_id: str, status: str) -> None:
        """Set a document's ``status`` column. No-op if the id is unknown."""

    # --- segments --------------------------------------------------------

    def create_segment(self, document_id: str, position: int,
                       source_text: str, candidate: str,
                       jeles_score: float) -> dict:
        """Create a segment row queued for tier-3 review and return it.

        The returned dict MUST contain ``"id"``. The new segment's state is
        the store's own "pending" default — Nestor does not set it here.
        """

    def get_segment(self, segment_id: str) -> Optional[dict]:
        """Return the segment row, or ``None`` if absent.

        When present the dict MUST expose ``"candidate"``, ``"source_text"``
        and ``"document_id"`` (all read by ``graduate_segment``). A store that
        graduates segments should also update/read a ``"status"`` field, but
        Nestor's graduate path only requires the three keys above.
        """

    # --- translation memory (tier 1) ------------------------------------
    #
    # memory.py previously ran these as raw ``db.get_db()`` SQL. They are
    # refactored here into named operations. Nestor keeps the *algorithm*
    # (text normalization + difflib fuzzy scoring); the store keeps only the
    # persistence primitives.

    def memory_init(self) -> None:
        """Ensure the translation-memory table exists. Idempotent.

        (Was ``init_tm``: ``db.init_db()`` + ``executescript(_TM_SCHEMA)``.)
        """

    def memory_find(self, source_norm: str, source_lang: str,
                   target_lang: str) -> Optional[dict]:
        """Exact-key lookup by *normalized* source, for upsert.

        Returns the single pair whose ``source_norm`` + language pair match,
        or ``None``. The returned dict MUST expose ``id``, ``status``,
        ``target_text`` (read by ``add_pair`` to decide insert vs. seal).
        (Was the ``SELECT ... WHERE source_norm=? AND source_lang=? AND
        target_lang=?`` at the top of ``add_pair``.)
        """

    def memory_insert(self, pair: dict) -> None:
        """Insert one new translation-memory pair.

        ``pair`` carries every column Nestor writes: ``id``, ``source_text``,
        ``source_norm``, ``source_lang``, ``target_text``, ``target_lang``,
        ``status``, ``verifier``, ``weight``, ``origin``, ``created_at``.
        (Was the ``INSERT INTO tm_pairs`` in ``add_pair``.)
        """

    def memory_seal(self, pair_id: str, target_text: str, verifier: str,
                   weight: float, seal_sig: str = "") -> None:
        """Upgrade an existing pair to sealed status.

        Sets ``target_text``, ``status='sealed'``, ``verifier`` and ``weight``
        on the row with ``pair_id``. (Was the conditional ``UPDATE tm_pairs
        SET target_text=?, status='sealed', ...`` in ``add_pair``.)
        """

    def memory_candidates(self, source_lang: str,
                         target_lang: str) -> list[dict]:
        """Return ALL pairs for a language direction, for fuzzy scoring.

        Nestor's ``lookup`` ranks these with difflib in Python — the store
        does no matching, it just returns the candidate set. Each dict MUST
        expose at least ``source_norm``, ``status``, ``target_text``, ``id``.
        (Was the ``SELECT * WHERE source_lang=? AND target_lang=?`` in
        ``lookup``.)
        """

    def memory_stats(self) -> dict:
        """Return ``{"total", "sealed", "draft", "lang_pairs"}``.

        ``lang_pairs`` is a list of ``(source_lang, target_lang, count)``
        tuples, busiest first. (Was the COUNT/GROUP BY block in ``stats``.)
        """

    # --- rejection (OPTIONAL capability) ---------------------------------
    #
    # A reviewer could always record "this is right" (a seal) and never "this
    # is wrong", so a bad match came back identically forever and every
    # reviewer paid the same attention tax to dismiss it again. These three
    # operations close that.
    #
    # They are an OPTIONAL extension: a store predating them keeps working and
    # simply has no rejection capability. Nestor checks with
    # :func:`supports_rejection` before filtering, and the reject_* entry points
    # raise a clear RuntimeError rather than silently doing nothing. Implement
    # all three or none — a store with only some of them is treated as having
    # none, because writing rejections that are never read is worse than not
    # having the feature.

    def memory_reject_pair(self, pair_id: str, verifier: str, reason: str) -> None:
        """Mark a pair itself wrong: set ``status='rejected'`` on ``pair_id``.

        The mapping is bad in its own right, so it must never be served or
        offered as engine context again. Distinct from a *match* rejection —
        see :meth:`memory_add_rejection`.
        """

    def memory_add_rejection(self, rejection: dict) -> None:
        """Record that something must not be served **for one specific query**.

        ``rejection`` carries: ``id``, ``query_norm``, ``source_lang``,
        ``target_lang``, ``pair_id`` (``""`` if the rejected candidate has no
        pair yet), ``target_text``, ``verifier``, ``reason``, ``created_at``,
        ``reject_sig``.

        The pair named here stays valid for its OWN source text — this says only
        that it is the wrong answer for ``query_norm``. That distinction is the
        whole point: a false seal is a good pair matched to the wrong input, and
        deleting the pair would destroy a correct verification.
        """

    def memory_rejections(self, query_norm: str, source_lang: str,
                          target_lang: str) -> list[dict]:
        """Rejections recorded for exactly this query key and domain.

        Each dict MUST expose ``pair_id``, ``target_text``, ``verifier`` and
        ``reject_sig``. Returns ``[]`` when there are none.
        """

    # --- rejection listing (OPTIONAL, separate from the three above) ------
    #
    # The two reads above answer "what was refused for THIS query" and (under
    # curation) "what was refused against THIS pair". Neither can enumerate a
    # domain, and a rejection is allowed to name no pair at all —
    # :meth:`memory_add_rejection` documents ``pair_id`` as ``""`` when the
    # refused candidate never became one. So the pair-keyed walk cannot see
    # those rows, and :func:`nestor.portable.export_bundle` used it: a signed,
    # ledgered "no" against a raw candidate did not survive export → import.
    #
    # Deliberately NOT added to :data:`_REJECTION_OPS`. That tuple is
    # all-or-nothing, so a fourth entry would report every host store
    # implementing the existing three as having *no* rejection capability at
    # all — turning a bug about incomplete bundles into `reject_match` raising
    # on stores that work today. A separate predicate breaks nothing, and
    # follows the precedent set by :func:`supports_lineage`.

    def memory_list_rejections(self, source_lang: str = "", target_lang: str = "",
                               limit: int = 100_000) -> list[dict]:
        """Every rejection in a domain, whether or not it names a pair.

        Empty-string filters mean "no filter on this field". Rows carry the same
        fields as :meth:`memory_rejections`, plus ``reopen_when``. Ordered
        oldest-first so an export is stable across runs.
        """

    # --- curation (OPTIONAL capability) -----------------------------------
    #
    # Sealing was write-only: a pair could be verified but never browsed,
    # inspected, revoked or exported. For a system whose entire value is human
    # verification, the human could not see what they had verified. These four
    # reads/writes are the curator's surface.
    #
    # Optional and all-or-nothing on the same terms as rejection — see
    # :func:`supports_curation`.

    def memory_list(self, source_lang: str = "", target_lang: str = "",
                    status: str = "", verifier: str = "", contains: str = "",
                    limit: int = 50, offset: int = 0) -> list[dict]:
        """Browse pairs. Empty-string filters mean "no filter on this field".

        ``contains`` is a case-insensitive substring match against source OR
        target text. Results are newest-first and Nestor treats ``limit`` /
        ``offset`` as a stable pagination window. Each dict exposes the same
        columns as :meth:`memory_find`.
        """

    def memory_get(self, pair_id: str) -> Optional[dict]:
        """One pair by id, or ``None``."""

    def memory_unseal(self, pair_id: str, verifier: str, reason: str) -> None:
        """Demote a sealed pair back to ``draft`` and clear its signature.

        Distinct from :meth:`memory_reject_pair`. Unsealing says *"this needs
        verifying again"* and returns the pair to the review queue, where it can
        be re-sealed. Rejecting says *"this is wrong"* and retires it. A curator
        who is merely unsure must not have to choose between destroying a
        mapping and leaving a seal they no longer trust standing.

        The signature MUST be cleared: a row marked ``draft`` that still carries
        a valid seal signature is a seal waiting to be reactivated by anything
        that flips the status column back.
        """

    def memory_rejections_for_pair(self, pair_id: str) -> list[dict]:
        """Every rejection recorded against ``pair_id``, across all queries.

        A pair rejected for many different queries is probably junk — this is
        how a curator sees that.
        """

    # --- review queue (OPTIONAL capability) -------------------------------
    #
    # The reviewer's half of the surface was write-only in exactly the way the
    # memory was: ``translate_text`` *creates* documents and segments for tier-3
    # review, and nothing could read them back. The queue existed and could not
    # be worked without querying the host's own database directly — so the one
    # human the schema was built for could not see their own queue.
    #
    # Optional and all-or-nothing on the same terms as rejection and curation —
    # see :func:`supports_queue`. ``update_segment_status`` is part of the set
    # rather than an extra: a queue you can list but not clear offers the same
    # item forever, which is the attention tax rejection exists to end.

    def list_documents(self, status: str = "", limit: int = 50,
                       offset: int = 0) -> list[dict]:
        """Browse documents, newest first. ``status=""`` means no filter.

        Each dict exposes the columns :meth:`get_document` returns.
        """

    def list_segments(self, document_id: str = "", status: str = "",
                      limit: int = 200, offset: int = 0) -> list[dict]:
        """Browse segments, oldest first within a document (reading order).

        Empty-string filters mean "no filter on this field". Each dict exposes
        the columns :meth:`get_segment` returns, plus ``status`` — a reviewer
        needs to see what is still pending, not just what exists.
        """

    def update_segment_status(self, segment_id: str, status: str) -> None:
        """Set a segment's ``status`` column. No-op if the id is unknown.

        Nestor writes ``verified`` when a segment is graduated and ``rejected``
        when it is refused, so a decided segment leaves the queue.
        """


# --------------------------------------------------------------------------
# Global injection point
# --------------------------------------------------------------------------

_REJECTION_OPS = ("memory_reject_pair", "memory_add_rejection", "memory_rejections")


def supports_rejection(store: "Storage") -> bool:
    """Whether ``store`` implements the optional rejection capability.

    All three operations or none: a store that can record rejections but not
    read them back would let a reviewer believe their "no" was captured while
    the same bad match kept being served. Partial support is therefore reported
    as no support.
    """
    return supports(store, "rejection")


_REJECTION_LISTING_OPS = ("memory_list_rejections",)


def supports_rejection_listing(store: "Storage") -> bool:
    """Whether ``store`` can enumerate rejections by domain rather than by key.

    Its own predicate rather than a fourth entry in :data:`_REJECTION_OPS`,
    because that tuple is all-or-nothing: adding to it would report every store
    implementing the existing three as having no rejection capability, and
    ``reject_match`` would start raising on stores that work today. Widening a
    capability must not be able to switch one off.

    A store without it can still record and read rejections; what it cannot do
    is hand :func:`nestor.portable.export_bundle` the ones that name no pair.
    Export says so out loud rather than shipping a quietly short bundle.
    """
    return supports(store, "rejection_listing")


_CURATION_OPS = ("memory_list", "memory_get", "memory_unseal",
                 "memory_rejections_for_pair")


def supports_curation(store: "Storage") -> bool:
    """Whether ``store`` implements the optional curation capability.

    All four or none, for the same reason as :func:`supports_rejection`: a
    curator surface that can list but not unseal, or unseal without showing what
    is being unsealed, is worse than none — it invites a decision the store
    cannot actually carry out.
    """
    return supports(store, "curation")


_QUEUE_OPS = ("list_documents", "list_segments", "update_segment_status")


def supports_queue(store: "Storage") -> bool:
    """Whether ``store`` implements the optional review-queue capability.

    All three or none, for the same reason as the other two: a queue that lists
    work but cannot record the decision leaves the reviewer looking at segments
    they have already sealed, and a reviewer who cannot trust the queue to empty
    stops trusting the queue.
    """
    return supports(store, "queue")


_LINEAGE_OPS = ("memory_mark_superseded", "memory_lineage")


class LineageStorage(Storage, Protocol):
    """``Storage`` plus the lineage capability (see :func:`supports_lineage`).

    Exists only as a ``cast`` target: a caller that already ran
    :func:`supports_lineage` (or the ``_require_lineage`` raise-if-not
    wrapper in :mod:`nestor.memory`) knows the two methods below are present,
    but that runtime check does not by itself tell the type checker so —
    a store predating this capability legitimately has no
    ``memory_mark_superseded`` on its plain ``Storage`` type. The predicate
    stays the single source of truth for *whether* a store qualifies; this
    class only names *what* it gains once it does.
    """

    def memory_mark_superseded(self, pair_id: str, successor_id: str) -> None: ...

    def memory_lineage(self, pair_id: str) -> list[dict]: ...


_ATOMIC_SUPERSEDE_OPS = ("memory_mark_superseded_if",)


class AtomicSupersedeStorage(Storage, Protocol):
    """``Storage`` plus the atomic-supersede capability — a ``cast`` target
    on the same terms as :class:`LineageStorage`; see
    :func:`supports_atomic_supersede`."""

    def memory_mark_superseded_if(self, pair_id: str, successor_id: str,
                                  expected_status: str,
                                  expected_superseded_by: str = "") -> bool: ...


def supports_atomic_supersede(store: "Storage") -> bool:
    """Whether ``store`` can retire a row conditionally, in one statement.

    Its own predicate rather than a fourth entry in :data:`_LINEAGE_OPS`, on
    :func:`supports_rejection_listing`'s precedent: that tuple is
    all-or-nothing, so extending it would report every host store implementing
    the existing pair as having *no* lineage capability at all.

    Without it, ``memory.revise_draft`` refuses rather than racing. That is a
    deliberate refusal, not a degrade: the operation it would otherwise perform
    can retire a human's seal and install an unverified draft in its place, and
    "probably not concurrent" is not a basis on which to risk that. Sealing and
    superseding a *sealed* row are unaffected — they are human-driven and carry
    a verifier; this verb is the one an agent drives at machine frequency.
    """
    return supports(store, "atomic_supersede")


def supports_lineage(store: "Storage") -> bool:
    """Whether ``store`` implements the optional lineage capability.

    Both operations or none, same rule as the other three: a store that can
    retire a row nobody can read back is an archive with no door, and one
    that can list lineage it cannot write is a door with no archive. Without
    this capability :func:`nestor.memory.supersede_pair` raises rather than
    falling back to the destructive overwrite it exists to replace —
    destroying a prior human decision quietly must not be a fallback
    (the ``reject_*`` precedent, one capability over).
    """
    return supports(store, "lineage")


_EDGE_OPS = ("memory_add_edge", "memory_edges_to", "memory_edges_from",
             "memory_seal_edge")


class EdgeStorage(Storage, Protocol):
    """``Storage`` plus the decision-graph capability — a ``cast`` target on
    the same terms as :class:`LineageStorage`; see :func:`supports_edges`."""

    def memory_add_edge(self, edge: dict) -> None: ...

    def memory_edges_to(self, dst_id: str, kind: str = "") -> list[dict]: ...

    def memory_edges_from(self, src_id: str, kind: str = "") -> list[dict]: ...

    def memory_seal_edge(self, edge_id: str, verifier: str,
                         edge_sig: str) -> bool: ...


def supports_edges(store: "Storage") -> bool:
    """Whether ``store`` implements the optional decision-graph capability
    (docs/decision-memory.md N6).

    Its own predicate rather than a fourth entry in :data:`_LINEAGE_OPS`, on
    :func:`supports_atomic_supersede`'s precedent: that tuple is all-or-nothing,
    so extending it would report every host store implementing the existing
    lineage pair as having *no* lineage capability at all. Without this,
    :class:`nestor.decision.DecisionMemory` still records and seals decisions —
    it just cannot relate one to another, so ``constraints_on`` returns the
    live decision and its rejected alternatives but no graph neighbours.
    """
    return supports(store, "edges")


_EVIDENCE_OPS = ("memory_add_evidence", "memory_evidence_for",
                 "memory_unevidenced_seals")


class EvidenceStorage(Storage, Protocol):
    """``Storage`` plus the evidence capability (docs/evidence-edge.md) — a
    ``cast`` target on the same terms as :class:`EdgeStorage`; see
    :func:`supports_evidence`."""

    def memory_add_evidence(self, ev: dict) -> None: ...

    def memory_evidence_for(self, pair_id: str) -> list[dict]: ...

    def memory_unevidenced_seals(self, source_lang: str = "",
                                 target_lang: str = "") -> list[dict]: ...


def supports_evidence(store: "Storage") -> bool:
    """Whether ``store`` implements the optional evidence capability
    (docs/evidence-edge.md).

    Its own predicate on :func:`supports_edges`' precedent — a host store
    without it still seals and serves exactly as before; it simply cannot record
    what a claim rests on, so :func:`nestor.evidence.attach` raises rather than
    dropping the reference, and the unevidenced-seals report is unavailable.
    """
    return supports(store, "evidence")


_VERIFIER_POLICY_OPS = ("memory_policy_add", "memory_policy_remove",
                        "memory_policy_list")


class VerifierPolicyStorage(Storage, Protocol):
    """``Storage`` plus the verifier-policy capability — a ``cast`` target on
    the same terms as :class:`EdgeStorage`; see :func:`supports_verifier_policy`."""

    def memory_policy_add(self, source_lang: str, target_lang: str,
                          verifier: str) -> dict: ...

    def memory_policy_remove(self, source_lang: str, target_lang: str,
                             verifier: str) -> bool: ...

    def memory_policy_list(self, source_lang: str = "",
                           target_lang: str = "") -> list[dict]: ...


def supports_verifier_policy(store: "Storage") -> bool:
    """Whether ``store`` can enforce a per-domain verifier allowlist
    (issue #167 piece 3).

    Its own predicate on :func:`supports_evidence`'s precedent. Without it,
    :func:`nestor.memory.add_pair` / :func:`nestor.memory.supersede_pair`
    skip the check entirely and every verifier name is accepted at seal
    time, exactly as before this capability existed — a host store predating
    it, or one that never opted in, keeps working unchanged. With it, a
    domain that has recorded at least one policy row refuses a seal from any
    verifier not on that row's list; a domain with none is unrestricted (the
    opt-in semantics live in :mod:`nestor.memory`, not here).
    """
    return supports(store, "verifier_policy")


# --------------------------------------------------------------------------
# The capability registry
# --------------------------------------------------------------------------
#
# Everything above this point defines each capability's ops tuple and its
# ``supports_<cap>`` predicate by hand, once per capability — nine times the
# same ``all(callable(getattr(store, op, None)) for op in OPS)`` line, and
# (in memory.py, decision.py, evidence.py, curator.py) a ``_require_<cap>``
# wrapper repeating the same "not supported -> raise" shape with its own
# exception and message. This table is the one place a capability's ops list
# lives; ``supports()`` and ``require_capability()`` below are the one place
# the "is it there" and "raise if not" logic lives. The ``supports_<cap>``
# predicates above are kept (name, docstring, and return value all unchanged)
# as thin shims over :func:`supports`, so every existing caller —
# ``from nestor.storage import supports_rejection`` included — keeps working
# unmodified; ``embedding_store`` is registered here too even though its
# Protocol, predicate and callers live in :mod:`nestor.embedding_store`
# (kept there because that capability was deliberately never folded into the
# core ``Storage`` Protocol — see that module's docstring).
_CAPABILITY_OPS: dict[str, tuple[str, ...]] = {
    "rejection": _REJECTION_OPS,
    "rejection_listing": _REJECTION_LISTING_OPS,
    "curation": _CURATION_OPS,
    "queue": _QUEUE_OPS,
    "lineage": _LINEAGE_OPS,
    "atomic_supersede": _ATOMIC_SUPERSEDE_OPS,
    "edges": _EDGE_OPS,
    "evidence": _EVIDENCE_OPS,
    "verifier_policy": _VERIFIER_POLICY_OPS,
    "embedding_store": ("embedding_load", "embedding_save", "embedding_drop"),
}


def supports(store: "Storage", capability: str) -> bool:
    """Whether ``store`` implements ``capability`` — the table-driven form of
    the individual ``supports_<cap>`` predicates above (and of
    :func:`nestor.embedding_store.supports_embedding_store`).

    ``capability`` is one of :data:`_CAPABILITY_OPS`'s keys, e.g.
    ``supports(store, "lineage")``. All of a capability's ops or none, same
    rule every ``supports_<cap>`` predicate documents on its own: partial
    support is reported as no support.
    """
    return all(callable(getattr(store, op, None))
              for op in _CAPABILITY_OPS[capability])


def require_capability(store: "Storage", capability: str, message: str,
                       exc_type: "type[BaseException]" = RuntimeError) -> None:
    """Raise ``exc_type(message)`` unless ``supports(store, capability)``.

    The table-driven counterpart of the hand-written ``_require_<cap>``
    wrappers (``nestor.memory._require_lineage`` / ``_require_rejection``,
    ``nestor.decision.DecisionMemory._require_edges``,
    ``nestor.evidence._require_evidence``, the check in
    ``nestor.curator.Curator.__init__``). Each of those raises its own exact
    exception type and message for its own capability — most raise
    ``RuntimeError``, curation raises ``CurationUnsupportedError`` — so
    rather than hardcode one exception type here (or import the others,
    which this module cannot do without risking an import cycle: it is
    imported by all of them), the caller supplies the message and, when it
    is not the default ``RuntimeError``, the exception class. This function
    only centralizes the "check, then raise" shape; each call site still
    owns its own wording and exception type exactly as before.
    """
    if not supports(store, capability):
        raise exc_type(message)


_store: "Optional[Storage]" = None


def set_store(store: "Storage") -> None:
    """Install the process-wide store used when no explicit ``store=`` is passed."""
    global _store
    _store = store


def get_store(store: "Optional[Storage]" = None) -> "Storage":
    """Resolve the store to use.

    An explicit ``store`` argument wins. Otherwise the global store set via
    :func:`set_store` is returned. Raises ``RuntimeError`` with a clear
    message if neither is available — Nestor never falls back to a hidden
    default database.
    """
    if store is not None:
        return store
    if _store is None:
        raise RuntimeError(
            "Nestor storage is not configured. Call nestor.storage.set_store(...) "
            "with a Storage implementation (e.g. nestor.sqlite_store.SqliteStore()) "
            "before using the cascade, or pass store=... explicitly."
        )
    return _store
