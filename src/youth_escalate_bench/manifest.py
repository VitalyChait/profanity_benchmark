"""SHA-256 manifests for pipeline reproducibility."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ManifestEntry(BaseModel):
    path: str
    row_count: int | None = None
    sha256: str
    bytes: int


class StageManifest(BaseModel):
    stage: str
    benchmark_version: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    config_sha256: str
    random_seed: int
    inputs: list[ManifestEntry] = Field(default_factory=list)
    outputs: list[ManifestEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def write_manifest(manifest: StageManifest, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_manifest(path: Path) -> StageManifest:
    return StageManifest.model_validate_json(path.read_text(encoding="utf-8"))


def manifest_entry_from_file(path: Path, row_count: int | None = None) -> ManifestEntry:
    return ManifestEntry(
        path=str(path),
        row_count=row_count,
        sha256=sha256_file(path),
        bytes=path.stat().st_size,
    )


def config_digest(config: dict[str, Any]) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return sha256_text(canonical)
