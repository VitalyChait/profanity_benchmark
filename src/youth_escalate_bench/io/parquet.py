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
    schema = {
        "conversation_id": pl.Utf8,
        "source_id": pl.Utf8,
        "source_tier": pl.Utf8,
        "platform_style": pl.Utf8,
        "language_mode": pl.Utf8,
        "benchmark_version": pl.Utf8,
        "turn_id": pl.Utf8,
        "speaker_id": pl.Utf8,
        "role": pl.Utf8,
        "text": pl.Utf8,
        "relative_time": pl.Utf8,
        "parent_turn_id": pl.Utf8,
        "metadata_json": pl.Utf8,
    }
    return pl.DataFrame(rows, schema=schema)



def frame_to_conversations(df: pl.DataFrame) -> list[ConversationRecord]:
    if df.is_empty():
        return []

    by_conv: dict[str, list[dict]] = {}
    for row in df.iter_rows(named=True):
        cid = str(row["conversation_id"])
        if cid not in by_conv:
            by_conv[cid] = []
        by_conv[cid].append(row)

    conversations: list[ConversationRecord] = []
    for cid, rows in by_conv.items():
        first = rows[0]
        seen_tids: set[str] = set()
        turns: list[StoredTurn] = []
        for r in rows:
            tid = str(r["turn_id"])
            if tid not in seen_tids:
                seen_tids.add(tid)
                turns.append(
                    StoredTurn(
                        turn_id=tid,
                        speaker_id=r["speaker_id"],
                        role=r["role"],
                        text=r["text"],
                        relative_time=r["relative_time"],
                        parent_turn_id=r.get("parent_turn_id"),
                    )
                )
        meta = _parse_metadata(first.get("metadata_json"))
        conversations.append(
            ConversationRecord(
                conversation_id=cid,
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
