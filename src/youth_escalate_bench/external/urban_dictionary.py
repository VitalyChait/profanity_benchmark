"""Client for the Unofficial Urban Dictionary API (https://unofficialurbandictionaryapi.com/)."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

DEFAULT_API_URL = "https://unofficialurbandictionaryapi.com/"


@dataclass(frozen=True)
class UrbanDefinition:
    """A slang definition entry from Urban Dictionary."""

    word: str
    meaning: str
    example: str = ""
    contributor: str = ""
    date: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_api_item(cls, item: dict[str, Any]) -> UrbanDefinition:
        word = str(item.get("word", "")).strip()
        meaning = str(item.get("meaning", "")).strip()
        example = str(item.get("example", "")).strip()
        contributor = str(item.get("contributor", "")).strip()
        date = str(item.get("date", "")).strip()
        return cls(
            word=word,
            meaning=meaning,
            example=example,
            contributor=contributor,
            date=date,
        )


class UrbanDictionaryClient:
    """HTTP client with caching and timeout resilience for the Unofficial Urban Dictionary API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 12.0,
        cache_dir: Path | str | None = None,
        user_agent: str = "YouthEscalateBench/0.1.2 (+https://github.com/VitalyChait/profanity_benchmark)",
    ) -> None:
        raw_url = base_url or os.getenv("URBAN_DICTIONARY_API_URL", DEFAULT_API_URL)
        self.base_url = raw_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent

        # In-memory LRU/dict cache: (endpoint, query_key) -> list[UrbanDefinition]
        self._memory_cache: dict[str, list[UrbanDefinition]] = {}

        # Optional disk cache
        self.cache_dir: Path | None = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, endpoint: str, query: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", query.lower())
        return f"{endpoint}_{clean}"

    def _read_cache(self, key: str) -> list[UrbanDefinition] | None:
        if key in self._memory_cache:
            return self._memory_cache[key]
        if self.cache_dir:
            disk_file = self.cache_dir / f"{key}.json"
            if disk_file.exists():
                try:
                    with disk_file.open(encoding="utf-8") as f:
                        raw = json.load(f)
                    defs = [UrbanDefinition(**d) for d in raw]
                    self._memory_cache[key] = defs
                    return defs
                except Exception:
                    pass
        return None

    def _write_cache(self, key: str, defs: list[UrbanDefinition]) -> None:
        self._memory_cache[key] = defs
        if self.cache_dir:
            disk_file = self.cache_dir / f"{key}.json"
            try:
                with disk_file.open("w", encoding="utf-8") as f:
                    json.dump([d.to_dict() for d in defs], f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
        query_str = urllib.parse.urlencode({k: str(v) for k, v in params.items() if v is not None})
        url = (
            f"{self.base_url}{endpoint}?{query_str}" if query_str else f"{self.base_url}{endpoint}"
        )

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8", errors="replace")
                    return json.loads(body)
                else:
                    logger.warning("urban_dict_non_200", status=resp.status, url=url)
                    return None
        except Exception as e:
            logger.warning("urban_dict_request_failed", error=str(e), url=url)
            return None

    def search(
        self,
        term: str,
        strict: bool = False,
        limit: int | None = None,
    ) -> list[UrbanDefinition]:
        """Search Urban Dictionary for definitions of a term."""
        term_clean = term.strip()
        if not term_clean:
            return []

        cache_key = self._cache_key("search", f"{term_clean}_{strict}_{limit}")
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        params: dict[str, Any] = {
            "term": term_clean,
            "strict": "true" if strict else "false",
        }
        if limit is not None:
            params["limit"] = limit

        data = self._request("/api/search", params)
        if not data or not isinstance(data, dict):
            return []

        items = data.get("data", [])
        if not isinstance(items, list):
            return []

        definitions: list[UrbanDefinition] = []
        term_lower = term_clean.lower()

        for it in items:
            if not isinstance(it, dict):
                continue
            entry = UrbanDefinition.from_api_item(it)
            # If strict is requested, ensure headword matches query
            if strict and entry.word.lower() != term_lower:
                continue
            definitions.append(entry)

        if limit is not None:
            definitions = definitions[:limit]

        self._write_cache(cache_key, definitions)
        return definitions

    def lookup(self, term: str, strict: bool = True) -> UrbanDefinition | None:
        """Lookup the top definition for a term, returning None if not found."""
        defs = self.search(term, strict=strict, limit=1)
        return defs[0] if defs else None

    def is_slang_defined(self, term: str) -> bool:
        """Check whether a slang word or phrase has an active definition on Urban Dictionary."""
        return self.lookup(term, strict=True) is not None

    def get_random(self, limit: int | None = 1) -> list[UrbanDefinition]:
        """Retrieve random slang terms from Urban Dictionary."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit

        data = self._request("/api/random", params)
        if not data or not isinstance(data, dict):
            return []

        items = data.get("data", [])
        if not isinstance(items, list):
            return []

        defs = [UrbanDefinition.from_api_item(it) for it in items if isinstance(it, dict)]
        if limit is not None:
            defs = defs[:limit]
        return defs

    def extract_and_define_slang(
        self,
        text: str,
        candidate_words: list[str] | None = None,
    ) -> dict[str, str]:
        """Extract candidate slang tokens from text and retrieve their Urban Dictionary definitions."""
        if candidate_words is None:
            # Tokenize into clean lowercase alphabetic words of length >= 3
            candidate_words = list({w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", text)})

        results: dict[str, str] = {}
        for word in candidate_words:
            entry = self.lookup(word, strict=True)
            if entry and entry.meaning:
                results[word] = entry.meaning

        return results
