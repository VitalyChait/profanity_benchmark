"""Unit tests for LLM provider validation and sanity checking."""

import json
import os
from unittest.mock import MagicMock, patch

import httpx

from youth_escalate_bench.annotation.llm_judge import MultiLLMJudge
from youth_escalate_bench.llm.validator import (
    ProviderValidationResult,
    ValidationReport,
    get_working_providers,
    validate_all_providers,
    validate_provider,
)


def test_validate_unconfigured_provider():
    with patch.dict(os.environ, {}, clear=True):
        res = validate_provider("openai")
        assert not res.is_configured
        assert not res.is_working
        assert res.status == "NOT_CONFIGURED"
        assert res.error_message is not None


def test_validate_healthy_provider():
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk-mock123456"}, clear=True):
        with patch("youth_escalate_bench.llm.router.LLMRouter.call_llm", return_value="OK"):
            res = validate_provider("groq")
            assert res.is_configured
            assert res.is_working
            assert res.status == "WORKING"
            assert res.latency_ms is not None
            assert res.response_sample == "OK"


def test_validate_auth_error():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-invalid"}, clear=True):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        mock_resp.reason_phrase = "Unauthorized"
        mock_resp.text = "Incorrect API key provided"
        err = httpx.HTTPStatusError("401 Unauthorized", request=MagicMock(), response=mock_resp)

        with patch("youth_escalate_bench.llm.router.LLMRouter.call_llm", side_effect=err):
            res = validate_provider("openai")
            assert res.is_configured
            assert not res.is_working
            assert res.status == "AUTH_ERROR"
            assert res.http_status_code == 401
            assert "401" in (res.error_message or "")


def test_validate_timeout_error():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyFakeKey"}, clear=True):
        err = httpx.TimeoutException("Read timed out")
        with patch("youth_escalate_bench.llm.router.LLMRouter.call_llm", side_effect=err):
            res = validate_provider("gemini", timeout=2.0)
            assert res.is_configured
            assert not res.is_working
            assert res.status == "TIMEOUT"
            assert "timed out" in (res.error_message or "")


def test_validation_report_formatting_and_export(tmp_path):
    results = [
        ProviderValidationResult(
            provider="groq",
            model="llama-3.1-8b-instant",
            is_configured=True,
            is_working=True,
            status="WORKING",
            latency_ms=120.5,
            response_sample="OK",
        ),
        ProviderValidationResult(
            provider="openai",
            model="gpt-4o-mini",
            is_configured=True,
            is_working=False,
            status="AUTH_ERROR",
            latency_ms=85.0,
            http_status_code=401,
            error_message="HTTP 401: Invalid API key",
        ),
        ProviderValidationResult(
            provider="xai",
            model="grok-2-latest",
            is_configured=False,
            is_working=False,
            status="NOT_CONFIGURED",
            error_message="No key in .env",
        ),
    ]
    report = ValidationReport(timestamp=1700000000.0, results=results)

    assert len(report.working_models) == 1
    assert len(report.failing_models) == 1
    assert len(report.unconfigured_models) == 1
    assert report.working_provider_names == ["groq"]

    # Markdown table
    md = report.to_markdown_table()
    assert "| Provider | Configured Model | Status | Latency | Probe Response / Error |" in md
    assert "llama-3.1-8b-instant" in md
    assert "AUTH_ERROR" in md or "FAILED" in md

    # Summary text
    summary = report.summary_text()
    assert "YouthEscalateBench — LLM Validation Sanity Check Report" in summary
    assert "WORKING MODELS" in summary

    # JSON export
    json_file = tmp_path / "report.json"
    report.save_json(json_file)
    assert json_file.exists()
    data = json.loads(json_file.read_text())
    assert data["working_count"] == 1
    assert data["failing_count"] == 1


def test_get_working_providers():
    with patch.dict(os.environ, {"MISTRAL_API_KEY": "mock_key"}, clear=True):
        with patch("youth_escalate_bench.llm.router.LLMRouter.call_llm", return_value="OK"):
            working = get_working_providers(["mistral"])
            assert "mistral" in working


def test_multi_llm_judge_preflight():
    with patch.dict(os.environ, {"MISTRAL_API_KEY": "mock_key"}, clear=True):
        with patch(
            "youth_escalate_bench.annotation.llm_judge.get_working_providers",
            return_value=["mistral"],
        ):
            judge = MultiLLMJudge(validate_preflight=True)
            assert judge.providers == ["mistral"]


def test_validate_all_providers_function():
    with patch.dict(os.environ, {"MISTRAL_API_KEY": "mock_key"}, clear=True):
        with patch("youth_escalate_bench.llm.router.LLMRouter.call_llm", return_value="OK"):
            report = validate_all_providers(providers=["mistral", "openai"], only_configured=False)
            assert len(report.results) == 2
            assert report.working_models[0]["provider"] == "mistral"
