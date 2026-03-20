"""LLM output validator.

Validates the raw LLM string response against the mandatory JSON schema
defined in PRD Section 8.1 and 8.4. Implements the repair-and-retry logic
from PRD Section 8.5.
"""

import json
import logging

logger = logging.getLogger(__name__)

_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"insights", "warnings", "recommendations", "data"}
)

# Safe fallback response returned when both attempts fail (PRD 8.5)
_SAFE_FALLBACK: dict = {
    "insights": [],
    "warnings": ["System was unable to generate a valid response. Please try again."],
    "recommendations": [],
    "data": {},
}


class JSONValidationError(Exception):
    """Raised when LLM output fails validation and cannot be repaired."""


class OutputValidator:
    """Parse and validate LLM output against the PRD 8.1 schema."""

    def validate(self, raw_output: str) -> dict:
        """Parse and validate. Raises JSONValidationError on failure.

        Steps (PRD 8.4):
          1. Strip markdown code fences if present
          2. json.loads()
          3. Validate required keys
          4. Validate types
        """
        cleaned = self._strip_fences(raw_output)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            extracted = self._extract_first_json_object(cleaned)
            if extracted is None:
                raise JSONValidationError(f"JSON parse failed: {exc}") from exc
            try:
                parsed = json.loads(extracted)
            except json.JSONDecodeError as extracted_exc:
                raise JSONValidationError(f"JSON parse failed: {extracted_exc}") from extracted_exc

        if not isinstance(parsed, dict):
            raise JSONValidationError("LLM output is not a JSON object")

        missing = _REQUIRED_KEYS - parsed.keys()
        if missing:
            raise JSONValidationError(f"Missing required keys: {missing}")

        if not isinstance(parsed["insights"], list):
            raise JSONValidationError("'insights' must be an array")
        if not isinstance(parsed["warnings"], list):
            raise JSONValidationError("'warnings' must be an array")
        if not isinstance(parsed["recommendations"], list):
            raise JSONValidationError("'recommendations' must be an array")
        if not isinstance(parsed["data"], dict):
            raise JSONValidationError("'data' must be an object")

        def _dict_to_human_text(item: dict) -> str:
            preferred_keys = (
                "description",
                "text",
                "message",
                "summary",
                "recommendation",
                "insight",
                "warning",
            )
            for key in preferred_keys:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            # Fallback: return first non-empty scalar value instead of raw JSON.
            for value in item.values():
                if isinstance(value, (str, int, float, bool)):
                    text = str(value).strip()
                    if text:
                        return text

            return ""

        def _coerce_to_str_list(lst: list) -> list[str]:
            result: list[str] = []
            for item in lst:
                if isinstance(item, str):
                    text = item.strip()
                elif isinstance(item, dict):
                    text = _dict_to_human_text(item)
                else:
                    text = str(item).strip()

                if text:
                    result.append(text)
            return result
        
        parsed["insights"] = _coerce_to_str_list(parsed["insights"])
        parsed["warnings"] = _coerce_to_str_list(parsed["warnings"])
        parsed["recommendations"] = _coerce_to_str_list(parsed["recommendations"])

        return parsed

    def safe_fallback(self) -> dict:
        """Return the safe fallback response (PRD 8.5)."""
        return dict(_SAFE_FALLBACK)

    def _strip_fences(self, text: str) -> str:
        """Remove markdown code fences (``` or ```json) if present (PRD 8.4).

        Uses a regex to correctly handle edge cases:
        - Missing closing fence
        - JSON content that contains backticks
        - Both ```json and ``` openings
        """
        import re
        cleaned = text.strip()
        # Match ```json\n...\n``` or ```\n...\n``` with optional language label
        match = re.search(r"```(?:json)?\s*(.*?)(?:```|$)", cleaned, re.DOTALL)
        if match:
            return match.group(1).strip()
        return cleaned

    def _extract_first_json_object(self, text: str) -> str | None:
        """Extract the first balanced JSON object from text, if present."""
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escaped = False

        for i in range(start, len(text)):
            ch = text[i]

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        return None
