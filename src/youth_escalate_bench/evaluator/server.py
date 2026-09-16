"""Private benchmark evaluator HTTP server and interactive analysis dashboard."""

import gzip
import hashlib
import json
import mimetypes
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import yaml

from youth_escalate_bench.baselines.scorers import ModerationScorer, build_default_scorers
from youth_escalate_bench.evaluator.dashboard import (
    _load_difficulty_data,
    _load_json_safe,
    _load_yaml_safe,
    _unwrap_cached_list,
    build_analytics_matrix_rows_html,
    build_evaluated_models_catalog,
    build_trajectory_bars_html,
    generate_predict_page_html,
    generate_service_dashboard_html,
    invalidate_dashboard_caches,
)
from youth_escalate_bench.reporting.infographics import (
    _get_display_name,
    generate_all_infographics,
    generate_governance_and_data_infographics,
)
from youth_escalate_bench.schemas.inference import InferenceRequest, ModelOutput

# In-process response caches (mtime-aware). Shared across handler threads.
_API_BYTES_CACHE: dict[str, tuple[str, bytes]] = {}
_STATIC_BYTES_CACHE: dict[str, tuple[int, bytes, str]] = {}
_RESPONSE_CACHE_LOCK = threading.Lock()
_MAX_STATIC_CACHE_BYTES = 8 * 1024 * 1024  # cache individual files up to 8 MiB
_STUB_MAX_BYTES = 512


def _file_is_stub(path: Path) -> bool:
    try:
        return path.stat().st_size <= _STUB_MAX_BYTES
    except OSError:
        return True


def pick_static_report_file(
    relative_name: str,
    candidate_dirs: list[Path],
    *,
    preferred_dir: Path | None = None,
) -> Path | None:
    """Choose which on-disk report artifact to serve for a URL.

    Stub files (tiny placeholders) never win. When the request maps to a
    preferred directory (e.g. ``/reports/foo.png`` → ``reports/foo.png``), that
    copy is used if it is a real file so freshly regenerated figures are not
    hidden by a larger stale copy under ``data/processed/report/``.
    """
    matches: list[Path] = []
    for c_dir in candidate_dirs:
        target = c_dir / relative_name
        if target.is_file() and target not in matches:
            matches.append(target)
        base_only = c_dir / Path(relative_name).name
        if base_only.is_file() and base_only not in matches:
            matches.append(base_only)
    if not matches:
        return None

    if preferred_dir is not None:
        for candidate in (preferred_dir / relative_name, preferred_dir / Path(relative_name).name):
            if candidate in matches and not _file_is_stub(candidate):
                return candidate

    def _rank(p: Path) -> tuple[int, float, int]:
        try:
            st = p.stat()
            return (0 if st.st_size <= _STUB_MAX_BYTES else 1, st.st_mtime, st.st_size)
        except OSError:
            return (0, 0.0, 0)

    return max(matches, key=_rank)


def _catalog_models_to_eval_rows(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build evaluation-result rows from catalog metrics when YAML rows are missing."""
    rows: list[dict[str, Any]] = []
    cond_map = (
        ("current_turn_only", "turn_auprc", "turn_auroc"),
        ("prev_plus_current", "pair_auprc", "pair_auroc"),
        ("full_prefix", "prefix_auprc", "prefix_auroc"),
    )
    for m in models:
        scorer = str(m.get("id") or "")
        if not scorer:
            continue
        for cond, auprc_key, auroc_key in cond_map:
            auroc = m.get(auroc_key)
            row: dict[str, Any] = {
                "scorer": scorer,
                "condition": cond,
                "auprc": float(m.get(auprc_key) or 0.0),
                "recall_at_fpr_1pct": float(m.get("r_at_fpr1") or 0.0),
            }
            if auroc is not None:
                row["auroc"] = float(auroc)
            rows.append(row)
    return rows


def _paths_fingerprint(paths: list[Path]) -> str:
    parts: list[str] = []
    for p in paths:
        try:
            st = p.stat()
            parts.append(f"{p.resolve()}:{st.st_mtime_ns}:{st.st_size}")
        except OSError:
            parts.append(f"{p}:missing")
    return "|".join(parts)


def _get_cached_api_bytes(cache_key: str, fingerprint: str, builder) -> bytes:
    with _RESPONSE_CACHE_LOCK:
        hit = _API_BYTES_CACHE.get(cache_key)
        if hit and hit[0] == fingerprint:
            return hit[1]
    payload = builder()
    with _RESPONSE_CACHE_LOCK:
        _API_BYTES_CACHE[cache_key] = (fingerprint, payload)
    return payload


def _get_cached_static_bytes(path: Path) -> tuple[bytes, str] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    if st.st_size > _MAX_STATIC_CACHE_BYTES:
        return None
    key = str(path.resolve())
    with _RESPONSE_CACHE_LOCK:
        hit = _STATIC_BYTES_CACHE.get(key)
        if hit and hit[0] == st.st_mtime_ns:
            return hit[1], hit[2]
    data = path.read_bytes()
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        if path.suffix in (".md", ".txt", ".yaml", ".yml", ".tex"):
            mime_type = "text/plain; charset=utf-8"
        elif path.suffix == ".json":
            mime_type = "application/json"
        elif path.suffix == ".png":
            mime_type = "image/png"
        elif path.suffix in (".html", ".htm"):
            mime_type = "text/html; charset=utf-8"
        else:
            mime_type = "application/octet-stream"
    with _RESPONSE_CACHE_LOCK:
        _STATIC_BYTES_CACHE[key] = (st.st_mtime_ns, data, mime_type)
    return data, mime_type


def invalidate_response_caches() -> None:
    with _RESPONSE_CACHE_LOCK:
        _API_BYTES_CACHE.clear()
        _STATIC_BYTES_CACHE.clear()


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
                self._send_bytes(
                    200,
                    html_content.encode("utf-8"),
                    "text/html; charset=utf-8",
                    cacheable=True,
                    max_age=60,
                )
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
            self._send_bytes(
                200,
                html_content.encode("utf-8"),
                "text/html; charset=utf-8",
                cacheable=True,
                max_age=60,
            )
            return

        # 4. REST API endpoints for analysis
        if path == "/api/summary":
            candidates = [
                self.reports_dir / "report_summary.yaml",
                Path("data/processed/report/report_summary.yaml"),
            ]
            fp = _paths_fingerprint(candidates)

            def _build_summary() -> bytes:
                data: dict[str, Any] = {}
                for summary_file in candidates:
                    if summary_file.exists():
                        data = _load_yaml_safe(summary_file)
                        break
                return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

            payload = _get_cached_api_bytes("api_summary", fp, _build_summary)
            self._send_bytes(200, payload, "application/json", cacheable=True, max_age=120)
            return

        if path == "/api/errors":
            candidates = [
                self.reports_dir / "llm_error_cases.json",
                Path("data/processed/report/llm_error_cases.json"),
            ]
            fp = _paths_fingerprint(candidates)

            def _build_errors() -> bytes:
                data: dict[str, Any] = {}
                best_n = -1
                for errors_file in candidates:
                    if not errors_file.exists():
                        continue
                    candidate = _load_json_safe(errors_file)
                    n = int((candidate.get("summary") or {}).get("total_error_instances", 0) or 0)
                    if n > best_n:
                        data = candidate
                        best_n = n
                return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

            payload = _get_cached_api_bytes("api_errors", fp, _build_errors)
            self._send_bytes(200, payload, "application/json", cacheable=True, max_age=120)
            return

        if path == "/api/difficulty":
            yaml_candidates = [
                self.reports_dir / "difficulty_ranking.yaml",
                Path("data/processed/report/difficulty_ranking.yaml"),
                Path("data/processed/evaluate/difficulty_ranking.yaml"),
            ]
            json_candidates = [p.with_suffix(".json") for p in yaml_candidates]
            fp = _paths_fingerprint(yaml_candidates + json_candidates)

            def _build_difficulty() -> bytes:
                data: dict[str, Any] = {}
                for yaml_path in yaml_candidates:
                    if yaml_path.exists() or yaml_path.with_suffix(".json").exists():
                        data = _load_difficulty_data(yaml_path)
                        if data:
                            break
                return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

            payload = _get_cached_api_bytes("api_difficulty", fp, _build_difficulty)
            self._send_bytes(200, payload, "application/json", cacheable=True, max_age=120)
            return

        if path == "/api/models":
            fp = _paths_fingerprint(
                [
                    self.reports_dir / "evaluation_results.yaml",
                    self.reports_dir / "data" / "evaluation_results.yaml",
                    Path("data/processed/report/evaluation_results.yaml"),
                    Path(".env"),
                ]
            )

            def _build_models() -> bytes:
                models_catalog = build_evaluated_models_catalog(self.reports_dir)
                return json.dumps(models_catalog, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

            payload = _get_cached_api_bytes("api_models", fp, _build_models)
            self._send_bytes(200, payload, "application/json", cacheable=True, max_age=60)
            return

        if path == "/api/infographics/regenerate":
            self._handle_regenerate_infographics()
            return

        if path in ("/api/governance/regenerate", "/api/infographics/regenerate_governance"):
            self._handle_regenerate_governance_infographics()
            return

        # 5. Static reports, figures, heatmaps, and summaries
        filename = path.lstrip("/")
        # Keep full relative path under reports/ or data/processed/report/
        # so alternate roots remain reachable when stubs shadow basenames.
        relative_name = filename
        preferred_dir: Path | None = None
        if filename.startswith("reports/"):
            relative_name = filename[len("reports/") :]
            preferred_dir = self.reports_dir
        elif filename.startswith("data/processed/report/"):
            relative_name = filename[len("data/processed/report/") :]
            preferred_dir = Path("data/processed/report")

        candidate_dirs = [
            self.reports_dir,
            Path("data/processed/report"),
            Path("reports"),
            Path("reports/snapshots/snapshot_2026.Q1"),
        ]
        target = pick_static_report_file(
            relative_name,
            candidate_dirs,
            preferred_dir=preferred_dir,
        )
        if target is not None:
            cached = _get_cached_static_bytes(target)
            if cached is not None:
                data, mime_type = cached
            else:
                data = target.read_bytes()
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
            is_image = (mime_type or "").startswith("image/")
            self._send_bytes(200, data, mime_type, cacheable=not is_image, max_age=300)
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
            raw_data = _unwrap_cached_list(_load_yaml_safe(eval_path))
            if isinstance(raw_data, list):
                raw_results = [r for r in raw_data if isinstance(r, dict)]
            elif isinstance(raw_data, dict):
                nested = raw_data.get("results", [])
                raw_results = nested if isinstance(nested, list) else []

        # 2. Build full catalog
        full_catalog = build_evaluated_models_catalog(self.reports_dir)
        all_models = full_catalog.get("models", [])

        # 3. Filter models — never silently expand a subset back to the full panel
        subset_requested = bool(
            req_models and not any(str(m).lower() in ("all", "select_all", "*") for m in req_models)
        )
        if subset_requested:
            target_ids = {str(m).lower() for m in req_models or []}
            selected_models = [
                m for m in all_models
                if m["id"].lower() in target_ids
                or m["name"].lower() in target_ids
                or any(t in m["id"].lower() or t in m["name"].lower() for t in target_ids)
            ]
            if not selected_models:
                self._send_json(
                    400,
                    {
                        "status": "error",
                        "error": "No evaluated models matched the requested ids.",
                        "requested": req_models,
                    },
                )
                return
        else:
            selected_models = all_models

        selected_ids = {m["id"] for m in selected_models}
        filtered_results = [
            r for r in raw_results
            if r.get("scorer") in selected_ids
            or any(m["id"] == r.get("scorer") for m in selected_models)
        ]
        if not filtered_results:
            filtered_results = (
                _catalog_models_to_eval_rows(selected_models) if subset_requested else raw_results
            )

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
            include_governance=False,
        )
        invalidate_dashboard_caches()
        invalidate_response_caches()

        # 6. Recompute KPI summaries for selected models
        top_llm = next((m for m in selected_models if m.get("provider") != "Local Baseline"), None)
        top_baseline = next((m for m in selected_models if m.get("provider") == "Local Baseline"), None)
        max_delta_model = max(selected_models, key=lambda m: m.get("delta_auprc", 0.0)) if selected_models else None

        # 7. Pre-render updated HTML snippets for the selected scope (all rows, not a top-N sample)
        trajectory_html = build_trajectory_bars_html(selected_models, max_bars=None)
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
        invalidate_dashboard_caches()
        invalidate_response_caches()
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        resp = {
            "status": "success",
            "generated_files": generated_files,
            "elapsed_ms": elapsed_ms,
            "timestamp": int(time.time() * 1000),
        }
        self._send_json(200, resp)

    def _client_accepts_gzip(self) -> bool:
        accept = (self.headers.get("Accept-Encoding") or "").lower()
        return "gzip" in accept

    def _send_json(self, status: int, data: Any) -> None:
        payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, payload, "application/json")

    def _send_bytes(
        self,
        status: int,
        payload: bytes,
        content_type: str,
        *,
        cacheable: bool = False,
        max_age: int = 300,
    ) -> None:
        use_gzip = (
            self._client_accepts_gzip()
            and len(payload) >= 512
            and (
                content_type.startswith("text/")
                or content_type.startswith("application/json")
                or "javascript" in content_type
            )
        )
        body = gzip.compress(payload, compresslevel=6) if use_gzip else payload

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Vary", "Accept-Encoding")
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
        if cacheable:
            self.send_header("Cache-Control", f"public, max-age={max_age}")
            etag = hashlib.sha1(payload).hexdigest()[:16]
            self.send_header("ETag", f'"{etag}"')
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy raw request text logging (private benchmark policy)
        return


def _prewarm_service_caches(reports_dir: Path, host: str, port: int, lexicon_path: Path) -> None:
    """Warm dashboard HTML, API payloads, and baseline scorers before accepting traffic."""
    t0 = time.perf_counter()
    try:
        PredictHandler.get_all_scorers(lexicon_path)
    except Exception:
        pass
    try:
        generate_service_dashboard_html(reports_dir=reports_dir, host=host, port=port)
    except Exception:
        pass
    try:
        generate_predict_page_html(host=host, port=port, reports_dir=reports_dir)
    except Exception:
        pass
    try:
        build_evaluated_models_catalog(reports_dir)
    except Exception:
        pass
    # Prefetch hot API payloads into the byte cache
    try:
        for yaml_path in (
            reports_dir / "difficulty_ranking.yaml",
            Path("data/processed/report/difficulty_ranking.yaml"),
        ):
            if yaml_path.exists() or yaml_path.with_suffix(".json").exists():
                _load_difficulty_data(yaml_path)
                break
        for errors_file in (
            reports_dir / "llm_error_cases.json",
            Path("data/processed/report/llm_error_cases.json"),
        ):
            if errors_file.exists():
                _load_json_safe(errors_file)
                break
    except Exception:
        pass
    print(f"  • Cache prewarm complete   : {round((time.perf_counter() - t0) * 1000.0)} ms")


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

    lex = PredictHandler.lexicon_path
    reps = PredictHandler.reports_dir
    _prewarm_service_caches(reps, host, port, lex)

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
