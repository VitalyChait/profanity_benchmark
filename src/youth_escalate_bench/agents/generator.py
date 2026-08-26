"""Autonomous contrastive scenario and minimal-pair generator agent (Phase 7.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier, StoredTurn
from youth_escalate_bench.transforms.algospeak import apply_algospeak_transform


@dataclass
class ContrastivePair:
    term: str
    benign_turn: str
    hostile_turn: str
    transformed_hostile_turn: str
    transform_family: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "benign_turn": self.benign_turn,
            "hostile_turn": self.hostile_turn,
            "transformed_hostile_turn": self.transformed_hostile_turn,
            "transform_family": self.transform_family,
        }


class GeneratorAgent:
    """Generates contrastive minimal-pair conversations for newly discovered slang."""

    BENIGN_TEMPLATES = [
        "bro you are such a {term} haha that play was crazy",
        "lol that was totally {term}, good game",
        "my dude is literally {term} today, love this lobby",
        "stop being a {term} and come help us at mid",
    ]

    HOSTILE_TEMPLATES = [
        "you are an absolute {term} uninstall the game right now",
        "nobody wants you here you fucking {term}",
        "you're a worthless {term}, go kill yourself",
        "shut up you stupid {term}, i know where you live",
    ]

    def generate_contrastive_pair(
        self,
        term: str,
        template_idx: int = 0,
        transform_family: str = "leetspeak",
    ) -> ContrastivePair:
        """Create a paired benign vs hostile turn and apply algospeak mutation."""
        benign = self.BENIGN_TEMPLATES[template_idx % len(self.BENIGN_TEMPLATES)].format(term=term)
        hostile = self.HOSTILE_TEMPLATES[template_idx % len(self.HOSTILE_TEMPLATES)].format(term=term)

        # Apply algospeak evasion transform
        transformed = apply_algospeak_transform(
            hostile,
            transform_family=transform_family,
            seed=42,
        )

        return ContrastivePair(
            term=term,
            benign_turn=benign,
            hostile_turn=hostile,
            transformed_hostile_turn=transformed,
            transform_family=transform_family,
        )

    def create_synthetic_conversation(
        self,
        conversation_id: str,
        term: str,
        is_hostile: bool,
    ) -> ConversationRecord:
        """Create a valid ConversationRecord containing the term."""
        turn_text = (
            self.HOSTILE_TEMPLATES[0].format(term=term)
            if is_hostile
            else self.BENIGN_TEMPLATES[0].format(term=term)
        )
        return ConversationRecord(
            conversation_id=conversation_id,
            source_id="agentic_generator",
            source_tier=SourceTier.SYNTHETIC,
            platform_style="gaming_chat",
            turns=[
                StoredTurn(turn_id="t1", speaker_id="u1", role="user", relative_time="0s", text="yo what are you doing"),
                StoredTurn(turn_id="t2", speaker_id="u2", role="user", relative_time="5s", text=turn_text),
            ],
            metadata={"discovered_term": term, "is_hostile": is_hostile},
        )
