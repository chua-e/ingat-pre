"""Filipino nativization and IPA: the `fil_na` condition the classifier was trained on.

TagaBaybay adapts each word into Filipino spelling, at the revision pho pins, and
Taglog-G2P's Phonetisaurus decoder transcribes that spelling to IPA.
"""

import atexit
import json
import os
import re
import subprocess
import threading
import unicodedata
from pathlib import Path

PY_DIR = Path(__file__).parent
ROOT_DIR = Path(__file__).parents[3]

TBB_CLI = Path(
    os.environ.get(
        "TBB_CLI",
        PY_DIR / ".tbb/bin" / ("tbb-cli.exe" if os.name == "nt" else "tbb-cli"),
    )
)
TAGALOG_G2P = Path(
    os.environ.get("TAGALOG_G2P", ROOT_DIR.parent / "Taglog-G2P/dist/tagalog-g2p")
)
WSL_DISTRO = os.environ.get("WSL_DISTRO", "Ubuntu-22.04")
# Words go on the command line, which Windows limits to about 32,000 characters.
MAX_BATCH_CHARACTERS = 20000

_WORD = re.compile(r"[a-z]+")
_WORD_OR_OTHER = re.compile(r"[a-z]+|[^a-z]+")
_TONE_LETTERS = re.compile(r"[˥-˩]")
_IPA_FIXUPS = {"d͡ʒ": "ʤ", "t͡ʃ": "ʧ", "ɡ": "g"}

for _tool, _hint in (
    (
        TBB_CLI,
        "run.bat builds it from the tagabaybay revision pho pins, or set TBB_CLI.",
    ),
    (TAGALOG_G2P, "Build it in the Taglog-G2P repo, or set TAGALOG_G2P."),
):
    if not _tool.exists():
        raise RuntimeError(f"{_tool} not found. {_hint}")


class _TagaBaybay:
    """A long-running tbb-cli worker that answers one word at a time."""

    def __init__(self) -> None:
        self._process = subprocess.Popen(
            [TBB_CLI],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
            bufsize=1,
        )
        atexit.register(self._process.terminate)
        self._lock = threading.Lock()
        self._cache: dict[str, str] = {}
        self._next_id = 0
        self._read_reply()
        self._write({"cmd": "config", "assign_prominence": True})
        self._read_reply()

    def _write(self, request: dict) -> None:
        self._process.stdin.write(json.dumps(request) + "\n")
        self._process.stdin.flush()

    def _read_reply(self, request_id: int | None = None) -> dict:
        for line in self._process.stdout:
            try:
                reply = json.loads(line)
            except ValueError:
                continue  # tbb-cli can also print debug lines to stdout.
            if isinstance(reply, dict) and (
                request_id is None or reply.get("id") == request_id
            ):
                return reply
        raise RuntimeError("tbb-cli stopped responding.")

    def adapt(self, word: str) -> str:
        with self._lock:
            if word not in self._cache:
                self._next_id += 1
                self._write({"id": self._next_id, "cmd": "adapt", "word": word})
                reply = self._read_reply(self._next_id)
                adapted = (
                    reply.get("adapted") if reply.get("type") == "result" else None
                )
                self._cache[word] = adapted or word
            return self._cache[word]


class _TagalogG2P:
    """Runs Taglog-G2P's decoder, whose release build is a Linux binary."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, str] = {}

    def _command(self, words: list[str]) -> list[str | Path]:
        if os.name != "nt":
            return [TAGALOG_G2P, *words]
        drive, path = TAGALOG_G2P.resolve().as_posix().split(":", 1)
        return [
            "wsl.exe",
            "-d",
            WSL_DISTRO,
            "--",
            f"/mnt/{drive.lower()}{path}",
            *words,
        ]

    def _run(self, words: list[str]) -> list[str]:
        completed = subprocess.run(
            self._command(words),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        lines = completed.stdout.splitlines()
        if completed.returncode == 0 and len(lines) == len(words):
            return lines
        if "tagalog-g2p: error" not in completed.stderr:
            raise RuntimeError(f"tagalog-g2p could not run: {completed.stderr.strip()}")
        # One word the model can't decode fails its whole batch, so narrow it down.
        if len(words) == 1:
            return [""]
        middle = len(words) // 2
        return self._run(words[:middle]) + self._run(words[middle:])

    def _store(self, words: list[str]) -> None:
        for word, phones in zip(words, self._run(words)):
            ipa = "".join(phones.split())
            for source, target in _IPA_FIXUPS.items():
                ipa = ipa.replace(source, target)
            self._cache[word] = _TONE_LETTERS.sub("", ipa)

    def decode_all(self, words: set[str]) -> None:
        """Make sure every word is in the cache, decoding the rest in batches."""
        with self._lock:
            batch: list[str] = []
            characters = 0
            for word in sorted(words - self._cache.keys()):
                if characters + len(word) + 1 > MAX_BATCH_CHARACTERS:
                    self._store(batch)
                    batch, characters = [], 0
                batch.append(word)
                characters += len(word) + 1
            if batch:
                self._store(batch)

    def ipa(self, word: str) -> str:
        return self._cache[word]


_tagabaybay = _TagaBaybay()
_tagalog_g2p = _TagalogG2P()


def nativize(name: str) -> str:
    """Adapt each word of a cleaned name into Filipino spelling."""
    return _WORD.sub(lambda word: _tagabaybay.adapt(word.group()), name)


def transcribe_all(spellings: list[str]) -> list[str]:
    """Transcribe Filipino spellings to IPA, keeping non-letters as they are."""
    chunked = [
        _WORD_OR_OTHER.findall(unicodedata.normalize("NFC", spelling).lower())
        for spelling in spellings
    ]
    _tagalog_g2p.decode_all(
        {text for chunks in chunked for text in chunks if _WORD.fullmatch(text)}
    )
    return [
        "".join(
            _tagalog_g2p.ipa(text) if _WORD.fullmatch(text) else "".join(text.split())
            for text in chunks
        )
        for chunks in chunked
    ]
