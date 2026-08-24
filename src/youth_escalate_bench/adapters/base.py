"""Base ingest adapter interface and normalization utilities."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from youth_escalate_bench.schemas.conversation import ConversationRecord, StoredTurn


class IngestAdapter(ABC):
    source_id: str

    @abstractmethod
    def load(self, input_path: Path) -> list[ConversationRecord]:
        """Load raw source records into normalized conversation records."""

    def validate_source_approved(self, approved_ids: set[str]) -> None:
        if self.source_id not in approved_ids:
            raise PermissionError(
                f"Source '{self.source_id}' not approved for ingest. "
                "Complete license audit in configs/source_registry.yaml before ingestion."
            )

    @staticmethod
    def normalize_turns(raw_turns: list[dict[str, Any]]) -> list[StoredTurn]:
        """Convert raw turn dicts to validated StoredTurn objects with sensible defaults."""
        turns: list[StoredTurn] = []
        for idx, t in enumerate(raw_turns):
            turn_id = str(t.get("turn_id") or t.get("id") or f"t{idx+1}")
            speaker_id = str(t.get("speaker_id") or t.get("user") or t.get("author") or t.get("speaker") or f"user_{idx%2+1}")
            role = str(t.get("role") or ("user" if idx % 2 == 0 else "peer"))
            text = str(t.get("text") or t.get("content") or t.get("body") or t.get("message") or "").strip()
            rel_time = str(t.get("relative_time") or t.get("timestamp") or f"+{idx*5}s")
            parent_id = t.get("parent_turn_id") or t.get("parent_id") or t.get("reply_to")
            if parent_id is not None:
                parent_id = str(parent_id)

            if text:  # Filter out empty turns
                turns.append(
                    StoredTurn(
                        turn_id=turn_id,
                        speaker_id=speaker_id,
                        role=role,
                        text=text,
                        relative_time=rel_time,
                        parent_turn_id=parent_id,
                    )
                )
        return turns
