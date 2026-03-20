"""LLM router with Gemini primary and Groq fallback.

Implements the exact routing and retry policy from PRD Section 11.
All model identifiers and timeouts are read from config, not hardcoded.
"""

import asyncio
import logging

import httpx
import google.generativeai as genai
from groq import AsyncGroq

from config import settings
from core.exceptions import LLMUnavailableError
from core.runtime_llm_settings import get_runtime_llm_settings

logger = logging.getLogger(__name__)

# Retry delay (seconds) for Gemini HTTP 500 before falling to Groq (PRD 11.2)
_GEMINI_500_RETRY_DELAY = 2.0


class LLMRouter:
    """Try Gemini (primary), fall to Groq (fallback) on any failure.

    Routing logic (PRD 11.1):
      - Gemini HTTP 429  → immediately fall to Groq (no retry)
      - Gemini HTTP 500  → 1 retry with 2s delay, then fall to Groq
      - Gemini timeout   → immediately fall to Groq
      - Groq failure     → raise LLMUnavailableError (HTTP 503)

    Returns: (raw_output: str, provider: str)
    """

    def __init__(self) -> None:
        genai.configure(api_key=settings.gemini_api_key)
        self._groq_client = AsyncGroq(api_key=settings.groq_api_key)

    async def call(
        self, prompt: str, session_id: str
    ) -> tuple[str, str]:
        """Attempt Gemini then Groq. Returns (raw_text, provider_name)."""
        runtime = get_runtime_llm_settings()

        raw = await self._try_gemini(prompt, session_id, runtime)
        if raw is not None:
            return raw, "gemini"

        raw = await self._try_groq(prompt, session_id, runtime)
        if raw is not None:
            return raw, "groq"

        raise LLMUnavailableError()

    # ------------------------------------------------------------------
    # Gemini
    # ------------------------------------------------------------------

    async def _try_gemini(
        self, prompt: str, session_id: str, runtime
    ) -> str | None:
        """Call Gemini with the configured timeout. Returns None on any failure."""
        if not runtime.gemini_enabled:
            return None

        model = genai.GenerativeModel(
            model_name=runtime.gemini_model,
            generation_config={
                "temperature": runtime.gemini_temperature,
                "max_output_tokens": runtime.gemini_max_output_tokens,
                "top_p": runtime.top_p,
                "response_mime_type": "application/json",
            },
        )

        try:
            response = await asyncio.wait_for(
                model.generate_content_async(prompt),
                timeout=runtime.llm_timeout_seconds,
            )
            return response.text

        except asyncio.TimeoutError:
            logger.error(
                "Gemini timeout after %ds (session=%s)", runtime.llm_timeout_seconds, session_id
            )
            return None  # Immediately fall to Groq (PRD 11.2)

        except Exception as exc:
            exc_str = str(exc)
            status_code = self._extract_status_code(exc_str)

            if status_code == 429:
                # Rate limit — no retry, fall to Groq immediately (PRD 11.2)
                logger.warning("Gemini 429 rate limit (session=%s)", session_id)
                return None

            if status_code == 500:
                # One retry with 2s delay (PRD 11.2)
                logger.warning(
                    "Gemini 500 error, retrying in 2s (session=%s)", session_id
                )
                await asyncio.sleep(_GEMINI_500_RETRY_DELAY)
                try:
                    response = await asyncio.wait_for(
                        model.generate_content_async(prompt),
                        timeout=runtime.llm_timeout_seconds,
                    )
                    return response.text
                except Exception as retry_exc:
                    logger.error(
                        "Gemini 500 retry also failed (session=%s): %s",
                        session_id, retry_exc,
                    )
                    return None

            logger.error("Gemini unexpected error (session=%s): %s", session_id, exc)
            return None

    # ------------------------------------------------------------------
    # Groq
    # ------------------------------------------------------------------

    async def _try_groq(
        self, prompt: str, session_id: str, runtime
    ) -> str | None:
        """Call Groq with the configured timeout. Returns None on failure."""
        if not runtime.groq_enabled:
            return None

        try:
            response = await asyncio.wait_for(
                self._groq_client.chat.completions.create(
                    model=runtime.groq_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=runtime.groq_temperature,
                    max_tokens=runtime.groq_max_tokens,
                    top_p=runtime.top_p,
                    response_format={"type": "json_object"},
                ),
                timeout=runtime.llm_timeout_seconds,
            )
            content = response.choices[0].message.content
            return content

        except asyncio.TimeoutError:
            logger.error(
                "Groq timeout after %ds (session=%s)", runtime.llm_timeout_seconds, session_id
            )
            return None

        except Exception as exc:
            # Some models/endpoints may not support JSON mode. Retry once without
            # response_format to avoid hard failure on capability mismatch.
            logger.warning("Groq JSON-mode call failed (session=%s): %s", session_id, exc)
            try:
                response = await asyncio.wait_for(
                    self._groq_client.chat.completions.create(
                        model=runtime.groq_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=runtime.groq_temperature,
                        max_tokens=runtime.groq_max_tokens,
                        top_p=runtime.top_p,
                    ),
                    timeout=runtime.llm_timeout_seconds,
                )
                return response.choices[0].message.content
            except Exception as retry_exc:
                logger.error("Groq failed (session=%s): %s", session_id, retry_exc)
                return None

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_status_code(error_message: str) -> int | None:
        """Extract HTTP status code from error message string if present.

        Matches common SDK error string patterns:
          - "400 Bad Request"
          - "HTTP 429"
          - "status: 500"
          - "status_code=429"
        Avoids false positives from large numbers like 4096 (token count) or 5000ms.
        """
        import re
        patterns = [
            r"HTTP[/ ]+(\d{3})\b",          # HTTP 429 / HTTP/1.1 200
            r"\bstatus[_\s:=]+(\d{3})\b",   # status: 429 / status_code=500
            r"\b(4\d{2}|5\d{2})\s+[A-Z]",  # 429 Too Many / 500 Internal (status + reason)
        ]
        for pattern in patterns:
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None
