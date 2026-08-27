"""Generic multi-format Ingest Adapter for CSV, JSON, JSONL, and Parquet data."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from youth_escalate_bench.adapters.base import IngestAdapter
from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier, StoredTurn


class GenericConversationAdapter(IngestAdapter):
    """Universal adapter capable of ingesting nested JSONL/JSON or flat CSV/Parquet dialog rows."""

    def __init__(
        self,
        source_id: str = "generic_conversation",
        source_tier: SourceTier = SourceTier.ORGANIC,
        platform_style: str = "group_chat",
        language_mode: str = "english",
        conv_id_col: str | None = None,
        text_col: str | None = None,
        speaker_col: str | None = None,
        turn_id_col: str | None = None,
    ) -> None:
        self.source_id = source_id
        self.source_tier = source_tier
        self.platform_style = platform_style
        self.language_mode = language_mode
        self.conv_id_col = conv_id_col
        self.text_col = text_col
        self.speaker_col = speaker_col
        self.turn_id_col = turn_id_col

    def load(self, input_path: Path) -> list[ConversationRecord]:
        suffix = input_path.suffix.lower()
        if suffix in (".jsonl", ".jsonlines"):
            return self._load_jsonl(input_path)
        elif suffix == ".json":
            return self._load_json(input_path)
        elif suffix in (".csv", ".tsv"):
            return self._load_csv(input_path, delimiter="\t" if suffix == ".tsv" else ",")
        elif suffix in (".parquet", ".pq"):
            return self._load_parquet(input_path)
        else:
            # Attempt jsonl parse first, fallback to text lines
            try:
                return self._load_jsonl(input_path)
            except Exception:
                return self._load_flat_text(input_path)

    def _load_jsonl(self, path: Path) -> list[ConversationRecord]:
        conversations: list[ConversationRecord] = []
        flat_rows: list[dict[str, Any]] = []

        with path.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)

                # Check if nested conversation structure
                turns_raw = (
                    item.get("turns")
                    or item.get("messages")
                    or item.get("dialog")
                    or item.get("conversation")
                )
                if isinstance(turns_raw, list):
                    cid = str(
                        item.get("conversation_id")
                        or item.get("id")
                        or item.get("thread_id")
                        or f"{self.source_id}_{idx + 1}"
                    )
                    turns = self.normalize_turns(turns_raw)
                    if turns:
                        conversations.append(
                            ConversationRecord(
                                conversation_id=cid,
                                source_id=self.source_id,
                                source_tier=self.source_tier,
                                platform_style=item.get("platform_style", self.platform_style),
                                language_mode=item.get("language_mode", self.language_mode),
                                turns=turns,
                                metadata={
                                    k: v
                                    for k, v in item.items()
                                    if k not in ("turns", "messages", "dialog")
                                },
                            )
                        )
                else:
                    # Flat row with grouping ID
                    flat_rows.append(item)

        if flat_rows:
            conversations.extend(self._group_flat_rows(flat_rows))

        return conversations

    def _load_json(self, path: Path) -> list[ConversationRecord]:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            # List of conversation dicts or flat rows
            conversations: list[ConversationRecord] = []
            flat_rows: list[dict[str, Any]] = []
            for idx, item in enumerate(data):
                turns_raw = item.get("turns") or item.get("messages") or item.get("dialog")
                if isinstance(turns_raw, list):
                    cid = str(
                        item.get("conversation_id")
                        or item.get("id")
                        or f"{self.source_id}_{idx + 1}"
                    )
                    turns = self.normalize_turns(turns_raw)
                    if turns:
                        conversations.append(
                            ConversationRecord(
                                conversation_id=cid,
                                source_id=self.source_id,
                                source_tier=self.source_tier,
                                platform_style=item.get("platform_style", self.platform_style),
                                language_mode=item.get("language_mode", self.language_mode),
                                turns=turns,
                                metadata={
                                    k: v
                                    for k, v in item.items()
                                    if k not in ("turns", "messages", "dialog")
                                },
                            )
                        )
                else:
                    flat_rows.append(item)
            if flat_rows:
                conversations.extend(self._group_flat_rows(flat_rows))
            return conversations
        elif isinstance(data, dict):
            # Check if dict of {post_id: {post_tokens: [...]}} (e.g. HateXplain)
            items_list = []
            for post_id, val in data.items():
                if isinstance(val, dict):
                    row_dict = dict(val)
                    row_dict["post_id"] = str(post_id)
                    if "post_tokens" in row_dict and isinstance(row_dict["post_tokens"], list):
                        row_dict["text"] = " ".join(str(tok) for tok in row_dict["post_tokens"])
                    items_list.append(row_dict)
            if items_list:
                return self._group_flat_rows(items_list)

            # Single conversation or keyed dict
            turns_raw = data.get("turns") or data.get("messages") or data.get("dialog")
            if isinstance(turns_raw, list):
                cid = str(data.get("conversation_id") or data.get("id") or f"{self.source_id}_1")
                turns = self.normalize_turns(turns_raw)
                return [
                    ConversationRecord(
                        conversation_id=cid,
                        source_id=self.source_id,
                        source_tier=self.source_tier,
                        platform_style=data.get("platform_style", self.platform_style),
                        language_mode=data.get("language_mode", self.language_mode),
                        turns=turns,
                        metadata={
                            k: v
                            for k, v in data.items()
                            if k not in ("turns", "messages", "dialog")
                        },
                    )
                ]
        return []

    def _load_csv(self, path: Path, delimiter: str = ",") -> list[ConversationRecord]:
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for r in reader:
                rows.append(dict(r))
        return self._group_flat_rows(rows)

    def _load_parquet(self, path: Path) -> list[ConversationRecord]:
        try:
            import pyarrow.parquet as pq

            table = pq.read_table(path)
            rows = table.to_pylist()
            # If rows have 'turns' as nested struct/list
            if rows and "turns" in rows[0] and isinstance(rows[0]["turns"], list):
                conversations: list[ConversationRecord] = []
                for idx, item in enumerate(rows):
                    cid = str(
                        item.get("conversation_id")
                        or item.get("id")
                        or f"{self.source_id}_{idx + 1}"
                    )
                    turns = self.normalize_turns(item["turns"])
                    if turns:
                        conversations.append(
                            ConversationRecord(
                                conversation_id=cid,
                                source_id=self.source_id,
                                source_tier=self.source_tier,
                                platform_style=item.get("platform_style", self.platform_style),
                                language_mode=item.get("language_mode", self.language_mode),
                                turns=turns,
                                metadata={k: v for k, v in item.items() if k != "turns"},
                            )
                        )
                return conversations
            return self._group_flat_rows(rows)
        except Exception as e:
            raise RuntimeError(f"Failed to read parquet file {path}: {e}") from e

    def _load_flat_text(self, path: Path) -> list[ConversationRecord]:
        conversations: list[ConversationRecord] = []
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if line:
                    conversations.append(
                        ConversationRecord(
                            conversation_id=f"{self.source_id}_{idx + 1}",
                            source_id=self.source_id,
                            source_tier=self.source_tier,
                            platform_style=self.platform_style,
                            language_mode=self.language_mode,
                            turns=[
                                StoredTurn(
                                    turn_id="t1",
                                    speaker_id="user_1",
                                    role="user",
                                    text=line,
                                    relative_time="+0s",
                                )
                            ],
                            metadata={"filename": path.name, "line": idx + 1},
                        )
                    )
        return conversations

    def _group_flat_rows(self, rows: list[dict[str, Any]]) -> list[ConversationRecord]:
        """Group tabular flat message rows by conversation/thread ID into multi-turn records."""
        if not rows:
            return []

        # Detect columns
        sample = rows[0]
        cid_key = self.conv_id_col or self._find_matching_key(
            sample,
            [
                "conversation_id",
                "conv_id",
                "thread_id",
                "dialog_id",
                "dialogue_id",
                "post_id",
                "session_id",
                "context_id",
                "id",
            ],
        )
        text_key = self.text_col or self._find_matching_key(
            sample,
            [
                "text",
                "tweet",
                "user_input",
                "comment_text",
                "body",
                "message",
                "utterance",
                "content",
                "cleaned_text",
                "post",
                "sentence",
                "prompt",
            ],
        )
        speaker_key = self.speaker_col or self._find_matching_key(
            sample, ["speaker_id", "speaker", "author", "user", "username", "sender", "role"]
        )
        turn_id_key = self.turn_id_col or self._find_matching_key(
            sample, ["turn_id", "message_id", "comment_id", "id", "index"]
        )

        if not text_key:
            raise ValueError(
                f"Could not automatically identify a 'text' column in data fields: {list(sample.keys())}"
            )

        has_model_output = "model_output" in sample or "assistant_response" in sample

        # Group by conversation ID
        grouped: dict[str, list[dict[str, Any]]] = {}
        for idx, row in enumerate(rows):
            cid = str(row.get(cid_key) if cid_key and row.get(cid_key) else f"conv_{idx + 1}")
            if cid not in grouped:
                grouped[cid] = []
            grouped[cid].append(row)

        conversations: list[ConversationRecord] = []
        for cid, group in grouped.items():
            turns: list[StoredTurn] = []
            seen_tids: set[str] = set()
            for t_idx, r in enumerate(group):
                tid = str(
                    r.get(turn_id_key) or f"t{t_idx * 2 + 1 if has_model_output else t_idx + 1}"
                )
                if tid in seen_tids:
                    tid = f"t{len(turns) + 1}_{tid}"
                seen_tids.add(tid)
                spk = str(r.get(speaker_key) or f"user_{t_idx % 2 + 1}")
                txt = str(r.get(text_key) or "").strip()
                rel_time = str(
                    r.get("relative_time")
                    or r.get("timestamp")
                    or r.get("created_utc")
                    or f"+{t_idx * 5}s"
                )
                parent = r.get("parent_id") or r.get("parent_turn_id")
                if txt:
                    turns.append(
                        StoredTurn(
                            turn_id=tid,
                            speaker_id=spk,
                            role="user" if t_idx % 2 == 0 else "peer",
                            text=txt,
                            relative_time=rel_time,
                            parent_turn_id=str(parent) if parent else None,
                        )
                    )

                # If dialogue has user_input + model_output (e.g. ToxicChat)
                model_txt = str(r.get("model_output") or r.get("assistant_response") or "").strip()
                if model_txt:
                    m_tid = f"t{len(turns) + 1}"
                    seen_tids.add(m_tid)
                    turns.append(
                        StoredTurn(
                            turn_id=m_tid,
                            speaker_id="assistant",
                            role="assistant",
                            text=model_txt,
                            relative_time=f"+{t_idx * 5 + 2}s",
                            parent_turn_id=tid,
                        )
                    )

            if turns:
                conversations.append(
                    ConversationRecord(
                        conversation_id=cid,
                        source_id=self.source_id,
                        source_tier=self.source_tier,
                        platform_style=self.platform_style,
                        language_mode=self.language_mode,
                        turns=turns,
                        metadata={"source_row_count": len(group)},
                    )
                )
        return conversations

    @staticmethod
    def _find_matching_key(row: dict[str, Any], candidates: list[str]) -> str | None:
        lowered = {k.lower().strip(): k for k in row.keys()}
        for cand in candidates:
            if cand in lowered:
                return lowered[cand]
        return None
