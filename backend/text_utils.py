"""
Small text helpers shared by all metrics.

Every metric compares text the same way: lowercase, no punctuation,
single spaces. Keeping this in one place means "Paris." and "paris"
are treated as equal everywhere, not just in one metric.
"""

import re
import unicodedata

_PUNCT_RE = re.compile(r"[^\w\s]")
_SPACE_RE = re.compile(r"\s+")

# Words that carry little meaning. Removed only where a metric asks for it.
STOPWORDS = frozenset(
    "a an the is are was were be been of to in on at for and or but with "
    "it this that these those as by from your you i we they".split()
)


def normalize(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse spaces."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _PUNCT_RE.sub(" ", text.lower())
    return _SPACE_RE.sub(" ", text).strip()


def tokenize(text: str, drop_stopwords: bool = False) -> list[str]:
    """Split text into normalized word tokens."""
    tokens = normalize(text).split()
    if drop_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens


def same_word(a: str, b: str) -> bool:
    """
    Equal, or equal apart from a plural ending ("refund" / "refunds", "box" / "boxes").

    This is not full stemming on purpose. "refund" should not match
    "refunded", because in a support answer that can change the meaning.
    """
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return long_ in (short + "s", short + "es")


def contains_phrase(text_tokens: list[str], phrase: str) -> bool:
    """
    True if the phrase appears in the tokens as whole words.

    "refund" matches "a refund" and "refunds", but not "refunded".
    Multi-word phrases like "tracking number" must appear in order.
    """
    phrase_tokens = tokenize(phrase)
    if not phrase_tokens:
        return False

    size = len(phrase_tokens)
    for i in range(len(text_tokens) - size + 1):
        window = text_tokens[i:i + size]
        if all(same_word(x, y) for x, y in zip(window, phrase_tokens)):
            return True
    return False
