from src.evaluation.entities import evaluate_entities


def test_phone_digits():
    scored = evaluate_entities("call 9876543210", "call 9876543210")
    assert scored["phone"]["applicable"] is True
    assert scored["phone"]["exact"] is True
    assert scored["phone"]["digit_accuracy"] == 1


def test_time_pattern():
    scored = evaluate_entities("meet at 10:30", "meet at 10:30")
    assert scored["time"]["exact"] is True


def test_code_mix_telugu_english():
    scored = evaluate_entities("నమస్తే hello", "నమస్తే hello", {"language": "te"})
    assert scored["code_mix"]["applicable"] is True
    assert scored["code_mix"]["latin_wer"] == 0
    assert scored["code_mix"]["indic_wer"] == 0


def test_name_from_metadata_only():
    missed = evaluate_entities(
        "hello ram", "hello", {"entities": [{"type": "name", "text": "ram"}]}
    )
    assert missed["name"]["applicable"] is True
    assert missed["name"]["exact"] is False
