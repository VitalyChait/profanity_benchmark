"""PII detection and redaction (first pass)."""

import re
from dataclasses import dataclass

PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("url", re.compile(r"https?://[^\s]+|www\.[^\s]+")),
    ("phone", re.compile(r"\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    (
        "username_at",
        re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,30}(?!\w)"),
    ),
]


@dataclass
class PIIHit:
    pattern_name: str
    start: int
    end: int
    matched_text: str


def detect_pii(text: str) -> list[PIIHit]:
    hits: list[PIIHit] = []
    for name, pattern in PII_PATTERNS:
        for match in pattern.finditer(text):
            hits.append(
                PIIHit(
                    pattern_name=name,
                    start=match.start(),
                    end=match.end(),
                    matched_text=match.group(),
                )
            )
    return hits


def redact_text(text: str, replacement: str = "[REDACTED]") -> tuple[str, list[PIIHit]]:
    hits = detect_pii(text)
    if not hits:
        return text, hits
    # Redact from end to start to preserve indices
    redacted = text
    for hit in sorted(hits, key=lambda h: h.start, reverse=True):
        redacted = redacted[:hit.start] + replacement + redacted[hit.end:]
    return redacted, hits


def redact_conversation_texts(texts: list[str]) -> tuple[list[str], int]:
    total_hits = 0
    redacted: list[str] = []
    for text in texts:
        new_text, hits = redact_text(text)
        redacted.append(new_text)
        total_hits += len(hits)
    return redacted, total_hits
