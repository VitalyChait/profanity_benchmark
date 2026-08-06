"""Adjudication and agreement tests."""

from pathlib import Path

from youth_escalate_bench.metrics.agreement import actionable_agreement, severity_alpha
from youth_escalate_bench.schemas.labels import AnnotationRecord, Severity
from youth_escalate_bench.stages.adjudicate import adjudicate_annotations, run_adjudicate


def _ann(conv: str, turn: str, severity: Severity, who: str) -> AnnotationRecord:
    return AnnotationRecord(
        conversation_id=conv,
        turn_id=turn,
        severity=severity,
        annotator_id=who,
    )


def test_majority_adjudication():
    anns = [
        _ann("c1", "t1", Severity.BENIGN, "a"),
        _ann("c1", "t1", Severity.ACTIONABLE, "b"),
        _ann("c1", "t1", Severity.ACTIONABLE, "c"),
    ]
    gold = adjudicate_annotations(anns)
    assert len(gold) == 1
    assert gold[0].severity == Severity.ACTIONABLE


def test_severity_alpha_perfect_agreement():
    anns = [_ann("c1", "t1", Severity.BENIGN, "a"), _ann("c1", "t1", Severity.BENIGN, "b")]
    alpha = severity_alpha(anns)
    assert alpha is not None and alpha >= 0.99


def test_adjudicate_stage(tmp_path: Path):
    import json

    ann_path = tmp_path / "annotations.jsonl"
    rows = [
        {"conversation_id": "c1", "turn_id": "t1", "severity": "benign", "annotator_id": "a"},
        {"conversation_id": "c1", "turn_id": "t1", "severity": "actionable", "annotator_id": "b"},
        {"conversation_id": "c1", "turn_id": "t1", "severity": "actionable", "annotator_id": "c"},
    ]
    with ann_path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    out = tmp_path / "out"
    config = {"annotations_path": str(ann_path), "benchmark_version": "0.1.0"}
    result = run_adjudicate(config, tmp_path, out)
    assert (out / "gold_labels.jsonl").exists()
    assert result["metadata"]["gold_labels"] == 1


def test_actionable_agreement():
    anns = [
        _ann("c1", "t1", Severity.BENIGN, "a"),
        _ann("c1", "t1", Severity.BENIGN, "b"),
        _ann("c2", "t1", Severity.ACTIONABLE, "a"),
        _ann("c2", "t1", Severity.BENIGN, "b"),
    ]
    agree = actionable_agreement(anns)
    assert agree is not None
    assert 0.5 <= agree <= 1.0
