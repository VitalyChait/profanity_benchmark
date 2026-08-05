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
