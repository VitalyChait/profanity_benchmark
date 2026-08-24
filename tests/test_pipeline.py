"""Tests for pipeline stage stubs."""

from pathlib import Path

from youth_escalate_bench.pipeline import get_runner, run_stage


def test_source_audit_stage_runs(tmp_path: Path):
    config = Path("configs/stages/source_audit.yaml")
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    runner = get_runner("source_audit")
    manifest = run_stage("source_audit", config, input_dir, output_dir, runner)
    assert manifest.stage == "source_audit"
    assert len(manifest.outputs) == 2
    assert (output_dir / "manifest.json").exists()


def test_stage_generate_runs(tmp_path: Path):
    config = Path("configs/stages/stage_generate.yaml")
    output_dir = tmp_path / "stage_generate"
    runner = get_runner("stage_generate")
    manifest = run_stage("stage_generate", config, tmp_path, output_dir, runner)
    assert manifest.stage == "stage_generate"
    assert (output_dir / "scenario_plans.jsonl").exists()
    assert (output_dir / "generated_conversations.parquet").exists()
    assert (output_dir / "generated_annotations.jsonl").exists()
    assert (output_dir / "manifest.json").exists()


def test_sample_stage_runs(tmp_path: Path):
    # Prepare generated conversations as input
    stage_gen_dir = tmp_path / "stage_generate"
    runner_gen = get_runner("stage_generate")
    run_stage(
        "stage_generate",
        Path("configs/stages/stage_generate.yaml"),
        tmp_path,
        stage_gen_dir,
        runner_gen,
    )

    sample_out = tmp_path / "sample"
    runner_sample = get_runner("sample")
    manifest = run_stage(
        "sample", Path("configs/stages/sample.yaml"), stage_gen_dir, sample_out, runner_sample
    )
    assert manifest.stage == "sample"
    assert (sample_out / "conversations_sampled.parquet").exists()
    assert (sample_out / "quota_report.yaml").exists()


def test_report_stage_runs(tmp_path: Path):
    # Create mock evaluation results in input_dir
    eval_dir = tmp_path / "evaluate"
    eval_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    mock_eval = {
        "benchmark_version": "0.1.0",
        "random_seed": 42,
        "results": [
            {
                "scorer": "rule_based_lexicon",
                "condition": "current_turn_only",
                "metrics": {"auprc": 0.85, "auroc": 0.90, "f1": 0.80, "support": 50},
                "per_harm_auprc": {"targeted_insult": 0.82},
            }
        ],
    }
    with (eval_dir / "evaluation_results.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(mock_eval, f)

    report_out = tmp_path / "report"
    runner = get_runner("report")
    manifest = run_stage("report", Path("configs/stages/report.yaml"), eval_dir, report_out, runner)
    assert manifest.stage == "report"
    assert (report_out / "evaluation_report.md").exists()
    assert (report_out / "report_summary.yaml").exists()
    assert (report_out / "table_main_results.tex").exists()
