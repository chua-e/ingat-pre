"""
PoCA - Phonetic and Orthographic Computer Analysis for Philippine Drugs

A pipeline for detecting Look-Alike Sound-Alike (LASA) drug names using
Filipino phonetic nativization and multiple similarity metrics.

Pipeline stages:
    1. Filipino Nativization - Adapts English drug names to Filipino orthography
    2. G2P Conversion - Converts text to IPA phonetic transcriptions
    3. Similarity Analysis - Computes phonetic and orthographic similarities

Usage:
    python main.py <input_file>

Example:
    python main.py data/group1.txt
"""

import sys
import argparse
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent / "algos"))

import numpy as np
from legacy_tagabaybay import FilipinoNativizer
from tagalog_g2p import TagalogG2P
from aline import phonetic_similarity
from english_g2p import english_to_ipa, clean_for_aline
from bisim import dice_coefficient
from nltk.metrics.aline import align, delta


@dataclass
class WordData:
    """
    Container for all phonetic representations of a single word.

    Attributes:
        original: The original input word (e.g., "Aspirin")
        nativized: Filipino-adapted spelling (e.g., "Aspirin" -> "Aspirin")
        english_ipa: English IPA transcription via eng-to-ipa
        tagalog_ipa: Tagalog IPA transcription of the nativized form
        direct_ipa: Tagalog IPA transcription of the original (no nativization)
    """

    original: str
    nativized: str
    english_ipa: str
    tagalog_ipa: str
    direct_ipa: str


@dataclass
class PairSimilarity:
    """
    Container for similarity metrics between two words.

    Attributes:
        word1: First word's phonetic data
        word2: Second word's phonetic data
        english_sim: ALINE similarity using English IPA
        direct_sim: ALINE similarity using direct Tagalog G2P (no nativization)
        filipino_sim: ALINE similarity using nativized Tagalog G2P
        english_bigram: Dice coefficient on original English spellings
        nativized_bigram: Dice coefficient on nativized spellings
    """

    word1: WordData
    word2: WordData
    english_sim: float
    direct_sim: float
    filipino_sim: float
    english_bigram: float
    nativized_bigram: float
    weighted_avg: float


def compute_english_similarity(phones1: list, phones2: list) -> float:
    """
    Compute phonetic similarity between two English IPA transcriptions using ALINE.

    Uses the ALINE algorithm (Kondrak 2000) to align phonetic segments and
    compute a normalized similarity score based on phonetic feature differences.

    Args:
        phones1: List of IPA characters for the first word
        phones2: List of IPA characters for the second word

    Returns:
        Similarity score between 0.0 (completely different) and 1.0 (identical)
    """
    if not phones1 or not phones2:
        return 0.0
    try:
        alignments = align(phones1, phones2)
        if not alignments or not alignments[0]:
            return 0.0

        total_delta = 0.0
        valid_pairs = 0
        for pair in alignments[0]:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                p1, p2 = str(pair[0]), str(pair[1])
                if p1 == "-" or p2 == "-":
                    total_delta += 115
                else:
                    try:
                        total_delta += delta(p1, p2)
                    except (KeyError, TypeError):
                        total_delta += 115
                valid_pairs += 1

        if valid_pairs == 0:
            return 0.0
        sim = 1.0 - (total_delta / (valid_pairs * 115))
        return max(0.0, min(1.0, sim))
    except Exception:
        return 0.0


def process_words(
    words: list[str], nativizer: FilipinoNativizer, g2p: TagalogG2P
) -> list[WordData]:
    """
    Process a list of words through nativization and G2P conversion.

    For each word, generates:
        - Filipino nativized form
        - English IPA transcription
        - Tagalog IPA from nativized form
        - Direct Tagalog IPA (without nativization)

    Args:
        words: List of input words (typically drug names)
        nativizer: FilipinoNativizer instance for orthographic adaptation
        g2p: TagalogG2P instance for phonetic transcription

    Returns:
        List of WordData objects containing all phonetic representations
    """
    result = []
    for word in words:
        nativized = nativizer.nativize(word)
        english_ipa = clean_for_aline(english_to_ipa(word.lower()))
        tagalog_ipa = g2p.convert_word(nativized)
        direct_ipa = g2p.convert_word(word.lower())
        result.append(WordData(word, nativized, english_ipa, tagalog_ipa, direct_ipa))
    return result


def compute_pairwise_similarities(
    candidates: list[WordData], g2p: TagalogG2P, query: WordData
) -> list[PairSimilarity]:
    """
    Compute all pairwise similarity metrics between words.

    For each unique pair, computes:
        - English G2P phonetic similarity (ALINE)
        - Direct Tagalog G2P similarity (ALINE)
        - Nativized Filipino similarity (ALINE)
        - English bigram similarity (Dice coefficient)
        - Nativized bigram similarity (Dice coefficient)

    Args:
        word_data: List of WordData objects from process_words()
        g2p: TagalogG2P instance for similarity computation

    Returns:
        List of PairSimilarity objects, sorted by Filipino similarity (descending)
    """
    pairs = []
    
    for candidate in candidates:
        eng_bigram = dice_coefficient(query.original, candidate.original)
        nat_bigram = dice_coefficient(query.nativized, candidate.nativized)

        fil_sim, _ = phonetic_similarity(query.nativized, candidate.nativized, g2p)
        direct_sim, _ = phonetic_similarity(
            query.original.lower(), candidate.original.lower(), g2p
        )
        eng_sim = compute_english_similarity(
            list(query.english_ipa), list(candidate.english_ipa)
        )

        weighted_sim = (eng_bigram + direct_sim + fil_sim + eng_sim)/4

        pairs.append(
            PairSimilarity(
                query, candidate, eng_sim, direct_sim, fil_sim, eng_bigram, nat_bigram, weighted_sim
            )
        )

    pairs.sort(key=lambda x: x.filipino_sim, reverse=True)
    return pairs

def search_drugs(query: str, drugs: list[dict[str, str]], 
                 nativizer: FilipinoNativizer, g2p: TagalogG2P) -> list[dict[str, object]]:
    query = query.strip()
    if not query:
        raise ValueError("Query empty.")

    records = [
        row for row in drugs
            if row.get("Drugs", "").strip()
    ]

    candidate_names = [row["Drugs"].strip() for row in records]

    query_data = process_words([query], nativizer, g2p)[0]
    candidates = process_words(candidate_names, nativizer, g2p)
    pairs = compute_pairwise_similarities(query_data, candidates, g2p)

    ranked = sorted(
        zip(pairs, records),
        key=lambda item: item[0].weighted_avg,
        reverse=True,
    )[:50]

    return [
        {
            "name": record["Drugs"],
            "type": record.get("Drug_Type", ""),
            "source": "Philippine FDA",
            "score": round(pair.weighted_avg * 100, 2),
            "components": {
                "english": round(pair.english_sim * 100, 2),
                "direct": round(pair.direct_sim * 100, 2),
                "filipino": round(pair.filipino_sim * 100, 2),
                "english_bigram": round(pair.english_bigram * 100, 2),
                "nativized_bigram": round(pair.nativized_bigram * 100, 2),
            },
        }
        for pair, record in ranked
    ]
    
