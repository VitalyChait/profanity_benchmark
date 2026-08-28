"""Private benchmark evaluator HTTP server and interactive analysis dashboard."""

import json
import mimetypes
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import yaml

from youth_escalate_bench.baselines.scorers import ModerationScorer, build_default_scorers
from youth_escalate_bench.evaluator.dashboard import (
    _load_yaml_safe,
    build_analytics_matrix_rows_html,
    build_evaluated_models_catalog,
    build_trajectory_bars_html,
    generate_predict_page_html,
    generate_service_dashboard_html,
)
from youth_escalate_bench.reporting.infographics import (
    _get_display_name,
    generate_all_infographics,
    generate_governance_and_data_infographics,
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
                    reports_dir=self.reports_dir,
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

        if path == "/api/infographics/regenerate":
            self._handle_regenerate_infographics()
            return

        if path in ("/api/governance/regenerate", "/api/infographics/regenerate_governance"):
            self._handle_regenerate_governance_infographics()
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

    _scorers_cache: dict[str, ModerationScorer] | None = None

    @classmethod
    def get_all_scorers(cls, lexicon_path: Path) -> dict[str, ModerationScorer]:
        if cls._scorers_cache is None:
            cand_paths = [
                lexicon_path,
                Path("data/processed/youth_profanity_lexicon.json"),
                Path("configs/profanity_lexicon.txt"),
                Path("configs/youth_slang_lexicon.yaml"),
            ]
            valid_path = lexicon_path
            for p in cand_paths:
                if p.exists():
                    valid_path = p
                    break
            cls._scorers_cache = build_default_scorers(valid_path)
        return cls._scorers_cache

    def _resolve_scorers(self, req_model: Any, req_models: Any) -> list[tuple[str, ModerationScorer]]:
        all_scorers = self.get_all_scorers(self.lexicon_path)

        # Injected scorer override if neither model nor models was requested
        if self.scorer is not None and not req_model and not req_models:
            return [(getattr(self.scorer, "name", "custom_scorer"), self.scorer)]

        is_all = False
        targets: list[str] = []

        if req_models is not None:
            if isinstance(req_models, str):
                if req_models.strip().lower() in ("all", "select_all", "select all", "*"):
                    is_all = True
                else:
                    targets = [m.strip() for m in req_models.split(",") if m.strip()]
            elif isinstance(req_models, list):
                if any(str(m).strip().lower() in ("all", "select_all", "select all", "*") for m in req_models):
                    is_all = True
                else:
                    targets = [str(m).strip() for m in req_models if str(m).strip()]
        elif req_model is not None:
            s_model = str(req_model).strip()
            if s_model.lower() in ("all", "select_all", "select all", "*"):
                is_all = True
            else:
                targets = [s_model]
        else:
            targets = ["lexicon_raw"]

        if is_all:
            return list(all_scorers.items())

        resolved: list[tuple[str, ModerationScorer]] = []
        for t in targets:
            if t in all_scorers:
                resolved.append((t, all_scorers[t]))
            else:
                found = False
                for k, v in all_scorers.items():
                    if t.lower() == k.lower() or t.lower() == _get_display_name(k).lower():
                        resolved.append((k, v))
                        found = True
                        break
                if not found and "lexicon_raw" in all_scorers and ("lexicon_raw", all_scorers["lexicon_raw"]) not in resolved:
                    resolved.append(("lexicon_raw", all_scorers["lexicon_raw"]))

        return resolved or list(all_scorers.items())[:1]

    @staticmethod
    def _predict_single_scorer(name: str, scorer: ModerationScorer, request: InferenceRequest) -> dict[str, Any]:
        t0 = time.perf_counter()
        try:
            output = scorer.predict(request)
            dur_ms = (time.perf_counter() - t0) * 1000.0
            harm_p = float(output.harm_probability)
            sev_probs = output.severity_probabilities or {}
            dom_sev = max(sev_probs, key=sev_probs.get) if sev_probs else "safe"
            provider = getattr(scorer, "provider", "Local Baseline") or "Local Baseline"

            return {
                "model_id": name,
                "model_name": _get_display_name(name),
                "provider": provider,
                "harm_probability": round(harm_p, 4),
                "actionable": bool(harm_p >= 0.5),
                "dominant_severity": dom_sev,
                "severity_probabilities": {k: round(v, 4) for k, v in sev_probs.items()},
                "harm_types": {k: round(v, 4) for k, v in (output.harm_types or {}).items()},
                "abstain": bool(output.abstain),
                "latency_ms": round(dur_ms, 2),
                "status": "success" if not output.abstain else "abstained",
                "error": None,
            }
        except Exception as e:
            dur_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "model_id": name,
                "model_name": _get_display_name(name),
                "provider": getattr(scorer, "provider", "Local Baseline") or "Local Baseline",
                "harm_probability": 0.0,
                "actionable": False,
                "dominant_severity": "unknown",
                "severity_probabilities": {},
                "harm_types": {},
                "abstain": True,
                "latency_ms": round(dur_ms, 2),
                "status": "error",
                "error": str(e),
            }

    @staticmethod
    def _compute_multi_model_aggregation(
        results: dict[str, dict[str, Any]],
        total_expected: int | None = None,
    ) -> dict[str, Any]:
        valid_items = [r for r in results.values() if r["status"] == "success" and not r["abstain"]]
        if not valid_items:
            valid_items = list(results.values())

        probs = [r["harm_probability"] for r in valid_items]
        flagged_models = [r["model_name"] for r in valid_items if r["actionable"]]
        cleared_models = [r["model_name"] for r in valid_items if not r["actionable"]]

        n_total = max(len(valid_items), 1)
        n_flagged = len(flagged_models)
        n_cleared = len(cleared_models)

        mean_p = statistics.mean(probs) if probs else 0.0
        median_p = statistics.median(probs) if probs else 0.0
        std_p = statistics.stdev(probs) if len(probs) > 1 else 0.0
        min_p = min(probs) if probs else 0.0
        max_p = max(probs) if probs else 0.0

        consensus_actionable = bool(n_flagged >= (n_total / 2.0))
        majority_count = max(n_flagged, n_cleared)
        agreement_rate = majority_count / float(n_total)

        sev_sums: dict[str, float] = {}
        for r in valid_items:
            for s_key, s_val in r.get("severity_probabilities", {}).items():
                sev_sums[s_key] = sev_sums.get(s_key, 0.0) + s_val
        dominant_severity = max(sev_sums, key=sev_sums.get) if sev_sums else "safe"

        divergence_level = "Low (High Consensus)" if agreement_rate >= 0.75 else "High (Divergent Context)"

        total_models = total_expected or len(results)
        is_in_progress = total_expected is not None and len(results) < total_expected

        if is_in_progress:
            synthesis = (
                f"Asynchronous evaluation in progress: {len(results)} of {total_models} models reporting "
                f"({round((len(results) / total_models) * 100)}%). "
                f"Current trend: {majority_count} of {len(results)} models indicate "
                f"{'actionable violation' if consensus_actionable else 'benign conversation'} "
                f"({round(agreement_rate * 100)}% current consensus)."
            )
        elif agreement_rate == 1.0:
            if consensus_actionable:
                synthesis = f"Unanimous consensus: All {n_total} models agreed this turn represents actionable harmful language (mean harm: {mean_p:.2f})."
            else:
                synthesis = f"Unanimous consensus: All {n_total} models cleared this turn as non-actionable benign conversation (mean harm: {mean_p:.2f})."
        elif consensus_actionable:
            synthesis = f"Consensus flagged: {n_flagged} of {n_total} models ({agreement_rate*100:.0f}%) classified this turn as actionable {dominant_severity}. Dissenting models scored it below 0.50 threshold."
        else:
            synthesis = f"Consensus cleared: {n_cleared} of {n_total} models ({agreement_rate*100:.0f}%) determined this turn is non-actionable banter. Elevated sensitivity triggers on flagging models were outweighed by contextual clearing."

        return {
            "consensus_actionable": consensus_actionable,
            "verdict_label": "ACTIONABLE VIOLATION" if consensus_actionable else "BENIGN CONVERSATION",
            "agreement_rate": round(agreement_rate, 4),
            "agreement_percentage": round(agreement_rate * 100, 1),
            "mean_harm_probability": round(mean_p, 4),
            "median_harm_probability": round(median_p, 4),
            "std_harm_probability": round(std_p, 4),
            "min_harm_probability": round(min_p, 4),
            "max_harm_probability": round(max_p, 4),
            "dominant_severity": dominant_severity,
            "models_evaluated_count": len(results),
            "models_reporting_count": len(results),
            "models_total_count": total_models,
            "is_final": not is_in_progress,
            "progress_percentage": round((len(results) / max(1, total_models)) * 100, 1),
            "actionable_count": n_flagged,
            "cleared_count": n_cleared,
            "flagged_by": flagged_models,
            "cleared_by": cleared_models,
            "divergence_level": divergence_level,
            "synthesis": synthesis,
        }

    def do_HEAD(self) -> None:
        """Handle HEAD requests for health checks and asset validation."""
        self.do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/infographics/regenerate":
            self._handle_regenerate_infographics()
            return

        if self.path in ("/api/governance/regenerate", "/api/infographics/regenerate_governance"):
            self._handle_regenerate_governance_infographics()
            return

        if self.path != "/predict":
            self.send_error(404, "Unknown endpoint. Supported: POST /predict, /api/infographics/regenerate, /api/governance/regenerate.")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                data = {}

            req_model = data.pop("model", None)
            req_models = data.pop("models", None)
            is_stream = bool(data.pop("stream", False)) or ("stream=true" in self.path.lower()) or ("text/event-stream" in self.headers.get("Accept", ""))

            # Determine multi-model mode
            is_multi = False
            if req_models is not None:
                if isinstance(req_models, list) and len(req_models) > 1:
                    is_multi = True
                elif isinstance(req_models, str) and ("," in req_models or req_models.strip().lower() in ("all", "select_all", "select all", "*")):
                    is_multi = True
                elif isinstance(req_models, list) and any(str(m).strip().lower() in ("all", "select_all", "select all", "*") for m in req_models):
                    is_multi = True
            elif req_model is not None and str(req_model).strip().lower() in ("all", "select_all", "select all", "*"):
                is_multi = True

            # Fill convenience defaults for interactive playground or partial requests
            if "benchmark_version" not in data:
                data["benchmark_version"] = "0.1.2"
            if "conversation_id" not in data:
                data["conversation_id"] = f"predict_{int(time.time() * 1000)}"
            if "current_turn_id" not in data and data.get("turns"):
                data["current_turn_id"] = data["turns"][-1].get("turn_id", "t1")
            if "platform_style" not in data:
                data["platform_style"] = "gaming_chat"
            if "language_mode" not in data:
                data["language_mode"] = "english"
            if "task" not in data:
                data["task"] = "current_harm"

            request = InferenceRequest.model_validate(data)
            scorers_to_run = self._resolve_scorers(req_model, req_models)

            if is_stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-transform")
                self.send_header("Connection", "close")
                self.send_header("X-Accel-Buffering", "no")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                t_start = time.perf_counter()
                total_models = len(scorers_to_run)

                # Send init event listing all queued models
                init_info = {
                    "event": "init",
                    "mode": "multi_model" if is_multi or total_models > 1 else "single_model",
                    "models_count": total_models,
                    "models_queued": [
                        {
                            "model_id": s_name,
                            "model_name": _get_display_name(s_name),
                            "provider": getattr(s_obj, "provider", "Local Baseline") or "Local Baseline",
                        }
                        for s_name, s_obj in scorers_to_run
                    ],
                    "benchmark_version": request.benchmark_version,
                    "conversation_id": request.conversation_id,
                    "current_turn_id": request.current_turn_id,
                    "task": request.task,
                }
                self._send_sse_event("init", init_info)

                results_by_model: dict[str, dict[str, Any]] = {}
                workers = min(32, max(1, total_models))
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {
                        pool.submit(self._predict_single_scorer, s_name, s_obj, request): s_name
                        for s_name, s_obj in scorers_to_run
                    }
                    for fut in as_completed(futures):
                        res = fut.result()
                        results_by_model[res["model_id"]] = res
                        elapsed_from_start_ms = round((time.perf_counter() - t_start) * 1000, 2)
                        res["elapsed_since_req_ms"] = elapsed_from_start_ms

                        progressive_agg = self._compute_multi_model_aggregation(
                            results_by_model, total_expected=total_models
                        )
                        self._send_sse_event(
                            "model_done",
                            {
                                "model": res,
                                "completed_count": len(results_by_model),
                                "total_count": total_models,
                                "elapsed_ms": elapsed_from_start_ms,
                                "aggregate": progressive_agg,
                            },
                        )

                final_agg = self._compute_multi_model_aggregation(results_by_model, total_expected=total_models)
                target_text = request.turns[-1].text if request.turns else ""
                total_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
                self._send_sse_event(
                    "complete",
                    {
                        "mode": "multi_model" if is_multi or total_models > 1 else "single_model",
                        "models_count": len(results_by_model),
                        "total_duration_ms": total_duration_ms,
                        "aggregate": final_agg,
                        "models": results_by_model,
                        "target_text": target_text,
                    },
                )
                self.close_connection = True
            elif not is_multi and len(scorers_to_run) == 1:
                name, scorer = scorers_to_run[0]
                single_res = self._predict_single_scorer(name, scorer, request)
                response = {
                    **single_res,
                    "benchmark_version": request.benchmark_version,
                    "conversation_id": request.conversation_id,
                    "current_turn_id": request.current_turn_id,
                    "task": request.task,
                }
                self._send_json(200, response)
            else:
                # Concurrent parallel multi-model execution
                results_by_model: dict[str, dict[str, Any]] = {}
                workers = min(32, max(1, len(scorers_to_run)))
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {
                        pool.submit(self._predict_single_scorer, s_name, s_obj, request): s_name
                        for s_name, s_obj in scorers_to_run
                    }
                    for fut in futures:
                        res = fut.result()
                        results_by_model[res["model_id"]] = res

                aggregation = self._compute_multi_model_aggregation(results_by_model)
                target_text = request.turns[-1].text if request.turns else ""

                response = {
                    "mode": "multi_model",
                    "benchmark_version": request.benchmark_version,
                    "conversation_id": request.conversation_id,
                    "current_turn_id": request.current_turn_id,
                    "task": request.task,
                    "target_text": target_text,
                    "models_count": len(scorers_to_run),
                    "aggregate": aggregation,
                    "models": results_by_model,
                }
                self._send_json(200, response)
        except Exception as e:
            abstain = ModelOutput.create_abstention_output()
            self._send_json(422, {"error": str(e), "output": abstain.model_dump()})

    def _send_sse_event(self, event_name: str, data: Any) -> bool:
        """Send a Server-Sent Event (SSE) formatted message and flush immediately."""
        try:
            payload = json.dumps(data)
            msg = f"event: {event_name}\ndata: {payload}\n\n".encode()
            self.wfile.write(msg)
            self.wfile.flush()
            return True
        except Exception:
            return False

    def _handle_regenerate_infographics(self) -> None:
        """Dynamically regenerate publication figures, trajectory dynamics, and matrix rows for selected models."""
        t0 = time.perf_counter()
        req_models: list[str] | None = None

        if self.command == "GET":
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if "models" in query:
                req_models = []
                for item in query["models"]:
                    req_models.extend([m.strip() for m in item.split(",") if m.strip()])
        else:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                payload = {}
            raw_models = payload.get("models")
            if isinstance(raw_models, list):
                req_models = [str(m).strip() for m in raw_models if str(m).strip()]
            elif isinstance(raw_models, str):
                req_models = [m.strip() for m in raw_models.split(",") if m.strip()]

        # 1. Load evaluation results
        eval_candidates = [
            self.reports_dir / "data" / "evaluation_results.yaml",
            self.reports_dir / "evaluation_results.yaml",
            Path("data/processed/report/data/evaluation_results.yaml"),
            Path("data/processed/report/evaluation_results.yaml"),
            Path("data/processed/evaluate/evaluation_results.yaml"),
        ]
        eval_path = next((p for p in eval_candidates if p.exists()), None)
        raw_results: list[dict[str, Any]] = []
        if eval_path:
            raw_data = _load_yaml_safe(eval_path)
            raw_results = raw_data if isinstance(raw_data, list) else raw_data.get("results", [])

        # 2. Build full catalog
        full_catalog = build_evaluated_models_catalog(self.reports_dir)
        all_models = full_catalog.get("models", [])

        # 3. Filter models
        if req_models and not any(str(m).lower() in ("all", "select_all", "*") for m in req_models):
            target_ids = {str(m).lower() for m in req_models}
            selected_models = [
                m for m in all_models
                if m["id"].lower() in target_ids
                or m["name"].lower() in target_ids
                or any(t in m["id"].lower() or t in m["name"].lower() for t in target_ids)
            ]
            if not selected_models:
                selected_models = all_models
        else:
            selected_models = all_models

        selected_ids = {m["id"] for m in selected_models}
        filtered_results = [
            r for r in raw_results
            if r.get("scorer") in selected_ids
            or any(m["id"] == r.get("scorer") for m in selected_models)
        ]
        if not filtered_results:
            filtered_results = raw_results

        # 4. Load onset data if available
        onset_candidates = [
            self.reports_dir / "data" / "onset_metrics.yaml",
            self.reports_dir / "onset_metrics.yaml",
            Path("data/processed/evaluate/onset_metrics.yaml"),
        ]
        onset_path = next((p for p in onset_candidates if p.exists()), None)
        onset_data = _load_yaml_safe(onset_path) if onset_path else {}

        # 5. Generate updated infographics (saved directly into self.reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        generated_files = generate_all_infographics(
            filtered_results,
            self.reports_dir,
            onset_data,
        )

        # 6. Recompute KPI summaries for selected models
        top_llm = next((m for m in selected_models if m.get("provider") != "Local Baseline"), None)
        top_baseline = next((m for m in selected_models if m.get("provider") == "Local Baseline"), None)
        max_delta_model = max(selected_models, key=lambda m: m.get("delta_auprc", 0.0)) if selected_models else None

        # 7. Pre-render updated HTML snippets
        trajectory_html = build_trajectory_bars_html(selected_models)
        matrix_html = build_analytics_matrix_rows_html(selected_models)

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)

        resp = {
            "status": "success",
            "models_count": len(selected_models),
            "selected_models": [m["id"] for m in selected_models],
            "generated_files": generated_files,
            "top_llm": {
                "name": top_llm["name"],
                "prefix_auprc": round(top_llm["prefix_auprc"], 3),
            } if top_llm else None,
            "top_baseline": {
                "name": top_baseline["name"],
                "prefix_auprc": round(top_baseline["prefix_auprc"], 3),
            } if top_baseline else None,
            "max_delta_model": {
                "name": max_delta_model["name"],
                "delta_auprc": round(max_delta_model["delta_auprc"], 3),
            } if max_delta_model else None,
            "trajectory_bars_html": trajectory_html,
            "matrix_rows_html": matrix_html,
            "elapsed_ms": elapsed_ms,
            "timestamp": int(time.time() * 1000),
        }
        self._send_json(200, resp)

    def _handle_regenerate_governance_infographics(self) -> None:
        """Handle on-demand generation of governance, split data & audit reports infographics."""
        t0 = time.perf_counter()
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        generated_files = generate_governance_and_data_infographics(
            self.reports_dir,
            self.reports_dir,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        resp = {
            "status": "success",
            "generated_files": generated_files,
            "elapsed_ms": elapsed_ms,
            "timestamp": int(time.time() * 1000),
        }
        self._send_json(200, resp)

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

    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), PredictHandler)
    server.daemon_threads = True
    print("=" * 72)
    print("YouthEscalateBench Evaluator Service Online!")
    print(f"  • Moderation API Endpoint : http://{host}:{port}/predict")
    print(f"  • Web Dashboard View      : http://{host}:{port}/dashboard")
    print(f"  • Health Check            : http://{host}:{port}/health")
    print("=" * 72)
    server.serve_forever()
