"""LLM Provider and Model Validation Sanity Checker.

Provides pre-flight sanity checks, health probing, latency measurement,
and structured reporting of working vs. failing LLM models before invoking
real context pipelines.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from youth_escalate_bench.llm.keys import (
    PROVIDER_KEY_MAP,
    get_provider_model,
    is_provider_configured,
)
from youth_escalate_bench.llm.router import LLMRouter


@dataclass
class ProviderValidationResult:
    provider: str
    model: str
    is_configured: bool
    is_working: bool
    status: str  # "WORKING", "NOT_CONFIGURED", "AUTH_ERROR", "MODEL_NOT_FOUND", "RATE_LIMITED", "TIMEOUT", "CONNECTION_ERROR", "ERROR"
    latency_ms: float | None = None
    response_sample: str | None = None
    http_status_code: int | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    timestamp: float
    results: list[ProviderValidationResult]

    @property
    def working_models(self) -> list[dict[str, str]]:
        return [
            {
                "provider": r.provider,
                "model": r.model,
                "latency_ms": f"{r.latency_ms:.1f}ms" if r.latency_ms else "N/A",
            }
            for r in self.results
            if r.is_working
        ]

    @property
    def failing_models(self) -> list[dict[str, str]]:
        return [
            {
                "provider": r.provider,
                "model": r.model,
                "status": r.status,
                "error": r.error_message or "Unknown error",
            }
            for r in self.results
            if r.is_configured and not r.is_working
        ]

    @property
    def unconfigured_models(self) -> list[dict[str, str]]:
        return [
            {"provider": r.provider, "model": r.model, "status": r.status}
            for r in self.results
            if not r.is_configured
        ]

    @property
    def working_provider_names(self) -> list[str]:
        return [r.provider for r in self.results if r.is_working]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_tested": len(self.results),
            "working_count": len(self.working_models),
            "failing_count": len(self.failing_models),
            "unconfigured_count": len(self.unconfigured_models),
            "working_models": self.working_models,
            "failing_models": self.failing_models,
            "unconfigured_models": self.unconfigured_models,
            "details": [r.to_dict() for r in self.results],
        }

    def to_markdown_table(self) -> str:
        lines = [
            "| Provider | Configured Model | Status | Latency | Probe Response / Error |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for r in self.results:
            status_icon = (
                "🟢 WORKING"
                if r.is_working
                else ("⚪ NOT SET" if not r.is_configured else "🔴 FAILED")
            )
            latency = f"{r.latency_ms:.0f} ms" if r.latency_ms is not None else "-"
            if r.is_working:
                detail = f"`{(r.response_sample or '').strip()[:45]}`"
            elif not r.is_configured:
                detail = "No API key in .env"
            else:
                err_clean = (r.error_message or r.status).replace("\n", " ")[:60]
                detail = f"*{err_clean}*"
            lines.append(
                f"| **{r.provider}** | `{r.model}` | {status_icon} | {latency} | {detail} |"
            )
        return "\n".join(lines)

    def summary_text(self) -> str:
        lines = [
            "============================================================",
            "YouthEscalateBench — LLM Validation Sanity Check Report",
            "============================================================",
            f"Total Providers Evaluated : {len(self.results)}",
            f"  🟢 Working / Ready      : {len(self.working_models)}",
            f"  🔴 Configured but Failed: {len(self.failing_models)}",
            f"  ⚪ Unconfigured / No Key : {len(self.unconfigured_models)}",
            "------------------------------------------------------------",
        ]
        if self.working_models:
            lines.append("🟢 WORKING MODELS:")
            for m in self.working_models:
                lines.append(
                    f"   ✓ {m['provider']:<12} -> {m['model']} (Latency: {m['latency_ms']})"
                )
        else:
            lines.append("🟢 WORKING MODELS: (None detected or responding)")

        if self.failing_models:
            lines.append("\n🔴 FAILING MODELS:")
            for f in self.failing_models:
                lines.append(
                    f"   ✗ {f['provider']:<12} -> {f['model']} [{f['status']}]: {f['error']}"
                )

        if self.unconfigured_models:
            lines.append("\n⚪ UNCONFIGURED (Set in .env to activate):")
            for u in self.unconfigured_models:
                lines.append(f"   - {u['provider']:<12} -> {u['model']}")

        lines.append("============================================================")
        return "\n".join(lines)

    def save_json(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


def validate_provider(
    provider: str,
    model: str | None = None,
    prompt: str = "Ping. Respond strictly with the single word 'OK'.",
    timeout: float = 10.0,
) -> ProviderValidationResult:
    """Run sanity validation probe against a single LLM provider."""
    p_norm = provider.lower()
    if p_norm == "grok":
        p_norm = "xai"

    configured = is_provider_configured(p_norm)
    target_model = model or get_provider_model(p_norm)

    if not configured:
        return ProviderValidationResult(
            provider=p_norm,
            model=target_model,
            is_configured=False,
            is_working=False,
            status="NOT_CONFIGURED",
            error_message=f"No API key or endpoint configured in .env for provider '{p_norm}'",
        )

    router = LLMRouter(timeout=timeout)
    start_time = time.perf_counter()

    try:
        response = router.call_llm(
            prompt=prompt,
            provider=p_norm,
            model=target_model,
            temperature=0.0,
        )
        latency = (time.perf_counter() - start_time) * 1000.0
        return ProviderValidationResult(
            provider=p_norm,
            model=target_model,
            is_configured=True,
            is_working=True,
            status="WORKING",
            latency_ms=latency,
            response_sample=response.strip().replace("\n", " ")[:120],
        )

    except httpx.HTTPStatusError as e:
        latency = (time.perf_counter() - start_time) * 1000.0
        code = e.response.status_code
        if code in (401, 403):
            status = "AUTH_ERROR"
        elif code == 404:
            status = "MODEL_NOT_FOUND"
        elif code == 429:
            status = "RATE_LIMITED"
        else:
            status = f"HTTP_{code}"

        err_body = e.response.text[:200].strip() if e.response.text else e.response.reason_phrase
        return ProviderValidationResult(
            provider=p_norm,
            model=target_model,
            is_configured=True,
            is_working=False,
            status=status,
            latency_ms=latency,
            http_status_code=code,
            error_message=f"HTTP {code}: {err_body}",
        )

    except httpx.TimeoutException:
        latency = (time.perf_counter() - start_time) * 1000.0
        return ProviderValidationResult(
            provider=p_norm,
            model=target_model,
            is_configured=True,
            is_working=False,
            status="TIMEOUT",
            latency_ms=latency,
            error_message=f"Request timed out after {timeout:.1f}s",
        )

    except (httpx.ConnectError, httpx.NetworkError) as e:
        latency = (time.perf_counter() - start_time) * 1000.0
        return ProviderValidationResult(
            provider=p_norm,
            model=target_model,
            is_configured=True,
            is_working=False,
            status="CONNECTION_ERROR",
            latency_ms=latency,
            error_message=str(e),
        )

    except NotImplementedError as e:
        return ProviderValidationResult(
            provider=p_norm,
            model=target_model,
            is_configured=True,
            is_working=False,
            status="NOT_IMPLEMENTED",
            error_message=str(e),
        )

    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000.0
        return ProviderValidationResult(
            provider=p_norm,
            model=target_model,
            is_configured=True,
            is_working=False,
            status="ERROR",
            latency_ms=latency,
            error_message=f"{type(e).__name__}: {str(e)}",
        )


def validate_all_providers(
    providers: list[str] | None = None,
    only_configured: bool = False,
    timeout: float = 10.0,
) -> ValidationReport:
    """Validate all or specified LLM providers and generate a comprehensive validation report."""
    target_providers = providers or list(PROVIDER_KEY_MAP.keys())
    results: list[ProviderValidationResult] = []

    from youth_escalate_bench.llm.keys import get_openrouter_models

    for p in target_providers:
        if only_configured and not is_provider_configured(p):
            continue
        if p == "openrouter" and is_provider_configured(p):
            for model in get_openrouter_models():
                res = validate_provider(provider="openrouter", model=model, timeout=timeout)
                results.append(res)
        else:
            res = validate_provider(provider=p, timeout=timeout)
            results.append(res)

    return ValidationReport(timestamp=time.time(), results=results)


def get_working_providers(
    providers: list[str] | None = None,
    timeout: float = 10.0,
) -> list[str]:
    """Return list of provider names that are configured and verified healthy via sanity check."""
    report = validate_all_providers(providers=providers, only_configured=True, timeout=timeout)
    return report.working_provider_names
