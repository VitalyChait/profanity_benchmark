"""Detection metrics for benchmark evaluation."""

from dataclasses import dataclass


@dataclass
class BinaryMetrics:
    auroc: float | None
    auprc: float
    precision_at_recall_95: float | None
    recall_at_fpr_1pct: float | None
    threshold: float


def _rank_data(y_true: list[bool], y_score: list[float]) -> list[tuple[bool, float]]:
    return sorted(zip(y_true, y_score, strict=True), key=lambda x: x[1], reverse=True)


def auprc(y_true: list[bool], y_score: list[float]) -> float:
    if not y_true:
        return 0.0
    positives = sum(y_true)
    if positives == 0:
        return 0.0
    ranked = _rank_data(y_true, y_score)
    tp = 0
    fp = 0
    prev_recall = 0.0
    auc = 0.0
    for label, _ in ranked:
        if label:
            tp += 1
        else:
            fp += 1
        recall = tp / positives
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        auc += (recall - prev_recall) * precision
        prev_recall = recall
    return auc


def auroc(y_true: list[bool], y_score: list[float]) -> float | None:
    positives = sum(y_true)
    negatives = len(y_true) - positives
    if positives == 0 or negatives == 0:
        return None
    ranked = _rank_data(y_true, y_score)
    tp = 0
    fp = 0
    prev_tpr = 0.0
    prev_fpr = 0.0
    auc = 0.0
    for label, _ in ranked:
        if label:
            tp += 1
        else:
            fp += 1
        tpr = tp / positives
        fpr = fp / negatives
        auc += (fpr - prev_fpr) * (tpr + prev_tpr) / 2
        prev_tpr = tpr
        prev_fpr = fpr
    return auc


def precision_at_min_recall(
    y_true: list[bool],
    y_score: list[float],
    min_recall: float,
) -> float | None:
    positives = sum(y_true)
    if positives == 0:
        return None
    ranked = _rank_data(y_true, y_score)
    tp = 0
    fp = 0
    best_precision = None
    for label, _ in ranked:
        if label:
            tp += 1
        else:
            fp += 1
        recall = tp / positives
        if recall >= min_recall:
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            if best_precision is None or precision > best_precision:
                best_precision = precision
    return best_precision


def recall_at_max_fpr(
    y_true: list[bool],
    y_score: list[float],
    max_fpr: float,
) -> float | None:
    positives = sum(y_true)
    negatives = len(y_true) - positives
    if positives == 0 or negatives == 0:
        return None
    ranked = _rank_data(y_true, y_score)
    tp = 0
    fp = 0
    best_recall = 0.0
    for label, _ in ranked:
        if label:
            tp += 1
        else:
            fp += 1
        fpr = fp / negatives
        if fpr <= max_fpr:
            best_recall = max(best_recall, tp / positives)
    return best_recall


def compute_binary_metrics(
    y_true: list[bool],
    y_score: list[float],
    dev_threshold: float = 0.5,
) -> BinaryMetrics:
    return BinaryMetrics(
        auroc=auroc(y_true, y_score),
        auprc=auprc(y_true, y_score),
        precision_at_recall_95=precision_at_min_recall(y_true, y_score, 0.95),
        recall_at_fpr_1pct=recall_at_max_fpr(y_true, y_score, 0.01),
        threshold=dev_threshold,
    )
