"""Tests for Pydantic inference and output contracts."""

import pytest
from pydantic import ValidationError

from youth_escalate_bench.schemas.inference import (
    InferenceRequest,
    ModelOutput,
    PlatformStyle,
    TaskType,
    TurnRecord,
)
from youth_escalate_bench.schemas.taxonomy import SEVERITY_LEVELS


def _turn(turn_id: str, text: str = "hello") -> TurnRecord:
    return TurnRecord(
        turn_id=turn_id,
        speaker_id=f"sp_{turn_id}",
        role="peer",
        text=text,
        relative_time="t0",
    )


def test_inference_request_causal_prefix_valid():
    turns = [_turn("t1"), _turn("t2"), _turn("t3")]
    req = InferenceRequest(
        benchmark_version="0.1.0",
        conversation_id="c1",
        current_turn_id="t2",
        platform_style=PlatformStyle.GAMING_CHAT,
        language_mode="english",
        turns=turns[:2],
        task=TaskType.CURRENT_HARM,
    )
    prefix = req.causal_prefix()
    assert len(prefix) == 2
    assert prefix[-1].turn_id == "t2"


def test_inference_request_rejects_missing_current_turn():
    turns = [_turn("t1")]
    with pytest.raises(ValidationError):
        InferenceRequest(
            benchmark_version="0.1.0",
            conversation_id="c1",
            current_turn_id="t2",
            platform_style=PlatformStyle.GROUP_CHAT,
            language_mode="english",
            turns=turns,
            task=TaskType.CURRENT_HARM,
        )


def test_inference_request_rejects_future_turns():
    turns = [_turn("t1"), _turn("t2"), _turn("t3")]
    with pytest.raises(ValidationError):
        InferenceRequest(
            benchmark_version="0.1.0",
            conversation_id="c1",
            current_turn_id="t2",
            platform_style=PlatformStyle.GROUP_CHAT,
            language_mode="english",
            turns=turns,
            task=TaskType.CURRENT_HARM,
        )


def test_model_output_valid():
    out = ModelOutput(
        harm_probability=0.5,
        harm_types={"targeted_insult": 0.3},
        severity_probabilities={s: 0.25 for s in SEVERITY_LEVELS},
        target_type={"individual_peer": 0.8},
        escalation_state={"stable": 1.0},
        forecast_next_two_turns=0.1,
        evidence_turn_ids=["t1"],
    )
    assert out.harm_probability == 0.5


def test_model_output_severity_must_sum_to_one():
    with pytest.raises(ValidationError):
        ModelOutput(
            harm_probability=0.5,
            severity_probabilities={"benign": 0.5, "coarse_monitor": 0.3},
        )


def test_model_output_rejects_unknown_harm_type():
    with pytest.raises(ValidationError):
        ModelOutput(
            harm_probability=0.5,
            harm_types={"unknown_harm": 0.9},
            severity_probabilities={s: 0.25 for s in SEVERITY_LEVELS},
        )


def test_abstention_output():
    out = ModelOutput.create_abstention_output()
    assert out.abstain is True
    assert sum(out.severity_probabilities.values()) == 1.0
