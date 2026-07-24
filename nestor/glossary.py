"""Per-language-pair term locks — the consistency promise, and tier 2's constraint."""
from __future__ import annotations

import json
import pathlib

_PATH = pathlib.Path("data/glossary.json")


def _key(source_lang: str, target_lang: str) -> str:
    return f"{source_lang}->{target_lang}"


def load() -> dict:
    if _PATH.exists():
        return json.loads(_PATH.read_text(encoding="utf-8"))
    return {}


def save(data: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
                     encoding="utf-8")


def add_term(term: str, translation: str, source_lang: str, target_lang: str) -> None:
    data = load()
    data.setdefault(_key(source_lang, target_lang), {})[term] = translation
    save(data)


def terms_for(source_lang: str, target_lang: str) -> dict[str, str]:
    return load().get(_key(source_lang, target_lang), {})


def locks_in_text(text: str, source_lang: str, target_lang: str) -> dict[str, str]:
    """The subset of glossary terms that actually appear in this segment."""
    lower = text.lower()
    return {t: tr for t, tr in terms_for(source_lang, target_lang).items()
            if t.lower() in lower}
