import functools
import heapq
import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "algos"))

from bisim import get_bigrams
from english_g2p import clean_for_aline, english_to_ipa
from tagalog_g2p import TagalogG2P

# NLTK's align() spends most of its time recomputing feature distances for the
# same phoneme pairs. They only depend on the segments, so memoize them.
# align() looks these up as module globals, so patching the module is enough.
# Inputs must be str (not list) so the 2-segment slices passed to sigma_exp are
# hashable.
_aline = importlib.import_module("nltk.metrics.aline")
for _name in ("sigma_skip", "sigma_sub", "sigma_exp", "delta"):
    _fn = getattr(_aline, _name)
    if not hasattr(_fn, "cache_info"):
        setattr(_aline, _name, functools.lru_cache(maxsize=None)(_fn))
align = _aline.align

# Only the best-looking candidates by cheap bigram scores go through ALINE.
# Taken separately on spelling and on IPA so sound-alikes spelled differently
# still get a chance. Set to None to run ALINE on every row.
PREFILTER_SIZE: int | None = 500
RESULT_LIMIT = 20


@dataclass
class WordData:
    original: str
    english_ipa: str
    # tagalog_ipa: str
    name_bigrams: frozenset[str] = field(init=False, repr=False, compare=False)
    ipa_bigrams: frozenset[str] = field(init=False, repr=False, compare=False)
    normalized: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.name_bigrams = frozenset(get_bigrams(self.original))
        self.ipa_bigrams = frozenset(get_bigrams(self.english_ipa))
        self.normalized = normalize_name(self.original)


def dice(bigrams1: frozenset[str], bigrams2: frozenset[str]) -> float:
    """Same result as bisim.dice_coefficient, on precomputed bigram sets."""
    if not bigrams1 and not bigrams2:
        return 1.0
    if not bigrams1 or not bigrams2:
        return 0.0
    return 2.0 * len(bigrams1 & bigrams2) / (len(bigrams1) + len(bigrams2))


@dataclass
class PairSimilarity:
    word1: WordData
    word2: WordData
    english_sim: float
    # filipino_sim: float
    english_bigram: float
    weighted_avg: float


def compute_ipa_similarity(phones1: str, phones2: str) -> float:
    # The memoized ALINE functions need hashable (str) input.
    if not isinstance(phones1, str):
        phones1 = "".join(phones1)
    if not isinstance(phones2, str):
        phones2 = "".join(phones2)
    if not phones1 or not phones2:
        return 0.0
    if phones1 == phones2:
        return 1.0

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
                    total_delta += _aline.delta(phone1, phone2)
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
        english_bigram = dice(query.name_bigrams, candidate.name_bigrams)
        english_sim = compute_ipa_similarity(query.english_ipa, candidate.english_ipa)
        # filipino_sim = compute_ipa_similarity(
        #     list(query.tagalog_ipa), list(candidate.tagalog_ipa)
        # )
        weighted_avg = (english_bigram + english_sim) / 2
        pairs.append(
            PairSimilarity(
                word1=query,
                word2=candidate,
                english_sim=english_sim,
                # filipino_sim=filipino_sim,
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
        # tagalog_ipa = row.get("fil_ipa", "").strip()
        if name and english_ipa:
            prepared.append(
                (
                    row,
                    WordData(
                        original=name,
                        english_ipa=clean_for_aline(english_ipa),
                        # tagalog_ipa=tagalog_ipa,
                    ),
                )
            )
    return prepared


def shortlist_candidates(
    query: WordData,
    prepared_candidates: list[tuple[dict[str, str], WordData]],
    size: int | None,
) -> list[tuple[dict[str, str], WordData]]:
    """Top `size` rows by spelling bigrams plus top `size` by IPA bigrams.

    Keeps the original row order so ties rank the same as a full scan.
    """
    if size is None or len(prepared_candidates) <= 2 * size:
        return prepared_candidates
    indices = range(len(prepared_candidates))
    by_name = heapq.nlargest(
        size,
        indices,
        key=lambda i: dice(query.name_bigrams, prepared_candidates[i][1].name_bigrams),
    )
    by_ipa = heapq.nlargest(
        size,
        indices,
        key=lambda i: dice(query.ipa_bigrams, prepared_candidates[i][1].ipa_bigrams),
    )
    return [prepared_candidates[i] for i in sorted(set(by_name) | set(by_ipa))]


def search_drugs(
    query: str,
    prepared_candidates: list[tuple[dict[str, str], WordData]],
) -> list[dict[str, object]]:
    """Rank candidates using the existing combined phonetic and spelling score."""
    query = query.strip()
    if not query:
        raise ValueError("Query must not be empty.")

    normalized_query = normalize_name(query)
    exact_candidate = next(
        (
            candidate
            for _, candidate in prepared_candidates
            if candidate.normalized == normalized_query
        ),
        None,
    )
    query_data = exact_candidate or WordData(
        original=query,
        english_ipa=clean_for_aline(english_to_ipa(query.lower())),
    )
    shortlist = shortlist_candidates(query_data, prepared_candidates, PREFILTER_SIZE)
    pairs = compute_pairwise_similarities(
        query_data,
        [candidate for _, candidate in shortlist],
    )
    ranked = sorted(
        zip(pairs, shortlist),
        key=lambda item: item[0].weighted_avg,
        reverse=True,
    )[:RESULT_LIMIT]

    return [
        {
            "name": drug["name"],
            "type": drug.get("type", ""),
            "source": drug.get("source", "Philippine FDA"),
            "score": round(float(pair.weighted_avg) * 100, 2),
            "components": {
                "english": round(float(pair.english_sim) * 100, 2),
                # "filipino": round(float(pair.filipino_sim) * 100, 2),
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
