"""Language codes used by the bench. English is only for the pipeline demo."""

from __future__ import annotations

TARGET_LANGUAGES: tuple[str, ...] = ("te", "ta", "hi", "kn", "ml")

DISPLAY_NAMES: dict[str, str] = {
    "te": "Telugu",
    "ta": "Tamil",
    "hi": "Hindi",
    "kn": "Kannada",
    "ml": "Malayalam",
    "en": "English",
}

SCRIPTS: dict[str, str] = {
    "te": "తెలుగు",
    "ta": "தமிழ்",
    "hi": "हिन्दी",
    "kn": "ಕನ್ನಡ",
    "ml": "മലയാളം",
    "en": "English",
}

ALIASES: dict[str, str] = {
    "te": "te",
    "tel": "te",
    "telugu": "te",
    "ta": "ta",
    "tam": "ta",
    "tamil": "ta",
    "hi": "hi",
    "hin": "hi",
    "hindi": "hi",
    "kn": "kn",
    "kan": "kn",
    "kannada": "kn",
    "ml": "ml",
    "mal": "ml",
    "malayalam": "ml",
    "en": "en",
    "eng": "en",
    "english": "en",
}

WHISPER_NAMES: dict[str, str] = {
    "te": "telugu",
    "ta": "tamil",
    "hi": "hindi",
    "kn": "kannada",
    "ml": "malayalam",
    "en": "english",
}

# Meta MMS adapter ids. Verified against the MMS language list.
MMS_CODES: dict[str, str] = {
    "te": "tel",
    "ta": "tam",
    "hi": "hin",
    "kn": "kan",
    "ml": "mal",
    "en": "eng",
}

FLEURS_CONFIGS: dict[str, str] = {
    "te": "te_in",
    "ta": "ta_in",
    "hi": "hi_in",
    "kn": "kn_in",
    "ml": "ml_in",
}


def canonicalize(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip().lower().replace("_", "-")
    if key in ALIASES:
        return ALIASES[key]
    head = key.split("-")[0]
    return ALIASES.get(head)
