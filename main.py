"""YouthEscalateBench Main Pipeline Orchestrator Entrypoint.

Usage:
  python main.py --all
  python main.py --resume
  python main.py --status
  python main.py --step <step_name> --force
  python main.py --from-step <step_name> --to-step <step_name>
"""

from youth_escalate_bench.orchestrator import run_pipeline_cli

if __name__ == "__main__":
    run_pipeline_cli()
