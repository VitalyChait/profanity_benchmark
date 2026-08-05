"""Algospeak transformation tests."""

from youth_escalate_bench.transforms.algospeak import (
    TransformFamily,
    apply_leetspeak,
    transform_text,
    transform_version_hash,
)


def test_leetspeak_deterministic():
    assert apply_leetspeak("aste") == "4573"


def test_composition_depth():
    text = "test"
    out = transform_text(text, [TransformFamily.LEETSPEAK, TransformFamily.SPACING])
    assert " " in out


def test_version_hash_stable():
    assert transform_version_hash() == transform_version_hash()
