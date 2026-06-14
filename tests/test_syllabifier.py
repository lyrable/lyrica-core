from processor.syllabifier import Lang, syllabify_word


def test_single_syllable_returns_none_offsets():
    word, offsets = syllabify_word("cat", duration_subbeats=4, lang=Lang.EN)
    assert word == "cat"
    assert offsets is None


def test_multi_syllable_word_splits_and_offsets():
    word, offsets = syllabify_word("beautiful", duration_subbeats=8, lang=Lang.EN)
    assert "|" in word
    assert offsets is not None
    assert len(offsets) >= 2
    assert offsets[0] == 0.0


def test_hyphenated_word_splits():
    word, offsets = syllabify_word("nah-nah", duration_subbeats=4, lang=Lang.EN)
    assert "|" in word
    assert offsets is not None
