import math

from pipelines.ingestion.file_parser import CsvParser


def test_csv_parser_parses_symbol_and_code_amount_formats() -> None:
    parser = CsvParser()
    csv_bytes = (
        "Date,Amount,Category\n"
        "2024-01-01,$1,234.56,Food\n"
        "2024-01-02,EUR 1.234,50,Travel\n"
        "2024-01-03,(₹2,000.00),Bills\n"
    ).encode("utf-8")

    # Quote rows that include commas inside amount so CSV parsing is deterministic.
    csv_bytes = (
        "Date,Amount,Category\n"
        "2024-01-01,\"$1,234.56\",Food\n"
        "2024-01-02,\"EUR 1.234,50\",Travel\n"
        "2024-01-03,\"(₹2,000.00)\",Bills\n"
    ).encode("utf-8")

    df = parser.run(csv_bytes, "currency_formats.csv")

    assert df.shape[0] == 3
    assert "currency" in df.columns
    assert math.isclose(float(df.loc[0, "amount"]), 1234.56, rel_tol=1e-6)
    assert math.isclose(float(df.loc[1, "amount"]), 1234.50, rel_tol=1e-6)
    assert math.isclose(float(df.loc[2, "amount"]), -2000.00, rel_tol=1e-6)
    assert df.loc[0, "currency"] == "USD"
    assert df.loc[1, "currency"] == "EUR"
    assert df.loc[2, "currency"] == "INR"


def test_csv_parser_preserves_explicit_currency_column() -> None:
    parser = CsvParser()
    csv_bytes = (
        "date,amount,currency,category\n"
        "2024-02-01,1250.00,usd,Ops\n"
        "2024-02-02,-42.25,USD,Fees\n"
    ).encode("utf-8")

    df = parser.run(csv_bytes, "with_currency_column.csv")

    assert df.shape[0] == 2
    assert "currency" in df.columns
    assert df.loc[0, "currency"] == "USD"
    assert df.loc[1, "currency"] == "USD"
