"""Tests for synthetic dialogue generator."""

from youth_escalate_bench.generation.generator import ScenarioPlan, SyntheticDialogueGenerator
from youth_escalate_bench.schemas.labels import Severity


def test_synthetic_dialogue_gradual_escalation():
    gen = SyntheticDialogueGenerator(seed=42)
    plan = ScenarioPlan(
        plan_id="test_01",
        template_id="gradual_escalation_gaming",
        platform_style="gaming_chat",
        transition_pattern="gradual_escalation",
        intended_harm_type="targeted_insult",
        turns_min=4,
        turns_max=6,
    )
    conv, anns = gen.generate_conversation(plan)
    assert 4 <= len(conv.turns) <= 6
    assert len(anns) == len(conv.turns)
    # The last turn should be actionable
    assert anns[-1].severity >= Severity.ACTIONABLE


def test_synthetic_dialogue_false_alarm():
    gen = SyntheticDialogueGenerator(seed=42)
    plan = ScenarioPlan(
        plan_id="test_02",
        template_id="friendly_profanity_gaming",
        platform_style="gaming_chat",
        transition_pattern="false_alarm",
        intended_harm_type=None,
        turns_min=3,
        turns_max=5,
    )
    conv, anns = gen.generate_conversation(plan)
    assert all(a.severity == Severity.BENIGN for a in anns)
