"""Ranks drugs with the CatBoost LASA classifier.

Each query is paired with every drug. `phoc` scores each pair twice, on the full
names and on their core words, and the classifier combines those scores into
the probability that the two names are look-alike/sound-alike.
"""

import csv
import os
import subprocess
import sys
import tempfile
import tomllib
import types
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

from filipino_ipa import nativize, transcribe_all
from names import clean_name, core_name

PY_DIR = Path(__file__).parent
ROOT_DIR = Path(__file__).parents[3]
PHOC_PATH = (
    ROOT_DIR / "vendor/pho/target/release" / ("phoc.exe" if os.name == "nt" else "phoc")
)
# phoc names each score column after its config file, as in walter's bin/pho_conf.
CONFIG_DIR = PY_DIR / "classifier_configs"
ALINE_COLUMN = "aline_kondrak"
MODEL_PATH = ROOT_DIR / "c9_catboost.joblib"
CACHE_PATH = PY_DIR / "data/classifier_cache.csv"
RESULT_LIMIT = 20

if not PHOC_PATH.exists():
    raise RuntimeError(
        f"phoc not found at {PHOC_PATH}. Build it from the repo root with: "
        "cargo build --release --bin phoc --manifest-path vendor/pho/Cargo.toml"
    )

with (CONFIG_DIR / f"{ALINE_COLUMN}.toml").open("rb") as config_file:
    # phoc fails the whole batch on a symbol missing from the config's inventory.
    # It ignores digits but rejects an empty transcription, so walter keeps them.
    _ALLOWED_SYMBOLS = set("".join(tomllib.load(config_file)["sounds"])) | set(
        "ː .0123456789"
    )


def _load_model():
    """Return the fitted CatBoost model from inside bowl's wrapper object."""
    # The .joblib references bowl's wrapper class, which isn't installed here.
    # Only the CatBoostClassifier it holds is needed.
    stand_ins = {
        name: types.ModuleType(name)
        for name in ("src", "src.models", "src.models.catboost")
    }
    stand_ins["src.models.catboost"].CatBoost = type("CatBoost", (), {})
    sys.modules.update(stand_ins)
    try:
        return joblib.load(MODEL_PATH)._model
    finally:
        for name in stand_ins:
            del sys.modules[name]


_model = _load_model()


def _phoc_column(feature: str) -> tuple[bool, str]:
    """Map a model feature to (scored on core words?, phoc column name)."""
    is_core = feature.startswith("core_")
    name = feature.removeprefix("core_")
    return is_core, ALINE_COLUMN if name.startswith("aline_var:") else name


FEATURES: list[str] = list(_model.feature_names_)
_FEATURE_COLUMNS = [_phoc_column(feature) for feature in FEATURES]


def _feature_group(feature: str) -> str:
    """Sort a feature into pho's look-alike and sound-alike algorithm families."""
    name = feature.removeprefix("core_")
    if "_separate_" in name:
        return "edit_counts"  # Counts, so not on the 0-1 scale of the similarities.
    if name.startswith("aline_var:") or name in ("bisim", "editex"):
        return "sound_alike"
    return "look_alike"


_GROUP_COLUMNS = {
    group: [
        column
        for column, feature in enumerate(FEATURES)
        if _feature_group(feature) == group
    ]
    for group in ("look_alike", "sound_alike", "edit_counts")
}


@dataclass
class Drug:
    name: str
    clean: str
    core: str
    nativized: str
    ipa: str
    core_ipa: str


def _to_phoc_ipa(ipa: str) -> str:
    return "".join(symbol for symbol in ipa if symbol in _ALLOWED_SYMBOLS)


def _prepare_all(names: list[str]) -> list[Drug]:
    cleans = [clean_name(name) for name in names]
    cores = [core_name(clean) for clean in cleans]
    nativized = [nativize(clean) for clean in cleans]
    ipas = transcribe_all(nativized)
    core_ipas = transcribe_all([nativize(core) for core in cores])
    return [
        Drug(name, clean, core, spelling, _to_phoc_ipa(ipa), _to_phoc_ipa(core_ipa))
        for name, clean, core, spelling, ipa, core_ipa in zip(
            names, cleans, cores, nativized, ipas, core_ipas
        )
    ]


def prepare_drugs(names: list[str]) -> list[Drug]:
    """Transcribe the drug list, reusing the cache when it covers the same names."""
    if CACHE_PATH.exists():
        with CACHE_PATH.open(newline="", encoding="utf-8") as cache_file:
            cached = [Drug(**row) for row in csv.DictReader(cache_file)]
        if [drug.name for drug in cached] == names:
            return cached

    drugs = _prepare_all(names)
    with CACHE_PATH.open("w", newline="", encoding="utf-8") as cache_file:
        writer = csv.DictWriter(cache_file, fieldnames=list(Drug.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(vars(drug) for drug in drugs)
    return drugs


def _run_phoc(
    query: tuple[str, str], candidates: list[tuple[str, str]]
) -> dict[str, np.ndarray]:
    """Score (name, ipa) against each candidate and return every phoc column."""
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir, "input.csv")
        output_path = Path(temp_dir, "output.csv")

        with input_path.open("w", newline="", encoding="utf-8") as input_file:
            writer = csv.writer(input_file)
            writer.writerow(["x_1", "x_2", "t_1", "t_2"])
            for name, ipa in candidates:
                writer.writerow([query[0], name, query[1], ipa])

        completed = subprocess.run(
            [
                PHOC_PATH,
                "csv",
                "--input",
                input_path,
                "--output",
                output_path,
                "--config-dir",
                CONFIG_DIR,
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise RuntimeError(f"phoc failed: {completed.stderr.strip()}")

        with output_path.open(newline="", encoding="utf-8") as output_file:
            rows = list(csv.DictReader(output_file))

    columns = {column for _, column in _FEATURE_COLUMNS}
    return {
        column: np.array([float(row[column]) for row in rows]) for column in columns
    }


def search_drugs(query: str, drugs: list[Drug]) -> list[dict[str, object]]:
    """Rank drugs by the classifier's look-alike/sound-alike probability."""
    target = _prepare_all([query])[0]
    if not target.clean:
        raise ValueError("Query must contain at least one letter or number.")
    if not target.ipa:
        raise ValueError("Query must contain at least one letter.")

    full = _run_phoc(
        (target.clean, target.ipa), [(drug.clean, drug.ipa) for drug in drugs]
    )
    core = _run_phoc(
        (target.core, target.core_ipa), [(drug.core, drug.core_ipa) for drug in drugs]
    )

    inputs = np.column_stack(
        [(core if is_core else full)[column] for is_core, column in _FEATURE_COLUMNS]
    )
    probabilities = _model.predict_proba(inputs)[:, 1]
    look_alike = inputs[:, _GROUP_COLUMNS["look_alike"]].mean(axis=1) * 100
    sound_alike = inputs[:, _GROUP_COLUMNS["sound_alike"]].mean(axis=1) * 100

    # Include each measure's top drugs so the page can re-arrange without searching.
    selected = {
        int(index)
        for measure in (probabilities, look_alike, sound_alike)
        for index in np.argsort(-measure, kind="stable")[:RESULT_LIMIT]
    }

    def group_scores(index: int, group: str) -> dict[str, float]:
        return {FEATURES[c]: float(inputs[index, c]) for c in _GROUP_COLUMNS[group]}

    return [
        {
            "name": drugs[index].name,
            "nativized": drugs[index].nativized,
            "score": round(float(probabilities[index]) * 100, 2),
            "look_alike": float(look_alike[index]),
            "sound_alike": float(sound_alike[index]),
            "source": "ph_GenBrn",
            "look_alike_scores": group_scores(index, "look_alike"),
            "sound_alike_scores": group_scores(index, "sound_alike"),
            "edit_counts": group_scores(index, "edit_counts"),
        }
        for index in sorted(selected, key=lambda i: (-probabilities[i], i))
    ]
