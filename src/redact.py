"""Remove tokens from errors before they are stored or shown."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"(?i)(token|authorization|hf_token|api_key)(\s*[=:]\s*)(\S+)")
_HF = re.compile(r"hf_[A-Za-z0-9]{8,}")


def scrub(text: str | None) -> str:
    if not text:
        return ""
    cleaned = _TOKEN.sub(r"\1\2<redacted>", text)
    return _HF.sub("hf_<redacted>", cleaned)
