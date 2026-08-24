"""End-to-end pipeline tests on fixture data."""

from pathlib import Path

import pytest

from youth_escalate_bench.pipeline import get_runner, run_stage


@pytest.fixture
def e2e_output(tmp_path: Path) -> Path:
    return tmp_path / "e2e"


def _run_chain(output_dir: Path) -> None:
    # Use lightweight test config for fast deterministic e2e verification
    fixture_ingest_cfg = output_dir / "ingest_fixture.yaml"
    output_dir.mkdir(parents=True, exist_ok=True)
    import yaml
    with fixture_ingest_cfg.open("w", encoding="utf-8") as f:
        yaml.safe_dump({
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
        }, f)

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
    stages = [
        "source_audit",
        "ingest",
        "redact",
        "thread",
        "transform",
        "annotate_export",
        "split",
        "evaluate",
    ]
    processed = output_dir / "processed"

    def input_for(stage: str) -> Path:
        if stage in ("source_audit", "ingest"):
            return Path("data/raw")
        if stage in ("annotate_export", "split"):
            return processed / "thread"
        if stage == "evaluate":
            return processed / "split"
        prev = stages[stages.index(stage) - 1]
        return processed / prev

    for stage in stages:
        runner = get_runner(stage)
        run_stage(stage, configs[stage], input_for(stage), processed / stage, runner)



def test_e2e_pipeline(e2e_output: Path) -> None:
    _run_chain(e2e_output)
    processed = e2e_output / "processed"
    assert (processed / "ingest" / "conversations.parquet").exists()
    assert (processed / "redact" / "conversations_redacted.parquet").exists()
    assert (processed / "thread" / "conversations_threaded.parquet").exists()
    assert (processed / "transform" / "transform_pairs.parquet").exists()
    assert (processed / "split" / "split_train.parquet").exists()
    assert (processed / "annotate_export" / "annotation_packets.jsonl").exists()
    assert (processed / "evaluate" / "evaluation_results.yaml").exists()
    assert (processed / "evaluate" / "onset_metrics.yaml").exists()


def test_redact_removes_email(e2e_output: Path) -> None:
    _run_chain(e2e_output)
    from youth_escalate_bench.io.parquet import read_conversations

    redacted = read_conversations(
        e2e_output / "processed" / "redact" / "conversations_redacted.parquet"
    )
    all_text = " ".join(t.text for c in redacted for t in c.turns)
    assert "test@example.com" not in all_text
    assert "[REDACTED]" in all_text


def test_full_12_stage_pipeline(e2e_output: Path) -> None:
    """Validate all 12 pipeline stages run and produce verified outputs."""
    processed = e2e_output / "processed_all"
    fixture_ingest_cfg = e2e_output / "ingest_fixture_12.yaml"
    e2e_output.mkdir(parents=True, exist_ok=True)
    import yaml
    with fixture_ingest_cfg.open("w", encoding="utf-8") as f:
        yaml.safe_dump({
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
        }, f)

    configs = {
        "source_audit": Path("configs/stages/source_audit.yaml"),
        "ingest": fixture_ingest_cfg,
        "redact": Path("configs/stages/redact.yaml"),
        "thread": Path("configs/stages/thread.yaml"),
        "stage_generate": Path("configs/stages/stage_generate.yaml"),
        "sample": Path("configs/stages/sample.yaml"),
        "transform": Path("configs/stages/transform.yaml"),
        "annotate_export": Path("configs/stages/annotate_export.yaml"),
        "adjudicate": Path("configs/stages/adjudicate.yaml"),
        "split": Path("configs/stages/split.yaml"),
        "evaluate": Path("configs/stages/evaluate.yaml"),
        "report": Path("configs/stages/report.yaml"),
    }

    all_12 = [
        "source_audit",
        "ingest",
        "redact",
        "thread",
        "stage_generate",
        "sample",
        "transform",
        "annotate_export",
        "adjudicate",
        "split",
        "evaluate",
        "report",
    ]

    for stage in all_12:
        runner = get_runner(stage)
        if stage in ("source_audit", "ingest"):
            in_dir = Path("data/raw")
        elif stage == "redact":
            in_dir = processed / "ingest"
        elif stage in ("thread", "sample", "transform", "annotate_export", "split"):
            in_dir = (
                processed / "thread" if (processed / "thread").exists() else processed / "redact"
            )
        elif stage == "adjudicate":
            in_dir = processed / "stage_generate"
        elif stage == "evaluate":
            in_dir = processed / "split"
        elif stage == "report":
            in_dir = processed / "evaluate"
        else:
            in_dir = processed

        manifest = run_stage(stage, configs[stage], in_dir, processed / stage, runner)
        assert manifest.stage == stage
        assert (processed / stage / "manifest.json").exists()

    assert (processed / "report" / "evaluation_report.md").exists()
    assert (processed / "report" / "report_summary.yaml").exists()
    assert (processed / "report" / "table_main_results.tex").exists()
    assert (processed / "adjudicate" / "gold_labels.jsonl").exists()
