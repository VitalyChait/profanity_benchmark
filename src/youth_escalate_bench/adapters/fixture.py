"""Fixture adapter for tests and miniature E2E pipeline."""

import json
from pathlib import Path

from youth_escalate_bench.adapters.base import IngestAdapter
from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier, StoredTurn


class FixtureAdapter(IngestAdapter):
    """Loads normalized JSONL; source_id read from each record."""

    source_id = "fixture"

    def load(self, input_path: Path) -> list[ConversationRecord]:
        conversations: list[ConversationRecord] = []
        with input_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                tier = raw.get("source_tier", SourceTier.FIXTURE.value)
                turns = [
                    StoredTurn(
                        turn_id=t["turn_id"],
                        speaker_id=t.get("speaker_id", "sp"),
                        role=t.get("role", "peer"),
                        text=t["text"],
                        relative_time=t.get("relative_time", "t0"),
                        parent_turn_id=t.get("parent_turn_id"),
                    )
                    for t in raw["turns"]
                ]
                conversations.append(
                    ConversationRecord(
                        conversation_id=raw["conversation_id"],
                        source_id=raw.get("source_id", "fixture"),
                        source_tier=tier,
                        platform_style=raw.get("platform_style", "gaming_chat"),
                        language_mode=raw.get("language_mode", "english"),
                        benchmark_version=raw.get("benchmark_version", "0.1.0"),
                        turns=turns,
                        metadata=raw.get("metadata", {}),
                    )
                )
        return conversations
