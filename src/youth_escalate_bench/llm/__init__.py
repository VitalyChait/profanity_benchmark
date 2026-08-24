"""Centralized LLM API key discovery and model router.

KEY LOCATION:
Set your LLM API keys in the `.env` file at the root of the repository.
See `.env.example` for all supported providers and models.
"""

from youth_escalate_bench.llm.keys import (
    ENV_FILE_PATH,
    get_active_keys,
    get_available_providers,
    get_llm_config,
    is_provider_configured,
)
from youth_escalate_bench.llm.router import LLMRouter, get_default_router
from youth_escalate_bench.llm.validator import (
    ProviderValidationResult,
    ValidationReport,
    get_working_providers,
    validate_all_providers,
    validate_provider,
)

__all__ = [
    "ENV_FILE_PATH",
    "get_active_keys",
    "get_available_providers",
    "get_llm_config",
    "is_provider_configured",
    "LLMRouter",
    "get_default_router",
    "ProviderValidationResult",
    "ValidationReport",
    "validate_provider",
    "validate_all_providers",
    "get_working_providers",
]

