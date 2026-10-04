import hashlib
from collections.abc import Callable

import httpx

from app.config import Settings
from app.providers.base import ProviderExecutionError, ProviderNotConfiguredError, ProviderResult


class GroqAdapter:
    """Server-side Groq Cloud API adapter."""

    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(
        self, settings: Settings, client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient
    ):
        self._settings = settings
        self._client_factory = client_factory

    def is_configured(self) -> bool:
        return self._settings.groq_api_key is not None

    async def execute(self, payload: dict, user_id: str) -> ProviderResult:
        if not self.is_configured():
            raise ProviderNotConfiguredError("Groq is not configured on this server.")

        model = payload.get("model") or "llama-3.1-8b-instant"
        messages = [
            {"role": "system", "content": payload.get("system_prompt", "")},
            {"role": "user", "content": payload.get("user_prompt", "")},
        ]
        body = {
            "model": model,
            "messages": messages,
            "temperature": payload.get("temperature", 0.2),
            "max_tokens": payload.get("max_response_tokens", 512),
        }
        headers = {
            "Authorization": f"Bearer {self._settings.groq_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        try:
            async with self._client_factory(timeout=self._settings.provider_timeout_seconds) as client:
                response = await client.post(self.endpoint, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderExecutionError("The Groq provider timed out.") from exc
        except httpx.HTTPError as exc:
            raise ProviderExecutionError("The Groq provider could not be reached.") from exc

        if response.is_error:
            raise ProviderExecutionError(f"Groq API error ({response.status_code}): {response.text[:200]}")

        data = response.json()
        choices = data.get("choices") or []
        text = choices[0]["message"]["content"] if choices else ""
        usage = data.get("usage") or {}
        return ProviderResult(output_text=text, token_estimate=int(usage.get("total_tokens") or 0))
