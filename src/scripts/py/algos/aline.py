"""
Phonetic similarity computation using NLTK's ALINE algorithm
"""

from typing import List, Tuple, Optional
from itertools import combinations
import numpy as np
from nltk.metrics.aline import align, delta
from tagalog_g2p import TagalogG2P


def phonetic_similarity(
    word1: str, word2: str, g2p: Optional[TagalogG2P] = None
) -> Tuple[float, List[Tuple[str, str]]]:
    """
    Compute the phonetic similarity between two Tagalog words using NLTK's ALINE algorithm.

    ALINE (Automatic Language-Independent Phonetic Aligner) computes similarity based on
    phonetic features such as manner, place of articulation, voicing, etc.

    Args:
        word1: First Tagalog word
        word2: Second Tagalog word
        g2p: Optional TagalogG2P instance (will create one if not provided)

    Returns:
        A tuple of (similarity_score, alignment) where alignment is a list of
        aligned phoneme pairs. Score is normalized to 0-1 range where 1 = identical.
    """
    if g2p is None:
        g2p = TagalogG2P()

    # Convert words to phonetic transcriptions
    # See: `tagalog_g2p.py`
    phones1_raw = g2p.convert_word(word1)
    phones2_raw = g2p.convert_word(word2)

    # Clean phonetic transcriptions - remove characters not in ALINE's feature matrix
    # Remove: syllable boundaries (.), and other special markers
    chars_to_remove = {".", "-", "_", "|", " "}
    phones1 = [p for p in phones1_raw if p not in chars_to_remove]
    phones2 = [p for p in phones2_raw if p not in chars_to_remove]

    if not phones1 or not phones2:
        return (0.0, [])

    alignments = align(phones1, phones2)

    if alignments and alignments[0]:
        alignment = alignments[0]  # Get best alignment

        # Calculate similarity score based on delta values
        # delta returns 0 for identical phones, higher values for more different phones
        # Skip gap markers ('-') and handle unknown phones
        total_delta = 0.0
        valid_pairs = 0

        for pair in alignment:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                p1, p2 = pair[0], pair[1]
            else:
                continue

            p1 = str(p1) if not isinstance(p1, str) else p1
            p2 = str(p2) if not isinstance(p2, str) else p2

            if p1 == "-" or p2 == "-":
                total_delta += 115
                valid_pairs += 1
                continue

            try:
                total_delta += delta(p1, p2)
                valid_pairs += 1
            except (KeyError, TypeError):
                if p1 == p2:
                    total_delta += 0
                else:
                    total_delta += 115  # High penalty for unknown phones (max delta)
                valid_pairs += 1

        # Convert to similarity (1 = identical, 0 = completely different)
        # Based on analysis: max delta between different phoneme classes is ~115
        # Typical deltas: identical=0, similar=5-25, different=25-50, very different=50-115
        if valid_pairs > 0:
            # Use 115 as max delta (vowel-consonant difference)
            max_possible_delta = valid_pairs * 115
            similarity = 1.0 - (total_delta / max_possible_delta)
            similarity = max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
        else:
            similarity = 0.0

        return (similarity, alignment)

    return (0.0, [])


def compute_pairwise_similarity(
    words: List[str],
) -> List[Tuple[str, str, float, List[Tuple[str, str]]]]:
    """
    Compute phonetic similarity for all pairs of words in a list.

    Args:
        words: A list of Tagalog words

    Returns:
        A list of tuples (word1, word2, similarity_score, alignment)
        sorted by similarity score in descending order
    """
    g2p = TagalogG2P()
    results = []

    for word1, word2 in combinations(words, 2):
        score, alignment = phonetic_similarity(word1, word2, g2p)
        results.append((word1, word2, score, alignment))

    results.sort(key=lambda x: x[2], reverse=True)
    return results


def get_similarity_matrix(words: List[str]) -> Tuple[List[str], List[List[float]]]:
    """
    Compute a similarity matrix for a list of words.

    Args:
        words: A list of Tagalog words

    Returns:
        A tuple of (words, matrix) where matrix[i][j] is the similarity
        between words[i] and words[j] (0 to 1 scale, 1 = identical)
    """
    g2p = TagalogG2P()
    n = len(words)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(i, n):
            if i == j:
                # Same word = perfect similarity
                matrix[i][j] = 1.0
            else:
                score, _ = phonetic_similarity(words[i], words[j], g2p)
                matrix[i][j] = score
                matrix[j][i] = score

    return words, matrix
