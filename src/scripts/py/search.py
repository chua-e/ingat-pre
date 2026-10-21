import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "algos"))

from bisim import dice_coefficient
from english_g2p import clean_for_aline, english_to_ipa
from nltk.metrics.aline import align, delta
from tagalog_g2p import TagalogG2P


@dataclass
class WordData:
    original: str
    english_ipa: str
    tagalog_ipa: str


@dataclass
class PairSimilarity:
    word1: WordData
    word2: WordData
    english_sim: float
    filipino_sim: float
    english_bigram: float
    weighted_avg: float


def compute_ipa_similarity(phones1: list[str], phones2: list[str]) -> float:
    if not phones1 or not phones2:
        return 0.0

    try:
        alignments = align(phones1, phones2)
    except ValueError:
        return 0.0
    if not alignments or not alignments[0]:
        return 0.0

    total_delta = 0.0
    valid_pairs = 0
    for pair in alignments[0]:
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            phone1, phone2 = str(pair[0]), str(pair[1])
            if phone1 == "-" or phone2 == "-":
                total_delta += 115
            else:
                try:
                    total_delta += delta(phone1, phone2)
                except (KeyError, TypeError):
                    total_delta += 115
            valid_pairs += 1

    if not valid_pairs:
        return 0.0
    score = 1.0 - total_delta / (valid_pairs * 115)
    return max(0.0, min(1.0, score))


def compute_pairwise_similarities(
    query: WordData, candidates: list[WordData]
) -> list[PairSimilarity]:
    pairs = []
    for candidate in candidates:
        english_bigram = dice_coefficient(query.original, candidate.original)
        english_sim = compute_ipa_similarity(
            list(query.english_ipa), list(candidate.english_ipa)
        )
        filipino_sim = compute_ipa_similarity(
            list(query.tagalog_ipa), list(candidate.tagalog_ipa)
        )
        weighted_avg = (english_bigram + english_sim + filipino_sim) / 3
        pairs.append(
            PairSimilarity(
                word1=query,
                word2=candidate,
                english_sim=english_sim,
                filipino_sim=filipino_sim,
                english_bigram=english_bigram,
                weighted_avg=weighted_avg,
            )
        )
    return pairs


def prepare_candidates(
    rows: list[dict[str, str]],
) -> list[tuple[dict[str, str], WordData]]:
    prepared = []
    for row in rows:
        name = row.get("name", "").strip()
        english_ipa = row.get("eng_ipa", "").strip()
        tagalog_ipa = row.get("fil_ipa", "").strip()
        if name and english_ipa and tagalog_ipa:
            prepared.append(
                (
                    row,
                    WordData(
                        original=name,
                        english_ipa=clean_for_aline(english_ipa),
                        tagalog_ipa=tagalog_ipa,
                    ),
                )
            )
    return prepared


def search_drugs(
    query: str,
    prepared_candidates: list[tuple[dict[str, str], WordData]],
    g2p: TagalogG2P,
) -> list[dict[str, object]]:
    """Rank candidates using the existing combined phonetic and spelling score."""
    query = query.strip()
    if not query:
        raise ValueError("Query must not be empty.")

    query_data = WordData(
        original=query,
        english_ipa=clean_for_aline(english_to_ipa(query.lower())),
        tagalog_ipa=g2p.convert_word(query.lower()),
    )
    pairs = compute_pairwise_similarities(
        query_data,
        [candidate for _, candidate in prepared_candidates],
    )
    ranked = sorted(
        zip(pairs, prepared_candidates),
        key=lambda item: item[0].weighted_avg,
        reverse=True,
    )[:20]

    return [
        {
            "name": drug["name"],
            "type": drug.get("type", ""),
            "source": drug.get("source", "Pretranscribed dataset"),
            "score": round(float(pair.weighted_avg) * 100, 2),
            "components": {
                "english": round(float(pair.english_sim) * 100, 2),
                "filipino": round(float(pair.filipino_sim) * 100, 2),
                "english_bigram": round(float(pair.english_bigram) * 100, 2),
            },
        }
        for pair, (drug, _) in ranked
    ]

def normalize_name(name: str) -> str:
    return "".join(character for character in name.casefold() if character.isalnum())

def levenshtein_distance(first: str, second: str) -> int:
    if len(first) < len(second):
        first, second = second, first

    previous = list(range(len(second) + 1))
    for row, first_char in enumerate(first, start=1):
        current = [row]
        for column, second_char in enumerate(second, start=1):
            current.append(
                min(
                    current[column - 1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (first_char != second_char),
                )
            )
        previous = current
    return previous[-1]


def lev_search(
    query: str,
    prepared_candidates: list[tuple[dict[str, str], WordData]],
) -> list[dict[str, object]]:
    normalized_query = normalize_name(query.strip())
    if not normalized_query:
        raise ValueError("Query must contain at least one letter or number.")

    ranked = []
    for drug, candidate in prepared_candidates:
        distance = levenshtein_distance(
            normalized_query, normalize_name(candidate.original)
        )
        max_len = max(len(normalized_query), len(normalize_name(candidate.original)))
        score = 1.0 - (distance / max_len)
        ranked.append((score, candidate.original.casefold(), drug))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    return [
        {
            "name": drug["name"],
            "type": drug.get("type", ""),
            "source": drug.get("source", "Philippine FDA"),
            "score": round(score * 100, 2),
        }
        for score, _, drug in ranked[:20]
    ]
