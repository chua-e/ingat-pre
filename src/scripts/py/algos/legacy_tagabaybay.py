"""
(Legacy Code) Filipino Phonetic Nativization

Applies phonological rules to convert foreign words to Filipino spelling
(e.g., paracetamol -> parasetamol)
"""

import re
import argparse
from pathlib import Path
from typing import List, Optional


class FilipinoNativizer:
    def __init__(self):
        # Core Filipino alphabet
        self.core_consonants = {
            "b",
            "k",
            "d",
            "g",
            "h",
            "l",
            "m",
            "n",
            "ng",
            "p",
            "r",
            "s",
            "t",
            "w",
            "y",
        }
        self.vowels = {"a", "e", "i", "o", "u"}

        # Basic phoneme mapping rules
        self.phoneme_rules = [
            ("ph", "f"),  # phone -> fon
            ("ps", "s"),  # psychology -> sikolodyi
            ("v", "b"),  # verde -> berde
            ("j", "dy"),  # jeep -> dyip
            ("z", "s"),  # zipon -> sipon
            ("ñ", "ny"),  # baño -> banyo
            ("qu", "kuw"),  # queen -> kuwin
        ]

        # English-specific ending patterns
        self.english_patterns = [
            (r"tion$", "syon"),
            (r"sion$", "syon"),
            (r"ture$", "tyur"),
            (r"ter$", "ter"),
            (r"ble$", "bol"),
        ]

    def _single_letters_to_phonetic(self, word: str, i: int = 0) -> str:
        """Convert single uppercase letters to phonetic spelling (for abbreviations)"""
        if len(word) <= i:
            return word.removesuffix("-")

        first_half = word[:i]
        secnd_half = word[i + 1 :]
        mapped = self._phonetic_alphabet(word[i]) + "-"
        word = first_half + mapped + secnd_half
        return self._single_letters_to_phonetic(word, i + len(mapped))

    def _phonetic_alphabet(self, char: str) -> str:
        """Map single letter to Filipino phonetic pronunciation"""
        char = char.strip().lower()
        mapping = {
            "a": "ey",
            "b": "bi",
            "c": "si",
            "d": "di",
            "e": "i",
            "f": "ef",
            "g": "dyi",
            "h": "eyts",
            "i": "ay",
            "j": "dyey",
            "k": "key",
            "l": "el",
            "m": "em",
            "n": "en",
            "ñ": "enye",
            "o": "o",
            "p": "pi",
            "q": "kyu",
            "r": "ar",
            "s": "es",
            "t": "ti",
            "u": "yu",
            "v": "vi",
            "w": "dobolyu",
            "x": "eks",
            "y": "way",
            "z": "zi",
        }
        return mapping.get(char, char)

    def nativize(self, word: str) -> str:
        """
        Apply Filipino phonetic nativization rules to convert foreign words.

        Examples:
            paracetamol -> parasetamol
            ibuprofen -> aybuprofen
            computer -> kompyuter
        """
        substrings = word.split(" ")
        nativized = ""

        for sb in substrings:
            # Handle abbreviations (all uppercase)
            if re.match(r"^[A-Z]+$", sb):
                nativized += " " + self._single_letters_to_phonetic(sb)
            else:
                result = sb.lower()

                # Step 1: Apply basic phoneme mappings
                for pattern, replacement in self.phoneme_rules:
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
                for pattern, replacement in self.english_patterns:
                    result = re.sub(pattern, replacement, result)

                # Step 12: Reduce triple consonants
                for consonant in "bdfghjklmnpqrstvwxz":
                    triple = consonant * 3
                    if triple in result:
                        result = result.replace(triple, consonant)

                nativized += " " + result

        return nativized.strip()


def nativize(word: str) -> str:
    """
    Convenience function to nativize a word to Filipino spelling.

    Args:
        word: Foreign word to nativize

    Returns:
        Filipino phonetic spelling

    Example:
        >>> nativize('paracetamol')
        'parasetamol'
    """
    return FilipinoNativizer().nativize(word)


def nativize_list(words: List[str]) -> List[str]:
    """
    Nativize a list of words to Filipino spelling.

    Args:
        words: List of foreign words

    Returns:
        List of Filipino phonetic spellings
    """
    nativizer = FilipinoNativizer()
    return [nativizer.nativize(word) for word in words]


def nativize_file(input_path: str, output_path: Optional[str] = None) -> List[str]:
    """
    Read words from a text file (one per line) and write nativized versions.

    Args:
        input_path: Path to input text file with words separated by newlines
        output_path: Path to output text file (optional, defaults to input_nativized.txt)

    Returns:
        List of nativized words
    """
    input_file = Path(input_path)

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Read words from file
    with open(input_file, "r", encoding="utf-8") as f:
        words = [line.strip() for line in f if line.strip()]

    # Nativize all words
    nativizer = FilipinoNativizer()
    results = []
    for word in words:
        nativized = nativizer.nativize(word)
        results.append((word, nativized))

    # Determine output path
    if output_path is None:
        output_path = input_file.parent / f"{input_file.stem}_nativized.txt"
    else:
        output_path = Path(output_path)

    # Write results to file
    with open(output_path, "w", encoding="utf-8") as f:
        for original, nativized in results:
            f.write(f"{original}\t{nativized}\n")

    print(f"Processed {len(results)} words")
    print(f"Output saved to: {output_path}")

    return [r[1] for r in results]


# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filipino Phonetic Nativization")
    parser.add_argument(
        "input_file", nargs="?", help="Input text file with words (one per line)"
    )
    parser.add_argument(
        "-o", "--output", help="Output file path (default: input_nativized.txt)"
    )

    args = parser.parse_args()

    if args.input_file:
        nativize_file(args.input_file, args.output)

    else:
        nativizer = FilipinoNativizer()

        print("Filipino Phonetic Nativization")
        print("Usage: python legacy_tagabaybay.py <input_file> \n\t\t[-o output_file]")
