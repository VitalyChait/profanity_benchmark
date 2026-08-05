"""Tests for causal-prefix construction and no-future-turn exposure."""

from youth_escalate_bench.causal import (
    build_inference_requests,
    gold_onset_turn_id,
    validate_no_future_evidence,
)
from youth_escalate_bench.schemas.inference import PlatformStyle, TaskType, TurnRecord
from youth_escalate_bench.schemas.labels import AnnotationRecord, HarmType, Severity


def _turn(turn_id: str) -> TurnRecord:
    return TurnRecord(
        turn_id=turn_id,
        speaker_id=f"sp_{turn_id}",
        role="peer",
        text=f"text {turn_id}",
        relative_time="t0",
    )


def test_build_inference_requests_no_future_turns():
    turns = [_turn("t1"), _turn("t2"), _turn("t3")]
    requests = build_inference_requests(
        conversation_id="c1",
        turns=turns,
        benchmark_version="0.1.0",
        platform_style=PlatformStyle.DIRECT_MESSAGING,
        language_mode="english",
        task=TaskType.CURRENT_HARM,
    )
    assert len(requests) == 3
    for i, req in enumerate(requests):
        assert len(req.turns) == i + 1
        assert req.current_turn_id == turns[i].turn_id
        visible = req.visible_turn_ids()
        assert visible == {t.turn_id for t in turns[:i + 1]}


def test_validate_no_future_evidence():
    turns = [_turn("t1"), _turn("t2")]
    requests = build_inference_requests(
        conversation_id="c1",
        turns=turns,
        benchmark_version="0.1.0",
        platform_style=PlatformStyle.FORUM_THREAD,
        language_mode="english",
        task=TaskType.ONSET_DETECTION,
    )
    assert validate_no_future_evidence(requests[0], ["t1"])
    assert not validate_no_future_evidence(requests[0], ["t2"])


def test_gold_onset_turn_id():
    labels = [
        AnnotationRecord(
            conversation_id="c1",
            turn_id="t1",
            severity=Severity.BENIGN,
        ),
        AnnotationRecord(
            conversation_id="c1",
            turn_id="t2",
            severity=Severity.COARSE_MONITOR,
        ),
        AnnotationRecord(
            conversation_id="c1",
            turn_id="t3",
            severity=Severity.ACTIONABLE,
            harm_types=[HarmType.TARGETED_INSULT],
        ),
    ]
    assert gold_onset_turn_id(labels) == "t3"
