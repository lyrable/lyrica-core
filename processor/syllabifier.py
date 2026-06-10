from __future__ import annotations

try:
    import pyphen
    _dic = pyphen.Pyphen(lang="ru_RU")
    _USE_PYPHEN = True
except (ImportError, KeyError):
    _USE_PYPHEN = False


_VOWELS = set("аеёиоуыэюяАЕЁИОУЫЭЮЯ") # fallback for no pyphen available


def _strip_punct(word: str) -> tuple[str, str, str]:
    left, right = 0, len(word)
    while left < right and not word[left].isalpha():
        left += 1
    while right > left and not word[right - 1].isalpha():
        right -= 1
    return word[left:right], word[:left], word[right:]


def _fallback_split(clean: str) -> list[str]:
    if not clean:
        return []
    syllables, current = [], ""
    for i, ch in enumerate(clean):
        current += ch
        if ch in _VOWELS:
            if i + 1 < len(clean) and clean[i + 1] not in _VOWELS:
                syllables.append(current)
                current = ""
    if current:
        if syllables:
            syllables[-1] += current
        else:
            syllables.append(current)
    return syllables if len(syllables) > 1 else []


def _split_word(clean: str) -> list[str]:
    if _USE_PYPHEN:
        parts = _dic.inserted(clean, hyphen="|").split("|")
        return parts if len(parts) > 1 else []
    return _fallback_split(clean)


def syllabify_word(word: str, duration_subbeats: int) -> list[float] | None:
    # returns a list of offsetted words in subbeats from the beginning of the word (beat_id)
    # if there is only one syllable => None

    clean, prefix, suffix = _strip_punct(word)
    parts = _split_word(clean)

    if len(parts) <= 1:
        return None

    n = len(parts)
    step = duration_subbeats / n
    offsets = [round(i * step, 2) for i in range(n)]
    return offsets


def syllabify_text(word: str) -> str:
    # returns word with syllable separations (ex. Ван|на)

    clean, prefix, suffix = _strip_punct(word)
    parts = _split_word(clean)
    if len(parts) <= 1:
        return word
    return prefix + "|".join(parts) + suffix