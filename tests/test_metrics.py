from src.evaluation.metrics import score_pair


def test_substitution_wer():
    scored = score_pair("the cat sat", "the dog sat")
    assert scored["substitutions"] == 1
    assert scored["deletions"] == 0
    assert scored["insertions"] == 0
    assert scored["wer"] == 1 / 3


def test_deletion_and_insertion():
    deleted = score_pair("hello world", "hello")
    assert deleted["deletions"] == 1
    assert deleted["wer"] == 0.5
    inserted = score_pair("hello", "hello world")
    assert inserted["insertions"] == 1
    assert inserted["wer"] == 1


def test_sentence_error_and_empty():
    assert score_pair("same line", "same line")["ser"] == 0
    assert score_pair("same line", "other line")["ser"] == 1
    assert score_pair("", "")["wer"] == 0
