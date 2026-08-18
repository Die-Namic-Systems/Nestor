"""Per-language-pair term locks — the consistency promise, and tier 2's constraint.

**Where the glossary lives is a setting, not an accident of the working
directory** (IDEAS §6.27). This module used to hold
``pathlib.Path("data/glossary.json")`` and resolve it on every call, so the
locks a deployment had were a function of where its process was launched: a
service unit and the shell that entered the terms disagreed in silence, and the
only symptom was tier-2 drafts quietly ignoring terminology somebody chose.

Resolution follows :func:`nestor.cascade.set_ledger_path` — an explicit
override wins, then ``NESTOR_GLOSSARY``, then the default relative to the
current directory **captured once at import** rather than re-read per call. The
last of those is still launch-dependent and is the compatible default; the
first two are how a deployment stops guessing.

Only the *default* is captured. ``NESTOR_GLOSSARY`` is read on every call, the
same posture the ledger has, so a ``chdir`` cannot move the file but a
mid-process environment change still can — raised in review of PR #47 and
measured. :func:`set_glossary_path` is what pins it: it wins over the variable,
so a deployment that wants the path fixed for the life of the process calls it
once at startup rather than trusting the environment to stay still.
"""
from __future__ import annotations

import json
import pathlib
from typing import Optional

from . import config

#: Captured at import, so a `chdir` mid-process cannot silently move the
#: glossary out from under a running server. Launch-dependent by default —
#: `NESTOR_GLOSSARY` or `set_glossary_path` is how you stop that mattering.
_DEFAULT_PATH = (pathlib.Path.cwd() / "data" / "glossary.json").resolve()

_OVERRIDE: Optional[pathlib.Path] = None


def set_glossary_path(path) -> None:
    """Point the term locks at ``path``. Wins over ``NESTOR_GLOSSARY``.

    Pass ``None`` to fall back to the environment and then the default.
    """
    global _OVERRIDE
    _OVERRIDE = None if path is None else pathlib.Path(path).expanduser().resolve()


def glossary_path() -> pathlib.Path:
    """The file the locks are read from and written to. Always absolute."""
    if _OVERRIDE is not None:
        return _OVERRIDE
    # get_str's blank-env fallthrough and the old `if env:` truthy check land
    # on the same branch (both fall through when NESTOR_GLOSSARY is unset or
    # blank), so adopting the resolver only adds the file layer here.
    env = config.load().get_str("glossary", "")
    if env:
        return pathlib.Path(env).expanduser().resolve()
    return _DEFAULT_PATH


def _key(source_lang: str, target_lang: str) -> str:
    return f"{source_lang}->{target_lang}"


def load() -> dict:
    path = glossary_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save(data: dict) -> None:
    path = glossary_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8")


def add_term(term: str, translation: str, source_lang: str, target_lang: str) -> None:
    data = load()
    data.setdefault(_key(source_lang, target_lang), {})[term] = translation
    save(data)


def terms_for(source_lang: str, target_lang: str) -> dict[str, str]:
    return load().get(_key(source_lang, target_lang), {})


def _word_boundary_match(needle: str, haystack: str) -> bool:
    """Check if needle appears in haystack as a whole word, not inside a longer word."""
    import re
    return bool(re.search(r'\b' + re.escape(needle) + r'\b', haystack, re.IGNORECASE))


def locks_in_text(text: str, source_lang: str, target_lang: str) -> dict[str, str]:
    """The subset of glossary terms that actually appear in this segment.

    Uses word-boundary matching so a short term like "lock" does not fire
    inside "blockchain" or "locksmith" (IDEAS §6.38).
    """
    return {t: tr for t, tr in terms_for(source_lang, target_lang).items()
            if _word_boundary_match(t, text)}
