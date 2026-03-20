"""HuggingFace Inference API embedder with Supabase embedding cache.

All embeddings are produced by remote API calls — no local model is loaded
(PRD 1.4, 12.1). Batching is capped at 32 chunks per call (PRD 3.1).
Cache is keyed by SHA-256(text + model_name) (PRD 6.1).
"""

import asyncio
import logging
from typing import Any

import httpx

from config import settings
from core import database
from core.exceptions import EmbeddingServiceUnavailableError

logger = logging.getLogger(__name__)

_HF_API_URL_TEMPLATE = (
    "https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction"
)


class HFEmbedder:
    """Embed a list of texts using the HuggingFace Inference API.

    Handles:
      - Cache lookup before every API call
      - Batched API calls (batch_size = 32)
      - Cache write after successful API call
      - Raises EmbeddingServiceUnavailableError on API failure
    """

    def __init__(self) -> None:
        self._api_url = _HF_API_URL_TEMPLATE.format(model=settings.huggingface_model)
        self._headers = {"Authorization": f"Bearer {settings.huggingface_api_token}"}
        self._batch_size = settings.embedding_batch_size

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed all texts; return vectors in the same order as input.

        Vectors for cache-hit texts are retrieved from Supabase.
        Remaining texts are sent to HF in batches of 32.
        """
        if not texts:
            return []

        vectors: list[list[float] | None] = [None] * len(texts)
        cache_misses: list[tuple[int, str]] = []  # (original_index, text)

        # Phase 1 — check cache for all texts
        cache_checks = await asyncio.gather(
            *(database.get_embedding_cache(text, settings.huggingface_model)
              for text in texts)
        )
        for i, cached_vector in enumerate(cache_checks):
            if cached_vector is not None:
                vectors[i] = cached_vector
            else:
                cache_misses.append((i, texts[i]))

        # Phase 2 — embed cache misses in batches
        if cache_misses:
            miss_indices = [idx for idx, _ in cache_misses]
            miss_texts = [txt for _, txt in cache_misses]
            new_vectors = await self._embed_in_batches(miss_texts)

            # Write new embeddings back to cache and assign to output
            cache_writes = [
                database.set_embedding_cache(
                    text, settings.huggingface_model, vec
                )
                for text, vec in zip(miss_texts, new_vectors)
            ]
            await asyncio.gather(*cache_writes)

            for original_idx, vec in zip(miss_indices, new_vectors):
                vectors[original_idx] = vec

        return vectors  # type: ignore[return-value]

    async def _embed_in_batches(self, texts: list[str]) -> list[list[float]]:
        """Call HF API in batches of `batch_size`. Return flat list of vectors."""
        all_vectors: list[list[float]] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for batch_start in range(0, len(texts), self._batch_size):
                batch = texts[batch_start: batch_start + self._batch_size]
                batch_vectors = await self._call_hf_api(client, batch)
                all_vectors.extend(batch_vectors)

        return all_vectors

    async def _call_hf_api(
        self, client: httpx.AsyncClient, texts: list[str]
    ) -> list[list[float]]:
        """POST a single batch to the HF Inference API.

        The feature-extraction pipeline returns either:
          - list[list[float]]   — one vector per input text
          - list[list[list[float]]] — token-level embeddings (need mean pooling)
        """
        try:
            response = await client.post(
                self._api_url,
                headers=self._headers,
                json={"inputs": texts, "options": {"wait_for_model": True}},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("HF API HTTP error: %s", exc)
            raise EmbeddingServiceUnavailableError(
                f"HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            logger.error("HF API request error: %s", exc)
            raise EmbeddingServiceUnavailableError(str(exc)) from exc

        raw: Any = response.json()

        if not isinstance(raw, list):
            raise EmbeddingServiceUnavailableError(
                "Unexpected HF API response shape"
            )

        return self._normalise_output(raw, len(texts))

    def _normalise_output(
        self, raw: list[Any], expected_count: int
    ) -> list[list[float]]:
        """Normalise HF output to list[list[float]].

        For sentence similarity models, each element is already a float vector.
        For token-level models, each element is a list of token vectors — apply mean pool.
        """
        result: list[list[float]] = []
        for item in raw:
            if isinstance(item, list) and isinstance(item[0], float):
                # Already a flat vector — apply L2 normalization for Qdrant cosine distance
                norm = sum(x * x for x in item) ** 0.5
                normed = [x / norm for x in item] if norm > 0 else item
                result.append(normed)
            elif isinstance(item, list) and isinstance(item[0], list):
                # Token-level — mean pool across tokens
                token_vecs = item
                dim = len(token_vecs[0])
                pooled = [
                    sum(token_vecs[t][d] for t in range(len(token_vecs))) / len(token_vecs)
                    for d in range(dim)
                ]
                
                # Apply L2 normalization to the pooled vector (required for Cosine distance in Qdrant)
                norm = sum(x * x for x in pooled) ** 0.5
                if norm > 0:
                    pooled = [x / norm for x in pooled]
                
                result.append(pooled)
            else:
                raise EmbeddingServiceUnavailableError(
                    f"Unrecognised embedding element shape: {type(item)}"
                )

        if len(result) != expected_count:
            raise EmbeddingServiceUnavailableError(
                f"HF returned {len(result)} vectors for {expected_count} inputs"
            )
        return result
