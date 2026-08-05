"""Parquet I/O tests."""

from pathlib import Path

from youth_escalate_bench.adapters.fixture import FixtureAdapter
from youth_escalate_bench.io.parquet import read_conversations, write_conversations


def test_parquet_round_trip(tmp_path: Path) -> None:
    adapter = FixtureAdapter()
    convs = adapter.load(Path("tests/fixtures/sample_conversations.jsonl"))
    path = tmp_path / "out.parquet"
    write_conversations(path, convs)
    loaded = read_conversations(path)
    assert len(loaded) == len(convs)
    assert loaded[0].turns[0].text == convs[0].turns[0].text
