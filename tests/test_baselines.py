"""Baseline scorer tests."""

from youth_escalate_bench.baselines.scorers import build_default_scorers
from youth_escalate_bench.evaluation.conditions import ContextCondition, apply_context_condition
from youth_escalate_bench.schemas.inference import (
    InferenceRequest,
    PlatformStyle,
    TaskType,
    TurnRecord,
)


def _request(text: str, prefix: list[str] | None = None) -> InferenceRequest:
    texts = prefix or [text]
    turns = [
        TurnRecord(turn_id=f"t{i}", speaker_id="s", role="peer", text=t, relative_time=f"t{i}")
        for i, t in enumerate(texts)
    ]
    return InferenceRequest(
        benchmark_version="0.1.0",
        conversation_id="c1",
        current_turn_id=turns[-1].turn_id,
        platform_style=PlatformStyle.GAMING_CHAT,
        language_mode="english",
        turns=turns,
        task=TaskType.CURRENT_HARM,
    )


def test_lexicon_detects_trash():
    scorers = build_default_scorers("configs/profanity_lexicon.txt")
    out = scorers["lexicon_raw"].predict(_request("you are trash kid"))
    assert out.harm_probability > 0.3


def test_context_condition_turn_only():
    req = _request("ok", prefix=["you are trash", "lol"])
    trimmed = apply_context_condition(req, ContextCondition.CURRENT_TURN_ONLY)
    assert len(trimmed.turns) == 1
    assert trimmed.turns[0].text == "lol"


def test_full_context_scores_higher():
    scorers = build_default_scorers("configs/profanity_lexicon.txt")
    req = _request("lol", prefix=["you are trash kid", "lol"])
    turn_only = apply_context_condition(req, ContextCondition.CURRENT_TURN_ONLY)
    full = apply_context_condition(req, ContextCondition.FULL_PREFIX)
    s_turn = scorers["lexicon_full_context"].predict(turn_only).harm_probability
    s_full = scorers["lexicon_full_context"].predict(full).harm_probability
    assert s_full >= s_turn
