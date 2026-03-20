"""CSV column validation and text serialisation for Finance documents.

The validator converts a normalised Finance DataFrame into a text
representation suitable for chunking and embedding.
"""

import pandas as pd


def dataframe_to_text(df: pd.DataFrame) -> str:
    """Serialise a normalised Finance DataFrame to plain text for embedding.

    Each row becomes a CSV-style line. The result is chunked by the
    RecursiveCharChunker. No LLM is involved in this step.
    """
    lines: list[str] = []

    # Header
    cols = list(df.columns)
    lines.append(", ".join(cols))

    # Rows
    for _, row in df.iterrows():
        parts = []
        for col in cols:
            val = row[col]
            if pd.isnull(val):
                parts.append("")
            elif col == "date":
                parts.append(str(val.date()) if hasattr(val, "date") else str(val))
            elif col == "amount":
                parts.append(f"{val:.2f}")
            else:
                parts.append(str(val))
        lines.append(", ".join(parts))

    return "\n".join(lines)
