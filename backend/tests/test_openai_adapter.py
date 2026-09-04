import asyncio

import httpx

from app.config import Settings
from app.providers.openai_responses import OpenAIResponsesAdapter


def test_openai_responses_adapter_uses_ephemeral_response_storage() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(
            200,
            json={
                "output": [{"content": [{"type": "output_text", "text": "Safe response."}]}],
                "usage": {"total_tokens": 17},
            },
        )

    transport = httpx.MockTransport(handler)
    adapter = OpenAIResponsesAdapter(
        Settings(openai_api_key="test-key"),
        client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
    )
    result = asyncio.run(
        adapter.execute(
            {
                "model": "gpt-4.1-mini",
                "system_prompt": "Keep customer data private.",
                "user_prompt": "Help me reset my password.",
                "temperature": 0.2,
                "max_response_tokens": 256,
            },
            "user-123",
        )
    )

    body = __import__("json").loads(seen["request"].content)
    assert seen["request"].url == "https://api.openai.com/v1/responses"
    assert body["store"] is False
    assert body["instructions"] == "Keep customer data private."
    assert result.output_text == "Safe response."
    assert result.token_estimate == 17
