"""
Bigram Similarity using Dice's Coefficient

Dice's Coefficient: 2 * |bigrams(s1) ∩ bigrams(s2)| / (|bigrams(s1)| + |bigrams(s2)|)
"""

from typing import Set, List


def get_bigrams(text: str) -> Set[str]:
    """
    Extract character bigrams from a string.

    Args:
        text: Input string

    Returns:
        Set of bigrams

    Example:
        >>> get_bigrams("hello")
        {'he', 'el', 'll', 'lo'}
    """
    text = text.lower().strip()
    if len(text) < 2:
        return set()
    return {text[i : i + 2] for i in range(len(text) - 1)}


def dice_coefficient(text1: str, text2: str) -> float:
    """
    Calculate Dice's coefficient between two strings based on their bigrams.

    Dice's Coefficient = 2 * |intersection| / (|bigrams1| + |bigrams2|)

    Args:
        text1: First string
        text2: Second string

    Returns:
        Similarity score between 0.0 and 1.0

    Example:
        >>> dice_coefficient("night", "nacht")
        0.25
        >>> dice_coefficient("hello", "hello")
        1.0
    """
    bigrams1 = get_bigrams(text1)
    bigrams2 = get_bigrams(text2)

    # Edge cases
    if not bigrams1 and not bigrams2:
        return 1.0
    if not bigrams1 or not bigrams2:
        return 0.0

    intersection = bigrams1 & bigrams2
    total_bigrams = len(bigrams1) + len(bigrams2)

    if total_bigrams == 0:
        return 0.0

    return (2.0 * len(intersection)) / total_bigrams


def get_similarity_matrix(words: List[str]) -> List[List[float]]:
    """
    Compute pairwise bigram similarity matrix for a list of words.

    Args:
        words: List of drug names

    Returns:
        2D matrix of similarity scores
    """
    n = len(words)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 1.0
            else:
                matrix[i][j] = dice_coefficient(words[i], words[j])

    return matrix


def bigram_similarity(word1: str, word2: str) -> float:
    """
    Convenience function for computing bigram similarity.
    Alias for dice_coefficient.

    Args:
        word1: First word
        word2: Second word

    Returns:
        Dice coefficient similarity (0.0 to 1.0)
    """
    return dice_coefficient(word1, word2)
