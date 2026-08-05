"""Stratified bootstrap confidence intervals."""

import random
from collections.abc import Callable
from typing import Any


def stratified_bootstrap_ci(
    groups: dict[str, list[Any]],
    statistic: Callable[[list[Any]], float],
    n_samples: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Return (estimate, lower, upper) using conversation-level resampling."""
    rng = random.Random(seed)
    all_items: list[Any] = []
    group_keys = list(groups.keys())
    for items in groups.values():
        all_items.extend(items)

    if not all_items:
        return 0.0, 0.0, 0.0

    estimate = statistic(all_items)
    samples: list[float] = []
    for _ in range(n_samples):
        boot: list[Any] = []
        for key in group_keys:
            pool = groups[key]
            if not pool:
                continue
            boot.extend(rng.choices(pool, k=len(pool)))
        if boot:
            samples.append(statistic(boot))

    if not samples:
        return estimate, estimate, estimate

    samples.sort()
    alpha = (1 - ci) / 2
    lower_idx = int(alpha * len(samples))
    upper_idx = int((1 - alpha) * len(samples)) - 1
    return estimate, samples[lower_idx], samples[upper_idx]
