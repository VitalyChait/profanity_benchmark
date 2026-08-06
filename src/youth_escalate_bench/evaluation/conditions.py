"""Context evaluation conditions (plan.md Section 6)."""

from enum import StrEnum

from youth_escalate_bench.schemas.inference import (
    InferenceRequest,
    PlatformStyle,
    TaskType,
    TurnRecord,
)


class ContextCondition(StrEnum):
    CURRENT_TURN_ONLY = "current_turn_only"
    PREV_PLUS_CURRENT = "prev_plus_current"
    FULL_PREFIX = "full_prefix"
    SHUFFLED_PREFIX = "shuffled_prefix"
    NO_SPEAKER_IDS = "no_speaker_ids"


def apply_context_condition(
    request: InferenceRequest,
    condition: ContextCondition,
    seed: int = 42,
) -> InferenceRequest:
    prefix = request.causal_prefix()
    current = prefix[-1]

    if condition == ContextCondition.CURRENT_TURN_ONLY:
        turns = [current]
    elif condition == ContextCondition.PREV_PLUS_CURRENT:
        turns = prefix[-2:] if len(prefix) >= 2 else prefix
    elif condition == ContextCondition.FULL_PREFIX:
        turns = prefix
    elif condition == ContextCondition.SHUFFLED_PREFIX:
        import random

        rng = random.Random(seed)
        prior = prefix[:-1]
        shuffled = prior.copy()
        rng.shuffle(shuffled)
        turns = shuffled + [current]
    elif condition == ContextCondition.NO_SPEAKER_IDS:
        turns = [
            TurnRecord(
                turn_id=t.turn_id,
                speaker_id="anonymous",
                role=t.role,
                text=t.text,
                relative_time=t.relative_time,
            )
            for t in prefix
        ]
    else:
        turns = prefix

    return InferenceRequest(
        benchmark_version=request.benchmark_version,
        conversation_id=request.conversation_id,
        current_turn_id=current.turn_id,
        platform_style=request.platform_style,
        language_mode=request.language_mode,
        turns=turns,
        task=request.task,
    )


def build_requests_for_conversation(
    conversation_id: str,
    turns: list[TurnRecord],
    benchmark_version: str,
    platform_style: PlatformStyle | str,
    language_mode: str,
    task: TaskType,
    condition: ContextCondition,
    seed: int = 42,
) -> list[InferenceRequest]:
    from youth_escalate_bench.causal import build_inference_requests
    from youth_escalate_bench.schemas.inference import PlatformStyle as PS

    ps = platform_style if isinstance(platform_style, PS) else PS(platform_style)
    base = build_inference_requests(
        conversation_id=conversation_id,
        turns=turns,
        benchmark_version=benchmark_version,
        platform_style=ps,
        language_mode=language_mode,
        task=task,
    )
    return [apply_context_condition(r, condition, seed=seed) for r in base]
