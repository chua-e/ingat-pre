"""
A Very Simple Tagalog Grapheme-to-Phoneme (G2P) Algorithm

This module converts Tagalog words to their phonetic transcriptions using IPA.
"""


class TagalogG2P:
    """
    A grapheme-to-phoneme converter for Tagalog.

    Tagalog phoneme inventory:
    - Vowels: /a/, /e/, /i/, /o/, /u/
    - Consonants: /p/, /t/, /k/, /b/, /d/, /g/, /m/, /n/, /ŋ/, /s/, /h/, /l/, /ɾ/, /w/, /j/
    - Glottal stop: /ʔ/ (often unmarked in standard orthography)
    """

    def __init__(self):
        self.consonants: dict[str, str] = {
            "p": "p",
            "t": "t",
            "k": "k",
            "b": "b",
            "f": "f",  # Loanwords; kept because the stored fil_ipa keeps it
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
        self.vowels: dict[str, str] = {
            "a": "a",
            "e": "ɛ",
            "i": "i",
            "o": "o",
            "u": "u",
        }

        self.digraphs: dict[str, str] = {
            "ng": "ŋ",
            "ts": "ts",
            "dy": "dj",
            "ty": "tj",
        }

        self.trigraphs: dict[str, str] = {
            "ngg": "ŋg",
            "ngk": "ŋk",
        }

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

    def _handle_glottal_stop(self, phonemes: list[str]) -> list[str]:
        """Insert a glottal stop between two adjacent vowels (hiatus)."""
        vowels = set(self.vowels.values())
        result = phonemes[:1]

        for previous, current in zip(phonemes, phonemes[1:]):
            if previous in vowels and current in vowels:
                result.append("ʔ")
            result.append(current)

        return result

    def convert_word(self, word: str) -> str:
        """
        Convert a single Tagalog word to its phonetic transcription.

        Args:
            word: A Tagalog word in standard orthography

        Returns:
            The phonetic transcription in IPA
        """
        word = self._preprocess(word)
        phonemes: list[str] = []
        i = 0

        while i < len(word):
            trigraph = word[i : i + 3]
            if trigraph in self.trigraphs:
                phonemes.append(self.trigraphs[trigraph])
                i += 3
                continue

            digraph = word[i : i + 2]
            if digraph in self.digraphs:
                phonemes.append(self.digraphs[digraph])
                i += 2
                continue

            # Anything without a sound (digits, spaces, punctuation) is skipped.
            char = word[i]
            if char in self.consonants:
                phonemes.append(self.consonants[char])
            elif char in self.vowels:
                phonemes.append(self.vowels[char])
            elif char == "-":
                phonemes.append(".")
            elif char == "'":
                phonemes.append("ʔ")

            i += 1

        return "".join(self._handle_glottal_stop(phonemes))
