"""Shared stage utilities."""

from pathlib import Path


def find_parquet(input_dir: Path, *names: str) -> Path:
    for name in names:
        direct = input_dir / name
        if direct.exists():
            return direct
        nested = list(input_dir.rglob(name))
        if nested:
            return nested[0]
    raise FileNotFoundError(f"None of {names} found under {input_dir}")
