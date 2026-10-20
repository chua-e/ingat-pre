"""
English G2P using eng_to_ipa library
"""

import eng_to_ipa as ipa
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

    return "".join(c for c in ipa_string if c not in chars_to_remove)
