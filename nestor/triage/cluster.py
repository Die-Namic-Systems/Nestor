"""Cluster pass — group the seal queue into themed batches a human can review.

Re-lands the clustering **shape** of willow-mcp's ``nest/selflearn`` clean-room
(no import of ``willow_mcp`` — it is not available here): build a similarity
graph over the decisions' ``question`` text, then cut it into communities with a
stdlib, deterministic method. Nothing here reaches a network, a clock, or a
random source, so the same decisions in give the same groups out and a test can
pin the result.

The pipeline is three passes, each deterministic:

1. **Normalize once.** ``matcher.normalize`` is called a single time per
   decision; every pairwise score reuses those norms.
2. **Graph.** For each pair an edge exists when
   ``matcher.similarity(norm_i, norm_j) >= bar``. The pair count is quadratic
   (~50k for 316 decisions), so two lossless short-circuits keep the expensive
   ``difflib`` ratio off pairs that cannot clear the bar: a length-ratio ceiling
   (the most two strings can share is the shorter length) and, when the matcher
   offers it, :meth:`StringMatcher.similarity_bound` — an upper bound that is
   cheaper than the real ratio. A pair whose upper bound is below ``bar`` cannot
   be above it, so it is dropped without ever being scored in full.
3. **Community detection.** Asynchronous label propagation over the graph,
   nodes visited in sorted-id order with ties broken toward the smallest label —
   fully determined, no seed needed. Connected components would be an acceptable
   floor; label propagation is the closer re-land of the selflearn shape and
   splits weakly-bridged themes that components would merge.

Each returned :class:`Cluster` carries:

* ``member_ids`` — the decision ids, sorted.
* ``representative_id`` — the most central member (largest sum of in-cluster
  edge similarities; ties to the smallest id).
* ``label`` — a short theme from the tokens shared across the group's questions,
  trivial stopwords dropped, ranked by how many members use each token.

Singletons (a decision with no above-``bar`` neighbour) are surfaced as their own
one-member clusters, never dropped.
"""
from __future__ import annotations

from collections import Counter

from nestor.matcher import Matcher
from nestor.triage import Cluster, Decision

#: Tokens too common to name a theme. Kept small and generic on purpose — the
#: label only needs the *distinctive* shared words, and an over-long list would
#: start dropping real domain terms. Deterministic (a frozenset membership test).
_STOPWORDS = frozenset({
    "a", "an", "and", "the", "of", "to", "in", "on", "for", "is", "it", "its",
    "be", "was", "were", "are", "as", "at", "by", "or", "if", "do", "does",
    "did", "should", "would", "could", "can", "cant", "will", "wont", "not",
    "no", "yes", "this", "that", "these", "those", "there", "here", "with",
    "without", "from", "into", "onto", "how", "what", "why", "when", "where",
    "which", "who", "whom", "whose", "you", "your", "i", "we", "they", "them",
    "he", "she", "his", "her", "my", "me", "us", "our", "any", "all", "some",
    "each", "both", "one", "two", "own", "get", "got", "make", "made", "want",
    "wants", "way", "s", "t", "re", "d", "ll", "m", "than", "then", "so",
    "but", "have", "has", "had", "up", "out", "over", "about", "still", "just",
    "only", "also", "per", "vs",
})

#: How many shared tokens a label may name before it stops being a label.
_LABEL_TOKENS = 3


def _tokens(norm: str) -> list[str]:
    """Content tokens of a normalized question — stopwords and one-char tokens out.

    ``normalize`` has already lowercased, stripped punctuation and collapsed
    whitespace, so a bare ``split`` yields clean word tokens.
    """
    return [w for w in norm.split() if len(w) > 1 and w not in _STOPWORDS]


def _label(member_norms: list[str], fallback: str) -> str:
    """A short theme from the tokens shared across a cluster's questions.

    Ranks tokens by *document frequency* — how many members use the token — so a
    word two members share outranks one a single member repeats. Ties break
    alphabetically, so the label is a pure function of the members. ``fallback``
    (the representative id) is used only when every question is all-stopword.
    """
    df: Counter[str] = Counter()
    for norm in member_norms:
        df.update(set(_tokens(norm)))
    if not df:
        return fallback
    ranked = sorted(df.items(), key=lambda kv: (-kv[1], kv[0]))
    return " ".join(tok for tok, _ in ranked[:_LABEL_TOKENS])


def _build_graph(norms: list[str], matcher: Matcher,
                 bar: float) -> tuple[list[list[int]], dict[tuple[int, int], float]]:
    """Adjacency lists and edge weights for the similarity graph.

    An edge ``(i, j)`` with ``i < j`` exists when the two normalized questions
    score ``>= bar``. Two lossless filters keep full scoring off pairs that
    cannot clear the bar — a length-ratio ceiling and ``similarity_bound`` — but
    both are upper bounds on *difflib's* ratio only, not on an embedding matcher's
    cosine (a short paraphrase of a long question is a real semantic edge with a
    poor length ratio). So both are gated on ``has_bound``: the character matcher
    that publishes ``similarity_bound`` gets the prunes; a semantic / ollama
    matcher skips them and scores every pair, which is cheap because it caches
    each question's embedding and the pairwise step is only a cosine.
    """
    n = len(norms)
    lengths = [len(x) for x in norms]
    # Fetched once via getattr (Matcher — the generic Protocol — does not
    # declare this method; only StringMatcher's cheap-bound optimization
    # does) and called through the same reference below, rather than
    # re-accessing `matcher.similarity_bound` directly, so a type checker
    # sees one dynamic lookup instead of an attribute Matcher doesn't have.
    similarity_bound = getattr(matcher, "similarity_bound", None)
    adj: list[list[int]] = [[] for _ in range(n)]
    weights: dict[tuple[int, int], float] = {}
    for i in range(n):
        a = norms[i]
        la = lengths[i]
        if not la:
            continue
        for j in range(i + 1, n):
            lb = lengths[j]
            if not lb:
                continue
            b = norms[j]
            # Prunes valid only for a length-bounded (difflib) matcher — see the
            # docstring. A matcher without similarity_bound (semantic/ollama)
            # scores every pair rather than risk dropping a real paraphrase edge.
            # Checked with `is not None` (not a separate `has_bound` flag) so
            # the call below narrows away the "callable or None" type instead
            # of relying on a bool alias a type checker cannot trace back.
            if similarity_bound is not None:
                if 2.0 * min(la, lb) / (la + lb) < bar:
                    continue
                if similarity_bound(a, b, floor=bar) < bar:
                    continue
            score = matcher.similarity(a, b)
            if score >= bar:
                adj[i].append(j)
                adj[j].append(i)
                weights[(i, j)] = score
    return adj, weights


def _label_propagation(adj: list[list[int]]) -> list[int]:
    """Deterministic asynchronous label propagation.

    Each node starts as its own label. On every pass the nodes are visited in
    ascending index order and each adopts the label most common among its
    neighbours, with ties broken toward the smallest label id (and a node keeps
    its own label when that is already among the winners). Passes repeat until
    one changes nothing. Isolated nodes never change and stay their own label,
    which is exactly the singleton-cluster behaviour the contract wants.

    No randomness and a fixed visit order, so the fixed point is a pure function
    of ``adj``.
    """
    labels = list(range(len(adj)))
    changed = True
    # A full pass can only propagate a label one hop, so the graph settles in at
    # most (node count) passes; the cap is a guard, not the usual exit.
    for _ in range(len(adj) + 1):
        if not changed:
            break
        changed = False
        for node, neighbours in enumerate(adj):
            if not neighbours:
                continue
            counts: Counter[int] = Counter(labels[k] for k in neighbours)
            best = max(counts.values())
            current = labels[node]
            if counts.get(current, 0) == best:
                continue  # keep own label when it ties for most common — stable
            winner = min(lbl for lbl, c in counts.items() if c == best)
            if winner != current:
                labels[node] = winner
                changed = True
    return labels


def group(decisions: list[Decision], matcher: Matcher, bar: float) -> list[Cluster]:
    """Group ``decisions`` into themed clusters on their ``question`` text.

    Returns a list of :class:`Cluster`, sorted so the output is stable: largest
    groups first, ties broken by representative id. Every input decision appears
    in exactly one cluster; singletons are their own one-member clusters.
    """
    if not decisions:
        return []

    ids = [d.id for d in decisions]
    norms = [matcher.normalize(d.question) for d in decisions]

    adj, weights = _build_graph(norms, matcher, bar)
    labels = _label_propagation(adj)

    # Bucket node indices by their settled label.
    buckets: dict[int, list[int]] = {}
    for node, lbl in enumerate(labels):
        buckets.setdefault(lbl, []).append(node)

    clusters: list[Cluster] = []
    for members in buckets.values():
        members.sort(key=lambda idx: ids[idx])
        # Centrality: sum of in-cluster edge similarities; most central wins,
        # ties to the smallest id. Singletons trivially pick themselves.
        member_set = set(members)
        best_idx = members[0]
        best_score = -1.0
        for idx in members:
            total = 0.0
            for other in adj[idx]:
                if other in member_set:
                    key = (idx, other) if idx < other else (other, idx)
                    total += weights[key]
            if total > best_score:
                best_score = total
                best_idx = idx
        rep_id = ids[best_idx]
        label = _label([norms[idx] for idx in members], rep_id)
        clusters.append(Cluster(
            label=label,
            member_ids=tuple(ids[idx] for idx in members),
            representative_id=rep_id,
        ))

    clusters.sort(key=lambda c: (-len(c.member_ids), c.representative_id))
    return clusters
