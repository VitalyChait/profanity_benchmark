"""Tests for manifest hashing and reproducibility."""

from pathlib import Path

from youth_escalate_bench.manifest import (
    StageManifest,
    config_digest,
    load_manifest,
    manifest_entry_from_file,
    sha256_text,
    write_manifest,
)


def test_sha256_text_deterministic():
    assert sha256_text("hello") == sha256_text("hello")
    assert sha256_text("hello") != sha256_text("world")


def test_config_digest_order_independent():
    a = {"seed": 42, "version": "0.1.0"}
    b = {"version": "0.1.0", "seed": 42}
    assert config_digest(a) == config_digest(b)


def test_manifest_round_trip(tmp_path: Path):
    manifest = StageManifest(
        stage="source_audit",
        benchmark_version="0.1.0",
        config_sha256=sha256_text("test"),
        random_seed=42,
    )
    path = tmp_path / "manifest.json"
    write_manifest(manifest, path)
    loaded = load_manifest(path)
    assert loaded.stage == "source_audit"
    assert loaded.random_seed == 42


def test_manifest_entry_from_file(tmp_path: Path):
    f = tmp_path / "data.parquet"
    f.write_text("content", encoding="utf-8")
    entry = manifest_entry_from_file(f, row_count=10)
    assert entry.row_count == 10
    assert entry.sha256 == sha256_text("content")
