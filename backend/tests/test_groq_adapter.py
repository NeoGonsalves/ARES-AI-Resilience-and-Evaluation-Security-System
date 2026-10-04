import asyncio
import json

import httpx

from app.config import Settings
from app.providers.groq_provider import GroqAdapter


def test_groq_adapter_executes_successfully() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Groq response."}}],
                "usage": {"total_tokens": 25},
            },
        )

    transport = httpx.MockTransport(handler)
    adapter = GroqAdapter(
        Settings(groq_api_key="gsk-test-key"),
        client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
    )
    result = asyncio.run(
        adapter.execute(
            {
                "model": "llama-3.1-8b-instant",
                "system_prompt": "You are a red-team assistant.",
                "user_prompt": "Test attack",
                "temperature": 0.0,
                "max_response_tokens": 128,
            },
            "user-123",
        )
    )

    body = json.loads(seen["request"].content)
    assert seen["request"].url == "https://api.groq.com/openai/v1/chat/completions"
    assert body["model"] == "llama-3.1-8b-instant"
    assert body["messages"][0]["content"] == "You are a red-team assistant."
    assert result.output_text == "Groq response."
    assert result.token_estimate == 25
