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


@main.command("ingest-data")
@click.option("--input", "-i", "input_path", type=click.Path(exists=True, path_type=Path), required=True, help="Path to raw data file (CSV, JSONL, Parquet).")
@click.option("--source-id", "-s", default="generic", help="Source ID in source_registry.yaml (e.g. wikiconv_wikidetox, contextual_abuse_dataset, convotox, gametox, davidson, generic).")
@click.option("--output-dir", "-o", type=click.Path(path_type=Path), default=Path("data/processed/ingest"), help="Destination directory for ingested parquet.")
@click.option("--platform-style", default="group_chat", help="Platform style (gaming_chat, group_chat, direct_messaging, forum_thread).")
@click.option("--enforce-gate/--skip-gate", default=True, help="Enforce source legal audit gate.")
def ingest_data_command(
    input_path: Path,
    source_id: str,
    output_dir: Path,
    platform_style: str,
    enforce_gate: bool,
) -> None:
    """Ingest a real-world dataset directly into normalized conversation parquet."""
    from youth_escalate_bench.adapters import get_adapter
    from youth_escalate_bench.io.parquet import write_conversations
    from youth_escalate_bench.manifest import (
        StageManifest,
        config_digest,
        manifest_entry_from_file,
        write_manifest,
    )

    # Gate check
    if enforce_gate and source_id not in ("fixture", "fixture_wikiconv", "fixture_cad"):
        reg = load_registry(Path("configs/source_registry.yaml"))
        approved = {s.source_id for s in reg.approved_sources()}
        if source_id not in approved:
            click.echo(f"❌ Source '{source_id}' not found or not approved in configs/source_registry.yaml.")
            raise SystemExit(1)

    adapter = get_adapter(source_id, platform_style=platform_style)
    click.echo(f"Ingesting '{input_path}' using adapter for '{source_id}'...")
    convs = adapter.load(input_path)

    if not convs:
        click.echo("⚠️ No conversations could be parsed from input file.")
        raise SystemExit(1)

    total_turns = sum(len(c.turns) for c in convs)
    unique_speakers = len({t.speaker_id for c in convs for t in c.turns})

    output_dir.mkdir(parents=True, exist_ok=True)
    out_parquet = output_dir / "conversations.parquet"
    write_conversations(out_parquet, convs)

    cfg = {"source_id": source_id, "input_path": str(input_path), "platform_style": platform_style}
    manifest = StageManifest(
        stage="ingest",
        benchmark_version="0.1.0",
        config_sha256=config_digest(cfg),
        random_seed=42,
        inputs=[manifest_entry_from_file(input_path)],
        outputs=[manifest_entry_from_file(out_parquet, row_count=total_turns)],
        metadata={"conversations_count": len(convs), "turns_count": total_turns, "speakers_count": unique_speakers},
    )
    write_manifest(manifest, output_dir / "manifest.json")

    click.echo("=" * 60)
    click.echo(f"✓ Ingestion Complete: {len(convs)} conversations, {total_turns} turns, {unique_speakers} unique speakers.")
    click.echo(f"  Parquet output: {out_parquet}")
    click.echo(f"  Manifest: {output_dir / 'manifest.json'}")
    click.echo("=" * 60)



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


@main.command("llm-status")
def show_llm_status() -> None:
    """Show detected LLM API keys and active provider routing (set in .env)."""
    from youth_escalate_bench.llm import get_active_keys, get_llm_config

    config = get_llm_config()
    active_keys = get_active_keys()

    click.echo("=" * 60)
    click.echo("YouthEscalateBench — LLM API Key Status")
    click.echo("=" * 60)
    click.echo(f"Designated key file: {config['env_file']}")
    click.echo(f"File exists: {'✓ Yes' if config['env_exists'] else '✗ Missing (create from .env.example)'}")
    click.echo(f"Active provider: {config['selected_provider']}")
    click.echo("-" * 60)
    click.echo("Detected Providers & Keys:")
    for provider, detected in config["keys_detected"].items():
        status = "✓ ACTIVE" if detected else "✗ Not set"
        key_info = f" ({active_keys[provider]})" if detected and provider in active_keys else ""
        click.echo(f"  - {provider:<12} : {status}{key_info}")
    click.echo("=" * 60)
@main.command("validate-llms")
@click.option("--all", "test_all", is_flag=True, default=False, help="Test all providers (including unconfigured).")
@click.option("--provider", "-p", "providers", multiple=True, help="Specific provider(s) to validate.")
@click.option("--timeout", default=10.0, type=float, help="Timeout in seconds per provider probe.")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Optional path to export JSON/Markdown validation report.")
def validate_llms_command(test_all: bool, providers: tuple[str, ...], timeout: float, output: Path | None) -> None:
    """Run sanity validation probe against configured LLM APIs before real inference."""
    from youth_escalate_bench.llm.validator import validate_all_providers

    target_list = list(providers) if providers else None
    only_configured = not test_all and not bool(providers)

    click.echo("Running LLM validation sanity checks...")
    report = validate_all_providers(providers=target_list, only_configured=only_configured, timeout=timeout)
    click.echo(report.summary_text())

    if output:
        if output.suffix.lower() == ".json":
            report.save_json(output)
            click.echo(f"Report saved to JSON: {output}")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("w", encoding="utf-8") as f:
                f.write(report.to_markdown_table())
            click.echo(f"Report saved to Markdown table: {output}")


if __name__ == "__main__":
    main()

