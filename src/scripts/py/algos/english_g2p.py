"""
English G2P using eng_to_ipa library
"""

import eng_to_ipa as ipa
from nltk.metrics.aline import feature_matrix
from typing import Optional


def english_to_ipa(word: str) -> str:
    """
    Convert English word to IPA phonetic transcription.

    Args:
        word: English word

    Returns:
        IPA transcription (or original if conversion fails)
    """
    try:
        result = ipa.convert(word)

        return result if result else word
    except Exception:
        return word


def clean_for_aline(ipa_string: str) -> str:
    """
    Clean IPA string to be compatible with ALINE algorithm.
    Remove stress marks, syllable boundaries, and other markers.

    Args:
        ipa_string: IPA transcription string

    Returns:
        Cleaned IPA string with only phoneme symbols
    """
    chars_to_remove = {
        "ˈ",  # Primary stress
        "ˌ",  # Secondary stress
        ".",  # Syllable boundary
        "-",  # Morpheme boundary
        " ",  # Spaces
        "*",  # Asterisk (used in some transcriptions)
    }

    cleaned = "".join(c for c in ipa_string if c not in chars_to_remove)
    return to_aline_segments(cleaned)


# NLTK's ALINE feature matrix has no ɪ, ɚ or length mark, and align() raises
# ValueError on any unknown segment, which made most rows score 0.
# ALINE writes long vowels as capitals (I = iː, E = eː, ...).
_LONG_VOWELS = {"i": "I", "e": "E", "u": "U", "o": "O", "a": "A"}
_SEGMENT_MAP = {
    "ɪ": "i",
    "ɚ": "əɹ",
    "ɝ": "ɜɹ",
    "ʧ": "tʃ",
    "ʤ": "dʒ",
    "ɫ": "l",
    "ᵻ": "ɨ",
}


def to_aline_segments(ipa_string: str) -> str:
    """Rewrite an IPA string so every character is a segment ALINE knows."""
    out: list[str] = []
    for char in ipa_string:
        if char == "ː":
            if out and out[-1] in _LONG_VOWELS:
                out[-1] = _LONG_VOWELS[out[-1]]
            continue
        for segment in _SEGMENT_MAP.get(char, char):
            if segment in feature_matrix:
                out.append(segment)
            # Anything else (diacritics, stray symbols) is dropped.
    return "".join(out)
