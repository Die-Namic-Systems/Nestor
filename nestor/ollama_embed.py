"""Local embeddings via Ollama (``nomic-embed-text``) — stdlib only.

Mirrors the fleet's nest embed client: POST ``/api/embeddings`` on
``OLLAMA_HOST`` (default ``http://localhost:11434``). No pip extra — the
dependency is a running daemon and an installed model tag, not a wheel.

``nomic-embed-text`` needs a task prefix or cosine scores bunch near chance.
This module always uses the document prefix so :class:`~nestor.semantic_matcher.SemanticMatcher`
keeps ``score(a, b) == score(b, a)`` and ``scores_against`` stays consistent
with ``score`` (asymmetric query/document prefixes would break that seam).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from . import config

# OLLAMA_HOST is not a NESTOR_* var (it names the fleet's own embed client
# convention) and stays a plain env read. The two NESTOR_OLLAMA_EMBED_* names
# are pulled from the registry rather than re-declaring their defaults here —
# still a bare `os.environ.get`, deliberately not `config.load()`, because
# these are computed once at import: routing an import-time constant through
# the resolver's file layer would mean an unrelated, malformed
# nestor.config.json in the working directory could fail `import
# nestor.ollama_embed` outright, which no prior behavior here risked.
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_MODEL_SPEC = config.REGISTRY["NESTOR_OLLAMA_EMBED_MODEL"]
DEFAULT_EMBED_MODEL = os.environ.get(_MODEL_SPEC.name, _MODEL_SPEC.default)

DOC_PREFIX = "search_document: "

_CAPS = (4000, 2000, 1000)
_TIMEOUT_SPEC = config.REGISTRY["NESTOR_OLLAMA_EMBED_TIMEOUT"]
_TIMEOUT = float(os.environ.get(_TIMEOUT_SPEC.name, str(_TIMEOUT_SPEC.default)))
_ALLOWED_SCHEMES = frozenset({"http", "https"})

_installed: set[str] | None = None


def host() -> str:
    """Resolved Ollama base URL (env wins over the shipped default).

    Only ``http`` / ``https`` are accepted — Bandit B310 and accidental
    ``file:`` / custom schemes both fail closed here, before any open.
    """
    raw = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    scheme = urllib.parse.urlsplit(raw).scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"OLLAMA_HOST must be http(s), got scheme {scheme!r} from {raw!r}"
        )
    return raw


def _urlopen(url: str, data: bytes | None = None, timeout: float = _TIMEOUT):
    """GET/POST ``url`` after re-checking the scheme (defense in depth for B310)."""
    scheme = urllib.parse.urlsplit(url).scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"refusing non-http(s) URL: {url!r}")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    # Scheme checked above; urlopen still flagged because the URL is dynamic.
    return urllib.request.urlopen(req, timeout=timeout)  # nosec B310


def reset_cache() -> None:
    """Drop the cached ``/api/tags`` set — for tests that flip reachability."""
    global _installed
    _installed = None


def installed_models() -> set[str]:
    global _installed
    if _installed is not None:
        return _installed
    try:
        with _urlopen(f"{host()}/api/tags", timeout=5) as resp:
            tags = json.loads(resp.read().decode("utf-8"))
        _installed = {m.get("name", "") for m in tags.get("models", [])}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        _installed = set()
    return _installed


def available(model: str = DEFAULT_EMBED_MODEL) -> bool:
    """True when Ollama answers and ``model`` (or a ``model:tag``) is installed."""
    models = installed_models()
    if not models:
        return False
    base = model.split(":", 1)[0]
    return model in models or any(m.split(":", 1)[0] == base for m in models)


def _resolve(model: str) -> str | None:
    models = installed_models()
    if model in models:
        return model
    base = model.split(":", 1)[0]
    for m in models:
        if m.split(":", 1)[0] == base:
            return m
    return None


def _post(prompt: str, model: str) -> list[float] | None:
    data = json.dumps({"model": model, "prompt": prompt}).encode("utf-8")
    with _urlopen(f"{host()}/api/embeddings", data=data, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8")).get("embedding")


def embed_one(text: str, model: str = DEFAULT_EMBED_MODEL) -> tuple[float, ...]:
    """Embed one surface with the document prefix. Raises on failure."""
    tag = _resolve(model)
    if not tag:
        raise RuntimeError(
            f"Ollama model {model!r} is not installed at {host()} "
            f"(pull it, or set NESTOR_OLLAMA_EMBED_MODEL)"
        )
    raw = "" if text is None else str(text)
    if not raw.strip():
        raise ValueError("cannot embed empty text")
    last_exc: BaseException | None = None
    for cap in _CAPS:
        try:
            vec = _post(f"{DOC_PREFIX}{raw[:cap]}", tag)
            if vec:
                return tuple(float(x) for x in vec)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            continue
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise RuntimeError(
                f"Ollama embed failed at {host()}: {type(exc).__name__}: {exc}"
            ) from exc
    detail = f"{type(last_exc).__name__}: {last_exc}" if last_exc else "empty embedding"
    raise RuntimeError(f"Ollama embed failed at {host()} for {tag!r}: {detail}")


def embed_many(texts: list[str], model: str = DEFAULT_EMBED_MODEL) -> list[tuple[float, ...]]:
    """Embed many surfaces; Ollama takes one prompt per request, so this loops."""
    return [embed_one(t, model=model) for t in texts]
