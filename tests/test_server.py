"""Unit tests for evaluator service, HTTP server, and analysis dashboard."""

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

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
