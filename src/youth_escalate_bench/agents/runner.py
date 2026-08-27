"""Autonomous agentic discovery loop orchestrator (Phase 7.5)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from youth_escalate_bench.agents.generator import GeneratorAgent
from youth_escalate_bench.agents.scout import ScoutAgent
from youth_escalate_bench.agents.verifier import VerifierAgent
from youth_escalate_bench.external.profanity_sources import (
    ProfanityDatabase,
    sync_lexicon_files,
)

logger = structlog.get_logger()


class DiscoveryLoop:
    """End-to-end continuous agentic discovery cycle."""

    def __init__(
        self,
        db_path: Path | None = None,
        lexicon_txt_path: Path | None = None,
        digest_path: Path | None = None,
    ) -> None:
        self.db_path = db_path or Path("configs/lexicons/profanity_database.json")
        self.lexicon_txt_path = lexicon_txt_path or Path("configs/profanity_lexicon.txt")
        self.digest_path = digest_path or Path("reports/agentic_discovery_digest.md")
        self.db = ProfanityDatabase.load_json(self.db_path)
        self.scout = ScoutAgent()
        self.verifier = VerifierAgent(database=self.db)
        self.generator = GeneratorAgent()

    def run_discovery_cycle(
        self,
        target_terms: list[str] | None = None,
        random_limit: int = 5,
    ) -> dict[str, Any]:
        """Execute one complete discovery pass."""
        logger.info(
            "discovery_cycle_started",
            target_count=len(target_terms or []),
            random_limit=random_limit,
        )

        # 1. Scout candidates
        candidates = []
        if target_terms:
            candidates.extend(self.scout.scout_targeted_terms(target_terms))
        if random_limit > 0:
            candidates.extend(self.scout.scout_random_slang(limit=random_limit))

        # 2. Verify each candidate
        verified_results = []
        newly_added_terms = []
        contrastive_pairs = []

        for cand in candidates:
            res = self.verifier.verify_candidate(cand)
            verified_results.append(res)

            # 3. If toxic/profane, incorporate into database if new
            if res.is_profane_or_toxic and not self.db.is_profane(cand.term):
                p_term = self.verifier.convert_to_profanity_term(
                    res, source="urban_dictionary_agent"
                )
                if p_term:
                    self.db.terms[p_term.word] = p_term
                    newly_added_terms.append(p_term.word)

                    # 4. Generate contrastive minimal pair
                    pair = self.generator.generate_contrastive_pair(p_term.word)
                    contrastive_pairs.append(pair)

        # 5. Persist database & lexicon if new terms found
        if newly_added_terms:
            sync_lexicon_files(
                db=self.db,
                lexicon_txt_path=self.lexicon_txt_path,
                database_json_path=self.db_path,
            )

        # 6. Append to discovery digest
        self._append_to_digest(candidates, verified_results, newly_added_terms)

        logger.info(
            "discovery_cycle_completed",
            candidates_scouted=len(candidates),
            new_terms_added=len(newly_added_terms),
        )

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "candidates_count": len(candidates),
            "new_terms_added": newly_added_terms,
            "contrastive_pairs_count": len(contrastive_pairs),
        }

    def _append_to_digest(
        self,
        candidates: list[Any],
        verified: list[Any],
        newly_added: list[str],
    ) -> None:
        """Write an entry in reports/agentic_discovery_digest.md."""
        now_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            f"\n## Discovery Run: `{now_utc}`",
            "",
            f"- **Candidates Scouted:** {len(candidates)}",
            f"- **New Profanity/Slur Terms Added:** {len(newly_added)}",
            "",
        ]

        if newly_added:
            lines.append("### Newly Ingested Terms")
            lines.append("| Term | Severity | Category | Rationale |")
            lines.append("| :--- | :---: | :--- | :--- |")
            for res in verified:
                if res.term in newly_added:
                    lines.append(
                        f"| `{res.term}` | Level {res.severity} | {', '.join(res.categories)} | {res.rationale} |"
                    )
            lines.append("")

        self.digest_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.digest_path.exists():
            header = "# Autonomous Agentic Discovery Digest\n\nChronological audit log of dynamically discovered slang, profanity, and algospeak.\n\n---"
            self.digest_path.write_text(header + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
        else:
            with self.digest_path.open("a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
