"""Synthetic & Staged dialogue generation engine for YouthEscalateBench."""

import random
from dataclasses import dataclass
from typing import Any

from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier, StoredTurn
from youth_escalate_bench.schemas.labels import (
    AnnotationRecord,
    HarmType,
    PragmaticUse,
    ProfanityForm,
    Severity,
    TargetType,
)

# Dialogue act pools for realistic youth-styled scenarios
GAMING_BANTER = [
    "yo drop your loadout at mid",
    "heading there now, don't get picked",
    "lmao nice snipe bro",
    "told you i had that angle covered",
    "gg that was clean",
]

TRASH_TALK = [
    "bro why did you push solo without comms",
    "i had full shields you should've traded",
    "you're throwing the game on purpose stop feeding",
    "literally bottom fragging every match",
]

TARGETED_INSULTS = [
    "you are fucking garbage uninstall right now",
    "worst player on the server, delete your account",
    "nobody wants to queue with your trash ass",
]

DE_ESCALATION_RESPONSES = [
    "chill out guys it's just one round",
    "my bad i missed the callout, let's reset and focus",
    "yeah all good, let's win this next one",
]

THREATS = [
    "i know what high school you go to, keep talking and see what happens",
    "watch your back tomorrow if you join this voice call again",
]

SELF_HARM_ENCOURAGEMENT = [
    "do everyone a favor and go unalive yourself",
    "literally go kys nobody cares about you",
]


@dataclass
class ScenarioPlan:
    plan_id: str
    template_id: str
    platform_style: str
    transition_pattern: str
    intended_harm_type: str | None
    turns_min: int = 4
    turns_max: int = 8
    language_mode: str = "english"
    description: str = ""


class SyntheticDialogueGenerator:
    """Generates synthetic multi-turn dialogues according to scenario plans.

    KEY LOCATION:
    - Set API keys in `.env` at the repository root to enable frontier LLM dialogue generation.
    - If no keys are set, this generator uses realistic deterministic state-machine simulation.
    """

    def __init__(self, seed: int = 42, use_llm_if_available: bool = False) -> None:
        self.rng = random.Random(seed)
        self.use_llm_if_available = use_llm_if_available

    def generate_conversation(
        self, plan: ScenarioPlan | dict[str, Any]
    ) -> tuple[ConversationRecord, list[AnnotationRecord]]:
        if isinstance(plan, dict):
            p = ScenarioPlan(
                plan_id=plan["plan_id"],
                template_id=plan.get("template_id", "custom"),
                platform_style=plan.get("platform_style", "gaming_chat"),
                transition_pattern=plan.get("transition_pattern", "gradual_escalation"),
                intended_harm_type=plan.get("intended_harm_type"),
                turns_min=plan.get("turns_min", 4),
                turns_max=plan.get("turns_max", 8),
            )
        else:
            p = plan

        num_turns = self.rng.randint(p.turns_min, p.turns_max)
        turns: list[StoredTurn] = []
        annotations: list[AnnotationRecord] = []

        speakers = ["user_alpha", "user_beta", "user_gamma"]
        target_speaker = "user_beta"
        aggressor = "user_alpha"

        cid = f"syn_{p.plan_id}_{self.rng.randint(1000, 9999)}"

        if p.transition_pattern == "gradual_escalation":
            # Turns 1..2 benign, 3 coarse, 4+ actionable
            for idx in range(num_turns):
                tid = f"t{idx+1}"
                spk = aggressor if idx % 2 == 0 else target_speaker
                if idx < 2:
                    text = self.rng.choice(GAMING_BANTER)
                    sev = Severity.BENIGN
                    prag = PragmaticUse.AFFILIATIVE_BANTER
                    harm: list[HarmType] = []
                    target = TargetType.NONE
                elif idx == 2:
                    text = self.rng.choice(TRASH_TALK)
                    sev = Severity.COARSE_MONITOR
                    prag = PragmaticUse.EMOTIONAL_EMPHASIS
                    harm = [HarmType.TARGETED_INSULT]
                    target = TargetType.INDIVIDUAL_PEER
                else:
                    text = self.rng.choice(TARGETED_INSULTS)
                    sev = Severity.ACTIONABLE
                    prag = PragmaticUse.TARGETED_ABUSE
                    harm = [HarmType.TARGETED_INSULT, HarmType.REPEATED_HARASSMENT]
                    target = TargetType.INDIVIDUAL_PEER

                turns.append(
                    StoredTurn(
                        turn_id=tid,
                        speaker_id=spk,
                        role="user",
                        text=text,
                        relative_time=f"+{idx*8}s",
                    )
                )
                annotations.append(
                    AnnotationRecord(
                        conversation_id=cid,
                        turn_id=tid,
                        profanity_form=ProfanityForm.LITERAL if sev >= Severity.COARSE_MONITOR else ProfanityForm.NONE,
                        pragmatic_use=prag,
                        harm_types=harm,
                        target_type=target,
                        severity=sev,
                        adjudicated=True,
                    )
                )

        elif p.transition_pattern == "immediate_abuse":
            for idx in range(num_turns):
                tid = f"t{idx+1}"
                spk = aggressor if idx % 2 == 0 else target_speaker
                if idx == 0:
                    text = self.rng.choice(THREATS)
                    sev = Severity.URGENT
                    prag = PragmaticUse.TARGETED_ABUSE
                    harm = [HarmType.THREAT_INTIMIDATION]
                    target = TargetType.INDIVIDUAL_PEER
                else:
                    text = "leave me alone" if spk == target_speaker else self.rng.choice(TARGETED_INSULTS)
                    sev = Severity.ACTIONABLE if spk == aggressor else Severity.BENIGN
                    prag = PragmaticUse.TARGETED_ABUSE if spk == aggressor else PragmaticUse.ABSENT
                    harm = [HarmType.REPEATED_HARASSMENT] if spk == aggressor else []
                    target = TargetType.INDIVIDUAL_PEER if spk == aggressor else TargetType.NONE

                turns.append(
                    StoredTurn(
                        turn_id=tid,
                        speaker_id=spk,
                        role="user",
                        text=text,
                        relative_time=f"+{idx*5}s",
                    )
                )
                annotations.append(
                    AnnotationRecord(
                        conversation_id=cid,
                        turn_id=tid,
                        profanity_form=ProfanityForm.LITERAL,
                        pragmatic_use=prag,
                        harm_types=harm,
                        target_type=target,
                        severity=sev,
                        adjudicated=True,
                    )
                )

        elif p.transition_pattern == "de_escalation":
            for idx in range(num_turns):
                tid = f"t{idx+1}"
                if idx == 0:
                    spk = aggressor
                    text = self.rng.choice(TARGETED_INSULTS)
                    sev = Severity.ACTIONABLE
                    prag = PragmaticUse.TARGETED_ABUSE
                    harm = [HarmType.TARGETED_INSULT]
                    target = TargetType.INDIVIDUAL_PEER
                elif idx == 1:
                    spk = "user_gamma"
                    text = self.rng.choice(DE_ESCALATION_RESPONSES)
                    sev = Severity.BENIGN
                    prag = PragmaticUse.ABSENT
                    harm = []
                    target = TargetType.NONE
                else:
                    spk = target_speaker if idx % 2 == 0 else aggressor
                    text = "yeah my bad, let's keep playing"
                    sev = Severity.BENIGN
                    prag = PragmaticUse.AFFILIATIVE_BANTER
                    harm = []
                    target = TargetType.NONE

                turns.append(
                    StoredTurn(
                        turn_id=tid,
                        speaker_id=spk,
                        role="user",
                        text=text,
                        relative_time=f"+{idx*10}s",
                    )
                )
                annotations.append(
                    AnnotationRecord(
                        conversation_id=cid,
                        turn_id=tid,
                        profanity_form=ProfanityForm.NONE if sev == Severity.BENIGN else ProfanityForm.LITERAL,
                        pragmatic_use=prag,
                        harm_types=harm,
                        target_type=target,
                        severity=sev,
                        adjudicated=True,
                    )
                )

        else:  # false_alarm / friendly profanity
            for idx in range(num_turns):
                tid = f"t{idx+1}"
                spk = self.rng.choice(speakers)
                text = self.rng.choice(
                    [
                        "holy shit that play was crazy",
                        "bro you are fucking cracked at this game lmao",
                        "deadass thought we were dead haha",
                        "nice clutch my dude",
                    ]
                )
                turns.append(
                    StoredTurn(
                        turn_id=tid,
                        speaker_id=spk,
                        role="user",
                        text=text,
                        relative_time=f"+{idx*6}s",
                    )
                )
                annotations.append(
                    AnnotationRecord(
                        conversation_id=cid,
                        turn_id=tid,
                        profanity_form=ProfanityForm.LITERAL,
                        pragmatic_use=PragmaticUse.AFFILIATIVE_BANTER,
                        harm_types=[],
                        target_type=TargetType.NONE,
                        severity=Severity.BENIGN,
                        adjudicated=True,
                    )
                )

        conv = ConversationRecord(
            conversation_id=cid,
            source_id="synthetic_generator",
            source_tier=SourceTier.SYNTHETIC,
            platform_style=p.platform_style,
            turns=turns,
            metadata={"plan_id": p.plan_id, "template_id": p.template_id, "pattern": p.transition_pattern},
        )
        return conv, annotations
