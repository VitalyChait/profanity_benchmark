"""Parquet read/write for conversation records."""

from pathlib import Path

import polars as pl

from youth_escalate_bench.schemas.conversation import ConversationRecord, StoredTurn


def conversations_to_frame(conversations: list[ConversationRecord]) -> pl.DataFrame:
    rows: list[dict] = []
    for conv in conversations:
        for turn in conv.turns:
            rows.append(
                {
                    "conversation_id": conv.conversation_id,
                    "source_id": conv.source_id,
                    "source_tier": conv.source_tier.value,
                    "platform_style": conv.platform_style,
                    "language_mode": conv.language_mode,
                    "benchmark_version": conv.benchmark_version,
                    "turn_id": turn.turn_id,
                    "speaker_id": turn.speaker_id,
                    "role": turn.role,
                    "text": turn.text,
                    "relative_time": turn.relative_time,
                    "parent_turn_id": turn.parent_turn_id,
                    "metadata_json": _metadata_json(conv.metadata),
                }
            )
    return pl.DataFrame(rows)


def frame_to_conversations(df: pl.DataFrame) -> list[ConversationRecord]:
    conversations: list[ConversationRecord] = []
    for conv_id in df["conversation_id"].unique(maintain_order=True).to_list():
        sub = df.filter(pl.col("conversation_id") == conv_id)
        first = sub.row(0, named=True)
        turns = [
            StoredTurn(
                turn_id=row["turn_id"],
                speaker_id=row["speaker_id"],
                role=row["role"],
                text=row["text"],
                relative_time=row["relative_time"],
                parent_turn_id=row.get("parent_turn_id"),
            )
            for row in sub.iter_rows(named=True)
        ]
        meta = _parse_metadata(first.get("metadata_json"))
        conversations.append(
            ConversationRecord(
                conversation_id=conv_id,
                source_id=first["source_id"],
                source_tier=first["source_tier"],
                platform_style=first["platform_style"],
                language_mode=first["language_mode"],
                benchmark_version=first["benchmark_version"],
                turns=turns,
                metadata=meta,
            )
        )
    return conversations


def write_conversations(path: Path, conversations: list[ConversationRecord]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = conversations_to_frame(conversations)
    df.write_parquet(path)
    return len(conversations)


def read_conversations(path: Path) -> list[ConversationRecord]:
    df = pl.read_parquet(path)
    return frame_to_conversations(df)


def count_turns(path: Path) -> int:
    return pl.read_parquet(path).height


def _metadata_json(metadata: dict) -> str:
    import json

    return json.dumps(metadata, sort_keys=True)


def _parse_metadata(raw: str | None) -> dict:
    import json

    if not raw:
        return {}
    return json.loads(raw)
