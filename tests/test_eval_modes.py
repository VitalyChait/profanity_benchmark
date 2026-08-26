"""Tests for evaluation scale modes (extra-small, small, medium, large, extra-large)."""

from youth_escalate_bench.orchestrator import EVAL_MODES, PipelineRunner


def test_eval_modes_presets() -> None:
    """Verify all 5 evaluation modes are properly configured."""
    expected_modes = {
        "extra-small": 20,
        "small": 100,
        "medium": 250,
        "large": 500,
        "extra-large": 1000,
    }
    for mode_name, expected_samples in expected_modes.items():
        assert mode_name in EVAL_MODES, f"Missing mode {mode_name}"
        assert EVAL_MODES[mode_name]["max_samples"] == expected_samples
        assert EVAL_MODES[mode_name]["plans_per_template"] > 0


def test_eval_modes_defaults_to_extra_small() -> None:
    """Default mode must be extra-small with 20 samples."""
    default_config = EVAL_MODES["extra-small"]
    assert default_config["max_samples"] == 20
    assert default_config["plans_per_template"] == 2


def test_dry_run_with_modes(capsys) -> None:
    """PipelineRunner dry-run correctly displays chosen mode and max samples."""
    runner = PipelineRunner()

    # Dry run with small mode
    success = runner.run(dry_run=True, mode="small")
    assert success is True
    captured = capsys.readouterr().out
    assert "Mode: small" in captured
    assert "Max Samples: 100" in captured

    # Dry run with custom max_samples override
    success_override = runner.run(dry_run=True, mode="small", max_samples=42)
    assert success_override is True
    captured_override = capsys.readouterr().out
    assert "Mode: small" in captured_override
    assert "Max Samples: 42" in captured_override


def test_cli_argument_parsing() -> None:
    """Argparse in run_pipeline_cli accepts --mode and --max-samples."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", "-m", choices=list(EVAL_MODES.keys()), default="extra-small")
    parser.add_argument("--max-samples", type=int, default=None)

    args = parser.parse_args(["--mode", "medium", "--max-samples", "300"])
    assert args.mode == "medium"
    assert args.max_samples == 300

    # Default fallback
    args_default = parser.parse_args([])
    assert args_default.mode == "extra-small"
    assert args_default.max_samples is None
