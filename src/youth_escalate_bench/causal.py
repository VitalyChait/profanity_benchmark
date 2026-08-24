"""Causal prefix and conversation topology utilities."""

from youth_escalate_bench.schemas.inference import (
    InferenceRequest,
    PlatformStyle,
    TaskType,
    TurnRecord,
)
from youth_escalate_bench.schemas.labels import AnnotationRecord, Severity, is_actionable


def build_inference_requests(
    conversation_id: str,
    turns: list[TurnRecord],
    benchmark_version: str,
    platform_style: PlatformStyle,
    language_mode: str,
    task: TaskType,
    labels: list[AnnotationRecord] | None = None,
) -> list[InferenceRequest]:
    """Build one causal-prefix request per turn (no future-turn exposure)."""
    requests: list[InferenceRequest] = []
    for i in range(len(turns)):
        prefix = turns[: i + 1]
        req = InferenceRequest(
            benchmark_version=benchmark_version,
            conversation_id=conversation_id,
            current_turn_id=prefix[-1].turn_id,
            platform_style=platform_style,
            language_mode=language_mode,
            turns=prefix,
            task=task,
        )
        requests.append(req)
    return requests


def gold_onset_turn_id(labels: list[AnnotationRecord]) -> str | None:
    """First turn with adjudicated actionable severity (severity >= 2)."""
    for label in labels:
        if is_actionable(label.severity):
            return label.turn_id
    return None


def validate_no_future_evidence(request: InferenceRequest, output_evidence_ids: list[str]) -> bool:
    visible = request.visible_turn_ids()
    return all(tid in visible for tid in output_evidence_ids)


def severity_at_turn(labels: list[AnnotationRecord], turn_id: str) -> Severity | None:
    for label in labels:
        if label.turn_id == turn_id:
            return label.severity
    return None
