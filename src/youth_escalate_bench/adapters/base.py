"""Base ingest adapter interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from youth_escalate_bench.schemas.conversation import ConversationRecord


class IngestAdapter(ABC):
    source_id: str

    @abstractmethod
    def load(self, input_path: Path) -> list[ConversationRecord]:
        """Load raw source records into normalized conversation records."""

    def validate_source_approved(self, approved_ids: set[str]) -> None:
        if self.source_id not in approved_ids:
            raise PermissionError(
                f"Source {self.source_id} not approved for ingest. "
                "Complete license audit before ingestion."
            )
