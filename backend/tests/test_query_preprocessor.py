from pipelines.retrieval.query_preprocessor import normalize_query_for_retrieval


def test_query_preprocessor_corrects_common_finance_typos() -> None:
    query = "pls analys my stocj buget and transections"
    normalized = normalize_query_for_retrieval(query, domain="finance")

    assert "analysis" in normalized
    assert "stock" in normalized
    assert "budget" in normalized
    assert "transactions" in normalized


def test_query_preprocessor_keeps_numbers_and_symbols() -> None:
    query = "compare AAPL 2024 vs 2025 @ 5%"
    normalized = normalize_query_for_retrieval(query, domain="finance")

    assert "2024" in normalized
    assert "2025" in normalized
    assert "@" in normalized
    assert "%" in normalized
