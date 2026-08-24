"""Near-duplicate detection via character n-gram MinHash."""

import hashlib
from collections.abc import Iterable

import numpy as np

# Fixed random permutation coefficients for deterministic reproducible signatures
_RNG = np.random.RandomState(42)
_MAX_PERM = 256
_A_COEFFS = _RNG.randint(1, 2**31 - 1, size=(_MAX_PERM,), dtype=np.uint64)
_B_COEFFS = _RNG.randint(0, 2**31 - 1, size=(_MAX_PERM,), dtype=np.uint64)
_MERSENNE_PRIME = np.uint64((1 << 61) - 1)


def _shingles(text: str, n: int = 5) -> set[str]:
    normalized = " ".join(text.lower().split())
    if len(normalized) < n:
        return {normalized} if normalized else set()
    return {normalized[i : i + n] for i in range(len(normalized) - n + 1)}



def minhash_signature(text: str, num_perm: int = 64, ngram: int = 5) -> tuple[int, ...]:
    shingles = _shingles(text, ngram)
    if not shingles:
        return tuple(0 for _ in range(num_perm))

    # Compute 64-bit integer hash for each unique shingle once
    shingle_hashes = np.fromiter(
        (
            int.from_bytes(hashlib.md5(s.encode(), usedforsecurity=False).digest()[:8], "big")
            for s in shingles
        ),
        dtype=np.uint64,
        count=len(shingles),
    )

    a = _A_COEFFS[:num_perm]
    b = _B_COEFFS[:num_perm]

    # Vectorized permutation evaluation: (H * A + B) % P
    permuted = (shingle_hashes[:, None] * a[None, :] + b[None, :]) % _MERSENNE_PRIME
    min_sig = np.min(permuted, axis=0)
    return tuple(min_sig.tolist())



def minhash_jaccard(sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
    if len(sig_a) != len(sig_b):
        raise ValueError("signatures must have same length")
    matches = sum(1 for a, b in zip(sig_a, sig_b, strict=True) if a == b)
    return matches / len(sig_a)


def find_near_duplicates(
    texts: Iterable[str],
    threshold: float = 0.8,
    num_perm: int = 64,
    b: int = 16,
) -> list[tuple[int, int, float]]:
    text_list = list(texts)
    if not text_list:
        return []
    signatures = [minhash_signature(t, num_perm=num_perm) for t in text_list]
    r = max(1, num_perm // b)

    # LSH Band Indexing for sublinear candidate pairing
    buckets: dict[tuple[int, tuple[int, ...]], list[int]] = {}
    for doc_id, sig in enumerate(signatures):
        for band_idx in range(b):
            band_tuple = sig[band_idx * r : (band_idx + 1) * r]
            key = (band_idx, band_tuple)
            buckets.setdefault(key, []).append(doc_id)

    candidate_pairs: set[tuple[int, int]] = set()
    for doc_ids in buckets.values():
        if len(doc_ids) > 1:
            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    candidate_pairs.add((min(doc_ids[i], doc_ids[j]), max(doc_ids[i], doc_ids[j])))

    pairs: list[tuple[int, int, float]] = []
    for i, j in candidate_pairs:
        sim = minhash_jaccard(signatures[i], signatures[j])
        if sim >= threshold:
            pairs.append((i, j, sim))
    return pairs


def normalized_text_hash(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()
