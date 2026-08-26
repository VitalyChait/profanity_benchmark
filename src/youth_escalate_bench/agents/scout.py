"""Autonomous slang and neologism scout agent (Phase 7.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from youth_escalate_bench.external.urban_dictionary import UrbanDictionaryClient


@dataclass
class SlangCandidate:
    """A newly scouted candidate term from online corpora or slang dictionaries."""

    term: str
    meaning: str
    example: str
    source: str
    contributor: str | None = None
    date: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "meaning": self.meaning,
            "example": self.example,
            "source": self.source,
            "contributor": self.contributor,
            "date": self.date,
        }


class ScoutAgent:
    """Continuous scout querying live Urban Dictionary and youth internet sources."""

    def __init__(self, client: UrbanDictionaryClient | None = None) -> None:
        self.client = client or UrbanDictionaryClient()

    def scout_random_slang(self, limit: int = 10) -> list[SlangCandidate]:
        """Fetch random candidates from Urban Dictionary."""
        defs = self.client.get_random(limit=limit)
        candidates: list[SlangCandidate] = []
        for d in defs:
            if not d.word or len(d.word) < 2:
                continue
            candidates.append(
                SlangCandidate(
                    term=d.word.strip().lower(),
                    meaning=d.meaning,
                    example=d.example,
                    source="urban_dictionary",
                    contributor=d.contributor,
                    date=d.date,
                )
            )
        return candidates

    def scout_targeted_terms(self, terms: list[str]) -> list[SlangCandidate]:
        """Query specific slang terms to retrieve their colloquial meanings and examples."""
        candidates: list[SlangCandidate] = []
        for t in terms:
            defs = self.client.search(term=t, strict=True, limit=2)
            if not defs:
                defs = self.client.search(term=t, strict=False, limit=1)
            for d in defs:
                candidates.append(
                    SlangCandidate(
                        term=d.word.strip().lower(),
                        meaning=d.meaning,
                        example=d.example,
                        source="urban_dictionary",
                        contributor=d.contributor,
                        date=d.date,
                    )
                )
        return candidates
