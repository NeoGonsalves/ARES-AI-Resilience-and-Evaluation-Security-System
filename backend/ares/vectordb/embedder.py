"""
Gemini Embedding Client for ARES.

Generates normalized vector embeddings using Google Gemini's embedding endpoint
(default: models/gemini-embedding-001 with outputDimensionality=768).
Supports single text and batch embedding with exponential backoff retries.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from ares.config import Settings, settings as default_settings

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Exception raised when embedding generation fails."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class GeminiEmbedder:
    """
    Asynchronous Gemini text embedder with retry resilience.
    Uses Google Gemini's native embedContent / batchEmbedContents API.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.settings = settings or default_settings
        self._http_client = http_client
        self._owns_http_client = http_client is None
        self.model = self.settings.gemini_embedding_model
        self.dimension = self.settings.qdrant_vector_size

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or getattr(self._http_client, "is_closed", False) is True:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.request_timeout_seconds)
            )
            self._owns_http_client = True
        return self._http_client

    async def close(self) -> None:
        """Close internal HTTP client if owned."""
        if self._owns_http_client and self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string into a float vector of length `dimension`.
        """
        if not text.strip():
            raise ValueError("Cannot embed empty text.")

        if not self.settings.gemini_api_key:
            raise EmbeddingError("GEMINI_API_KEY is not configured.", status_code=401)

        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/{self.model}:embedContent"
            f"?key={self.settings.gemini_api_key}"
        )
        payload = {
            "model": self.model,
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": self.dimension,
        }

        client = await self._get_client()
        retries = 0
        last_exception: Optional[Exception] = None

        while retries <= self.settings.max_retries:
            try:
                response = await client.post(endpoint, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    values = data.get("embedding", {}).get("values", [])
                    if not values:
                        raise EmbeddingError("No embedding values returned in response.")
                    return values

                elif response.status_code == 429:
                    retries += 1
                    wait = min(
                        self.settings.retry_max_wait_seconds,
                        self.settings.retry_min_wait_seconds * (2 ** (retries - 1)),
                    )
                    logger.warning("Gemini embedding rate-limited (429). Retrying in %.2fs...", wait)
                    await asyncio.sleep(wait)
                    continue

                else:
                    raise EmbeddingError(
                        f"Gemini embedding API error ({response.status_code}): {response.text}",
                        status_code=response.status_code,
                    )

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                retries += 1
                last_exception = exc
                wait = min(
                    self.settings.retry_max_wait_seconds,
                    self.settings.retry_min_wait_seconds * (2 ** (retries - 1)),
                )
                logger.warning("Network error calling Gemini embed: %s. Retrying in %.2fs...", exc, wait)
                await asyncio.sleep(wait)

        raise EmbeddingError(f"Failed to generate embedding after {self.settings.max_retries} retries: {last_exception}")

    async def embed_batch(self, texts: List[str], chunk_size: int = 50) -> List[List[float]]:
        """
        Embed a list of text strings in batch.
        Chuncked to avoid exceeding payload limits.
        """
        if not texts:
            return []

        if not self.settings.gemini_api_key:
            raise EmbeddingError("GEMINI_API_KEY is not configured.", status_code=401)

        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/{self.model}:batchEmbedContents"
            f"?key={self.settings.gemini_api_key}"
        )
        client = await self._get_client()
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), chunk_size):
            chunk = texts[i : i + chunk_size]
            requests_payload = [
                {
                    "model": self.model,
                    "content": {"parts": [{"text": t if t.strip() else " "}]},
                    "outputDimensionality": self.dimension,
                }
                for t in chunk
            ]
            payload = {"requests": requests_payload}

            retries = 0
            while retries <= self.settings.max_retries:
                try:
                    response = await client.post(endpoint, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        embeddings = [
                            emb.get("values", []) for emb in data.get("embeddings", [])
                        ]
                        all_embeddings.extend(embeddings)
                        break

                    elif response.status_code == 429:
                        retries += 1
                        wait = min(
                            self.settings.retry_max_wait_seconds,
                            self.settings.retry_min_wait_seconds * (2 ** (retries - 1)),
                        )
                        logger.warning("Gemini batch embed rate-limited (429). Retrying in %.2fs...", wait)
                        await asyncio.sleep(wait)
                        continue

                    else:
                        raise EmbeddingError(
                            f"Gemini batch embedding error ({response.status_code}): {response.text}",
                            status_code=response.status_code,
                        )

                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    retries += 1
                    if retries > self.settings.max_retries:
                        raise EmbeddingError(f"Network failure during batch embed: {exc}")
                    await asyncio.sleep(self.settings.retry_min_wait_seconds)

        return all_embeddings

    def embed_text_sync(self, text: str) -> List[float]:
        """Synchronous wrapper for embed_text."""
        return asyncio.run(self.embed_text(text))

    def embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronous wrapper for embed_batch."""
        return asyncio.run(self.embed_batch(texts))
