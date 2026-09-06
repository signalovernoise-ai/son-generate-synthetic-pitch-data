"""Stage cleaner for Skio billing attempts. Reusable across all Skio clients.

The billing-attempt stream is the bridge between subscription state and commerce: a
SUCCEEDED attempt creates a real Shopify order. FAILED, QUEUED and SKIPPED attempts
legitimately have no `shopify_order_id`, so that FK is sparse rather than broken and blank
values are left alone by the orphan check.

Non-final statuses are removed from the staged table so downstream revenue work counts
billing once; the dunning volume is reported in the notes so it is not lost.
"""

from __future__ import annotations

import pandas as pd

from ..cleaning_common import DatasetSpec


def flag_dunning_retries(df: pd.DataFrame, report) -> pd.DataFrame:
    """Attempts tried more than once are dunning retries — the usual origin of
    duplicate-looking orders in a subscription store."""
    tried = pd.to_numeric(df.get("attempt_number"), errors="coerce")
    if tried is None:
        return df
    retried = int((tried > 1).sum())
    if retried:
        codes = ""
        if "error_code" in df.columns:
            top = df.loc[tried > 1, "error_code"].astype("string").str.strip()
            top = top[top.notna() & (top != "")].value_counts().head(3)
            if len(top):
                codes = " — top codes: " + ", ".join(f"{k} ({v:,})" for k, v in top.items())
        report.record(
            "dunning_retry", retried, "flagged",
            "attempt_number > 1 (retained; expect duplicate-looking commerce orders nearby)" + codes,
        )
    return df


SPEC = DatasetSpec(
    name="skio_subscription_orders.csv",
    role="subscription_orders",
    source_files=["skio_subscription_orders.csv"],
    key="id",
    required=["id", "subscription_id", "created_at"],
    timestamp_cols=["scheduled_at", "processed_at", "created_at", "updated_at", "next_retry_at"],
    reversal_pairs=[("scheduled_at", "processed_at"), ("created_at", "updated_at")],
    primary_timestamp="created_at",
    amount_col="total_price",
    amount_bounds=(0.0, 5000.0),
    upper_cols=["currency"],
    lower_enum_cols=["origin", "status", "error_code", "tags"],
    status_col="status",
    keep_statuses={"succeeded"},
    fks=[
        ("shopify_order_id", "orders", "id"),
        ("shopify_customer_id", "customers", "id"),
        ("subscription_id", "subscriptions", "id"),
    ],
    provides_keys=["id"],
    pre_hooks=[flag_dunning_retries],
    static_notes=[
        "origin separates the subscription's first order (checkout) from renewals (recurring). "
        "Use it rather than re-deriving first-vs-repeat from order dates.",
        "error_code is populated only on failed attempts. Blank elsewhere is meaningful, not missing.",
        "shipping_price is carried separately and stays out of AOV, per metric-definitions.md.",
        "Recurring attempts are processed server-side with no browser session, so the orders they "
        "create will not appear in web-analytics purchase events. Check coverage before using "
        "web analytics for repeat-rate or LTV.",
    ],
)
