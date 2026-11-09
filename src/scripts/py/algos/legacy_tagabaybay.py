"""
Filipino Phonetic Nativization

Applies phonological rules to convert foreign words to Filipino spelling
(e.g., paracetamol -> parasetamol)
"""

import re

# Basic phoneme mapping rules
PHONEME_RULES = [
    ("ph", "f"),  # phone -> fon
    ("ps", "s"),  # psychology -> sikolodyi
    ("v", "b"),  # verde -> berde
    ("j", "dy"),  # jeep -> dyip
    ("z", "s"),  # zipon -> sipon
    ("ñ", "ny"),  # baño -> banyo
    ("qu", "kuw"),  # queen -> kuwin
]

# English-specific ending patterns
ENGLISH_PATTERNS = [
    (r"tion$", "syon"),
    (r"sion$", "syon"),
    (r"ture$", "tyur"),
    (r"ter$", "ter"),
    (r"ble$", "bol"),
]


def _nativize_word(word: str) -> str:
    result = word.lower()

    # Step 1: Apply basic phoneme mappings
    for pattern, replacement in PHONEME_RULES:
        result = result.replace(pattern, replacement)

    # Step 2: Handle 'x' variations
    result = re.sub(r"^x", "s", result)  # x at start -> s
    result = re.sub(r"(?<=[x])y", "i", result)  # xy -> xi
    result = re.sub(r"x", "ks", result)  # x elsewhere -> ks

    # Step 3: Handle 'y' before certain consonants
    result = re.sub(r"y(?=[s])", "i", result)  # ys -> is
    result = re.sub(r"(?i)y(?=l)", "i", result)  # yl -> il

    # Step 4: Handle 'c' variations
    result = re.sub(r"c([eyi])", r"s\1", result)  # c before e/i/y -> s
    result = result.replace("c", "k")  # c elsewhere -> k
    result = result.replace("kh", "k")  # ch -> k (after c->k)

    # Step 5: Handle 'y' as vowel
    result = re.sub(r"(?i)y", "ay", result)
    result = re.sub(r"(?<!a)y", "i", result)  # y not after 'a' -> i

    # Step 6: Handle 'g' before front vowels
    result = re.sub(r"g([eiy])(?![sck])", r"dy\1", result)

    # Step 7: Handle common English endings
    result = re.sub(r"ate$", "eyt", result)
    result = re.sub(r"ide$", "ayd", result)
    result = re.sub(r"one$", "own", result)
    result = re.sub(r"e$", "", result)  # silent final e

    # Step 8: Handle 'th' combinations
    result = re.sub(r"thi([ao])", r"tay\1", result)
    result = result.replace("th", "t")

    # Step 9: Reduce double consonants
    result = re.sub(r"([^\d])\1", r"\1", result)

    # Step 10: Handle vowel combinations
    result = result.replace("ein", "in")
    result = re.sub(r"o([aeiou])(?![aeiou])", r"oy\1", result)
    result = re.sub(r"i([aeiou])", r"iy\1", result)
    result = re.sub(r"u([aeiou])", r"uw\1", result)
    result = result.replace("eu", "u")
    result = re.sub(r"ee", "i", result)
    result = re.sub(r"oo", "u", result)

    # Step 11: Apply English-specific ending patterns
    for pattern, replacement in ENGLISH_PATTERNS:
        result = re.sub(pattern, replacement, result)

    # Step 12: Reduce triple consonants
    for consonant in "bdfghjklmnpqrstvwxz":
        result = result.replace(consonant * 3, consonant)

    return result


def nativize(word: str) -> str:
    """
    Apply Filipino phonetic nativization rules to each space-separated part.

    Example:
        >>> nativize('paracetamol')
        'parasetamol'
    """
    return " ".join(_nativize_word(part) for part in word.split(" ")).strip()
