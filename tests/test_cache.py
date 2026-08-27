"""Tests for DiskLLMCache and token savings engine."""

from pathlib import Path

from click.testing import CliRunner

from youth_escalate_bench.cache import DiskLLMCache, get_default_llm_cache
from youth_escalate_bench.cli import main


def test_disk_cache_basic_lifecycle(tmp_path: Path) -> None:
    cache = DiskLLMCache(cache_dir=tmp_path / "test_cache")

    prov = "openai"
    mdl = "gpt-4o-mini"
    prompt = "Classify this utterance: You are trash"
    sys_prompt = "You are a content moderation judge."
    data = {"harm_probability": 0.85, "severity": "actionable", "harm_types": ["targeted_insult"]}

    # Initial miss
    assert cache.get(prov, mdl, prompt, sys_prompt) is None
    stats = cache.stats()
    assert stats["cache_misses"] == 1
    assert stats["cache_hits"] == 0

    # Set cache entry
    cache.set(prov, mdl, prompt, sys_prompt, data)
    assert cache.stats()["cached_entries"] == 1

    # Second query -> Hit from memory
    hit_data = cache.get(prov, mdl, prompt, sys_prompt)
    assert hit_data is not None
    assert hit_data["harm_probability"] == 0.85
    assert cache.stats()["cache_hits"] == 1

    # Create new cache instance pointing to same disk dir -> Hit from disk
    cache2 = DiskLLMCache(cache_dir=tmp_path / "test_cache")
    hit_disk = cache2.get(prov, mdl, prompt, sys_prompt)
    assert hit_disk is not None
    assert hit_disk["severity"] == "actionable"
    assert cache2.stats()["cache_hits"] >= 1
    assert cache2.stats()["tokens_saved"] > 0

    # Clear cache
    cleared = cache.clear()
    assert cleared >= 1
    assert cache.get(prov, mdl, prompt, sys_prompt) is None


def test_global_singleton_cache() -> None:
    c1 = get_default_llm_cache()
    c2 = get_default_llm_cache()
    assert c1 is c2


def test_cli_cache_commands(tmp_path: Path) -> None:
    runner = CliRunner()

    # Test cache-stats
    res = runner.invoke(main, ["cache-stats"])
    assert res.exit_code == 0
    assert "YouthEscalateBench — LLM Response Cache" in res.output
    assert "Cache Location" in res.output

    # Test cache-clear
    res_clear = runner.invoke(main, ["cache-clear"])
    assert res_clear.exit_code == 0
    assert "Cleared" in res_clear.output
