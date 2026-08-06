"""YouthEscalateBench CLI."""

from pathlib import Path

import click

from youth_escalate_bench.evaluator.server import serve
from youth_escalate_bench.pipeline import get_runner, load_config, run_stage
from youth_escalate_bench.schemas.export import export_all
from youth_escalate_bench.schemas.taxonomy import PIPELINE_STAGES
from youth_escalate_bench.source_registry import audit_gate_passes, load_registry

E2E_STAGES = [
    "source_audit",
    "ingest",
    "redact",
    "thread",
    "transform",
    "annotate_export",
    "split",
    "evaluate",
]


@click.group()
def main() -> None:
    """YouthEscalateBench pipeline and evaluation toolkit."""


@main.command("stages")
def list_stages() -> None:
    """List available pipeline stages."""
    for stage in PIPELINE_STAGES:
        click.echo(stage)


@main.command("run")
@click.option("--stage", required=True, type=click.Choice(PIPELINE_STAGES, case_sensitive=False))
@click.option("--config", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--input-dir", type=click.Path(path_type=Path), default=Path("data/interim"))
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("data/processed"))
def run_pipeline_stage(
    stage: str,
    config: Path,
    input_dir: Path,
    output_dir: Path,
) -> None:
    """Run a single pipeline stage."""
    stage_output = output_dir / stage
    runner = get_runner(stage)
    manifest = run_stage(stage, config, input_dir, stage_output, runner)
    click.echo(f"Stage {stage} complete. Manifest: {stage_output / 'manifest.json'}")
    click.echo(f"Outputs: {len(manifest.outputs)} files")


@main.command("audit-sources")
@click.option(
    "--registry",
    type=click.Path(exists=True, path_type=Path),
    default=Path("configs/source_registry.yaml"),
)
def audit_sources(registry: Path) -> None:
    """Check source registry gate (Phase 1)."""
    reg = load_registry(registry)
    passed, failures = audit_gate_passes(reg)
    click.echo(f"Coverage: {reg.coverage_pct():.1f}% documented")
    click.echo(f"Pending: {len(reg.pending_sources())}")
    if passed:
        click.echo("GATE PASS: all sources have documented legal status")
    else:
        click.echo("GATE FAIL:")
        for f in failures:
            click.echo(f"  - {f}")
        raise SystemExit(1)


@main.command("serve")
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8080, type=int)
@click.option(
    "--lexicon",
    type=click.Path(exists=True, path_type=Path),
    default=Path("configs/profanity_lexicon.txt"),
)
def serve_evaluator(host: str, port: int, lexicon: Path) -> None:
    """Start private /predict evaluator server (baseline scorer default)."""
    serve(host=host, port=port, lexicon_path=lexicon)


@main.command("export-schemas")
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("schemas/json"))
def export_schemas(output_dir: Path) -> None:
    """Export JSON Schema for inference and annotation contracts."""
    paths = export_all(output_dir)
    for p in paths:
        click.echo(p)


@main.command("e2e")
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("data/e2e"))
def run_e2e(output_dir: Path) -> None:
    """Run miniature end-to-end pipeline on fixture data."""
    configs = {
        "source_audit": Path("configs/stages/source_audit.yaml"),
        "ingest": Path("configs/stages/ingest.yaml"),
        "redact": Path("configs/stages/redact.yaml"),
        "thread": Path("configs/stages/thread.yaml"),
        "transform": Path("configs/stages/transform.yaml"),
        "split": Path("configs/stages/split.yaml"),
        "annotate_export": Path("configs/stages/annotate_export.yaml"),
        "evaluate": Path("configs/stages/evaluate.yaml"),
    }
    processed = output_dir / "processed"

    def input_for(stage: str) -> Path:
        if stage in ("source_audit", "ingest"):
            return Path("data/raw")
        if stage in ("annotate_export", "split"):
            return processed / "thread"
        if stage == "evaluate":
            return processed / "split"
        prev = E2E_STAGES[E2E_STAGES.index(stage) - 1]
        return processed / prev

    for stage in E2E_STAGES:
        stage_out = processed / stage
        runner = get_runner(stage)
        run_stage(stage, configs[stage], input_for(stage), stage_out, runner)
        click.echo(f"  ✓ {stage}")
    click.echo(f"E2E complete: {processed}")


@main.command("validate-config")
@click.argument("config_path", type=click.Path(exists=True, path_type=Path))
def validate_config(config_path: Path) -> None:
    """Validate a stage YAML config loads correctly."""
    cfg = load_config(config_path)
    click.echo(f"Valid config: {config_path}")
    click.echo(f"  benchmark_version: {cfg.get('benchmark_version')}")
    click.echo(f"  random_seed: {cfg.get('random_seed')}")


if __name__ == "__main__":
    main()
