"""Entity, digit, and code-mix checks. Patterns are reported as patterns."""

from __future__ import annotations

import re

import jiwer
from rapidfuzz import fuzz

from src.evaluation.normalize import normalize_for_eval

_INDIC_DIGITS = str.maketrans(
    "०१२३४५६७८९௦௧௨௩௪௫௬௭௮௯೦೧೨೩೪೫೬೭೮೯൦൧൨൩൪൫൬൭൮൯",
    "0123456789" * 4,
)
_TIME = re.compile(r"\b\d{1,2}:\d{2}\b")
_DATE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
_TELUGU = re.compile(r"[\u0c00-\u0c7f]")
_LATIN = re.compile(r"[A-Za-z]")
_CHARS = jiwer.Compose([jiwer.ReduceToListOfListOfChars()])
_WORDS = jiwer.Compose([jiwer.ReduceToListOfListOfWords()])


def evaluate_entities(reference: str, hypothesis: str, metadata: dict | None = None) -> dict:
    metadata = metadata or {}
    return {
        "phone": _phone(reference, hypothesis),
        "time": _pattern(_TIME, reference, hypothesis),
        "date": _pattern(_DATE, reference, hypothesis),
        "name": _metadata_entity(metadata, "name", hypothesis),
        "address": _metadata_entity(metadata, "address", hypothesis),
        "code_mix": _code_mix(reference, hypothesis, str(metadata.get("language") or "")),
    }


def _digits(text: str) -> str:
    return "".join(ch for ch in text.translate(_INDIC_DIGITS) if ch.isdigit())


def _longest_run(text: str) -> str:
    runs = re.findall(r"\d+", text.translate(_INDIC_DIGITS))
    if not runs:
        return ""
    return max(runs, key=len)


def _phone(reference: str, hypothesis: str) -> dict:
    ref_digits = _longest_run(reference)
    if len(ref_digits) < 6:
        return {"applicable": False}
    hyp_digits = _digits(hypothesis)
    if ref_digits == "" and hyp_digits == "":
        accuracy = 1.0
    elif ref_digits == "":
        accuracy = 0.0
    else:
        cer = jiwer.process_characters(
            ref_digits,
            hyp_digits,
            reference_transform=_CHARS,
            hypothesis_transform=_CHARS,
        ).cer
        accuracy = max(0.0, 1.0 - float(cer))
    return {
        "applicable": True,
        "exact": ref_digits == hyp_digits,
        "digit_accuracy": accuracy,
        "ref_digits": ref_digits,
        "hyp_digits": hyp_digits,
    }


def _pattern(pattern: re.Pattern[str], reference: str, hypothesis: str) -> dict:
    found = pattern.findall(reference)
    if not found:
        return {"applicable": False}
    hyp_norm = normalize_for_eval(hypothesis)
    exact = all(normalize_for_eval(value) in hyp_norm for value in found)
    return {"applicable": True, "exact": exact, "values": found}


def _metadata_entity(metadata: dict, kind: str, hypothesis: str) -> dict:
    entities = metadata.get("entities") or []
    texts = [
        item.get("text", "") for item in entities if item.get("type") == kind and item.get("text")
    ]
    if not texts:
        return {"applicable": False}
    hyp = normalize_for_eval(hypothesis)
    matches = []
    for text in texts:
        norm = normalize_for_eval(text)
        matches.append(norm in hyp.split() or norm in hyp)
    return {
        "applicable": True,
        "exact": all(matches),
        "similarity": max(fuzz.ratio(normalize_for_eval(text), hyp) for text in texts) / 100,
    }


def _code_mix(reference: str, hypothesis: str, language: str) -> dict:
    ref_te, ref_lat = _script_tokens(reference)
    if not (ref_te and ref_lat):
        return {"applicable": False}
    if language and language != "te":
        return {"applicable": False}
    hyp_te, hyp_lat = _script_tokens(hypothesis)
    return {
        "applicable": True,
        "latin_wer": _token_wer(ref_lat, hyp_lat),
        "indic_wer": _token_wer(ref_te, hyp_te),
    }


def _script_tokens(text: str) -> tuple[list[str], list[str]]:
    telugu: list[str] = []
    latin: list[str] = []
    for token in normalize_for_eval(text).split():
        if _TELUGU.search(token):
            telugu.append(token)
        elif _LATIN.search(token):
            latin.append(token)
    return telugu, latin


def _token_wer(reference: list[str], hypothesis: list[str]) -> float | None:
    if not reference:
        return None
    out = jiwer.process_words(
        " ".join(reference),
        " ".join(hypothesis),
        reference_transform=_WORDS,
        hypothesis_transform=_WORDS,
    )
    return float(out.wer)
