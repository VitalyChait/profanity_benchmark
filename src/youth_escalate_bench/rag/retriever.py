"""Slang & Pragmatics RAG Retriever with token compression and multi-source grounding."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from youth_escalate_bench.external.urban_dictionary import UrbanDictionaryClient
from youth_escalate_bench.schemas.inference import InferenceRequest

# Standard English stop words to exclude from slang candidate extraction
STOP_WORDS: set[str] = {
    "about",
    "after",
    "again",
    "against",
    "all",
    "also",
    "and",
    "any",
    "are",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "can",
    "cant",
    "cannot",
    "chat",
    "come",
    "could",
    "day",
    "did",
    "does",
    "dont",
    "down",
    "during",
    "each",
    "even",
    "every",
    "few",
    "for",
    "from",
    "game",
    "get",
    "give",
    "going",
    "good",
    "got",
    "had",
    "has",
    "have",
    "her",
    "here",
    "hers",
    "him",
    "his",
    "how",
    "into",
    "its",
    "just",
    "know",
    "like",
    "look",
    "make",
    "many",
    "may",
    "more",
    "most",
    "much",
    "must",
    "need",
    "new",
    "not",
    "now",
    "off",
    "okay",
    "one",
    "only",
    "other",
    "our",
    "out",
    "over",
    "own",
    "play",
    "same",
    "see",
    "should",
    "some",
    "such",
    "sure",
    "take",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "time",
    "too",
    "under",
    "until",
    "very",
    "want",
    "was",
    "way",
    "well",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "would",
    "yeah",
    "yes",
    "you",
    "your",
    "yours",
}


class SlangRAGRetriever:
    """Retrieves and token-compresses dynamic slang, profanity, and algospeak definitions.

    Sources:
    1. Local verified `ProfanityDatabase` (`configs/lexicons/profanity_database.json`) [0-latency].
    2. Cached `UrbanDictionaryClient` (`data/cache/urban_dict/`) for emerging neologisms.
    """

    def __init__(
        self,
        db_path: Path | str = "configs/lexicons/profanity_database.json",
        cache_dir: Path | str = "data/cache/urban_dict",
        max_terms_per_request: int = 5,
        max_definition_chars: int = 120,
    ) -> None:
        self.db_path = Path(db_path)
        self.max_terms = max_terms_per_request
        self.max_def_len = max_definition_chars

        # Persistent cached Urban Dictionary client
        self.urban_client = UrbanDictionaryClient(cache_dir=cache_dir)

        # In-memory index of unified profanity database
        self._profanity_db: dict[str, dict[str, Any]] = self._load_profanity_db()

    def _load_profanity_db(self) -> dict[str, dict[str, Any]]:
        if self.db_path.is_file():
            try:
                with self.db_path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                return raw.get("terms", {})
            except Exception:
                pass
        return {}

    def extract_candidates(self, text: str) -> list[str]:
        """Extract candidate slang or obfuscated tokens from input text."""
        # Find alphanumeric words and common algospeak patterns ($ for s, ! for i, etc.)
        tokens = re.findall(r"\b[a-zA-Z0-9$!@#%]{2,}\b", text.lower())
        candidates: list[str] = []
        seen: set[str] = set()

        for raw_tok in tokens:
            # Normalize basic leetspeak for candidate checking
            clean_tok = (
                raw_tok.replace("$", "s")
                .replace("!", "i")
                .replace("@", "a")
                .replace("0", "o")
                .replace("1", "i")
                .replace("3", "e")
                .replace("7", "t")
            )
            # Remove punctuation
            clean_tok = re.sub(r"[^a-z]", "", clean_tok)
            if len(clean_tok) < 2:
                continue

            if clean_tok not in STOP_WORDS and clean_tok not in seen:
                seen.add(clean_tok)
                candidates.append(clean_tok)

        return candidates

    def retrieve_context_for_terms(self, terms: list[str]) -> dict[str, str]:
        """Retrieve concise definitions for candidate terms from local DB and Urban Dictionary."""
        definitions: dict[str, str] = {}

        for term in terms:
            if len(definitions) >= self.max_terms:
                break

            # 1. Check local verified profanity database (0 latency)
            if term in self._profanity_db:
                item = self._profanity_db[term]
                sev = item.get("severity", 2)
                cats = ", ".join(item.get("categories", ["slang"]))
                definitions[term] = (
                    f"Profanity DB: Severity L{sev} ({cats}). Typically {cats} in youth peer contexts."
                )
                continue

            # 2. Check Urban Dictionary (cached)
            try:
                entry = self.urban_client.lookup(term, strict=True)
                if entry and entry.meaning:
                    # Clean newlines and compact
                    clean_meaning = " ".join(entry.meaning.split()).strip()
                    if len(clean_meaning) > self.max_def_len:
                        clean_meaning = clean_meaning[: self.max_def_len].rstrip() + "..."
                    definitions[term] = clean_meaning
            except Exception:
                pass

        return definitions

    def retrieve_context_for_request(self, request: InferenceRequest) -> dict[str, str]:
        """Retrieve dynamic slang definitions relevant to the conversation prefix."""
        # Prioritize terms in the current target turn, then recent prefix turns
        prefix_turns = request.causal_prefix()
        target_turn = prefix_turns[-1] if prefix_turns else None

        candidates: list[str] = []
        if target_turn:
            candidates.extend(self.extract_candidates(target_turn.text))

        # Check prior turns if budget remains
        for turn in reversed(prefix_turns[:-1]):
            if len(candidates) >= self.max_terms * 2:
                break
            for c in self.extract_candidates(turn.text):
                if c not in candidates:
                    candidates.append(c)

        return self.retrieve_context_for_terms(candidates)

    def format_rag_context_block(self, definitions: dict[str, str]) -> str:
        """Format retrieved definitions into a token-optimized prompt block."""
        if not definitions:
            return ""

        lines = ["[Retrieved Dynamic Slang & Context Knowledge]:"]
        for term, meaning in definitions.items():
            lines.append(f'- "{term}": {meaning}')
        return "\n".join(lines)


# Singleton instance
_GLOBAL_RETRIEVER: SlangRAGRetriever | None = None


def get_default_rag_retriever() -> SlangRAGRetriever:
    """Retrieve or initialize the global SlangRAGRetriever singleton."""
    global _GLOBAL_RETRIEVER
    if _GLOBAL_RETRIEVER is None:
        _GLOBAL_RETRIEVER = SlangRAGRetriever()
    return _GLOBAL_RETRIEVER
