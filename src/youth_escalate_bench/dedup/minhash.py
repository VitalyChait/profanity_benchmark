"""Near-duplicate detection via character n-gram MinHash."""

import hashlib
from collections.abc import Iterable


def _shingles(text: str, n: int = 5) -> set[str]:
    normalized = " ".join(text.lower().split())
    if len(normalized) < n:
        return {normalized} if normalized else set()
    return {normalized[i : i + n] for i in range(len(normalized) - n + 1)}


def _hash_shingle(shingle: str, seed: int) -> int:
    h = hashlib.md5(f"{seed}:{shingle}".encode(), usedforsecurity=False)
    return int.from_bytes(h.digest()[:8], "big")


def minhash_signature(text: str, num_perm: int = 128, ngram: int = 5) -> tuple[int, ...]:
    shingles = _shingles(text, ngram)
    if not shingles:
        return tuple(0 for _ in range(num_perm))
    sig: list[int] = []
    for seed in range(num_perm):
        min_val = min(_hash_shingle(s, seed) for s in shingles)
        sig.append(min_val)
    return tuple(sig)


def minhash_jaccard(sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
    if len(sig_a) != len(sig_b):
        raise ValueError("signatures must have same length")
    matches = sum(1 for a, b in zip(sig_a, sig_b, strict=True) if a == b)
    return matches / len(sig_a)


def find_near_duplicates(
    texts: Iterable[str],
    threshold: float = 0.8,
    num_perm: int = 128,
) -> list[tuple[int, int, float]]:
    signatures = [minhash_signature(t, num_perm=num_perm) for t in texts]
    pairs: list[tuple[int, int, float]] = []
    for i in range(len(signatures)):
        for j in range(i + 1, len(signatures)):
            sim = minhash_jaccard(signatures[i], signatures[j])
            if sim >= threshold:
                pairs.append((i, j, sim))
    return pairs


def normalized_text_hash(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()
