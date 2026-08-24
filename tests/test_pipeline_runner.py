"""Unit tests for pipeline checkpoint manager and runner."""

from pathlib import Path

from youth_escalate_bench.orchestrator import CheckpointManager, PipelineRunner


def test_checkpoint_manager_initialization(tmp_path: Path):
    cp_file = tmp_path / "checkpoint.json"
    mgr = CheckpointManager(cp_file)

    assert not cp_file.exists()  # Not created until saved
    mgr.save()
    assert cp_file.exists()

    # Re-load
    mgr2 = CheckpointManager(cp_file)
    assert len(mgr2.checkpoints) > 0
    assert not mgr2.is_success("source_audit")


def test_checkpoint_lifecycle(tmp_path: Path):
    cp_file = tmp_path / "checkpoint.json"
    mgr = CheckpointManager(cp_file)

    step = "source_audit"
    mgr.mark_running(step)
    assert mgr.checkpoints[step].status == "RUNNING"
    assert mgr.checkpoints[step].started_at is not None

    mgr.mark_success(step, duration=1.23, output_files=["report.yaml"], row_counts={"report.yaml": 10})
    assert mgr.is_success(step)
    assert mgr.checkpoints[step].duration_sec == 1.23
    assert mgr.checkpoints[step].output_files == ["report.yaml"]

    mgr.mark_failed(step, duration=0.5, error_msg="Test error")
    assert not mgr.is_success(step)
    assert mgr.checkpoints[step].status == "FAILED"
    assert mgr.checkpoints[step].error_message == "Test error"

    mgr.reset_all()
    assert mgr.checkpoints[step].status == "PENDING"


def test_pipeline_runner_dry_run(tmp_path: Path):
    runner = PipelineRunner(
        base_dir=Path.cwd(),
        checkpoint_dir=tmp_path / "checkpoints",
        processed_dir=tmp_path / "processed",
    )
    # Dry run should return True without executing real work
    success = runner.run(dry_run=True)
    assert success


def test_pipeline_runner_single_step(tmp_path: Path):
    runner = PipelineRunner(
        base_dir=Path.cwd(),
        checkpoint_dir=tmp_path / "checkpoints",
        processed_dir=tmp_path / "processed",
    )
    # Run source_audit step
    success = runner.run(target_steps=["source_audit"], force=True)
    assert success
    assert runner.checkpoint_mgr.is_success("source_audit")
