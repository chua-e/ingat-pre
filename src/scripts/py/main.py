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

sys.path.insert(0, str(Path(__file__).parent / "src"))

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


def compute_stats(values: np.ndarray) -> dict:
    """
    Compute descriptive statistics for an array of values.

    Args:
        values: NumPy array of numeric values

    Returns:
        Dictionary with mean, std, min, max, and median
    """
    return {
        "mean": np.mean(values),
        "std": np.std(values),
        "min": np.min(values),
        "max": np.max(values),
        "median": np.median(values),
    }


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
    word_data: list[WordData], g2p: TagalogG2P
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
    for i in range(len(word_data)):
        for j in range(i + 1, len(word_data)):
            w1, w2 = word_data[i], word_data[j]

            eng_bigram = dice_coefficient(w1.original, w2.original)
            nat_bigram = dice_coefficient(w1.nativized, w2.nativized)
            fil_sim, _ = phonetic_similarity(w1.nativized, w2.nativized, g2p)
            direct_sim, _ = phonetic_similarity(
                w1.original.lower(), w2.original.lower(), g2p
            )
            eng_sim = compute_english_similarity(
                list(w1.english_ipa), list(w2.english_ipa)
            )

            pairs.append(
                PairSimilarity(
                    w1, w2, eng_sim, direct_sim, fil_sim, eng_bigram, nat_bigram
                )
            )

    pairs.sort(key=lambda x: x.filipino_sim, reverse=True)
    return pairs


def write_stats_section(f, name: str, stats: dict):
    """
    Write a formatted statistics section to a file.

    Args:
        f: File handle to write to
        name: Label for the statistics section
        stats: Dictionary with mean, std, min, max, median keys
    """
    f.write(f"{name}:\n")
    f.write(f"  Mean:      {stats['mean']:.4f}\n")
    f.write(f"  Std Dev:   {stats['std']:.4f}\n")
    f.write(f"  Min:       {stats['min']:.4f}\n")
    f.write(f"  Max:       {stats['max']:.4f}\n")
    f.write(f"  Median:    {stats['median']:.4f}\n\n")


def write_pair_details(f, pair: PairSimilarity):
    """
    Write detailed comparison for a single word pair to a file.

    Outputs phonetic transcriptions and all similarity metrics in a
    tree-structured format for easy reading.

    Args:
        f: File handle to write to
        pair: PairSimilarity object containing the comparison data
    """
    w1, w2 = pair.word1, pair.word2
    f.write(f"\n{w1.original} ↔ {w2.original}\n")
    f.write(f"  English G2P:        /{w1.english_ipa}/ ↔ /{w2.english_ipa}/\n")
    f.write(f"  Direct Tagalog G2P: /{w1.direct_ipa}/ ↔ /{w2.direct_ipa}/\n")
    f.write(f"  Nativized:          {w1.nativized} ↔ {w2.nativized}\n")
    f.write(f"  Nativized IPA:      /{w1.tagalog_ipa}/ ↔ /{w2.tagalog_ipa}/\n")
    f.write(f"  ├─ Phonetic Similarities:\n")
    f.write(f"  │  ├─ English G2P:     {pair.english_sim:.3f}\n")
    f.write(f"  │  ├─ Direct Tagalog:  {pair.direct_sim:.3f}\n")
    f.write(f"  │  └─ Nativized:       {pair.filipino_sim:.3f}\n")
    f.write(f"  └─ Bigram Similarities (Dice):\n")
    f.write(f"     ├─ English:         {pair.english_bigram:.3f}\n")
    f.write(f"     └─ Nativized:       {pair.nativized_bigram:.3f}\n")


def write_similarity_report(
    filepath: Path,
    words: list[str],
    word_data: list[WordData],
    pairs: list[PairSimilarity],
    g2p: TagalogG2P,
) -> dict:
    """
    Generate and write a comprehensive similarity report to a file.

    The report includes:
        - Statistical summaries for each similarity metric
        - Detailed pairwise comparisons sorted by Filipino similarity

    Args:
        filepath: Output file path
        words: Original word list
        word_data: Processed WordData objects
        pairs: Computed PairSimilarity objects
        g2p: TagalogG2P instance (unused, kept for API consistency)

    Returns:
        Dictionary of statistics for each metric type
    """
    eng_stats = compute_stats(np.array([p.english_sim for p in pairs]))
    direct_stats = compute_stats(np.array([p.direct_sim for p in pairs]))
    fil_stats = compute_stats(np.array([p.filipino_sim for p in pairs]))
    eng_bigram_stats = compute_stats(np.array([p.english_bigram for p in pairs]))
    nat_bigram_stats = compute_stats(np.array([p.nativized_bigram for p in pairs]))

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Pairwise Similarities (sorted by highest similarity)\n\n\n\n")
        f.write("\n## PHONETIC SIMILARITY STATISTICS\n\n")

        write_stats_section(f, "English G2P (eng-to-ipa)", eng_stats)
        write_stats_section(
            f,
            "Direct Tagalog G2P (English → Tagalog G2P, no nativization)",
            direct_stats,
        )
        write_stats_section(
            f, "Nativized Tagalog G2P (English → Nativize → Tagalog G2P)", fil_stats
        )

        f.write("## BIGRAM SIMILARITY (Dice's Coefficient)\n\n")
        write_stats_section(f, "English Bigrams", eng_bigram_stats)
        write_stats_section(f, "Nativized Bigrams", nat_bigram_stats)

        f.write("## PAIRWISE SIMILARITIES (sorted by Filipino similarity)\n")
        for pair in pairs:
            write_pair_details(f, pair)

    return {
        "eng": eng_stats,
        "direct": direct_stats,
        "fil": fil_stats,
        "eng_bigram": eng_bigram_stats,
        "nat_bigram": nat_bigram_stats,
    }


def run_pipeline(input_file: str):
    """
    Execute the complete LASA detection pipeline.

    Reads drug names from a file and processes them through:
        1. Filipino nativization
        2. G2P phonetic transcription (English and Tagalog)
        3. Pairwise similarity analysis

    Outputs three files to the 'res/' directory:
        - {basename}_nativized.txt: Original and nativized forms
        - {basename}_g2p.txt: Phonetic transcriptions
        - {basename}_similarity.txt: Full similarity report

    Args:
        input_file: Path to text file with drug names (one per line)
    """
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    res_dir = Path("res")
    res_dir.mkdir(exist_ok=True)
    base_name = input_path.stem

    print(f"Reading input from: {input_file}")
    with open(input_path, "r", encoding="utf-8") as f:
        words = [line.strip() for line in f if line.strip()]
    print(f"Processing {len(words)} words...\n")

    nativizer = FilipinoNativizer()
    g2p = TagalogG2P()

    print("# 1: Processing words (Nativization + G2P)")
    word_data = process_words(words, nativizer, g2p)

    nativized_file = res_dir / f"{base_name}_nativized.txt"
    with open(nativized_file, "w", encoding="utf-8") as f:
        for wd in word_data:
            f.write(f"{wd.original}\t{wd.nativized}\n")
    print(f"DONE: Nativized {len(words)} words → {nativized_file}")

    g2p_file = res_dir / f"{base_name}_g2p.txt"
    with open(g2p_file, "w", encoding="utf-8") as f:
        for wd in word_data:
            f.write(f"{wd.original}\t{wd.nativized}\t/{wd.tagalog_ipa}/\n")
    print(f"DONE: G2P transcriptions → {g2p_file}\n")

    print("# 2: Computing pairwise similarities")
    pairs = compute_pairwise_similarities(word_data, g2p)

    similarity_file = res_dir / f"{base_name}_similarity.txt"
    stats = write_similarity_report(similarity_file, words, word_data, pairs, g2p)

    print(f"DONE: Computed {len(pairs)} pairwise similarities")
    print(
        f" - English G2P:    μ={stats['eng']['mean']:.3f}, σ={stats['eng']['std']:.3f}"
    )
    print(
        f" - Direct Tagalog: μ={stats['direct']['mean']:.3f}, σ={stats['direct']['std']:.3f}"
    )
    print(
        f" - Nativized:      μ={stats['fil']['mean']:.3f}, σ={stats['fil']['std']:.3f}"
    )
    print(
        f" - Eng Bigram:     μ={stats['eng_bigram']['mean']:.3f}, σ={stats['eng_bigram']['std']:.3f}"
    )
    print(
        f" - Nat Bigram:     μ={stats['nat_bigram']['mean']:.3f}, σ={stats['nat_bigram']['std']:.3f}"
    )
    print(f"Output: {similarity_file}\n")

    print("# PIPELINE COMPLETED SUCCESSFULLY")
    print(f"\nOutputs saved to: {res_dir}/")
    print(f"  1. {nativized_file.name}")
    print(f"  2. {g2p_file.name}")
    print(f"  3. {similarity_file.name}")


def main():
    """Entry point for the CLI. Parses arguments and runs the pipeline."""
    parser = argparse.ArgumentParser(
        description="Filipino Drug Name Pipeline: Nativization -> G2P -> ALINE Similarity"
    )
    parser.add_argument(
        "input_file", help="Input text file with drug names (one per line)"
    )
    args = parser.parse_args()
    run_pipeline(args.input_file)


if __name__ == "__main__":
    main()
