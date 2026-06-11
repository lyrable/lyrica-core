from __future__ import annotations

import re
from enum import Enum

try:
    import pyphen
    _dic_ru = pyphen.Pyphen(lang="ru_RU")
    _dic_en = pyphen.Pyphen(lang="en_US")
    _USE_PYPHEN = True
except (ImportError, KeyError):
    _USE_PYPHEN = False


_VOWELS_RU = set("аеёиоуыэюяАЕЁИОУЫЭЮЯ")
_VOWELS_EN = set("aeiouAEIOU")


class Lang(str, Enum):
    RU = "ru"
    EN = "en"


def _strip_punct(word: str) -> tuple[str, str, str]:
    left, right = 0, len(word)
    while left < right and not word[left].isalpha():
        left += 1
    while right > left and not word[right - 1].isalpha():
        right -= 1
    return word[left:right], word[:left], word[right:]


def _fallback_split(clean: str, lang: Lang) -> list[str]:
    vowels = _VOWELS_RU if lang == Lang.RU else _VOWELS_EN
    if not clean:
        return []
    syllables, current = [], ""
    for i, ch in enumerate(clean):
        current += ch
        if ch in vowels:
            if i + 1 < len(clean) and clean[i + 1] not in vowels:
                syllables.append(current)
                current = ""
    if current:
        if syllables:
            syllables[-1] += current
        else:
            syllables.append(current)
    return syllables if len(syllables) > 1 else []


def _split_clean(clean: str, lang: Lang) -> list[str]:
    # syllabifies word
    if not clean:
        return [clean]
    if _USE_PYPHEN:
        dic = _dic_ru if lang == Lang.RU else _dic_en
        parts = dic.inserted(clean, hyphen="|").split("|")
        return parts if len(parts) > 1 else [clean]
    parts = _fallback_split(clean, lang)
    return parts if parts else [clean]


def _split_word(clean: str, lang: Lang) -> list[str]:
    # splits words (such as nah-nah) into (nah nah)
    if "-" in clean:
        parts = []
        for chunk in clean.split("-"):
            parts.extend(_split_clean(chunk, lang))
        return parts
    return _split_clean(clean, lang)


def syllabify_word(
    word: str,
    duration_subbeats: int,
    lang: Lang = Lang.RU,
) -> tuple[str, list[float]] | tuple[str, None]:
    # returns a list of offsetted words in subbeats from the beginning of the word (beat_id)
    # if there is only one syllable => None

    clean, prefix, suffix = _strip_punct(word)
    parts = _split_word(clean, lang)

    if len(parts) <= 1:
        return word, None

    n = len(parts)
    step = duration_subbeats / n
    offsets = [round(i * step, 2) for i in range(n)]
    syllabified = prefix + "|".join(parts) + suffix

    return syllabified, offsets