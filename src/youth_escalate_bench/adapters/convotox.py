"""ConvoTox Reddit conversation tree ingest adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from youth_escalate_bench.adapters.base import IngestAdapter
from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier, StoredTurn


class ConvoToxAdapter(IngestAdapter):
    """Ingest Reddit conversation trees from ConvoTox dataset."""

    source_id = "convotox"

    def load(self, input_path: Path) -> list[ConversationRecord]:
        conversations: list[ConversationRecord] = []

        with input_path.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)

                cid = str(data.get("conversation_id") or data.get("thread_id") or f"convotox_{idx+1}")
                raw_turns = data.get("turns") or data.get("comments") or data.get("messages") or []

                turns: list[StoredTurn] = []
                for t_idx, item in enumerate(raw_turns):
                    tid = str(item.get("turn_id") or item.get("id") or item.get("comment_id") or f"t{t_idx+1}")
                    spk = str(item.get("speaker_id") or item.get("author") or f"reddit_user_{t_idx%2+1}")
                    txt = str(item.get("text") or item.get("body") or "").strip()
                    parent_id = item.get("parent_id") or item.get("parent_turn_id")
                    rel_time = str(item.get("relative_time") or item.get("created_utc") or f"+{t_idx*60}s")

                    if txt and txt not in ("[deleted]", "[removed]"):
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
                            platform_style="forum_thread",
                            language_mode=data.get("language_mode", "english"),
                            turns=turns,
                            metadata={
                                "subreddit": data.get("subreddit"),
                                "toxic_target": data.get("toxic_target"),
                                "source": "convotox",
                            },
                        )
                    )

        return conversations
