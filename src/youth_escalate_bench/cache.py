"""Persistent disk and memory caching engine for LLM predictions and token savings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

DEFAULT_CACHE_DIR = Path("data/cache/llm_predictions")


class DiskLLMCache:
    """High-performance atomic file-based cache for LLM JSON inferences.

    Avoids redundant API queries and token consumption across benchmark runs.
    """

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats_file = self.cache_dir / "_stats.json"

        self._memory_cache: dict[str, dict[str, Any]] = {}
        self._stats: dict[str, Any] = self._load_stats()

    def _load_stats(self) -> dict[str, Any]:
        if self.stats_file.is_file():
            try:
                with self.stats_file.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "cache_hits": 0,
            "cache_misses": 0,
            "tokens_saved": 0,
            "estimated_cost_usd_saved": 0.0,
        }

    def _save_stats(self) -> None:
        try:
            with self.stats_file.open("w", encoding="utf-8") as f:
                json.dump(self._stats, f, indent=2)
        except Exception:
            pass

    def compute_hash(
        self,
        provider: str,
        model: str,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.0,
    ) -> str:
        """Compute deterministic SHA256 key for a specific query."""
        payload = f"{provider.strip().lower()}|{model.strip().lower()}|{system_prompt.strip()}|{prompt.strip()}|{temperature}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(
        self,
        provider: str,
        model: str,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.0,
    ) -> dict[str, Any] | None:
        """Retrieve cached LLM output dictionary if present."""
        key = self.compute_hash(provider, model, prompt, system_prompt, temperature)

        # 1. Check in-memory LRU/dict
        if key in self._memory_cache:
            self._stats["cache_hits"] += 1
            self._save_stats()
            return self._memory_cache[key]

        # 2. Check disk file
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.is_file():
            try:
                with cache_file.open("r", encoding="utf-8") as f:
                    entry = json.load(f)
                data = entry.get("data")
                if isinstance(data, dict):
                    self._memory_cache[key] = data
                    self._stats["cache_hits"] += 1

                    # Estimate tokens saved
                    saved_tokens = entry.get("estimated_tokens", 0)
                    if not saved_tokens:
                        saved_tokens = int(
                            len(prompt.split()) * 1.33 + len(json.dumps(data).split()) * 1.33
                        )
                    self._stats["tokens_saved"] += saved_tokens
                    self._stats["estimated_cost_usd_saved"] += (saved_tokens / 1_000_000.0) * 1.50
                    self._save_stats()
                    return data
            except Exception:
                pass

        self._stats["cache_misses"] += 1
        self._save_stats()
        return None

    def set(
        self,
        provider: str,
        model: str,
        prompt: str,
        system_prompt: str,
        data: dict[str, Any],
        temperature: float = 0.0,
    ) -> None:
        """Save an LLM output to both memory and atomic disk cache."""
        key = self.compute_hash(provider, model, prompt, system_prompt, temperature)
        self._memory_cache[key] = data

        estimated_tokens = int(len(prompt.split()) * 1.33 + len(json.dumps(data).split()) * 1.33)
        record = {
            "key": key,
            "provider": provider,
            "model": model,
            "estimated_tokens": estimated_tokens,
            "data": data,
        }

        cache_file = self.cache_dir / f"{key}.json"
        temp_file = self.cache_dir / f"{key}.json.tmp"
        try:
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            temp_file.replace(cache_file)
        except Exception as e:
            logger.warning("cache_write_failed", key=key, error=str(e))
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)

    def stats(self) -> dict[str, Any]:
        """Return current cache usage and token savings statistics."""
        disk_files = list(self.cache_dir.glob("*.json"))
        cache_entries = len([f for f in disk_files if not f.name.startswith("_")])
        return {
            "cached_entries": cache_entries,
            "cache_hits": self._stats.get("cache_hits", 0),
            "cache_misses": self._stats.get("cache_misses", 0),
            "tokens_saved": self._stats.get("tokens_saved", 0),
            "estimated_cost_usd_saved": round(
                float(self._stats.get("estimated_cost_usd_saved", 0.0)), 4
            ),
        }

    def clear(self) -> int:
        """Delete all cached prediction files and reset statistics."""
        self._memory_cache.clear()
        count = 0
        for f in self.cache_dir.glob("*.json"):
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "tokens_saved": 0,
            "estimated_cost_usd_saved": 0.0,
        }
        self._save_stats()
        return count


# Global singleton instance
_GLOBAL_CACHE: DiskLLMCache | None = None


def get_default_llm_cache() -> DiskLLMCache:
    """Retrieve or initialize the global shared DiskLLMCache singleton."""
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE is None:
        _GLOBAL_CACHE = DiskLLMCache()
    return _GLOBAL_CACHE
