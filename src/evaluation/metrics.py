"""WER, CER, SER, and edit counts. jiwer does the alignment."""

from __future__ import annotations

import jiwer

from src.evaluation.normalize import normalize_for_eval, normalize_raw

_WORDS = jiwer.Compose([jiwer.ReduceToListOfListOfWords()])
_CHARS = jiwer.Compose([jiwer.ReduceToListOfListOfChars()])


def score_pair(reference: str, hypothesis: str) -> dict:
    raw_ref = normalize_raw(reference)
    raw_hyp = normalize_raw(hypothesis)
    norm_ref = normalize_for_eval(reference)
    norm_hyp = normalize_for_eval(hypothesis)
    raw = _details(raw_ref, raw_hyp)
    norm = _details(norm_ref, norm_hyp)
    char_errors, ref_chars = _char_counts(norm_ref.replace(" ", ""), norm_hyp.replace(" ", ""))
    return {
        "wer_raw": raw["wer"],
        "cer_raw": raw["cer"],
        "wer": norm["wer"],
        "cer": None
        if ref_chars == 0 and char_errors == 0
        else (1.0 if ref_chars == 0 else char_errors / ref_chars),
        "ser": 0 if norm_ref == norm_hyp else 1,
        "substitutions": norm["substitutions"],
        "deletions": norm["deletions"],
        "insertions": norm["insertions"],
        "ref_words": norm["ref_words"],
        "ref_chars": ref_chars,
        "char_errors": char_errors,
        "alignment": norm["alignment"],
        "normalized_reference": norm_ref,
        "normalized_hypothesis": norm_hyp,
    }


def _details(reference: str, hypothesis: str) -> dict:
    if reference == "" and hypothesis == "":
        return {
            "wer": 0.0,
            "cer": 0.0,
            "substitutions": 0,
            "deletions": 0,
            "insertions": 0,
            "ref_words": 0,
            "alignment": [],
        }
    word_out = jiwer.process_words(
        reference,
        hypothesis,
        reference_transform=_WORDS,
        hypothesis_transform=_WORDS,
    )
    char_ref = reference.replace(" ", "")
    char_hyp = hypothesis.replace(" ", "")
    if char_ref == "" and char_hyp == "":
        cer = 0.0
    else:
        cer = jiwer.process_characters(
            char_ref,
            char_hyp,
            reference_transform=_CHARS,
            hypothesis_transform=_CHARS,
        ).cer
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    alignment = []
    chunks = word_out.alignments[0] if word_out.alignments else []
    for chunk in chunks:
        kind = {"delete": "deletion", "insert": "insertion", "substitute": "substitution"}.get(
            chunk.type, chunk.type
        )
        alignment.append(
            {
                "op": kind,
                "ref": " ".join(ref_words[chunk.ref_start_idx : chunk.ref_end_idx]),
                "hyp": " ".join(hyp_words[chunk.hyp_start_idx : chunk.hyp_end_idx]),
            }
        )
    return {
        "wer": float(word_out.wer)
        if ref_words
        else (0.0 if not hyp_words else float(word_out.insertions)),
        "cer": float(cer),
        "substitutions": int(word_out.substitutions),
        "deletions": int(word_out.deletions),
        "insertions": int(word_out.insertions),
        "ref_words": len(ref_words),
        "alignment": alignment,
    }


def _char_counts(reference: str, hypothesis: str) -> tuple[int, int]:
    if reference == "" and hypothesis == "":
        return 0, 0
    out = jiwer.process_characters(
        reference,
        hypothesis,
        reference_transform=_CHARS,
        hypothesis_transform=_CHARS,
    )
    errors = int(out.substitutions) + int(out.deletions) + int(out.insertions)
    return errors, len(reference)
