"""Tests for LLM API key discovery and router."""

import os
from unittest.mock import patch

from youth_escalate_bench.llm.keys import (
    get_available_providers,
    get_llm_config,
    is_provider_configured,
)
from youth_escalate_bench.llm.router import LLMRouter


def test_llm_config_structure():
    config = get_llm_config()
    assert "env_file" in config
    assert "keys_detected" in config
    assert "selected_provider" in config
    assert "openai" in config["keys_detected"]
    assert "anthropic" in config["keys_detected"]
    assert "gemini" in config["keys_detected"]
    assert "groq" in config["keys_detected"]
    assert "xai" in config["keys_detected"]
    assert "qwen" in config["keys_detected"]
    assert "glm" in config["keys_detected"]
    assert "openrouter" in config["keys_detected"]


def test_key_auto_detection():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123456789"}, clear=False):
        assert is_provider_configured("openai")
        providers = get_available_providers()
        assert "openai" in providers

    with patch.dict(os.environ, {"XAI_API_KEY": "xai-test123456789"}, clear=False):
        assert is_provider_configured("xai")
        assert is_provider_configured("grok")

    with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-qwen123456789"}, clear=False):
        assert is_provider_configured("qwen")

    with patch.dict(os.environ, {"GLM_API_KEY": "glm-test123456789"}, clear=False):
        assert is_provider_configured("glm")

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-test123456789"}, clear=False):
        assert is_provider_configured("openrouter")


def test_groq_priority_auto_selection():
    with patch.dict(
        os.environ,
        {"GROQ_API_KEY": "gsk-test123456789", "DEFAULT_LLM_PROVIDER": "auto"},
        clear=False,
    ):
        config = get_llm_config()
        assert config["selected_provider"] == "groq"


def test_router_missing_key_raises_helpful_error():
    with patch.dict(os.environ, {}, clear=True):
        router = LLMRouter()
        try:
            router.call_llm(prompt="test", provider="openai")
            assert False, "Should raise RuntimeError"
        except RuntimeError as e:
            assert ".env" in str(e)


def test_openrouter_multi_model_configuration():
    from youth_escalate_bench.llm.keys import (
        get_expanded_eval_targets,
        get_openrouter_models,
    )

    with patch.dict(
        os.environ,
        {
            "OPENROUTER_API_KEY": "sk-or-v1-test",
            "OPENROUTER_MODELS": "meta-llama/llama-3.3-70b-instruct, mistralai/mistral-small-24b-instruct-2501, openai/gpt-4o-mini",
        },
        clear=False,
    ):
        models = get_openrouter_models()
        assert len(models) == 3
        assert "openai/gpt-4o-mini" in models
        assert "mistralai/mistral-small-24b-instruct-2501" in models

        targets = get_expanded_eval_targets()
        or_targets = [t for t in targets if t[0] == "openrouter"]
        assert len(or_targets) == 3
        assert ("openrouter", "openai/gpt-4o-mini") in or_targets
