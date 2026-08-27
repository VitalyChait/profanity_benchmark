"""Universal LLM client router with automatic provider selection and JSON parsing.

KEY CONFIGURATION LOCATION:
- Set keys in `.env` at repository root.
"""

import json
import re
from typing import Any

import httpx

from youth_escalate_bench.llm.keys import (
    get_llm_config,
    get_provider_key,
    get_provider_model,
    is_provider_configured,
)


class LLMRouter:
    """Dispatches prompt completions to detected LLM providers."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Call active LLM provider and return response text."""
        config = get_llm_config()
        active_provider = provider or config["selected_provider"]

        # Support compound provider strings like "openrouter:openai/gpt-4o-mini"
        if active_provider and ":" in active_provider:
            parts = active_provider.split(":", 1)
            active_provider = parts[0]
            if not model:
                model = parts[1]
        elif (
            active_provider
            and active_provider.startswith("openrouter/")
            and "/" in active_provider[11:]
        ):
            parts_model = active_provider[11:]
            active_provider = "openrouter"
            if not model:
                model = parts_model
        elif (
            active_provider
            and active_provider.startswith("requesty/")
            and "/" in active_provider[9:]
        ):
            parts_model = active_provider[9:]
            active_provider = "requesty"
            if not model:
                model = parts_model

        if active_provider == "none" or not is_provider_configured(active_provider):
            raise RuntimeError(
                f"No API key configured for provider '{active_provider}'. "
                "Please set your API keys in the `.env` file at the repository root."
            )

        active_model = model or get_provider_model(active_provider)
        key = get_provider_key(active_provider) or ""

        if active_provider in (
            "openai",
            "groq",
            "together",
            "deepseek",
            "mistral",
            "xai",
            "grok",
            "qwen",
            "glm",
            "openrouter",
            "requesty",
        ):
            return self._call_openai_compatible(
                prompt=prompt,
                system_prompt=system_prompt,
                provider=active_provider,
                model=active_model,
                api_key=key,
                temperature=temperature,
            )
        elif active_provider == "anthropic":
            return self._call_anthropic(
                prompt=prompt,
                system_prompt=system_prompt,
                model=active_model,
                api_key=key,
                temperature=temperature,
            )
        elif active_provider == "gemini":
            return self._call_gemini(
                prompt=prompt,
                system_prompt=system_prompt,
                model=active_model,
                api_key=key,
                temperature=temperature,
            )
        elif active_provider == "ollama":
            return self._call_ollama(
                prompt=prompt,
                system_prompt=system_prompt,
                model=active_model,
                temperature=temperature,
            )
        else:
            raise NotImplementedError(f"Provider '{active_provider}' is not yet supported.")

    def call_llm_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Query LLM and parse JSON response reliably."""
        json_sys = (
            system_prompt or ""
        ) + "\nYou MUST return valid JSON strictly adhering to the requested format."
        raw_text = self.call_llm(
            prompt=prompt, system_prompt=json_sys, provider=provider, model=model, temperature=0.0
        )

        # Clean markdown codeblocks if present
        clean_text = raw_text.strip()
        if "```json" in clean_text:
            match = re.search(r"```json\s*(.*?)\s*```", clean_text, re.DOTALL)
            if match:
                clean_text = match.group(1)
        elif "```" in clean_text:
            match = re.search(r"```\s*(.*?)\s*```", clean_text, re.DOTALL)
            if match:
                clean_text = match.group(1)

        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            # Try finding first { and last }
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(clean_text[start : end + 1])
            raise ValueError(f"Failed to parse JSON from LLM response: {raw_text}")

    def _call_openai_compatible(
        self,
        prompt: str,
        system_prompt: str | None,
        provider: str,
        model: str,
        api_key: str,
        temperature: float,
    ) -> str:
        endpoints = {
            "openai": "https://api.openai.com/v1/chat/completions",
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "together": "https://api.together.xyz/v1/chat/completions",
            "deepseek": "https://api.deepseek.com/v1/chat/completions",
            "mistral": "https://api.mistral.ai/v1/chat/completions",
            "xai": "https://api.x.ai/v1/chat/completions",
            "grok": "https://api.x.ai/v1/chat/completions",
            "qwen": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
            "glm": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
            "requesty": "https://router.requesty.ai/v1/chat/completions",
        }
        url = endpoints.get(provider, "https://api.openai.com/v1/chat/completions")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content")
            if not content and msg.get("reasoning_content"):
                content = msg["reasoning_content"]
            return content or ""

    def _call_anthropic(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str,
        api_key: str,
        temperature: float,
    ) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": 1024,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]

    def _call_gemini(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str,
        api_key: str,
        temperature: float,
    ) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        contents: list[dict[str, Any]] = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM: {system_prompt}"}]})
            contents.append(
                {"role": "model", "parts": [{"text": "Understood. Proceeding with instructions."}]}
            )
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _call_ollama(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
    ) -> str:
        import os

        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        url = f"{base_url}/api/chat"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature},
            "stream": False,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]


_DEFAULT_ROUTER: LLMRouter | None = None


def get_default_router() -> LLMRouter:
    global _DEFAULT_ROUTER
    if _DEFAULT_ROUTER is None:
        _DEFAULT_ROUTER = LLMRouter()
    return _DEFAULT_ROUTER
