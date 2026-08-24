"""GameTox in-game chat and gaming session ingest adapter."""

from __future__ import annotations

import json
from pathlib import Path

from youth_escalate_bench.adapters.base import IngestAdapter
from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier, StoredTurn


class GameToxAdapter(IngestAdapter):
    """Ingest multi-turn in-game chat dialogues from GameTox dataset."""

    source_id = "gametox"

    def load(self, input_path: Path) -> list[ConversationRecord]:
        conversations: list[ConversationRecord] = []

        with input_path.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)

                cid = str(data.get("conversation_id") or data.get("match_id") or data.get("session_id") or f"gametox_{idx+1}")
                raw_turns = data.get("turns") or data.get("messages") or data.get("chat_log") or []

                turns: list[StoredTurn] = []
                for t_idx, item in enumerate(raw_turns):
                    if isinstance(item, str):
                        # Simple string line in chat log
                        tid = f"t{t_idx+1}"
                        spk = f"player_{t_idx%2+1}"
                        txt = item.strip()
                        rel_time = f"+{t_idx*10}s"
                        parent_id = None
                    else:
                        tid = str(item.get("turn_id") or item.get("id") or f"t{t_idx+1}")
                        spk = str(item.get("speaker_id") or item.get("player_id") or item.get("user") or f"player_{t_idx%2+1}")
                        txt = str(item.get("text") or item.get("message") or item.get("content") or "").strip()
                        rel_time = str(item.get("relative_time") or item.get("timestamp") or f"+{t_idx*10}s")
                        parent_id = item.get("parent_id")

                    if txt:
                        turns.append(
                            StoredTurn(
                                turn_id=tid,
                                speaker_id=spk,
                                role="user" if t_idx % 2 == 0 else "peer",
                                text=txt,
                                relative_time=rel_time,
                                parent_turn_id=str(parent_id) if parent_id else None,
                            )
                        )

                if turns:
                    conversations.append(
                        ConversationRecord(
                            conversation_id=cid,
                            source_id=self.source_id,
                            source_tier=SourceTier.ORGANIC,
                            platform_style="gaming_chat",
                            language_mode=data.get("language_mode", "english"),
                            turns=turns,
                            metadata={
                                "game_title": data.get("game_title") or data.get("game"),
                                "match_type": data.get("match_type"),
                                "source": "gametox",
                            },
                        )
                    )

        return conversations
