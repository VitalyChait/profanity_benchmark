"""Tests for functional minimal pairs diagnostic suite."""

from youth_escalate_bench.schemas.labels import Severity
from youth_escalate_bench.transforms.minimal_pairs import (
    DEFAULT_MINIMAL_PAIRS,
    DiagnosticCategory,
    build_minimal_pair_conversations,
)


def test_default_minimal_pairs_structure():
    assert len(DEFAULT_MINIMAL_PAIRS) >= 5
    categories = {p.category for p in DEFAULT_MINIMAL_PAIRS}
    assert DiagnosticCategory.BANTER_VS_ABUSE in categories
    assert DiagnosticCategory.TARGETED_VS_UNTARGETED in categories
    assert DiagnosticCategory.QUOTATION_VS_ENDORSEMENT in categories


def test_build_minimal_pair_conversations():
    convs, anns = build_minimal_pair_conversations()
    assert len(convs) == len(DEFAULT_MINIMAL_PAIRS) * 2
    assert len(anns) == len(DEFAULT_MINIMAL_PAIRS) * 2

    # Check benign vs harmful severity labels
    benign_anns = [a for a in anns if a.severity == Severity.BENIGN]
    harmful_anns = [a for a in anns if a.severity == Severity.ACTIONABLE]
    assert len(benign_anns) == len(DEFAULT_MINIMAL_PAIRS)
    assert len(harmful_anns) == len(DEFAULT_MINIMAL_PAIRS)
