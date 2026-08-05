"""Deterministic algospeak transformation operators."""

import re
from collections.abc import Callable
from enum import StrEnum

from youth_escalate_bench.manifest import sha256_text


class TransformFamily(StrEnum):
    LEETSPEAK = "leetspeak"
    SPACING = "spacing"
    REPEATED_CHARS = "repeated_chars"
    HOMOGLYPH = "homoglyph"
    EMOJI_SUBSTITUTION = "emoji_substitution"


LEET_MAP: dict[str, str] = {
    "a": "4",
    "e": "3",
    "i": "1",
    "o": "0",
    "s": "5",
    "t": "7",
}

HOMOGLYPH_MAP: dict[str, str] = {
    "a": "а",  # Cyrillic
    "e": "е",
    "o": "о",
    "c": "с",
}

EMOJI_MAP: dict[str, str] = {
    "trash": "🗑️",
    "skull": "💀",
    "fire": "🔥",
}


def apply_leetspeak(text: str) -> str:
    out = []
    for ch in text:
        lower = ch.lower()
        if lower in LEET_MAP:
            out.append(LEET_MAP[lower] if ch.islower() else LEET_MAP[lower].upper())
        else:
            out.append(ch)
    return "".join(out)


def apply_spacing(text: str) -> str:
    return " ".join(text)


def apply_repeated_chars(text: str) -> str:
    out = []
    for ch in text:
        if ch.isalpha():
            out.append(ch * 2)
        else:
            out.append(ch)
    return "".join(out)


def apply_homoglyph(text: str) -> str:
    out = []
    for ch in text:
        lower = ch.lower()
        if lower in HOMOGLYPH_MAP:
            repl = HOMOGLYPH_MAP[lower]
            out.append(repl if ch.islower() else repl)
        else:
            out.append(ch)
    return "".join(out)


def apply_emoji_substitution(text: str) -> str:
    result = text
    for word, emoji in EMOJI_MAP.items():
        result = re.sub(rf"\b{word}\b", emoji, result, flags=re.IGNORECASE)
    return result


OPERATORS: dict[TransformFamily, Callable[[str], str]] = {
    TransformFamily.LEETSPEAK: apply_leetspeak,
    TransformFamily.SPACING: apply_spacing,
    TransformFamily.REPEATED_CHARS: apply_repeated_chars,
    TransformFamily.HOMOGLYPH: apply_homoglyph,
    TransformFamily.EMOJI_SUBSTITUTION: apply_emoji_substitution,
}


def transform_text(text: str, families: list[TransformFamily]) -> str:
    result = text
    for family in families:
        result = OPERATORS[family](result)
    return result


def transform_version_hash() -> str:
    """Immutable version id for transformation operator set."""
    payload = "|".join(sorted(TransformFamily))
    return sha256_text(payload)[:16]
