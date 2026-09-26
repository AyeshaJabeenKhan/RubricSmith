from text_utils import contains_phrase, normalize, same_word, tokenize


def test_normalize_removes_case_punctuation_and_accents():
    assert normalize("  Café, the  REFUND!! ") == "cafe the refund"


def test_tokenize_can_drop_stopwords():
    assert tokenize("The parcel is on the way", drop_stopwords=True) == ["parcel", "way"]


def test_same_word_handles_simple_plurals_only():
    assert same_word("refund", "refunds")
    assert same_word("boxes", "box")
    assert not same_word("refund", "refunded")


def test_contains_phrase_whole_words_in_order():
    tokens = tokenize("Enter your tracking number on the website")
    assert contains_phrase(tokens, "Tracking Number")
    assert not contains_phrase(tokens, "number tracking")
    assert not contains_phrase(tokens, "track")


def test_contains_phrase_empty_phrase_is_false():
    assert not contains_phrase(tokenize("anything"), "  !! ")
