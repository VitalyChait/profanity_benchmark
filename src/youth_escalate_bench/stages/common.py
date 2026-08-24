"""Shared stage utilities."""

from pathlib import Path


def find_parquet(input_dir: Path, *names: str) -> Path:
    # 1. Direct name matches
    for name in names:
        direct = input_dir / name
        if direct.exists():
            return direct
        nested = list(input_dir.rglob(name))
        if nested:
            return nested[0]

    # 2. Known common parquet candidate names
    common_fallbacks = [
        "conversations_sampled.parquet",
        "conversations_threaded.parquet",
        "conversations_redacted.parquet",
        "conversations.parquet",
        "generated_conversations.parquet",
        "transform_pairs.parquet",
    ]
    for name in common_fallbacks:
        direct = input_dir / name
        if direct.exists():
            return direct

    # 3. Any parquet file in input directory
    parquets = sorted(input_dir.glob("*.parquet"))
    if parquets:
        return parquets[0]

    raise FileNotFoundError(f"None of {names} found under {input_dir}")

