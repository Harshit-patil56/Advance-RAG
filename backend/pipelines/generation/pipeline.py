"""Generation pipeline orchestrator.

Wires together: prompt_builder → llm_router → validator (with retry).
Implements the repair-and-retry logic from PRD Section 8.5.
"""

import hashlib
import logging

from pipelines.generation.llm_router import LLMRouter
from pipelines.generation.prompt_builder import REPAIR_PROMPT, PromptBuilder
from pipelines.generation.validator import JSONValidationError, OutputValidator

logger = logging.getLogger(__name__)


class GenerationPipeline:
    """Orchestrate prompt construction, LLM call, and output validation.

    On first validation failure: send repair prompt (PRD 8.5).
    On second failure: return safe fallback and log both events.
    """

    def __init__(self) -> None:
        self._prompt_builder = PromptBuilder()
        self._llm_router = LLMRouter()
        self._validator = OutputValidator()

    async def run(
        self,
        domain: str,
        query: str,
        chunks: list[dict],
        summary: str | None,
        recent_messages: list[dict],
        session_id: str,
    ) -> tuple[dict, str]:
        """Build prompt, call LLM, validate, retry once if needed.

        Returns:
            (validated_response_dict, llm_provider_name)
        """
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]

        prompt = self._prompt_builder.build(
            domain=domain,
            query=query,
            chunks=chunks,
            summary=summary,
            recent_messages=recent_messages,
        )

        # First attempt
        raw_output, provider = await self._llm_router.call(prompt, session_id)
        try:
            validated = self._validator.validate(raw_output)
            return validated, provider
        except JSONValidationError as first_err:
            logger.warning(
                "First validation attempt failed (session=%s, query_hash=%s): %s | raw(500)=%.500s",
                session_id,
                query_hash,
                first_err,
                raw_output,
            )

        # Second attempt — send repair prompt (PRD 8.5)
        repair_prompt = f"{REPAIR_PROMPT}\n\nOriginal output:\n{raw_output}"
        raw_output_2, provider = await self._llm_router.call(repair_prompt, session_id)
        try:
            validated = self._validator.validate(raw_output_2)
            return validated, provider
        except JSONValidationError as second_err:
            logger.error(
                "Second validation attempt failed (session=%s, query_hash=%s): %s | raw(500)=%.500s",
                session_id,
                query_hash,
                second_err,
                raw_output_2,
            )

        # Both failed — return safe fallback (PRD 8.5)
        return self._validator.safe_fallback(), provider
