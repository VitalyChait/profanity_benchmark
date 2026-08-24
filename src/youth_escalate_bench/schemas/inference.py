"""Inference request and model output contracts (plan.md Section 2)."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from youth_escalate_bench.schemas.taxonomy import (
    ESCALATION_STATES,
    HARM_TYPES,
    LANGUAGE_MODES,
    SEVERITY_LEVELS,
    TARGET_TYPES,
)


class PlatformStyle(StrEnum):
    GAMING_CHAT = "gaming_chat"
    GROUP_CHAT = "group_chat"
    DIRECT_MESSAGING = "direct_messaging"
    FORUM_THREAD = "forum_thread"


class TaskType(StrEnum):
    CURRENT_HARM = "current_harm"
    ONSET_DETECTION = "onset_detection"
    TWO_TURN_FORECAST = "two_turn_forecast"


class TurnRecord(BaseModel):
    turn_id: str
    speaker_id: str
    role: str
    text: str
    relative_time: str  # coarse relative time, not exact timestamp


class InferenceRequest(BaseModel):
    """Causal-prefix inference input. Future turns must never be included."""

    benchmark_version: str
    conversation_id: str
    current_turn_id: str
    platform_style: PlatformStyle
    language_mode: Annotated[str, Field(pattern="^(english|english_led_code_switch)$")]
    turns: Annotated[list[TurnRecord], Field(min_length=1)]
    task: TaskType

    @field_validator("language_mode")
    @classmethod
    def validate_language_mode(cls, v: str) -> str:
        if v not in LANGUAGE_MODES:
            raise ValueError(f"language_mode must be one of {LANGUAGE_MODES}")
        return v

    @model_validator(mode="after")
    def validate_causal_prefix(self) -> "InferenceRequest":
        turn_ids = [t.turn_id for t in self.turns]
        if self.current_turn_id not in turn_ids:
            raise ValueError("current_turn_id must appear in turns")
        current_idx = turn_ids.index(self.current_turn_id)
        if current_idx != len(self.turns) - 1:
            raise ValueError(
                "turns must be causal prefix only: current_turn_id must be the last turn"
            )
        if turn_ids[: current_idx + 1] != [t.turn_id for t in self.turns[: current_idx + 1]]:
            raise ValueError("turns must be ordered; only causal prefix is valid")
        return self

    def causal_prefix(self) -> list[TurnRecord]:
        """Return turns up to and including current_turn_id."""
        turn_ids = [t.turn_id for t in self.turns]
        idx = turn_ids.index(self.current_turn_id)
        return self.turns[: idx + 1]

    def visible_turn_ids(self) -> set[str]:
        return {t.turn_id for t in self.causal_prefix()}


class ModelOutput(BaseModel):
    """Strict JSON model output schema."""

    harm_probability: Annotated[float, Field(ge=0.0, le=1.0)]
    harm_types: Annotated[dict[str, float], Field(default_factory=dict)]
    severity_probabilities: Annotated[
        dict[str, float],
        Field(default_factory=lambda: {s: 0.0 for s in SEVERITY_LEVELS}),
    ]
    target_type: Annotated[dict[str, float], Field(default_factory=dict)]
    escalation_state: Annotated[dict[str, float], Field(default_factory=dict)]
    forecast_next_two_turns: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    evidence_turn_ids: Annotated[list[str], Field(default_factory=list)]
    abstain: bool = False

    @model_validator(mode="after")
    def validate_probabilities(self) -> "ModelOutput":
        for name, mapping, allowed in (
            ("harm_types", self.harm_types, HARM_TYPES),
            ("target_type", self.target_type, TARGET_TYPES),
            ("escalation_state", self.escalation_state, ESCALATION_STATES),
        ):
            for key in mapping:
                if key not in allowed:
                    raise ValueError(f"{name}: unknown key {key}")
            for val in mapping.values():
                if not 0.0 <= val <= 1.0:
                    raise ValueError(f"{name}: probabilities must be in [0,1]")

        sev_sum = sum(self.severity_probabilities.values())
        if abs(sev_sum - 1.0) > 1e-6:
            raise ValueError(f"severity_probabilities must sum to 1, got {sev_sum}")
        for key in self.severity_probabilities:
            if key not in SEVERITY_LEVELS:
                raise ValueError(f"severity_probabilities: unknown key {key}")
        return self

    @staticmethod
    def create_abstention_output() -> "ModelOutput":
        return ModelOutput(
            harm_probability=0.0,
            severity_probabilities={s: 1.0 / len(SEVERITY_LEVELS) for s in SEVERITY_LEVELS},
            abstain=True,
        )

    @classmethod
    def contract_keys(cls) -> tuple[str, ...]:
        return (
            "harm_probability",
            "harm_types",
            "severity_probabilities",
            "target_type",
            "escalation_state",
            "forecast_next_two_turns",
            "evidence_turn_ids",
            "abstain",
        )
