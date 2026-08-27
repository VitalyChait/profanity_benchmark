"""Stored conversation records for Parquet pipeline."""

from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, model_validator


class SourceTier(StrEnum):
    ORGANIC = "organic"
    STAGED = "staged"
    SYNTHETIC = "synthetic"
    FUNCTIONAL = "functional"
    LIVE = "live"
    FIXTURE = "fixture"


class StoredTurn(BaseModel):
    turn_id: str
    speaker_id: str
    role: str
    text: str
    relative_time: str
    parent_turn_id: str | None = None


class ConversationRecord(BaseModel):
    conversation_id: str
    source_id: str
    source_tier: SourceTier
    platform_style: str
    language_mode: str = "english"
    turns: Annotated[list[StoredTurn], Field(min_length=1)]
    benchmark_version: str = "0.1.2"
    metadata: Annotated[dict[str, Any], Field(default_factory=dict)]

    @model_validator(mode="after")
    def validate_turn_ids_unique(self) -> "ConversationRecord":
        ids = [t.turn_id for t in self.turns]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate turn_id in conversation")
        return self

    def turn_index(self, turn_id: str) -> int:
        for i, t in enumerate(self.turns):
            if t.turn_id == turn_id:
                return i
        raise KeyError(turn_id)

    def ordered_turn_ids(self) -> list[str]:
        return [t.turn_id for t in self.turns]
