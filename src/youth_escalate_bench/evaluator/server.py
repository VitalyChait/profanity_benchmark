"""Private benchmark evaluator HTTP server and interactive analysis dashboard."""

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from youth_escalate_bench.baselines.scorers import ModerationScorer, build_default_scorers
from youth_escalate_bench.evaluator.dashboard import (
    build_evaluated_models_catalog,
    generate_predict_page_html,
    generate_service_dashboard_html,
)
from youth_escalate_bench.schemas.inference import InferenceRequest, ModelOutput


class PredictHandler(BaseHTTPRequestHandler):
    scorer: ModerationScorer | None = None
    lexicon_path: Path = Path("configs/profanity_lexicon.txt")
    reports_dir: Path = Path("reports")
    server_host: str = "127.0.0.1"
    server_port: int = 8080

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Health check
        if path == "/health":
            self._send_json(200, {"status": "healthy", "service": "YouthEscalateBench Evaluator"})
            return

        # 2. Dedicated /predict interactive sandbox & API descriptor
        if path == "/predict":
            accept = self.headers.get("Accept", "")
            # Return interactive HTML page for browsers (which ask for text/html)
            if "text/html" in accept or ("*/*" in accept and "application/json" not in accept):
                html_content = generate_predict_page_html(
                    host=self.server_host,
                    port=self.server_port,
                )
                self._send_bytes(200, html_content.encode("utf-8"), "text/html; charset=utf-8")
                return

            # Programmatic API descriptor for JSON clients
            desc = {
                "endpoint": "/predict",
                "method_supported": "POST",
                "status": "ready",
                "description": "YouthEscalateBench Moderation Inference API Endpoint",
                "instructions": (
                    "To run inference, submit an HTTP POST request with a JSON body conforming "
                    "to the InferenceRequest schema. For an interactive testing console in your "
                    f"browser, visit http://{self.server_host}:{self.server_port}/predict or "
                    f"http://{self.server_host}:{self.server_port}/"
                ),
                "interactive_sandbox_url": f"http://{self.server_host}:{self.server_port}/predict",
                "dashboard_url": f"http://{self.server_host}:{self.server_port}/",
                "sample_curl": (
                    f"curl -X POST http://{self.server_host}:{self.server_port}/predict "
                    "-H 'Content-Type: application/json' "
                    '-d \'{"turns": [{"speaker_id": "u1", "turn_id": "t1", "text": "you suck uninstall"}]}\''
                ),
                "sample_payload": {
                    "benchmark_version": "0.1.2",
                    "conversation_id": "demo_01",
                    "current_turn_id": "t1",
                    "platform_style": "gaming_chat",
                    "language_mode": "english",
                    "task": "current_harm",
                    "turns": [
                        {
                            "speaker_id": "u1",
                            "turn_id": "t1",
                            "text": "you are absolute garbage uninstall right now",
                        }
                    ],
                },
            }
            self._send_json(200, desc)
            return

        # 3. Main interactive analysis dashboard view
        if path in ("/", "/dashboard", "/index.html"):
            html_content = generate_service_dashboard_html(
                reports_dir=self.reports_dir,
                host=self.server_host,
                port=self.server_port,
            )
            self._send_bytes(200, html_content.encode("utf-8"), "text/html; charset=utf-8")
            return

        # 4. REST API endpoints for analysis
        if path == "/api/summary":
            summary_file = self.reports_dir / "report_summary.yaml"
            if not summary_file.exists():
                summary_file = Path("data/processed/report/report_summary.yaml")
            data = {}
            if summary_file.exists():
                try:
                    with summary_file.open("r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                except Exception:
                    data = {}
            self._send_json(200, data)
            return

        if path == "/api/errors":
            errors_file = self.reports_dir / "llm_error_cases.json"
            if not errors_file.exists():
                errors_file = Path("data/processed/report/llm_error_cases.json")
            data = {}
            if errors_file.exists():
                try:
                    with errors_file.open("r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                except Exception:
                    data = {}
            self._send_json(200, data)
            return

        if path == "/api/difficulty":
            diff_file = self.reports_dir / "difficulty_ranking.yaml"
            if not diff_file.exists():
                diff_file = Path("data/processed/report/difficulty_ranking.yaml")
            data = {}
            if diff_file.exists():
                try:
                    with diff_file.open("r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                except Exception:
                    data = {}
            self._send_json(200, data)
            return

        if path == "/api/models":
            models_catalog = build_evaluated_models_catalog(self.reports_dir)
            self._send_json(200, models_catalog)
            return

        # 4. Static reports, figures, heatmaps, and summaries
        filename = path.lstrip("/")
        if filename.startswith("reports/"):
            filename = filename[len("reports/") :]
        elif filename.startswith("data/processed/report/"):
            filename = filename[len("data/processed/report/") :]

        candidate_dirs = [
            self.reports_dir,
            Path("data/processed/report"),
            Path("reports"),
            Path("reports/snapshots/snapshot_2026.Q1"),
        ]

        for c_dir in candidate_dirs:
            target = c_dir / filename
            if target.is_file():
                mime_type, _ = mimetypes.guess_type(target.name)
                if not mime_type:
                    if target.suffix in (".md", ".txt", ".yaml", ".yml", ".tex"):
                        mime_type = "text/plain; charset=utf-8"
                    elif target.suffix == ".json":
                        mime_type = "application/json"
                    elif target.suffix == ".png":
                        mime_type = "image/png"
                    elif target.suffix in (".html", ".htm"):
                        mime_type = "text/html; charset=utf-8"
                    else:
                        mime_type = "application/octet-stream"
                self._send_bytes(200, target.read_bytes(), mime_type)
                return

        self.send_error(404, f"Resource not found: {path}")

    def do_HEAD(self) -> None:
        """Handle HEAD requests for health checks and asset validation."""
        self.do_GET()

    def do_POST(self) -> None:
        if self.path != "/predict":
            self.send_error(404, "Unknown endpoint. Only POST /predict is supported for inference.")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            # Fill convenience defaults for interactive playground or partial requests
            if isinstance(data, dict):
                if "benchmark_version" not in data:
                    data["benchmark_version"] = "0.1.2"
                if "current_turn_id" not in data and data.get("turns"):
                    data["current_turn_id"] = data["turns"][-1].get("turn_id", "t1")
                if "platform_style" not in data:
                    data["platform_style"] = "gaming_chat"
                if "language_mode" not in data:
                    data["language_mode"] = "english"
                if "task" not in data:
                    data["task"] = "current_harm"

            request = InferenceRequest.model_validate(data)
            scorer = self.scorer or build_default_scorers(self.lexicon_path)["lexicon_raw"]
            output = scorer.predict(request)
            response = output.model_dump()
            self._send_json(200, response)
        except Exception as e:
            abstain = ModelOutput.create_abstention_output()
            self._send_json(422, {"error": str(e), "output": abstain.model_dump()})

    def _send_json(self, status: int, data: Any) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self._send_bytes(status, payload, "application/json")

    def _send_bytes(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy raw request text logging (private benchmark policy)
        return


def serve(
    host: str = "127.0.0.1",
    port: int = 8080,
    lexicon_path: Path | None = None,
    reports_dir: Path | None = None,
) -> None:
    """Start the evaluator server with active /predict interface and interactive dashboard view."""
    if lexicon_path:
        PredictHandler.lexicon_path = lexicon_path
    if reports_dir:
        PredictHandler.reports_dir = reports_dir
    PredictHandler.server_host = host
    PredictHandler.server_port = port

    server = ThreadingHTTPServer((host, port), PredictHandler)
    print("=" * 72)
    print("YouthEscalateBench Evaluator Service Online!")
    print(f"  • Moderation API Endpoint : http://{host}:{port}/predict")
    print(f"  • Web Dashboard View      : http://{host}:{port}/dashboard")
    print(f"  • Health Check            : http://{host}:{port}/health")
    print("=" * 72)
    server.serve_forever()
