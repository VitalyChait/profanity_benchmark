"""Autonomous linguistic verification and classification agent (Phase 7.2)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from youth_escalate_bench.agents.scout import SlangCandidate
from youth_escalate_bench.external.profanity_sources import ProfanityDatabase, ProfanityTerm


@dataclass
class VerificationResult:
    term: str
    is_profane_or_toxic: bool
    severity: int
    categories: list[str]
    rationale: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "is_profane_or_toxic": self.is_profane_or_toxic,
            "severity": self.severity,
            "categories": self.categories,
            "rationale": self.rationale,
            "confidence": self.confidence,
        }


class VerifierAgent:
    """Classifies scouted candidates into semantic toxicity categories and severity levels."""

    def __init__(self, database: ProfanityDatabase | None = None) -> None:
        self.db = database or ProfanityDatabase()

    def verify_candidate(self, candidate: SlangCandidate) -> VerificationResult:
        """Analyze term text, meaning, and usage example to classify toxicity."""
        text = f"{candidate.term} {candidate.meaning} {candidate.example}".lower()

        # Check existing known database
        existing = self.db.lookup(candidate.term)
        if existing:
            return VerificationResult(
                term=candidate.term,
                is_profane_or_toxic=True,
                severity=existing.severity,
                categories=existing.categories,
                rationale="Matched existing verified entry in unified profanity database.",
                confidence=0.98,
            )

        # High-confidence slur / hate speech patterns
        slur_cues = [
            "hate speech",
            "racial slur",
            "homophobic",
            "transphobic",
            "derogatory term for",
            "ethnic slur",
        ]
        for cue in slur_cues:
            if cue in text:
                return VerificationResult(
                    term=candidate.term,
                    is_profane_or_toxic=True,
                    severity=4,
                    categories=["slur_hate_speech"],
                    rationale=f"Definition contains explicit hate speech cue: '{cue}'.",
                    confidence=0.95,
                )

        # Sexual vulgarity patterns
        sexual_cues = [
            "sexual",
            "penis",
            "vagina",
            "anal",
            "blowjob",
            "fuck",
            "masturbat",
            "cum",
            "porn",
        ]
        for cue in sexual_cues:
            if re.search(r"\b" + cue, text):
                return VerificationResult(
                    term=candidate.term,
                    is_profane_or_toxic=True,
                    severity=3,
                    categories=["offensive_sexual"],
                    rationale=f"Definition contains sexual vulgarity indicator: '{cue}'.",
                    confidence=0.90,
                )

        # Harassment / Insult cues
        insult_cues = [
            "insult",
            "offensive",
            "derogatory",
            "stupid person",
            "idiot",
            "ugly",
            "annoying person",
            "kill yourself",
            "die",
        ]
        for cue in insult_cues:
            if cue in text:
                sev = 3 if "kill" in cue or "die" in cue else 2
                return VerificationResult(
                    term=candidate.term,
                    is_profane_or_toxic=True,
                    severity=sev,
                    categories=["derogatory_insult"],
                    rationale=f"Definition indicates interpersonal insult/derogation: '{cue}'.",
                    confidence=0.85,
                )

        # Gaming toxicity cues
        gaming_cues = [
            "gaming",
            "gamer",
            "bot",
            "noob",
            "uninstall",
            "trash player",
            "diff",
            "feeding",
        ]
        for cue in gaming_cues:
            if cue in text:
                return VerificationResult(
                    term=candidate.term,
                    is_profane_or_toxic=True,
                    severity=2,
                    categories=["gaming_toxic"],
                    rationale=f"Definition indicates gaming community toxicity/banter: '{cue}'.",
                    confidence=0.80,
                )

        # Innocent youth slang (non-toxic neologisms)
        return VerificationResult(
            term=candidate.term,
            is_profane_or_toxic=False,
            severity=1,
            categories=["benign_youth_slang"],
            rationale="Term identified as benign colloquialism or adolescent neologism without overt harassment.",
            confidence=0.75,
        )

    def convert_to_profanity_term(
        self, res: VerificationResult, source: str
    ) -> ProfanityTerm | None:
        """Convert a toxic/profane verification result into a standardized ProfanityTerm."""
        if not res.is_profane_or_toxic:
            return None
        return ProfanityTerm(
            word=res.term,
            severity=res.severity,
            categories=res.categories,
            sources=[source],
        )
