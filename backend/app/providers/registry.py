from app.config import Settings
from app.providers.base import ProviderExecutionError, ProviderNotConfiguredError, ProviderResult
from app.providers.openai_responses import OpenAIResponsesAdapter


class ProviderRegistry:
    def __init__(self, settings: Settings):
        self._openai = OpenAIResponsesAdapter(settings)

    def ensure_configured(self, provider: str) -> None:
        if provider == "OpenAI" and self._openai.is_configured():
            return
        if provider == "OpenAI":
            raise ProviderNotConfiguredError("OpenAI is not configured on this server.")
        raise ProviderNotConfiguredError(f"{provider} is not enabled on this server.")

    async def execute(self, provider: str, payload: dict, user_id: str) -> ProviderResult:
        self.ensure_configured(provider)
        if provider == "OpenAI":
            return await self._openai.execute(payload, user_id)
        raise ProviderExecutionError("No adapter is available for this provider.")
