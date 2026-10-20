"""
A Very Simple Tagalog Grapheme-to-Phoneme (G2P) Algorithm

This module converts Tagalog words to their phonetic transcriptions using IPA.
"""

from typing import List, Tuple, Dict, Optional
import argparse
from pathlib import Path


class TagalogG2P:
    """
    A grapheme-to-phoneme converter for Tagalog.

    Tagalog phoneme inventory:
    - Vowels: /a/, /e/, /i/, /o/, /u/
    - Consonants: /p/, /t/, /k/, /b/, /d/, /g/, /m/, /n/, /ŋ/, /s/, /h/, /l/, /ɾ/, /w/, /j/
    - Glottal stop: /ʔ/ (often unmarked in standard orthography)

    Note: Uses ALINE-compatible phonetic symbols for compatibility with NLTK's
    ALINE algorithm for phonetic similarity computation.
    """

    def __init__(self):
        self.consonants: Dict[str, str] = {
            "p": "p",
            "t": "t",
            "k": "k",
            "b": "b",
            "d": "d",
            "g": "g",  # Using 'g' for ALINE compatibility (not 'ɡ')
            "m": "m",
            "n": "n",
            "s": "s",
            "h": "h",
            "l": "l",
            "r": "ɾ",
            "w": "w",
            "y": "j",
        }

        # Vowel mappings (ALINE-compatible)
        self.vowels: Dict[str, str] = {
            "a": "a",
            "e": "ɛ",
            "i": "i",
            "o": "o",
            "u": "u",
        }

        self.digraphs: Dict[str, str] = {
            "ng": "ŋ",
            "ts": "ts",
            "dy": "dj",
            "ty": "tj",
        }

        self.trigraphs: Dict[str, str] = {
            "ngg": "ŋg",
            "ngk": "ŋk",
        }

        self.vowel_chars = set("aeiouAEIOU")

    def _preprocess(self, word: str) -> str:
        """
        Preprocess the word: lowercase and handle special characters.
        """
        word = word.lower().strip()
        # Handle common diacritics if present
        word = word.replace("á", "a").replace("à", "a")
        word = word.replace("é", "e").replace("è", "e")
        word = word.replace("í", "i").replace("ì", "i")
        word = word.replace("ó", "o").replace("ò", "o")
        word = word.replace("ú", "u").replace("ù", "u")
        word = word.replace("ñ", "ny")  # Spanish loan influence
        return word

    def _is_vowel(self, char: str) -> bool:
        """Check if a character is a vowel."""
        return char.lower() in self.vowel_chars

    def _handle_glottal_stop(self, phonemes: List[str], word: str) -> List[str]:
        """
        Insert glottal stops where appropriate in Tagalog.

        Glottal stops typically occur:
        1. Between two vowels (hiatus)
        2. Word-finally after a vowel (in many dialects)
        """
        result = []
        i = 0

        while i < len(phonemes):
            result.append(phonemes[i])

            if i < len(phonemes) - 1:
                current_is_vowel = phonemes[i] in self.vowels.values()
                next_is_vowel = phonemes[i + 1] in self.vowels.values()

                if current_is_vowel and next_is_vowel:
                    result.append("ʔ")

            i += 1

        return result

    def convert_word(self, word: str) -> str:
        """
        Convert a single Tagalog word to its phonetic transcription.

        Args:
            word: A Tagalog word in standard orthography

        Returns:
            The phonetic transcription in IPA
        """
        if not word:
            return ""

        word = self._preprocess(word)
        phonemes: List[str] = []
        i = 0

        while i < len(word):
            matched = False

            if i <= len(word) - 3:
                trigraph = word[i : i + 3]
                if trigraph in self.trigraphs:
                    phonemes.append(self.trigraphs[trigraph])
                    i += 3
                    matched = True
                    continue

            if i <= len(word) - 2:
                digraph = word[i : i + 2]
                if digraph in self.digraphs:
                    phonemes.append(self.digraphs[digraph])
                    i += 2
                    matched = True
                    continue

            char = word[i]

            if char in self.consonants:
                phonemes.append(self.consonants[char])
                matched = True
            elif char in self.vowels:
                phonemes.append(self.vowels[char])
                matched = True
            elif char == "-":
                phonemes.append(".")
                matched = True
            elif char == "'":
                phonemes.append("ʔ")
                matched = True
            elif char.isspace():
                matched = True

            if not matched:
                pass

            i += 1

        phonemes = self._handle_glottal_stop(phonemes, word)

        return "".join(phonemes)

    def convert(self, words: List[str]) -> List[Tuple[str, str]]:
        """
        Convert a list of Tagalog words to their phonetic transcriptions.

        Args:
            words: A list of Tagalog words

        Returns:
            A list of tuples (word, transcription)
        """
        results = []
        for word in words:
            transcription = self.convert_word(word)
            results.append((word, transcription))
        return results

    def transcribe(self, words: List[str]) -> List[str]:
        """
        Convert a list of Tagalog words and return only the transcriptions.

        Args:
            words: A list of Tagalog words

        Returns:
            A list of phonetic transcriptions
        """
        return [self.convert_word(word) for word in words]


def transcribe_file(
    input_path: str, output_path: Optional[str] = None
) -> List[Tuple[str, str]]:
    """
    Read words from a text file (one per line) and write phonetic transcriptions.

    Args:
        input_path: Path to input text file with words separated by newlines
        output_path: Path to output text file (optional, defaults to input_transcribed.txt)

    Returns:
        List of (word, transcription) tuples
    """
    input_file = Path(input_path)

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_file, "r", encoding="utf-8") as f:
        words = [line.strip() for line in f if line.strip()]

    g2p = TagalogG2P()
    results = g2p.convert(words)

    if output_path is None:
        output_path = input_file.parent / f"{input_file.stem}_transcribed.txt"
    else:
        output_path = Path(output_path)

    with open(output_path, "w", encoding="utf-8") as f:
        for word, transcription in results:
            f.write(f"{word}\t/{transcription}/\n")

    print(f"Transcribed {len(results)} words")
    print(f"Output saved to: {output_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tagalog Grapheme-to-Phoneme Converter"
    )
    parser.add_argument(
        "input_file", nargs="?", help="Input text file with words (one per line)"
    )
    parser.add_argument("-o", "--output", help="Output file path for transcriptions")

    args = parser.parse_args()

    if args.input_file:
        results = transcribe_file(args.input_file, args.output)

    else:
        print("Tagalog Grapheme-to-Phoneme Converter")
        print(
            "Usage: uv run tagalog_g2p.py <input_file> \n\t\t[-o output]\n\t\t[--heatmap path]"
        )
