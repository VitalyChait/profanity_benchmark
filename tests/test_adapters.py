"""Unit tests for corpus ingestion adapters."""

import csv
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from youth_escalate_bench.adapters import (
    CADAdapter,
    ConvoToxAdapter,
    FlatToMultiTurnJoiner,
    GameToxAdapter,
    GenericConversationAdapter,
    WikiConvAdapter,
    get_adapter,
)


def test_adapter_registry_retrieval():
    assert isinstance(get_adapter("wikiconv_wikidetox"), WikiConvAdapter)
    assert isinstance(get_adapter("contextual_abuse_dataset"), CADAdapter)
    assert isinstance(get_adapter("convotox"), ConvoToxAdapter)
    assert isinstance(get_adapter("gametox"), GameToxAdapter)
    assert isinstance(get_adapter("davidson"), FlatToMultiTurnJoiner)
    assert isinstance(get_adapter("generic"), GenericConversationAdapter)

    # Dynamic fallback for unknown source
    custom = get_adapter("unknown_custom_source")
    assert isinstance(custom, GenericConversationAdapter)
    assert custom.source_id == "unknown_custom_source"


def test_generic_adapter_jsonl_nested(tmp_path: Path):
    file_path = tmp_path / "test_nested.jsonl"
    data = [
        {
            "conversation_id": "conv_101",
            "platform_style": "group_chat",
            "turns": [
                {"turn_id": "t1", "speaker_id": "alex", "text": "hey everyone", "relative_time": "+0s"},
                {"turn_id": "t2", "speaker_id": "sam", "text": "yo alex what's up", "relative_time": "+5s"},
            ],
        },
        {
            "id": "conv_102",
            "messages": [
                {"id": "m1", "user": "jordan", "content": "game starting soon"},
                {"id": "m2", "user": "taylor", "content": "joining in 2 mins"},
            ],
        },
    ]
    with file_path.open("w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")

    adapter = GenericConversationAdapter()
    records = adapter.load(file_path)

    assert len(records) == 2
    assert records[0].conversation_id == "conv_101"
    assert len(records[0].turns) == 2
    assert records[0].turns[0].text == "hey everyone"

    assert records[1].conversation_id == "conv_102"
    assert len(records[1].turns) == 2
    assert records[1].turns[1].speaker_id == "taylor"


def test_generic_adapter_csv_flat(tmp_path: Path):
    file_path = tmp_path / "test_flat.csv"
    with file_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["thread_id", "author", "comment_text", "timestamp"])
        writer.writeheader()
        writer.writerow({"thread_id": "thread_A", "author": "user1", "comment_text": "First comment", "timestamp": "1000"})
        writer.writerow({"thread_id": "thread_A", "author": "user2", "comment_text": "Reply to first", "timestamp": "1015"})
        writer.writerow({"thread_id": "thread_B", "author": "user3", "comment_text": "Separate thread", "timestamp": "2000"})

    adapter = GenericConversationAdapter(source_id="csv_test")
    records = adapter.load(file_path)

    assert len(records) == 2
    rec_a = next(r for r in records if r.conversation_id == "thread_A")
    assert len(rec_a.turns) == 2
    assert rec_a.turns[0].text == "First comment"
    assert rec_a.turns[1].speaker_id == "user2"

    rec_b = next(r for r in records if r.conversation_id == "thread_B")
    assert len(rec_b.turns) == 1
    assert rec_b.turns[0].text == "Separate thread"


def test_generic_adapter_parquet(tmp_path: Path):
    file_path = tmp_path / "test_data.parquet"
    data = [
        {
            "conversation_id": "pq_conv_1",
            "turns": [
                {"turn_id": "t1", "speaker_id": "user1", "text": "hello parquet", "relative_time": "+0s"},
                {"turn_id": "t2", "speaker_id": "user2", "text": "parquet reply", "relative_time": "+10s"},
            ],
        }
    ]
    table = pa.Table.from_pylist(data)
    pq.write_table(table, file_path)

    adapter = GenericConversationAdapter(source_id="parquet_test")
    records = adapter.load(file_path)

    assert len(records) == 1
    assert records[0].conversation_id == "pq_conv_1"
    assert len(records[0].turns) == 2
    assert records[0].turns[0].text == "hello parquet"


def test_convotox_adapter(tmp_path: Path):
    file_path = tmp_path / "convotox_sample.jsonl"
    data = {
        "conversation_id": "reddit_post_999",
        "subreddit": "gaming",
        "comments": [
            {"turn_id": "c1", "author": "redditor_1", "body": "Who is excited for the new update?", "created_utc": "+0s"},
            {"turn_id": "c2", "author": "redditor_2", "body": "It looks terrible tbh", "parent_id": "c1", "created_utc": "+60s"},
            {"turn_id": "c3", "author": "redditor_3", "body": "[deleted]", "created_utc": "+120s"},
        ],
    }
    with file_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")

    adapter = ConvoToxAdapter()
    records = adapter.load(file_path)

    assert len(records) == 1
    assert records[0].conversation_id == "reddit_post_999"
    # [deleted] comment should be filtered out
    assert len(records[0].turns) == 2
    assert records[0].turns[0].speaker_id == "redditor_1"
    assert records[0].turns[1].parent_turn_id == "c1"


def test_gametox_adapter(tmp_path: Path):
    file_path = tmp_path / "gametox_sample.jsonl"
    data = {
        "match_id": "match_555",
        "game_title": "Valorant",
        "chat_log": [
            {"turn_id": "t1", "player_id": "JettMain", "text": "rush B site", "relative_time": "+0s"},
            {"turn_id": "t2", "player_id": "Sova77", "text": "i have dart ready", "relative_time": "+5s"},
            {"turn_id": "t3", "player_id": "JettMain", "text": "nice flash bro", "relative_time": "+15s"},
        ],
    }
    with file_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")

    adapter = GameToxAdapter()
    records = adapter.load(file_path)

    assert len(records) == 1
    assert records[0].conversation_id == "match_555"
    assert records[0].platform_style == "gaming_chat"
    assert len(records[0].turns) == 3
    assert records[0].turns[0].speaker_id == "JettMain"


def test_flat_joiner_adapter(tmp_path: Path):
    file_path = tmp_path / "toxic_seeds.csv"
    with file_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["tweet", "author", "class"])
        writer.writeheader()
        writer.writerow({"tweet": "you are absolute trash get out of here", "author": "troll_user", "class": "offensive"})

    joiner = FlatToMultiTurnJoiner(source_id="davidson_scaffold")
    records = joiner.load(file_path)

    assert len(records) == 1
    rec = records[0]
    # Scaffolding: 2 prefix turns + 1 target seed + 1 reaction turn = 4 turns
    assert len(rec.turns) == 4
    assert rec.turns[0].speaker_id == "peer_alpha"
    assert rec.turns[2].speaker_id == "troll_user"
    assert rec.turns[2].text == "you are absolute trash get out of here"
    assert rec.turns[3].speaker_id == "peer_alpha"
