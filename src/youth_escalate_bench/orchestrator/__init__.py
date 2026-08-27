"""YouthEscalateBench Pipeline Orchestrator & Checkpoint State Management."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from youth_escalate_bench.pipeline import get_runner, run_stage

# Pipeline Stage Execution Sequence
ORDERED_STEPS: list[dict[str, Any]] = [
    {
        "id": "source_audit",
        "title": "Source Audit & Governance Gate",
        "config": "configs/stages/source_audit.yaml",
        "input_from": None,
        "input_fallback": "data/raw",
    },
    {
        "id": "ingest",
        "title": "Raw Corpus Ingestion to Parquet",
        "config": "configs/stages/ingest.yaml",
        "input_from": None,
        "input_fallback": "data/raw",
    },
    {
        "id": "redact",
        "title": "PII Detection & Redaction",
        "config": "configs/stages/redact.yaml",
        "input_from": "ingest",
        "input_fallback": "data/processed/ingest",
    },
    {
        "id": "thread",
        "title": "Thread Topology & Causal Validation",
        "config": "configs/stages/thread.yaml",
        "input_from": "redact",
        "input_fallback": "data/processed/redact",
    },
    {
        "id": "stage_generate",
        "title": "Synthetic Scenarios & Minimal Pairs",
        "config": "configs/stages/stage_generate.yaml",
        "input_from": None,
        "input_fallback": "configs",
    },
    {
        "id": "transform",
        "title": "Algospeak Obfuscation Suite",
        "config": "configs/stages/transform.yaml",
        "input_from": "thread",
        "input_fallback": "data/processed/thread",
    },
    {
        "id": "sample",
        "title": "Deduplication & Quota Sampling",
        "config": "configs/stages/sample.yaml",
        "input_from": "thread",
        "input_fallback": "data/processed/thread",
    },
    {
        "id": "annotate_export",
        "title": "Annotation Packet Export / LLM Judge",
        "config": "configs/stages/annotate_export.yaml",
        "input_from": "sample",
        "input_fallback": "data/processed/thread",
    },
    {
        "id": "adjudicate",
        "title": "Consensus Adjudication & Gold Freeze",
        "config": "configs/stages/adjudicate.yaml",
        "input_from": "stage_generate",
        "input_fallback": "data/processed/stage_generate",
    },
    {
        "id": "split",
        "title": "Train/Dev/Test Split with Zero Leakage",
        "config": "configs/stages/split.yaml",
        "input_from": "sample",
        "input_fallback": "data/processed/thread",
    },
    {
        "id": "evaluate",
        "title": "Moderation Baseline & Causal Evaluation",
        "config": "configs/stages/evaluate.yaml",
        "input_from": "split",
        "input_fallback": "data/processed/split",
    },
    {
        "id": "report",
        "title": "Paper LaTeX Tables & Markdown Reports",
        "config": "configs/stages/report.yaml",
        "input_from": "evaluate",
        "input_fallback": "data/processed/evaluate",
    },
]

STEP_NAMES = [s["id"] for s in ORDERED_STEPS]

EVAL_MODES: dict[str, dict[str, int]] = {
    "extra-small": {"max_samples": 20, "plans_per_template": 2},
    "small": {"max_samples": 100, "plans_per_template": 15},
    "medium": {"max_samples": 250, "plans_per_template": 35},
    "large": {"max_samples": 500, "plans_per_template": 70},
    "extra-large": {"max_samples": 1000, "plans_per_template": 140},
}


@dataclass
class StepCheckpoint:
    step_id: str
    title: str
    status: str = "PENDING"  # PENDING, RUNNING, SUCCESS, FAILED, SKIPPED
    started_at: str | None = None
    finished_at: str | None = None
    duration_sec: float | None = None
    output_files: list[str] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)
    error_message: str | None = None
    log_file: str | None = None


class CheckpointManager:
    """Manages persistent JSON checkpoint states for pipeline runs."""

    def __init__(self, checkpoint_path: Path) -> None:
        self.path = checkpoint_path
        self.checkpoints: dict[str, StepCheckpoint] = {}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                for step_id, info in data.get("steps", {}).items():
                    self.checkpoints[step_id] = StepCheckpoint(**info)
            except Exception:
                self._init_defaults()
        else:
            self._init_defaults()

    def _init_defaults(self) -> None:
        self.checkpoints = {
            s["id"]: StepCheckpoint(step_id=s["id"], title=s["title"]) for s in ORDERED_STEPS
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now(UTC).isoformat(),
            "steps": {k: asdict(v) for k, v in self.checkpoints.items()},
        }
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def mark_running(self, step_id: str) -> None:
        if step_id not in self.checkpoints:
            self.checkpoints[step_id] = StepCheckpoint(step_id=step_id, title=step_id)
        cp = self.checkpoints[step_id]
        cp.status = "RUNNING"
        cp.started_at = datetime.now(UTC).isoformat()
        cp.error_message = None
        cp.log_file = None
        self.save()

    def mark_success(
        self,
        step_id: str,
        duration: float,
        output_files: list[str],
        row_counts: dict[str, int],
    ) -> None:
        cp = self.checkpoints[step_id]
        cp.status = "SUCCESS"
        cp.finished_at = datetime.now(UTC).isoformat()
        cp.duration_sec = round(duration, 3)
        cp.output_files = output_files
        cp.row_counts = row_counts
        cp.error_message = None
        self.save()

    def mark_failed(
        self,
        step_id: str,
        duration: float,
        error_msg: str,
        log_file: str | None = None,
    ) -> None:
        cp = self.checkpoints[step_id]
        cp.status = "FAILED"
        cp.finished_at = datetime.now(UTC).isoformat()
        cp.duration_sec = round(duration, 3)
        cp.error_message = error_msg
        cp.log_file = log_file
        self.save()

    def mark_skipped(self, step_id: str) -> None:
        cp = self.checkpoints[step_id]
        cp.status = "SKIPPED"
        self.save()

    def is_success(self, step_id: str) -> bool:
        return self.checkpoints.get(step_id, StepCheckpoint(step_id, step_id)).status == "SUCCESS"

    def reset_all(self) -> None:
        self._init_defaults()
        self.save()

    def reset_step(self, step_id: str) -> None:
        if step_id in self.checkpoints:
            self.checkpoints[step_id] = StepCheckpoint(
                step_id=step_id,
                title=self.checkpoints[step_id].title,
            )
            self.save()

    def display_status(self) -> None:
        print("\n" + "=" * 80)
        print("YouthEscalateBench — Pipeline Checkpoint Status")
        print("=" * 80)
        print(
            f"{'#':<3} {'Step ID':<18} {'Status':<12} {'Duration':<10} {'Output Files / Summary'}"
        )
        print("-" * 80)

        status_icons = {
            "SUCCESS": "🟢 SUCCESS",
            "FAILED": "🔴 FAILED",
            "RUNNING": "🟡 RUNNING",
            "SKIPPED": "⚪ SKIPPED",
            "PENDING": "⚪ PENDING",
        }

        for idx, s in enumerate(ORDERED_STEPS, 1):
            cp = self.checkpoints.get(s["id"], StepCheckpoint(s["id"], s["title"]))
            status_str = status_icons.get(cp.status, cp.status)
            dur_str = f"{cp.duration_sec:.2f}s" if cp.duration_sec is not None else "-"

            if cp.status == "SUCCESS":
                summary = f"{len(cp.output_files)} files ({', '.join(cp.output_files[:2])})"
            elif cp.status == "FAILED":
                summary = f"Error: {(cp.error_message or '')[:35]}..."
            else:
                summary = s["title"]

            print(f"{idx:<3} {s['id']:<18} {status_str:<12} {dur_str:<10} {summary}")
        print("=" * 80 + "\n")


class PipelineRunner:
    """Executes the YouthEscalateBench pipeline with automated checkpoint recovery."""

    def __init__(
        self,
        base_dir: Path | None = None,
        checkpoint_dir: Path | None = None,
        processed_dir: Path | None = None,
    ) -> None:
        self.base_dir = base_dir or Path.cwd()
        self.processed_dir = processed_dir or (self.base_dir / "data" / "processed")
        self.checkpoint_dir = checkpoint_dir or (self.base_dir / "data" / "checkpoints")
        self.logs_dir = self.base_dir / "reports" / "pipeline_errors"
        self.checkpoint_mgr = CheckpointManager(self.checkpoint_dir / "pipeline_checkpoint.json")

    def resolve_input_dir(self, step_info: dict[str, Any]) -> Path:
        """Resolve the input directory for a given pipeline step with fallback checking."""
        input_from = step_info.get("input_from")
        fallback = self.base_dir / step_info.get("input_fallback", "data/raw")

        if input_from:
            primary = self.processed_dir / input_from
            if primary.exists() and any(primary.iterdir()):
                return primary

        if fallback.exists() and any(fallback.iterdir()):
            return fallback

        if input_from:
            return self.processed_dir / input_from
        return fallback

    def _rel_or_abs(self, p: Path) -> Path | str:
        try:
            return p.relative_to(self.base_dir)
        except ValueError:
            return p

    def execute_step(
        self,
        step_info: dict[str, Any],
        force: bool = False,
        config_overrides: dict[str, Any] | None = None,
    ) -> bool:
        """Run a single pipeline step with timing, manifests, and error logging."""
        step_id = step_info["id"]
        title = step_info["title"]
        config_path = self.base_dir / step_info["config"]

        if not config_path.exists():
            print(f"❌ Missing config file for {step_id}: {config_path}")
            return False

        if not force and self.checkpoint_mgr.is_success(step_id):
            print(f"⏭️  [Step: {step_id}] Already completed successfully. (Use --force to re-run)")
            return True

        input_dir = self.resolve_input_dir(step_info)
        output_dir = self.processed_dir / step_id

        print(f"\n▶️  [Running: {step_id}] {title}")
        print(f"    Config : {self._rel_or_abs(config_path)}")
        print(f"    Input  : {self._rel_or_abs(input_dir)}")
        print(f"    Output : {self._rel_or_abs(output_dir)}")

        self.checkpoint_mgr.mark_running(step_id)
        start_time = time.perf_counter()

        try:
            runner = get_runner(step_id)
            manifest = run_stage(
                step_id,
                config_path,
                input_dir,
                output_dir,
                runner,
                config_overrides=config_overrides,
            )
            duration = time.perf_counter() - start_time

            output_filenames = [Path(e.path).name for e in manifest.outputs]
            row_counts = {Path(e.path).name: (e.row_count or 0) for e in manifest.outputs}

            self.checkpoint_mgr.mark_success(
                step_id=step_id,
                duration=duration,
                output_files=output_filenames,
                row_counts=row_counts,
            )

            # Mirror stage data reports and manifests to reports/data/
            reports_data_dir = Path("reports/data")
            reports_data_dir.mkdir(parents=True, exist_ok=True)
            for entry in manifest.outputs:
                src_path = Path(entry.path)
                if src_path.name.endswith(
                    ("_report.yaml", "_manifest.yaml", "manifest.json", "_ranking.yaml")
                ):
                    dest_file = reports_data_dir / (
                        f"{step_id}_{src_path.name}"
                        if src_path.name == "manifest.json"
                        else src_path.name
                    )
                    try:
                        shutil.copy2(src_path, dest_file)
                    except Exception:
                        pass

            print(f"  ✓ {step_id} completed in {duration:.2f}s ({len(manifest.outputs)} outputs)")
            return True

        except Exception as e:
            duration = time.perf_counter() - start_time
            error_msg = str(e)

            # Dump detailed error traceback
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            log_path = self.logs_dir / f"{step_id}_error.log"
            with log_path.open("w", encoding="utf-8") as f:
                f.write(f"Pipeline Step Failure: {step_id}\n")
                f.write(f"Timestamp: {datetime.now(UTC).isoformat()}\n")
                f.write(f"Config: {config_path}\n")
                f.write(f"Input Dir: {input_dir}\n")
                f.write(f"Output Dir: {output_dir}\n")
                f.write("-" * 60 + "\n")
                f.write(f"Error: {error_msg}\n")
                f.write("-" * 60 + "\n")
                traceback.print_exc(file=f)

            self.checkpoint_mgr.mark_failed(
                step_id=step_id,
                duration=duration,
                error_msg=error_msg,
                log_file=str(log_path),
            )

            print("\n" + "!" * 80)
            print(f"❌ [FAILED: {step_id}] {error_msg}")
            print(f"   Detailed error log saved to: {log_path}")
            print("   To debug this step individually, run:")
            print(f"     python scripts/run_pipeline.py --step {step_id} --force")
            print(
                f"     python -m youth_escalate_bench.cli run --stage {step_id} --config {config_path}"
            )
            print("!" * 80 + "\n")
            return False

    def run(
        self,
        target_steps: list[str] | None = None,
        from_step: str | None = None,
        to_step: str | None = None,
        resume: bool = False,
        force: bool = False,
        dry_run: bool = False,
        extended_report: bool = False,
        mode: str = "extra-small",
        max_samples: int | None = None,
        seed: int | None = None,
        sample_strategy: str = "auto",
        enable_rag: bool = False,
        rag_compare: bool = False,
        difficulty_level: str = "standard",
    ) -> bool:
        """Execute selected range of pipeline steps with controllable seed and sampling strategy."""
        all_ids = [s["id"] for s in ORDERED_STEPS]

        mode_config = EVAL_MODES.get(mode, EVAL_MODES["extra-small"])
        active_max_samples = max_samples if max_samples is not None else mode_config["max_samples"]
        active_plans = mode_config["plans_per_template"]

        if target_steps:
            steps_to_run = [s for s in ORDERED_STEPS if s["id"] in target_steps]
        else:
            start_idx = 0
            end_idx = len(ORDERED_STEPS)

            if resume:
                # Find earliest non-successful step
                for idx, s in enumerate(ORDERED_STEPS):
                    if not self.checkpoint_mgr.is_success(s["id"]):
                        start_idx = idx
                        break

            if from_step:
                if from_step not in all_ids:
                    raise ValueError(f"Invalid --from-step '{from_step}'. Choose from {all_ids}")
                start_idx = all_ids.index(from_step)

            if to_step:
                if to_step not in all_ids:
                    raise ValueError(f"Invalid --to-step '{to_step}'. Choose from {all_ids}")
                end_idx = all_ids.index(to_step) + 1

            steps_to_run = ORDERED_STEPS[start_idx:end_idx]

        seed_info = f", Seed: {seed}" if seed is not None else ""
        strat_info = f", Strategy: {sample_strategy}" if sample_strategy != "auto" else ""
        rag_info = (
            ", RAG: ON"
            if enable_rag and not rag_compare
            else (", RAG Compare: ON" if rag_compare else "")
        )

        if dry_run:
            print(
                f"\n[DRY RUN] Planned Execution Sequence (Mode: {mode}, Max Samples: {active_max_samples}{seed_info}{strat_info}{rag_info}):"
            )
            for idx, s in enumerate(steps_to_run, 1):
                input_dir = self.resolve_input_dir(s)
                status = self.checkpoint_mgr.checkpoints.get(
                    s["id"], StepCheckpoint(s["id"], s["title"])
                ).status
                print(
                    f"  {idx}. {s['id']:<18} | Status: {status:<10} | Input: {input_dir} -> Output: data/processed/{s['id']}"
                )
            print()
            return True

        print("=" * 80)
        print(
            f"YouthEscalateBench — Starting Pipeline ({len(steps_to_run)} steps queued, Mode: {mode}, Max Samples: {active_max_samples}{seed_info}{strat_info}{rag_info})"
        )
        print("=" * 80)

        overall_start = time.perf_counter()
        for s in steps_to_run:
            overrides: dict[str, Any] = {}
            if seed is not None:
                overrides["random_seed"] = seed
            if s["id"] == "stage_generate":
                overrides["plans_per_template"] = active_plans
                if difficulty_level:
                    overrides["difficulty_level"] = difficulty_level
            elif s["id"] == "evaluate":
                overrides["max_samples"] = active_max_samples
                if difficulty_level:
                    overrides["difficulty_level"] = difficulty_level
                if sample_strategy != "auto":
                    overrides["sample_strategy"] = sample_strategy
                if enable_rag:
                    overrides["enable_rag"] = True
                if rag_compare:
                    overrides["rag_compare"] = True
            elif s["id"] == "report" and extended_report:
                overrides["extended_report"] = True

            success = self.execute_step(
                s,
                force=force,
                config_overrides=overrides if overrides else None,
            )
            if not success:
                print(
                    f"\n⛔ Pipeline halted at step '{s['id']}'. Fix error or re-run with --force."
                )
                self.checkpoint_mgr.display_status()
                return False

        overall_dur = time.perf_counter() - overall_start
        print("\n" + "=" * 80)
        print(f"🎉 Pipeline Execution Finished Successfully in {overall_dur:.2f}s!")
        print("=" * 80)
        self.checkpoint_mgr.display_status()
        return True


def run_pipeline_cli() -> None:
    parser = argparse.ArgumentParser(
        description="YouthEscalateBench Main Pipeline Orchestrator with Checkpoints & State Recovery.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run entire pipeline with default extra-small scale (20 test samples):
  python main.py --all

  # Run pipeline with small scale (100 test samples):
  python main.py --all --mode small

  # Run pipeline with medium scale (250 test samples):
  python main.py --all --mode medium

  # Run pipeline with large scale (500 test samples):
  python main.py --all --mode large

  # Run pipeline with extra-large scale (1000 test samples):
  python main.py --all --mode extra-large

  # Auto-resume from earliest incomplete/failed checkpoint:
  python main.py --resume

  # Run only evaluation and report with small mode:
  python main.py --step evaluate report --mode small --force

  # Display current checkpoint status table:
  python main.py --status
        """,
    )

    parser.add_argument("--all", "-a", action="store_true", help="Run all pipeline stages.")
    parser.add_argument(
        "--resume",
        "-r",
        action="store_true",
        help="Auto-resume from earliest incomplete checkpoint.",
    )
    parser.add_argument(
        "--step", "-s", nargs="+", choices=STEP_NAMES, help="Run specific pipeline step(s)."
    )
    parser.add_argument("--from-step", choices=STEP_NAMES, help="Start execution from this step.")
    parser.add_argument("--to-step", choices=STEP_NAMES, help="Stop execution after this step.")
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force re-execution of already completed steps."
    )
    parser.add_argument(
        "--extended-report",
        "-e",
        "--extended",
        dest="extended_report",
        action="store_true",
        help="Generate detailed extended report outputting all failure cases per LLM.",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=list(EVAL_MODES.keys()),
        default="extra-small",
        help="Evaluation scale mode: extra-small=20 (default), small=100, medium=250, large=500, extra-large=1000.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Explicitly override maximum evaluation samples across conditions (overrides --mode default).",
    )
    parser.add_argument(
        "--seed",
        "--random-seed",
        type=int,
        default=None,
        dest="seed",
        help="Controllable random seed for reproducible example selection, sampling, and evaluation splits.",
    )
    parser.add_argument(
        "--sample-strategy",
        "--strategy",
        choices=["auto", "difficulty", "random", "stratified"],
        default="auto",
        dest="sample_strategy",
        help="Example selection strategy: 'auto' (difficulty prioritized if available), 'difficulty' (hard samples), 'random' (pure seeded random selection), 'stratified' (balanced harm labels).",
    )
    parser.add_argument(
        "--difficulty-level",
        "--difficulty",
        choices=["standard", "hard", "extreme", "adversarial"],
        default="standard",
        dest="difficulty_level",
        help="Benchmark difficulty tier: 'standard' (balanced baseline), 'hard' (high-FP hype & covert exclusion), 'extreme' (heavy algospeak obfuscation), 'adversarial' (causal context flips).",
    )
    parser.add_argument(
        "--rag",
        action="store_true",
        help="Enable dynamic slang and pragmatics RAG retrieval for LLM moderation.",
    )
    parser.add_argument(
        "--rag-compare",
        action="store_true",
        help="Benchmark standard LLM moderation against RAG-augmented LLMs side-by-side.",
    )
    parser.add_argument(
        "--status", action="store_true", help="Show current pipeline checkpoint status table."
    )
    parser.add_argument(
        "--reset", action="store_true", help="Reset all checkpoint states to PENDING."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate execution without running stages."
    )

    args = parser.parse_args()
    runner = PipelineRunner()

    if args.status:
        runner.checkpoint_mgr.display_status()
        return

    if args.reset:
        runner.checkpoint_mgr.reset_all()
        print("✓ All pipeline checkpoints reset to PENDING.")
        runner.checkpoint_mgr.display_status()
        return

    if (
        not args.all
        and not args.resume
        and not args.step
        and not args.from_step
        and not args.dry_run
    ):
        runner.checkpoint_mgr.display_status()
        parser.print_help()
        return

    success = runner.run(
        target_steps=args.step,
        from_step=args.from_step,
        to_step=args.to_step,
        resume=args.resume or (not args.force and not args.step),
        force=args.force,
        dry_run=args.dry_run,
        extended_report=args.extended_report,
        mode=args.mode,
        max_samples=args.max_samples,
        seed=args.seed,
        sample_strategy=args.sample_strategy,
        enable_rag=args.rag,
        rag_compare=args.rag_compare,
        difficulty_level=args.difficulty_level,
    )

    sys.exit(0 if success else 1)
