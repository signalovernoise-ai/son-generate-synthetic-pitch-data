from __future__ import annotations

from datetime import date
from pathlib import Path
import os
import sqlite3

import pandas as pd

from synthetic_pitch_data.paths import ANALYTICS_ROOT, STAGE_ROOT


AS_OF_DATE = os.getenv("RETENTION_AS_OF_DATE", date.today().isoformat())

OUTPUT_COLUMNS = [
    "first_order_month",
    "months_since_first_order",
    "brand",
    "total_cohort_users",
    "retained_users",
    "retention_rate",
]


RETENTION_SQL = """
WITH ordered AS (
    SELECT
        CAST(user_id AS TEXT) AS user_id,
        CAST(order_id AS TEXT) AS order_id,
        datetime(ordered_at) AS ordered_at,
        ROW_NUMBER() OVER (
            PARTITION BY CAST(user_id AS TEXT)
            ORDER BY datetime(ordered_at), CAST(order_id AS TEXT)
        ) AS order_index
    FROM orders
    WHERE user_id IS NOT NULL
      AND order_id IS NOT NULL
      AND ordered_at IS NOT NULL
),
first_orders AS (
    SELECT
        user_id,
        ordered_at AS first_order_at,
        date(ordered_at, 'start of month') AS first_order_month,
        CAST((julianday(:as_of_date) - julianday(ordered_at)) / 30 AS INTEGER) AS matured_months
    FROM ordered
    WHERE order_index = 1
),
max_maturity AS (
    SELECT MAX(matured_months) AS max_month FROM first_orders
),
retention_months(months_since_first_order) AS (
    SELECT 1
    WHERE (SELECT max_month FROM max_maturity) >= 1
    UNION ALL
    SELECT months_since_first_order + 1
    FROM retention_months
    WHERE months_since_first_order + 1 <= (SELECT max_month FROM max_maturity)
),
eligible_cohort_months AS (
    SELECT
        f.first_order_month,
        m.months_since_first_order,
        COUNT(DISTINCT f.user_id) AS total_cohort_users
    FROM first_orders f
    JOIN retention_months m
      ON f.matured_months >= m.months_since_first_order
    GROUP BY
        f.first_order_month,
        m.months_since_first_order
),
retained_user_months AS (
    SELECT DISTINCT
        f.first_order_month,
        CAST((julianday(o.ordered_at) - julianday(f.first_order_at)) / 30 AS INTEGER)
            AS months_since_first_order,
        o.user_id
    FROM ordered o
    JOIN first_orders f
      ON o.user_id = f.user_id
    WHERE o.order_index > 1
      AND CAST((julianday(o.ordered_at) - julianday(f.first_order_at)) / 30 AS INTEGER) >= 1
),
retained_counts AS (
    SELECT
        first_order_month,
        months_since_first_order,
        COUNT(DISTINCT user_id) AS retained_users
    FROM retained_user_months
    GROUP BY
        first_order_month,
        months_since_first_order
)
SELECT
    e.first_order_month,
    e.months_since_first_order,
    :brand AS brand,
    e.total_cohort_users,
    COALESCE(r.retained_users, 0) AS retained_users,
    CASE
        WHEN e.total_cohort_users = 0 THEN 0.0
        ELSE ROUND(CAST(COALESCE(r.retained_users, 0) AS REAL) / e.total_cohort_users, 6)
    END AS retention_rate
FROM eligible_cohort_months e
LEFT JOIN retained_counts r
  ON e.first_order_month = r.first_order_month
 AND e.months_since_first_order = r.months_since_first_order
ORDER BY
    e.first_order_month,
    e.months_since_first_order
"""


def staged_company_folders() -> list[Path]:
    if not STAGE_ROOT.exists():
        raise FileNotFoundError(f"No staged data folder found at {STAGE_ROOT}")
    return sorted(
        folder
        for folder in STAGE_ROOT.iterdir()
        if folder.is_dir() and (folder / "orders.csv").exists() and (folder / "users.csv").exists()
    )


def build_monthly_retention(company_folder: Path) -> pd.DataFrame:
    orders = pd.read_csv(
        company_folder / "orders.csv",
        dtype={
            "order_id": "string",
            "user_id": "string",
            "ordered_at": "string",
        },
        usecols=["order_id", "user_id", "ordered_at"],
    )

    with sqlite3.connect(":memory:") as conn:
        orders.to_sql("orders", conn, index=False, if_exists="replace")
        result = pd.read_sql_query(
            RETENTION_SQL,
            conn,
            params={"brand": company_folder.name, "as_of_date": AS_OF_DATE},
        )

    return result[OUTPUT_COLUMNS]


def validate_output(df: pd.DataFrame) -> None:
    if list(df.columns) != OUTPUT_COLUMNS:
        raise ValueError(f"Unexpected output columns: {list(df.columns)}")
    if df[OUTPUT_COLUMNS].isna().any().any():
        raise ValueError("Output contains null values in required columns")
    if (df["months_since_first_order"] < 1).any():
        raise ValueError("months_since_first_order must start at 1")
    if (df["retained_users"] > df["total_cohort_users"]).any():
        raise ValueError("retained_users cannot exceed total_cohort_users")
    if ((df["retention_rate"] < 0) | (df["retention_rate"] > 1)).any():
        raise ValueError("retention_rate must be between 0 and 1")


def main() -> None:
    ANALYTICS_ROOT.mkdir(parents=True, exist_ok=True)
    for company_folder in staged_company_folders():
        retention = build_monthly_retention(company_folder)
        validate_output(retention)

        output_dir = ANALYTICS_ROOT / company_folder.name
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "monthly_cohort_retention.csv"
        retention.to_csv(output_path, index=False)
        print(f"{company_folder.name}: wrote {len(retention):,} rows to {output_path}")


if __name__ == "__main__":
    main()
