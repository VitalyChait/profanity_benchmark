"""Unit tests for evaluator service, HTTP server, and analysis dashboard."""

import json
import threading
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

import pytest

from youth_escalate_bench.evaluator.dashboard import generate_service_dashboard_html
from youth_escalate_bench.evaluator.server import PredictHandler, ThreadingHTTPServer


@pytest.fixture(scope="module")
def live_server():
    """Start an ephemeral test HTTP server on an open local port."""
    PredictHandler.reports_dir = Path("reports")
    PredictHandler.lexicon_path = Path("configs/profanity_lexicon.txt")
    PredictHandler.server_host = "127.0.0.1"
    PredictHandler.server_port = 0  # picks random free port

    server = ThreadingHTTPServer(("127.0.0.1", 0), PredictHandler)
    host, port = server.server_address
    PredictHandler.server_port = port

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield host, port
    server.shutdown()
    server.server_close()


def test_generate_service_dashboard_html() -> None:
    html = generate_service_dashboard_html(reports_dir=Path("reports"), host="127.0.0.1", port=8080)
    assert "<title>YouthEscalateBench — Live Evaluator Dashboard</title>" in html
    assert "Visual Analytics" in html
    assert "Live Predict Playground" in html
    assert "Failure Case Diagnostics" in html
    assert "Fig 1: Comprehensive Multi-Panel" in html
    assert "Causal Context Trajectories" in html
    assert "analytics-matrix-table" in html
    assert "lightbox-modal" in html
    assert "tab-badge" in html
    assert "difficulty-table" in html
    assert "difficulty-search" in html
    assert "setDifficultyFilter" in html
    assert "setModelFilter" in html
    assert "setDashboardPreset" in html
    assert "testTurnInPlayground" in html
    assert "dash-model-grid" in html
    assert "Local Baselines" in html
    assert "Frontier LLMs" in html
    assert "Custom Models" in html
    assert "<th>Custom</th>" in html
    assert "addCustomPredictModel" in html
    assert "dash-visual-verdict" in html
    assert "renderPredictResponse" in html
    assert "analytics-selected-count" in html
    assert "btn-regenerate-analytics" in html
    assert "analytics-model-grid" in html
    assert "analytics-matrix-tbody" in html
    assert "analytics-trajectory-container" in html
    assert "fig-img-comparison" in html
    assert "fig-dl-comparison" in html
    assert "regenerateAnalyticsInfographics" in html


def test_server_health_check(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=5)
    conn.request("GET", "/health")
    res = conn.getresponse()
    assert res.status == 200
    data = json.loads(res.read().decode("utf-8"))
    assert data["status"] == "healthy"
    conn.close()

    # Test HEAD request
    conn = HTTPConnection(host, port, timeout=5)
    conn.request("HEAD", "/health")
    res_head = conn.getresponse()
    assert res_head.status == 200
    conn.close()


def test_server_dashboard_view(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=5)
    conn.request("GET", "/dashboard")
    res = conn.getresponse()
    assert res.status == 200
    assert "text/html" in res.getheader("Content-Type", "")
    body = res.read().decode("utf-8")
    assert "YouthEscalateBench Evaluator" in body
    assert "service-badge" in body
    conn.close()


def test_server_predict_get_html(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=5)
    headers = {"Accept": "text/html,application/xhtml+xml"}
    conn.request("GET", "/predict", headers=headers)
    res = conn.getresponse()
    assert res.status == 200
    assert "text/html" in res.getheader("Content-Type", "")
    body = res.read().decode("utf-8")
    assert "Moderation API Sandbox (/predict)" in body
    assert "Live Response Payload" in body
    assert "Execute POST /predict Request" in body
    assert "pred-model-grid" in body
    assert "Select All" in body
    assert "Local Baselines" in body
    assert "Frontier LLMs" in body
    assert "Custom Models" in body
    assert "<th>Custom</th>" in body
    assert "addCustomPredictModel" in body
    assert "renderPredictResponse" in body
    conn.close()


def test_server_predict_get_json(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=5)
    headers = {"Accept": "application/json"}
    conn.request("GET", "/predict", headers=headers)
    res = conn.getresponse()
    assert res.status == 200
    assert "application/json" in res.getheader("Content-Type", "")
    data = json.loads(res.read().decode("utf-8"))
    assert data["endpoint"] == "/predict"
    assert data["method_supported"] == "POST"
    assert "sample_curl" in data
    assert "sample_payload" in data
    conn.close()


def test_server_predict_options(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=5)
    conn.request("OPTIONS", "/predict")
    res = conn.getresponse()
    assert res.status == 204
    assert res.getheader("Access-Control-Allow-Origin") == "*"
    assert "POST" in res.getheader("Access-Control-Allow-Methods", "")
    conn.close()



def test_server_api_endpoints(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=5)

    # 1. /api/summary
    conn.request("GET", "/api/summary")
    res_sum = conn.getresponse()
    assert res_sum.status == 200
    assert "application/json" in res_sum.getheader("Content-Type", "")
    data_sum = json.loads(res_sum.read().decode("utf-8"))
    assert isinstance(data_sum, dict)

    # 2. /api/difficulty
    conn.request("GET", "/api/difficulty")
    res_diff = conn.getresponse()
    assert res_diff.status == 200
    data_diff = json.loads(res_diff.read().decode("utf-8"))
    assert isinstance(data_diff, dict)

    # 3. /api/errors
    conn.request("GET", "/api/errors")
    res_err = conn.getresponse()
    assert res_err.status == 200
    data_err = json.loads(res_err.read().decode("utf-8"))
    assert isinstance(data_err, dict)

    # 4. /api/models
    conn.request("GET", "/api/models")
    res_mod = conn.getresponse()
    assert res_mod.status == 200
    assert "application/json" in res_mod.getheader("Content-Type", "")
    data_mod = json.loads(res_mod.read().decode("utf-8"))
    assert isinstance(data_mod, dict)
    assert "total_models" in data_mod
    assert data_mod["total_models"] >= 30
    assert "session" in data_mod
    assert "timestamp" in data_mod["session"]
    assert "models" in data_mod
    assert len(data_mod["models"]) >= 30
    first_model = data_mod["models"][0]
    assert "name" in first_model
    assert "provider" in first_model
    assert "when_evaluated" in first_model
    assert "is_accessible" in first_model

    conn.close()


def test_server_static_report_assets(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=5)

    # Check png figure serving
    conn.request("GET", "/reports/figure_auprc_heatmap.png")
    res_img = conn.getresponse()
    assert res_img.status in (200, 404)
    if res_img.status == 200:
        assert res_img.getheader("Content-Type") == "image/png"
        payload = res_img.read()
        assert len(payload) > 100

    conn.close()


def test_server_predict_post(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=5)

    req_body = {
        "request_id": "test_req_01",
        "conversation_id": "test_conv_01",
        "condition": "current_turn_only",
        "turns": [
            {
                "turn_id": "t1",
                "speaker_id": "user1",
                "role": "user",
                "relative_time": "0s",
                "text": "you are trash and nobody likes you",
            }
        ],
    }
    payload = json.dumps(req_body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Content-Length": str(len(payload))}

    conn.request("POST", "/predict", body=payload, headers=headers)
    res = conn.getresponse()
    assert res.status == 200
    data = json.loads(res.read().decode("utf-8"))
    assert "severity_probabilities" in data
    assert "harm_probability" in data

    conn.close()


def test_server_predict_post_invalid(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=5)

    # Missing required turns
    bad_payload = json.dumps({"invalid_field": True}).encode("utf-8")
    headers = {"Content-Type": "application/json", "Content-Length": str(len(bad_payload))}

    conn.request("POST", "/predict", body=bad_payload, headers=headers)
    res = conn.getresponse()
    assert res.status == 422
    data = json.loads(res.read().decode("utf-8"))
    assert "error" in data
    assert "output" in data

    conn.close()


def test_server_predict_single_model(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=5)

    req_body = {
        "request_id": "test_req_single",
        "conversation_id": "test_conv_single",
        "model": "lexicon_normalized",
        "turns": [
            {
                "turn_id": "t1",
                "speaker_id": "user1",
                "role": "user",
                "relative_time": "0s",
                "text": "you are trash and useless",
            }
        ],
    }
    payload = json.dumps(req_body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Content-Length": str(len(payload))}

    conn.request("POST", "/predict", body=payload, headers=headers)
    res = conn.getresponse()
    assert res.status == 200
    data = json.loads(res.read().decode("utf-8"))
    assert data["model_id"] == "lexicon_normalized"
    assert "harm_probability" in data
    assert "actionable" in data
    assert "latency_ms" in data
    conn.close()


def test_server_predict_multi_model(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=5)

    req_body = {
        "request_id": "test_req_multi",
        "conversation_id": "test_conv_multi",
        "models": ["lexicon_raw", "lexicon_normalized", "char_ngram_tfidf"],
        "turns": [
            {
                "turn_id": "t1",
                "speaker_id": "user1",
                "role": "user",
                "relative_time": "0s",
                "text": "you are trash uninstall right now",
            }
        ],
    }
    payload = json.dumps(req_body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Content-Length": str(len(payload))}

    conn.request("POST", "/predict", body=payload, headers=headers)
    res = conn.getresponse()
    assert res.status == 200
    data = json.loads(res.read().decode("utf-8"))
    assert data["mode"] == "multi_model"
    assert data["models_count"] == 3
    assert "aggregate" in data
    agg = data["aggregate"]
    assert "consensus_actionable" in agg
    assert "agreement_rate" in agg
    assert "mean_harm_probability" in agg
    assert "synthesis" in agg
    assert "models" in data
    assert len(data["models"]) == 3
    assert "lexicon_raw" in data["models"]
    assert "lexicon_normalized" in data["models"]
    assert "char_ngram_tfidf" in data["models"]
    conn.close()


def test_server_predict_multi_model_all_baselines(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=10)

    req_body = {
        "request_id": "test_req_all_baselines",
        "conversation_id": "test_conv_all_baselines",
        "models": [
            "lexicon_raw",
            "lexicon_normalized",
            "char_ngram_tfidf",
            "lexicon_full_context",
            "rule_based_safeguard",
            "ensemble_moderator",
        ],
        "turns": [
            {
                "turn_id": "t1",
                "speaker_id": "user1",
                "role": "user",
                "relative_time": "0s",
                "text": "you are trash and useless uninstall right now",
            }
        ],
    }
    payload = json.dumps(req_body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Content-Length": str(len(payload))}

    conn.request("POST", "/predict", body=payload, headers=headers)
    res = conn.getresponse()
    assert res.status == 200
    data = json.loads(res.read().decode("utf-8"))
    assert data["mode"] == "multi_model"
    assert data["models_count"] == 6
    assert "aggregate" in data
    assert "consensus_actionable" in data["aggregate"]
    assert "agreement_percentage" in data["aggregate"]
    assert len(data["models"]) == 6
    conn.close()


def test_server_resolve_scorers_all() -> None:
    handler = PredictHandler.__new__(PredictHandler)
    handler.lexicon_path = Path("data/processed/youth_profanity_lexicon.json")
    handler.scorer = None
    scorers = handler._resolve_scorers(None, "all")
    assert len(scorers) >= 30
    assert any(s[0] == "lexicon_raw" for s in scorers)


def test_server_predict_streaming_multi_model(live_server: tuple[str, int]) -> None:
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=10)

    req_body = {
        "stream": True,
        "models": ["lexicon_raw", "lexicon_normalized", "char_ngram_tfidf"],
        "turns": [
            {
                "turn_id": "t1",
                "speaker_id": "user1",
                "role": "user",
                "relative_time": "0s",
                "text": "you are trash and useless uninstall right now",
            }
        ],
    }
    payload = json.dumps(req_body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Content-Length": str(len(payload))}

    conn.request("POST", "/predict", body=payload, headers=headers)
    res = conn.getresponse()
    assert res.status == 200
    assert "text/event-stream" in res.getheader("Content-Type", "")

    events: list[tuple[str, dict[str, Any]]] = []
    current_event = "message"
    for line_bytes in res:
        line = line_bytes.decode("utf-8").strip()
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_str = line.split(":", 1)[1].strip()
            events.append((current_event, json.loads(data_str)))

    event_names = [e[0] for e in events]
    assert "init" in event_names
    assert "model_done" in event_names
    assert "complete" in event_names

    # Verify progressive model_done events
    model_done_events = [e[1] for e in events if e[0] == "model_done"]
    assert len(model_done_events) == 3
    for mde in model_done_events:
        assert "model" in mde
        assert "completed_count" in mde
        assert "total_count" in mde
        assert mde["total_count"] == 3
        assert "aggregate" in mde
        assert "consensus_actionable" in mde["aggregate"]

    # Verify complete event
    complete_event = next(e[1] for e in events if e[0] == "complete")
    assert complete_event["models_count"] == 3
    assert len(complete_event["models"]) == 3
    assert "aggregate" in complete_event
    assert complete_event["aggregate"]["is_final"] is True
    conn.close()


def test_server_infographics_regenerate_post(live_server: tuple[str, int]) -> None:
    """Test POST /api/infographics/regenerate with specific model subset."""
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=30)
    payload = json.dumps({"models": ["lexicon_raw", "char_ngram_tfidf"]})
    headers = {"Content-Type": "application/json"}
    conn.request("POST", "/api/infographics/regenerate", body=payload, headers=headers)
    res = conn.getresponse()
    assert res.status == 200
    assert "application/json" in res.getheader("Content-Type", "")
    data = json.loads(res.read().decode("utf-8"))
    assert data["status"] == "success"
    assert data["models_count"] == 2
    assert "lexicon_raw" in data["selected_models"]
    assert "char_ngram_tfidf" in data["selected_models"]
    assert len(data["generated_files"]) >= 4
    assert "infographic_models_comparison.png" in data["generated_files"]
    assert "figure_auprc_heatmap.png" in data["generated_files"]
    assert "figure_context_trajectory.png" in data["generated_files"]
    assert "figure_llm_leaderboard.png" in data["generated_files"]
    assert data["top_baseline"] is not None
    assert "trajectory_bars_html" in data
    assert "matrix_rows_html" in data
    assert "timestamp" in data
    conn.close()


def test_server_infographics_regenerate_get(live_server: tuple[str, int]) -> None:
    """Test GET /api/infographics/regenerate with query params."""
    host, port = live_server
    conn = HTTPConnection(host, port, timeout=30)
    conn.request("GET", "/api/infographics/regenerate?models=lexicon_raw")
    res = conn.getresponse()
    assert res.status == 200
    assert "application/json" in res.getheader("Content-Type", "")
    data = json.loads(res.read().decode("utf-8"))
    assert data["status"] == "success"
    assert data["models_count"] == 1
    assert data["selected_models"] == ["lexicon_raw"]
    conn.close()
