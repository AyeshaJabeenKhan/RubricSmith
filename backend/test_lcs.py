import random

import pytest

from lcs import lcs_indices, lcs_length, lcs_table, lcs_tokens


def words(text):
    return text.split()


def brute_force_lcs(a, b):
    """Slow but obviously correct: try every subsequence of the shorter list."""
    from itertools import combinations

    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    for size in range(len(short), 0, -1):
        for combo in combinations(short, size):
            it = iter(long_)
            if all(word in it for word in combo):
                return size
    return 0


@pytest.mark.parametrize("a, b, expected", [
    ("the cat sat on the mat", "the cat is on a mat", 4),
    ("a b c d", "a b c d", 4),
    ("a b c", "x y z", 0),
    ("a b c", "c b a", 1),
    ("", "a b", 0),
    ("a", "", 0),
])
def test_lcs_length_known_cases(a, b, expected):
    assert lcs_length(words(a), words(b)) == expected


def test_lcs_tokens_keep_order():
    assert lcs_tokens(words("the cat sat on the mat"), words("the cat is on a mat")) == ["the", "cat", "on", "mat"]


def test_indices_point_to_matching_words():
    a, b = words("please open my orders page"), words("open the my orders tab")
    a_idx, b_idx = lcs_indices(a, b)
    assert [a[i] for i in a_idx] == [b[j] for j in b_idx] == ["open", "my", "orders"]


def test_table_corner_equals_length():
    a, b = words("x a b y c"), words("a q b c")
    assert lcs_table(a, b)[-1][-1] == lcs_length(a, b) == 3


def test_length_is_symmetric():
    a, b = words("one two three four"), words("two four one")
    assert lcs_length(a, b) == lcs_length(b, a)


def test_matches_brute_force_on_random_inputs():
    rng = random.Random(7)
    vocab = list("abcde")
    for _ in range(200):
        a = [rng.choice(vocab) for _ in range(rng.randint(0, 7))]
        b = [rng.choice(vocab) for _ in range(rng.randint(0, 7))]
        expected = brute_force_lcs(a, b)
        assert lcs_length(a, b) == expected
        assert len(lcs_tokens(a, b)) == expected
