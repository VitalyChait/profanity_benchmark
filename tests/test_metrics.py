"""Metric computation tests."""

from youth_escalate_bench.metrics.detection import auprc, compute_binary_metrics


def test_auprc_perfect_classifier():
    y_true = [True, False, True, False]
    y_score = [0.9, 0.1, 0.8, 0.2]
    assert auprc(y_true, y_score) == 1.0


def test_auprc_empty():
    assert auprc([], []) == 0.0


def test_compute_binary_metrics():
    y_true = [True, False, True, False, True]
    y_score = [0.9, 0.2, 0.7, 0.3, 0.6]
    m = compute_binary_metrics(y_true, y_score)
    assert m.auprc > 0.5
