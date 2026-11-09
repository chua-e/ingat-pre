"""Drug name cleaning and core words, matching walter's feature pipeline.

Ported from walter: `clean_name` from src/pipeline/preprocessing.py, `core_name`
from src/pipeline/core_name.py, and the word lists from config/phonetics.py.
The classifier was trained on these exact rules, so keep them in step.
"""

import re
import unicodedata

_HAS_DIGIT = re.compile(r"\d")

CORE_NAME_STOPWORDS = frozenset(
    {
        # Salts and hydrates
        "acetate", "bromide", "carbonate", "chloride", "citrate", "dihydrate",
        "dihydrochloride", "dipropionate", "fumarate", "gluconate", "hcl",
        "hydrobromide", "hydrochloride", "hydroxide", "maleate", "monohydrate",
        "mononitrate", "phosphate", "potassium", "propionate", "sodium",
        "succinate", "sulfate", "sulphate", "trihydrate", "valerate", "besilate",
        # Dosage forms and routes
        "adsorbed", "cap", "capsule", "capsules", "cream", "drops", "er", "eye",
        "formulation", "gel", "iv", "mg", "mr", "odt", "ointment", "reformulated",
        "solution", "sr", "suspension", "syrup", "tab", "tablet", "tablets",
        "topical", "xr",
        # Product qualifiers and connecting words
        "advance", "and", "ds", "for", "forte", "kids", "od", "plus", "with",
    }
)  # fmt: skip

# First words that identify little alone, so the core keeps the word after them.
CORE_LEADING_WORDS = frozenset(
    {
        # Brand-style prefixes
        "bio", "co", "dr", "fin", "go", "md", "mega", "neo", "neuro", "new", "one",
        "rapid", "st", "tri",
        # Ingredient and class words shared by many products
        "calcium", "human", "insulin", "iron", "magnesium", "multivitamins",
        "potassium", "purified", "sodium", "tetanus", "vitamin", "zinc",
    }
)  # fmt: skip

# Words that cannot complete a leading word: forms, routes, and qualifiers.
CORE_LEADING_EXCLUDED = frozenset(
    {
        "adsorbed", "advance", "and", "cap", "capsule", "capsules", "cream", "drops",
        "ds", "er", "eye", "for", "formulation", "forte", "gel", "iv", "kids", "mg",
        "mr", "od", "odt", "ointment", "plus", "reformulated", "solution", "sr",
        "suspension", "syrup", "tab", "tablet", "tablets", "topical", "with", "xr",
    }
)  # fmt: skip


def clean_name(name: str) -> str:
    """Lowercase a name, drop accents and punctuation, and collapse whitespace."""
    name = name.lower().strip()
    name = "".join(
        character
        for character in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(character)
    )
    name = re.sub(r"[-/']", " ", name)
    name = re.sub(r"[^a-z0-9 ]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def core_name(name: str) -> str:
    """Return the part of a cleaned drug name that identifies the product."""
    words = name.split()
    if words and words[0] in CORE_LEADING_WORDS:
        for word in words[1:]:
            if (
                word not in CORE_LEADING_EXCLUDED
                and not _HAS_DIGIT.search(word)
                and len(word) > 1
            ):
                return f"{words[0]} {word}"
        return words[0]
    for word in words:
        if (
            word not in CORE_NAME_STOPWORDS
            and not _HAS_DIGIT.search(word)
            and len(word) > 1
        ):
            return word
    return words[0] if words else ""
