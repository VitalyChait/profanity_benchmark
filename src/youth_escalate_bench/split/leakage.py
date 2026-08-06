"""Split leakage detection."""

from dataclasses import dataclass

from youth_escalate_bench.dedup.minhash import (
    minhash_jaccard,
    minhash_signature,
    normalized_text_hash,
)
from youth_escalate_bench.schemas.conversation import ConversationRecord


@dataclass
class LeakageFinding:
    kind: str
    detail: str


def check_split_leakage(splits: dict[str, list[ConversationRecord]]) -> list[LeakageFinding]:
    findings: list[LeakageFinding] = []
    names = list(splits.keys())

    # Conversation ID overlap
    id_sets = {name: {c.conversation_id for c in convs} for name, convs in splits.items()}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = id_sets[a] & id_sets[b]
            if overlap:
                findings.append(
                    LeakageFinding(
                        "conversation_id_overlap",
                        f"{a}/{b}: {len(overlap)} ids e.g. {list(overlap)[:3]}",
                    )
                )

    # Exact text hash overlap across splits
    hash_sets: dict[str, set[str]] = {}
    for name, convs in splits.items():
        hashes: set[str] = set()
        for conv in convs:
            for turn in conv.turns:
                hashes.add(normalized_text_hash(turn.text))
        hash_sets[name] = hashes

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = hash_sets[a] & hash_sets[b]
            if overlap:
                findings.append(
                    LeakageFinding(
                        "text_hash_overlap",
                        f"{a}/{b}: {len(overlap)} normalized text hashes",
                    )
                )

    # Minimal pair group integrity
    for name, convs in splits.items():
        groups: dict[str, list[str]] = {}
        for conv in convs:
            gid = conv.metadata.get("minimal_pair_group_id")
            if gid:
                groups.setdefault(gid, []).append(conv.conversation_id)
        if groups:
            findings.append(
                LeakageFinding(
                    "minimal_pair_groups",
                    f"{name}: {len(groups)} groups present",
                )
            )

    return findings


def check_near_duplicates_across_splits(
    splits: dict[str, list[ConversationRecord]],
    threshold: float = 0.85,
) -> list[LeakageFinding]:
    findings: list[LeakageFinding] = []
    names = list(splits.keys())

    sigs: dict[str, list[tuple[str, tuple[int, ...]]]] = {}
    for name, convs in splits.items():
        sigs[name] = []
        for conv in convs:
            text = " ".join(t.text for t in conv.turns)
            sigs[name].append((conv.conversation_id, minhash_signature(text)))

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            count = 0
            for id_a, sig_a in sigs[a]:
                for id_b, sig_b in sigs[b]:
                    if minhash_jaccard(sig_a, sig_b) >= threshold:
                        count += 1
            if count:
                findings.append(
                    LeakageFinding(
                        "near_duplicate_cross_split",
                        f"{a}/{b}: {count} pairs >= {threshold}",
                    )
                )

    return findings
