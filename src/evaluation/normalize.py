"""Unicode and punctuation normalization for scoring.

Raw scores keep punctuation. Normalized scores remove a fixed punctuation set.
Indic letters and digits are kept. Nothing is transliterated.
"""

from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)
_SPACE = re.compile(r"\s+")
_PUNCT = ".,!?;:\"'“”‘’()[]{}<>/\\|@#$%^&*_+=~`…—–-।॥"

NORMALIZED = "NFC, drop zero-width characters, replace the fixed punctuation set with spaces, casefold, collapse whitespace"
RAW = "NFC, drop zero-width characters, collapse whitespace"


def _base(text: str) -> str:
    cleaned = unicodedata.normalize("NFC", text or "")
    cleaned = cleaned.translate(_ZERO_WIDTH)
    cleaned = cleaned.replace("\u00a0", " ")
    return cleaned


def normalize_raw(text: str) -> str:
    return _SPACE.sub(" ", _base(text)).strip()


def normalize_for_eval(text: str) -> str:
    cleaned = _base(text)
    cleaned = "".join(" " if char in _PUNCT else char for char in cleaned)
    cleaned = cleaned.casefold()
    return _SPACE.sub(" ", cleaned).strip()
