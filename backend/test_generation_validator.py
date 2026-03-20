from pipelines.generation.validator import OutputValidator


def test_validator_extracts_json_from_wrapped_text() -> None:
    validator = OutputValidator()
    raw = (
        "Here is your result:\n"
        "```json\n"
        "{\n"
        "  \"insights\": [\"Total transactions: 24\"],\n"
        "  \"warnings\": [],\n"
        "  \"recommendations\": [\"Review monthly spikes\"],\n"
        "  \"data\": {\"count\": 24}\n"
        "}\n"
        "```\n"
        "Thanks."
    )

    parsed = validator.validate(raw)

    assert parsed["insights"] == ["Total transactions: 24"]
    assert parsed["warnings"] == []
    assert parsed["recommendations"] == ["Review monthly spikes"]
    assert parsed["data"] == {"count": 24}
