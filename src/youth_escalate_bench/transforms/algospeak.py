"""Deterministic algospeak transformation operators."""

import re
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from youth_escalate_bench.manifest import sha256_text


class TransformFamily(StrEnum):
    LEETSPEAK = "leetspeak"
    SPACING = "spacing"
    REPEATED_CHARS = "repeated_chars"
    HOMOGLYPH = "homoglyph"
    EMOJI_SUBSTITUTION = "emoji_substitution"
    EUPHEMISTIC_ALGO_CODED = "euphemistic_algo_coded"
    PHONETIC_OBFUSCATION = "phonetic_obfuscation"
    DELIMITER_INJECTION = "delimiter_injection"
    ACRONYM_SUBSTITUTION = "acronym_substitution"


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
    "p": "р",
    "x": "х",
}

EMOJI_MAP: dict[str, str] = {
    "trash": "🗑️",
    "skull": "💀",
    "fire": "🔥",
    "clown": "🤡",
    "toxic": "☣️",
    "dead": "☠️",
    "snake": "🐍",
    "poop": "💩",
    "knife": "🔪",
}

EUPHEMISM_MAP: dict[str, str] = {
    "kill yourself": "go unalive your account",
    "killed": "unalived",
    "kill": "unalive",
    "suicide": "sewerslide",
    "porn": "corn",
    "rape": "grape",
    "raped": "graped",
    "abuse": "mascara",
    "sex": "seggs",
    "drugs": "spices",
    "murder": "game end",
    "murdered": "game ended",
    "die": "d1e",
    "hate": "h8",
}

PHONETIC_MAP: dict[str, str] = {
    "fuck": "fuk",
    "fucking": "fukking",
    "bitch": "biatch",
    "bitches": "biatches",
    "asshole": "ashole",
    "dick": "dikk",
    "crap": "krap",
    "loser": "loozer",
    "idiot": "idijot",
    "stupid": "stoopid",
}

ACRONYM_MAP: dict[str, str] = {
    "shut the fuck up": "stfu",
    "get the fuck out": "gtfo",
    "kill yourself": "kys",
    "kill myself": "kms",
    "piece of shit": "pos",
    "what the fuck": "wtf",
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
        result = re.sub(rf"\b{re.escape(word)}\b", emoji, result, flags=re.IGNORECASE)
    return result


def apply_euphemisms(text: str) -> str:
    result = text
    for word, repl in EUPHEMISM_MAP.items():
        result = re.sub(rf"\b{re.escape(word)}\b", repl, result, flags=re.IGNORECASE)
    return result


def apply_phonetics(text: str) -> str:
    result = text
    for word, repl in PHONETIC_MAP.items():
        result = re.sub(rf"\b{re.escape(word)}\b", repl, result, flags=re.IGNORECASE)
    return result


def apply_delimiter_injection(text: str, delimiter: str = "*") -> str:
    words = text.split()
    modified = []
    for word in words:
        if len(word) > 3 and word.isalpha():
            # inject delimiter in middle
            mid = len(word) // 2
            modified.append(word[:mid] + delimiter + word[mid:])
        else:
            modified.append(word)
    return " ".join(modified)


def apply_acronyms(text: str) -> str:
    result = text
    for phrase, acr in ACRONYM_MAP.items():
        result = re.sub(rf"\b{re.escape(phrase)}\b", acr, result, flags=re.IGNORECASE)
    return result


OPERATORS: dict[TransformFamily, Callable[[str], str]] = {
    TransformFamily.LEETSPEAK: apply_leetspeak,
    TransformFamily.SPACING: apply_spacing,
    TransformFamily.REPEATED_CHARS: apply_repeated_chars,
    TransformFamily.HOMOGLYPH: apply_homoglyph,
    TransformFamily.EMOJI_SUBSTITUTION: apply_emoji_substitution,
    TransformFamily.EUPHEMISTIC_ALGO_CODED: apply_euphemisms,
    TransformFamily.PHONETIC_OBFUSCATION: apply_phonetics,
    TransformFamily.DELIMITER_INJECTION: apply_delimiter_injection,
    TransformFamily.ACRONYM_SUBSTITUTION: apply_acronyms,
}


def transform_text(text: str, families: list[TransformFamily]) -> str:
    result = text
    for family in families:
        if family in OPERATORS:
            result = OPERATORS[family](result)
    return result


def transform_version_hash() -> str:
    """Immutable version id for transformation operator set."""
    payload = "|".join(sorted(TransformFamily))
    return sha256_text(payload)[:16]


def verify_slang_in_urban_dictionary(word: str, client: Any | None = None) -> bool:
    """Check whether an algospeak or youth slang term is defined in Urban Dictionary."""
    if client is None:
        from youth_escalate_bench.external.urban_dictionary import UrbanDictionaryClient

        client = UrbanDictionaryClient()
    return bool(client.is_slang_defined(word))
