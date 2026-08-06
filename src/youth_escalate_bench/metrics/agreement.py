"""Annotation agreement metrics."""

from collections import defaultdict

from youth_escalate_bench.schemas.labels import AnnotationRecord, is_actionable


def krippendorff_alpha_nominal(labels_per_item: list[list[str]]) -> float | None:
    """Nominal Krippendorff alpha for categorical labels."""
    if not labels_per_item:
        return None

    # Flatten to matrix: only items with 2+ annotations
    items = [item for item in labels_per_item if len(item) >= 2]
    if not items:
        return None

    n_coins = 0
    do = 0.0  # observed disagreement
    categories: set[str] = set()
    for item in items:
        categories.update(item)

    sorted(categories)
    for item in items:
        n = len(item)
        n_coins += n
        for i in range(n):
            for j in range(i + 1, n):
                if item[i] != item[j]:
                    do += 1.0
                else:
                    do += 0.0

    if n_coins < 2:
        return None

    do /= (n_coins * (n_coins - 1) / 2) if n_coins > 1 else 1

    # Expected disagreement from category frequencies
    freq: dict[str, float] = defaultdict(float)
    total = 0
    for item in items:
        for cat in item:
            freq[cat] += 1
            total += 1
    for cat in freq:
        freq[cat] /= total

    de = 1.0 - sum(v * v for v in freq.values())

    if de == 0:
        return 1.0
    return 1.0 - do / de


def severity_alpha(annotations: list[AnnotationRecord]) -> float | None:
    """Krippendorff alpha on severity labels grouped by turn."""
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for ann in annotations:
        grouped[(ann.conversation_id, ann.turn_id)].append(ann.severity.value)

    return krippendorff_alpha_nominal(list(grouped.values()))


def actionable_agreement(annotations: list[AnnotationRecord]) -> float | None:
    """Percent agreement on actionable vs non-actionable."""
    grouped: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for ann in annotations:
        grouped[(ann.conversation_id, ann.turn_id)].append(is_actionable(ann.severity))

    agreements: list[float] = []
    for votes in grouped.values():
        if len(votes) < 2:
            continue
        majority = sum(votes) > len(votes) / 2
        agree = sum(1 for v in votes if v == majority) / len(votes)
        agreements.append(agree)

    if not agreements:
        return None
    return sum(agreements) / len(agreements)
