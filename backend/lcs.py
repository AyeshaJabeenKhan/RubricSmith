"""
Longest Common Subsequence (LCS) with dynamic programming.

A subsequence keeps the order of words but can skip words.
For "the cat sat on the mat" and "the cat is on a mat",
the LCS is "the cat on mat" (4 words).

ROUGE-L uses the LCS length to measure how much of the reference
answer shows up, in order, in the model's answer.

Two versions are here:
  - lcs_length: only the length, using two rows of memory, O(n*m) time, O(m) space
  - lcs_tokens: the actual words, using the full table so we can walk back
"""


def lcs_length(a: list[str], b: list[str]) -> int:
    """Length of the LCS. Keeps only two rows of the DP table."""
    if not a or not b:
        return 0

    # Make b the shorter list so the rows are as small as possible.
    if len(b) > len(a):
        a, b = b, a

    previous = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        current = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                current[j] = previous[j - 1] + 1
            else:
                current[j] = max(previous[j], current[j - 1])
        previous = current

    return previous[-1]


def lcs_table(a: list[str], b: list[str]) -> list[list[int]]:
    """
    Full DP table. table[i][j] = LCS length of a[:i] and b[:j].

    Rule for each cell:
      - words match:  diagonal + 1
      - otherwise:    the bigger of the cell above and the cell to the left
    """
    table = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                table[i][j] = table[i - 1][j - 1] + 1
            else:
                table[i][j] = max(table[i - 1][j], table[i][j - 1])
    return table


def lcs_indices(a: list[str], b: list[str]) -> tuple[list[int], list[int]]:
    """
    Walk back through the table to find which positions are in the LCS.

    Returns the matched indexes in a and in b. The dashboard uses the
    indexes in the answer to highlight matched words.
    """
    table = lcs_table(a, b)
    i, j = len(a), len(b)
    a_idx: list[int] = []
    b_idx: list[int] = []

    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            a_idx.append(i - 1)
            b_idx.append(j - 1)
            i -= 1
            j -= 1
        elif table[i - 1][j] >= table[i][j - 1]:
            i -= 1
        else:
            j -= 1

    return a_idx[::-1], b_idx[::-1]


def lcs_tokens(a: list[str], b: list[str]) -> list[str]:
    """The LCS words themselves, in order."""
    a_idx, _ = lcs_indices(a, b)
    return [a[i] for i in a_idx]
