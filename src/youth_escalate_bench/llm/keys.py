"""Designated LLM API Key discovery and environment loader.

KEY CONFIGURATION LOCATION:
- File: `.env` at repository root: `/home/vitaly/uni/research/profanity_benchmark/.env`
- Template: `.env.example`
"""

import os
from pathlib import Path
from typing import Any

# Locate root directory and designated .env file
_ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE_PATH = _ROOT_DIR / ".env"
ENV_EXAMPLE_PATH = _ROOT_DIR / ".env.example"


def load_env_file() -> None:
    """Auto-load environment variables from the designated .env file."""
    # Check current working directory or repository root
    candidates = [
        Path.cwd() / ".env",
        ENV_FILE_PATH,
    ]
    for env_path in candidates:
        if env_path.exists():
            try:
                # Use python-dotenv if available
                from dotenv import load_dotenv

                load_dotenv(dotenv_path=env_path, override=False)
                return
            except ImportError:
                # Fallback manual parser
                with env_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("\"'")
                            if k and k not in os.environ and v:
                                os.environ[k] = v
                return


# Auto-load on import
load_env_file()

PROVIDER_KEY_MAP: dict[str, list[str]] = {
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "xai": ["XAI_API_KEY", "GROK_API_KEY"],
    "qwen": ["DASHSCOPE_API_KEY", "QWEN_API_KEY", "ALIBABA_API_KEY"],
    "glm": ["GLM_API_KEY", "ZHIPUAI_API_KEY", "BIGMODEL_API_KEY"],
    "groq": ["GROQ_API_KEY"],
    "deepseek": ["DEEPSEEK_API_KEY"],
    "mistral": ["MISTRAL_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY"],
    "huggingface": ["HF_TOKEN", "HUGGINGFACE_API_KEY"],
    "together": ["TOGETHER_API_KEY"],
    "cohere": ["COHERE_API_KEY"],
    "ollama": ["OLLAMA_BASE_URL"],
}

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "gemini": "gemini-1.5-flash",
    "xai": "grok-2-latest",
    "grok": "grok-2-latest",
    "qwen": "qwen-plus",
    "glm": "glm-4-flash",
    "groq": "llama-3.1-8b-instant",
    "deepseek": "deepseek-chat",
    "mistral": "mistral-small-latest",
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "huggingface": "meta-llama/Llama-Guard-3-1B",
    "together": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "cohere": "command-r-08-2024",
    "ollama": "llama3.2:3b",
}


def get_llm_config() -> dict[str, Any]:
    """Inspect and return current LLM configuration and detected active keys."""
    load_env_file()
    active_providers: list[str] = []
    keys_detected: dict[str, bool] = {}

    for provider, env_vars in PROVIDER_KEY_MAP.items():
        found = False
        for var in env_vars:
            val = os.environ.get(var, "").strip()
            if val:
                found = True
                break
        keys_detected[provider] = found
        if found:
            active_providers.append(provider)

    default_provider = os.environ.get("DEFAULT_LLM_PROVIDER", "auto").strip().lower()
    selected_provider = default_provider
    if default_provider == "auto":
        # Priority order
        priority = [
            "groq",
            "openai",
            "anthropic",
            "gemini",
            "xai",
            "qwen",
            "glm",
            "openrouter",
            "ollama",
            "huggingface",
            "together",
            "deepseek",
            "mistral",
            "cohere",
        ]
        for p in priority:
            if keys_detected.get(p):
                selected_provider = p
                break
        if selected_provider == "auto":
            selected_provider = "none"

    return {
        "env_file": str(ENV_FILE_PATH),
        "env_exists": ENV_FILE_PATH.exists(),
        "keys_detected": keys_detected,
        "active_providers": active_providers,
        "selected_provider": selected_provider,
        "default_mode": default_provider,
    }


def get_active_keys() -> dict[str, str]:
    """Get dictionary of masked active keys for display/logging."""
    load_env_file()
    result = {}
    for provider, env_vars in PROVIDER_KEY_MAP.items():
        for var in env_vars:
            val = os.environ.get(var, "").strip()
            if val:
                masked = val[:4] + "..." + val[-3:] if len(val) > 8 else "***"
                result[provider] = f"{var}={masked}"
                break
    return result


def get_available_providers() -> list[str]:
    """List of all providers with an active API key or configured endpoint."""
    config = get_llm_config()
    return config["active_providers"]


def is_provider_configured(provider: str) -> bool:
    """Check whether a specific provider has a valid key/endpoint configured."""
    load_env_file()
    p = provider.lower()
    if p == "grok":
        p = "xai"
    env_vars = PROVIDER_KEY_MAP.get(p, [])
    return any(bool(os.environ.get(var, "").strip()) for var in env_vars)


def get_provider_key(provider: str) -> str | None:
    """Get raw key for a provider."""
    load_env_file()
    p = provider.lower()
    if p == "grok":
        p = "xai"
    for var in PROVIDER_KEY_MAP.get(p, []):
        val = os.environ.get(var, "").strip()
        if val:
            return val
    return None


def get_provider_model(provider: str) -> str:
    """Get model name configured for a provider."""
    load_env_file()
    p = provider.lower()
    model_env_aliases = {
        "xai": ["XAI_MODEL", "GROK_MODEL"],
        "grok": ["GROK_MODEL", "XAI_MODEL"],
        "qwen": ["QWEN_MODEL", "DASHSCOPE_MODEL"],
        "glm": ["GLM_MODEL", "ZHIPUAI_MODEL", "BIGMODEL_MODEL"],
        "openrouter": ["OPENROUTER_MODEL", "OPEN_ROUTER_MODEL"],
        "gemini": ["GEMINI_MODEL", "GOOGLE_MODEL"],
        "huggingface": ["HUGGINGFACE_MODEL", "HF_MODEL"],
    }
    candidates = model_env_aliases.get(p, [f"{provider.upper()}_MODEL"])
    for var in candidates:
        val = os.environ.get(var, "").strip()
        if val:
            return val
    return DEFAULT_MODELS.get(p, "default")
