"""Onset detection and forecasting metrics."""

from dataclasses import dataclass

from youth_escalate_bench.schemas.labels import AnnotationRecord, is_actionable


@dataclass
class OnsetMetrics:
    conversations_with_onset: int
    detected_count: int
    detection_rate: float
    median_delay: float | None
    delays: list[int]
    missed: int


def gold_onset(labels: list[AnnotationRecord], conversation_id: str) -> str | None:
    conv_labels = [lab for lab in labels if lab.conversation_id == conversation_id]
    for label in conv_labels:
        if is_actionable(label.severity):
            return label.turn_id
    return None


def turn_order(labels: list[AnnotationRecord], conversation_id: str) -> list[str]:
    conv_labels = [lab for lab in labels if lab.conversation_id == conversation_id]
    return [lab.turn_id for lab in conv_labels]


def compute_onset_metrics(
    labels: list[AnnotationRecord],
    predictions: dict[tuple[str, str], float],
    threshold: float = 0.5,
) -> OnsetMetrics:
    """Time-to-detection from threshold-crossing after gold onset."""
    conversation_ids = {lab.conversation_id for lab in labels}
    delays: list[int] = []
    missed = 0
    with_onset = 0

    for conv_id in conversation_ids:
        onset_turn = gold_onset(labels, conv_id)
        if onset_turn is None:
            continue
        with_onset += 1
        order = turn_order(labels, conv_id)
        if onset_turn not in order:
            continue
        onset_idx = order.index(onset_turn)

        detected_at: int | None = None
        for i in range(onset_idx, len(order)):
            turn_id = order[i]
            prob = predictions.get((conv_id, turn_id), 0.0)
            if prob >= threshold:
                detected_at = i - onset_idx
                break

        if detected_at is None:
            missed += 1
        else:
            delays.append(detected_at)

    detected = len(delays)
    rate = detected / with_onset if with_onset else 0.0
    median = sorted(delays)[len(delays) // 2] if delays else None

    return OnsetMetrics(
        conversations_with_onset=with_onset,
        detected_count=detected,
        detection_rate=rate,
        median_delay=median,
        delays=delays,
        missed=missed,
    )


def detection_recall_at_lag(
    labels: list[AnnotationRecord],
    predictions: dict[tuple[str, str], float],
    max_lag: int,
    threshold: float = 0.5,
) -> dict[int, float]:
    """Recall at lag 0, 1, 2 turns after gold onset."""
    recalls: dict[int, float] = {}
    conversation_ids = {lab.conversation_id for lab in labels}
    with_onset = sum(1 for c in conversation_ids if gold_onset(labels, c) is not None)

    if with_onset == 0:
        return {lag: 0.0 for lag in range(max_lag + 1)}

    for lag in range(max_lag + 1):
        detected = 0
        for conv_id in conversation_ids:
            onset_turn = gold_onset(labels, conv_id)
            if onset_turn is None:
                continue
            order = turn_order(labels, conv_id)
            onset_idx = order.index(onset_turn)
            check_idx = min(onset_idx + lag, len(order) - 1)
            for i in range(onset_idx, check_idx + 1):
                if predictions.get((conv_id, order[i]), 0.0) >= threshold:
                    detected += 1
                    break
        recalls[lag] = detected / with_onset

    return recalls
