"""YouthEscalateBench CLI."""

from pathlib import Path

import click

from youth_escalate_bench import __version__
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
@click.version_option(__version__, "-v", "--version")
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
@click.option(
    "--extended-report",
    "-e",
    is_flag=True,
    default=False,
    help="Generate detailed extended report outputting all failure cases per LLM.",
)
def run_pipeline_stage(
    stage: str,
    config: Path,
    input_dir: Path,
    output_dir: Path,
    extended_report: bool = False,
) -> None:
    """Run a single pipeline stage."""
    stage_output = output_dir if output_dir.name == stage else (output_dir / stage)
    runner = get_runner(stage)
    overrides = {"extended_report": True} if (stage == "report" and extended_report) else None
    manifest = run_stage(stage, config, input_dir, stage_output, runner, config_overrides=overrides)
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
@click.option(
    "--input",
    "-i",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to raw data file (CSV, JSONL, Parquet).",
)
@click.option(
    "--source-id",
    "-s",
    default="generic",
    help="Source ID in source_registry.yaml (e.g. wikiconv_wikidetox, contextual_abuse_dataset, convotox, gametox, davidson, generic).",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("data/processed/ingest"),
    help="Destination directory for ingested parquet.",
)
@click.option(
    "--platform-style",
    default="group_chat",
    help="Platform style (gaming_chat, group_chat, direct_messaging, forum_thread).",
)
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
            click.echo(
                f"❌ Source '{source_id}' not found or not approved in configs/source_registry.yaml."
            )
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
        metadata={
            "conversations_count": len(convs),
            "turns_count": total_turns,
            "speakers_count": unique_speakers,
        },
    )
    write_manifest(manifest, output_dir / "manifest.json")

    click.echo("=" * 60)
    click.echo(
        f"✓ Ingestion Complete: {len(convs)} conversations, {total_turns} turns, {unique_speakers} unique speakers."
    )
    click.echo(f"  Parquet output: {out_parquet}")
    click.echo(f"  Manifest: {output_dir / 'manifest.json'}")
    click.echo("=" * 60)


@main.command("pipeline")
@click.option(
    "--all", "-a", "run_all", is_flag=True, default=False, help="Run all pipeline stages."
)
@click.option(
    "--resume",
    "-r",
    is_flag=True,
    default=False,
    help="Auto-resume from earliest incomplete checkpoint.",
)
@click.option("--step", "-s", "steps", multiple=True, help="Specific pipeline step(s) to run.")
@click.option("--from-step", help="Start execution from this step.")
@click.option("--to-step", help="Stop execution after this step.")
@click.option(
    "--force", "-f", is_flag=True, default=False, help="Force re-execution of completed steps."
)
@click.option("--status", is_flag=True, default=False, help="Show checkpoint status table.")
@click.option("--reset", is_flag=True, default=False, help="Reset all checkpoints.")
@click.option("--dry-run", is_flag=True, default=False, help="Simulate pipeline without executing.")
@click.option(
    "--extended-report",
    "-e",
    is_flag=True,
    default=False,
    help="Generate detailed extended report outputting all failure cases per LLM.",
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["extra-small", "small", "medium", "large", "extra-large"]),
    default="extra-small",
    help="Evaluation scale mode: extra-small=20 (default), small=100, medium=250, large=500, extra-large=1000.",
)
@click.option(
    "--max-samples",
    type=int,
    default=None,
    help="Explicitly override maximum evaluation samples across conditions.",
)
@click.option(
    "--seed",
    "--random-seed",
    "seed",
    type=int,
    default=None,
    help="Controllable random seed for reproducible example selection and pipeline stages.",
)
@click.option(
    "--sample-strategy",
    "sample_strategy",
    type=click.Choice(["auto", "difficulty", "random", "stratified"]),
    default="auto",
    help="Example selection strategy: 'auto', 'difficulty', 'random', or 'stratified'.",
)
@click.option(
    "--difficulty-level",
    "difficulty_level",
    type=click.Choice(["standard", "hard", "extreme", "adversarial"]),
    default="standard",
    help="Benchmark difficulty tier: 'standard', 'hard', 'extreme', or 'adversarial'.",
)
@click.option(
    "--rag",
    is_flag=True,
    default=False,
    help="Enable dynamic slang and pragmatics RAG retrieval for LLM moderation.",
)
@click.option(
    "--rag-compare",
    is_flag=True,
    default=False,
    help="Benchmark standard LLM moderation against RAG-augmented LLMs side-by-side.",
)
def pipeline_command(
    run_all: bool,
    resume: bool,
    steps: tuple[str, ...],
    from_step: str | None,
    to_step: str | None,
    force: bool,
    status: bool,
    reset: bool,
    dry_run: bool,
    extended_report: bool = False,
    mode: str = "extra-small",
    max_samples: int | None = None,
    seed: int | None = None,
    sample_strategy: str = "auto",
    difficulty_level: str = "standard",
    rag: bool = False,
    rag_compare: bool = False,
) -> None:
    """Execute pipeline with automated checkpoints, state recovery, and error diagnostics."""
    from youth_escalate_bench.orchestrator import PipelineRunner

    runner = PipelineRunner()

    if status:
        runner.checkpoint_mgr.display_status()
        return

    if reset:
        runner.checkpoint_mgr.reset_all()
        click.echo("✓ All pipeline checkpoints reset to PENDING.")
        runner.checkpoint_mgr.display_status()
        return

    if not run_all and not resume and not steps and not from_step and not dry_run:
        runner.checkpoint_mgr.display_status()
        click.echo("Run with --all to start full execution, or --resume to continue.")
        return

    success = runner.run(
        target_steps=list(steps) if steps else None,
        from_step=from_step,
        to_step=to_step,
        resume=resume or (not force and not steps),
        force=force,
        dry_run=dry_run,
        extended_report=extended_report,
        mode=mode,
        max_samples=max_samples,
        seed=seed,
        sample_strategy=sample_strategy,
        enable_rag=rag,
        rag_compare=rag_compare,
        difficulty_level=difficulty_level,
    )
    if not success:
        raise SystemExit(1)


@main.command("serve")
@click.option("--host", default="127.0.0.1", help="Host IP to bind evaluator service to.")
@click.option("--port", default=8080, type=int, help="Port to listen on.")
@click.option(
    "--lexicon",
    type=click.Path(exists=True, path_type=Path),
    default=Path("configs/profanity_lexicon.txt"),
    help="Lexicon file used for baseline scoring.",
)
@click.option(
    "--reports-dir",
    type=click.Path(path_type=Path),
    default=Path("reports"),
    help="Directory containing benchmark reports, figures, and summaries.",
)
def serve_evaluator(host: str, port: int, lexicon: Path, reports_dir: Path) -> None:
    """Start private /predict evaluator server and interactive analysis dashboard."""
    serve(host=host, port=port, lexicon_path=lexicon, reports_dir=reports_dir)


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
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_ingest_cfg = output_dir / "ingest_fixture.yaml"
    import yaml

    with fixture_ingest_cfg.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "stage": "ingest",
                "benchmark_version": "0.1.0",
                "default_language_mode": "english",
                "allow_fixture_sources": True,
                "sources": [
                    {
                        "source_id": "fixture",
                        "input_path": "tests/fixtures/sample_conversations.jsonl",
                        "adapter": "jsonl",
                    }
                ],
            },
            f,
        )

    configs = {
        "source_audit": Path("configs/stages/source_audit.yaml"),
        "ingest": fixture_ingest_cfg,
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
    click.echo(
        f"File exists: {'✓ Yes' if config['env_exists'] else '✗ Missing (create from .env.example)'}"
    )
    click.echo(f"Active provider: {config['selected_provider']}")
    click.echo("-" * 60)
    click.echo("Detected Providers & Keys:")
    for provider, detected in config["keys_detected"].items():
        status = "✓ ACTIVE" if detected else "✗ Not set"
        key_info = f" ({active_keys[provider]})" if detected and provider in active_keys else ""
        click.echo(f"  - {provider:<12} : {status}{key_info}")
    click.echo("=" * 60)


@main.command("validate-llms")
@click.option(
    "--all",
    "test_all",
    is_flag=True,
    default=False,
    help="Test all providers (including unconfigured).",
)
@click.option(
    "--provider", "-p", "providers", multiple=True, help="Specific provider(s) to validate."
)
@click.option("--timeout", default=10.0, type=float, help="Timeout in seconds per provider probe.")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Optional path to export JSON/Markdown validation report.",
)
def validate_llms_command(
    test_all: bool, providers: tuple[str, ...], timeout: float, output: Path | None
) -> None:
    """Run sanity validation probe against configured LLM APIs before real inference."""
    from youth_escalate_bench.llm.validator import validate_all_providers

    target_list = list(providers) if providers else None
    only_configured = not test_all and not bool(providers)

    click.echo("Running LLM validation sanity checks...")
    report = validate_all_providers(
        providers=target_list, only_configured=only_configured, timeout=timeout
    )
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


@main.command("audit-models")
@click.option(
    "--lexicon",
    type=click.Path(exists=True, path_type=Path),
    default=Path("configs/profanity_lexicon.txt"),
    help="Lexicon file to construct candidate scorers.",
)
def audit_models_command(lexicon: Path) -> None:
    """Audit LLM models to detect and report any duplicate entries before running evaluation."""
    from youth_escalate_bench.baselines.scorers import build_default_scorers, deduplicate_scorers
    from youth_escalate_bench.llm.keys import audit_llm_model_duplicates, get_expanded_eval_targets

    click.echo("\n" + "=" * 72)
    click.echo("🔍 YouthEscalateBench — LLM Model Duplication Pre-Flight Audit")
    click.echo("=" * 72)

    # 1. Audit environment keys and openrouter list
    env_duplicates = audit_llm_model_duplicates()
    if env_duplicates:
        click.echo(
            f"\n⚠️  Found {len(env_duplicates)} potential duplicate definitions in .env configuration:"
        )
        for d in env_duplicates:
            click.echo(f"   • Duplicate Model : {d['duplicate_model']}")
            click.echo(f"     Scope/Location  : {d['location']}")
            click.echo(f"     Reason          : {d['reason']}")
    else:
        click.echo(
            "\n✅ .env configuration check: Zero duplicate model entries in OPENROUTER_MODELS / REQUESTY_MODELS."
        )

    # 2. Expanded evaluation targets
    targets = get_expanded_eval_targets()
    click.echo(f"\n📋 Active Unique LLM Evaluation Targets ({len(targets)} models):")
    for idx, (prov, mdl) in enumerate(targets, start=1):
        click.echo(f"   {idx:2d}. [{prov}] {mdl}")

    # 3. Full scorers panel audit
    scorers = build_default_scorers(lexicon)
    _, removed = deduplicate_scorers(scorers)
    if removed:
        click.echo(
            f"\n⚠️  Deduplication gate removed {len(removed)} duplicate scorers from evaluation panel:"
        )
        for r in removed:
            click.echo(f"   • Removed  : '{r['removed_scorer']}' ({r['provider']}:{r['model']})")
            click.echo(f"     Retained : '{r['retained_scorer']}'")
            click.echo("     Action   : Excluded from evaluation to save time and API tokens.")
    else:
        click.echo(
            "\n✅ Scorer panel check: All moderation scorers and LLM targets are 100% distinct."
        )

    click.echo("\n" + "=" * 72 + "\n")


@main.command("urban-dict")
@click.argument("term", required=False, default=None)
@click.option("--limit", "-l", default=3, type=int, help="Maximum definitions to display.")
@click.option("--strict", is_flag=True, default=False, help="Match query term strictly.")
@click.option(
    "--random", "-r", "fetch_random", is_flag=True, default=False, help="Fetch random slang terms."
)
@click.option(
    "--api-url",
    default=None,
    help="Custom Urban Dictionary API base URL (default: https://unofficialurbandictionaryapi.com/).",
)
def urban_dict_command(
    term: str | None,
    limit: int,
    strict: bool,
    fetch_random: bool,
    api_url: str | None,
) -> None:
    """Query slang and colloquial definitions against the Unofficial Urban Dictionary API."""
    from youth_escalate_bench.external.urban_dictionary import UrbanDictionaryClient

    client = UrbanDictionaryClient(base_url=api_url)

    if fetch_random:
        click.echo(f"Fetching random slang terms from {client.base_url}...")
        results = client.get_random(limit=limit)
    elif term:
        click.echo(f"Querying Urban Dictionary for '{term}' (strict={strict})...")
        results = client.search(term=term, strict=strict, limit=limit)
    else:
        click.echo("Error: Please provide a term to search, or use --random to browse.")
        raise click.UsageError("Missing argument 'TERM' or flag '--random'.")

    if not results:
        click.echo("No definitions found for query.")
        return

    click.echo("=" * 65)
    click.echo(f"Urban Dictionary Results ({len(results)} entry/entries):")
    click.echo("=" * 65)

    for idx, d in enumerate(results, 1):
        click.echo(f"\n[{idx}] {d.word}")
        click.echo(f"Meaning: {d.meaning}")
        if d.example:
            click.echo(f"Example: {d.example}")
        if d.contributor or d.date:
            attr = f"by {d.contributor}" if d.contributor else ""
            if d.date:
                attr += f" on {d.date}"
            click.echo(f"({attr.strip()})")

    click.echo("=" * 65)


@main.command("difficulty-ranking")
@click.option(
    "--top-sentences", "-s", default=10, type=int, help="Number of hardest sentences to display."
)
@click.option(
    "--top-words", "-w", default=15, type=int, help="Number of most vulnerable words to display."
)
@click.option(
    "--path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to difficulty_ranking.yaml (default: checks reports/ and data/processed/evaluate/).",
)
def difficulty_ranking_command(top_sentences: int, top_words: int, path: Path | None) -> None:
    """View internal difficulty and misclassification rankings for words and sentences."""
    from youth_escalate_bench.evaluation.difficulty import load_difficulty_index

    resolved_path = path
    if not resolved_path:
        for candidate in [
            Path("reports/data/difficulty_ranking.yaml"),
            Path("reports/difficulty_ranking.yaml"),
            Path("data/processed/evaluate/difficulty_ranking.yaml"),
            Path("data/processed/report/difficulty_ranking.yaml"),
        ]:
            if candidate.exists():
                resolved_path = candidate
                break

    if not resolved_path or not resolved_path.exists():
        click.echo("Error: No difficulty_ranking.yaml found. Please run the evaluate stage first:")
        click.echo("  python main.py --step evaluate")
        return

    index = load_difficulty_index(resolved_path)
    if not index:
        click.echo(f"Error: Unable to parse difficulty ranking file at {resolved_path}")
        return

    meta = index.metadata
    click.echo("=" * 80)
    click.echo("YouthEscalateBench — Internal Evaluation Difficulty Ranking")
    click.echo(f"Source file : {resolved_path}")
    click.echo(f"Generated   : {meta.get('generated_at', 'N/A')}")
    click.echo(
        f"Total turns : {meta.get('total_evaluated_turns', 0)} ({meta.get('total_misclassified_turns', 0)} misclassified)"
    )
    click.echo("=" * 80)

    # 1. Top Sentences
    click.echo(f"\n[ Top {top_sentences} Hardest Sentences / Turns ]")
    click.echo("-" * 80)
    click.echo(f"{'Rank':<5} {'Priority':<9} {'Error Rate':<12} {'Type':<22} {'Turn Text'}")
    click.echo("-" * 80)
    for rank, s in enumerate(index.sentences[:top_sentences], 1):
        clean_text = s.turn_text.replace("\n", " ").strip()
        if len(clean_text) > 45:
            clean_text = clean_text[:42] + "..."
        err_str = f"{s.error_rate * 100:.0f}% ({s.total_errors}/{s.total_evaluations})"
        click.echo(
            f'#{rank:<4} {s.priority_weight:<9.2f} {err_str:<12} {s.primary_error_type[:20]:<22} "{clean_text}"'
        )

    # 2. Top Words
    click.echo(f"\n[ Top {top_words} Most Vulnerable Words / Slang Terms ]")
    click.echo("-" * 80)
    click.echo(
        f"{'Rank':<5} {'Word/Slang':<18} {'Vuln Score':<12} {'Count':<8} {'Error Rate':<12} {'Failure Mode'}"
    )
    click.echo("-" * 80)
    for rank, w in enumerate(index.words[:top_words], 1):
        err_rate_str = f"{w.error_rate * 100:.0f}%"
        click.echo(
            f"#{rank:<4} {w.word:<18} {w.vulnerability_score:<12.3f} {w.total_occurrences:<8} {err_rate_str:<12} {w.primary_failure_mode}"
        )

    click.echo("=" * 80)


@main.command("profanity-check")
@click.argument("term")
def profanity_check_command(term: str) -> None:
    """Check whether a word or phrase is in the unified trusted profanity database."""
    from youth_escalate_bench.external.profanity_sources import ProfanityDatabase

    db_path = Path("configs/lexicons/profanity_database.json")
    db = ProfanityDatabase.load_json(db_path)
    entry = db.lookup(term)

    if not entry:
        click.echo(f"Term '{term}' is NOT in the unified profanity database.")
        return

    click.echo(f"Term        : {entry.word}")
    click.echo(f"Severity    : Level {entry.severity} / 4")
    click.echo(f"Categories  : {', '.join(entry.categories) if entry.categories else 'None'}")
    click.echo(f"Sources     : {', '.join(entry.sources)}")
    if entry.match_patterns:
        click.echo(f"Patterns    : {', '.join(entry.match_patterns[:5])}")


@main.command("lexicon-stats")
def lexicon_stats_command() -> None:
    """Display statistics for the unified profanity database and lexicons."""
    from youth_escalate_bench.external.profanity_sources import ProfanityDatabase

    db_path = Path("configs/lexicons/profanity_database.json")
    db = ProfanityDatabase.load_json(db_path)
    stats = db.stats()

    click.echo("=" * 65)
    click.echo("YouthEscalateBench — Unified Profanity Lexicon Statistics")
    click.echo("=" * 65)
    click.echo(f"Total Unique Terms: {stats['total_terms']:,}")
    click.echo("\nTerms by Severity:")
    for sev, count in stats.get("by_severity", {}).items():
        label = {1: "Mild", 2: "Moderate", 3: "Severe / Toxic", 4: "Extreme / Slurs"}.get(sev, "")
        click.echo(f"  Level {sev} ({label:<16}): {count:,}")
    click.echo("\nTop Categories:")
    for cat, count in list(stats.get("by_category", {}).items())[:8]:
        click.echo(f"  {cat:<22}: {count:,}")
    click.echo("\nContributing Sources:")
    for src, count in stats.get("by_source", {}).items():
        click.echo(f"  {src:<22}: {count:,}")
    click.echo("=" * 65)


@main.command("update-lexicon")
def update_lexicon_command() -> None:
    """Ingest and recompile trusted profanity sources into the database and lexicon."""
    from youth_escalate_bench.external.profanity_sources import (
        compile_profanity_database,
        sync_lexicon_files,
    )

    click.echo(
        "Fetching and compiling trusted profanity sources (Google, dsojevic, LDNOOBW, HurtLex, HateCheck)..."
    )
    db = compile_profanity_database()
    seeds, total = sync_lexicon_files(
        db=db,
        lexicon_txt_path=Path("configs/profanity_lexicon.txt"),
        database_json_path=Path("configs/lexicons/profanity_database.json"),
    )
    click.echo(f"Done! {seeds} seed words preserved. {total:,} total unique profanities compiled.")


@main.command("audit-pii")
@click.option(
    "--sample-size", "-n", default=200, type=int, help="Number of random conversations to inspect."
)
@click.option(
    "--dataset",
    type=click.Path(path_type=Path),
    default=Path("data/processed/split/split_test.parquet"),
    help="Path to dataset parquet file.",
)
def audit_pii_command(sample_size: int, dataset: Path) -> None:
    """Perform an independent spot-check audit for residual PII entities."""
    from youth_escalate_bench.pii.audit import generate_pii_audit_markdown, run_pii_audit

    target = dataset
    if not target.exists():
        for candidate in [
            Path("data/processed/split/split_test.parquet"),
            Path("data/processed/redact/conversations_redacted.parquet"),
            Path("data/processed/split/split_train.parquet"),
            Path("data/processed/sample/conversations_sampled.parquet"),
            Path("tests/fixtures/sample_conversations.parquet"),
        ]:
            if candidate.exists():
                target = candidate
                break

    click.echo(f"Auditing sample of {sample_size} conversations from {target}...")
    results = run_pii_audit(target, sample_size=sample_size)
    if results.get("status") == "error":
        click.echo(f"Error: {results.get('error')}")
        click.echo(f"PII Spot-Check Result: {results['status'].upper()}")
        click.echo("Inspected Turns     : 0")
        click.echo("Residual Flags Found: 0")
        return

    report_content = generate_pii_audit_markdown(results)
    report_path = Path("reports/pii_spot_check_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_content, encoding="utf-8")

    click.echo("=" * 65)
    click.echo(f"PII Spot-Check Result: {results['status'].upper()}")
    click.echo(f"Inspected Turns     : {results['total_turns']}")
    click.echo(f"Residual Flags Found: {results.get('flag_count', 0)}")
    click.echo(f"Formal Report Saved : {report_path}")
    click.echo("=" * 65)


@main.command("create-snapshot")
@click.option("--tag", default="2026.Q1", help="Version tag for quarterly release.")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("reports/snapshots"),
    help="Output directory.",
)
def create_snapshot_command(tag: str, output_dir: Path) -> None:
    """Create a sealed quarterly snapshot bundle with Croissant metadata and SHA256."""
    from youth_escalate_bench.snapshot import create_snapshot_bundle

    click.echo(f"Packaging quarterly release snapshot bundle '{tag}'...")
    res = create_snapshot_bundle(output_dir=output_dir, version_tag=tag)
    click.echo("=" * 65)
    click.echo("Quarterly Snapshot Packaged Successfully!")
    click.echo(f"Version Tag : {res['version_tag']}")
    click.echo(f"Archive File: {res['archive_path']}")
    click.echo(f"SHA256      : {res['sha256']}")
    click.echo(f"Files Count : {len(res['files_included'])}")
    click.echo("=" * 65)


@main.command("agent-discover")
@click.option(
    "--random-limit",
    "-r",
    default=5,
    type=int,
    help="Number of random Urban Dictionary terms to scout.",
)
@click.option(
    "--terms", "-t", default=None, type=str, help="Comma-separated target slang terms to verify."
)
def agent_discover_command(random_limit: int, terms: str | None) -> None:
    """Run an autonomous agentic discovery pass to scout and verify new profanity/slang."""
    from youth_escalate_bench.agents.runner import DiscoveryLoop

    target_list = [w.strip() for w in terms.split(",") if w.strip()] if terms else None
    click.echo("Launching Autonomous Discovery Agent...")
    loop = DiscoveryLoop()
    res = loop.run_discovery_cycle(target_terms=target_list, random_limit=random_limit)
    click.echo("=" * 65)
    click.echo("Agentic Discovery Pass Complete!")
    click.echo(f"Candidates Scouted : {res['candidates_count']}")
    new_terms_str = ", ".join(res["new_terms_added"]) if res["new_terms_added"] else "None"
    click.echo(f"New Terms Ingested : {len(res['new_terms_added'])} ({new_terms_str})")
    click.echo(f"Pairs Synthesized  : {res['contrastive_pairs_count']}")
    click.echo("Audit Digest       : reports/agentic_discovery_digest.md")
    click.echo("=" * 65)


@main.command("cache-stats")
def cache_stats_command() -> None:
    """Display statistics for the persistent LLM response cache and token savings."""
    from youth_escalate_bench.cache import get_default_llm_cache

    cache = get_default_llm_cache()
    stats = cache.stats()
    hits = stats["cache_hits"]
    misses = stats["cache_misses"]
    total = hits + misses
    hit_rate = (hits / total * 100.0) if total > 0 else 0.0

    click.echo("=" * 65)
    click.echo("YouthEscalateBench — LLM Response Cache & Token Savings")
    click.echo("=" * 65)
    click.echo(f"Cache Location      : {cache.cache_dir}")
    click.echo(f"Cached Entries      : {stats['cached_entries']:,}")
    click.echo(f"Cache Hits          : {hits:,}")
    click.echo(f"Cache Misses        : {misses:,}")
    click.echo(f"Cache Hit Rate      : {hit_rate:.1f}%")
    click.echo(f"Tokens Saved        : {stats['tokens_saved']:,}")
    click.echo(f"Est. Cost Saved     : ${stats['estimated_cost_usd_saved']:.4f} USD")
    click.echo("=" * 65)


@main.command("cache-clear")
def cache_clear_command() -> None:
    """Clear the persistent LLM response cache and reset token savings stats."""
    from youth_escalate_bench.cache import get_default_llm_cache

    cache = get_default_llm_cache()
    deleted = cache.clear()
    click.echo(f"✓ Cleared {deleted} cached prediction entries and reset token stats.")


if __name__ == "__main__":
    main()
