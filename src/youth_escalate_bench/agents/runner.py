"""Autonomous agentic discovery loop orchestrator (Phase 7.5)."""

from __future__ import annotations

import re
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

_DISCOVERY_RUN_RE = re.compile(
    r"^## Discovery Run: `([^`]+)`(?:\s+\(same for last (\d+) runs\))?\s*$"
)
_DEFAULT_DIGEST_HEADER = (
    "# Autonomous Agentic Discovery Digest\n\n"
    "Chronological audit log of dynamically discovered slang, profanity, and algospeak.\n\n"
    "---"
)


def _parse_digest_entries(text: str) -> tuple[str, list[tuple[str, int, str]]]:
    """Split digest markdown into header prefix and (timestamp, count, body) entries."""
    prefix_lines: list[str] = []
    entries: list[tuple[str, int, str]] = []
    current_ts: str | None = None
    current_count = 1
    current_body_lines: list[str] = []

    for line in text.splitlines():
        match = _DISCOVERY_RUN_RE.match(line)
        if match:
            if current_ts is not None:
                entries.append((current_ts, current_count, "\n".join(current_body_lines).strip()))
            current_ts = match.group(1)
            current_count = int(match.group(2)) if match.group(2) else 1
            current_body_lines = []
        elif current_ts is None:
            prefix_lines.append(line)
        else:
            current_body_lines.append(line)

    if current_ts is not None:
        entries.append((current_ts, current_count, "\n".join(current_body_lines).strip()))

    prefix = "\n".join(prefix_lines).strip() or _DEFAULT_DIGEST_HEADER
    return prefix, entries


def _merge_consecutive_entries(
    entries: list[tuple[str, int, str]],
) -> list[tuple[str, int, str]]:
    """Collapse adjacent discovery runs with identical result bodies."""
    merged: list[tuple[str, int, str]] = []
    for ts, count, body in entries:
        if merged and merged[-1][2] == body:
            _, prev_count, _ = merged[-1]
            merged[-1] = (ts, prev_count + count, body)
        else:
            merged.append((ts, count, body))
    return merged


def _format_digest_document(prefix: str, entries: list[tuple[str, int, str]]) -> str:
    """Format digest header and entries back into markdown."""
    blocks: list[str] = []
    for ts, count, body in entries:
        suffix = f" (same for last {count} runs)" if count > 1 else ""
        heading = f"## Discovery Run: `{ts}`{suffix}"
        blocks.append(f"{heading}\n\n{body}" if body else heading)
    return prefix.rstrip() + "\n\n" + "\n\n\n".join(blocks) + "\n"


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
        same_as_previous = self._append_to_digest(candidates, verified_results, newly_added_terms)

        logger.info(
            "discovery_cycle_completed",
            candidates_scouted=len(candidates),
            new_terms_added=len(newly_added_terms),
            same_as_previous=same_as_previous,
        )

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "candidates_count": len(candidates),
            "new_terms_added": newly_added_terms,
            "contrastive_pairs_count": len(contrastive_pairs),
            "same_as_previous": same_as_previous,
        }

    def _append_to_digest(
        self,
        candidates: list[Any],
        verified: list[Any],
        newly_added: list[str],
    ) -> bool:
        """Write an entry in reports/agentic_discovery_digest.md, collapsing consecutive identical runs.

        Returns True when the new run matches the immediately preceding digest entry.
        """
        now_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        body_lines = [
            f"- **Candidates Scouted:** {len(candidates)}",
            f"- **New Profanity/Slur Terms Added:** {len(newly_added)}",
        ]

        if newly_added:
            body_lines.append("")
            body_lines.append("### Newly Ingested Terms")
            body_lines.append("| Term | Severity | Category | Rationale |")
            body_lines.append("| :--- | :---: | :--- | :--- |")
            for res in verified:
                if res.term in newly_added:
                    body_lines.append(
                        f"| `{res.term}` | Level {res.severity} | {', '.join(res.categories)} | {res.rationale} |"
                    )

        new_body = "\n".join(body_lines).strip()
        self.digest_path.parent.mkdir(parents=True, exist_ok=True)

        if self.digest_path.exists():
            prefix, entries = _parse_digest_entries(self.digest_path.read_text(encoding="utf-8"))
        else:
            prefix, entries = _DEFAULT_DIGEST_HEADER, []

        same_as_previous = bool(entries and entries[-1][2] == new_body)
        entries.append((now_utc, 1, new_body))
        merged_entries = _merge_consecutive_entries(entries)
        self.digest_path.write_text(
            _format_digest_document(prefix, merged_entries), encoding="utf-8"
        )
        return same_as_previous
