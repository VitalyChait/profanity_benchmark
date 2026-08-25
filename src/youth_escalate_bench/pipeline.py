"""Pipeline stage registry and runners.

KEY LOCATION:
- Set LLM API keys in `.env` at repository root to enable live LLM evaluation & synthetic generation.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog
import yaml

from youth_escalate_bench.manifest import (
    StageManifest,
    config_digest,
    manifest_entry_from_file,
    write_manifest,
)
from youth_escalate_bench.schemas.taxonomy import PIPELINE_STAGES
from youth_escalate_bench.stages import STAGE_IMPLEMENTATIONS

logger = structlog.get_logger()

StageFn = Callable[[dict[str, Any], Path, Path], dict[str, Any]]


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_stage(
    stage_name: str,
    config_path: Path,
    input_dir: Path,
    output_dir: Path,
    runner: StageFn,
    config_overrides: dict[str, Any] | None = None,
) -> StageManifest:
    config = load_config(config_path)
    if config_overrides:
        config.update(config_overrides)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("stage_start", stage=stage_name, config=str(config_path))
    result_meta = runner(config, input_dir, output_dir)

    outputs: list = []
    for rel_path in result_meta.get("output_files", []):
        out_path = output_dir / rel_path
        if out_path.exists():
            row_counts = result_meta.get("row_counts", {})
            outputs.append(manifest_entry_from_file(out_path, row_count=row_counts.get(rel_path)))

    manifest = StageManifest(
        stage=stage_name,
        benchmark_version=config.get("benchmark_version", "0.1.0"),
        config_sha256=config_digest(config),
        random_seed=config.get("random_seed", 42),
        outputs=outputs,
        metadata=result_meta.get("metadata", {}),
    )
    manifest_path = output_dir / "manifest.json"
    write_manifest(manifest, manifest_path)
    logger.info("stage_complete", stage=stage_name, manifest=str(manifest_path))
    return manifest


STAGE_RUNNERS: dict[str, StageFn] = dict(STAGE_IMPLEMENTATIONS)

for stage in PIPELINE_STAGES:
    if stage not in STAGE_RUNNERS:
        from youth_escalate_bench.stages import _stub_stage

        STAGE_RUNNERS[stage] = _stub_stage(stage)


def get_runner(stage: str) -> StageFn:
    if stage not in STAGE_RUNNERS:
        raise ValueError(f"Unknown stage: {stage}. Valid: {PIPELINE_STAGES}")
    return STAGE_RUNNERS[stage]


def register_runner(stage: str, fn: StageFn) -> None:
    STAGE_RUNNERS[stage] = fn
