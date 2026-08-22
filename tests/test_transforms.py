"""Algospeak transformation tests."""

from youth_escalate_bench.transforms.algospeak import (
    TransformFamily,
    apply_acronyms,
    apply_euphemisms,
    apply_leetspeak,
    apply_phonetics,
    transform_text,
    transform_version_hash,
)


def test_leetspeak_deterministic():
    assert apply_leetspeak("aste") == "4573"


def test_euphemisms():
    assert "unalive" in apply_euphemisms("they want to kill him")
    assert "seggs" in apply_euphemisms("talking about sex")


def test_phonetics():
    assert "fuk" in apply_phonetics("fuck this")
    assert "biatch" in apply_phonetics("bitch please")


def test_acronyms():
    assert apply_acronyms("shut the fuck up") == "stfu"
    assert apply_acronyms("kill yourself") == "kys"


def test_composition_depth():
    text = "kill yourself"
    out = transform_text(text, [TransformFamily.EUPHEMISTIC_ALGO_CODED, TransformFamily.SPACING])
    assert " " in out


def test_version_hash_stable():
    assert transform_version_hash() == transform_version_hash()
