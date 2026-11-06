from src.evaluation.normalize import normalize_for_eval, normalize_raw


def test_nfc_and_whitespace():
    assert normalize_raw("e\u0301  hello") == "é hello"


def test_punctuation_is_removed_only_for_normalized_scores():
    assert normalize_for_eval("హలో,") == normalize_for_eval("హలో")
    assert normalize_raw("హలో,") != normalize_raw("హలో")


def test_telugu_is_not_transliterated():
    text = "నమస్తే"
    assert normalize_for_eval(text) == text
