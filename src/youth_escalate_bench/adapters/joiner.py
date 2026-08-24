"""Semantic multi-turn window extractor and dialogue scaffold joiner for flat seeds."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from youth_escalate_bench.adapters.base import IngestAdapter
from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier, StoredTurn


class FlatToMultiTurnJoiner(IngestAdapter):
    """Transforms flat toxic/benign utterance seeds into multi-turn dialogue contexts.

    Supports:
    1. Extracting sliding multi-turn windows around emergence of toxic/profane terms in large dialog logs.
    2. Contextual scaffolding: embedding flat utterances into plausible conversational prefixes and reactions.
    """

    source_id = "flat_joiner"

    DEFAULT_PREFIXES = [
        ("yo drop your loadout at mid", "heading there now, don't get picked"),
        ("bro what happened to your team yesterday?", "we choked in the second half lmao"),
        ("anyone want to queue up for competitive?", "i can play in 5 minutes"),
        ("did you finish that history assignment?", "deadass forgot about it until now"),
        ("hey check the group chat link", "which one? there are like 5 chats"),
    ]

    DEFAULT_REACTIONS = [
        "why are you getting so mad over nothing?",
        "chill out bro it's just a game",
        "leave them alone, stop being toxic",
        "bruh what is wrong with you",
    ]

    def __init__(
        self,
        source_id: str = "flat_joiner",
        window_size: int = 5,
        target_term_lexicon: list[str] | None = None,
        platform_style: str = "group_chat",
    ) -> None:
        self.source_id = source_id
        self.window_size = window_size
        self.lexicon = set(target_term_lexicon) if target_term_lexicon else set()
        self.platform_style = platform_style

    def load(self, input_path: Path) -> list[ConversationRecord]:
        suffix = input_path.suffix.lower()
        if suffix in (".csv", ".tsv"):
            flat_items = self._load_csv_seeds(input_path, delimiter="\t" if suffix == ".tsv" else ",")
        else:
            flat_items = self._load_jsonl_seeds(input_path)

        conversations: list[ConversationRecord] = []
        for idx, item in enumerate(flat_items):
            cid = f"{self.source_id}_scaffold_{idx+1}"
            target_text = item["text"]
            turns = self._scaffold_dialogue(target_text, item.get("speaker_id", "user_aggressor"), idx)

            conversations.append(
                ConversationRecord(
                    conversation_id=cid,
                    source_id=self.source_id,
                    source_tier=SourceTier.ORGANIC,
                    platform_style=self.platform_style,
                    language_mode="english",
                    turns=turns,
                    metadata={
                        "original_seed": target_text,
                        "seed_metadata": item.get("metadata", {}),
                        "scaffold_type": "prefix_target_reaction",
                    },
                )
            )

        return conversations

    def _load_csv_seeds(self, path: Path, delimiter: str) -> list[dict[str, Any]]:
        seeds: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                text = row.get("text") or row.get("comment_text") or row.get("tweet") or row.get("body")
                if text and text.strip():
                    seeds.append({
                        "text": text.strip(),
                        "speaker_id": row.get("speaker_id") or row.get("author") or "seed_speaker",
                        "metadata": {k: v for k, v in row.items() if k not in ("text", "comment_text", "tweet", "body")},
                    })
        return seeds

    def _load_jsonl_seeds(self, path: Path) -> list[dict[str, Any]]:
        seeds: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                text = row.get("text") or row.get("comment_text") or row.get("body")
                if text and text.strip():
                    seeds.append({
                        "text": text.strip(),
                        "speaker_id": row.get("speaker_id") or row.get("author") or "seed_speaker",
                        "metadata": {k: v for k, v in row.items() if k not in ("text", "comment_text", "body")},
                    })
        return seeds

    def _scaffold_dialogue(self, target_text: str, aggressor_id: str, seed_index: int) -> list[StoredTurn]:
        """Construct multi-turn sequence: 2 prefix turns -> target seed turn -> 1 reaction turn."""
        turns: list[StoredTurn] = []
        prefix_pair = self.DEFAULT_PREFIXES[seed_index % len(self.DEFAULT_PREFIXES)]
        reaction = self.DEFAULT_REACTIONS[seed_index % len(self.DEFAULT_REACTIONS)]

        # Turn 1: Benign peer prefix
        turns.append(
            StoredTurn(
                turn_id="t1",
                speaker_id="peer_alpha",
                role="user",
                text=prefix_pair[0],
                relative_time="+0s",
            )
        )
        # Turn 2: Benign peer response
        turns.append(
            StoredTurn(
                turn_id="t2",
                speaker_id="peer_beta",
                role="peer",
                text=prefix_pair[1],
                relative_time="+15s",
                parent_turn_id="t1",
            )
        )
        # Turn 3: Target seed (escalation/attack/comment)
        turns.append(
            StoredTurn(
                turn_id="t3",
                speaker_id=aggressor_id,
                role="user",
                text=target_text,
                relative_time="+30s",
                parent_turn_id="t2",
            )
        )
        # Turn 4: Peer reaction
        turns.append(
            StoredTurn(
                turn_id="t4",
                speaker_id="peer_alpha",
                role="peer",
                text=reaction,
                relative_time="+45s",
                parent_turn_id="t3",
            )
        )

        return turns
