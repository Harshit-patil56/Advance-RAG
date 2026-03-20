"""File parsers for each supported file type per domain.

Finance domain  → CSV only       (PRD 4.1, 9.2)
Law domain      → PDF or .txt    (PRD 4.1, 10.2)

Each parser has a single `run()` method that accepts raw bytes and returns
either a cleaned string (PDF/TXT) or a pandas DataFrame (CSV).
No file bytes are written to disk (PRD 14.1).
"""

import io
import logging
import re

import pandas as pd

from core.exceptions import EmptyFileError, MissingRequiredColumnsError, ParseError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column alias maps for Finance CSV  (PRD 9.2)
# ---------------------------------------------------------------------------

_DATE_ALIASES: frozenset[str] = frozenset(
    {"date", "transaction_date", "date_of_transaction"}
)
_AMOUNT_ALIASES: frozenset[str] = frozenset(
    {"amount", "value", "debit", "credit"}
)
_CATEGORY_ALIASES: frozenset[str] = frozenset(
    {"category", "type"}
)
_CURRENCY_ALIASES: frozenset[str] = frozenset(
    {"currency", "currency_code", "curr", "ccy"}
)

_CURRENCY_SYMBOL_TO_CODE: dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
}


def _normalise_columns(df: pd.DataFrame, column_mapping: dict[str, str] | None = None) -> pd.DataFrame:
    """Rename columns to canonical names (date, amount, category).

    If column_mapping is provided, it applies those explicit renames first.
    Matching is case-insensitive. Missing optional columns are ignored.
    Raises MissingRequiredColumnsError if date or amount cannot be found.
    """
    if column_mapping:
        # The user provided an explicit mapping from frontend UI
        df = df.rename(columns=column_mapping)
        
    col_map: dict[str, str] = {}
    lower_cols = {c.lower(): c for c in df.columns}

    # Required
    date_col = next((lower_cols[k] for k in lower_cols if k in _DATE_ALIASES), None)
    amount_col = next((lower_cols[k] for k in lower_cols if k in _AMOUNT_ALIASES), None)

    missing = []
    if amount_col is None:
        missing.append("amount")
    if missing:
        raise MissingRequiredColumnsError(missing, found_columns=list(df.columns))

    if date_col:
        col_map[date_col] = "date"
    col_map[amount_col] = "amount"

    # Optional
    category_col = next((lower_cols[k] for k in lower_cols if k in _CATEGORY_ALIASES), None)
    if category_col:
        col_map[category_col] = "category"

    currency_col = next((lower_cols[k] for k in lower_cols if k in _CURRENCY_ALIASES), None)
    if currency_col:
        col_map[currency_col] = "currency"

    return df.rename(columns=col_map)


def _extract_currency_from_text(value: str) -> str | None:
    text = value.strip().upper()
    for symbol, code in _CURRENCY_SYMBOL_TO_CODE.items():
        if symbol in value:
            return code

    code_match = re.search(r"\b([A-Z]{3})\b", text)
    if code_match:
        return code_match.group(1)

    return None


def _parse_amount_text(value: str) -> float | None:
    s = value.strip()
    if not s:
        return None

    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1]

    s = s.replace(" ", "").replace("\u00A0", "")

    # Remove currency symbols and letter codes before numeric normalization.
    s = re.sub(r"[A-Za-z]{3}", "", s)
    for symbol in _CURRENCY_SYMBOL_TO_CODE:
        s = s.replace(symbol, "")

    if s.startswith("-"):
        is_negative = True
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]

    # Keep only number separators and digits.
    s = re.sub(r"[^0-9,.'-]", "", s)
    s = s.replace("'", "")

    if not s:
        return None

    if "," in s and "." in s:
        # Use the rightmost separator as decimal marker.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "")
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) > 1 and len(parts[-1]) in {1, 2}:
            s = "".join(parts[:-1]) + "." + parts[-1]
        else:
            s = "".join(parts)

    try:
        amount = float(s)
    except ValueError:
        return None

    return -amount if is_negative else amount


def _coerce_amount_column(df: pd.DataFrame, filename: str) -> pd.DataFrame:
    """Convert amount values to float and populate currency when inferable."""
    if pd.api.types.is_numeric_dtype(df["amount"]):
        df["amount"] = pd.to_numeric(df["amount"], errors="raise")
        if "currency" in df.columns:
            df["currency"] = df["currency"].astype(str).str.strip().str.upper()
        return df

    parsed_amounts: list[float] = []
    inferred_currencies: list[str | None] = []
    failed_values: list[str] = []

    for raw in df["amount"].astype(str):
        parsed = _parse_amount_text(raw)
        if parsed is None:
            failed_values.append(raw)
            parsed_amounts.append(float("nan"))
            inferred_currencies.append(None)
            continue

        parsed_amounts.append(parsed)
        inferred_currencies.append(_extract_currency_from_text(raw))

    if failed_values:
        sample = ", ".join(failed_values[:5])
        raise ParseError(
            filename,
            f"'amount' column contains non-numeric values after normalization. Samples: {sample}",
        )

    df["amount"] = pd.to_numeric(parsed_amounts, errors="raise")

    if "currency" in df.columns:
        existing = df["currency"].astype(str).str.strip().str.upper()
        inferred_series = pd.Series(inferred_currencies, index=df.index, dtype="object")
        df["currency"] = existing.where(existing != "", inferred_series)
    elif any(c for c in inferred_currencies):
        df["currency"] = pd.Series(inferred_currencies, index=df.index, dtype="object")

    if "currency" in df.columns:
        df["currency"] = df["currency"].astype(str).str.strip().str.upper()
        df.loc[df["currency"].isin({"", "NAN", "NONE"}), "currency"] = pd.NA

    return df


# ---------------------------------------------------------------------------
# CSV parser
# ---------------------------------------------------------------------------


class CsvParser:
    """Parse a Finance CSV file from raw bytes.

    Steps (PRD 3.1):
      1. read_csv with pandas
      2. Validate required columns (date, amount) via alias matching
      3. Clean NaN and whitespace
      4. Return a normalised DataFrame ready for aggregation + chunking
    """

    def run(self, file_bytes: bytes, filename: str, column_mapping: dict[str, str] | None = None) -> pd.DataFrame:
        if not file_bytes:
            raise EmptyFileError()

        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
        except Exception as exc:
            raise ParseError(filename, f"pandas read_csv failed: {exc}") from exc

        if df.empty:
            raise EmptyFileError()

        # Strip leading/trailing whitespace from string columns
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].str.strip()

        # Normalise to canonical column names and validate required ones
        df = _normalise_columns(df, column_mapping=column_mapping)

        # Remove rows where required columns are NaN
        subset_cols = [c for c in ["date", "amount"] if c in df.columns]
        df.dropna(subset=subset_cols, inplace=True)

        if df.empty:
            raise EmptyFileError()

        # Ensure amount is numeric and infer currency when present.
        df = _coerce_amount_column(df, filename)

        # Parse dates (only if the column exists — budget files may not have dates)
        if "date" in df.columns:
            try:
                df["date"] = pd.to_datetime(df["date"])
            except Exception as exc:
                raise ParseError(
                    filename, f"'date' column cannot be parsed as dates: {exc}"
                ) from exc

        return df


# ---------------------------------------------------------------------------
# PDF parser
# ---------------------------------------------------------------------------

_PAGE_NUMBER_PATTERN = re.compile(r"^\s*\d+\s*$", re.MULTILINE)
_EXCESS_WHITESPACE_PATTERN = re.compile(r"\n{3,}")


class PdfParser:
    """Parse a PDF file from raw bytes and return cleaned plain text.

    Uses PyMuPDF (fitz) as primary. Falls back to pdfplumber on failure.
    Steps follow PRD Section 10.2 exactly:
      1. Extract text page by page
      2. Strip isolated page numbers
      3. Strip repeated headers/footers (heuristic: text appearing on >30% of pages)
      4. Normalise whitespace
      5. Join into a single document string
    """

    def run(self, file_bytes: bytes, filename: str) -> str:
        if not file_bytes:
            raise EmptyFileError()

        text = self._extract_with_pymupdf(file_bytes, filename)
        if not text.strip():
            text = self._extract_with_pdfplumber(file_bytes, filename)

        if not text.strip():
            raise ParseError(filename, "No text could be extracted from PDF")

        text = self._clean(text)
        return text

    def _extract_with_pymupdf(self, file_bytes: bytes, filename: str) -> str:
        try:
            import fitz  # PyMuPDF

            pages: list[str] = []
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    pages.append(page.get_text())
        except Exception as exc:
            logger.warning("PyMuPDF failed for '%s': %s — trying pdfplumber", filename, exc)
            return ""

        return self._strip_repeated_lines(pages)

    def _extract_with_pdfplumber(self, file_bytes: bytes, filename: str) -> str:
        try:
            import pdfplumber

            pages: list[str] = []
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        pages.append(extracted)
        except Exception as exc:
            raise ParseError(filename, f"pdfplumber failed: {exc}") from exc

        return self._strip_repeated_lines(pages)

    def _strip_repeated_lines(self, pages: list[str]) -> str:
        """Remove lines that appear on more than 30% of pages (header/footer heuristic)."""
        if not pages:
            return ""

        threshold = max(1, int(len(pages) * 0.30))
        line_counts: dict[str, int] = {}
        for page_text in pages:
            for line in page_text.splitlines():
                stripped = line.strip()
                if stripped:
                    line_counts[stripped] = line_counts.get(stripped, 0) + 1

        repeated = {line for line, count in line_counts.items() if count >= threshold}

        cleaned_pages = []
        for page_text in pages:
            filtered = [
                line
                for line in page_text.splitlines()
                if line.strip() not in repeated
            ]
            cleaned_pages.append("\n".join(filtered))

        return "\n".join(cleaned_pages)

    def _clean(self, text: str) -> str:
        """Strip isolated page numbers and collapse excess whitespace."""
        text = _PAGE_NUMBER_PATTERN.sub("", text)
        text = _EXCESS_WHITESPACE_PATTERN.sub("\n\n", text)
        return text.strip()


# ---------------------------------------------------------------------------
# TXT parser
# ---------------------------------------------------------------------------


class TxtParser:
    """Parse a plain-text file from raw bytes.

    Steps (PRD 3.1):
      1. Decode as UTF-8 (fallback latin-1)
      2. Strip excessive whitespace
    """

    def run(self, file_bytes: bytes, filename: str) -> str:
        if not file_bytes:
            raise EmptyFileError()

        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = file_bytes.decode("latin-1")
            except Exception as exc:
                raise ParseError(filename, f"Cannot decode file: {exc}") from exc

        text = _EXCESS_WHITESPACE_PATTERN.sub("\n\n", text).strip()

        if not text:
            raise EmptyFileError()

        return text
