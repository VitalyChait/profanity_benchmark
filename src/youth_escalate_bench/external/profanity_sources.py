"""Trusted profanity and slur sources ingestion and database compilation."""

from __future__ import annotations

import csv
import json
import re
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

TRUSTED_SOURCES_CONFIG = {
    "google_profanity_words": {
        "name": "Google Banned Words List",
        "url": "https://raw.githubusercontent.com/coffee-and-fun/google-profanity-words/master/data/en.txt",
        "format": "txt",
        "default_severity": 2,
        "default_category": "general_profanity",
        "license": "Public Domain",
    },
    "ldnoobw": {
        "name": "List of Dirty, Naughty, Obscene, and Otherwise Bad Words (LDNOOBW)",
        "url": "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/en",
        "format": "txt",
        "default_severity": 2,
        "default_category": "general_profanity",
        "license": "CC0 Public Domain",
    },
    "dsojevic": {
        "name": "dsojevic/profanity-list",
        "url": "https://raw.githubusercontent.com/dsojevic/profanity-list/main/en.json",
        "format": "json",
        "license": "MIT License",
    },
    "hatecheck": {
        "name": "HateCheck Slur Placeholders",
        "url": "https://raw.githubusercontent.com/paul-rottger/hatecheck-data/main/template_placeholders.csv",
        "format": "csv_placeholders",
        "default_severity": 4,
        "default_category": "slur_hate_speech",
        "license": "CC-BY 4.0",
    },
    "hurtlex_en": {
        "name": "HurtLex English Lexicon (Conservative Subset)",
        "url": "https://raw.githubusercontent.com/valeriobasile/hurtlex/master/lexica/EN/1.2/hurtlex_EN.tsv",
        "format": "tsv_hurtlex",
        "license": "CC-BY-NC 4.0",
    },
}


@dataclass
class ProfanityTerm:
    """Standardized entry in the unified profanity database."""

    word: str
    severity: int  # 1 (mild) to 4 (severe / slurs / shock)
    categories: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    match_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfanityTerm:
        return cls(**data)


class ProfanityDatabase:
    """Unified profanity lookup and classification database."""

    def __init__(self, terms: dict[str, ProfanityTerm] | None = None) -> None:
        self.terms: dict[str, ProfanityTerm] = terms or {}

    def lookup(self, word: str) -> ProfanityTerm | None:
        clean = word.strip().lower()
        return self.terms.get(clean)

    def is_profane(self, word: str) -> bool:
        return self.lookup(word) is not None

    def get_severity(self, word: str) -> int:
        entry = self.lookup(word)
        return entry.severity if entry else 0

    def stats(self) -> dict[str, Any]:
        cat_counts: dict[str, int] = {}
        sev_counts: dict[int, int] = {}
        src_counts: dict[str, int] = {}

        for term in self.terms.values():
            sev_counts[term.severity] = sev_counts.get(term.severity, 0) + 1
            for cat in term.categories:
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
            for src in term.sources:
                src_counts[src] = src_counts.get(src, 0) + 1

        return {
            "total_terms": len(self.terms),
            "by_severity": dict(sorted(sev_counts.items())),
            "by_category": dict(sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)),
            "by_source": dict(sorted(src_counts.items(), key=lambda x: x[1], reverse=True)),
        }

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "metadata": self.stats(),
            "terms": {k: v.to_dict() for k, v in sorted(self.terms.items())},
        }
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_json(cls, path: Path) -> ProfanityDatabase:
        if not path.exists():
            return cls()
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        terms_data = data.get("terms", {})
        terms = {k: ProfanityTerm.from_dict(v) for k, v in terms_data.items()}
        return cls(terms=terms)


def fetch_source_text(url: str, cache_path: Path, timeout: float = 12.0) -> str:
    """Fetch remote text resource with disk caching."""
    if cache_path.exists():
        try:
            return cache_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "YouthEscalateBench/0.1.0 (+https://github.com/VitalyChait/profanity_benchmark)"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(text, encoding="utf-8")
            return text
    except Exception as e:
        logger.warning("fetch_profanity_source_failed", url=url, error=str(e))
        return ""


def parse_google_list(raw_text: str) -> list[ProfanityTerm]:
    """Parse Google banned words list (one term per line)."""
    terms: list[ProfanityTerm] = []
    for line in raw_text.splitlines():
        word = line.strip().lower()
        if word and not word.startswith("#"):
            terms.append(
                ProfanityTerm(
                    word=word,
                    severity=2,
                    categories=["general_profanity"],
                    sources=["google_profanity_words"],
                )
            )
    return terms


def parse_ldnoobw_list(raw_text: str) -> list[ProfanityTerm]:
    """Parse LDNOOBW word list."""
    terms: list[ProfanityTerm] = []
    for line in raw_text.splitlines():
        word = line.strip().lower()
        if word and not word.startswith("#"):
            terms.append(
                ProfanityTerm(
                    word=word,
                    severity=2,
                    categories=["general_profanity"],
                    sources=["ldnoobw"],
                )
            )
    return terms


def parse_dsojevic_json(raw_text: str) -> list[ProfanityTerm]:
    """Parse dsojevic JSON structure with severity and categories."""
    terms: list[ProfanityTerm] = []
    try:
        data = json.loads(raw_text)
    except Exception:
        return terms

    for item in data:
        if not isinstance(item, dict):
            continue
        word = str(item.get("id", "")).strip().lower()
        if not word:
            continue
        sev = int(item.get("severity", 2))
        tags = [str(t).lower() for t in item.get("tags", [])]
        match_str = str(item.get("match", ""))
        patterns = [p.strip().lower() for p in match_str.split("|") if p.strip()]

        terms.append(
            ProfanityTerm(
                word=word,
                severity=sev,
                categories=tags,
                sources=["dsojevic"],
                match_patterns=patterns,
            )
        )
    return terms


def parse_hatecheck_placeholders(raw_text: str) -> list[ProfanityTerm]:
    """Parse HateCheck slur and leetspeak placeholders."""
    terms: list[ProfanityTerm] = []
    reader = csv.reader(raw_text.splitlines())
    for row in reader:
        if not row or len(row) < 2:
            continue
        placeholder, values_str = row[0].strip(), row[1].strip()
        if "SLUR" in placeholder.upper():
            is_leet = "leet" in placeholder.lower()
            vals = [v.strip().lower() for v in values_str.split(",") if v.strip()]
            for v in vals:
                cats = ["slur_hate_speech"]
                if is_leet:
                    cats.append("leetspeak_evasion")
                terms.append(
                    ProfanityTerm(
                        word=v,
                        severity=4,
                        categories=cats,
                        sources=["hatecheck"],
                    )
                )
    return terms


def parse_hurtlex_tsv(raw_text: str) -> list[ProfanityTerm]:
    """Parse HurtLex TSV (filtering to offensive/slur categories: cds, asm, om, is)."""
    terms: list[ProfanityTerm] = []
    category_map = {
        "cds": "derogatory_insult",
        "asm": "slur_hate_speech",
        "om": "offensive_sexual",
        "is": "insult",
        "re": "hostile_reproach",
    }
    reader = csv.reader(raw_text.splitlines(), delimiter="\t")
    header = True
    for row in reader:
        if header:
            header = False
            continue
        if len(row) < 6:
            continue
        # id, pos, category, stereotype, lemma, level
        cat_code = row[2].strip().lower()
        lemma = row[4].strip().lower()
        level = row[5].strip().lower()

        # Only select high-confidence offensive categories in conservative level
        if level == "conservative" and cat_code in category_map and len(lemma) >= 3:
            # Map category code to human readable name
            cat_name = category_map[cat_code]
            sev = 4 if cat_code == "asm" else 3 if cat_code in ("cds", "om") else 2
            terms.append(
                ProfanityTerm(
                    word=lemma,
                    severity=sev,
                    categories=[cat_name],
                    sources=["hurtlex_en"],
                )
            )
    return terms


def compile_profanity_database(
    cache_dir: Path | None = None,
    seed_lexicon_path: Path | None = None,
) -> ProfanityDatabase:
    """Ingest, normalize, and merge all trusted profanity sources into a unified database."""
    cache = cache_dir or Path(".cache/profanity_sources")
    cache.mkdir(parents=True, exist_ok=True)

    terms_map: dict[str, ProfanityTerm] = {}

    def _merge_term(new_term: ProfanityTerm) -> None:
        w = re.sub(r"\s+", " ", new_term.word).strip().lower()
        if not w or len(w) < 2:
            return

        if w in terms_map:
            curr = terms_map[w]
            # Maximize severity score
            curr.severity = max(curr.severity, new_term.severity)
            for c in new_term.categories:
                if c not in curr.categories:
                    curr.categories.append(c)
            for s in new_term.sources:
                if s not in curr.sources:
                    curr.sources.append(s)
            for p in new_term.match_patterns:
                if p not in curr.match_patterns:
                    curr.match_patterns.append(p)
        else:
            terms_map[w] = new_term

    # 1. Existing YouthEscalateBench seed words
    seed_path = seed_lexicon_path or Path("configs/profanity_lexicon.txt")
    if seed_path.exists():
        for line in seed_path.read_text(encoding="utf-8").splitlines():
            word = line.strip().lower()
            if word and not word.startswith("#"):
                _merge_term(
                    ProfanityTerm(
                        word=word,
                        severity=3 if word in ("kill", "die", "unalive", "kys") else 2,
                        categories=["bench_seed_insult"],
                        sources=["bench_seeds"],
                    )
                )

    # 2. Ingest Google Profanity Words
    google_text = fetch_source_text(
        TRUSTED_SOURCES_CONFIG["google_profanity_words"]["url"],
        cache / "google_en.txt",
    )
    for t in parse_google_list(google_text):
        _merge_term(t)

    # 3. Ingest LDNOOBW
    ldnoobw_text = fetch_source_text(
        TRUSTED_SOURCES_CONFIG["ldnoobw"]["url"],
        cache / "ldnoobw_en.txt",
    )
    for t in parse_ldnoobw_list(ldnoobw_text):
        _merge_term(t)

    # 4. Ingest dsojevic JSON
    dsojevic_text = fetch_source_text(
        TRUSTED_SOURCES_CONFIG["dsojevic"]["url"],
        cache / "dsojevic_en.json",
    )
    for t in parse_dsojevic_json(dsojevic_text):
        _merge_term(t)

    # 5. Ingest HateCheck Placeholders
    hatecheck_text = fetch_source_text(
        TRUSTED_SOURCES_CONFIG["hatecheck"]["url"],
        cache / "hatecheck_placeholders.csv",
    )
    for t in parse_hatecheck_placeholders(hatecheck_text):
        _merge_term(t)

    # 6. Ingest HurtLex (Conservative Subset)
    hurtlex_text = fetch_source_text(
        TRUSTED_SOURCES_CONFIG["hurtlex_en"]["url"],
        cache / "hurtlex_en.tsv",
    )
    for t in parse_hurtlex_tsv(hurtlex_text):
        _merge_term(t)

    return ProfanityDatabase(terms=terms_map)


def sync_lexicon_files(
    db: ProfanityDatabase,
    lexicon_txt_path: Path,
    database_json_path: Path,
    original_seed_path: Path | None = None,
) -> tuple[int, int]:
    """Write unified profanity database JSON and updated profanity_lexicon.txt.

    Preserves original seed words at the top of profanity_lexicon.txt.
    """
    # 1. Save structured database JSON
    db.save_json(database_json_path)

    # 2. Gather original seed words
    original_seeds: list[str] = []
    seed_file = original_seed_path or lexicon_txt_path
    if seed_file.exists():
        for line in seed_file.read_text(encoding="utf-8").splitlines():
            s = line.strip().lower()
            if s and not s.startswith("#") and s not in original_seeds:
                original_seeds.append(s)

    # 3. Add remaining terms sorted alphabetically
    all_terms = sorted(db.terms.keys())
    remaining_terms = [t for t in all_terms if t not in original_seeds]

    final_lines = [
        "# YouthEscalateBench Unified Profanity & Slur Lexicon",
        f"# Total compiled entries: {len(all_terms)}",
        "# ----------------------------------------------------",
        "# Section 1: Core Benchmark Seed Words",
        "# ----------------------------------------------------",
    ]
    final_lines.extend(original_seeds)
    final_lines.extend(
        [
            "",
            "# ----------------------------------------------------",
            "# Section 2: Ingested Trusted Sources (Google, dsojevic, LDNOOBW, HurtLex, HateCheck)",
            "# ----------------------------------------------------",
        ]
    )
    final_lines.extend(remaining_terms)

    lexicon_txt_path.parent.mkdir(parents=True, exist_ok=True)
    lexicon_txt_path.write_text("\n".join(final_lines) + "\n", encoding="utf-8")

    return len(original_seeds), len(all_terms)
