import csv
import os
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PY_DIR = Path(__file__).parent
sys.path.insert(0, str(PY_DIR / "algos"))

from legacy_tagabaybay import nativize
from tagalog_g2p import TagalogG2P

PHOC_PATH = (
    Path(__file__).parents[3]
    / "vendor/pho/target/release"
    / ("phoc.exe" if os.name == "nt" else "phoc")
)
# phoc loads every .toml in this folder, so it must only hold the weights in use.
PHOC_CONFIG_DIR = PY_DIR / "phoc_configs"
ALINE_CONFIG = PHOC_CONFIG_DIR / "aline_cangu.toml"
# phoc names the score column after the config file.
ALINE_COLUMN = ALINE_CONFIG.stem
RESULT_LIMIT = 20

if not PHOC_PATH.exists():
    raise RuntimeError(
        f"phoc not found at {PHOC_PATH}. Build it from the repo root with: "
        "cargo build --release --bin phoc --manifest-path vendor/pho/Cargo.toml"
    )

# phoc fails the whole batch on a symbol missing from the config's inventory.
with ALINE_CONFIG.open("rb") as config_file:
    _ALLOWED_SYMBOLS = set("".join(tomllib.load(config_file)["sounds"])) | set("ː .")

_g2p = TagalogG2P()


def to_phoc_ipa(ipa: str) -> str:
    return "".join(symbol for symbol in ipa if symbol in _ALLOWED_SYMBOLS)


def query_to_fil_ipa(query: str) -> str:
    """Transcribe a typed name using the same conventions as the stored fil_ipa."""
    ipa = _g2p.convert_word(nativize(query.lower())).replace("ɛ", "e").replace("ʔ", "")
    if ipa[:1] in {"a", "e", "i", "o", "u"}:
        ipa = "ʔ" + ipa
    return to_phoc_ipa(ipa)


def normalize_name(name: str) -> str:
    return "".join(character for character in name.casefold() if character.isalnum())


@dataclass
class WordData:
    original: str
    filipino_ipa: str
    normalized: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.normalized = normalize_name(self.original)


def compute_aline_scores(query: WordData, candidates: list[WordData]) -> list[float]:
    """Score the query against each candidate with phoc, in candidate order."""
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir, "input.csv")
        output_path = Path(temp_dir, "output.csv")

        with input_path.open("w", newline="", encoding="utf-8") as input_file:
            writer = csv.writer(input_file)
            writer.writerow(["x_1", "x_2", "t_1", "t_2"])
            for candidate in candidates:
                writer.writerow(
                    [
                        query.original,
                        candidate.original,
                        query.filipino_ipa,
                        candidate.filipino_ipa,
                    ]
                )

        completed = subprocess.run(
            [
                PHOC_PATH,
                "csv",
                "--input",
                input_path,
                "--output",
                output_path,
                "--config-dir",
                PHOC_CONFIG_DIR,
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise RuntimeError(f"phoc failed: {completed.stderr.strip()}")

        with output_path.open(newline="", encoding="utf-8") as output_file:
            return [float(row[ALINE_COLUMN]) for row in csv.DictReader(output_file)]


def prepare_candidates(
    rows: list[dict[str, str]],
) -> list[tuple[dict[str, str], WordData]]:
    prepared = []
    for row in rows:
        name = (row.get("name") or "").strip()
        filipino_ipa = to_phoc_ipa((row.get("fil_ipa") or "").strip())
        if name and filipino_ipa:
            prepared.append((row, WordData(original=name, filipino_ipa=filipino_ipa)))
    return prepared


def search_drugs(
    query: str,
    prepared_candidates: list[tuple[dict[str, str], WordData]],
) -> list[dict[str, object]]:
    """Rank candidates by ALINE similarity on their Filipino transcriptions."""
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
        filipino_ipa=query_to_fil_ipa(query),
    )
    if not query_data.filipino_ipa:
        raise ValueError("Query must contain at least one letter.")

    scores = compute_aline_scores(
        query_data,
        [candidate for _, candidate in prepared_candidates],
    )
    ranked = sorted(
        zip(scores, prepared_candidates),
        key=lambda item: item[0],
        reverse=True,
    )[:RESULT_LIMIT]

    return [
        {
            "name": drug["name"],
            "type": drug.get("type", ""),
            "source": drug.get("source", "Philippine FDA"),
            "score": round(score * 100, 2),
            "components": {"filipino": round(score * 100, 2)},
        }
        for score, (drug, _) in ranked
    ]


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
