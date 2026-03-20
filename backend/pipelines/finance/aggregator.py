"""Deterministic chart data computation for Finance CSV files.

All aggregations are pure Python/pandas — no LLM involved (PRD 9.1, 9.3).
The result is a structured dict matching the PRD 9.1 chart_data JSONB schema.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class CsvAggregator:
    """Compute all chart data aggregations from a normalised Finance DataFrame.

    Input DataFrame must have canonical columns produced by CsvParser:
      - date     : datetime64
      - amount   : float64
      - category : str (optional)

    Returns a dict matching PRD Section 9.1 chart_data schema.
    """

    def compute(self, df: pd.DataFrame) -> dict[str, Any]:
        result: dict[str, Any] = {
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

        currency_mode = "unknown"
        dominant_currency: str | None = None
        currency_breakdown: dict[str, int] = {}
        if "currency" in df.columns:
            cleaned_currency = (
                df["currency"]
                .dropna()
                .astype(str)
                .str.strip()
                .str.upper()
            )
            if not cleaned_currency.empty:
                counts = cleaned_currency.value_counts()
                currency_breakdown = {str(k): int(v) for k, v in counts.items()}
                dominant_currency = str(counts.index[0])
                currency_mode = "single" if len(counts.index) == 1 else "mixed"

        # -- Category totals  (PRD 9.3)
        if "category" in df.columns:
            cat_totals = (
                df.groupby("category")["amount"].sum().round(2).to_dict()
            )
            result["category_totals"] = cat_totals
        else:
            result["category_totals"] = {}

        # -- Monthly totals  (PRD 9.3)
        if "date" in df.columns:
            df_indexed = df.set_index("date").sort_index()
            monthly = (
                df_indexed["amount"]
                .resample("ME")
                .sum()
                .round(2)
            )
            result["monthly_trends"] = [
                {"period": str(period.date()), "total": float(total)}
                for period, total in monthly.items()
            ]
        else:
            result["monthly_trends"] = []

        # -- Top categories  (PRD 9.3 — top 5 by ABSOLUTE total amount)
        # Use abs() so that high-spend debit categories (negative sums) rank correctly.
        if "category" in df.columns and result["category_totals"]:
            top = sorted(
                result["category_totals"].items(),
                key=lambda kv: abs(kv[1]),
                reverse=True,
            )[:5]
            result["top_categories"] = [k for k, _ in top]
        else:
            result["top_categories"] = []

        # -- Summary stats  (PRD 9.3)
        total = float(df["amount"].sum().round(2))
        debit_total = float((-df.loc[df["amount"] < 0, "amount"]).sum().round(2))
        credit_total = float((df.loc[df["amount"] > 0, "amount"]).sum().round(2))
        if debit_total > 0:
            total_spent = debit_total
        else:
            # Some datasets encode spends as positive amounts only.
            total_spent = credit_total if credit_total > 0 else 0.0

        num_months = len(result["monthly_trends"])
        avg_monthly = round(total / num_months, 2) if num_months > 0 else 0.0
        avg_monthly_spent = round(total_spent / num_months, 2) if num_months > 0 else 0.0
        highest_category = (
            max(result["category_totals"], key=result["category_totals"].get)
            if result["category_totals"]
            else None
        )

        result["summary_stats"] = {
            "total": total,
            "total_spent": float(round(total_spent, 2)),
            "total_inflow": float(round(credit_total, 2)),
            "avg_monthly": avg_monthly,
            "avg_monthly_spent": avg_monthly_spent,
            "highest_category": highest_category,
            "currency": dominant_currency,
            "currency_mode": currency_mode,
            "currency_breakdown": currency_breakdown,
            # Use abs() to report the single transaction with largest magnitude,
            # regardless of whether it's a debit (negative) or credit (positive).
            "highest_single_transaction": float(df["amount"].abs().max()),
            "lowest_single_transaction": float(df["amount"].abs().min()),
        }

        # -- Chart-ready data for frontend bar / line / pie rendering (PRD 9.4)
        result["bar_chart"] = {
            "labels": list(result["category_totals"].keys()),
            "values": list(result["category_totals"].values()),
        }
        result["line_chart"] = {
            "periods": [item["period"] for item in result["monthly_trends"]],
            "totals": [item["total"] for item in result["monthly_trends"]],
        }
        result["pie_chart"] = {
            "labels": list(result["category_totals"].keys()),
            "values": list(result["category_totals"].values()),
        }

        return result
