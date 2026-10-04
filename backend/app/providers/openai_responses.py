import hashlib
from collections.abc import Callable

import httpx

from app.config import Settings
from app.providers.base import ProviderExecutionError, ProviderNotConfiguredError, ProviderResult


class OpenAIResponsesAdapter:
    """Server-side OpenAI Responses API adapter. Raw responses are returned only to the in-memory worker."""

    endpoint = "https://api.openai.com/v1/responses"

    def __init__(
        self, settings: Settings, client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient
    ):
        self._settings = settings
        self._client_factory = client_factory

    def is_configured(self) -> bool:
        return self._settings.openai_api_key is not None

    async def execute(self, payload: dict, user_id: str) -> ProviderResult:
        if not self.is_configured():
            raise ProviderNotConfiguredError("OpenAI is not configured on this server.")

        body = {
            "model": payload["model"],
            "instructions": payload["system_prompt"],
            "input": [{"role": "user", "content": payload["user_prompt"]}],
            "temperature": payload["temperature"],
            "max_output_tokens": payload["max_response_tokens"],
            "store": False,
            "safety_identifier": hashlib.sha256(user_id.encode()).hexdigest()[:64],
        }
        headers = {"Authorization": f"Bearer {self._settings.openai_api_key.get_secret_value()}"}
        try:
            async with self._client_factory(timeout=self._settings.provider_timeout_seconds) as client:
                response = await client.post(self.endpoint, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderExecutionError("The provider timed out.") from exc
        except httpx.HTTPError as exc:
            raise ProviderExecutionError("The provider could not be reached.") from exc

        if response.is_error:
            messages = {
                401: "OpenAI rejected the server-side credential.",
                403: "The OpenAI project is not permitted to use this model.",
                404: "The configured OpenAI model is not available to this project.",
                429: "OpenAI returned HTTP 429: the project has reached a rate or quota limit.",
            }
            raise ProviderExecutionError(messages.get(
                response.status_code, "OpenAI could not process the controlled test."
            ))

        data = response.json()
        text = self._output_text(data)
        usage = data.get("usage") or {}
        return ProviderResult(output_text=text, token_estimate=int(usage.get("total_tokens") or 0))

    @staticmethod
    def _output_text(data: dict) -> str:
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        parts: list[str] = []
        for item in data.get("output") or []:
            for content in item.get("content") or []:
                if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                    parts.append(content["text"])
        if not parts:
            raise ProviderExecutionError("The provider returned no text for analysis.")
        return "\n".join(parts)
